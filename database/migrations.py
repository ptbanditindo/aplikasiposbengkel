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

SCHEMA_VERSION = 46

SYNC_ID_TABLES = (
    "customers",
    "suppliers",
    "supplier_items",
    "supplier_followups",
    "vehicle_or_units",
    "stock_items",
    "stock_barcodes",
    "harga_jasa",
    "employees",
    "employee_debts",
    "salary_payments",
    "service_records",
    "pengerjaan_nota",
    "pengerjaan_nota_events",
    "wa_message_logs",
    "followup_items",
    "followup_events",
    "service_jobs",
    "service_parts",
    "service_returns",
    "service_return_items",
    "stock_movements",
)


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


def _migrate_007_audit_events(cursor) -> None:
    """ARC-15: jejak audit append-only untuk void, retur, dan restore."""
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS audit_events ("
        "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
        "operator_id VARCHAR(64) NOT NULL, "
        "operator_role VARCHAR(16) NOT NULL, "
        "action VARCHAR(32) NOT NULL, "
        "reference_type VARCHAR(32) NOT NULL, "
        "reference_id VARCHAR(64) NOT NULL DEFAULT '', "
        "reason TEXT, "
        "created_at DATETIME NOT NULL)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_events_action "
        "ON audit_events (action)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_events_created_at "
        "ON audit_events (created_at)"
    )


def _migrate_008_payments(cursor) -> None:
    """Tahap 11: status bayar, jatuh tempo, dan buku pembayaran nota."""
    _add_column(
        cursor,
        "service_records",
        "status_bayar",
        "status_bayar VARCHAR(16) NOT NULL DEFAULT 'LUNAS'",
    )
    _add_column(cursor, "service_records", "jatuh_tempo", "jatuh_tempo DATE")
    _add_column(
        cursor,
        "service_records",
        "total_dibayar",
        "total_dibayar NUMERIC(14, 2) NOT NULL DEFAULT 0",
    )
    if "service_records" in _tables(cursor):
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS ix_service_records_status_bayar "
            "ON service_records (status_bayar)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS ix_service_records_jatuh_tempo "
            "ON service_records (jatuh_tempo)"
        )

    cursor.execute(
        "CREATE TABLE IF NOT EXISTS service_payments ("
        "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
        "service_record_id INTEGER NOT NULL, "
        "jenis VARCHAR(16) NOT NULL, "
        "metode VARCHAR(16) NOT NULL, "
        "nominal NUMERIC(14, 2) NOT NULL, "
        "waktu DATETIME NOT NULL, "
        "operator VARCHAR(64) NOT NULL DEFAULT 'Kasir', "
        "catatan TEXT, "
        "request_id VARCHAR(64), "
        "created_at DATETIME NOT NULL, "
        "FOREIGN KEY(service_record_id) REFERENCES service_records (id) "
        "ON DELETE CASCADE)"
    )
    for column in ("service_record_id", "jenis", "waktu"):
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS ix_service_payments_{column} "
            f"ON service_payments ({column})"
        )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_service_payments_request_id "
        "ON service_payments (request_id)"
    )

    if "service_records" not in _tables(cursor):
        return
    # Nota lama dianggap LUNAS sebesar nilai yang sudah dibayar (netto retur).
    # VOID tidak menghasilkan penerimaan dan tidak masuk piutang.
    cursor.execute(
        "UPDATE service_records SET "
        "total_dibayar = CASE WHEN COALESCE(status, 'NORMAL') = 'VOID' THEN 0 "
        "ELSE MAX(COALESCE(total_servis, 0) - COALESCE(total_retur, 0), 0) END, "
        "status_bayar = 'LUNAS'"
    )
    cursor.execute(
        "INSERT INTO service_payments ("
        "service_record_id, jenis, metode, nominal, waktu, operator, catatan, "
        "request_id, created_at) "
        "SELECT r.id, 'PELUNASAN', COALESCE(r.metode_bayar, 'CASH'), "
        "r.total_dibayar, r.waktu_service, 'Kasir', 'Migrasi nota lama', "
        "NULL, COALESCE(r.created_at, r.waktu_service) "
        "FROM service_records r "
        "WHERE r.total_dibayar > 0 AND NOT EXISTS ("
        "SELECT 1 FROM service_payments p WHERE p.service_record_id = r.id)"
    )


