"""Fase 1 web: registry toko, isolasi data, gating premium, dan kuota Follow up."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest

from database import store_registry
from database.models import ServiceRecord
from services import followup_quota_service, settings_service
from services.errors import FeatureLockedError


def _primary_id(client):
    response = client.get("/api/stores")
    assert response.status_code == 200, response.text
    return response.json()["aktif"]


def _create_branch(client, nama="Cabang Dua", alamat="Jl. Cabang No. 2"):
    response = client.post(
        "/api/stores", json={"nama": nama, "alamat": alamat}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _activate(client, store_id):
    response = client.post(f"/api/stores/{store_id}/activate")
    assert response.status_code == 200, response.text
    return response.json()


def _shift_record(db_session, record_id, days_ago=30):
    record = db_session.get(ServiceRecord, record_id)
    record.waktu_service = datetime.combine(
        date.today() - timedelta(days=days_ago), time(9, 0)
    )
    db_session.commit()


def _prospek_item(client):
    response = client.get("/api/followup/items", params={"jenis": "prospek"})
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert items, response.text
    return items[0]


def test_config_memuat_paket_toko_dan_database_id(client):
    config = client.get("/api/config")
    assert config.status_code == 200, config.text
    data = config.json()

    assert data["entitlement"] == {"plan": "premium", "premium": True}
    assert data["store_aktif"] == "utama"
    assert len(data["stores"]) == 1
    primary = data["stores"][0]
    assert primary["aktif"] is True
    assert primary["tersedia"] is True
    assert len(primary["database_id"]) >= 26

    assert data["kuota_followup"]["plan"] == "premium"
    assert data["kuota_followup"]["sisa"] is None
    assert data["kuota_followup"]["terkunci"] is False


def test_tambah_toko_kosong_dan_terisolasi(client, create_customer):
    primary = _primary_id(client)
    customer = create_customer(nama="Pelanggan Toko Utama")

    branch = _create_branch(client)
    assert branch["store_id"] != primary
    assert branch["aktif"] is False
    assert branch["database_id"] == branch["store_id"]

    stores = client.get("/api/stores").json()
    assert stores["aktif"] == primary
    assert len(stores["toko"]) == 2
    assert len({row["database_id"] for row in stores["toko"]}) == 2

    _activate(client, branch["store_id"])

    auth = client.get("/api/auth/status")
    assert auth.status_code == 200
    assert auth.json()["authenticated"] is True

    config = client.get("/api/config").json()
    assert config["store_aktif"] == branch["store_id"]
    assert config["bengkel"]["nama"] == "Cabang Dua"
    assert config["bengkel"]["alamat"] == "Jl. Cabang No. 2"

    customers = client.get("/api/customers")
    assert customers.status_code == 200
    assert customers.json() == []

    stock = client.get("/api/stock")
    assert stock.status_code == 200
    assert stock.json(), "Toko baru memakai database kosong dengan seed awal."

    _activate(client, primary)
    names = [row["nama"] for row in client.get("/api/customers").json()]
    assert names == [customer["nama"]]


def test_gratis_tidak_bisa_tambah_toko_atau_menulis_premium(client):
    store_registry.set_plan("free")

    config = client.get("/api/config")
    assert config.status_code == 200
    assert config.json()["entitlement"]["plan"] == "free"

    add_store = client.post(
        "/api/stores", json={"nama": "Cabang Terlarang", "alamat": "Jl. X"}
    )
    assert add_store.status_code == 403
    assert add_store.json()["code"] == "premium_locked"

    employee = client.post(
        "/api/employees", json={"nama": "Budi", "peran": "KASIR"}
    )
    assert employee.status_code == 403
    assert employee.json()["code"] == "premium_locked"

    employees = client.get("/api/employees")
    assert employees.status_code == 200, "Data lama tetap boleh dibaca."

    telegram = client.put(
        "/api/settings/telegram", json={"enabled": False, "jam": "21:00"}
    )
    assert telegram.status_code == 403
    assert telegram.json()["code"] == "premium_locked"

    scheduled = client.post("/api/admin/scheduled-backup")
    assert scheduled.status_code == 403

    core_write = client.post(
        "/api/customers",
        json={"nama": "Pelanggan Gratis", "nomor_hp": "0812-0000-1111"},
    )
    assert core_write.status_code == 201, core_write.text


def test_kuota_followup_gratis_20_kredit_lalu_terkunci(client, db_session):
    store_registry.set_plan("free")
    database_id = client.get("/api/config").json()["kuota_followup"]["database_id"]

    for expected in range(1, 21):
        status = followup_quota_service.consume(db_session)
        assert status["terpakai"] == expected
        assert status["sisa"] == 20 - expected
        assert status["database_id"] == database_id

    assert status["sisa"] == 0
    assert status["terkunci"] is True

    with pytest.raises(FeatureLockedError):
        followup_quota_service.consume(db_session)

    endpoint = client.get("/api/followup/quota")
    assert endpoint.status_code == 200
    assert endpoint.json()["terpakai"] == 20
    assert endpoint.json()["terkunci"] is True

    store_registry.set_plan("premium")
    premium = followup_quota_service.consume(db_session)
    assert premium["plan"] == "premium"
    assert premium["terpakai"] == 20
    assert premium["sisa"] is None
    assert premium["terkunci"] is False


def test_kuota_terpotong_saat_followup_dibuka(
    client, create_customer, create_unit, make_transaction, db_session
):
    customer = create_customer(nama="Pelanggan Kuota", nomor_hp="0812-7777-8888")
    unit = create_unit(customer["id"], nopol="B 7711 KTA")
    created = make_transaction(unit["id"])
    assert created.status_code == 201, created.text
    _shift_record(db_session, created.json()["record"]["id"])
    item = _prospek_item(client)

    store_registry.set_plan("free")
    first = client.post(
        f"/api/followup/items/{item['id']}/followup",
        json={"status": "DIBUKA"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["link"].startswith("https://wa.me/")
    assert first.json()["kuota"]["terpakai"] == 1
    assert first.json()["kuota"]["sisa"] == 19

    settings_service.set_setting(db_session, followup_quota_service.USED_KEY, "20")
    db_session.commit()

    blocked = client.post(
        f"/api/followup/items/{item['id']}/followup",
        json={"status": "DIBUKA"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "followup_quota_habis"
