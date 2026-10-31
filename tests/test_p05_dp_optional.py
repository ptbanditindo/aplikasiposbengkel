"""P-05: DP tanpa jatuh tempo, pelunasan kapan saja, pesan kendaraan selesai."""
from __future__ import annotations

from decimal import Decimal

from database.models import ServicePayment, WhatsAppLog
from database.session import SessionLocal

KATA_TERLARANG = ("hutang", "piutang", "tagihan", "kekurangan")


def _dp(client, unit_id, dp="100000"):
    return client.post(
        "/api/pos/transaction",
        json={
            "unit_id": unit_id,
            "keluhan_awal": "Servis radiator",
            "jenis_bayar": "DP",
            "dp": dp,
            "metode_bayar": "CASH",
            "jobs": [{"deskripsi": "Korok Radiator", "jumlah": 1, "harga": "150000"}],
            "parts": [],
        },
    )


def _receipt_text(receipt) -> str:
    return "\n".join(receipt["struk_58"])


def _assert_pesan_pelanggan(text: str) -> None:
    lower = text.lower()
    for kata in KATA_TERLARANG:
        assert kata not in lower, (kata, text)


def test_dp_tanpa_jatuh_tempo_tersimpan_dan_muncul_di_piutang(
    client, create_customer, create_unit
):
    customer = create_customer(nama="Dewi DP")
    unit = create_unit(customer["id"], nopol="B 5501 DPX")

    response = _dp(client, unit["id"])
    assert response.status_code == 201, response.text
    body = response.json()
    record = body["record"]
    receipt = body["receipt"]

    assert record["jatuh_tempo"] is None
    assert record["status_bayar"] == "BELUM_LUNAS"
    assert record["total_dibayar"] == "100000.00"
    assert record["sisa_bayar"] == "50000.00"
    assert receipt["jatuh_tempo"] is None

    text = _receipt_text(receipt)
    assert "BELUM LUNAS" in text
    assert "Sisa" in text
    assert "Jatuh Tempo" not in text
    assert "None" not in text
    assert "null" not in text

    receivables = client.get("/api/receivables").json()
    assert receivables["jumlah_nota"] == 1
    assert receivables["total_sisa"] == "50000.00"
    row = receivables["items"][0]["records"][0]
    assert row["jatuh_tempo"] is None
    assert row["sisa_bayar"] == "50000.00"

    completion = receipt["completion_wa_text"]
    assert "sudah selesai dikerjakan" in completion
    assert "siap diambil" in completion
    assert "DP sudah kami terima." in completion
    assert "Sisa pembayaran Rp 50.000" in completion
    _assert_pesan_pelanggan(completion)

    with SessionLocal() as db:
        payment = db.query(ServicePayment).one()
        assert payment.jenis == "DP"
        assert payment.nominal == Decimal("100000.00")


def test_pelunasan_tanpa_jatuh_tempo_sampai_lunas(
    client, create_customer, create_unit
):
    customer = create_customer(nama="Eko Lunas")
    unit = create_unit(customer["id"], nopol="B 5502 LNS")
    record_id = _dp(client, unit["id"], dp="50000").json()["record"]["id"]

    partial = client.post(
        f"/api/service-records/{record_id}/payments",
        json={"nominal": "40000", "metode": "TRANSFER"},
    )
    assert partial.status_code == 201, partial.text
    assert partial.json()["record"]["sisa_bayar"] == "60000.00"
    assert partial.json()["record"]["status_bayar"] == "BELUM_LUNAS"
    assert client.get("/api/receivables").json()["jumlah_nota"] == 1

    full = client.post(
        f"/api/service-records/{record_id}/payments",
        json={"nominal": "60000", "metode": "CASH"},
    )
    assert full.status_code == 201, full.text
    assert full.json()["record"]["status_bayar"] == "LUNAS"
    assert full.json()["record"]["sisa_bayar"] == "0.00"
    assert client.get("/api/receivables").json()["jumlah_nota"] == 0

    detail = client.get(f"/api/service-records/{record_id}/receipt").json()
    completion = detail["completion_wa_text"]
    assert "sudah selesai dikerjakan" in completion
    assert "siap diambil" in completion
    assert "Sisa pembayaran" not in completion
    assert "DP sudah kami terima" not in completion
    _assert_pesan_pelanggan(completion)


def test_whatsapp_jenis_piutang_memakai_teks_kendaraan_selesai(
    client, create_customer, create_unit
):
    customer = create_customer(nama="Fitri Selesai", nomor_hp="0812-9999-0001")
    unit = create_unit(customer["id"], nopol="B 5503 SEL")
    body = _dp(client, unit["id"]).json()
    record_id = body["record"]["id"]

    response = client.post(
        f"/api/service-records/{record_id}/whatsapp",
        json={"status": "DIBUKA", "jenis": "piutang"},
    )
    assert response.status_code == 201, response.text
    attempt = response.json()
    assert attempt["wa_text"] == body["receipt"]["completion_wa_text"]
    assert attempt["link"].startswith("https://wa.me/6281299990001?text=")
    _assert_pesan_pelanggan(attempt["wa_text"])

    with SessionLocal() as db:
        log = db.query(WhatsAppLog).one()
        assert log.jenis == "piutang"
        assert log.pesan == attempt["wa_text"]


def test_jenis_whatsapp_tidak_dikenal_ditolak(client, create_customer, create_unit):
    customer = create_customer()
    unit = create_unit(customer["id"])
    record_id = _dp(client, unit["id"]).json()["record"]["id"]

    response = client.post(
        f"/api/service-records/{record_id}/whatsapp",
        json={"status": "DIBUKA", "jenis": "followup"},
    )
    assert response.status_code == 422, response.text
