"""Migrasi skema ringan pada database lama (tanpa kehilangan data)."""
from __future__ import annotations

from dataclasses import replace

import pytest
from sqlalchemy.orm import Session

from config import settings
from database.base import Base
from database.models import Customer
from database.session import build_engine, init_db
from services import backup_service


def test_migrasi_legacy_membuat_backup_pra_migrasi_dan_data_tetap(
    tmp_path, monkeypatch
):
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(
        backup_service, "settings", replace(settings, backup_dir=backup_dir)
    )

    legacy = build_engine(f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    Base.metadata.create_all(legacy)
    with Session(legacy) as db:
        db.add(Customer(nama="Pelanggan Lama", nomor_hp="081200000030"))
        db.commit()

    # Database versi lama: belum punya tabel counter nota & kolom request_id.
    with legacy.begin() as conn:
        conn.exec_driver_sql("DROP TABLE nota_counters")
        conn.exec_driver_sql("DROP INDEX IF EXISTS ix_service_records_request_id")
        conn.exec_driver_sql(
            "ALTER TABLE service_records DROP COLUMN request_id"
        )

    init_db(legacy)

    backups = list(backup_dir.glob("sebelum_migrasi_*.db"))
    assert len(backups) == 1

    with legacy.connect() as conn:
        tables = {
            row[0]
            for row in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert "nota_counters" in tables
        columns = {
            row[1]
            for row in conn.exec_driver_sql(
                "PRAGMA table_info(service_records)"
            )
        }
        assert "request_id" in columns
        indexes = {
            row[1]: row[2]
            for row in conn.exec_driver_sql(
                "PRAGMA index_list(service_records)"
            )
        }
        assert indexes.get("ix_service_records_request_id") == 1
        assert conn.exec_driver_sql("SELECT nama FROM customers").scalar() == (
            "Pelanggan Lama"
        )

    # Migrasi idempoten: tidak ada perubahan tersisa & tidak ada backup baru.
    init_db(legacy)
    assert len(list(backup_dir.glob("sebelum_migrasi_*.db"))) == 1


def _legacy_engine(tmp_path, nama="Pelanggan Versi Lama"):
    legacy = build_engine(f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    Base.metadata.create_all(legacy)
    with Session(legacy) as db:
        db.add(Customer(nama=nama, nomor_hp="081200000031"))
        db.commit()

    with legacy.begin() as conn:
        conn.exec_driver_sql("DROP TABLE nota_counters")
        conn.exec_driver_sql("DROP INDEX IF EXISTS ix_service_records_request_id")
        conn.exec_driver_sql("ALTER TABLE service_records DROP COLUMN request_id")
    return legacy


def test_migrasi_menyetel_user_version_dan_data_tetap(tmp_path, monkeypatch):
    from database import migrations

    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(
        backup_service, "settings", replace(settings, backup_dir=backup_dir)
    )
    legacy = _legacy_engine(tmp_path)

    init_db(legacy)

    with legacy.connect() as conn:
        assert (
            conn.exec_driver_sql("PRAGMA user_version").scalar()
            == migrations.SCHEMA_VERSION
        )
        assert conn.exec_driver_sql("SELECT nama FROM customers").scalar() == (
            "Pelanggan Versi Lama"
        )
        tables = {
            row[0]
            for row in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert "nota_counters" in tables
    assert len(list(backup_dir.glob("sebelum_migrasi_*.db"))) == 1

    init_db(legacy)

    with legacy.connect() as conn:
        assert (
            conn.exec_driver_sql("PRAGMA user_version").scalar()
            == migrations.SCHEMA_VERSION
        )
    assert len(list(backup_dir.glob("sebelum_migrasi_*.db"))) == 1


def test_migrasi_tidak_dijalankan_dua_kali(tmp_path):
    from database import migrations

    legacy = _legacy_engine(tmp_path)
    dijalankan = []

    def migrasi_uji(cursor):
        dijalankan.append(1)
        cursor.execute("CREATE TABLE IF NOT EXISTS tabel_uji (id INTEGER)")

    migrations.apply_migrations(
        legacy, migrations=[(1, migrasi_uji)], target_version=1
    )
    migrations.apply_migrations(
        legacy, migrations=[(1, migrasi_uji)], target_version=1
    )

    assert dijalankan == [1]


def test_migrasi_gagal_mempertahankan_database_lama(tmp_path):
    from database import migrations

    legacy = _legacy_engine(tmp_path)

    def migrasi_rusak(cursor):
        cursor.execute("ALTER TABLE service_records ADD COLUMN kolom_rusak TEXT")
        cursor.execute("UPDATE customers SET nama = 'DATA RUSAK'")
        raise RuntimeError("migrasi gagal di tengah jalan")

    with pytest.raises(RuntimeError):
        migrations.apply_migrations(
            legacy, migrations=[(1, migrasi_rusak)], target_version=1
        )

    with legacy.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA user_version").scalar() == 0
        assert conn.exec_driver_sql("SELECT nama FROM customers").scalar() == (
            "Pelanggan Versi Lama"
        )
        columns = {
            row[1]
            for row in conn.exec_driver_sql(
                "PRAGMA table_info(service_records)"
            )
        }
        assert "kolom_rusak" not in columns


def test_backup_pra_migrasi_berisi_skema_lama(tmp_path, monkeypatch):
    import sqlite3

    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(
        backup_service, "settings", replace(settings, backup_dir=backup_dir)
    )
    legacy = _legacy_engine(tmp_path)

    init_db(legacy)

    backups = list(backup_dir.glob("sebelum_migrasi_*.db"))
    assert len(backups) == 1
    connection = sqlite3.connect(str(backups[0]))
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert "nota_counters" not in tables
        assert (
            connection.execute("SELECT nama FROM customers").fetchone()[0]
            == "Pelanggan Versi Lama"
        )
    finally:
        connection.close()
