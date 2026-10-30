"""Engine SQLite, session factory, dan dependency FastAPI."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Generator, Optional

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from config import BASE_DIR, settings
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


def _table_columns(conn, table: str) -> set[str]:
    return {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}


LABEL_INDEX_NAME = "ix_vehicle_or_units_label_radiator"


def _index_is_unique(conn, table: str, name: str) -> bool:
    for row in conn.exec_driver_sql(f"PRAGMA index_list({table})"):
        if row[1] == name:
            return bool(row[2])
    return False


def _has_duplicate_labels(conn) -> bool:
    return (
        conn.exec_driver_sql(
            "SELECT 1 FROM vehicle_or_units "
            "WHERE label_radiator IS NOT NULL "
            "GROUP BY label_radiator HAVING COUNT(*) > 1 LIMIT 1"
        ).first()
        is not None
    )


def _pending_schema_changes(conn, tables: set[str]) -> list[str]:
    pending: list[str] = []
    if "service_parts" in tables and "harga_modal" not in _table_columns(conn, "service_parts"):
        pending.append("kolom service_parts.harga_modal")
    if "service_records" in tables and "request_id" not in _table_columns(
        conn, "service_records"
    ):
        pending.append("kolom service_records.request_id")
    if any(table in tables for table in CORE_TABLES) and "nota_counters" not in tables:
        pending.append("tabel nota_counters")
    if (
        "vehicle_or_units" in tables
        and not _index_is_unique(conn, "vehicle_or_units", LABEL_INDEX_NAME)
        and not _has_duplicate_labels(conn)
    ):
        pending.append("indeks unik label radiator")
    return pending


def _has_existing_data(conn, tables: set[str]) -> bool:
    for table in CORE_TABLES:
        if table in tables:
            if conn.exec_driver_sql(f"SELECT 1 FROM {table} LIMIT 1").first():
                return True
    return False


def _backup_before_migration(bind: Engine) -> None:
    """Buat salinan database berisi data sebelum perubahan skema pertama."""
    path = _sqlite_file_path(bind)
    if path is None:
        return

    with bind.connect() as conn:
        tables = _table_names(conn)
        pending = _pending_schema_changes(conn, tables)
        has_data = _has_existing_data(conn, tables)

    if pending and has_data:
        from services.backup_service import create_migration_backup

        destination = create_migration_backup(path)
        logger.warning(
            "Backup pra-migrasi dibuat: %s (%s)", destination, ", ".join(pending)
        )


def _apply_sqlite_migrations(bind: Engine) -> None:
    """Migrasi ringan untuk database lama tanpa alat migrasi eksternal."""
    if not str(bind.url).startswith("sqlite"):
        return

    with bind.begin() as conn:
        tables = _table_names(conn)
        if not tables:
            return

        if "service_parts" in tables:
            columns = _table_columns(conn, "service_parts")
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

        if "nota_counters" not in tables:
            conn.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS nota_counters ("
                "tanggal VARCHAR(8) NOT NULL PRIMARY KEY, "
                "terakhir INTEGER NOT NULL DEFAULT 0)"
            )

        if "service_records" in tables:
            columns = _table_columns(conn, "service_records")
            if "request_id" not in columns:
                conn.exec_driver_sql(
                    "ALTER TABLE service_records ADD COLUMN request_id VARCHAR(64)"
                )
            has_duplicate = conn.exec_driver_sql(
                "SELECT 1 FROM service_records "
                "WHERE request_id IS NOT NULL "
                "GROUP BY request_id HAVING COUNT(*) > 1 LIMIT 1"
            ).first()
            if has_duplicate:
                logger.warning(
                    "Indeks unik service_records.request_id dilewati: "
                    "data lama berisi request_id duplikat."
                )
            else:
                conn.exec_driver_sql(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "ix_service_records_request_id "
                    "ON service_records (request_id)"
                )

        if (
            "vehicle_or_units" in tables
            and not _index_is_unique(conn, "vehicle_or_units", LABEL_INDEX_NAME)
        ):
            if _has_duplicate_labels(conn):
                logger.warning(
                    "Indeks unik label radiator dilewati: data lama berisi "
                    "label duplikat. Perbaiki label tersebut lalu mulai ulang."
                )
            else:
                conn.exec_driver_sql(
                    f"DROP INDEX IF EXISTS {LABEL_INDEX_NAME}"
                )
                conn.exec_driver_sql(
                    f"CREATE UNIQUE INDEX {LABEL_INDEX_NAME} "
                    "ON vehicle_or_units (label_radiator)"
                )


def init_db(bind: Optional[Engine] = None) -> None:
    target = bind or engine
    _backup_before_migration(target)
    Base.metadata.create_all(target)
    _apply_sqlite_migrations(target)