def _migrate_009_whatsapp(cursor) -> None:
    """Tahap 12: izin WhatsApp pelanggan dan log upaya membuka WhatsApp."""
    _add_column(
        cursor,
        "customers",
        "wa_consent",
        "wa_consent BOOLEAN NOT NULL DEFAULT 1",
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS wa_message_logs ("
        "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
        "service_record_id INTEGER, "
        "customer_id INTEGER, "
        "nomor_masked VARCHAR(32) NOT NULL, "
        "jenis VARCHAR(16) NOT NULL DEFAULT 'struk', "
        "status VARCHAR(16) NOT NULL, "
        "pesan TEXT, "
        "operator VARCHAR(64) NOT NULL DEFAULT 'Kasir', "
        "created_at DATETIME NOT NULL, "
        "FOREIGN KEY(service_record_id) REFERENCES service_records (id) "
        "ON DELETE CASCADE, "
        "FOREIGN KEY(customer_id) REFERENCES customers (id) "
        "ON DELETE SET NULL)"
    )
    for column in ("service_record_id", "customer_id", "status", "created_at"):
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS ix_wa_message_logs_{column} "
            f"ON wa_message_logs ({column})"
        )


def _migrate_010_followup(cursor) -> None:
    """Tahap 13: interval jasa dan papan follow-up append-only."""
    _add_column(
        cursor,
        "harga_jasa",
        "interval_servis_bulan",
        "interval_servis_bulan INTEGER NOT NULL DEFAULT 0",
    )
    _add_column(
        cursor,
        "service_jobs",
        "interval_servis_bulan",
        "interval_servis_bulan INTEGER NOT NULL DEFAULT 0",
    )
    _add_column(
        cursor,
        "wa_message_logs",
        "jenis",
        "jenis VARCHAR(16) NOT NULL DEFAULT 'struk'",
    )

    cursor.execute(
        "CREATE TABLE IF NOT EXISTS followup_items ("
        "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
        "jenis VARCHAR(24) NOT NULL, "
        "customer_id INTEGER NOT NULL, "
        "unit_id INTEGER, "
        "service_record_id INTEGER, "
        "judul VARCHAR(255) NOT NULL DEFAULT '', "
        "jatuh_tempo DATE, "
        "status VARCHAR(24) NOT NULL DEFAULT 'BARU', "
        "penanggung_jawab VARCHAR(64), "
        "diambil_pada DATETIME, "
        "followup_terakhir DATETIME, "
        "janji_bayar DATE, "
        "alasan_arsip TEXT, "
        "archived_at DATETIME, "
        "created_at DATETIME NOT NULL, "
        "updated_at DATETIME NOT NULL, "
        "FOREIGN KEY(customer_id) REFERENCES customers (id) "
        "ON DELETE CASCADE, "
        "FOREIGN KEY(unit_id) REFERENCES vehicle_or_units (id) "
        "ON DELETE SET NULL, "
        "FOREIGN KEY(service_record_id) REFERENCES service_records (id) "
        "ON DELETE SET NULL)"
    )
    for column in ("jenis", "customer_id", "status", "jatuh_tempo"):
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS ix_followup_items_{column} "
            f"ON followup_items ({column})"
        )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_followup_items_active "
        "ON followup_items (jenis, customer_id) WHERE status != 'ARSIP'"
    )

    cursor.execute(
        "CREATE TABLE IF NOT EXISTS followup_events ("
        "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
        "item_id INTEGER NOT NULL, "
        "from_status VARCHAR(24), "
        "to_status VARCHAR(24) NOT NULL, "
        "alasan TEXT, "
        "operator VARCHAR(64) NOT NULL DEFAULT 'Kasir', "
        "created_at DATETIME NOT NULL, "
        "FOREIGN KEY(item_id) REFERENCES followup_items (id) "
        "ON DELETE CASCADE)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_followup_events_item_id "
        "ON followup_events (item_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_followup_events_created_at "
        "ON followup_events (created_at)"
    )


def _migrate_011_unit_archive(cursor) -> None:
    """P-03: arsip unit (soft delete) agar riwayat nota tetap utuh."""
    _add_column(cursor, "vehicle_or_units", "archived_at", "archived_at DATETIME")


def _migrate_012_part_interval(cursor) -> None:
    """P-10: interval servis berkala untuk sparepart (master + snapshot nota)."""
    _add_column(
        cursor,
        "stock_items",
        "interval_servis_bulan",
        "interval_servis_bulan INTEGER NOT NULL DEFAULT 0",
    )
    _add_column(
        cursor,
        "service_parts",
        "interval_servis_bulan",
        "interval_servis_bulan INTEGER NOT NULL DEFAULT 0",
    )


def _migrate_013_followup_service_date(cursor) -> None:
    """P-12: tanggal service yang disepakati pada follow-up berkala/garansi."""
    _add_column(
        cursor,
        "followup_items",
        "tanggal_service",
        "tanggal_service DATE",
    )


def _migrate_014_record_credit(cursor) -> None:
    """Kredit: jenis bayar tersimpan + nominal rencana pembayaran."""
    if "service_records" not in _tables(cursor):
        return
    _add_column(
        cursor,
        "service_records",
        "jenis_bayar",
        "jenis_bayar VARCHAR(16) NOT NULL DEFAULT 'LUNAS'",
    )
    _add_column(
        cursor,
        "service_records",
        "rencana_bayar",
        "rencana_bayar NUMERIC(14, 2)",
    )
    # Nota lama yang belum lunas adalah DP; belum ada kredit sebelum migrasi ini.
    cursor.execute(
        "UPDATE service_records SET jenis_bayar = 'DP' "
        "WHERE status_bayar = 'BELUM_LUNAS'"
    )


