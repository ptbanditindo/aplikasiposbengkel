"""Kasir sparepart saja, dua garansi, dan tukar barang."""
from __future__ import annotations

from datetime import date


def _get_stock(client, kode):
    response = client.get("/api/stock")
    assert response.status_code == 200, response.text
    return next(item for item in response.json() if item["kode"] == kode)


def _stock(client, kode, harga_jual, jumlah=10):
    response = client.post(
        "/api/stock",
        json={
            "kode": kode,
            "nama": "Barang " + kode,
            "harga_modal": str(int(harga_jual) // 2),
            "harga_jual": str(harga_jual),
            "jumlah": jumlah,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _sell_part(client, item, harga="10000", customer_id=None, **extra):
    payload = {
        "sparepart_only": True,
        "keluhan_awal": "",
        "metode_bayar": "CASH",
        "bayar": harga,
        "bergaransi": False,
        "garansi_tukar_aktif": True,
        "garansi_tukar_hari": 7,
        "garansi_barang_aktif": True,
        "garansi_barang_nilai": 1,
        "garansi_barang_satuan": "BULAN",
        "parts": [
            {
                "stock_item_id": item["id"],
                "jumlah": 1,
                "harga_satuan": harga,
            }
        ],
    }
    if customer_id:
        payload["customer_id"] = customer_id
    payload.update(extra)
    return client.post("/api/pos/transaction", json=payload)


def test_sparepart_saja_tanpa_pelanggan_dan_tanpa_followup(client):
    item = _stock(client, "TUKAR-A", 10000)
    response = _sell_part(client, item)
    assert response.status_code == 201, response.text
    body = response.json()
    record = body["record"]
    assert record["sparepart_only"] is True
    assert record["customer_nama"] == "Pelanggan Umum"
    assert record["unit_deskripsi"] == "Pembelian sparepart"
    assert record["garansi_tukar_aktif"] is True
    assert record["garansi_tukar_hari"] == 7
    assert record["garansi_barang_aktif"] is True
    assert record["garansi_barang_nilai"] == 1
    assert record["garansi_barang_satuan"] == "BULAN"
    assert record["bergaransi"] is True
    text = "\n".join(body["receipt"]["struk_58"])
    assert "GARANSI SPAREPART" in text
    assert "Garansi tukar" in text
    assert "Garansi barang" in text

    followup = client.get("/api/followup/items", params={"filter": "semua"})
    assert followup.status_code == 200, followup.text
    assert all(
        row.get("service_record_id") != record["id"]
        for row in followup.json()["items"]
    )
    overview = client.get("/api/customers/overview").json()
    assert all(row["nama"] != "Pelanggan Umum" for row in overview)
    assert _get_stock(client, "TUKAR-A")["jumlah"] == 9


def test_sparepart_saja_memakai_pelanggan_dipilih(client, create_customer):
    customer = create_customer(nama="Pelanggan Sparepart")
    item = _stock(client, "TUKAR-B", 20000)
    response = _sell_part(
        client, item, harga="20000", customer_id=customer["id"]
    )
    assert response.status_code == 201, response.text
    record = response.json()["record"]
    assert record["customer_nama"] == "Pelanggan Sparepart"
    assert record["customer_id"] == customer["id"]
    assert record["unit_deskripsi"] == "Pembelian sparepart"
    overview = client.get("/api/customers/overview").json()
    row = next(item for item in overview if item["id"] == customer["id"])
    assert row["total_unit"] == 0
    assert row["units"] == []


def test_tukar_ke_barang_lebih_mahal_menambah_bayar(client):
    lama = _stock(client, "TUKAR-C", 10000)
    baru = _stock(client, "TUKAR-D", 20000)
    sold = _sell_part(client, lama)
    assert sold.status_code == 201, sold.text
    record = sold.json()["record"]
    part_id = sold.json()["receipt"]["parts"][0]["id"]

    response = client.post(
        f"/api/service-records/{record['id']}/exchange",
        json={
            "service_part_id": part_id,
            "stock_item_id": baru["id"],
            "jumlah": 1,
            "harga_ganti": "20000",
            "bayar_tambahan": True,
            "metode": "CASH",
            "alasan": "Ukuran tidak cocok",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["jenis"] == "TUKAR"
    assert body["ganti_nama"] == "Barang TUKAR-D"
    assert body["ganti_jumlah"] == 1
    assert body["total_nilai"] == "10000.00"

    detail = client.get(f"/api/service-records/{record['id']}").json()
    assert detail["total_servis"] == "30000.00"
    assert detail["total_retur"] == "10000.00"
    assert detail["total_dibayar"] == "20000.00"
    assert detail["sisa_bayar"] == "0.00"
    payments = client.get(
        f"/api/service-records/{record['id']}/payments"
    ).json()
    assert any(
        row["jenis"] == "TUKAR_TAMBAHAN" and row["nominal"] == "10000.00"
        for row in payments
    )
    assert _get_stock(client, "TUKAR-C")["jumlah"] == 10
    assert _get_stock(client, "TUKAR-D")["jumlah"] == 9


def test_tukar_ke_barang_lebih_murah_mengembalikan_selisih(client):
    lama = _stock(client, "TUKAR-E", 10000)
    murah = _stock(client, "TUKAR-F", 5000)
    sold = _sell_part(client, lama)
    assert sold.status_code == 201, sold.text
    record = sold.json()["record"]
    part_id = sold.json()["receipt"]["parts"][0]["id"]

    response = client.post(
        f"/api/service-records/{record['id']}/exchange",
        json={
            "service_part_id": part_id,
            "stock_item_id": murah["id"],
            "jumlah": 1,
            "harga_ganti": "5000",
            "alasan": "Minta ukuran lebih kecil",
        },
    )
    assert response.status_code == 201, response.text

    detail = client.get(f"/api/service-records/{record['id']}").json()
    assert detail["total_servis"] == "15000.00"
    assert detail["total_retur"] == "10000.00"
    assert detail["total_dibayar"] == "5000.00"
    assert detail["sisa_bayar"] == "0.00"
    payments = client.get(
        f"/api/service-records/{record['id']}/payments"
    ).json()
    assert any(
        row["jenis"] == "REFUND" and row["nominal"] == "-5000.00"
        for row in payments
    )
    assert _get_stock(client, "TUKAR-E")["jumlah"] == 10
    assert _get_stock(client, "TUKAR-F")["jumlah"] == 9


def test_tukar_sparepart_tidak_boleh_stok_kurang(client):
    lama = _stock(client, "TUKAR-G", 10000)
    baru = _stock(client, "TUKAR-H", 20000, jumlah=1)
    sold = _sell_part(client, lama)
    assert sold.status_code == 201, sold.text
    record = sold.json()["record"]
    part_id = sold.json()["receipt"]["parts"][0]["id"]
    response = client.post(
        f"/api/service-records/{record['id']}/exchange",
        json={
            "service_part_id": part_id,
            "stock_item_id": baru["id"],
            "jumlah": 2,
            "harga_ganti": "20000",
            "alasan": "Tukar dua unit",
        },
    )
    assert response.status_code == 400, response.text
