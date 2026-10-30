"""Migrasi skema SQLite berurutan memakai `PRAGMA user_version`.

Setiap migrasi dijalankan satu kali dan dicatat pada header database. Semua
migrasi yang tertunda dieksekusi dalam satu transaksi: bila salah satu gagal,
perubahan DDL dan data dibatalkan sehingga database lama tetap utuh.
"""
from __future__ import annotations

import logging
from typing import Callable, List, Optional, Sequence, Tuple

from sqlalchemy import Engine

logger = logging.getLogger(__name__)

Migration = Tuple[int, Callable[[object], None]]

LABEL_INDEX_NAME = "ix_vehicle_or_units_label_radiator"

SCHEMA_VERSION = 4


def get_user_version(conn) -> int:
    row = conn.exec_driver_sql("PRAGMA user_version").first()
    return int(row[0]) if row else 0


def _cursor_user_version(cursor) -> int:
    cursor.execute("PRAGMA user_version")
    row = cursor.fetchone()
    return int(row[0]) if row else 0


def _tables(cursor) -> set[str]:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {row[0] for row in cursor.fetchall()}


def _columns(cursor, table: str) -> set[str]:
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def _index_is_unique(cursor, table: str, name: str) -> bool:
    cursor.execute(f"PRAGMA index_list({table})")
    for row in cursor.fetchall():
        if row[1] == name:
            return bool(row[2])
    return False


def _has_duplicate_labels(cursor) -> bool:
    cursor.execute(
        "SELECT 1 FROM vehicle_or_units "
        "WHERE label_radiator IS NOT NULL "
        "GROUP BY label_radiator HAVING COUNT(*) > 1 LIMIT 1"
    )
    return cursor.fetchone() is not None


def _migrate_001_harga_modal(cursor) -> None:
    tables = _tables(cursor)
    if "service_parts" not in tables:
        return
    if "harga_modal" not in _columns(cursor, "service_parts"):
        cursor.execute(
            "ALTER TABLE service_parts ADD COLUMN harga_modal NUMERIC(14, 2)"
        )
    if "stock_items" not in tables:
        return
    # Isi snapshot modal untuk nota lama memakai master yang tersedia.
    cursor.execute(
        "UPDATE service_parts SET harga_modal = ("
        "SELECT harga_modal FROM stock_items "
        "WHERE stock_items.id = service_parts.stock_item_id"
        ") WHERE harga_modal IS NULL AND stock_item_id IS NOT NULL"
    )


def _migrate_002_nota_counters(cursor) -> None:
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS nota_counters ("
        "tanggal VARCHAR(8) NOT NULL PRIMARY KEY, "
        "terakhir INTEGER NOT NULL DEFAULT 0)"
    )


def _migrate_003_request_id(cursor) -> None:
    if "service_records" not in _tables(cursor):
        return
    if "request_id" not in _columns(cursor, "service_records"):
        cursor.execute(
            "ALTER TABLE service_records ADD COLUMN request_id VARCHAR(64)"
        )
    cursor.execute(
        "SELECT 1 FROM service_records "
        "WHERE request_id IS NOT NULL "
        "GROUP BY request_id HAVING COUNT(*) > 1 LIMIT 1"
    )
    if cursor.fetchone() is not None:
        logger.warning(
            "Indeks unik service_records.request_id dilewati: "
            "data lama berisi request_id duplikat."
        )
        return
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_service_records_request_id "
        "ON service_records (request_id)"
    )


def _migrate_004_unique_label(cursor) -> None:
    if "vehicle_or_units" not in _tables(cursor):
        return
    if _index_is_unique(cursor, "vehicle_or_units", LABEL_INDEX_NAME):
        return
    if _has_duplicate_labels(cursor):
        logger.warning(
            "Indeks unik label radiator dilewati: data lama berisi "
            "label duplikat. Perbaiki label tersebut lalu mulai ulang."
        )
        return
    cursor.execute(f"DROP INDEX IF EXISTS {LABEL_INDEX_NAME}")
    cursor.execute(
        f"CREATE UNIQUE INDEX {LABEL_INDEX_NAME} "
        "ON vehicle_or_units (label_radiator)"
    )


MIGRATIONS: List[Migration] = [
    (1, _migrate_001_harga_modal),
    (2, _migrate_002_nota_counters),
    (3, _migrate_003_request_id),
    (4, _migrate_004_unique_label),
]


def apply_migrations(
    bind: Engine,
    migrations: Optional[Sequence[Migration]] = None,
    target_version: Optional[int] = None,
) -> int:
    """Jalankan migrasi yang belum tercatat, secara atomik.

    Mengembalikan versi skema setelah migrasi. Migrasi yang gagal membatalkan
    seluruh perubahan (termasuk `user_version`) sehingga database lama tetap
    dapat dipakai.
    """
    if bind.dialect.name != "sqlite":
        return 0

    active = sorted(
        MIGRATIONS if migrations is None else migrations,
        key=lambda item: item[0],
    )
    target = SCHEMA_VERSION if target_version is None else target_version

    raw = bind.raw_connection()
    cursor = raw.cursor()
    try:
        if getattr(raw, "in_transaction", False):
            raw.rollback()
        cursor.execute("BEGIN IMMEDIATE")
        try:
            current = _cursor_user_version(cursor)
            for version, migrate in active:
                if current < version <= target:
                    migrate(cursor)
                    cursor.execute(f"PRAGMA user_version = {int(version)}")
            raw.commit()
            return _cursor_user_version(cursor)
        except Exception:
            raw.rollback()
            raise
    finally:
        cursor.close()
        raw.close()
