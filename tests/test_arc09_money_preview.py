"""ARC-09: nilai uang final dari server dan pratinjau kasir konsisten."""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

MONEY_RE = re.compile(r"^-?\d+\.\d{2}$")

PREVIEW_JOBS = [
    {"deskripsi": "Servis radiator", "jumlah": 3, "harga": "123456.55"}
]
PREVIEW_PARTS = [
    {
        "nama_part": "Upper Tank",
        "jumlah": 2,
        "harga_satuan": "1000.05",
        "harga_modal": "700.05",
    }
]


def _preview(client, **overrides):
    payload = {
        "diskon": "0",
        "metode_bayar": "TRANSFER",
        "bayar": "0",
        "jobs": PREVIEW_JOBS,
        "parts": PREVIEW_PARTS,
    }
    payload.update(overrides)
    return client.post("/api/pos/preview", json=payload)


def test_preview_memakai_mesin_harga_yang_sama_dengan_transaksi(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer(nama="Pelanggan ARC09")
    unit = create_unit(customer["id"], nopol="B 0901 ARC")

    response = _preview(client, diskon="500.10")
    assert response.status_code == 200, response.text
    preview = response.json()

    # Pratinjau tidak boleh mengklaim sebagai nilai final.
    assert preview["is_final"] is False
    assert preview["biaya_jasa"] == "370369.65"
    assert preview["total_part"] == "2000.10"
    assert preview["subtotal"] == "372369.75"
    assert preview["diskon"] == "500.10"
    assert preview["total_servis"] == "371869.65"
    assert preview["jobs"][0]["subtotal"] == "370369.65"
    assert preview["parts"][0]["subtotal"] == "2000.10"
    # Transfer selalu pas, kembalian nol.
    assert preview["bayar"] == "371869.65"
    assert preview["kembalian"] == "0.00"
    assert preview["kekurangan"] == "0.00"

    created = make_transaction(
        unit["id"],
        jobs=PREVIEW_JOBS,
        parts=PREVIEW_PARTS,
        diskon="500.10",
        metode_bayar="TRANSFER",
    )
    assert created.status_code == 201, created.text
    body = created.json()
    record = body["record"]
    receipt = body["receipt"]

    for field in ("biaya_jasa", "total_part", "diskon", "total_servis"):
        assert record[field] == preview[field]
        assert receipt[field] == preview[field]
    assert receipt["jobs"][0]["subtotal"] == preview["jobs"][0]["subtotal"]
    assert receipt["parts"][0]["subtotal"] == preview["parts"][0]["subtotal"]
    assert record["total_neto"] == preview["total_servis"]
    assert receipt["total_neto"] == preview["total_servis"]

    # Semua nilai uang dikirim sebagai string desimal dua tempat (tidak ambigu).
    for value in (
        preview["biaya_jasa"],
        preview["total_part"],
        preview["subtotal"],
        preview["diskon"],
        preview["total_servis"],
        preview["bayar"],
        preview["kembalian"],
        preview["kekurangan"],
    ):
        assert MONEY_RE.match(value), value


def test_preview_tidak_menyimpan_transaksi_atau_mengubah_laporan(
    client, create_customer, create_unit
):
    customer = create_customer(nama="Pelanggan Pratinjau")
    create_unit(customer["id"], nopol="B 0902 ARC")

    assert _preview(client, diskon="0").status_code == 200
    assert client.get("/api/service-records").json() == []

    report = client.get(
        "/api/reports/daily-cash", params={"tanggal": date.today().isoformat()}
    ).json()
    assert report["jumlah_transaksi"] == 0
    assert report["total_omset"] == "0.00"


def test_preview_diskon_melebihi_subtotal_ditolak_sama_seperti_simpan(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer(nama="Pelanggan Diskon")
    unit = create_unit(customer["id"], nopol="B 0903 ARC")
    jobs = [{"deskripsi": "Servis", "jumlah": 1, "harga": "100000"}]

    preview = _preview(
        client, jobs=jobs, parts=[], diskon="150000", metode_bayar="TRANSFER"
    )
    assert preview.status_code == 400, preview.text

    created = make_transaction(
        unit["id"], jobs=jobs, parts=[], diskon="150000", metode_bayar="TRANSFER"
    )
    assert created.status_code == 400, created.text
    assert preview.json()["detail"] == created.json()["detail"]


def test_preview_uang_kurang_hanya_perkiraan_dan_simpan_tetap_ditolak(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer(nama="Pelanggan Tunai")
    unit = create_unit(customer["id"], nopol="B 0904 ARC")
    jobs = [{"deskripsi": "Servis", "jumlah": 1, "harga": "100000"}]

    preview = _preview(
        client, jobs=jobs, parts=[], metode_bayar="CASH", bayar="40000"
    )
    assert preview.status_code == 200, preview.text
    data = preview.json()
    assert data["is_final"] is False
    assert data["total_servis"] == "100000.00"
    assert data["bayar"] == "40000.00"
    assert data["kembalian"] == "0.00"
    assert data["kekurangan"] == "60000.00"

    created = make_transaction(
        unit["id"], jobs=jobs, parts=[], metode_bayar="CASH", bayar="40000"
    )
    assert created.status_code == 400, created.text
    assert "kurang" in created.json()["detail"].lower()


def test_total_nota_konsisten_dengan_laporan_backend(
    client, create_customer, create_unit, make_transaction, stock
):
    customer = create_customer(nama="Pelanggan Laporan")
    unit = create_unit(customer["id"], nopol="B 0905 ARC")
    item = stock("SP-001")

    cash = make_transaction(
        unit["id"],
        jobs=[{"deskripsi": "Servis", "jumlah": 1, "harga": "150000"}],
        parts=[
            {
                "stock_item_id": item["id"],
                "nama_part": item["nama"],
                "jumlah": 3,
                "harga_satuan": "160000",
            }
        ],
        metode_bayar="CASH",
        bayar="700000",
    )
    assert cash.status_code == 201, cash.text
    cash_body = cash.json()

    transfer = make_transaction(
        unit["id"],
        jobs=[{"deskripsi": "Kuras radiator", "jumlah": 2, "harga": "75000.50"}],
        parts=[],
        metode_bayar="TRANSFER",
    )
    assert transfer.status_code == 201, transfer.text

    part_id = cash_body["receipt"]["parts"][0]["id"]
    retur = client.post(
        f"/api/service-records/{cash_body['record']['id']}/returns",
        json={
            "alasan": "Barang tidak cocok",
            "items": [{"service_part_id": part_id, "jumlah": 1}],
        },
    )
    assert retur.status_code == 201, retur.text

    receipt = client.get(
        f"/api/service-records/{cash_body['record']['id']}/receipt"
    ).json()
    detail = client.get(
        f"/api/service-records/{cash_body['record']['id']}"
    ).json()
    assert receipt["total_neto"] == detail["total_neto"]
    assert receipt["total_neto"] == "470000.00"

    report = client.get(
        "/api/reports/daily-cash", params={"tanggal": date.today().isoformat()}
    ).json()
    records = report["transaksi"]
    assert len(records) == 2

    neto = sum(Decimal(record["total_neto"]) for record in records)
    laba = sum(Decimal(record["laba_kotor"]) for record in records)
    assert Decimal(report["total_omset"]) == neto
    assert Decimal(report["total_cash"]) + Decimal(
        report["total_transfer"]
    ) == neto
    assert Decimal(report["laba_kotor"]) == laba
    record_ids = {record["id"] for record in records}
    assert cash_body["record"]["id"] in record_ids
