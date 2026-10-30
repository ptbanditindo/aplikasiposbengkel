"""Engine SQLite, session factory, dan dependency FastAPI."""
from __future__ import annotations

from pathlib import Path
from typing import Generator, Optional

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from config import BASE_DIR, settings
from database.base import Base


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


def _apply_sqlite_migrations(bind: Engine) -> None:
    """Migrasi ringan untuk database lama tanpa alat migrasi eksternal."""
    if not str(bind.url).startswith("sqlite"):
        return

    with bind.begin() as conn:
        tables = {
            row[0]
            for row in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if "service_parts" not in tables:
            return

        columns = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(service_parts)")
        }
        if "harga_modal" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE service_parts ADD COLUMN harga_modal NUMERIC(14, 2)"
            )

        # Isi snapshot modal untuk nota lama memakai master yang tersedia.
        conn.exec_driver_sql(
            "UPDATE service_parts SET harga_modal = ("
            "SELECT harga_modal FROM stock_items "
            "WHERE stock_items.id = service_parts.stock_item_id"
            ") WHERE harga_modal IS NULL AND stock_item_id IS NOT NULL"
        )


def init_db(bind: Optional[Engine] = None) -> None:
    target = bind or engine
    Base.metadata.create_all(target)
    _apply_sqlite_migrations(target)
