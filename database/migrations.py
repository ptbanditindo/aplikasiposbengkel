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

SCHEMA_VERSION = 6


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
    # Backfill data lama dilakukan sekali di migrasi 005 beserta penanda estimasi.


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


def _migrate_005_modal_estimasi(cursor) -> None:
    tables = _tables(cursor)
    if "service_parts" not in tables:
        return
    if "harga_modal_estimasi" not in _columns(cursor, "service_parts"):
        cursor.execute(
            "ALTER TABLE service_parts ADD COLUMN harga_modal_estimasi "
            "BOOLEAN NOT NULL DEFAULT 0"
        )
    if "stock_items" not in tables:
        return
    # Backfill sekali: modal master saat migrasi adalah estimasi, bukan
    # snapshot saat transaksi. Baris dengan snapshot asli tidak disentuh.
    cursor.execute(
        "UPDATE service_parts SET harga_modal = ("
        "SELECT harga_modal FROM stock_items "
        "WHERE stock_items.id = service_parts.stock_item_id"
        "), harga_modal_estimasi = 1 "
        "WHERE harga_modal IS NULL AND stock_item_id IS NOT NULL"
    )


def _add_column(cursor, table: str, column: str, ddl: str) -> None:
    if table not in _tables(cursor):
        return
    if column not in _columns(cursor, table):
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def _migrate_006_void_retur_ledger(cursor) -> None:
    """S-06: status VOID, akumulasi retur, dan ledger pergerakan stok."""
    _add_column(
        cursor,
        "service_records",
        "status",
        "status VARCHAR(16) NOT NULL DEFAULT 'NORMAL'",
    )
    _add_column(cursor, "service_records", "void_reason", "void_reason TEXT")
    _add_column(cursor, "service_records", "voided_at", "voided_at DATETIME")
    _add_column(cursor, "service_records", "voided_by", "voided_by VARCHAR(64)")
    _add_column(
        cursor,
        "service_records",
        "total_retur",
        "total_retur NUMERIC(14, 2) NOT NULL DEFAULT 0",
    )
    _add_column(
        cursor,
        "service_records",
        "total_retur_jasa",
        "total_retur_jasa NUMERIC(14, 2) NOT NULL DEFAULT 0",
    )
    _add_column(
        cursor,
        "service_records",
        "total_retur_part",
        "total_retur_part NUMERIC(14, 2) NOT NULL DEFAULT 0",
    )
    _add_column(
        cursor,
        "service_records",
        "retur_count",
        "retur_count INTEGER NOT NULL DEFAULT 0",
    )
    _add_column(
        cursor,
        "service_parts",
        "jumlah_retur",
        "jumlah_retur INTEGER NOT NULL DEFAULT 0",
    )
    _add_column(
        cursor,
        "service_jobs",
        "jumlah_retur",
        "jumlah_retur INTEGER NOT NULL DEFAULT 0",
    )

    if "service_records" in _tables(cursor):
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS ix_service_records_status "
            "ON service_records (status)"
        )

    cursor.execute(
        "CREATE TABLE IF NOT EXISTS service_returns ("
        "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
        "service_record_id INTEGER NOT NULL, "
        "alasan TEXT NOT NULL, "
        "oleh VARCHAR(64) NOT NULL DEFAULT 'Kasir', "
        "total_nilai NUMERIC(14, 2) NOT NULL DEFAULT 0, "
        "created_at DATETIME NOT NULL, "
        "FOREIGN KEY(service_record_id) REFERENCES service_records (id) "
        "ON DELETE CASCADE)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_service_returns_service_record_id "
        "ON service_returns (service_record_id)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS service_return_items ("
        "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
        "service_return_id INTEGER NOT NULL, "
        "service_part_id INTEGER, "
        "service_job_id INTEGER, "
        "stock_item_id INTEGER, "
        "nama_item VARCHAR(255) NOT NULL, "
        "jumlah INTEGER NOT NULL, "
        "harga_satuan NUMERIC(14, 2) NOT NULL, "
        "harga_modal NUMERIC(14, 2), "
        "subtotal NUMERIC(14, 2) NOT NULL, "
        "FOREIGN KEY(service_return_id) REFERENCES service_returns (id) "
        "ON DELETE CASCADE, "
        "FOREIGN KEY(service_part_id) REFERENCES service_parts (id) "
        "ON DELETE SET NULL, "
        "FOREIGN KEY(service_job_id) REFERENCES service_jobs (id) "
        "ON DELETE SET NULL, "
        "FOREIGN KEY(stock_item_id) REFERENCES stock_items (id) "
        "ON DELETE SET NULL)"
    )
    for column in (
        "service_return_id",
        "service_part_id",
        "service_job_id",
    ):
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS ix_service_return_items_{column} "
            f"ON service_return_items ({column})"
        )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS stock_movements ("
        "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
        "stock_item_id INTEGER, "
        "nama_item VARCHAR(255), "
        "jenis VARCHAR(16) NOT NULL, "
        "jumlah INTEGER NOT NULL, "
        "alasan TEXT, "
        "oleh VARCHAR(64) NOT NULL DEFAULT 'Kasir', "
        "service_record_id INTEGER, "
        "service_return_id INTEGER, "
        "created_at DATETIME NOT NULL, "
        "FOREIGN KEY(stock_item_id) REFERENCES stock_items (id) "
        "ON DELETE SET NULL, "
        "FOREIGN KEY(service_record_id) REFERENCES service_records (id) "
        "ON DELETE SET NULL, "
        "FOREIGN KEY(service_return_id) REFERENCES service_returns (id) "
        "ON DELETE SET NULL)"
    )
    for column in (
        "stock_item_id",
        "jenis",
        "service_record_id",
        "service_return_id",
    ):
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS ix_stock_movements_{column} "
            f"ON stock_movements ({column})"
        )


MIGRATIONS: List[Migration] = [
    (1, _migrate_001_harga_modal),
    (2, _migrate_002_nota_counters),
    (3, _migrate_003_request_id),
    (4, _migrate_004_unique_label),
    (5, _migrate_005_modal_estimasi),
    (6, _migrate_006_void_retur_ledger),
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