def _migrate_015_pengerjaan_nota(cursor) -> None:
    """Penanda unit ditinggal untuk follow-up kendaraan selesai."""
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS pengerjaan_nota ("
        "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
        "service_record_id INTEGER NOT NULL, "
        "unit_id INTEGER, "
        "customer_id INTEGER, "
        "status_pengerjaan VARCHAR(24) NOT NULL DEFAULT 'SEDANG_DIKERJAKAN', "
        "janji_ambil DATE, "
        "diambil_pada DATETIME, "
        "dibuat_pada DATETIME NOT NULL, "
        "diubah_pada DATETIME NOT NULL, "
        "diubah_oleh VARCHAR(64) NOT NULL DEFAULT 'Kasir', "
        "FOREIGN KEY(service_record_id) REFERENCES service_records (id) "
        "ON DELETE CASCADE, "
        "FOREIGN KEY(unit_id) REFERENCES vehicle_or_units (id) "
        "ON DELETE SET NULL, "
        "FOREIGN KEY(customer_id) REFERENCES customers (id) "
        "ON DELETE SET NULL)"
    )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_pengerjaan_nota_service_record_id "
        "ON pengerjaan_nota (service_record_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_pengerjaan_nota_unit_id "
        "ON pengerjaan_nota (unit_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_pengerjaan_nota_customer_id "
        "ON pengerjaan_nota (customer_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_pengerjaan_nota_status_pengerjaan "
        "ON pengerjaan_nota (status_pengerjaan)"
    )


def _migrate_016_ingat_piutang(cursor) -> None:
    """Penanda pengingat piutang pada satu siklus jatuh tempo."""
    _add_column(
        cursor,
        "service_records",
        "diingatkan_pada",
        "diingatkan_pada DATETIME",
    )


def _migrate_017_hapus_penugasan_followup(cursor) -> None:
    """Bersihkan data penanggung jawab lama; fitur penugasan sudah dihapus."""
    if "followup_items" not in _tables(cursor):
        return
    columns = _columns(cursor, "followup_items")
    if "penanggung_jawab" in columns:
        cursor.execute("UPDATE followup_items SET penanggung_jawab = NULL")
    if "diambil_pada" in columns:
        cursor.execute("UPDATE followup_items SET diambil_pada = NULL")


def _migrate_018_log_pengerjaan(cursor) -> None:
    """Pisahkan log pengerjaan dari piutang dan tautkan log ke item follow-up."""
    _add_column(
        cursor,
        "wa_message_logs",
        "followup_item_id",
        "followup_item_id INTEGER",
    )
    _add_column(
        cursor,
        "followup_items",
        "cycle_started_at",
        "cycle_started_at DATETIME",
    )
    if "wa_message_logs" in _tables(cursor):
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS ix_wa_message_logs_followup_item_id "
            "ON wa_message_logs (followup_item_id)"
        )
    if "followup_items" in _tables(cursor):
        cursor.execute(
            "UPDATE followup_items SET cycle_started_at = created_at "
            "WHERE cycle_started_at IS NULL"
        )



def _migrate_019_pengerjaan_events(cursor) -> None:
    """Riwayat status pengerjaan unit."""
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS pengerjaan_nota_events ("
        "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
        "pengerjaan_id INTEGER NOT NULL, "
        "from_status VARCHAR(24), "
        "to_status VARCHAR(24) NOT NULL, "
        "operator VARCHAR(64) NOT NULL DEFAULT 'Pemilik', "
        "catatan TEXT, "
        "created_at DATETIME NOT NULL, "
        "FOREIGN KEY(pengerjaan_id) REFERENCES pengerjaan_nota (id) "
        "ON DELETE CASCADE)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_pengerjaan_nota_events_pengerjaan_id "
        "ON pengerjaan_nota_events (pengerjaan_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_pengerjaan_nota_events_created_at "
        "ON pengerjaan_nota_events (created_at)"
    )
    cursor.execute(
        "INSERT INTO pengerjaan_nota_events "
        "(pengerjaan_id, from_status, to_status, operator, catatan, created_at) "
        "SELECT p.id, NULL, p.status_pengerjaan, p.diubah_oleh, "
        "'Riwayat awal setelah migrasi.', p.dibuat_pada "
        "FROM pengerjaan_nota p "
        "WHERE NOT EXISTS (SELECT 1 FROM pengerjaan_nota_events e "
        "WHERE e.pengerjaan_id = p.id)"
    )



