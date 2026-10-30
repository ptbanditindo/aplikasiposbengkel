"""TC-06 s/d TC-12: harga deal, stok atomik, pembayaran & presisi desimal."""
from __future__ import annotations

from datetime import date

import pytest

ADMIN_HEADERS = {"X-Admin-Token": "test-admin-token"}


def _receipt_text(body) -> str:
    return "\n".join(body["receipt"]["struk_58"])


def test_tc06_harga_jasa_deal_override_tanpa_ubah_master(
    client, create_customer, create_unit, make_transaction, jasa
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    master = jasa("Korok / Kuras Kerak Radiator")
    assert master["harga_standar"] == "150000.00"

    response = make_transaction(
        unit["id"],
        jobs=[
            {
                "harga_jasa_id": master["id"],
                "deskripsi": master["nama"],
                "jumlah": 1,
                "harga": "175000",
            }
        ],
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["record"]["biaya_jasa"] == "175000.00"
    assert body["record"]["total_servis"] == "175000.00"
    assert body["receipt"]["jobs"][0]["harga"] == "175000.00"
    assert "175.000" in _receipt_text(body)

    # Master tarif jasa di gudang tidak boleh tertimpa harga deal.
    assert jasa("Korok / Kuras Kerak Radiator")["harga_standar"] == "150000.00"


def test_tc07_harga_part_deal_override_dan_laba_kotor(
    client, create_customer, create_unit, make_transaction, stock
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    item = stock("SP-001")
    assert item["harga_jual"] == "135000.00"
    assert item["harga_modal"] == "85000.00"

    response = make_transaction(
        unit["id"],
        jobs=[],
        parts=[
            {
                "stock_item_id": item["id"],
                "nama_part": "",
                "jumlah": 2,
                "harga_satuan": "160000",
            }
        ],
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["record"]["total_part"] == "320000.00"
    assert body["record"]["total_servis"] == "320000.00"
    assert body["receipt"]["parts"][0]["harga_satuan"] == "160000.00"
    assert body["receipt"]["parts"][0]["subtotal"] == "320000.00"
    # (160.000 deal - 85.000 modal) x 2 = 150.000
    assert body["laba_kotor"] == "150000.00"
    assert "320.000" in _receipt_text(body)

    # Harga patokan master di gudang tetap.
    assert stock("SP-001")["harga_jual"] == "135000.00"


def test_tc08_servis_potong_stok_gudang_otomatis(
    client, create_customer, create_unit, make_transaction, stock
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    item = stock("SP-007")
    initial = item["jumlah"]

    response = make_transaction(
        unit["id"],
        jobs=[],
        parts=[
            {
                "stock_item_id": item["id"],
                "nama_part": "Selang Radiator Atas",
                "jumlah": 2,
                "harga_satuan": "50000",
            }
        ],
    )

    assert response.status_code == 201, response.text
    assert stock("SP-007")["jumlah"] == initial - 2


def test_tc09_stok_kurang_ditolak_lalu_boleh_dikonfirmasi(
    client, create_customer, create_unit, make_transaction, stock
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    item = stock("SP-001")
    initial = item["jumlah"]
    payload = {
        "jobs": [],
        "parts": [
            {
                "stock_item_id": item["id"],
                "nama_part": "",
                "jumlah": initial + 40,
                "harga_satuan": "135000",
            }
        ],
    }

    rejected = make_transaction(unit["id"], **payload)
    assert rejected.status_code == 409, rejected.text
    detail = rejected.json()["detail"]
    assert "tidak mencukupi" in detail["message"]
    assert detail["items"][0]["tersedia"] == initial
    assert detail["items"][0]["diminta"] == initial + 40
    # Rollback utuh: stok tidak berubah & nota tidak dibuat.
    assert stock("SP-001")["jumlah"] == initial
    assert client.get("/api/service-records").json() == []

    confirmed = make_transaction(unit["id"], izinkan_stok_minus=True, **payload)
    assert confirmed.status_code == 201, confirmed.text
    body = confirmed.json()
    assert body["warnings"]
    assert "stok minus" in body["warnings"][0]
    assert stock("SP-001")["jumlah"] == initial - (initial + 40)


def test_tc10_pembayaran_cash_hitung_kembalian(
    client, create_customer, create_unit, make_transaction, stock
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    item = stock("SP-001")

    response = make_transaction(
        unit["id"],
        jobs=[{"deskripsi": "Korok Radiator", "jumlah": 1, "harga": "150000"}],
        parts=[
            {
                "stock_item_id": item["id"],
                "nama_part": "",
                "jumlah": 1,
                "harga_satuan": "135000",
            }
        ],
        metode_bayar="CASH",
        bayar="300000",
    )

    assert response.status_code == 201, response.text
    record = response.json()["record"]
    assert record["total_servis"] == "285000.00"
    assert record["bayar"] == "300000.00"
    assert record["kembalian"] == "15000.00"
    receipt = _receipt_text(response.json())
    assert "CASH / TUNAI" in receipt
    assert "15.000" in receipt


def test_tc11_cash_kurang_ditolak_tanpa_menyimpan_nota(
    client, create_customer, create_unit, make_transaction, stock
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    item = stock("SP-001")
    initial_stock = item["jumlah"]

    response = make_transaction(
        unit["id"],
        jobs=[{"deskripsi": "Korok Radiator", "jumlah": 1, "harga": "150000"}],
        parts=[
            {
                "stock_item_id": item["id"],
                "nama_part": "",
                "jumlah": 1,
                "harga_satuan": "135000",
            }
        ],
        metode_bayar="CASH",
        bayar="100000",
    )

    assert response.status_code == 400, response.text
    assert "kurang" in response.json()["detail"].lower()
    assert client.get("/api/service-records").json() == []
    assert stock("SP-001")["jumlah"] == initial_stock


def test_tc12_pembayaran_transfer_pas_kembalian_nol(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer()
    unit = create_unit(customer["id"])

    response = make_transaction(
        unit["id"],
        jobs=[{"deskripsi": "Las Radiator", "jumlah": 1, "harga": "175000"}],
        metode_bayar="TRANSFER",
        bayar="999999",
    )

    assert response.status_code == 201, response.text
    record = response.json()["record"]
    assert record["total_servis"] == "175000.00"
    assert record["bayar"] == "175000.00"
    assert record["kembalian"] == "0.00"
    assert "TRANSFER BANK" in _receipt_text(response.json())


def test_presisi_desimal_tidak_terkena_floating_point(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer()
    unit = create_unit(customer["id"])

    response = make_transaction(
        unit["id"],
        jobs=[{"deskripsi": "Tes Presisi", "jumlah": 1, "harga": "0"}],
        parts=[
            {"nama_part": "Part A", "jumlah": 1, "harga_satuan": "0.10"},
            {"nama_part": "Part B", "jumlah": 1, "harga_satuan": "0.20"},
        ],
    )

    assert response.status_code == 201, response.text
    record = response.json()["record"]
    assert record["total_part"] == "0.30"
    assert record["total_servis"] == "0.30"
    assert record["bayar"] == "0.30"
    assert record["kembalian"] == "0.00"


def test_laba_kotor_historis_memakai_snapshot_modal(
    client, create_customer, create_unit, make_transaction, stock
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    item = stock("SP-001")

    created = make_transaction(
        unit["id"],
        jobs=[],
        parts=[
            {
                "stock_item_id": item["id"],
                "nama_part": "",
                "jumlah": 2,
                "harga_satuan": "160000",
            }
        ],
    )
    assert created.status_code == 201, created.text
    body = created.json()
    record_id = body["record"]["id"]
    assert body["laba_kotor"] == "150000.00"
    assert body["record"]["laba_kotor"] == "150000.00"

    # Modal master dinaikkan: laba nota lama tidak boleh ikut berubah.
    updated = client.put(
        f"/api/stock/{item['id']}", json={"harga_modal": "100000"}
    )
    assert updated.status_code == 200, updated.text

    detail = client.get(f"/api/service-records/{record_id}").json()
    assert detail["laba_kotor"] == "150000.00"

    report = client.get(
        "/api/reports/daily-cash", params={"tanggal": date.today().isoformat()}
    ).json()
    assert report["laba_kotor"] == "150000.00"

    # Master dihapus pun laba historis tetap terbaca dari snapshot nota.
    deleted = client.delete(
        f"/api/stock/{item['id']}", headers=ADMIN_HEADERS
    )
    assert deleted.status_code == 204, deleted.text
    detail_after_delete = client.get(f"/api/service-records/{record_id}").json()
    assert detail_after_delete["laba_kotor"] == "150000.00"


def test_rollback_atomik_saat_penyimpanan_part_gagal(
    client, create_customer, create_unit, make_transaction, stock, monkeypatch
):
    from services import pos_service

    customer = create_customer()
    unit = create_unit(customer["id"])
    item = stock("SP-001")
    initial_stock = item["jumlah"]

    class Boom:
        def __init__(self, **_kwargs):
            raise RuntimeError("simulasi kegagalan simpan part")

    monkeypatch.setattr(pos_service, "ServicePart", Boom)

    with pytest.raises(RuntimeError):
        make_transaction(
            unit["id"],
            jobs=[{"deskripsi": "Korok", "jumlah": 1, "harga": "150000"}],
            parts=[
                {
                    "stock_item_id": item["id"],
                    "nama_part": "",
                    "jumlah": 1,
                    "harga_satuan": "135000",
                }
            ],
        )

    # Rollback utuh: tidak ada nota baru & stok tidak berkurang.
    assert client.get("/api/service-records").json() == []
    assert stock("SP-001")["jumlah"] == initial_stock


def test_nomor_nota_unik_dan_berurutan(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    prefix = f"INV-{date.today():%Y%m%d}-"

    first = make_transaction(unit["id"]).json()["record"]["no_nota"]
    second = make_transaction(unit["id"]).json()["record"]["no_nota"]

    assert first == f"{prefix}0001"
    assert second == f"{prefix}0002"

    records = client.get("/api/service-records").json()
    assert len(records) == 2
    assert {record["no_nota"] for record in records} == {first, second}
