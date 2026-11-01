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


def _window_outside_now():
    now = datetime.now()
    return f"{(now.hour + 2) % 24:02d}:00", f"{(now.hour + 3) % 24:02d}:00"


def _set_followup_window(client, start, end):
    response = client.put(
        "/api/settings/ops",
        json={"followup_jam_mulai": start, "followup_jam_selesai": end},
    )
    assert response.status_code == 200, response.text


def test_followup_ditolak_di_luar_jam(
    client, create_customer, create_unit, make_transaction, db_session
):
    customer = create_customer(nama="Pelanggan Luar Jam")
    unit = create_unit(customer["id"], nopol="B 7019 JAM")
    record_id = _record_id(make_transaction(unit["id"]))
    _shift_record(db_session, record_id, days_ago=7)
    item = _items(client, jenis="prospek")[0]

    start, end = _window_outside_now()
    _set_followup_window(client, start, end)
    blocked = client.post(
        f"/api/followup/items/{item['id']}/followup",
        json={"status": "DIBUKA"},
    )
    assert blocked.status_code == 409
    assert "pukul" in blocked.json()["detail"].lower()

    _set_followup_window(client, "00:00", "23:59")
    allowed = client.post(
        f"/api/followup/items/{item['id']}/followup",
        json={"status": "DIBUKA"},
    )
    assert allowed.status_code == 200, allowed.text


def test_pengingat_piutang_ditolak_di_luar_jam(
    client, create_customer, create_unit, make_transaction, db_session
):
    customer = create_customer(nama="Pelanggan Piutang Jam")
    unit = create_unit(customer["id"], nopol="B 7020 PJM")
    record_id = _record_id(
        make_transaction(
            unit["id"],
            jobs=[{"deskripsi": "Servis Radiator", "jumlah": 1, "harga": "150000"}],
            jenis_bayar="KREDIT",
            dp="50000",
            bayar="50000",
        )
    )
    record = db_session.get(ServiceRecord, record_id)
    record.jatuh_tempo = date.today() - timedelta(days=1)
    db_session.commit()

    start, end = _window_outside_now()
    _set_followup_window(client, start, end)
    blocked = client.post(f"/api/customers/{customer['id']}/remind")
    assert blocked.status_code == 409
    assert "pukul" in blocked.json()["detail"].lower()

    _set_followup_window(client, "00:00", "23:59")
    allowed = client.post(f"/api/customers/{customer['id']}/remind")
    assert allowed.status_code == 201, allowed.text


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


def test_rincian_servis_hanya_dari_nota_followup(
    client, create_customer, create_unit, make_transaction, db_session
):
    jasa_lama = _create_jasa(client, nama="Cuci Radiator", interval=3, harga="100000")
    jasa_baru = _create_jasa(client, nama="Ganti Oli", interval=6, harga="75000")
    customer = create_customer(nama="Pelanggan Satu Nota")
    unit = create_unit(customer["id"], nopol="B 7017 NOT")

    record_lama = _record_id(
        make_transaction(
            unit["id"],
            jobs=[
                {
                    "harga_jasa_id": jasa_lama["id"],
                    "deskripsi": "Cuci Radiator",
                    "jumlah": 1,
                    "harga": "100000",
                }
            ],
        )
    )
    record_baru = _record_id(
        make_transaction(
            unit["id"],
            jobs=[
                {
                    "harga_jasa_id": jasa_baru["id"],
                    "deskripsi": "Ganti Oli",
                    "jumlah": 1,
                    "harga": "75000",
                }
            ],
        )
    )
    _shift_record(db_session, record_lama, days_ago=120)
    _shift_record(db_session, record_baru, days_ago=30)
    note_lama = db_session.get(ServiceRecord, record_lama).no_nota
    note_baru = db_session.get(ServiceRecord, record_baru).no_nota

    item = next(
        row
        for row in _items(client, jenis="servis_berkala")
        if row["customer_id"] == customer["id"]
    )
    assert item["no_nota"] == note_lama
    assert item["rincian"]
    assert {row["no_nota"] for row in item["rincian"]} == {note_lama}
    assert all(row["no_nota"] != note_baru for row in item["rincian"])
    assert all(row["pekerjaan"] != "Ganti Oli" for row in item["rincian"])


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
    assert item["status_label"] == "Masih bagus"
    assert item["sisa_hari"] == 0
    assert item["bisa_followup"] is True

    blocked = client.post(
        f"/api/followup/items/{item['id']}/status",
        json={"status": "MASIH_KENDALA"},
    )
    assert blocked.status_code == 409
    assert "follow up" in blocked.json()["detail"].lower()

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


