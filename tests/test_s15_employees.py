"""Tahap 5-6: karyawan, penugasan nota, performa, komisi, dan struk."""
from __future__ import annotations


def _employee(
    client, nama, peran, mode="PERSEN", basis="JASA", nilai="10", **extra
):
    payload = {
        "nama": nama,
        "peran": peran,
        "aktif": True,
        "nomor_hp": "081200002222",
        "komisi_mode": mode,
        "komisi_basis": basis,
        "komisi_nilai": nilai,
    }
    payload.update(extra)
    response = client.post("/api/employees", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_penugasan_karyawan_dan_nama_di_struk(
    client, create_customer, create_unit, make_transaction
):
    mechanic = _employee(client, "Mekanik Uji", "MEKANIK", nilai="10")
    cashier = _employee(client, "Kasir Uji", "KASIR", mode="NOMINAL", nilai="5000")
    customer = create_customer(nama="Pelanggan Karyawan")
    unit = create_unit(customer["id"], nopol="B 8401 KAR")
    response = make_transaction(
        unit["id"],
        jobs=[{"deskripsi": "Servis Radiator", "jumlah": 1, "harga": "150000"}],
        cashier_employee_id=cashier["id"],
        mechanic_ids=[mechanic["id"]],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["receipt"]["cashier_nama"] == "Kasir Uji"
    assert body["receipt"]["mekanik_nama"] == "Mekanik Uji"
    text = "\n".join(body["receipt"]["struk_58"])
    assert "Kasir Uji" in text
    assert "Mekanik Uji" in text

    response = client.get(f"/api/employees/{mechanic['id']}/performance")
    assert response.status_code == 200, response.text
    performance = response.json()
    assert performance["jumlah_nota"] == 1
    assert performance["total_nilai"] == "150000.00"
    assert performance["komisi_total"] == "15000.00"

    response = client.put(
        f"/api/employees/{mechanic['id']}/commissions/"
        + str(body["record"]["id"]),
        json={"nominal": "20000"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["komisi_total"] == "20000.00"


def test_komisi_manual_dibatasi_total_nota_dan_sisa_setelah_modal(
    client, create_customer, create_unit, make_transaction
):
    mechanic = _employee(client, "Mekanik Batas", "MEKANIK", nilai="0")
    customer = create_customer(nama="Pelanggan Batas")
    unit = create_unit(customer["id"], nopol="B 8408 BAT")
    part = next(
        item
        for item in client.get("/api/stock").json()
        if item["kode"] == "SP-003"
    )
    response = make_transaction(
        unit["id"],
        jobs=[{"deskripsi": "Servis", "jumlah": 1, "harga": "50000"}],
        parts=[
            {
                "stock_item_id": part["id"],
                "jumlah": 1,
                "harga_satuan": "35000",
            }
        ],
        mechanic_ids=[mechanic["id"]],
    )
    assert response.status_code == 201, response.text
    record_id = response.json()["record"]["id"]
    url = f"/api/employees/{mechanic['id']}/commissions/{record_id}"

    # Nota 85.000 (jasa 50.000 + part 35.000), modal SP-003 18.000.
    over_nota = client.put(url, json={"nominal": "90000"})
    assert over_nota.status_code == 400, over_nota.text
    assert "total nota" in over_nota.json()["detail"]

    over_laba = client.put(url, json={"nominal": "70000"})
    assert over_laba.status_code == 400, over_laba.text
    assert "harga modal" in over_laba.json()["detail"]

    pas = client.put(url, json={"nominal": "67000"})
    assert pas.status_code == 200, pas.text
    assert pas.json()["komisi_total"] == "67000.00"


def test_mekanik_boleh_kosong_dan_kasir_harus_berperan_kasir(
    client, create_customer, create_unit, make_transaction
):
    mechanic = _employee(client, "Mekanik Saja", "MEKANIK", nilai="0")
    customer = create_customer(nama="Pelanggan Tanpa Mekanik")
    unit = create_unit(customer["id"], nopol="B 8402 TAN")
    response = make_transaction(unit["id"])
    assert response.status_code == 201, response.text
    assert response.json()["receipt"]["mekanik_nama"] == "Tidak dicatat"

    response = make_transaction(
        unit["id"],
        cashier_employee_id=mechanic["id"],
    )
    assert response.status_code == 400, response.text


def test_komisi_beberapa_mekanik_dibagi_rata(
    client, create_customer, create_unit, make_transaction
):
    first = _employee(client, "Mekanik Satu", "MEKANIK", nilai="10")
    second = _employee(client, "Mekanik Dua", "MEKANIK", nilai="10")
    customer = create_customer(nama="Pelanggan Dua Mekanik")
    unit = create_unit(customer["id"], nopol="B 8403 DUA")
    response = make_transaction(
        unit["id"],
        jobs=[{"deskripsi": "Servis", "jumlah": 1, "harga": "200000"}],
        mechanic_ids=[first["id"], second["id"]],
    )
    assert response.status_code == 201, response.text
    for employee in (first, second):
        body = client.get(
            f"/api/employees/{employee['id']}/performance"
        ).json()
        assert body["komisi_total"] == "10000.00"


def test_laporan_estimasi_laba_bersih_setelah_komisi(
    client, create_customer, create_unit, make_transaction
):
    mechanic = _employee(
        client, "Mekanik Laba", "MEKANIK", basis="KEDUANYA", nilai="10"
    )
    customer = create_customer(nama="Pelanggan Laba")
    unit = create_unit(customer["id"], nopol="B 8405 LAB")
    stock = client.get("/api/stock").json()
    part = next(item for item in stock if item["kode"] == "SP-003")
    response = make_transaction(
        unit["id"],
        jobs=[{"deskripsi": "Servis", "jumlah": 1, "harga": "150000"}],
        parts=[
            {
                "stock_item_id": part["id"],
                "jumlah": 1,
                "harga_satuan": "35000",
            }
        ],
        mechanic_ids=[mechanic["id"]],
    )
    assert response.status_code == 201, response.text

    report = client.get("/api/reports/daily-cash").json()
    assert report["laba_kotor"] == "17000.00"
    assert report["total_jasa"] == "150000.00"
    # Komisi barang dihitung dari margin (35.000 - 18.000), bukan total jual.
    assert report["komisi_total"] == "16700.00"
    assert report["laba_bersih_setelah_komisi"] == "150300.00"


def test_komisi_barang_dari_margin_dan_jasa_terpisah(
    client, create_customer, create_unit, make_transaction
):
    mechanic = _employee(
        client,
        "Mekanik Margin",
        "MEKANIK",
        nilai="0",
        komisi_barang_nilai="10",
        komisi_jasa_nilai="20",
    )
    customer = create_customer(nama="Pelanggan Margin")
    unit = create_unit(customer["id"], nopol="B 8406 MAR")
    part = next(
        item
        for item in client.get("/api/stock").json()
        if item["kode"] == "SP-003"
    )
    response = make_transaction(
        unit["id"],
        jobs=[{"deskripsi": "Servis", "jumlah": 1, "harga": "150000"}],
        parts=[
            {
                "stock_item_id": part["id"],
                "jumlah": 1,
                "harga_satuan": "35000",
            }
        ],
        mechanic_ids=[mechanic["id"]],
    )
    assert response.status_code == 201, response.text
    body = client.get(f"/api/employees/{mechanic['id']}/performance").json()
    # Margin sparepart 17.000 x 10% = 1.700; jasa 150.000 x 20% = 30.000.
    assert body["komisi_total"] == "31700.00"


def test_karyawan_gaji_tidak_mendapat_komisi(
    client, create_customer, create_unit, make_transaction
):
    salaried = _employee(
        client,
        "Kasir Gaji",
        "KASIR",
        nilai="0",
        jenis_imbalan="GAJI",
        gaji_bulanan="3000000",
    )
    customer = create_customer(nama="Pelanggan Gaji")
    unit = create_unit(customer["id"], nopol="B 8404 GAJ")
    response = make_transaction(
        unit["id"],
        jobs=[{"deskripsi": "Servis", "jumlah": 1, "harga": "100000"}],
        cashier_employee_id=salaried["id"],
    )
    assert response.status_code == 201, response.text
    body = client.get(
        f"/api/employees/{salaried['id']}/performance"
    ).json()
    assert body["employee"]["jenis_imbalan"] == "GAJI"
    assert body["employee"]["gaji_bulanan"] == "3000000.00"
    assert body["komisi_total"] == "0.00"
