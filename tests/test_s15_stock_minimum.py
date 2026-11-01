"""Tahap 1: stok minimum, stok menipis, stok habis, dan total hutang."""
from __future__ import annotations

from database.models import StockItem


def _stock(client, nama, jumlah, stok_minimum=None):
    payload = {
        "nama": nama,
        "harga_modal": "10000",
        "harga_jual": "15000",
        "jumlah": jumlah,
        "interval_servis_bulan": 0,
    }
    if stok_minimum is not None:
        payload["stok_minimum"] = stok_minimum
    response = client.post("/api/stock", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_stok_minimum_mengikuti_pengaturan_dan_item(client, db_session):
    # Matikan bawaan agar data seed tidak ikut dihitung.
    for item in db_session.query(StockItem).all():
        item.stok_minimum = 0
    db_session.commit()
    response = client.put(
        "/api/settings/ops", json={"stok_minimum_default": 0}
    )
    assert response.status_code == 200, response.text

    low = _stock(client, "Barang Menipis", 2, 5)
    normal = _stock(client, "Barang Aman", 10, 5)
    out = _stock(client, "Barang Habis", 0, 5)
    inherited = _stock(client, "Barang Ikut Bawaan", 2)
    disabled = _stock(client, "Barang Nonaktif", 1, 0)

    assert low["stok_minimum"] == 5
    assert inherited["stok_minimum"] is None
    assert disabled["stok_minimum"] == 0
    assert normal["stok_minimum"] == 5

    report = client.get("/api/reports/daily-cash").json()
    assert report["stok_menipis"] == 1
    assert report["stok_habis"] == 1

    response = client.put(
        "/api/settings/ops", json={"stok_minimum_default": 3}
    )
    assert response.status_code == 200, response.text
    report = client.get("/api/reports/daily-cash").json()
    assert report["stok_menipis"] == 2
    assert report["stok_habis"] == 1

    # Barang yang stoknya naik di atas batas keluar dari daftar menipis.
    response = client.put(
        f"/api/stock/{low['id']}",
        json={"jumlah": 6},
    )
    assert response.status_code == 200, response.text
    report = client.get("/api/reports/daily-cash").json()
    assert report["stok_menipis"] == 1

    # Batas 0 mematikan peringatan item tersebut.
    response = client.put(
        f"/api/stock/{inherited['id']}",
        json={"stok_minimum": 0},
    )
    assert response.status_code == 200, response.text
    report = client.get("/api/reports/daily-cash").json()
    assert report["stok_menipis"] == 0

    assert out["jumlah"] == 0


def test_total_hutang_dashboard_memakai_sisa_piutang(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer(nama="Pelanggan Hutang")
    unit = create_unit(customer["id"], nopol="B 8201 HUT")
    response = make_transaction(
        unit["id"],
        jobs=[{"deskripsi": "Servis", "jumlah": 1, "harga": "150000"}],
        jenis_bayar="KREDIT",
        dp="50000",
        bayar="50000",
    )
    assert response.status_code == 201, response.text

    report = client.get("/api/reports/daily-cash").json()
    assert report["piutang_count"] == 1
    assert report["piutang_total"] == "100000.00"


def test_pengaturan_stok_minimum_bawaan(client):
    response = client.get("/api/settings/ops")
    assert response.status_code == 200, response.text
    assert response.json()["stok_minimum_default"] == 3

    response = client.put(
        "/api/settings/ops", json={"stok_minimum_default": 7}
    )
    assert response.status_code == 200, response.text
    assert response.json()["stok_minimum_default"] == 7