def test_pesan_followup_mengikuti_nama_bengkel_dari_pengaturan(
    client, create_customer, create_unit, make_transaction, db_session
):
    updated = client.put(
        "/api/settings/bengkel",
        json={"nama": "BENGKEL UJI FORMAL"},
    )
    assert updated.status_code == 200, updated.text

    customer = create_customer(nama="Pelanggan Nama Bengkel")
    unit = create_unit(customer["id"], nopol="B 7021 NMB")
    record_id = _record_id(make_transaction(unit["id"]))
    _shift_record(db_session, record_id, days_ago=7)
    item = _items(client, jenis="prospek")[0]

    body = client.post(
        f"/api/followup/items/{item['id']}/followup",
        json={"status": "DIBUKA"},
    ).json()
    text = body["wa_text"]
    assert text.startswith("Mohon maaf")
    assert "Perkenalkan, kami dari BENGKEL UJI FORMAL." in text
    assert "BENGKEL RADIATOR TEST" not in text
    assert "Terima kasih atas perhatian" in text


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
    assert body["wa_text"].startswith("Mohon maaf")
    assert "Perkenalkan, kami dari" in body["wa_text"]
    assert "garansi servis" in body["wa_text"]
    assert "5 hari lagi" in body["wa_text"]
    assert "Terima kasih atas perhatian" in body["wa_text"]

    archived = client.post(
        f"/api/followup/items/{item['id']}/status",
        json={"status": "ARSIP", "alasan": "Pelanggan menolak diingatkan"},
    )
    assert archived.status_code == 200, archived.text
    assert _items(client, jenis="garansi") == []
    assert _items(client, jenis="garansi") == []


def test_pesan_followup_yang_diedit_tersimpan_dan_tampil_di_detail(
    client, create_customer, create_unit, make_transaction, db_session
):
    customer = create_customer(nama="Pelanggan Pesan")
    unit = create_unit(customer["id"], nopol="B 7014 PSN")
    record_id = _record_id(make_transaction(unit["id"]))
    _shift_record(
        db_session,
        record_id,
        days_ago=20,
        garansi_sampai=date.today() + timedelta(days=5),
    )

    item = _items(client, jenis="garansi")[0]
    edited = "Halo Pak, garansi radiator segera berakhir. Silakan mampir minggu ini."
    response = client.post(
        f"/api/followup/items/{item['id']}/followup",
        json={"status": "DIBUKA", "pesan": edited},
    )
    assert response.status_code == 200, response.text
    assert response.json()["wa_text"] == edited

    detail = client.get(f"/api/followup/items/{item['id']}").json()
    assert detail["pesan"] == edited


