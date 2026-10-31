"""Tahap 12: pesan WhatsApp, izin pelanggan, template, dan log upaya."""
from __future__ import annotations

import pytest

from database.models import WhatsAppLog
from database.session import SessionLocal
from services.utils import mask_phone


def _make(client, unit_id, **overrides):
    payload = {
        "unit_id": unit_id,
        "keluhan_awal": "Servis radiator",
        "metode_bayar": "TRANSFER",
        "bergaransi": True,
        "garansi_bulan": 1,
        "jobs": [{"deskripsi": "Korok Radiator", "jumlah": 1, "harga": "150000"}],
        "parts": [],
    }
    payload.update(overrides)
    return client.post("/api/pos/transaction", json=payload)


def test_config_menyertakan_pengaturan_ops_default(client):
    response = client.get("/api/config")
    assert response.status_code == 200, response.text
    ops = response.json()["ops"]
    assert ops["tempo_hari"] == 7
    assert ops["prospek_hari"] == 7
    assert ops["cooldown_hari"] == 7
    assert ops["garansi_akan_habis_hari"] == 7
    assert ops["servis_berkala_awal_hari"] == 14
    assert ops["wa_after_print"] is False
    assert ops["wa_template"] == ""


def test_pengaturan_ops_dapat_diubah_dan_divalidasi(client):
    payload = {
        "tempo_hari": 14,
        "prospek_hari": 10,
        "cooldown_hari": 3,
        "garansi_akan_habis_hari": 5,
        "servis_berkala_awal_hari": 20,
        "wa_after_print": True,
        "wa_template": "Halo {nama}, nota {no_nota} total {total}.",
    }
    updated = client.put("/api/settings/ops", json=payload)
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["tempo_hari"] == 14
    assert body["wa_after_print"] is True
    assert body["wa_template"] == payload["wa_template"]

    config = client.get("/api/config").json()["ops"]
    assert config["tempo_hari"] == 14
    assert config["wa_template"] == payload["wa_template"]

    invalid = client.put("/api/settings/ops", json={**payload, "tempo_hari": 0})
    assert invalid.status_code == 422, invalid.text


def test_struk_memuat_teks_wa_default_dan_nomor_ternormalisasi(
    client, create_customer, create_unit
):
    customer = create_customer(nama="Siti WA", nomor_hp="0812-1111-2222")
    unit = create_unit(customer["id"])

    created = _make(client, unit["id"])
    assert created.status_code == 201, created.text
    receipt = created.json()["receipt"]

    assert receipt["wa_consent"] is True
    assert receipt["customer_wa"] == "6281211112222"
    text = receipt["wa_text"]
    assert "Siti WA" in text
    assert receipt["no_nota"] in text
    assert "Rp 150.000" in text
    assert "Sisa bayar: Rp 0" in text
    # Nomor lengkap tidak dicetak ke teks pesan.
    assert "0812-1111-2222" not in text


def test_template_wa_kustom_dipakai_untuk_teks_pesan(
    client, create_customer, create_unit
):
    template = "Halo {nama}, nota {no_nota} total {total} sisa {sisa}."
    saved = client.put(
        "/api/settings/ops",
        json={"wa_template": template},
    )
    assert saved.status_code == 200, saved.text

    customer = create_customer(nama="Agus Template", nomor_hp="0812-3333-4444")
    unit = create_unit(customer["id"])
    receipt = _make(client, unit["id"]).json()["receipt"]

    assert receipt["wa_text"] == (
        f"Halo Agus Template, nota {receipt['no_nota']} total Rp 150.000 "
        "sisa Rp 0."
    )


