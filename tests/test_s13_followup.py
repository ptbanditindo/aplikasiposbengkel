"""Tahap 13: follow-up, servis berkala, garansi, dan piutang."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from database.models import ServiceJob, ServiceRecord
from services.followup_service import add_months


def _shift_record(db_session, record_id, days_ago=0, garansi_sampai=None):
    record = db_session.get(ServiceRecord, record_id)
    record.waktu_service = datetime.combine(
        date.today() - timedelta(days=days_ago), time(9, 0)
    )
    if garansi_sampai is not None:
        record.garansi_sampai = garansi_sampai
    db_session.commit()
    return record


def _record_id(response):
    assert response.status_code == 201, response.text
    return response.json()["record"]["id"]


def _create_jasa(client, nama="Ganti Oli", interval=0, harga="75000"):
    response = client.post(
        "/api/harga-jasa",
        json={
            "nama": nama,
            "harga_standar": harga,
            "interval_servis_bulan": interval,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _items(client, **params):
    response = client.get("/api/followup/items", params=params)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def test_add_months_mengikuti_kalender():
    assert add_months(date(2025, 1, 31), 1) == date(2025, 2, 28)
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert add_months(date(2025, 8, 31), 6) == date(2026, 2, 28)
    assert add_months(date(2025, 3, 15), 12) == date(2026, 3, 15)
    assert add_months(date(2025, 3, 15), 0) == date(2025, 3, 15)


def test_master_jasa_interval_dan_snapshot_nota(
    client, create_customer, create_unit, make_transaction, db_session
):
    jasa = _create_jasa(client, interval=6)
    assert jasa["interval_servis_bulan"] == 6

    response = client.put(
        f"/api/harga-jasa/{jasa['id']}",
        json={"interval_servis_bulan": 3},
    )
    assert response.status_code == 200, response.text
    assert response.json()["interval_servis_bulan"] == 3

    customer = create_customer(nama="Pelanggan Oli")
    unit = create_unit(customer["id"], nopol="B 7001 OLI")
    record_id = _record_id(
        make_transaction(
            unit["id"],
            jobs=[
                {
                    "harga_jasa_id": jasa["id"],
                    "deskripsi": "Ganti Oli",
                    "jumlah": 1,
                    "harga": "75000",
                }
            ],
        )
    )
    job = db_session.query(ServiceJob).filter_by(service_record_id=record_id).one()
    assert job.interval_servis_bulan == 3

    # Mengubah master tidak boleh mengubah snapshot nota lama.
    client.put(f"/api/harga-jasa/{jasa['id']}", json={"interval_servis_bulan": 12})
    db_session.expire_all()
    job = db_session.query(ServiceJob).filter_by(service_record_id=record_id).one()
    assert job.interval_servis_bulan == 3

    # Nilai untuk satu nota boleh ditimpa saat transaksi.
    response = make_transaction(
        unit["id"],
        jobs=[
            {
                "harga_jasa_id": jasa["id"],
                "deskripsi": "Ganti Oli",
                "jumlah": 1,
                "harga": "75000",
                "interval_servis_bulan": 1,
            }
        ],
    )
    second_id = _record_id(response)
    job = db_session.query(ServiceJob).filter_by(service_record_id=second_id).one()
    assert job.interval_servis_bulan == 1


def test_servis_berkala_muncul_dari_jasa_nota_dan_batas_h14(
    client, create_customer, create_unit, make_transaction, db_session
):
    jasa = _create_jasa(client, nama="Cuci Radiator", interval=3, harga="100000")
    customer = create_customer(nama="Pelanggan Servis")
    unit = create_unit(customer["id"], nopol="B 7002 RAD")
    record_id = _record_id(
        make_transaction(
            unit["id"],
            jobs=[
                {
                    "harga_jasa_id": jasa["id"],
                    "deskripsi": "Cuci Radiator",
                    "jumlah": 1,
                    "harga": "100000",
                }
            ],
        )
    )

    today = date.today()
    service_day = add_months(today, -3)
    _shift_record(
        db_session, record_id, days_ago=(today - service_day).days
    )

    items = _items(client, jenis="servis_berkala")
    assert len(items) == 1
    item = items[0]
    assert item["jenis"] == "servis_berkala"
    assert item["customer_id"] == customer["id"]
    assert item["jatuh_tempo"] == add_months(service_day, 3).isoformat()
    assert item["rincian"][0]["pekerjaan"] == "Cuci Radiator"
    assert item["rincian"][0]["interval_bulan"] == 3

    # Jasa tanpa interval tidak pernah masuk daftar servis berkala.
    other = create_customer(nama="Pelanggan Tanpa Interval")
    other_unit = create_unit(other["id"], nopol="B 7003 PLAIN")
    plain = _create_jasa(client, nama="Servis Umum", interval=0, harga="50000")
    plain_record = _record_id(
        make_transaction(
            other_unit["id"],
            jobs=[
                {
                    "harga_jasa_id": plain["id"],
                    "deskripsi": "Servis Umum",
                    "jumlah": 1,
                    "harga": "50000",
                }
            ],
        )
    )
    _shift_record(db_session, plain_record, days_ago=400)
    items = _items(client, jenis="servis_berkala")
    assert all(row["customer_id"] != other["id"] for row in items)

    # Di luar jendela H-14 item belum tampil; tepat H-14 tampil.
    fixed_today = date(2026, 6, 15)
    near = create_customer(nama="Pelanggan H14")
    near_unit = create_unit(near["id"], nopol="B 7004 H14")
    near_jasa = _create_jasa(client, nama="Servis H14", interval=3, harga="10000")
    near_record = _record_id(
        make_transaction(
            near_unit["id"],
            jobs=[
                {
                    "harga_jasa_id": near_jasa["id"],
                    "deskripsi": "Servis H14",
                    "jumlah": 1,
                    "harga": "10000",
                }
            ],
        )
    )
    record = db_session.get(ServiceRecord, near_record)
    record.waktu_service = datetime.combine(date(2026, 3, 29), time(9, 0))
    db_session.commit()
    assert add_months(date(2026, 3, 29), 3) == date(2026, 6, 29)

    far = create_customer(nama="Pelanggan H15")
    far_unit = create_unit(far["id"], nopol="B 7015 H15")
    far_record = _record_id(
        make_transaction(
            far_unit["id"],
            jobs=[
                {
                    "harga_jasa_id": near_jasa["id"],
                    "deskripsi": "Servis H14",
                    "jumlah": 1,
                    "harga": "10000",
                }
            ],
        )
    )
    far_row = db_session.get(ServiceRecord, far_record)
    far_row.waktu_service = datetime.combine(date(2026, 3, 30), time(9, 0))
    db_session.commit()
    assert add_months(date(2026, 3, 30), 3) == date(2026, 6, 30)

    overdue = create_customer(nama="Pelanggan Lewat")
    overdue_unit = create_unit(overdue["id"], nopol="B 7016 LWT")
    overdue_record = _record_id(
        make_transaction(
            overdue_unit["id"],
            jobs=[
                {
                    "harga_jasa_id": near_jasa["id"],
                    "deskripsi": "Servis H14",
                    "jumlah": 1,
                    "harga": "10000",
                }
            ],
        )
    )
    overdue_row = db_session.get(ServiceRecord, overdue_record)
    overdue_row.waktu_service = datetime.combine(date(2026, 1, 10), time(9, 0))
    db_session.commit()

    from services import followup_service

    listed = followup_service.list_items(
        db_session, jenis="servis_berkala", today=fixed_today
    )
    customer_ids = {row["customer_id"] for row in listed["items"]}
    assert near["id"] in customer_ids
    assert overdue["id"] in customer_ids
    assert far["id"] not in customer_ids


def test_prospek_batas_hari_cooldown_dan_arsip(
    client, create_customer, create_unit, make_transaction, db_session
):
    customer = create_customer(nama="Pelanggan Prospek")
    unit = create_unit(customer["id"], nopol="B 7005 PRO")
    record_id = _record_id(make_transaction(unit["id"]))

    _shift_record(db_session, record_id, days_ago=6)
    assert _items(client, jenis="prospek") == []

    _shift_record(db_session, record_id, days_ago=7)
    items = _items(client, jenis="prospek")
    assert len(items) == 1
    item = items[0]
    assert item["status"] == "BARU"
    assert item["sisa_hari"] == 0
    assert item["bisa_followup"] is True

    response = client.post(
        f"/api/followup/items/{item['id']}/followup",
        json={"status": "DIBUKA"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["item"]["status"] == "SUDAH_FOLLOWUP"
    assert body["item"]["sudah_followup"] is True
    assert body["link"].startswith("https://wa.me/62")
    assert "Pelanggan Prospek" in body["wa_text"]
    assert body["log"]["status"] == "DIBUKA"

    logs = client.get(
        f"/api/service-records/{record_id}/whatsapp-logs"
    ).json()
    assert any(row["status"] == "DIBUKA" for row in logs)

    repeat = client.post(
        f"/api/followup/items/{item['id']}/followup",
        json={"status": "DIBUKA"},
    )
    assert repeat.status_code == 409

    moved = client.post(
        f"/api/followup/items/{item['id']}/status",
        json={"status": "MASIH_KENDALA", "alasan": "Menunggu pelanggan"},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["status"] == "MASIH_KENDALA"

    detail = client.get(f"/api/followup/items/{item['id']}").json()
    assert len(detail["events"]) >= 3

    archived = client.post(
        f"/api/followup/items/{item['id']}/status",
        json={"status": "ARSIP", "alasan": "Sudah servis di tempat lain"},
    )
    assert archived.status_code == 200, archived.text
    assert _items(client, jenis="prospek") == []

    # Sinkron ulang tidak boleh memunculkan kembali siklus yang diarsipkan.
    assert _items(client, jenis="prospek") == []


def test_garansi_akan_habis_followup_dan_hilangkan_pengingat(
    client, create_customer, create_unit, make_transaction, db_session
):
    customer = create_customer(nama="Pelanggan Garansi")
    unit = create_unit(customer["id"], nopol="B 7006 GAR")
    record_id = _record_id(make_transaction(unit["id"]))
    _shift_record(
        db_session, record_id, days_ago=20, garansi_sampai=date.today() + timedelta(days=5)
    )

    items = _items(client, jenis="garansi")
    assert len(items) == 1
    item = items[0]
    assert item["sisa_hari"] == 5
    assert "Garansi" in item["judul"]

    body = client.post(
        f"/api/followup/items/{item['id']}/followup",
        json={"status": "DIBUKA"},
    ).json()
    assert "Garansi servis" in body["wa_text"]
    assert "5 hari lagi" in body["wa_text"]

    archived = client.post(
        f"/api/followup/items/{item['id']}/status",
        json={"status": "ARSIP", "alasan": "Pelanggan menolak diingatkan"},
    )
    assert archived.status_code == 200, archived.text
    assert _items(client, jenis="garansi") == []
    assert _items(client, jenis="garansi") == []


def test_piutang_followup_tidak_mengubah_sisa_dan_hanya_lunas_menghapus(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer(nama="Pelanggan Sisa")
    unit = create_unit(customer["id"], nopol="B 7007 PIU")
    record_id = _record_id(
        make_transaction(
            unit["id"],
            jobs=[{"deskripsi": "Servis Radiator", "jumlah": 1, "harga": "150000"}],
            jenis_bayar="DP",
            dp="50000",
            bayar="50000",
        )
    )

    items = _items(client, jenis="piutang")
    assert len(items) == 1
    item = items[0]
    assert item["rincian"][0]["sisa_bayar"] == "100000.00"

    body = client.post(
        f"/api/followup/items/{item['id']}/followup",
        json={"status": "DIBUKA"},
    ).json()
    wa_text = body["wa_text"]
    assert "sudah selesai dikerjakan" in wa_text
    assert "siap diambil" in wa_text
    assert "Sisa pembayaran" in wa_text
    for kata in ("hutang", "piutang", "tagihan", "kekurangan"):
        assert kata not in wa_text.lower(), (kata, wa_text)
    assert body["item"]["status"] == "SUDAH_FOLLOWUP"

    receivables = client.get("/api/receivables").json()
    assert receivables["jumlah_nota"] == 1
    assert receivables["total_sisa"] == "100000.00"

    record = client.get(f"/api/service-records/{record_id}").json()
    assert record["status_bayar"] == "BELUM_LUNAS"

    blocked = client.post(
        f"/api/followup/items/{item['id']}/status",
        json={"status": "SELESAI"},
    )
    assert blocked.status_code == 400

    no_date = client.post(
        f"/api/followup/items/{item['id']}/status",
        json={"status": "JANJI_BAYAR"},
    )
    assert no_date.status_code == 400

    promise = client.post(
        f"/api/followup/items/{item['id']}/status",
        json={
            "status": "JANJI_BAYAR",
            "janji_bayar": (date.today() + timedelta(days=3)).isoformat(),
        },
    )
    assert promise.status_code == 200, promise.text
    assert promise.json()["janji_bayar"] == (
        date.today() + timedelta(days=3)
    ).isoformat()

    payment = client.post(
        f"/api/service-records/{record_id}/payments",
        json={"nominal": "100000", "metode": "CASH"},
    )
    assert payment.status_code in (200, 201), payment.text
    assert _items(client, jenis="piutang") == []


def test_filter_customer_dan_filter_arsip(
    client, create_customer, create_unit, make_transaction, db_session
):
    first = create_customer(nama="Piutang Satu", nomor_hp="081200000001")
    second = create_customer(nama="Garansi Dua", nomor_hp="081200000002")
    first_unit = create_unit(first["id"], nopol="B 7101 AAA")
    second_unit = create_unit(second["id"], nopol="B 7102 BBB")
    _record_id(
        make_transaction(
            first_unit["id"], jenis_bayar="DP", dp="20000", bayar="20000"
        )
    )
    garansi_record = _record_id(make_transaction(second_unit["id"]))
    _shift_record(
        db_session,
        garansi_record,
        garansi_sampai=date.today() + timedelta(days=5),
    )

    only_first = _items(client, customer_id=first["id"])
    assert [row["customer_id"] for row in only_first] == [first["id"]]

    default_items = _items(client)
    assert {(row["jenis"], row["customer_id"]) for row in default_items} == {
        ("piutang", first["id"]),
        ("garansi", second["id"]),
    }

    garansi_item = next(
        row for row in default_items if row["jenis"] == "garansi"
    )
    archived = client.post(
        f"/api/followup/items/{garansi_item['id']}/status",
        json={"status": "ARSIP", "alasan": "Pelanggan pindah kota"},
    )
    assert archived.status_code == 200, archived.text

    archived_items = _items(client, filter="arsip")
    assert [(row["jenis"], row["customer_id"]) for row in archived_items] == [
        ("garansi", second["id"])
    ]

    remaining = _items(client)
    assert [(row["jenis"], row["customer_id"]) for row in remaining] == [
        ("piutang", first["id"])
    ]


def test_satu_pelanggan_beberapa_unit_tetap_satu_item(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer(nama="Pelanggan Multi Unit")
    first = create_unit(customer["id"], nopol="B 7008 A")
    second = create_unit(customer["id"], nopol="B 7008 B")
    third = create_unit(customer["id"], nopol="B 7008 C")
    for unit in (first, second, third):
        _record_id(
            make_transaction(
                unit["id"],
                jobs=[{"deskripsi": "Servis", "jumlah": 1, "harga": "80000"}],
                jenis_bayar="DP",
                dp="30000",
                bayar="30000",
            )
        )

    items = _items(client, jenis="piutang")
    assert len(items) == 1
    item = items[0]
    assert item["customer_id"] == customer["id"]
    assert len(item["rincian"]) == 3


def test_ambil_tugas_dan_lepas_tercatat(client, create_customer, create_unit, make_transaction, db_session):
    customer = create_customer(nama="Pelanggan Tugas")
    unit = create_unit(customer["id"], nopol="B 7009 TGS")
    record_id = _record_id(make_transaction(unit["id"]))
    _shift_record(db_session, record_id, days_ago=10)

    item = _items(client, jenis="prospek")[0]
    assigned = client.post(f"/api/followup/items/{item['id']}/assign", json={})
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["penanggung_jawab"]
    assert assigned.json()["diambil_pada"]

    again = client.post(f"/api/followup/items/{item['id']}/assign", json={})
    assert again.status_code == 400

    released = client.post(
        f"/api/followup/items/{item['id']}/assign",
        json={"release": True, "alasan": "Shift selesai"},
    )
    assert released.status_code == 200, released.text
    assert released.json()["penanggung_jawab"] is None

    detail = client.get(f"/api/followup/items/{item['id']}").json()
    assert any("Shift selesai" in (row["alasan"] or "") for row in detail["events"])

    tasks = client.get("/api/followup/items", params={"filter": "terlambat"}).json()
    assert tasks["jumlah"] >= 1


def test_dashboard_menampilkan_kartu_followup(
    client, create_customer, create_unit, make_transaction, db_session
):
    customer = create_customer(nama="Pelanggan Dasbor")
    unit = create_unit(customer["id"], nopol="B 7010 DSH")
    record_id = _record_id(
        make_transaction(
            unit["id"],
            jobs=[{"deskripsi": "Servis", "jumlah": 1, "harga": "100000"}],
            jenis_bayar="DP",
            dp="40000",
            bayar="40000",
        )
    )
    _shift_record(db_session, record_id, days_ago=9)

    report_response = client.get("/api/reports/daily-cash")
    assert report_response.status_code == 200, report_response.text
    report = report_response.json()
    assert report["piutang_count"] == 1
    assert report["piutang_total"] == "60000.00"
    assert report["prospek_count"] == 1
    assert report["followup_hari_ini"] >= 1

    counts = client.get("/api/followup/counts").json()
    assert counts["prospek_count"] == 1
    assert counts["followup_hari_ini"] >= 1


def test_pelanggan_tanpa_izin_wa_tetap_di_daftar_tapi_tidak_bisa_followup(
    client, create_customer, create_unit, make_transaction, db_session
):
    customer = create_customer(nama="Pelanggan Tanpa Izin")
    denied = client.put(
        f"/api/customers/{customer['id']}/consent",
        json={"wa_consent": False},
    )
    assert denied.status_code == 200, denied.text
    assert denied.json()["wa_consent"] is False

    unit = create_unit(customer["id"], nopol="B 7011 NOA")
    record_id = _record_id(make_transaction(unit["id"]))
    _shift_record(
        db_session, record_id, days_ago=20, garansi_sampai=date.today() + timedelta(days=4)
    )

    items = _items(client, jenis="garansi")
    assert len(items) == 1
    assert items[0]["bisa_followup"] is False

    response = client.post(
        f"/api/followup/items/{items[0]['id']}/followup",
        json={"status": "DIBUKA"},
    )
    assert response.status_code == 409
