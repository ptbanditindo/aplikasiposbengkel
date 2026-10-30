"""ARC-15: identitas operator dari backend & jejak audit tetap."""
from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app import app
from config import settings
from database.models import AuditEvent
from database.session import build_engine, engine, init_db
from services import backup_service

BASE_URL = "http://127.0.0.1:8000"
TEST_PIN = "2468"


def _sell(client, make_transaction, create_customer, create_unit, stock):
    customer = create_customer(nama="Pelanggan ARC15")
    unit = create_unit(customer["id"], nopol="B 1501 ARC")
    item = stock("SP-001")
    body = make_transaction(
        unit["id"],
        jobs=[{"deskripsi": "Servis Radiator", "jumlah": 1, "harga": "150000"}],
        parts=[
            {
                "stock_item_id": item["id"],
                "nama_part": item["nama"],
                "jumlah": 1,
                "harga_satuan": "160000",
            }
        ],
    )
    assert body.status_code == 201, body.text
    return body.json()


def _audit(client):
    response = client.get("/api/audit-events")
    assert response.status_code == 200, response.text
    return response.json()


def test_void_mencatat_operator_pemilik_dan_alasan(client):
    customer = client.post(
        "/api/customers",
        json={"nama": "Pelanggan ARC15", "nomor_hp": "081211112222"},
    ).json()
    unit = client.post(
        "/api/units",
        json={
            "customer_id": customer["id"],
            "unit_type": "MOBIL",
            "nopol": "B 1501 ARC",
            "jenis_mobil": "Avanza",
            "tahun_mobil": 2015,
        },
    ).json()
    created = client.post(
        "/api/pos/transaction",
        json={
            "unit_id": unit["id"],
            "keluhan_awal": "Panas",
            "metode_bayar": "TRANSFER",
            "jobs": [
                {
                    "deskripsi": "Servis Radiator",
                    "jumlah": 1,
                    "harga": "150000",
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    record = created.json()["record"]

    voided = client.post(
        f"/api/service-records/{record['id']}/void",
        json={"alasan": "Salah input pelanggan"},
    )
    assert voided.status_code == 200, voided.text
    assert voided.json()["voided_by"] == "Pemilik"

    event = _audit(client)[0]
    assert event["operator_id"] == "owner"
    assert event["operator_role"] == "owner"
    assert event["action"] == "VOID"
    assert event["reference_id"] == record["no_nota"]
    assert event["reason"] == "Salah input pelanggan"


def test_operator_palsu_dari_frontend_ditolak(client):
    fake_void = client.post(
        "/api/service-records/1/void",
        json={"alasan": "Salah input", "operator_id": "owner"},
    )
    assert fake_void.status_code == 422

    fake_nama = client.post(
        "/api/service-records/1/void",
        json={"alasan": "Salah input", "oleh": "Pemilik Palsu"},
    )
    assert fake_nama.status_code == 422

    fake_return = client.post(
        "/api/service-records/1/returns",
        json={
            "alasan": "Barang tidak cocok",
            "operator_id": "owner",
            "items": [{"service_part_id": 1, "jumlah": 1}],
        },
    )
    assert fake_return.status_code == 422


def test_kasir_tidak_boleh_tindakan_owner(
    client,
    anon_client,
    create_customer,
    create_unit,
    make_transaction,
    stock,
):
    created = client.put("/api/auth/kasir-pin", json={"pin": "9753"})
    assert created.status_code == 200, created.text

    status = anon_client.get("/api/auth/status").json()
    assert status["kasir_configured"] is True

    login = anon_client.post("/api/auth/login", json={"pin": "9753"})
    assert login.status_code == 200, login.text
    assert anon_client.get("/api/auth/status").json()["role"] == "kasir"

    assert (
        anon_client.put(
            "/api/settings/bengkel", json={"nama": "Diubah Kasir"}
        ).status_code
        == 403
    )
    assert anon_client.post("/api/admin/backup").status_code == 403
    assert anon_client.get("/api/audit-events").status_code == 403
    assert (
        anon_client.put("/api/auth/kasir-pin", json={"pin": "1111"}).status_code
        == 403
    )

    # Kasir tetap boleh melakukan operasi dan tercatat sebagai kasir.
    body = _sell(
        client, make_transaction, create_customer, create_unit, stock
    )
    record = body["record"]
    voided = anon_client.post(
        f"/api/service-records/{record['id']}/void",
        json={"alasan": "Salah input pelanggan"},
    )
    assert voided.status_code == 200, voided.text
    assert voided.json()["voided_by"] == "Kasir"

    events = _audit(client)
    assert len(events) == 1
    event = events[0]
    assert event["operator_id"] == "kasir"
    assert event["operator_role"] == "kasir"
    assert event["action"] == "VOID"
    assert event["reference_type"] == "SERVICE_RECORD"
    assert event["reference_id"] == record["no_nota"]
    assert event["reason"] == "Salah input pelanggan"
    assert event["created_at"]


def test_owner_boleh_mengelola_dan_mencatat_audit_retur(
    client,
    create_customer,
    create_unit,
    make_transaction,
    stock,
):
    body = _sell(
        client, make_transaction, create_customer, create_unit, stock
    )
    record = body["record"]
    part = body["receipt"]["parts"][0]

    retur = client.post(
        f"/api/service-records/{record['id']}/returns",
        json={
            "alasan": "Barang tidak cocok",
            "items": [{"service_part_id": part["id"], "jumlah": 1}],
        },
    )
    assert retur.status_code == 201, retur.text
    assert retur.json()["oleh"] == "Pemilik"

    events = _audit(client)
    assert [event["action"] for event in events] == ["RETURN"]
    assert events[0]["operator_id"] == "owner"
    assert events[0]["operator_role"] == "owner"
    assert events[0]["reference_id"] == record["no_nota"]


def test_riwayat_audit_tetap_setelah_restart(
    client,
    create_customer,
    create_unit,
    make_transaction,
    stock,
):
    body = _sell(
        client, make_transaction, create_customer, create_unit, stock
    )
    record = body["record"]
    assert (
        client.post(
            f"/api/service-records/{record['id']}/void",
            json={"alasan": "Nota batal"},
        ).status_code
        == 200
    )

    engine.dispose()
    with TestClient(app, base_url=BASE_URL) as fresh:
        login = fresh.post("/api/auth/login", json={"pin": TEST_PIN})
        assert login.status_code == 200, login.text
        events = _audit(fresh)
        assert [event["action"] for event in events] == ["VOID"]
        assert events[0]["reference_id"] == record["no_nota"]


def test_restore_mencatat_audit_di_database_hasil(
    client, create_customer, create_unit, make_transaction, stock
):
    body = _sell(
        client, make_transaction, create_customer, create_unit, stock
    )
    record = body["record"]
    assert (
        client.post(
            f"/api/service-records/{record['id']}/void",
            json={"alasan": "Nota batal"},
        ).status_code
        == 200
    )
    backup = client.post("/api/admin/backup")
    assert backup.status_code == 200, backup.text

    restore = client.post(
        "/api/admin/restore",
        files={"file": ("cadangan.db", backup.content, "application/x-sqlite3")},
    )
    assert restore.status_code == 200, restore.text

    # Restore menghapus kredensial; pemilik membuat PIN baru lalu membaca audit.
    setup = client.post("/api/auth/setup", json={"pin": "1357"})
    assert setup.status_code == 201, setup.text
    events = _audit(client)
    actions = [event["action"] for event in events]
    assert "RESTORE" in actions
    restore_event = next(
        event for event in events if event["action"] == "RESTORE"
    )
    assert restore_event["operator_id"] == "owner"
    assert restore_event["reference_id"] == "cadangan.db"


def test_audit_immutable_tanpa_endpoint_ubah(client, create_customer, create_unit, make_transaction, stock):
    body = _sell(
        client, make_transaction, create_customer, create_unit, stock
    )
    record = body["record"]
    assert (
        client.post(
            f"/api/service-records/{record['id']}/void",
            json={"alasan": "Nota batal"},
        ).status_code
        == 200
    )
    event_id = _audit(client)[0]["id"]

    assert client.put(f"/api/audit-events/{event_id}", json={}).status_code in (
        404,
        405,
    )
    assert client.delete(f"/api/audit-events/{event_id}").status_code in (
        404,
        405,
    )


def test_migrasi_v6_menambah_tabel_audit(tmp_path, monkeypatch):
    from database import migrations

    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(
        backup_service, "settings", replace(settings, backup_dir=backup_dir)
    )
    legacy = build_engine(f"sqlite:///{(tmp_path / 'legacy_v6.db').as_posix()}")
    from database.base import Base

    Base.metadata.create_all(legacy)
    with legacy.begin() as conn:
        conn.exec_driver_sql("DROP TABLE audit_events")
        conn.exec_driver_sql("PRAGMA user_version = 6")

    init_db(legacy)

    with legacy.connect() as conn:
        assert (
            conn.exec_driver_sql("PRAGMA user_version").scalar()
            == migrations.SCHEMA_VERSION
            == 7
        )
        tables = {
            row[0]
            for row in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert "audit_events" in tables
        columns = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(audit_events)")
        }
        assert {
            "id",
            "operator_id",
            "operator_role",
            "action",
            "reference_type",
            "reference_id",
            "reason",
            "created_at",
        } <= columns

    init_db(legacy)
    with legacy.connect() as conn:
        assert (
            conn.exec_driver_sql("PRAGMA user_version").scalar() == 7
        )


def test_baris_audit_tidak_bisa_diubah_lewat_orm(
    client, create_customer, create_unit, make_transaction, stock
):
    body = _sell(
        client, make_transaction, create_customer, create_unit, stock
    )
    record = body["record"]
    assert (
        client.post(
            f"/api/service-records/{record['id']}/void",
            json={"alasan": "Nota batal"},
        ).status_code
        == 200
    )

    with Session(engine) as db:
        event = db.scalars(select(AuditEvent)).first()
        assert event is not None
        event.reason = "diubah"
        with pytest.raises(ValueError):
            db.commit()
