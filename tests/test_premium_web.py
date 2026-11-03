"""Premium web: lisensi, akun, perangkat, relay E2E, snapshot, dan arsip."""
from __future__ import annotations

import io
import json
import zipfile
from datetime import timedelta

import pytest
from sqlalchemy import select

from database import store_registry
from database.models import (
    License,
    OutboxItem,
    RelayEnvelope,
    StockItem,
    SyncConflict,
    utcnow,
)
from services import account_service, premium_crypto, sync_service
from services import store_service

PRIMARY = store_registry.PRIMARY_STORE_ID
OWNER_PIN = "2468"
EMPLOYEE_PASSWORD = "rahasia123"
EMPLOYEE_PIN = "123456"


def _set_free(client_plan="free"):
    store_registry.set_plan(client_plan)


def _activate(client, days=30, device_limit=2):
    response = client.post(
        "/api/license/activate",
        json={"days": days, "provider": "manual", "device_limit": device_limit},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _owner_id(client):
    response = client.get("/api/premium/status")
    assert response.status_code == 200, response.text
    return response.json()["owner_id"]


def _register_device(client, nama, kind="owner", account_id=None, stores=None):
    response = client.post(
        "/api/devices",
        json={
            "nama": nama,
            "kind": kind,
            "employee_account_id": account_id,
            "store_ids": stores or [PRIMARY],
            "generate_keys": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_account(client, username="kasir1", role="KASIR", stores=None, extras=None):
    response = client.post(
        "/api/accounts",
        json={
            "username": username,
            "nama": "Kasir Satu",
            "role": role,
            "store_ids": stores or [PRIMARY],
            "extra_permissions": extras or [],
            "password": EMPLOYEE_PASSWORD,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _logout(client):
    client.post("/api/auth/logout")


def _login_owner(client):
    response = client.post("/api/auth/login", json={"pin": OWNER_PIN})
    assert response.status_code == 200, response.text


def _employee_login(client, username="kasir1", pin=EMPLOYEE_PIN, password=EMPLOYEE_PASSWORD):
    response = client.post(
        "/api/auth/employee/login",
        json={"username": username, "password": password, "pin": pin},
    )
    return response


def _envelope_payload(store_key, item, data, private_key):
    plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
    ciphertext, nonce = premium_crypto.encrypt_payload(store_key, plaintext)
    fields = {
        "store_id": PRIMARY,
        "sender_device_id": item["device_id"],
        "recipient_device_id": "",
        "seq": item["seq"],
        "hlc_wall": item["hlc_wall"],
        "hlc_counter": item["hlc_counter"],
        "idempotency_key": item["idempotency_key"],
        "ciphertext": ciphertext,
        "nonce": nonce,
    }
    signature = sync_service.sign_envelope(private_key, fields)
    return {**fields, "signature": signature}


def _store_key(client, device_id):
    response = client.post(
        "/api/devices/keys",
        json={
            "store_id": PRIMARY,
            "device_ids": [device_id],
            "hub_device_id": device_id,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["store_key"]
    return premium_crypto.b64d(data["store_key"])


def test_lisensi_gratis_mengunci_tulis_premium(client):
    store_registry.set_plan("free")
    status = client.get("/api/premium/status")
    assert status.status_code == 200, status.text
    assert status.json()["premium"] is False

    blocked = client.post(
        "/api/accounts",
        json={"username": "kasir1", "role": "KASIR", "store_ids": [PRIMARY]},
    )
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "premium_locked"

    activated = _activate(client, days=15, device_limit=1)
    assert activated["status"] == "active"
    assert len(activated["owner_id"]) == 8
    assert len(activated["recovery_code"]) == 16

    status = client.get("/api/premium/status").json()
    assert status["premium"] is True
    assert status["plan"] == "premium"
    assert status["owner_id"] == activated["owner_id"]
    assert status["license"]["days_left"] >= 14
    assert status["owner_public_key"]

    config = client.get("/api/config").json()
    assert config["entitlement"] == {"plan": "premium", "premium": True}
    assert config["premium"]["owner_id"] == activated["owner_id"]


def test_lisensi_kedaluwarsa_dan_jam_mundur(client, db_session):
    activated = _activate(client, days=10)
    row = db_session.get(License, 1)
    assert row is not None
    row.current_period_end = utcnow() - timedelta(days=1)
    db_session.commit()

    status = client.get("/api/premium/status").json()
    assert status["premium"] is False
    assert status["license"]["status"] == "expired"

    renewed = client.post("/api/license/renew", json={"days": 30})
    assert renewed.status_code == 200, renewed.text
    assert renewed.json()["status"] == "active"

    row = db_session.get(License, 1)
    row.max_seen_at = utcnow() + timedelta(days=2)
    db_session.commit()
    status = client.get("/api/premium/status").json()
    assert status["license"]["clock_warning"] is True
    assert status["owner_id"] == activated["owner_id"]


def test_akun_karyawan_peran_izin_audit_dan_snapshot(client, db_session):
    _activate(client)
    created = _create_account(client, extras=["stok_masuk", "baca_supplier"])
    account = created["akun"]
    assert account["role"] == "KASIR"
    assert "lihat_laporan" in account["permissions"]
    assert "stok_masuk" in account["permissions"]
    assert created["password"] == EMPLOYEE_PASSWORD

    listed = client.get("/api/accounts").json()
    assert [row["username"] for row in listed] == ["kasir1"]

    updated = client.put(
        f"/api/accounts/{account['id']}",
        json={
            "nama": "Kasir Utama",
            "role": "KEDUANYA",
            "store_ids": [PRIMARY],
            "extra_permissions": ["opname"],
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["role"] == "KEDUANYA"
    assert body["extra_permissions"] == ["opname"]
    assert body["permission_version"] == 2

    snapshot = client.get(f"/api/accounts/{account['id']}/snapshot")
    assert snapshot.status_code == 200, snapshot.text
    payload = snapshot.json()
    assert account_service.verify_snapshot(db_session, payload["payload"], payload["signature"])

    audit = client.get(f"/api/accounts/{account['id']}/audit").json()
    assert len(audit) >= 2
    assert audit[0]["actor_id"] == "owner"

    blocked = client.post(
        "/api/accounts",
        json={"username": "kasir1", "role": "KASIR", "store_ids": [PRIMARY]},
    )
    assert blocked.status_code == 409

    _logout(client)
    login = _employee_login(client)
    assert login.status_code == 200, login.text
    assert login.json()["must_change_password"] is True

    change = client.post(
        "/api/auth/employee/change-password",
        json={
            "old_password": EMPLOYEE_PASSWORD,
            "new_password": "passwordBaru9",
        },
    )
    assert change.status_code == 200, change.text

    pin_response = client.post(
        "/api/auth/employee/pin",
        json={"password": "passwordBaru9", "pin": EMPLOYEE_PIN},
    )
    assert pin_response.status_code == 200, pin_response.text

    forbidden = client.post(
        "/api/employees", json={"nama": "Tidak Boleh", "peran": "KASIR"}
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "owner_only"

    _logout(client)
    _login_owner(client)


def test_filter_toko_karyawan_dan_akses_pemilik(client):
    _activate(client)
    branch = client.post(
        "/api/stores", json={"nama": "Cabang Karyawan", "alamat": "Jl. Dua"}
    )
    assert branch.status_code == 201, branch.text
    branch_id = branch.json()["store_id"]
    _create_account(client, stores=[PRIMARY])

    _logout(client)
    login = _employee_login(client)
    assert login.status_code == 200, login.text
    client.post(
        "/api/auth/employee/change-password",
        json={
            "old_password": EMPLOYEE_PASSWORD,
            "new_password": "passwordBaru9",
        },
    )

    config = client.get("/api/config").json()
    assert config["operator"]["kind"] == "employee"
    assert config["operator"]["role"] == "KASIR"
    assert [row["store_id"] for row in config["stores"]] == [PRIMARY]

    stores = client.get("/api/stores").json()
    assert [row["store_id"] for row in stores["toko"]] == [PRIMARY]

    wrong_store = client.post(f"/api/stores/{branch_id}/activate")
    assert wrong_store.status_code == 403
    assert wrong_store.json()["code"] == "owner_only"

    accounts = client.get("/api/accounts")
    assert accounts.status_code == 403
    assert accounts.json()["code"] == "owner_only"

    sync_status = client.get("/api/sync/status")
    assert sync_status.status_code == 200, sync_status.text


def test_batas_perangkat_pencabutan_pelepasan_dan_hub(client, db_session):
    _activate(client, device_limit=1)
    first = _register_device(client, "HP Owner")
    assert first["token"]
    assert first["private_keys"]["sign"]

    second = client.post(
        "/api/devices",
        json={
            "nama": "HP Kedua",
            "kind": "owner",
            "store_ids": [PRIMARY],
            "generate_keys": True,
        },
    )
    assert second.status_code == 403
    assert second.json()["code"] == "device_limit"

    revoked = client.post(f"/api/devices/{first['device']['id']}/revoke")
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["revoked_at"]

    third = _register_device(client, "HP Ketiga")
    released = client.post(f"/api/devices/{third['device']['id']}/release")
    assert released.status_code == 200, released.text
    again = client.post(f"/api/devices/{third['device']['id']}/release")
    assert again.status_code == 403
    assert again.json()["code"] == "release_window"

    hub = _register_device(client, "Web Hub")
    hub_id = hub["device"]["id"]
    set_hub = client.post(
        "/api/devices/hub",
        json={"store_id": PRIMARY, "device_id": hub_id},
    )
    assert set_hub.status_code == 200, set_hub.text
    assert set_hub.json()["mode"] == "active"

    current = client.get(f"/api/devices/hub?store_id={PRIMARY}").json()
    assert current["device_id"] == hub_id


def test_login_perangkat_karyawan_dan_hub_uang(client, create_customer, create_unit):
    _activate(client)
    owner_id = _owner_id(client)
    account = _create_account(client, role="KASIR")["akun"]
    device = _register_device(
        client, "HP Kasir", kind="employee", account_id=account["id"]
    )
    customer = create_customer(nama="Pelanggan Hub")
    unit = create_unit(customer["id"])

    _logout(client)
    token_response = client.post(
        "/api/auth/device/login",
        headers={"X-Device-Token": device["token"]},
        json={
            "owner_id": owner_id,
            "username": "kasir1",
            "password": EMPLOYEE_PASSWORD,
        },
    )
    assert token_response.status_code == 200, token_response.text
    assert token_response.json()["operator"]["role"] == "KASIR"

    status = client.get(
        "/api/auth/status", headers={"X-Device-Token": device["token"]}
    )
    assert status.status_code == 200
    assert status.json()["operator_kind"] == "employee"
    assert status.json()["device_id"] == device["device"]["id"]

    _logout(client)
    client.cookies.clear()
    login = _employee_login(client)
    assert login.status_code == 200, login.text
    client.post(
        "/api/auth/employee/change-password",
        json={
            "old_password": EMPLOYEE_PASSWORD,
            "new_password": "passwordBaru9",
        },
    )

    blocked = client.post(
        "/api/pos/transaction",
        json={
            "unit_id": unit["id"],
            "keluhan_awal": "Tes",
            "metode_bayar": "CASH",
            "bayar": "50000",
            "jobs": [{"deskripsi": "Jasa", "jumlah": 1, "harga": "50000"}],
            "parts": [],
        },
    )
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "hub_required"

    _logout(client)
    _login_owner(client)
    hub = _register_device(client, "Web Hub")
    hub_id = hub["device"]["id"]
    assert (
        client.post(
            "/api/devices/hub",
            json={"store_id": PRIMARY, "device_id": hub_id},
        ).status_code
        == 200
    )

    _logout(client)
    login = _employee_login(client, password="passwordBaru9")
    assert login.status_code == 200, login.text
    assert login.json()["device_id"] == hub_id

    allowed = client.post(
        "/api/pos/transaction",
        json={
            "unit_id": unit["id"],
            "keluhan_awal": "Tes",
            "metode_bayar": "CASH",
            "bayar": "50000",
            "jobs": [{"deskripsi": "Jasa", "jumlah": 1, "harga": "50000"}],
            "parts": [],
        },
    )
    assert allowed.status_code == 201, allowed.text
    _logout(client)
    _login_owner(client)


def test_kunci_toko_dibungkus_dan_bisa_dibuka(client):
    _activate(client)
    hub = _register_device(client, "Web Hub")
    hub_id = hub["device"]["id"]
    encrypt_private = hub["private_keys"]["encrypt"]
    client.post(
        "/api/devices/hub",
        json={"store_id": PRIMARY, "device_id": hub_id},
    )

    response = client.post(
        "/api/devices/keys",
        json={
            "store_id": PRIMARY,
            "device_ids": [hub_id],
            "hub_device_id": hub_id,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    store_key = premium_crypto.b64d(data["store_key"])
    assert data["devices"] == [hub_id]

    wrapped = client.get(f"/api/devices/keys/{PRIMARY}/{hub_id}")
    assert wrapped.status_code == 200, wrapped.text
    assert premium_crypto.unwrap_store_key(
        encrypt_private, wrapped.json()["wrapped_key"]
    ) == store_key


def test_amplop_e2e_tidak_menyimpan_plaintext_dan_idempoten(client, db_session):
    _activate(client)
    sender = _register_device(client, "Hub A")
    recipient = _register_device(client, "B")
    sender_id = sender["device"]["id"]
    recipient_id = recipient["device"]["id"]
    store_key = _store_key(client, sender_id)
    client.post(
        "/api/devices/hub",
        json={"store_id": PRIMARY, "device_id": sender_id},
    )

    stock = client.get("/api/stock").json()[0]
    item = client.post(
        "/api/sync/outbox",
        json={
            "device_id": sender_id,
            "entity": "stock",
            "action": "delta",
            "entity_id": str(stock["id"]),
            "payload": {"stock_item_id": stock["id"], "qty": 2},
            "idempotency_key": "outbox-delta-1",
        },
    )
    assert item.status_code == 201, item.text
    queued = item.json()
    assert queued["status"] == "pending"

    secret_marker = "PELANGGAN-RAHASIA-E2E"
    envelope = _envelope_payload(
        store_key,
        {
            "device_id": sender_id,
            "seq": queued["seq"],
            "hlc_wall": queued["hlc_wall"],
            "hlc_counter": queued["hlc_counter"],
            "idempotency_key": queued["idempotency_key"],
        },
        {
            "entity": "stock",
            "action": "delta",
            "entity_id": str(stock["id"]),
            "payload": {"stock_item_id": stock["id"], "qty": 2},
            "note": secret_marker,
        },
        sender["private_keys"]["sign"],
    )
    submitted = client.post(
        "/api/sync/envelopes", json={**envelope, "sender_device_id": sender_id}
    )
    assert submitted.status_code == 201, submitted.text
    assert submitted.json()["created"] is True
    envelope_id = submitted.json()["envelope"]["id"]

    duplicate = client.post(
        "/api/sync/envelopes", json={**envelope, "sender_device_id": sender_id}
    )
    assert duplicate.status_code == 201, duplicate.text
    assert duplicate.json()["created"] is False
    assert duplicate.json()["envelope"]["id"] == envelope_id

    row = db_session.get(RelayEnvelope, envelope_id)
    assert secret_marker not in row.ciphertext
    assert secret_marker not in (row.signature or "")
    assert "note" not in row.ciphertext

    listed = client.get(
        f"/api/sync/envelopes?device_id={recipient_id}&store_id={PRIMARY}"
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()[0]["id"] == envelope_id

    before = db_session.get(StockItem, stock["id"]).jumlah
    applied = client.post(
        f"/api/sync/envelopes/{envelope_id}/apply",
        json={
            "device_id": recipient_id,
            "store_key": premium_crypto.b64e(store_key),
        },
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["status"] in {"applied", "duplicate"}
    db_session.expire_all()
    assert db_session.get(StockItem, stock["id"]).jumlah == before + 2

    again = client.post(
        f"/api/sync/envelopes/{envelope_id}/apply",
        json={
            "device_id": recipient_id,
            "store_key": premium_crypto.b64e(store_key),
        },
    )
    assert again.status_code == 200, again.text
    assert again.json()["status"] == "duplicate"


def test_konflik_opname_dan_resolusi(client, db_session):
    _activate(client)
    hub = _register_device(client, "Hub")
    hub_id = hub["device"]["id"]
    store_key = _store_key(client, hub_id)
    client.post(
        "/api/devices/hub",
        json={"store_id": PRIMARY, "device_id": hub_id},
    )
    stock = client.get("/api/stock").json()[0]
    queued = client.post(
        "/api/sync/outbox",
        json={
            "device_id": hub_id,
            "entity": "stock",
            "action": "opname",
            "entity_id": str(stock["id"]),
            "payload": {
                "stock_item_id": stock["id"],
                "base_jumlah": stock["jumlah"] + 5,
                "jumlah": 1,
            },
            "idempotency_key": "opname-bentrok-1",
        },
    ).json()
    envelope = _envelope_payload(
        store_key,
        {
            "device_id": hub_id,
            "seq": queued["seq"],
            "hlc_wall": queued["hlc_wall"],
            "hlc_counter": queued["hlc_counter"],
            "idempotency_key": queued["idempotency_key"],
        },
        {
            "entity": "stock",
            "action": "opname",
            "entity_id": str(stock["id"]),
            "payload": {
                "stock_item_id": stock["id"],
                "base_jumlah": stock["jumlah"] + 5,
                "jumlah": 1,
            },
        },
        hub["private_keys"]["sign"],
    )
    submitted = client.post(
        "/api/sync/envelopes", json={**envelope, "sender_device_id": hub_id}
    )
    assert submitted.status_code == 201, submitted.text
    envelope_id = submitted.json()["envelope"]["id"]
    result = client.post(
        f"/api/sync/envelopes/{envelope_id}/apply",
        json={
            "device_id": hub_id,
            "store_key": premium_crypto.b64e(store_key),
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "conflict"

    conflicts = client.get("/api/sync/conflicts")
    assert conflicts.status_code == 200, conflicts.text
    rows = conflicts.json()
    assert rows and rows[0]["reason"] == "opname_bentrok"

    resolved = client.post(
        f"/api/sync/conflicts/{rows[0]['id']}/resolve",
        json={"resolution": "keep_local"},
    )
    assert resolved.status_code == 200, resolved.text
    assert client.get("/api/sync/conflicts").json() == []


def test_snapshot_terenkripsi_memulihkan_data_dan_memutar_outbox(client, db_session):
    _activate(client)
    hub = _register_device(client, "Hub Snapshot")
    hub_id = hub["device"]["id"]
    store_key = _store_key(client, hub_id)
    client.post(
        "/api/devices/hub",
        json={"store_id": PRIMARY, "device_id": hub_id},
    )
    stock = client.get("/api/stock").json()[0]
    original = stock["jumlah"]

    created = client.post(
        "/api/sync/snapshots",
        json={
            "store_id": PRIMARY,
            "device_id": hub_id,
            "store_key": premium_crypto.b64e(store_key),
            "device_private_key": hub["private_keys"]["sign"],
            "hlc_wall": 1,
            "hlc_counter": 0,
        },
    )
    assert created.status_code == 201, created.text
    snapshot_id = created.json()["id"]

    fetched = client.get(f"/api/sync/snapshots/{PRIMARY}?device_id={hub_id}")
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["id"] == snapshot_id
    assert "ciphertext" in fetched.json()

    item = db_session.get(StockItem, stock["id"])
    item.jumlah = original + 99
    db_session.commit()

    client.post(
        "/api/sync/outbox",
        json={
            "device_id": hub_id,
            "entity": "stock",
            "action": "delta",
            "entity_id": str(stock["id"]),
            "payload": {"stock_item_id": stock["id"], "qty": 3},
            "idempotency_key": "setelah-snapshot-1",
        },
    )

    applied = client.post(
        "/api/sync/snapshots/apply",
        json={
            "device_id": hub_id,
            "snapshot_id": snapshot_id,
            "store_key": premium_crypto.b64e(store_key),
        },
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["replayed"]["applied"] == 1
    db_session.expire_all()
    assert db_session.get(StockItem, stock["id"]).jumlah == original + 3

    outbox = client.get(f"/api/sync/outbox?device_id={hub_id}").json()
    assert outbox[0]["status"] == "acked"


def test_ttl_amplop_dibersihkan(client, db_session):
    _activate(client)
    hub = _register_device(client, "Hub TTL")
    hub_id = hub["device"]["id"]
    store_key = _store_key(client, hub_id)
    client.post(
        "/api/devices/hub",
        json={"store_id": PRIMARY, "device_id": hub_id},
    )
    stock = client.get("/api/stock").json()[0]
    queued = client.post(
        "/api/sync/outbox",
        json={
            "device_id": hub_id,
            "entity": "stock",
            "action": "delta",
            "entity_id": str(stock["id"]),
            "payload": {"stock_item_id": stock["id"], "qty": 1},
            "idempotency_key": "ttl-delta-1",
        },
    ).json()
    envelope = _envelope_payload(
        store_key,
        {
            "device_id": hub_id,
            "seq": queued["seq"],
            "hlc_wall": queued["hlc_wall"],
            "hlc_counter": queued["hlc_counter"],
            "idempotency_key": queued["idempotency_key"],
        },
        {
            "entity": "stock",
            "action": "delta",
            "entity_id": str(stock["id"]),
            "payload": {"stock_item_id": stock["id"], "qty": 1},
        },
        hub["private_keys"]["sign"],
    )
    submitted = client.post(
        "/api/sync/envelopes", json={**envelope, "sender_device_id": hub_id}
    )
    assert submitted.status_code == 201, submitted.text
    envelope_id = submitted.json()["envelope"]["id"]
    row = db_session.get(RelayEnvelope, envelope_id)
    row.expires_at = utcnow() - timedelta(seconds=1)
    db_session.commit()

    purged = client.post("/api/sync/purge")
    assert purged.status_code == 200, purged.text
    assert purged.json()["deleted"] >= 1
    db_session.expire_all()
    assert db_session.get(RelayEnvelope, envelope_id) is None


def test_owner_app_summary_ditandatangani(client):
    _activate(client)
    hub = _register_device(client, "HP Owner")
    summary = client.get("/api/owner-app/summary")
    assert summary.status_code == 200, summary.text
    data = summary.json()
    assert data["payload"]["v"] == 1
    assert data["payload"]["owner_id"] == _owner_id(client)
    assert data["payload"]["devices"][0]["id"] == hub["device"]["id"]
    assert premium_crypto.verify(
        data["public_key"],
        premium_crypto.canonical_json(data["payload"]),
        data["signature"],
    )


def test_arsip_semua_toko_backup_dan_restore(client, create_customer):
    _activate(client)
    first = create_customer(nama="Pelanggan Utama")
    branch = client.post(
        "/api/stores", json={"nama": "Cabang Arsip", "alamat": "Jl. Arsip"}
    )
    assert branch.status_code == 201, branch.text
    branch_id = branch.json()["store_id"]
    assert (
        client.post(f"/api/stores/{branch_id}/activate").status_code == 200
    )
    second = create_customer(nama="Pelanggan Cabang")
    assert (
        client.post(f"/api/stores/{PRIMARY}/activate").status_code == 200
    )

    backup = client.post("/api/admin/backup-all")
    assert backup.status_code == 200, backup.text
    archive_bytes = backup.content
    assert archive_bytes[:2] == b"PK"
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        assert manifest["format"] == 1
        assert manifest["owner_id"] == _owner_id(client)
        store_ids = {row["store_id"] for row in manifest["stores"]}
        assert store_ids == {PRIMARY, branch_id}
        for row in manifest["stores"]:
            assert row["filename"] in archive.namelist()
            assert len(row["sha256"]) == 64

    archives = client.get("/api/admin/archives")
    assert archives.status_code == 200, archives.text
    assert any(
        row["filename"] == backup.headers["content-disposition"].split('"')[1]
        or row["size"] == len(archive_bytes)
        for row in archives.json()
    )

    changed = client.put(
        f"/api/customers/{first['id']}/contact",
        json={"wa_consent": False},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["wa_consent"] is False
    restore = client.post(
        "/api/admin/restore-all",
        files={"file": ("arsip.zip", archive_bytes, "application/zip")},
    )
    assert restore.status_code == 200, restore.text
    assert {row["store_id"] for row in restore.json()["stores"]} == {
        PRIMARY,
        branch_id,
    }

    customers = client.get("/api/customers").json()
    assert [row["nama"] for row in customers] == ["Pelanggan Utama"]
    assert customers[0]["wa_consent"] is True
    assert client.get("/api/auth/status").json()["authenticated"] is True

    client.post(f"/api/stores/{branch_id}/activate")
    branch_customers = client.get("/api/customers").json()
    assert [row["nama"] for row in branch_customers] == ["Pelanggan Cabang"]
    client.post(f"/api/stores/{PRIMARY}/activate")


def test_arsip_checksum_rusak_tidak_menimpa(client, create_customer):
    _activate(client)
    customer = create_customer(nama="Data Aman")
    backup = client.post("/api/admin/backup-all")
    assert backup.status_code == 200, backup.text

    source = zipfile.ZipFile(io.BytesIO(backup.content))
    manifest = json.loads(source.read("manifest.json").decode("utf-8"))
    entry = manifest["stores"][0]
    entry["sha256"] = "0" * 64
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as target:
        for name in source.namelist():
            if name == "manifest.json":
                target.writestr(name, json.dumps(manifest))
            else:
                target.writestr(name, source.read(name))
    source.close()

    response = client.post(
        "/api/admin/restore-all",
        files={"file": ("rusak.zip", buffer.getvalue(), "application/zip")},
    )
    assert response.status_code == 400
    names = [row["nama"] for row in client.get("/api/customers").json()]
    assert names == [customer["nama"]]


def test_hapus_metadata_owner_tidak_menyentuh_data_bengkel(client, create_customer):
    activated = _activate(client)
    customer = create_customer(nama="Tetap Ada")
    _register_device(client, "HP Owner")
    _create_account(client)

    response = client.delete(
        f"/api/license/owner?confirm={activated['owner_id']}"
    )
    assert response.status_code == 200, response.text
    assert client.get("/api/premium/status").json()["owner_id"] == ""
    assert client.get("/api/accounts").json() == []
    assert client.get("/api/devices").json() == []
    names = [row["nama"] for row in client.get("/api/customers").json()]
    assert names == [customer["nama"]]

    renewed = _activate(client)
    assert renewed["owner_id"] != activated["owner_id"]
