"""Hotfix PIN: hash & data bertahan setelah backend restart; reset PIN web
hanya menghapus kredensial, bukan database transaksi.

Alur ini meniru langkah uji manual:
1. Buat PIN.
2. Restart backend pada file database yang sama.
3. Login dengan PIN lama.
4. Reset PIN (setara `python reset_pin.py` di PC kasir).
5. Restart backend.
6. Login dengan PIN baru.
7. PIN lama ditolak.
8. Transaksi lama tetap tersedia.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from database.models import AppSetting
from database.session import SessionLocal, engine, init_db
from reset_pin import clear_pin, resolve_database_path

TEST_PIN = "2468"
NEW_PIN = "1357"


def _db_path():
    path = resolve_database_path()
    assert path is not None
    assert path.exists()
    return path


def _setting_value(key: str) -> str | None:
    with SessionLocal() as db:
        row = db.get(AppSetting, key)
        return row.value if row is not None else None


def _restart_backend() -> None:
    engine.dispose()
    init_db()


def _make_record(create_customer, create_unit, make_transaction) -> int:
    customer = create_customer(nama="Pelanggan Hotfix PIN")
    unit = create_unit(customer["id"], nopol="B 2468 HOT")
    response = make_transaction(unit["id"])
    assert response.status_code == 201, response.text
    return response.json()["record"]["id"]


def test_pin_dan_transaksi_tetap_setelah_backend_restart(
    client, create_customer, create_unit, make_transaction
):
    record_id = _make_record(create_customer, create_unit, make_transaction)
    _db_path()

    hash_before = _setting_value("auth.pin_hash")
    salt_before = _setting_value("auth.pin_salt")
    assert hash_before
    assert salt_before

    _restart_backend()

    assert _setting_value("auth.pin_hash") == hash_before
    assert _setting_value("auth.pin_salt") == salt_before

    login = client.post("/api/auth/login", json={"pin": TEST_PIN})
    assert login.status_code == 200, login.text

    records = client.get("/api/service-records")
    assert records.status_code == 200, records.text
    assert any(item["id"] == record_id for item in records.json())

    customers = client.get("/api/customers/search", params={"q": "Hotfix PIN"})
    assert customers.status_code == 200, customers.text
    assert customers.json()


def test_reset_pin_tidak_menghapus_data_dan_pin_baru_berlaku(
    client, create_customer, create_unit, make_transaction
):
    record_id = _make_record(create_customer, create_unit, make_transaction)
    db_path = _db_path()

    _restart_backend()
    engine.dispose()
    removed = clear_pin(db_path)
    assert removed >= 1
    init_db()

    status = client.get("/api/auth/status")
    assert status.status_code == 200, status.text
    assert status.json()["pin_configured"] is False

    setup = client.post("/api/auth/setup", json={"pin": NEW_PIN})
    assert setup.status_code == 201, setup.text

    old_pin = client.post("/api/auth/login", json={"pin": TEST_PIN})
    assert old_pin.status_code == 401, old_pin.text
    new_pin = client.post("/api/auth/login", json={"pin": NEW_PIN})
    assert new_pin.status_code == 200, new_pin.text

    _restart_backend()

    assert client.post("/api/auth/login", json={"pin": TEST_PIN}).status_code == 401
    assert client.post("/api/auth/login", json={"pin": NEW_PIN}).status_code == 200

    records = client.get("/api/service-records")
    assert records.status_code == 200, records.text
    assert any(item["id"] == record_id for item in records.json())

    daily = client.get("/api/reports/daily-cash")
    assert daily.status_code == 200, daily.text
    assert Decimal(daily.json()["total_omset"]) > 0
