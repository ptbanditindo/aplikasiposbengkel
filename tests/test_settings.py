"""Pengaturan identitas bengkel: default .env, simpan ke DB, dipakai struk."""
from __future__ import annotations

from sqlalchemy import select

from database.models import AppSetting

ADMIN_HEADERS = {"X-Admin-Token": "test-admin-token"}


def bengkel_payload(**overrides):
    data = {
        "nama": "BENGKEL RADIATOR JAYA",
        "tagline": "Melayani Sepenuh Hati",
        "alamat": "Jl. Raya Baru No. 9",
        "telepon": "021-555777",
        "wa": "0812-1111-2222",
        "bank_nama": "Mandiri",
        "no_rekening": "123-456-789",
        "atas_nama": "Bengkel Radiator Jaya",
    }
    data.update(overrides)
    return data


def test_config_memakai_default_env(client):
    bengkel = client.get("/api/config").json()["bengkel"]
    assert bengkel["nama"] == "BENGKEL RADIATOR TEST"
    assert bengkel["alamat"] == "Jl. Uji Otomotif No. 1"
    assert bengkel["bank_nama"] == "BCA TEST"
    assert bengkel["no_rekening"] == "987-654-3210"


def test_ubah_identitas_wajib_token_admin(client):
    assert client.put("/api/settings/bengkel", json=bengkel_payload()).status_code == 401
    assert (
        client.put(
            "/api/settings/bengkel",
            json=bengkel_payload(),
            headers={"X-Admin-Token": "salah"},
        ).status_code
        == 401
    )

    response = client.put(
        "/api/settings/bengkel", json=bengkel_payload(), headers=ADMIN_HEADERS
    )
    assert response.status_code == 200, response.text
    assert response.json()["nama"] == "BENGKEL RADIATOR JAYA"


def test_ubah_identitas_tersimpan_dan_tampil_di_config(client, db_session):
    response = client.put(
        "/api/settings/bengkel", json=bengkel_payload(), headers=ADMIN_HEADERS
    )
    assert response.status_code == 200, response.text

    bengkel = client.get("/api/config").json()["bengkel"]
    assert bengkel["nama"] == "BENGKEL RADIATOR JAYA"
    assert bengkel["tagline"] == "Melayani Sepenuh Hati"
    assert bengkel["alamat"] == "Jl. Raya Baru No. 9"
    assert bengkel["telepon"] == "021-555777"
    assert bengkel["wa"] == "0812-1111-2222"
    assert bengkel["bank_nama"] == "Mandiri"
    assert bengkel["no_rekening"] == "123-456-789"
    assert bengkel["atas_nama"] == "Bengkel Radiator Jaya"

    keys = {row.key for row in db_session.scalars(select(AppSetting)).all()}
    assert {key for key in keys if key.startswith("bengkel.")} == {
        "bengkel.nama",
        "bengkel.tagline",
        "bengkel.alamat",
        "bengkel.telepon",
        "bengkel.wa",
        "bengkel.bank_nama",
        "bengkel.no_rekening",
        "bengkel.atas_nama",
    }


def test_tagline_kosong_menimpa_default(client):
    payload = bengkel_payload(tagline="")
    response = client.put(
        "/api/settings/bengkel", json=payload, headers=ADMIN_HEADERS
    )
    assert response.status_code == 200, response.text
    assert client.get("/api/config").json()["bengkel"]["tagline"] == ""


def test_nama_bengkel_tidak_boleh_kosong(client):
    too_short = client.put(
        "/api/settings/bengkel",
        json=bengkel_payload(nama="A"),
        headers=ADMIN_HEADERS,
    )
    assert too_short.status_code == 422

    blank = client.put(
        "/api/settings/bengkel",
        json=bengkel_payload(nama="   "),
        headers=ADMIN_HEADERS,
    )
    assert blank.status_code == 400
    assert client.get("/api/config").json()["bengkel"]["nama"] == "BENGKEL RADIATOR TEST"


def test_struk_memakai_identitas_terbaru(client, create_customer, create_unit, make_transaction):
    customer = create_customer()
    unit = create_unit(customer["id"])

    update = client.put(
        "/api/settings/bengkel", json=bengkel_payload(), headers=ADMIN_HEADERS
    )
    assert update.status_code == 200, update.text

    created = make_transaction(unit["id"])
    assert created.status_code == 201, created.text
    receipt = created.json()["receipt"]
    assert receipt["bengkel_nama"] == "BENGKEL RADIATOR JAYA"
    assert receipt["bengkel_bank_nama"] == "Mandiri"
    assert any("BENGKEL RADIATOR" in line for line in receipt["struk_58"])
    assert all("BCA TEST" not in line for line in receipt["struk_58"])

    reprint = client.get(f"/api/service-records/{receipt['id']}/receipt")
    assert reprint.status_code == 200, reprint.text
    assert reprint.json()["bengkel_nama"] == "BENGKEL RADIATOR JAYA"