def test_piutang_followup_tidak_mengubah_sisa_dan_hanya_lunas_menghapus(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer(nama="Pelanggan Sisa")
    unit = create_unit(customer["id"], nopol="B 7007 PIU")
    record_id = _record_id(
        make_transaction(
            unit["id"],
            jobs=[{"deskripsi": "Servis Radiator", "jumlah": 1, "harga": "150000"}],
            jenis_bayar="KREDIT",
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
    assert "Mohon maaf" in wa_text
    assert "Perkenalkan, kami dari" in wa_text
    assert item["no_nota"] in wa_text
    assert "sisa sebesar" in wa_text.lower()
    assert "pembayaran" in wa_text.lower()
    assert "siap diambil" not in wa_text.lower()
    assert "Terima kasih atas perhatian" in wa_text
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
            first_unit["id"], jenis_bayar="KREDIT", dp="20000", bayar="20000"
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
                jenis_bayar="KREDIT",
                dp="30000",
                bayar="30000",
            )
        )

    items = _items(client, jenis="piutang")
    assert len(items) == 1
    item = items[0]
    assert item["customer_id"] == customer["id"]
    assert len(item["rincian"]) == 3


def test_jadwal_wajib_followup_dulu_dan_tidak_datang(
    client, create_customer, create_unit, make_transaction, db_session
):
    customer = create_customer(nama="Pelanggan Jadwal")
    unit = create_unit(customer["id"], nopol="B 7011 JDW")
    record_id = _record_id(make_transaction(unit["id"]))
    _shift_record(
        db_session,
        record_id,
        days_ago=20,
        garansi_sampai=date.today() + timedelta(days=5),
    )

    item = _items(client, jenis="garansi")[0]
    blocked = client.post(
        f"/api/followup/items/{item['id']}/status",
        json={"status": "AKAN_DATANG", "tanggal_service": date.today().isoformat()},
    )
    assert blocked.status_code == 409
    assert "follow up" in blocked.json()["detail"].lower()

    blocked_removed = client.post(
        f"/api/followup/items/{item['id']}/status",
        json={"status": "TIDAK_DATANG"},
    )
    assert blocked_removed.status_code == 409
    assert "follow up" in blocked_removed.json()["detail"].lower()

    archived = client.post(
        f"/api/followup/items/{item['id']}/status",
        json={"status": "ARSIP", "alasan": "Dihapus dari daftar follow-up"},
    )
    assert archived.status_code == 200, archived.text
    assert _items(client, jenis="garansi") == []

    other = create_customer(nama="Pelanggan Jadwal Dua")
    other_unit = create_unit(other["id"], nopol="B 7012 JDW")
    other_record = _record_id(make_transaction(other_unit["id"]))
    _shift_record(
        db_session,
        other_record,
        days_ago=20,
        garansi_sampai=date.today() + timedelta(days=5),
    )
    other_item = _items(client, jenis="garansi")[0]
    client.post(
        f"/api/followup/items/{other_item['id']}/followup",
        json={"status": "DIBUKA"},
    )
    scheduled = client.post(
        f"/api/followup/items/{other_item['id']}/status",
        json={"status": "AKAN_DATANG", "tanggal_service": date.today().isoformat()},
    )
    assert scheduled.status_code == 200, scheduled.text
    assert scheduled.json()["status"] == "AKAN_DATANG"

    third = create_customer(nama="Pelanggan Jadwal Tiga")
    third_unit = create_unit(third["id"], nopol="B 7013 JDW")
    third_record = _record_id(make_transaction(third_unit["id"]))
    _shift_record(
        db_session,
        third_record,
        days_ago=20,
        garansi_sampai=date.today() + timedelta(days=5),
    )

    active = _items(client, jenis="garansi")
    pending = _items(
        client, jenis="garansi", exclude_status="AKAN_DATANG"
    )
    scheduled_only = _items(client, jenis="garansi", status="AKAN_DATANG")
    assert len(active) == 2
    assert len(pending) == 1
    assert pending[0]["customer_id"] == third["id"]
    assert [row["id"] for row in scheduled_only] == [other_item["id"]]

    dashboard = client.get("/api/reports/daily-cash").json()
    assert dashboard["garansi_akan_habis"] == len(pending)
    assert dashboard["akan_datang_garansi"] == len(scheduled_only)

    third_item = pending[0]
    assert third_item["customer_id"] == third["id"]
    client.post(
        f"/api/followup/items/{third_item['id']}/followup",
        json={"status": "DIBUKA"},
    )
    not_coming = client.post(
        f"/api/followup/items/{third_item['id']}/status",
        json={"status": "TIDAK_DATANG"},
    )
    assert not_coming.status_code == 200, not_coming.text
    assert not_coming.json()["status"] == "TIDAK_DATANG"
    assert [row["id"] for row in _items(client, jenis="garansi")] == [other_item["id"]]
    assert _items(client, jenis="garansi", exclude_status="AKAN_DATANG") == []
    dashboard = client.get("/api/reports/daily-cash").json()
    assert dashboard["garansi_akan_habis"] == 0
    assert dashboard["akan_datang_garansi"] == len(scheduled_only)


def test_reschedule_akan_datang_tetap_di_kolom(
    client, create_customer, create_unit, make_transaction, db_session
):
    customer = create_customer(nama="Pelanggan Reschedule")
    unit = create_unit(customer["id"], nopol="B 7015 RSC")
    record_id = _record_id(make_transaction(unit["id"]))
    _shift_record(
        db_session,
        record_id,
        days_ago=20,
        garansi_sampai=date.today() + timedelta(days=5),
    )

    item = _items(client, jenis="garansi")[0]
    client.post(
        f"/api/followup/items/{item['id']}/followup",
        json={"status": "DIBUKA"},
    )
    first = date.today() + timedelta(days=3)
    scheduled = client.post(
        f"/api/followup/items/{item['id']}/status",
        json={"status": "AKAN_DATANG", "tanggal_service": first.isoformat()},
    )
    assert scheduled.status_code == 200, scheduled.text

    moved = date.today() + timedelta(days=10)
    rescheduled = client.post(
        f"/api/followup/items/{item['id']}/status",
        json={"status": "AKAN_DATANG", "tanggal_service": moved.isoformat()},
    )
    assert rescheduled.status_code == 200, rescheduled.text
    body = rescheduled.json()
    assert body["status"] == "AKAN_DATANG"
    assert body["tanggal_service"] == moved.isoformat()

    still_scheduled = _items(client, jenis="garansi", status="AKAN_DATANG")
    assert [row["id"] for row in still_scheduled] == [item["id"]]
    assert still_scheduled[0]["tanggal_service"] == moved.isoformat()


def test_prospek_akan_datang_bisa_reschedule(
    client, create_customer, create_unit, make_transaction, db_session
):
    customer = create_customer(nama="Pelanggan Prospek Jadwal")
    unit = create_unit(customer["id"], nopol="B 7018 PSJ")
    record_id = _record_id(make_transaction(unit["id"]))
    _shift_record(db_session, record_id, days_ago=7)

    item = _items(client, jenis="prospek")[0]
    client.post(
        f"/api/followup/items/{item['id']}/followup",
        json={"status": "DIBUKA"},
    )
    first = date.today() + timedelta(days=3)
    scheduled = client.post(
        f"/api/followup/items/{item['id']}/status",
        json={"status": "AKAN_DATANG", "tanggal_service": first.isoformat()},
    )
    assert scheduled.status_code == 200, scheduled.text

    moved = date.today() + timedelta(days=10)
    rescheduled = client.post(
        f"/api/followup/items/{item['id']}/status",
        json={"status": "AKAN_DATANG", "tanggal_service": moved.isoformat()},
    )
    assert rescheduled.status_code == 200, rescheduled.text
    body = rescheduled.json()
    assert body["status"] == "AKAN_DATANG"
    assert body["tanggal_service"] == moved.isoformat()

    still_listed = _items(client, jenis="prospek")
    row = next(row for row in still_listed if row["id"] == item["id"])
    assert row["status"] == "AKAN_DATANG"
    assert row["tanggal_service"] == moved.isoformat()


def test_dashboard_menampilkan_kartu_followup(
    client, create_customer, create_unit, make_transaction, db_session
):
    customer = create_customer(nama="Pelanggan Dasbor")
    unit = create_unit(customer["id"], nopol="B 7010 DSH")
    record_id = _record_id(
        make_transaction(
            unit["id"],
            jobs=[{"deskripsi": "Servis", "jumlah": 1, "harga": "100000"}],
            jenis_bayar="KREDIT",
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