def _migrate_020_item_identity(cursor) -> None:
    """Identitas follow-up per unit, baris servis, dan nota piutang."""
    _add_column(
        cursor,
        "customers",
        "do_not_contact",
        "do_not_contact BOOLEAN NOT NULL DEFAULT 0",
    )
    _add_column(
        cursor,
        "service_records",
        "piutang_reminder_ke",
        "piutang_reminder_ke INTEGER NOT NULL DEFAULT 0",
    )
    _add_column(
        cursor,
        "service_records",
        "piutang_next_at",
        "piutang_next_at DATETIME",
    )
    _add_column(
        cursor,
        "service_records",
        "piutang_perlu_telepon",
        "piutang_perlu_telepon BOOLEAN NOT NULL DEFAULT 0",
    )
    for column, ddl in (
        ("item_key", "item_key VARCHAR(180)"),
        ("stage", "stage INTEGER NOT NULL DEFAULT 0"),
        ("interval_bulan", "interval_bulan INTEGER"),
        ("item_nama", "item_nama VARCHAR(255)"),
        ("item_kind", "item_kind VARCHAR(24)"),
        ("reference_date", "reference_date DATE"),
        ("no_response_count", "no_response_count INTEGER NOT NULL DEFAULT 0"),
        ("perlu_telepon", "perlu_telepon BOOLEAN NOT NULL DEFAULT 0"),
    ):
        _add_column(cursor, "followup_items", column, ddl)
    if "followup_items" not in _tables(cursor):
        return
    cursor.execute("DROP INDEX IF EXISTS ux_followup_items_active")
    cursor.execute(
        "SELECT id, jenis, customer_id, unit_id, service_record_id, status, created_at "
        "FROM followup_items ORDER BY id"
    )
    rows = cursor.fetchall()
    used = set()
    for item_id, jenis, customer_id, unit_id, record_id, status, created_at in rows:
        key = None
        archive = False
        if jenis == "servis_berkala":
            key = f"servis:legacy:{item_id}"
            archive = status != "ARSIP"
        elif jenis in {"prospek", "garansi"}:
            base = (
                f"lifecycle:unit:{unit_id}"
                if unit_id is not None
                else f"lifecycle:customer:{customer_id}"
            )
            if base in used:
                key = f"lifecycle:legacy:{item_id}"
                archive = status != "ARSIP"
            else:
                key = base
                used.add(base)
        elif jenis == "piutang":
            base = (
                f"piutang:record:{record_id}"
                if record_id is not None
                else f"piutang:customer:{customer_id}"
            )
            if base in used:
                key = f"{base}:legacy:{item_id}"
                archive = status != "ARSIP"
            else:
                key = base
                used.add(base)
        else:
            key = f"other:{item_id}"
        cursor.execute(
            "UPDATE followup_items SET item_key = ?, item_kind = ?, "
            "reference_date = COALESCE(reference_date, substr(created_at, 1, 10)) "
            "WHERE id = ?",
            (key, jenis, item_id),
        )
        if archive:
            cursor.execute(
                "UPDATE followup_items SET status = 'ARSIP', "
                "alasan_arsip = 'Migrasi identitas item.', "
                "archived_at = COALESCE(archived_at, created_at) WHERE id = ?",
                (item_id,),
            )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_followup_items_key_active "
        "ON followup_items (item_key) "
        "WHERE status != 'ARSIP' AND item_key IS NOT NULL"
    )



def _migrate_021_followup_tunda(cursor: Cursor) -> None:
    _add_column(
        cursor,
        "followup_items",
        "tunda_sampai",
        "tunda_sampai DATETIME",
    )


def _migrate_022_stock_minimum(cursor: Cursor) -> None:
    _add_column(
        cursor,
        "stock_items",
        "stok_minimum",
        "stok_minimum INTEGER",
    )


def _migrate_023_suppliers(cursor: Cursor) -> None:
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS suppliers ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "nama VARCHAR(255) NOT NULL, "
        "nomor_hp VARCHAR(64) NOT NULL DEFAULT '', "
        "alamat TEXT, catatan TEXT, "
        "aktif BOOLEAN NOT NULL DEFAULT 1, "
        "created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_suppliers_nama ON suppliers (nama)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_suppliers_aktif ON suppliers (aktif)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS supplier_items ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "supplier_id INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE, "
        "stock_item_id INTEGER NOT NULL REFERENCES stock_items(id) ON DELETE CASCADE)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_supplier_items_supplier_id "
        "ON supplier_items (supplier_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_supplier_items_stock_item_id "
        "ON supplier_items (stock_item_id)"
    )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_supplier_items_pair "
        "ON supplier_items (supplier_id, stock_item_id)"
    )
    _add_column(
        cursor,
        "wa_message_logs",
        "supplier_id",
        "supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL",
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_wa_message_logs_supplier_id "
        "ON wa_message_logs (supplier_id)"
    )


