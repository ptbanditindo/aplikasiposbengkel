"""Tahap 12: pesan WhatsApp, izin pelanggan, template, dan log upaya."""
from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

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
    assert "wa_after_print" not in ops
    assert "wa_template" not in ops


def test_pengaturan_ops_dapat_diubah_dan_divalidasi(client):
    payload = {
        "tempo_hari": 14,
        "prospek_hari": 10,
        "cooldown_hari": 3,
        "garansi_akan_habis_hari": 5,
        "servis_berkala_awal_hari": 20,
    }
    updated = client.put("/api/settings/ops", json=payload)
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["tempo_hari"] == 14

    config = client.get("/api/config").json()["ops"]
    assert config["tempo_hari"] == 14

    invalid = client.put("/api/settings/ops", json={**payload, "tempo_hari": 0})
    assert invalid.status_code == 422, invalid.text


def test_struk_memuat_teks_wa_lengkap_dan_nomor_ternormalisasi(
    client, create_customer, create_unit
):
    customer = create_customer(nama="Siti WA", nomor_hp="0812-1111-2222")
    unit = create_unit(customer["id"])

    created = _make(client, unit["id"])
    assert created.status_code == 201, created.text
    receipt = created.json()["receipt"]

    assert receipt["customer_wa"] == "6281211112222"
    text = receipt["wa_text"]
    assert "No. Nota" in text
    assert receipt["no_nota"] in text
    assert "Siti WA" in text
    assert "081211112222" in text
    assert "Korok Radiator" in text
    assert "Rp 150.000" in text
    assert "Status Bayar" in text
    assert "LUNAS" in text
    assert "REKENING BENGKEL" in text
    assert "POTONG DI SINI" not in text


def test_struk_radiator_saja_tetap_berlabel_tapi_wa_tanpa_potongan(
    client, create_customer, create_unit
):
    customer = create_customer(nama="Agus Label", nomor_hp="0812-3333-4444")
    unit = create_unit(
        customer["id"],
        unit_type="RADIATOR_ONLY",
        nopol=None,
        jenis_mobil=None,
        tahun_mobil=None,
        tipe_radiator="Radiator Fortuner",
    )
    receipt = _make(client, unit["id"]).json()["receipt"]

    assert receipt["labels"]
    kode = receipt["labels"][0]["kode"]
    struk = "\n".join(receipt["struk_58"])
    assert "POTONG DI SINI" in struk
    assert kode in struk

    text = receipt["wa_text"]
    assert "POTONG DI SINI" not in text
    # Label hanya untuk instruksi potong; bagian unit tetap seperti nota.
    assert "Fortuner" in text


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
    assert "No. Nota" in body["wa_text"]
    assert "POTONG DI SINI" not in body["wa_text"]
    query = parse_qs(urlsplit(body["link"]).query, keep_blank_values=True)
    assert query["text"] == [body["wa_text"]]
    assert body["log"]["status"] == "DIBUKA"

    logs = client.get(f"/api/service-records/{record_id}/whatsapp-logs").json()
    assert len(logs) == 1
    assert logs[0]["nomor_masked"] == mask_phone("081255556666")
    assert "nomor" not in logs[0] or logs[0].get("nomor") is None

    with SessionLocal() as db:
        rows = db.query(WhatsAppLog).all()
        assert len(rows) == 1
        assert rows[0].pesan == body["wa_text"]
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
