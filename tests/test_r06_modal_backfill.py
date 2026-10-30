"""R-06: backfill modal sekali saat migrasi, ditandai estimasi, aman saat restart."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from config import settings
from database import migrations
from database.base import Base
from database.models import (
    Customer,
    ServiceJob,
    ServicePart,
    ServiceRecord,
    StockItem,
    VehicleOrUnit,
)
from database.session import build_engine, init_db
from services import backup_service


def _prepare_legacy(tmp_path):
    """Database lama: service_parts belum punya kolom modal sama sekali."""
    engine = build_engine(f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        customer = Customer(nama="Pelanggan Lama", nomor_hp="081200000040")
        db.add(customer)
        db.flush()
        unit = VehicleOrUnit(
            customer_id=customer.id,
            unit_type="MOBIL",
            nopol="B 6000 OLD",
            jenis_mobil="Avanza",
        )
        stock = StockItem(
            kode="OLD-001",
            nama="Part Lama",
            harga_modal=Decimal("85000"),
            harga_jual=Decimal("135000"),
            jumlah=5,
        )
        db.add_all([unit, stock])
        db.flush()
        record = ServiceRecord(
            unit_id=unit.id,
            no_nota="INV-20200101-0001",
            waktu_service=datetime(2020, 1, 1, 9, 0),
            keluhan_awal="Nota lama",
            biaya_jasa=Decimal("0"),
            total_part=Decimal("135000"),
            diskon=Decimal("0"),
            total_servis=Decimal("135000"),
            metode_bayar="CASH",
            bayar=Decimal("135000"),
            kembalian=Decimal("0"),
            bergaransi=False,
        )
        db.add(record)
        db.flush()
        db.add(
            ServiceJob(
                service_record_id=record.id,
                deskripsi="Jasa",
                jumlah=1,
                harga=Decimal("0"),
                subtotal=Decimal("0"),
            )
        )
        db.add(
            ServicePart(
                service_record_id=record.id,
                stock_item_id=stock.id,
                nama_part="Part Lama",
                jumlah=1,
                harga_satuan=Decimal("135000"),
                subtotal=Decimal("135000"),
                harga_modal=None,
            )
        )
        db.commit()

    with engine.begin() as conn:
        columns = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(service_parts)")
        }
        if "harga_modal_estimasi" in columns:
            conn.exec_driver_sql(
                "ALTER TABLE service_parts DROP COLUMN harga_modal_estimasi"
            )
        if "harga_modal" in columns:
            conn.exec_driver_sql(
                "ALTER TABLE service_parts DROP COLUMN harga_modal"
            )
    return engine


def _part_row(engine):
    with engine.connect() as conn:
        row = conn.exec_driver_sql(
            "SELECT harga_modal, harga_modal_estimasi FROM service_parts"
        ).first()
    return Decimal(str(row[0])), bool(row[1])


def test_r06_backfill_sekali_dan_ditandai_estimasi(tmp_path, monkeypatch):
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(
        backup_service, "settings", replace(settings, backup_dir=backup_dir)
    )
    legacy = _prepare_legacy(tmp_path)

    init_db(legacy)

    with legacy.connect() as conn:
        assert (
            conn.exec_driver_sql("PRAGMA user_version").scalar()
            == migrations.SCHEMA_VERSION
        )
    modal, estimasi = _part_row(legacy)
    assert modal == Decimal("85000")
    assert estimasi is True

    # Perubahan master setelah migrasi tidak boleh mengubah snapshot lama.
    with legacy.begin() as conn:
        conn.exec_driver_sql("UPDATE stock_items SET harga_modal = 99999")
    init_db(legacy)

    modal, estimasi = _part_row(legacy)
    assert modal == Decimal("85000")
    assert estimasi is True


def test_r06_snapshot_asli_tidak_ditimpa_backfill(tmp_path, monkeypatch):
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(
        backup_service, "settings", replace(settings, backup_dir=backup_dir)
    )
    legacy = _prepare_legacy(tmp_path)
    with legacy.begin() as conn:
        conn.exec_driver_sql(
            "ALTER TABLE service_parts ADD COLUMN harga_modal NUMERIC(14, 2)"
        )
        conn.exec_driver_sql(
            "ALTER TABLE service_parts ADD COLUMN harga_modal_estimasi "
            "BOOLEAN NOT NULL DEFAULT 0"
        )
        conn.exec_driver_sql(
            "UPDATE service_parts SET harga_modal = 50000, "
            "harga_modal_estimasi = 0"
        )
        conn.exec_driver_sql("PRAGMA user_version = 4")

    init_db(legacy)

    modal, estimasi = _part_row(legacy)
    assert modal == Decimal("50000")
    assert estimasi is False


def test_r06_migrasi_terputus_tidak_meninggalkan_perubahan(tmp_path, monkeypatch):
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(
        backup_service, "settings", replace(settings, backup_dir=backup_dir)
    )
    legacy = _prepare_legacy(tmp_path)

    def migrasi_gagal(cursor):
        cursor.execute("CREATE TABLE tabel_gagal (id INTEGER)")
        raise RuntimeError("migrasi terputus")

    with pytest.raises(RuntimeError):
        migrations.apply_migrations(
            legacy,
            migrations=list(migrations.MIGRATIONS) + [(99, migrasi_gagal)],
            target_version=99,
        )

    with legacy.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA user_version").scalar() == 0
        columns = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(service_parts)")
        }
        assert "harga_modal" not in columns
        assert "harga_modal_estimasi" not in columns

    init_db(legacy)
    modal, estimasi = _part_row(legacy)
    assert modal == Decimal("85000")
    assert estimasi is True


def test_r06_laporan_menandai_modal_estimasi(
    client, create_customer, create_unit, make_transaction, db_session, stock
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    item = stock("SP-001")
    record_id = make_transaction(
        unit["id"],
        parts=[
            {
                "stock_item_id": item["id"],
                "jumlah": 1,
                "harga_satuan": "135000",
            }
        ],
    ).json()["record"]["id"]

    part = db_session.query(ServicePart).filter_by(service_record_id=record_id).one()
    part.harga_modal_estimasi = True
    db_session.commit()

    detail = client.get(f"/api/service-records/{record_id}").json()
    assert detail["modal_estimasi"] is True

    daily = client.get("/api/reports/daily-cash").json()
    assert daily["transaksi_modal_estimasi"] == 1

    part.harga_modal_estimasi = False
    db_session.commit()
    detail = client.get(f"/api/service-records/{record_id}").json()
    assert detail["modal_estimasi"] is False