def _migrate_024_employees(cursor: Cursor) -> None:
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS employees ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "nama VARCHAR(255) NOT NULL, "
        "peran VARCHAR(16) NOT NULL DEFAULT 'MEKANIK', "
        "aktif BOOLEAN NOT NULL DEFAULT 1, "
        "nomor_hp VARCHAR(64) NOT NULL DEFAULT '', "
        "catatan TEXT, "
        "komisi_mode VARCHAR(16) NOT NULL DEFAULT 'PERSEN', "
        "komisi_basis VARCHAR(16) NOT NULL DEFAULT 'KEDUANYA', "
        "komisi_nilai NUMERIC(14, 2) NOT NULL DEFAULT 0, "
        "created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_employees_nama ON employees (nama)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_employees_aktif ON employees (aktif)"
    )
    _add_column(
        cursor,
        "service_records",
        "cashier_employee_id",
        "cashier_employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL",
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_service_records_cashier_employee_id "
        "ON service_records (cashier_employee_id)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS service_record_mechanics ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "service_record_id INTEGER NOT NULL REFERENCES service_records(id) ON DELETE CASCADE, "
        "employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE, "
        "urutan INTEGER NOT NULL DEFAULT 0)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_service_record_mechanics_record_id "
        "ON service_record_mechanics (service_record_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_service_record_mechanics_employee_id "
        "ON service_record_mechanics (employee_id)"
    )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_service_record_mechanics_pair "
        "ON service_record_mechanics (service_record_id, employee_id)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS service_record_commissions ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "service_record_id INTEGER NOT NULL REFERENCES service_records(id) ON DELETE CASCADE, "
        "employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE, "
        "nominal NUMERIC(14, 2) NOT NULL)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_service_record_commissions_record_id "
        "ON service_record_commissions (service_record_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_service_record_commissions_employee_id "
        "ON service_record_commissions (employee_id)"
    )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_service_record_commissions_pair "
        "ON service_record_commissions (service_record_id, employee_id)"
    )


def _migrate_025_employee_salary(cursor: Cursor) -> None:
    _add_column(
        cursor,
        "employees",
        "jenis_imbalan",
        "jenis_imbalan VARCHAR(16) NOT NULL DEFAULT 'KOMISI'",
    )
    _add_column(
        cursor,
        "employees",
        "gaji_bulanan",
        "gaji_bulanan NUMERIC(14, 2) NOT NULL DEFAULT 0",
    )


def _migrate_026_salary_payments(cursor: Cursor) -> None:
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS salary_payments ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL, "
        "nama_karyawan VARCHAR(255) NOT NULL, "
        "periode VARCHAR(7) NOT NULL, "
        "tanggal DATE NOT NULL, "
        "nominal NUMERIC(14, 2) NOT NULL, "
        "metode VARCHAR(16) NOT NULL DEFAULT 'CASH', "
        "catatan TEXT, "
        "created_at DATETIME NOT NULL)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_salary_payments_employee_id "
        "ON salary_payments (employee_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_salary_payments_periode "
        "ON salary_payments (periode)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_salary_payments_tanggal "
        "ON salary_payments (tanggal)"
    )


def _migrate_027_employee_commission_split(cursor: Cursor) -> None:
    _add_column(
        cursor,
        "employees",
        "komisi_barang_nilai",
        "komisi_barang_nilai NUMERIC(14, 2) NOT NULL DEFAULT 0",
    )
    _add_column(
        cursor,
        "employees",
        "komisi_jasa_nilai",
        "komisi_jasa_nilai NUMERIC(14, 2) NOT NULL DEFAULT 0",
    )
    _add_column(
        cursor,
        "employees",
        "payroll_period",
        "payroll_period VARCHAR(16) NOT NULL DEFAULT 'BULANAN'",
    )
    _add_column(
        cursor,
        "employees",
        "payroll_tanggal",
        "payroll_tanggal INTEGER NOT NULL DEFAULT 1",
    )
    cursor.execute(
        "UPDATE employees SET "
        "komisi_barang_nilai = CASE "
        "WHEN komisi_mode = 'PERSEN' AND komisi_basis IN ('BARANG', 'KEDUANYA') "
        "THEN komisi_nilai "
        "WHEN komisi_mode = 'NOMINAL' AND komisi_basis = 'BARANG' "
        "THEN komisi_nilai ELSE 0 END, "
        "komisi_jasa_nilai = CASE "
        "WHEN komisi_mode = 'PERSEN' AND komisi_basis IN ('JASA', 'KEDUANYA') "
        "THEN komisi_nilai "
        "WHEN komisi_mode = 'NOMINAL' AND komisi_basis = 'JASA' "
        "THEN komisi_nilai ELSE 0 END"
    )


