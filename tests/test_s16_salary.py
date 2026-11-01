"""Pembayaran gaji aktual dan pengaruhnya ke laba bersih."""
from __future__ import annotations

from datetime import date, timedelta


def _employee(client, nama="Kasir Gaji", **extra):
    payload = {
        "nama": nama,
        "peran": "KASIR",
        "aktif": True,
        "jenis_imbalan": "GAJI",
        "gaji_bulanan": "3000000",
        "komisi_mode": "PERSEN",
        "komisi_basis": "JASA",
        "komisi_nilai": "0",
    }
    payload.update(extra)
    response = client.post("/api/employees", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _salary(client, employee_id, nominal="3000000", tanggal=None, periode=None):
    payload = {
        "employee_id": employee_id,
        "periode": periode or date.today().strftime("%Y-%m"),
        "tanggal": (tanggal or date.today()).isoformat(),
        "nominal": nominal,
        "metode": "TRANSFER",
        "catatan": "Gaji bulan ini",
    }
    return client.post("/api/salary-payments", json=payload)


def test_gaji_dibayar_mengurangi_laba_bersih(
    client, create_customer, create_unit, make_transaction
):
    employee = _employee(client)
    customer = create_customer(nama="Pelanggan Gaji Laporan")
    unit = create_unit(customer["id"], nopol="B 8601 GAJ")
    response = make_transaction(
        unit["id"],
        jobs=[{"deskripsi": "Servis", "jumlah": 1, "harga": "150000"}],
    )
    assert response.status_code == 201, response.text

    response = _salary(client, employee["id"])
    assert response.status_code == 201, response.text
    payment = response.json()
    assert payment["nama_karyawan"] == "Kasir Gaji"
    assert payment["nominal"] == "3000000.00"

    report = client.get("/api/reports/daily-cash").json()
    assert report["komisi_total"] == "0.00"
    assert report["laba_bersih_setelah_komisi"] == "150000.00"
    assert report["gaji_dibayar"] == "3000000.00"
    assert report["laba_bersih_setelah_komisi_dan_gaji"] == "-2850000.00"

    response = client.put(
        f"/api/salary-payments/{payment['id']}",
        json={"nominal": "2500000"},
    )
    assert response.status_code == 200, response.text
    report = client.get("/api/reports/daily-cash").json()
    assert report["gaji_dibayar"] == "2500000.00"
    assert report["laba_bersih_setelah_komisi_dan_gaji"] == "-2350000.00"

    response = client.delete(f"/api/salary-payments/{payment['id']}")
    assert response.status_code == 204, response.text
    report = client.get("/api/reports/daily-cash").json()
    assert report["gaji_dibayar"] == "0.00"
    assert report["laba_bersih_setelah_komisi_dan_gaji"] == "150000.00"


def test_gaji_di_luar_periode_tidak_dipotong(client):
    employee = _employee(client)
    old_day = date.today() - timedelta(days=5)
    response = _salary(client, employee["id"], tanggal=old_day)
    assert response.status_code == 201, response.text

    today = client.get("/api/reports/daily-cash").json()
    assert today["gaji_dibayar"] == "0.00"

    period = client.get(
        "/api/reports/period",
        params={
            "start": old_day.isoformat(),
            "end": date.today().isoformat(),
        },
    ).json()
    assert period["gaji_dibayar"] == "3000000.00"


def test_riwayat_gaji_tetap_ada_setelah_karyawan_dihapus(client):
    employee = _employee(client, nama="Kasir Historis")
    response = _salary(client, employee["id"], nominal="1250000")
    assert response.status_code == 201, response.text

    response = client.delete(f"/api/employees/{employee['id']}")
    assert response.status_code == 204, response.text

    rows = client.get("/api/salary-payments").json()
    assert len(rows) == 1
    assert rows[0]["employee_id"] is None
    assert rows[0]["nama_karyawan"] == "Kasir Historis"
    assert rows[0]["nominal"] == "1250000.00"


def test_validasi_gaji(client):
    employee = _employee(client)
    assert _salary(client, employee["id"], nominal="0").status_code == 422
    assert (
        _salary(client, employee["id"], periode="2026-13").status_code == 400
    )
    assert (
        client.post(
            "/api/salary-payments",
            json={
                "employee_id": 99999,
                "periode": "2026-11",
                "nominal": "100000",
            },
        ).status_code
        == 404
    )
