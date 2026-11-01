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


def _salary(
    client,
    employee_id,
    nominal="3000000",
    tanggal=None,
    periode=None,
    potongan_hutang="0",
    cicilan_hutang="0",
    bonus="0",
):
    payload = {
        "employee_id": employee_id,
        "periode": periode or date.today().strftime("%Y-%m"),
        "tanggal": (tanggal or date.today()).isoformat(),
        "nominal": nominal,
        "potongan_hutang": potongan_hutang,
        "cicilan_hutang": cicilan_hutang,
        "bonus": bonus,
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


def test_ringkasan_gaji_dan_komisi_per_siklus(
    client, create_customer, create_unit, make_transaction
):
    today = date.today()
    employee = _employee(
        client,
        nama="Mekanik Siklus",
        peran="KEDUANYA",
        jenis_imbalan="KOMISI_GAJI",
        komisi_jasa_nilai="10",
        payroll_period="TANGGAL",
        payroll_tanggal=str(today.day),
    )
    customer = create_customer(nama="Pelanggan Siklus")
    unit = create_unit(customer["id"], nopol="B 8602 SIK")
    response = make_transaction(
        unit["id"],
        jobs=[{"deskripsi": "Servis", "jumlah": 1, "harga": "100000"}],
        mechanic_ids=[employee["id"]],
    )
    assert response.status_code == 201, response.text
    assert _salary(client, employee["id"], nominal="3000000").status_code == 201

    summary = client.get("/api/payroll/summary").json()
    row = next(
        item for item in summary["items"] if item["employee_id"] == employee["id"]
    )
    assert row["salary_due"] == "3000000.00"
    assert row["commission_earned"] == "10000.00"
    assert row["salary_paid"] == "3000000.00"
    assert row["total_due"] == "10000.00"
    assert summary["total_due"] == "10000.00"


def test_gaji_karyawan_periode_sama_ditolak(client):
    employee = _employee(client, nama="Kasir Sekali")
    assert _salary(client, employee["id"]).status_code == 201
    response = _salary(client, employee["id"])
    assert response.status_code == 409, response.text
    assert "sudah dicatat" in response.json()["detail"]


def test_hutang_dipotong_dari_komisi(
    client, create_customer, create_unit, make_transaction
):
    employee = _employee(
        client,
        nama="Mekanik Hutang",
        peran="MEKANIK",
        jenis_imbalan="KOMISI",
        gaji_bulanan="0",
        nilai="10",
        komisi_jasa_nilai="10",
        payroll_period="MINGGUAN",
    )
    customer = create_customer(nama="Pelanggan Hutang")
    unit = create_unit(customer["id"], nopol="B 8603 HTG")
    response = make_transaction(
        unit["id"],
        jobs=[{"deskripsi": "Servis", "jumlah": 1, "harga": "100000"}],
        mechanic_ids=[employee["id"]],
    )
    assert response.status_code == 201, response.text
    debt = client.post(
        "/api/employee-debts",
        json={
            "employee_id": employee["id"],
            "tanggal": date.today().isoformat(),
            "nominal": "5000",
            "keterangan": "Kebutuhan keluarga",
        },
    )
    assert debt.status_code == 201, debt.text

    summary = client.get("/api/payroll/summary").json()
    row = next(
        item for item in summary["items"] if item["employee_id"] == employee["id"]
    )
    assert row["gross_due"] == "10000.00"
    assert row["debt_total"] == "5000.00"
    assert row["debt_used"] == "5000.00"
    assert row["total_due"] == "5000.00"

    response = _salary(
        client,
        employee["id"],
        nominal="5000",
        potongan_hutang="5000",
    )
    assert response.status_code == 201, response.text
    assert response.json()["potongan_hutang"] == "5000.00"

    debts = client.get("/api/employee-debts").json()
    assert debts[0]["sisa"] == "0.00"
    assert debts[0]["lunas"] is True
    summary = client.get("/api/payroll/summary").json()
    row = next(
        item for item in summary["items"] if item["employee_id"] == employee["id"]
    )
    assert row["total_due"] == "0.00"

    report = client.get("/api/reports/daily-cash").json()
    assert report["gaji_dibayar"] == "10000.00"


def test_cicil_hutang_tanpa_potong_gaji(
    client, create_customer, create_unit, make_transaction
):
    employee = _employee(
        client,
        nama="Mekanik Cicil",
        peran="MEKANIK",
        jenis_imbalan="KOMISI",
        gaji_bulanan="0",
        nilai="10",
        komisi_jasa_nilai="10",
        payroll_period="MINGGUAN",
    )
    customer = create_customer(nama="Pelanggan Cicil")
    unit = create_unit(customer["id"], nopol="B 8604 CCL")
    response = make_transaction(
        unit["id"],
        jobs=[{"deskripsi": "Servis", "jumlah": 1, "harga": "100000"}],
        mechanic_ids=[employee["id"]],
    )
    assert response.status_code == 201, response.text
    assert (
        client.post(
            "/api/employee-debts",
            json={
                "employee_id": employee["id"],
                "nominal": "5000",
                "keterangan": "Pinjaman",
            },
        ).status_code
        == 201
    )

    response = _salary(
        client,
        employee["id"],
        nominal="10000",
        potongan_hutang="0",
        cicilan_hutang="5000",
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["potongan_hutang"] == "0.00"
    assert body["cicilan_hutang"] == "5000.00"

    debts = client.get("/api/employee-debts").json()
    assert debts[0]["sisa"] == "0.00"
    summary = client.get("/api/payroll/summary").json()
    row = next(
        item for item in summary["items"] if item["employee_id"] == employee["id"]
    )
    assert row["total_due"] == "0.00"
    report = client.get("/api/reports/daily-cash").json()
    assert report["gaji_dibayar"] == "10000.00"


def test_gaji_mingguan_boleh_beda_siklus(client):
    employee = _employee(
        client,
        nama="Mekanik Mingguan",
        peran="MEKANIK",
        payroll_period="MINGGUAN",
    )
    today = date.today()
    assert _salary(client, employee["id"], tanggal=today).status_code == 201
    assert (
        _salary(client, employee["id"], tanggal=today - timedelta(days=7)).status_code
        == 201
    )
    rows = client.get("/api/salary-payments").json()
    assert len(rows) == 2
    assert len({row["cycle_start"] for row in rows}) == 2
    assert _salary(client, employee["id"], tanggal=today).status_code == 409


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