def _migrate_028_salary_cycle(cursor: Cursor) -> None:
    _add_column(
        cursor,
        "salary_payments",
        "cycle_start",
        "cycle_start DATE",
    )
    cursor.execute(
        "UPDATE salary_payments SET cycle_start = date(substr(tanggal, 1, 7) || '-01') "
        "WHERE cycle_start IS NULL"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_salary_payments_cycle_start "
        "ON salary_payments (cycle_start)"
    )


def _migrate_029_employee_debts(cursor: Cursor) -> None:
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS employee_debts ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL, "
        "nama_karyawan VARCHAR(255) NOT NULL, "
        "tanggal DATE NOT NULL, "
        "nominal NUMERIC(14, 2) NOT NULL, "
        "terbayar NUMERIC(14, 2) NOT NULL DEFAULT 0, "
        "keterangan TEXT, "
        "created_at DATETIME NOT NULL)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_employee_debts_employee_id "
        "ON employee_debts (employee_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_employee_debts_tanggal "
        "ON employee_debts (tanggal)"
    )
    _add_column(
        cursor,
        "salary_payments",
        "potongan_hutang",
        "potongan_hutang NUMERIC(14, 2) NOT NULL DEFAULT 0",
    )


def _migrate_030_salary_bonus(cursor: Cursor) -> None:
    _add_column(
        cursor,
        "salary_payments",
        "bonus",
        "bonus NUMERIC(14, 2) NOT NULL DEFAULT 0",
    )


def _migrate_031_salary_debt_installment(cursor: Cursor) -> None:
    _add_column(
        cursor,
        "salary_payments",
        "cicilan_hutang",
        "cicilan_hutang NUMERIC(14, 2) NOT NULL DEFAULT 0",
    )


def _migrate_032_employee_bank(cursor: Cursor) -> None:
    _add_column(
        cursor,
        "employees",
        "bank_nama",
        "bank_nama VARCHAR(64) NOT NULL DEFAULT ''",
    )
    _add_column(
        cursor,
        "employees",
        "bank_nomor",
        "bank_nomor VARCHAR(64) NOT NULL DEFAULT ''",
    )
    _add_column(
        cursor,
        "employees",
        "bank_atas_nama",
        "bank_atas_nama VARCHAR(255) NOT NULL DEFAULT ''",
    )


def _migrate_033_payroll_day(cursor: Cursor) -> None:
    _add_column(
        cursor,
        "employees",
        "payroll_hari",
        "payroll_hari INTEGER NOT NULL DEFAULT 0",
    )


def _migrate_034_employee_join_date(cursor: Cursor) -> None:
    _add_column(
        cursor,
        "employees",
        "tanggal_masuk",
        "tanggal_masuk DATE",
    )


def _migrate_035_salary_bonus_note(cursor: Cursor) -> None:
    _add_column(
        cursor,
        "salary_payments",
        "bonus_keterangan",
        "bonus_keterangan VARCHAR(255) NOT NULL DEFAULT ''",
    )


def _migrate_036_sparepart_warranty(cursor: Cursor) -> None:
    _add_column(
        cursor,
        "service_records",
        "sparepart_only",
        "sparepart_only BOOLEAN NOT NULL DEFAULT 0",
    )
    _add_column(
        cursor,
        "service_records",
        "garansi_tukar_aktif",
        "garansi_tukar_aktif BOOLEAN NOT NULL DEFAULT 0",
    )
    _add_column(
        cursor,
        "service_records",
        "garansi_tukar_hari",
        "garansi_tukar_hari INTEGER NOT NULL DEFAULT 0",
    )
    _add_column(
        cursor,
        "service_records",
        "garansi_barang_aktif",
        "garansi_barang_aktif BOOLEAN NOT NULL DEFAULT 0",
    )
    _add_column(
        cursor,
        "service_records",
        "garansi_barang_nilai",
        "garansi_barang_nilai INTEGER NOT NULL DEFAULT 0",
    )
    _add_column(
        cursor,
        "service_records",
        "garansi_barang_satuan",
        "garansi_barang_satuan VARCHAR(8) NOT NULL DEFAULT 'HARI'",
    )
    _add_column(
        cursor,
        "service_records",
        "garansi_barang_sampai",
        "garansi_barang_sampai DATE",
    )


def _migrate_037_part_exchange(cursor: Cursor) -> None:
    _add_column(
        cursor,
        "service_returns",
        "jenis",
        "jenis VARCHAR(16) NOT NULL DEFAULT 'RETUR'",
    )
    _add_column(
        cursor,
        "service_returns",
        "ganti_nama",
        "ganti_nama VARCHAR(255) NOT NULL DEFAULT ''",
    )
    _add_column(
        cursor,
        "service_returns",
        "ganti_jumlah",
        "ganti_jumlah INTEGER NOT NULL DEFAULT 0",
    )
    _add_column(
        cursor,
        "service_returns",
        "ganti_service_part_id",
        "ganti_service_part_id INTEGER",
    )


