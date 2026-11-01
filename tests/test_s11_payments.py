"""Tahap 11: kredit, pelunasan bertahap, piutang, dan struk kredit/lunas."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from database.models import ServicePayment, ServiceRecord
from database.session import SessionLocal


def _receipt_text(receipt) -> str:
    return "\n".join(receipt["struk_58"])


def _kredit_transaction(client, unit_id, uang_muka="100000", metode="CASH", **overrides):
    payload = {
        "unit_id": unit_id,
        "keluhan_awal": "Servis radiator",
        "jenis_bayar": "KREDIT",
        "dp": uang_muka,
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


def test_kredit_menyimpan_nota_dan_struk_kredit_langsung_dicetak(
    client, create_customer, create_unit
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    jatuh_tempo = date.today() + timedelta(days=7)

    response = _kredit_transaction(
        client, unit["id"], uang_muka="100000", jatuh_tempo=jatuh_tempo.isoformat()
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
    assert "Uang Muka / Dibayar" in text
    assert "Sisa" in text
    assert "Jatuh Tempo" in text
    assert jatuh_tempo.strftime("%d/%m/%Y") in text

    with SessionLocal() as db:
        payments = db.query(ServicePayment).all()
        assert len(payments) == 1
        assert payments[0].jenis == "UANG_MUKA"
        assert payments[0].nominal == Decimal("100000.00")


def test_uang_muka_kredit_tidak_valid_ditolak(client, create_customer, create_unit):
    customer = create_customer()
    unit = create_unit(customer["id"])

    for invalid in ("150000", "200000"):
        response = _kredit_transaction(client, unit["id"], uang_muka=invalid)
        assert response.status_code == 400, (invalid, response.text)

    lewat = (date.today() - timedelta(days=1)).isoformat()
    response = _kredit_transaction(client, unit["id"], jatuh_tempo=lewat)
    assert response.status_code == 400, response.text
    assert client.get("/api/service-records").json() == []


def test_jenis_bayar_dp_tidak_diterima_lagi(client, create_customer, create_unit):
    customer = create_customer()
    unit = create_unit(customer["id"])
    payload = {
        "unit_id": unit["id"],
        "keluhan_awal": "Servis radiator",
        "jenis_bayar": "DP",
        "dp": "50000",
        "metode_bayar": "CASH",
        "jobs": [{"deskripsi": "Korok Radiator", "jumlah": 1, "harga": "150000"}],
        "parts": [],
    }

    preview = client.post("/api/pos/preview", json=payload)
    assert preview.status_code == 422, preview.text

    created = client.post("/api/pos/transaction", json=payload)
    assert created.status_code == 422, created.text
    assert client.get("/api/service-records").json() == []


def test_pelunasan_bertahap_sampai_lunas_dan_struk_lunas(
    client, create_customer, create_unit
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    created = _kredit_transaction(client, unit["id"], uang_muka="50000").json()
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
    assert [row["jenis"] for row in payments] == ["UANG_MUKA", "PELUNASAN", "PELUNASAN"]

    # Nota lunas keluar dari daftar piutang.
    receivables = client.get("/api/receivables").json()
    assert receivables["jumlah_nota"] == 0
    assert receivables["items"] == []


def test_kelebihan_bayar_ditolak_tanpa_mengubah_sisa(
    client, create_customer, create_unit
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    record_id = _kredit_transaction(client, unit["id"], uang_muka="100000").json()["record"]["id"]

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
    record_id = _kredit_transaction(client, unit["id"], uang_muka="100000").json()["record"]["id"]

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
    _kredit_transaction(client, unit_budi["id"], uang_muka="50000")
    _kredit_transaction(client, unit_budi["id"], uang_muka="25000")

    sari = create_customer(nama="Sari Lunas", nomor_hp="081200000112")
    unit_sari = create_unit(sari["id"], nopol="B 1102 PYT")
    created = _kredit_transaction(client, unit_sari["id"], uang_muka="100000").json()
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


def test_ingatkan_hanya_nota_jatuh_tempo_dan_mengunci_nota_itu(
    client, create_customer, create_unit
):
    customer = create_customer(nama="Multi Piutang", nomor_hp="081200000222")
    unit = create_unit(customer["id"], nopol="B 1301 MLT")
    first = _kredit_transaction(
        client,
        unit["id"],
        uang_muka="50000",
        jatuh_tempo=date.today().isoformat(),
        request_id="multi-piutang-0001",
    )
    second = _kredit_transaction(
        client,
        unit["id"],
        uang_muka="25000",
        jatuh_tempo=(date.today() + timedelta(days=5)).isoformat(),
        request_id="multi-piutang-0002",
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    first_record = first.json()["record"]
    second_record = second.json()["record"]

    sent = client.post(f"/api/customers/{customer['id']}/remind")
    assert sent.status_code == 201, sent.text
    body = sent.json()
    assert first_record["no_nota"] in body["wa_text"]
    assert second_record["no_nota"] not in body["wa_text"]
    assert "Total sisa" in body["wa_text"]
    assert body["link"].startswith("https://wa.me/6281200000222?text=")

    receivables = client.get("/api/receivables").json()
    assert receivables["jumlah_nota"] == 2
    rows = {
        record["id"]: record for record in receivables["items"][0]["records"]
    }
    assert rows[first_record["id"]]["sudah_diingatkan"] is True
    assert rows[first_record["id"]]["pengingat_ke"] == 1
    assert rows[first_record["id"]]["bisa_diingatkan"] is False
    assert rows[second_record["id"]]["sudah_diingatkan"] is False
    assert rows[second_record["id"]]["pengingat_ke"] == 0

    again = client.post(f"/api/customers/{customer['id']}/remind")
    assert again.status_code == 409
    blocked_first = client.post(
        f"/api/service-records/{first_record['id']}/remind"
    )
    blocked_second = client.post(
        f"/api/service-records/{second_record['id']}/remind"
    )
    assert blocked_first.status_code == 409
    assert blocked_second.status_code == 409

    with SessionLocal() as db:
        rows = (
            db.query(ServiceRecord)
            .filter(
                ServiceRecord.id.in_(
                    [first_record["id"], second_record["id"]]
                )
            )
            .all()
        )
        by_id = {row.id: row for row in rows}
        assert by_id[first_record["id"]].diingatkan_pada is not None
        assert by_id[second_record["id"]].diingatkan_pada is None


def test_laporan_memisahkan_nilai_nota_dan_uang_diterima(
    client, create_customer, create_unit
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    created = _kredit_transaction(client, unit["id"], uang_muka="100000", metode="CASH").json()
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


def test_void_nota_kredit_mengembalikan_uang_muka_tanpa_saldo_negatif(
    client, create_customer, create_unit
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    record_id = _kredit_transaction(client, unit["id"], uang_muka="100000").json()["record"]["id"]

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
    assert [row["jenis"] for row in payments] == ["UANG_MUKA", "REFUND"]
    assert payments[1]["nominal"] == "-100000.00"
    assert client.get("/api/receivables").json()["jumlah_nota"] == 0


def test_retur_nota_kredit_mengembalikan_kelebihan_bayar(
    client, create_customer, create_unit
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    body = _kredit_transaction(
        client,
        unit["id"],
        uang_muka="100000",
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