def test_whatsapp_dibuka_membuat_link_dan_log_tanpa_nomor_penuh(
    client, create_customer, create_unit
):
    customer = create_customer(nama="Rina WA", nomor_hp="0812-5555-6666")
    unit = create_unit(customer["id"])
    record_id = _make(client, unit["id"]).json()["record"]["id"]

    response = client.post(
        f"/api/service-records/{record_id}/whatsapp", json={"status": "DIBUKA"}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "DIBUKA"
    assert body["nomor_masked"] == mask_phone("081255556666")
    assert body["link"].startswith("https://wa.me/6281255556666?text=")
    assert "Rina WA" in body["wa_text"]
    assert body["log"]["status"] == "DIBUKA"

    logs = client.get(f"/api/service-records/{record_id}/whatsapp-logs").json()
    assert len(logs) == 1
    assert logs[0]["nomor_masked"] == mask_phone("081255556666")
    assert "nomor" not in logs[0] or logs[0].get("nomor") is None

    with SessionLocal() as db:
        rows = db.query(WhatsAppLog).all()
        assert len(rows) == 1
        assert rows[0].pesan
        assert rows[0].operator


def test_status_dibatalkan_dan_tidak_tersedia_dicatat(
    client, create_customer, create_unit
):
    customer = create_customer(nama="Joko WA", nomor_hp="0812-7777-8888")
    unit = create_unit(customer["id"])
    record_id = _make(client, unit["id"]).json()["record"]["id"]

    for status in ("DIBATALKAN", "TIDAK_TERSEDIA"):
        response = client.post(
            f"/api/service-records/{record_id}/whatsapp",
            json={"status": status},
        )
        assert response.status_code == 201, (status, response.text)
        assert response.json()["link"] == ""

    logs = client.get(f"/api/service-records/{record_id}/whatsapp-logs").json()
    assert [row["status"] for row in logs] == ["TIDAK_TERSEDIA", "DIBATALKAN"]

    invalid = client.post(
        f"/api/service-records/{record_id}/whatsapp", json={"status": "LAINNYA"}
    )
    assert invalid.status_code == 422, invalid.text


def test_izin_whatsapp_diminginkan_menolak_pesan(
    client, create_customer, create_unit
):
    customer = create_customer(nama="Tono Tanpa Izin", nomor_hp="0812-9999-0000")
    unit = create_unit(customer["id"])
    receipt = _make(client, unit["id"]).json()["receipt"]
    record_id = receipt["id"]

    revoked = client.put(
        f"/api/customers/{customer['id']}/consent", json={"wa_consent": False}
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["wa_consent"] is False
    overview = client.get(
        "/api/customers/overview", params={"q": "Tono Tanpa Izin"}
    )
    row = next(
        item for item in overview.json() if item["id"] == customer["id"]
    )
    assert row["wa_consent"] is False

    blocked = client.post(
        f"/api/service-records/{record_id}/whatsapp", json={"status": "DIBUKA"}
    )
    assert blocked.status_code == 409, blocked.text
    assert "menyetujui" in blocked.json()["detail"]

    assert client.get(f"/api/service-records/{record_id}/whatsapp-logs").json() == []
    detail_receipt = client.get(f"/api/service-records/{record_id}/receipt").json()
    assert detail_receipt["wa_consent"] is False

    allowed_again = client.put(
        f"/api/customers/{customer['id']}/consent", json={"wa_consent": True}
    )
    assert allowed_again.status_code == 200, allowed_again.text
    reopened = client.post(
        f"/api/service-records/{record_id}/whatsapp", json={"status": "DIBUKA"}
    )
    assert reopened.status_code == 201, reopened.text


def test_log_whatsapp_tidak_bisa_diubah_lewat_orm(
    client, create_customer, create_unit
):
    customer = create_customer(nama="Log Tetap", nomor_hp="0812-1212-3434")
    unit = create_unit(customer["id"])
    record_id = _make(client, unit["id"]).json()["record"]["id"]
    client.post(
        f"/api/service-records/{record_id}/whatsapp", json={"status": "DIBUKA"}
    )

    with SessionLocal() as db:
        log = db.query(WhatsAppLog).one()
        log.status = "DIBATALKAN"
        with pytest.raises(ValueError):
            db.commit()
