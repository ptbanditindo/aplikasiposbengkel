"""R-02: label radiator copotan unik, termasuk saat dibuat paralel."""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import settings
from database.base import Base
from database.models import Customer, VehicleOrUnit
from database.session import build_engine, init_db
from services import backup_service

PARALLEL = 20


def test_r02_dua_puluh_unit_radiator_paralel_label_unik(client, create_customer):
    customer = create_customer(nama="Pelanggan Label", nomor_hp="081200000060")
    barrier = threading.Barrier(PARALLEL)

    def submit(index: int):
        barrier.wait(timeout=30)
        try:
            response = client.post(
                "/api/units",
                json={
                    "customer_id": customer["id"],
                    "unit_type": "RADIATOR_ONLY",
                    "tipe_radiator": f"Radiator Uji {index}",
                },
            )
        except Exception:  # noqa: BLE001
            return None
        return response

    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        responses = list(pool.map(submit, range(PARALLEL)))

    assert all(response is not None for response in responses)
    assert [response.status_code for response in responses].count(201) == PARALLEL
    labels = [
        response.json()["label_radiator"]
        for response in responses
        if response.status_code == 201
    ]
    assert len(labels) == PARALLEL
    assert len(set(labels)) == PARALLEL, labels


def test_r02_indeks_unik_menolak_label_duplikat(db_session, create_customer):
    customer = create_customer(nama="Pelanggan Duplikat", nomor_hp="081200000061")
    label = "RAD-20260101-777"

    db_session.add(
        VehicleOrUnit(
            customer_id=customer["id"],
            unit_type="RADIATOR_ONLY",
            label_radiator=label,
        )
    )
    db_session.commit()

    db_session.add(
        VehicleOrUnit(
            customer_id=customer["id"],
            unit_type="RADIATOR_ONLY",
            label_radiator=label,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_r02_migrasi_label_duplikat_lama_tidak_menggagalkan_startup(
    tmp_path, monkeypatch, caplog
):
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(
        backup_service, "settings", replace(settings, backup_dir=backup_dir)
    )

    legacy = build_engine(f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    Base.metadata.create_all(legacy)
    with legacy.begin() as conn:
        conn.exec_driver_sql("DROP TABLE nota_counters")
        conn.exec_driver_sql("DROP INDEX IF EXISTS ix_service_records_request_id")
        conn.exec_driver_sql("ALTER TABLE service_records DROP COLUMN request_id")
        conn.exec_driver_sql(
            "DROP INDEX IF EXISTS ix_vehicle_or_units_label_radiator"
        )

    with Session(legacy) as db:
        customer = Customer(nama="Pelanggan Lama", nomor_hp="081200000062")
        db.add(customer)
        db.commit()
        db.refresh(customer)
        db.add_all(
            [
                VehicleOrUnit(
                    customer_id=customer.id,
                    unit_type="RADIATOR_ONLY",
                    label_radiator="RAD-20260101-001",
                ),
                VehicleOrUnit(
                    customer_id=customer.id,
                    unit_type="RADIATOR_ONLY",
                    label_radiator="RAD-20260101-001",
                ),
            ]
        )
        db.commit()

    with caplog.at_level(logging.WARNING):
        init_db(legacy)

    assert "duplikat" in caplog.text.lower()
    with legacy.connect() as conn:
        assert (
            conn.exec_driver_sql(
                "SELECT COUNT(*) FROM vehicle_or_units "
                "WHERE label_radiator = 'RAD-20260101-001'"
            ).scalar()
            == 2
        )
        indexes = {
            row[1]
            for row in conn.exec_driver_sql(
                "PRAGMA index_list(vehicle_or_units)"
            )
        }
        assert "ix_vehicle_or_units_label_radiator" not in indexes

    # Startup berikutnya tidak membuat backup berulang untuk indeks yang dilewati.
    init_db(legacy)
    assert len(list(backup_dir.glob("sebelum_migrasi_*.db"))) == 1
