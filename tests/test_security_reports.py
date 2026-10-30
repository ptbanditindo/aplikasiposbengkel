"""Audit keamanan & laporan: sesi PIN, XSS, SQL injection, rekap kas."""
from __future__ import annotations

from datetime import date


def test_hapus_stok_wajib_sesi(client, anon_client):
    created = client.post(
        "/api/stock",
        json={
            "kode": "SEC-001",
            "nama": "Sparepart Uji Keamanan",
            "harga_modal": "10000",
            "harga_jual": "15000",
            "jumlah": 2,
        },
    )
    assert created.status_code == 201, created.text
    stock_id = created.json()["id"]

    assert anon_client.delete(f"/api/stock/{stock_id}").status_code == 401

    deleted = client.delete(f"/api/stock/{stock_id}")
    assert deleted.status_code == 204
    listed = client.get("/api/stock").json()
    assert all(item["id"] != stock_id for item in listed)


def test_hapus_tarif_jasa_wajib_sesi(client, anon_client):
    created = client.post(
        "/api/harga-jasa",
        json={"nama": "Jasa Uji Keamanan", "harga_standar": "50000"},
    )
    assert created.status_code == 201, created.text
    jasa_id = created.json()["id"]

    assert anon_client.delete(f"/api/harga-jasa/{jasa_id}").status_code == 401
    assert client.delete(f"/api/harga-jasa/{jasa_id}").status_code == 204


def test_endpoint_admin_fail_closed_saat_pin_belum_dibuat(client, anon_client):
    from sqlalchemy import delete

    from database.models import AppSetting
    from database.session import SessionLocal

    with SessionLocal() as db:
        db.execute(delete(AppSetting).where(AppSetting.key.like("auth.%")))
        db.commit()

    response = anon_client.post("/api/admin/backup")
    assert response.status_code == 401


def test_header_token_admin_lama_tidak_lagi_diterima(anon_client):
    response = anon_client.post(
        "/api/admin/backup", headers={"X-Admin-Token": "test-admin-token"}
    )
    assert response.status_code == 401


def test_config_tidak_membocorkan_rahasia(client):
    response = client.get("/api/config")
    assert response.status_code == 200
    raw = response.text
    assert "test-admin-token" not in raw
    assert "SECRET_KEY" not in raw
    assert "admin_token_required" not in response.json()
    assert response.json()["bengkel"]["bank_nama"] == "BCA TEST"


def test_xss_payload_tersimpan_sebagai_teks_biasa(client):
    payload = "<script>alert('hack')</script>"
    response = client.post(
        "/api/customers",
        json={"nama": payload, "nomor_hp": "081277778888"},
    )

    assert response.status_code == 201, response.text
    assert response.json()["nama"] == payload

    search = client.get("/api/customers/search", params={"q": "script"})
    assert search.status_code == 200
    assert search.json()[0]["nama"] == payload


def test_pencarian_tahan_sql_injection(client, create_customer):
    create_customer(nama="Budi Santoso", nomor_hp="081211112222")

    injection = client.get(
        "/api/customers/search", params={"q": "' OR 'x'='x"}
    )
    assert injection.status_code == 200
    assert injection.json() == []

    records = client.get(
        "/api/service-records", params={"q": "' UNION SELECT * FROM customers --"}
    )
    assert records.status_code == 200
    assert records.json() == []


def test_laporan_kas_harian_memisahkan_cash_dan_transfer(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer()
    unit = create_unit(customer["id"])

    cash = make_transaction(
        unit["id"],
        jobs=[{"deskripsi": "Korok", "jumlah": 1, "harga": "150000"}],
        metode_bayar="CASH",
        bayar="200000",
    )
    assert cash.status_code == 201, cash.text

    transfer = make_transaction(
        unit["id"],
        jobs=[{"deskripsi": "Las", "jumlah": 1, "harga": "175000"}],
        metode_bayar="TRANSFER",
    )
    assert transfer.status_code == 201, transfer.text

    report = client.get(
        "/api/reports/daily-cash", params={"tanggal": date.today().isoformat()}
    )
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["jumlah_transaksi"] == 2
    assert body["total_omset"] == "325000.00"
    assert body["total_cash"] == "150000.00"
    assert body["total_transfer"] == "175000.00"
    assert body["laba_kotor"] == "0.00"
    assert len(body["transaksi"]) == 2

    period = client.get(
        "/api/reports/period",
        params={
            "start": date.today().isoformat(),
            "end": date.today().isoformat(),
        },
    )
    assert period.status_code == 200
    assert period.json()["total_omset"] == "325000.00"
    assert len(period.json()["harian"]) == 1


def test_laporan_stok_terjual_satu_baris_per_penjualan(
    client, create_customer, create_unit, make_transaction, stock
):
    customer = create_customer(nama="Siti Aminah", nomor_hp="081233334444")
    unit = create_unit(customer["id"], nopol="B 9999 XYZ")
    tutup = stock("SP-003")
    selang = stock("SP-007")

    first = make_transaction(
        unit["id"],
        jobs=[],
        parts=[
            {
                "stock_item_id": tutup["id"],
                "nama_part": "Tutup Radiator 0.9",
                "jumlah": 1,
                "harga_satuan": "35000",
            },
            {
                "stock_item_id": selang["id"],
                "nama_part": "Selang Radiator Atas",
                "jumlah": 1,
                "harga_satuan": "50000",
            },
        ],
    )
    assert first.status_code == 201, first.text

    second = make_transaction(
        unit["id"],
        jobs=[],
        parts=[
            {
                "stock_item_id": tutup["id"],
                "nama_part": "Tutup Radiator 0.9",
                "jumlah": 2,
                "harga_satuan": "30000",
            }
        ],
    )
    assert second.status_code == 201, second.text

    report = client.get(
        "/api/reports/sold-parts",
        params={
            "start": date.today().isoformat(),
            "end": date.today().isoformat(),
        },
    )
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["jumlah_penjualan"] == 3
    assert body["total_qty"] == 4
    assert body["total_nilai"] == "145000.00"

    # Barang sama dikelompokkan; tiap harga penjualan tetap baris sendiri.
    names_prices = [
        (item["nama_part"], item["harga_satuan"]) for item in body["items"]
    ]
    assert names_prices == [
        ("Selang Radiator Atas", "50000.00"),
        ("Tutup Radiator 0.9", "35000.00"),
        ("Tutup Radiator 0.9", "30000.00"),
    ]
    assert body["items"][0]["customer_nama"] == "Siti Aminah"
    assert body["items"][0]["unit_deskripsi"] == "B 9999 XYZ (Avanza)"
    assert body["items"][2]["subtotal"] == "60000.00"

    # Tanpa tanggal = seluruh riwayat.
    everything = client.get("/api/reports/sold-parts")
    assert everything.status_code == 200
    assert everything.json()["jumlah_penjualan"] == 3


def test_laporan_stok_terjual_validasi_rentang(client):
    today = date.today().isoformat()

    only_start = client.get("/api/reports/sold-parts", params={"start": today})
    assert only_start.status_code == 400

    reversed_range = client.get(
        "/api/reports/sold-parts",
        params={"start": today, "end": "2020-01-01"},
    )
    assert reversed_range.status_code == 400

    too_wide = client.get(
        "/api/reports/sold-parts",
        params={"start": "2020-01-01", "end": "2023-01-01"},
    )
    assert too_wide.status_code == 400
