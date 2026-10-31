"""Tahap 11: DP, pelunasan bertahap, piutang, dan struk DP/lunas."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from database.models import ServicePayment, ServiceRecord
from database.session import SessionLocal


def _receipt_text(receipt) -> str:
    return "\n".join(receipt["struk_58"])


def _dp_transaction(client, unit_id, dp="100000", metode="CASH", **overrides):
    payload = {
        "unit_id": unit_id,
        "keluhan_awal": "Servis radiator",
        "jenis_bayar": "DP",
        "dp": dp,
        "metode_bayar": metode,
        "jobs": [{"deskripsi": "Korok Radiator", "jumlah": 1, "harga": "150000"}],
        "parts": [],
    }
    payload.update(overrides)
    return client.post("/api/pos/transaction", json=payload)


def _pay(client, record_id, nominal, metode="CASH", **overrides):
    payload = {"nominal": nominal, "metode": metode}
    payload.update(overrides)
    return client.post(f"/api/service-records/{record_id}/payments", json=payload)


def test_nota_lunas_biasa_tetap_perilaku_lama(client, create_customer, create_unit, make_transaction):
    customer = create_customer()
    unit = create_unit(customer["id"])

    response = make_transaction(unit["id"])
    assert response.status_code == 201, response.text
    body = response.json()
    record = body["record"]
    receipt = body["receipt"]

    assert record["status_bayar"] == "LUNAS"
    assert record["total_dibayar"] == "150000.00"
    assert record["sisa_bayar"] == "0.00"
    assert record["jatuh_tempo"] is None
    assert receipt["status_bayar"] == "LUNAS"
    assert receipt["sisa_bayar"] == "0.00"
    assert "LUNAS" in _receipt_text(receipt)


def test_dp_menyimpan_nota_dan_struk_dp_langsung_dicetak(
    client, create_customer, create_unit
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    jatuh_tempo = date.today() + timedelta(days=7)

    response = _dp_transaction(
        client, unit["id"], dp="100000", jatuh_tempo=jatuh_tempo.isoformat()
    )
    assert response.status_code == 201, response.text
    body = response.json()
    record = body["record"]
    receipt = body["receipt"]

    assert record["total_servis"] == "150000.00"
    assert record["total_dibayar"] == "100000.00"
    assert record["sisa_bayar"] == "50000.00"
    assert record["status_bayar"] == "BELUM_LUNAS"
    assert record["jatuh_tempo"] == jatuh_tempo.isoformat()
    assert receipt["status_bayar"] == "BELUM_LUNAS"
    assert receipt["total_dibayar"] == "100000.00"
    assert receipt["sisa_bayar"] == "50000.00"

    text = _receipt_text(receipt)
    assert "BELUM LUNAS" in text
    assert "DP" in text
    assert "Sisa" in text
    assert "Jatuh Tempo" in text
    assert jatuh_tempo.strftime("%d/%m/%Y") in text

    with SessionLocal() as db:
        payments = db.query(ServicePayment).all()
        assert len(payments) == 1
        assert payments[0].jenis == "DP"
        assert payments[0].nominal == Decimal("100000.00")


def test_dp_uang_muka_tidak_valid_ditolak(client, create_customer, create_unit):
    customer = create_customer()
    unit = create_unit(customer["id"])

    for invalid in ("0", "150000", "200000"):
        response = _dp_transaction(client, unit["id"], dp=invalid)
        assert response.status_code == 400, (invalid, response.text)

    lewat = (date.today() - timedelta(days=1)).isoformat()
    response = _dp_transaction(client, unit["id"], jatuh_tempo=lewat)
    assert response.status_code == 400, response.text
    assert client.get("/api/service-records").json() == []


def test_pelunasan_bertahap_sampai_lunas_dan_struk_lunas(
    client, create_customer, create_unit
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    created = _dp_transaction(client, unit["id"], dp="50000").json()
    record_id = created["record"]["id"]

    first = _pay(client, record_id, "40000", metode="TRANSFER")
    assert first.status_code == 201, first.text
    first_body = first.json()
    assert first_body["record"]["sisa_bayar"] == "60000.00"
    assert first_body["record"]["status_bayar"] == "BELUM_LUNAS"
    assert first_body["payment"]["jenis"] == "PELUNASAN"
    assert first_body["payment"]["nominal"] == "40000.00"
    assert "PELUNASAN" in _receipt_text(first_body["receipt"])
    assert "Sisa" in _receipt_text(first_body["receipt"])

    second = _pay(client, record_id, "60000", metode="CASH")
    assert second.status_code == 201, second.text
    second_body = second.json()
    assert second_body["record"]["status_bayar"] == "LUNAS"
    assert second_body["record"]["sisa_bayar"] == "0.00"
    assert second_body["record"]["total_dibayar"] == "150000.00"
    text = _receipt_text(second_body["receipt"])
    assert "LUNAS" in text
    assert "0" in text

    payments = client.get(f"/api/service-records/{record_id}/payments").json()
    assert [row["jenis"] for row in payments] == ["DP", "PELUNASAN", "PELUNASAN"]

    # Nota lunas keluar dari daftar piutang.
    receivables = client.get("/api/receivables").json()
    assert receivables["jumlah_nota"] == 0
    assert receivables["items"] == []


def test_kelebihan_bayar_ditolak_tanpa_mengubah_sisa(
    client, create_customer, create_unit
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    record_id = _dp_transaction(client, unit["id"], dp="100000").json()["record"]["id"]

    rejected = _pay(client, record_id, "60000")
    assert rejected.status_code == 400, rejected.text
    assert "melebihi" in rejected.json()["detail"].lower()

    detail = client.get(f"/api/service-records/{record_id}").json()
    assert detail["sisa_bayar"] == "50000.00"
    assert detail["status_bayar"] == "BELUM_LUNAS"

    payments = client.get(f"/api/service-records/{record_id}/payments").json()
    assert len(payments) == 1


def test_pelunasan_idempoten_dengan_request_id(client, create_customer, create_unit):
    customer = create_customer()
    unit = create_unit(customer["id"])
    record_id = _dp_transaction(client, unit["id"], dp="100000").json()["record"]["id"]

    payload = {"nominal": "20000", "metode": "CASH", "request_id": "pay-request-0001"}
    first = client.post(f"/api/service-records/{record_id}/payments", json=payload)
    second = client.post(f"/api/service-records/{record_id}/payments", json=payload)
    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    assert first.json()["payment"]["id"] == second.json()["payment"]["id"]

    detail = client.get(f"/api/service-records/{record_id}").json()
    assert detail["total_dibayar"] == "120000.00"
    assert detail["sisa_bayar"] == "30000.00"


def test_piutang_dikelompokkan_per_pelanggan_dan_kartu_sama(
    client, create_customer, create_unit
):
    budi = create_customer(nama="Budi Piutang", nomor_hp="081200000111")
    unit_budi = create_unit(budi["id"], nopol="B 1101 PYT")
    _dp_transaction(client, unit_budi["id"], dp="50000")
    _dp_transaction(client, unit_budi["id"], dp="25000")

    sari = create_customer(nama="Sari Lunas", nomor_hp="081200000112")
    unit_sari = create_unit(sari["id"], nopol="B 1102 PYT")
    created = _dp_transaction(client, unit_sari["id"], dp="100000").json()
    partial = _pay(client, created["record"]["id"], "30000")
    assert partial.status_code == 201, partial.text

    receivables = client.get("/api/receivables").json()
    assert receivables["jumlah_pelanggan"] == 2
    assert receivables["jumlah_nota"] == 3
    assert receivables["total_sisa"] == "245000.00"
    budi_row = next(row for row in receivables["items"] if row["customer_id"] == budi["id"])
    assert len(budi_row["records"]) == 2
    assert budi_row["total_sisa"] == "225000.00"
    sari_row = next(row for row in receivables["items"] if row["customer_id"] == sari["id"])
    assert sari_row["total_sisa"] == "20000.00"

    report = client.get(
        "/api/reports/daily-cash", params={"tanggal": date.today().isoformat()}
    ).json()
    assert report["piutang_count"] == receivables["jumlah_nota"]
    assert report["piutang_customers"] == receivables["jumlah_pelanggan"]
    assert report["piutang_total"] == receivables["total_sisa"]


def test_laporan_memisahkan_nilai_nota_dan_uang_diterima(
    client, create_customer, create_unit
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    created = _dp_transaction(client, unit["id"], dp="100000", metode="CASH").json()
    record_id = created["record"]["id"]

    report_dp = client.get(
        "/api/reports/daily-cash", params={"tanggal": date.today().isoformat()}
    ).json()
    assert report_dp["total_omset"] == "150000.00"
    assert report_dp["penerimaan_total"] == "100000.00"
    assert report_dp["penerimaan_cash"] == "100000.00"
    assert report_dp["penerimaan_transfer"] == "0.00"

    assert _pay(client, record_id, "50000", metode="TRANSFER").status_code == 201

    report_full = client.get(
        "/api/reports/daily-cash", params={"tanggal": date.today().isoformat()}
    ).json()
    assert report_full["total_omset"] == "150000.00"
    assert report_full["penerimaan_total"] == "150000.00"
    assert report_full["penerimaan_cash"] == "100000.00"
    assert report_full["penerimaan_transfer"] == "50000.00"


def test_void_nota_dp_mengembalikan_dp_tanpa_saldo_negatif(
    client, create_customer, create_unit
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    record_id = _dp_transaction(client, unit["id"], dp="100000").json()["record"]["id"]

    voided = client.post(
        f"/api/service-records/{record_id}/void", json={"alasan": "Pelanggan batal servis"}
    )
    assert voided.status_code == 200, voided.text
    record = voided.json()
    assert record["status"] == "VOID"
    assert record["total_dibayar"] == "0.00"
    assert record["sisa_bayar"] == "0.00"
    assert record["status_bayar"] == "LUNAS"

    payments = client.get(f"/api/service-records/{record_id}/payments").json()
    assert [row["jenis"] for row in payments] == ["DP", "REFUND"]
    assert payments[1]["nominal"] == "-100000.00"
    assert client.get("/api/receivables").json()["jumlah_nota"] == 0


def test_retur_nota_dp_mengembalikan_kelebihan_bayar(
    client, create_customer, create_unit
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    body = _dp_transaction(
        client,
        unit["id"],
        dp="100000",
        jobs=[{"deskripsi": "Korok Radiator", "jumlah": 1, "harga": "150000"}],
    ).json()
    record_id = body["record"]["id"]
    job_id = body["receipt"]["jobs"][0]["id"]

    retur = client.post(
        f"/api/service-records/{record_id}/returns",
        json={
            "alasan": "Pekerjaan dibatalkan sebagian",
            "items": [{"service_job_id": job_id, "jumlah": 1}],
        },
    )
    assert retur.status_code == 201, retur.text

    detail = client.get(f"/api/service-records/{record_id}").json()
    assert detail["total_neto"] == "0.00"
    assert detail["total_dibayar"] == "0.00"
    assert detail["sisa_bayar"] == "0.00"
    assert detail["status_bayar"] == "LUNAS"
    payments = client.get(f"/api/service-records/{record_id}/payments").json()
    assert payments[-1]["jenis"] == "REFUND"
    assert payments[-1]["nominal"] == "-100000.00"
    assert client.get("/api/receivables").json()["jumlah_nota"] == 0


def test_migrasi_menandai_nota_lama_lunas(tmp_path):
    from dataclasses import replace

    from sqlalchemy.orm import Session

    from config import settings
    from database.base import Base
    from database.models import Customer, VehicleOrUnit
    from database.session import build_engine, init_db
    from services import backup_service

    backup_dir = tmp_path / "backups"
    original_settings = settings
    backup_service.settings = replace(original_settings, backup_dir=backup_dir)
    try:
        legacy = build_engine(f"sqlite:///{(tmp_path / 'legacy_pay.db').as_posix()}")
        Base.metadata.create_all(legacy)
        with Session(legacy) as db:
            customer = Customer(nama="Pelanggan Lama", nomor_hp="081200000099")
            db.add(customer)
            db.flush()
            unit = VehicleOrUnit(customer_id=customer.id, unit_type="MOBIL", nopol="B 9001 LMA")
            db.add(unit)
            db.flush()
            db.add(
                ServiceRecord(
                    unit_id=unit.id,
                    no_nota="INV-20250101-0001",
                    waktu_service=__import__("datetime").datetime(2025, 1, 1, 9, 0),
                    keluhan_awal="Nota lama",
                    total_servis=Decimal("100000.00"),
                    bayar=Decimal("100000.00"),
                )
            )
            db.commit()

        with legacy.begin() as conn:
            conn.exec_driver_sql("PRAGMA user_version = 7")

        init_db(legacy)

        with legacy.connect() as conn:
            row = conn.exec_driver_sql(
                "SELECT status_bayar, total_dibayar, jatuh_tempo FROM service_records"
            ).one()
            assert tuple(row) == ("LUNAS", 100000, None)
            payment = conn.exec_driver_sql(
                "SELECT jenis, nominal FROM service_payments"
            ).one()
            assert tuple(payment) == ("PELUNASAN", 100000)
    finally:
        backup_service.settings = original_settings