def _migrate_038_supplier_followups(cursor: Cursor) -> None:
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS supplier_followups ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "supplier_id INTEGER NOT NULL "
        "REFERENCES suppliers(id) ON DELETE CASCADE, "
        "stock_item_id INTEGER NOT NULL "
        "REFERENCES stock_items(id) ON DELETE CASCADE, "
        "status VARCHAR(32) NOT NULL, "
        "catatan VARCHAR(255), "
        "updated_at DATETIME NOT NULL)"
    )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_supplier_followups_pair "
        "ON supplier_followups (supplier_id, stock_item_id)"
    )


def _migrate_039_unit_part_and_barcodes(cursor) -> None:
    """Empat kategori unit: field part bebas dan alias barcode."""
    _add_column(
        cursor,
        "vehicle_or_units",
        "nama_barang",
        "nama_barang VARCHAR(255)",
    )
    _add_column(
        cursor,
        "vehicle_or_units",
        "nomor_seri",
        "nomor_seri VARCHAR(120)",
    )
    _add_column(
        cursor,
        "vehicle_or_units",
        "kondisi",
        "kondisi VARCHAR(64)",
    )
    _add_column(
        cursor,
        "vehicle_or_units",
        "kendaraan_asal",
        "kendaraan_asal VARCHAR(255)",
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS stock_barcodes ("
        "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
        "stock_item_id INTEGER NOT NULL, "
        "barcode VARCHAR(128) NOT NULL, "
        "created_at DATETIME NOT NULL, "
        "FOREIGN KEY(stock_item_id) REFERENCES stock_items (id) "
        "ON DELETE CASCADE)"
    )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_stock_barcodes_barcode "
        "ON stock_barcodes (barcode)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_stock_barcodes_stock_item_id "
        "ON stock_barcodes (stock_item_id)"
    )


def _migrate_040_sync_ids(cursor) -> None:
    """Tambahkan ID publik ULID agar baris dapat dirujuk antar perangkat."""
    from database import store_registry

    tables = _tables(cursor)
    for table in SYNC_ID_TABLES:
        if table not in tables:
            continue
        if "sync_id" not in _columns(cursor, table):
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN sync_id VARCHAR(26)")
        cursor.execute(
            f"SELECT id FROM {table} WHERE sync_id IS NULL OR sync_id = ''"
        )
        for (row_id,) in cursor.fetchall():
            cursor.execute(
                f"UPDATE {table} SET sync_id = ? WHERE id = ?",
                (store_registry.new_ulid(), row_id),
            )
        index_name = f"ux_{table}_sync_id"
        if not _index_is_unique(cursor, table, index_name):
            cursor.execute(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} "
                f"ON {table}(sync_id)"
            )


def _migrate_041_sync_feed(cursor) -> None:
    """Beri nomor urut feed per toko dan simpan kursor baca per perangkat."""
    tables = _tables(cursor)
    if "relay_envelopes" in tables:
        if "store_seq" not in _columns(cursor, "relay_envelopes"):
            cursor.execute(
                "ALTER TABLE relay_envelopes ADD COLUMN store_seq "
                "INTEGER NOT NULL DEFAULT 0"
            )
        cursor.execute("SELECT DISTINCT store_id FROM relay_envelopes")
        for (store_id,) in cursor.fetchall():
            cursor.execute(
                "SELECT id FROM relay_envelopes "
                "WHERE store_id = ? AND store_seq = 0 "
                "ORDER BY created_at, id",
                (store_id,),
            )
            pending_ids = [row[0] for row in cursor.fetchall()]
            cursor.execute(
                "SELECT COALESCE(MAX(store_seq), 0) FROM relay_envelopes "
                "WHERE store_id = ?",
                (store_id,),
            )
            next_seq = int(cursor.fetchone()[0]) + 1
            for envelope_id in pending_ids:
                cursor.execute(
                    "UPDATE relay_envelopes SET store_seq = ? WHERE id = ?",
                    (next_seq, envelope_id),
                )
                next_seq += 1
        if not _index_is_unique(cursor, "relay_envelopes", "ux_relay_store_seq"):
            cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_relay_store_seq "
                "ON relay_envelopes(store_id, store_seq)"
            )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS sync_cursors ("
        "store_id VARCHAR(32) NOT NULL, "
        "device_id VARCHAR(32) NOT NULL, "
        "last_seq INTEGER NOT NULL DEFAULT 0, "
        "updated_at DATETIME NOT NULL, "
        "PRIMARY KEY (store_id, device_id))"
    )


