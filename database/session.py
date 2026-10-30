"""Engine SQLite, session factory, dan dependency FastAPI."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Generator, Optional

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from config import BASE_DIR, settings
from database import migrations as schema_migrations
from database.base import Base

logger = logging.getLogger(__name__)

CORE_TABLES = (
    "customers",
    "vehicle_or_units",
    "stock_items",
    "harga_jasa",
    "service_records",
)


def _resolve_sqlite_url(url: str) -> str:
    prefix = "sqlite:///"
    if not url.startswith(prefix) or ":memory:" in url:
        return url
    raw = url[len(prefix):]
    path = Path(raw)
    if not path.is_absolute():
        path = (BASE_DIR / raw).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"{prefix}{path.as_posix()}"


def build_engine(url: Optional[str] = None) -> Engine:
    resolved = _resolve_sqlite_url(url or settings.database_url)
    kwargs = {"future": True, "pool_pre_ping": True}
    if resolved.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}

    engine = create_engine(resolved, **kwargs)

    if resolved.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record):  # pragma: no cover
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    return engine


engine: Engine = build_engine()
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def begin_immediate(db: Session) -> None:
    """Mulai transaksi tulis SQLite dengan RESERVED lock sejak awal.

    Mencegah dua penulis saling menunggu saat meng-upgrade lock (deadlock
    deferred transaction) tanpa memengaruhi transaksi baca biasa.
    """
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))


def _sqlite_file_path(bind: Engine) -> Optional[Path]:
    if not str(bind.url).startswith("sqlite"):
        return None
    database = bind.url.database
    if not database or database == ":memory:":
        return None
    path = Path(database)
    return path if path.exists() else None


def _table_names(conn) -> set[str]:
    return {
        row[0]
        for row in conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }


def _has_existing_data(conn, tables: set[str]) -> bool:
    for table in CORE_TABLES:
        if table in tables:
            if conn.exec_driver_sql(f"SELECT 1 FROM {table} LIMIT 1").first():
                return True
    return False


def _backup_before_migration(bind: Engine) -> None:
    """Buat salinan database berisi data sebelum skema dinaikkan versinya."""
    path = _sqlite_file_path(bind)
    if path is None:
        return

    with bind.connect() as conn:
        current = schema_migrations.get_user_version(conn)
        tables = _table_names(conn)
        has_data = _has_existing_data(conn, tables)

    target = schema_migrations.SCHEMA_VERSION
    if current < target and has_data:
        from services.backup_service import create_migration_backup

        destination = create_migration_backup(path)
        logger.warning(
            "Backup pra-migrasi dibuat: %s (skema %s -> %s)",
            destination,
            current,
            target,
        )


def init_db(bind: Optional[Engine] = None) -> None:
    target = bind or engine
    _backup_before_migration(target)
    Base.metadata.create_all(target)
    schema_migrations.apply_migrations(target)