def _migrate_042_store_feed_counters(cursor) -> None:
    """Simpan nomor feed permanen agar tidak kembali ke 1 setelah ack."""
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS store_feed_counters ("
        "store_id VARCHAR(32) NOT NULL PRIMARY KEY, "
        "last_seq INTEGER NOT NULL DEFAULT 0, "
        "updated_at DATETIME NOT NULL)"
    )
    if "relay_envelopes" not in _tables(cursor):
        return
    cursor.execute(
        "SELECT store_id, COALESCE(MAX(store_seq), 0) "
        "FROM relay_envelopes GROUP BY store_id"
    )
    for store_id, last_seq in cursor.fetchall():
        cursor.execute(
            "INSERT INTO store_feed_counters (store_id, last_seq, updated_at) "
            "VALUES (?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(store_id) DO UPDATE SET "
            "last_seq = CASE WHEN excluded.last_seq > last_seq "
            "THEN excluded.last_seq ELSE last_seq END",
            (store_id, int(last_seq or 0)),
        )


def _migrate_043_snapshot_store_seq(cursor) -> None:
    """Snapshot membawa posisi feed agar kursor perangkat baru tepat."""
    if "relay_snapshots" not in _tables(cursor):
        return
    if "store_seq" not in _columns(cursor, "relay_snapshots"):
        cursor.execute(
            "ALTER TABLE relay_snapshots ADD COLUMN store_seq "
            "INTEGER NOT NULL DEFAULT 0"
        )


def _migrate_044_device_nota_counters(cursor) -> None:
    """Counter nota per perangkat; nomor berawalan perangkat (K-12)."""
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS device_nota_counters ("
        "device_id VARCHAR(32) NOT NULL, "
        "tanggal VARCHAR(8) NOT NULL, "
        "terakhir INTEGER NOT NULL DEFAULT 0, "
        "PRIMARY KEY (device_id, tanggal))"
    )


def _migrate_045_stock_movement_request(cursor) -> None:
    """Penanda idempotensi stok masuk/opname yang dikirim ulang offline."""
    if "stock_movements" not in _tables(cursor):
        return
    if "request_id" not in _columns(cursor, "stock_movements"):
        cursor.execute(
            "ALTER TABLE stock_movements ADD COLUMN request_id VARCHAR(64)"
        )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_stock_movements_request "
        "ON stock_movements(request_id)"
    )


def _migrate_046_remove_hub(cursor) -> None:
    """Hapus konsep hub; kunci toko memakai perangkat utama biasa."""
    tables = _tables(cursor)
    cursor.execute("DROP TABLE IF EXISTS hub_audits")
    cursor.execute("DROP TABLE IF EXISTS store_hubs")
    if "store_keys" in tables:
        columns = _columns(cursor, "store_keys")
        if "hub_device_id" in columns and "primary_device_id" not in columns:
            cursor.execute(
                "ALTER TABLE store_keys RENAME COLUMN hub_device_id "
                "TO primary_device_id"
            )


MIGRATIONS: List[Migration] = [
    (1, _migrate_001_harga_modal),
    (2, _migrate_002_nota_counters),
    (3, _migrate_003_request_id),
    (4, _migrate_004_unique_label),
    (5, _migrate_005_modal_estimasi),
    (6, _migrate_006_void_retur_ledger),
    (7, _migrate_007_audit_events),
    (8, _migrate_008_payments),
    (9, _migrate_009_whatsapp),
    (10, _migrate_010_followup),
    (11, _migrate_011_unit_archive),
    (12, _migrate_012_part_interval),
    (13, _migrate_013_followup_service_date),
    (14, _migrate_014_record_credit),
    (15, _migrate_015_pengerjaan_nota),
    (16, _migrate_016_ingat_piutang),
    (17, _migrate_017_hapus_penugasan_followup),
    (18, _migrate_018_log_pengerjaan),
    (19, _migrate_019_pengerjaan_events),
    (20, _migrate_020_item_identity),
    (21, _migrate_021_followup_tunda),
    (22, _migrate_022_stock_minimum),
    (23, _migrate_023_suppliers),
    (24, _migrate_024_employees),
    (25, _migrate_025_employee_salary),
    (26, _migrate_026_salary_payments),
    (27, _migrate_027_employee_commission_split),
    (28, _migrate_028_salary_cycle),
    (29, _migrate_029_employee_debts),
    (30, _migrate_030_salary_bonus),
    (31, _migrate_031_salary_debt_installment),
    (32, _migrate_032_employee_bank),
    (33, _migrate_033_payroll_day),
    (34, _migrate_034_employee_join_date),
    (35, _migrate_035_salary_bonus_note),
    (36, _migrate_036_sparepart_warranty),
    (37, _migrate_037_part_exchange),
    (38, _migrate_038_supplier_followups),
    (39, _migrate_039_unit_part_and_barcodes),
    (40, _migrate_040_sync_ids),
    (41, _migrate_041_sync_feed),
    (42, _migrate_042_store_feed_counters),
    (43, _migrate_043_snapshot_store_seq),
    (44, _migrate_044_device_nota_counters),
    (45, _migrate_045_stock_movement_request),
    (46, _migrate_046_remove_hub),
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
