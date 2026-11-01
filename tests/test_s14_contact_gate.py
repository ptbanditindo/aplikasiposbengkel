"""Tahap 5: gerbang pesan pusat dan aturan anti-gangguan."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from database.models import FollowupItem, ServiceRecord, WhatsAppLog
from services import contact_gate_service, settings_service, whatsapp_service
from services.auth_service import OWNER


def _record_id(response):
    assert response.status_code == 201, response.text
    return response.json()["record"]["id"]


def _items(client, **params):
    response = client.get("/api/followup/items", params=params)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def _window_outside_now():
    now = datetime.now()
    return f"{(now.hour + 2) % 24:02d}:00", f"{(now.hour + 3) % 24:02d}:00"


def _set_window(client, start, end):
    response = client.put(
        "/api/settings/ops",
        json={"followup_jam_mulai": start, "followup_jam_selesai": end},
    )
    assert response.status_code == 200, response.text


def _shift(db_session, record_id, days_ago):
    record = db_session.get(ServiceRecord, record_id)
    record.waktu_service = datetime.combine(
        date.today() - timedelta(days=days_ago), time(9, 0)
    )
    db_session.commit()


def _credit(client, create_customer, create_unit, make_transaction, due_days=-1):
    customer = create_customer(nama="Pelanggan Piutang Gate")
    unit = create_unit(customer["id"], nopol="B 8101 GAT")
    record_id = _record_id(
        make_transaction(
            unit["id"],
            jobs=[{"deskripsi": "Servis Radiator", "jumlah": 1, "harga": "150000"}],
            jenis_bayar="KREDIT",
            dp="50000",
            bayar="50000",
        )
    )
    return customer, unit, record_id


def test_dnc_memblokir_prospek_dan_memberi_peringatan_piutang(
    client, create_customer, create_unit, make_transaction, db_session
):
    customer = create_customer(nama="Pelanggan DNC")
    unit = create_unit(customer["id"], nopol="B 8102 DNC")
    prospek_record = _record_id(
        make_transaction(unit["id"], bergaransi=False)
    )
    _shift(db_session, prospek_record, 30)

    credit_customer = create_customer(nama="Pelanggan DNC Piutang")
    credit_unit = create_unit(credit_customer["id"], nopol="B 8103 DNC")
    credit_id = _record_id(
        make_transaction(
            credit_unit["id"],
            jobs=[{"deskripsi": "Servis", "jumlah": 1, "harga": "120000"}],
            jenis_bayar="KREDIT",
            dp="40000",
            bayar="40000",
        )
    )
    record = db_session.get(ServiceRecord, credit_id)
    record.jatuh_tempo = date.today() - timedelta(days=1)
    db_session.commit()

    updated = client.put(
        f"/api/customers/{customer['id']}/contact",
        json={"do_not_contact": True},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["do_not_contact"] is True

    client.put(
        f"/api/customers/{credit_customer['id']}/contact",
        json={"do_not_contact": True},
    )

    prospek = next(
        row for row in _items(client, jenis="prospek")
        if row["customer_id"] == customer["id"]
    )
    assert prospek["bisa_followup"] is False
    assert "DNC" in prospek["bisa_alasan"]

    blocked = client.post(
        f"/api/followup/items/{prospek['id']}/followup",
        json={"status": "DIBUKA"},
    )
    assert blocked.status_code == 409, blocked.text
    assert "DNC" in blocked.json()["detail"]

    reminder = client.post(
        f"/api/customers/{credit_customer['id']}/remind"
    )
    assert reminder.status_code == 201, reminder.text
    assert "berhenti dihubungi" in reminder.json()["peringatan"].lower()

    chat = client.get(
        f"/api/customers/{customer['id']}/wa-link?jenis=chat"
    )
    assert chat.status_code == 200, chat.text
    assert chat.json()["link"].startswith("https://wa.me/")
    assert chat.json()["peringatan"]

    gate = client.get(
        f"/api/service-records/{credit_id}/wa-gate?jenis=pengerjaan"
    )
    assert gate.status_code == 200, gate.text
    assert gate.json()["allowed"] is True
    assert gate.json()["peringatan"]

    consent_off = client.put(
        f"/api/customers/{customer['id']}/contact",
        json={"wa_consent": False},
    )
    assert consent_off.status_code == 200, consent_off.text
    blocked_chat = client.get(
        f"/api/customers/{customer['id']}/wa-link?jenis=chat"
    )
    assert blocked_chat.status_code == 409, blocked_chat.text
    assert "izin" in blocked_chat.json()["detail"].lower()


def test_prioritas_piutang_dan_batas_satu_pesan_per_hari(
    client, create_customer, create_unit, make_transaction, db_session
):
    customer, _unit, credit_id = _credit(
        client, create_customer, create_unit, make_transaction
    )
    other_unit = create_unit(customer["id"], nopol="B 8104 PRI")
    prospek_record = _record_id(
        make_transaction(other_unit["id"], bergaransi=False)
    )
    _shift(db_session, prospek_record, 30)
    record = db_session.get(ServiceRecord, credit_id)
    record.jatuh_tempo = date.today() - timedelta(days=1)
    db_session.commit()

    prospek = next(
        row for row in _items(client, jenis="prospek")
        if row["customer_id"] == customer["id"]
    )
    assert prospek["bisa_followup"] is False
    assert "piutang" in prospek["bisa_alasan"].lower()

    reminder = client.post(f"/api/customers/{customer['id']}/remind")
    assert reminder.status_code == 201, reminder.text

    blocked = client.post(
        f"/api/followup/items/{prospek['id']}/followup",
        json={"status": "DIBUKA"},
    )
    assert blocked.status_code == 409, blocked.text
    assert "hari ini" in blocked.json()["detail"].lower()

    logs = db_session.query(WhatsAppLog).filter_by(customer_id=customer["id"]).all()
    assert len(logs) == 1


def test_pesan_sejenis_digabung_satu_kali(
    client, create_customer, create_unit, make_transaction, db_session
):
    customer = create_customer(nama="Pelanggan Gabung")
    first_unit = create_unit(customer["id"], nopol="B 8105 GAB")
    second_unit = create_unit(customer["id"], nopol="B 8106 GAB")
    first = _record_id(make_transaction(first_unit["id"], bergaransi=False))
    second = _record_id(make_transaction(second_unit["id"], bergaransi=False))
    _shift(db_session, first, 30)
    _shift(db_session, second, 30)

    items = [
        row for row in _items(client, jenis="prospek")
        if row["customer_id"] == customer["id"]
    ]
    assert len(items) == 2

    response = client.post(
        f"/api/followup/items/{items[0]['id']}/followup",
        json={"status": "DIBUKA"},
    )
    assert response.status_code == 200, response.text
    text = response.json()["wa_text"]
    assert items[0]["unit_deskripsi"] in text
    assert items[1]["unit_deskripsi"] in text

    db_session.expire_all()
    logs = db_session.query(WhatsAppLog).filter_by(
        customer_id=customer["id"], status="DIBUKA"
    ).all()
    assert len(logs) == 2
    assert {log.pesan for log in logs} == {text}

    refreshed = [
        row for row in _items(client, jenis="prospek")
        if row["customer_id"] == customer["id"]
    ]
    assert all(row["status"] == "SUDAH_FOLLOWUP" for row in refreshed)
    ops = settings_service.get_ops_settings(db_session)
    assert contact_gate_service.daily_cap_reason(
        db_session, customer["id"], datetime.now(), ops
    )


def test_jeda_tujuh_hari_dan_batas_bulanan(
    client, create_customer, create_unit, make_transaction, db_session
):
    customer = create_customer(nama="Pelanggan Jeda")
    first_unit = create_unit(customer["id"], nopol="B 8107 JDA")
    second_unit = create_unit(customer["id"], nopol="B 8108 JDA")
    first = _record_id(make_transaction(first_unit["id"], bergaransi=False))
    second = _record_id(make_transaction(second_unit["id"], bergaransi=False))
    _shift(db_session, first, 30)
    _shift(db_session, second, 30)

    items = [
        row for row in _items(client, jenis="prospek")
        if row["customer_id"] == customer["id"]
    ]
    db_session.rollback()
    moment = datetime.combine(date.today(), time(10, 0))
    whatsapp_service.append_attempt(
        db_session,
        db_session.get(ServiceRecord, first).unit.customer,
        jenis=whatsapp_service.JENIS_FOLLOWUP,
        status=whatsapp_service.STATUS_OPENED,
        message="Pesan sebelumnya.",
        operator=OWNER,
        record=db_session.get(ServiceRecord, first),
        now=moment - timedelta(days=2),
    )
    db_session.commit()

    from services import followup_service

    ops = settings_service.get_ops_settings(db_session)
    ops["maks_pesan_hari"] = 5
    ops["maks_pesan_bulan"] = 5
    reason = contact_gate_service.policy_reason(
        db_session, db_session.get(FollowupItem, items[0]["id"]), moment, ops
    )
    assert "Jeda minimal 7 hari" in reason

    ops["jeda_prospek_servis_hari"] = 1
    ops["maks_pesan_bulan"] = 1
    reason = contact_gate_service.policy_reason(
        db_session, db_session.get(FollowupItem, items[0]["id"]), moment, ops
    )
    assert "per bulan" in reason


def test_gate_pusat_jam_untuk_chat_dan_pengerjaan(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer(nama="Pelanggan Jam Gate")
    unit = create_unit(customer["id"], nopol="B 8109 JAM")
    record_id = _record_id(make_transaction(unit["id"]))

    start, end = _window_outside_now()
    _set_window(client, start, end)
    gate = client.get(
        f"/api/service-records/{record_id}/wa-gate?jenis=pengerjaan"
    )
    assert gate.status_code == 200, gate.text
    assert gate.json()["allowed"] is False
    assert "pukul" in gate.json()["alasan"].lower()

    chat = client.get(f"/api/customers/{customer['id']}/wa-link?jenis=chat")
    assert chat.status_code == 409, chat.text
    assert "pukul" in chat.json()["detail"].lower()

    _set_window(client, "00:00", "23:59")
    allowed = client.get(
        f"/api/service-records/{record_id}/wa-gate?jenis=pengerjaan"
    )
    assert allowed.status_code == 200
    assert allowed.json()["allowed"] is True
    assert "pukul" not in allowed.json()["alasan"].lower()


def test_pengaturan_angka_anti_gangguan_bisa_diubah(client):
    config = client.get("/api/config").json()
    ops = config["ops"]
    for key, value in {
        "prospek_hari_1": 30,
        "prospek_hari_2": 60,
        "prospek_hari_3": 90,
        "garansi_arsip_hari": 7,
        "belum_bisa_hari": 14,
        "belum_bisa_panjang_hari": 28,
        "maks_pesan_hari": 1,
        "maks_pesan_bulan": 2,
        "jeda_prospek_servis_hari": 7,
        "maks_tidak_merespons": 3,
        "piutang_jeda_hari": 14,
        "piutang_maks_pengingat": 3,
    }.items():
        assert ops[key] == value

    response = client.put(
        "/api/settings/ops",
        json={
            "maks_pesan_hari": 2,
            "maks_pesan_bulan": 4,
            "jeda_prospek_servis_hari": 10,
            "prospek_hari_1": 45,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["maks_pesan_hari"] == 2
    assert body["maks_pesan_bulan"] == 4
    assert body["jeda_prospek_servis_hari"] == 10
    assert body["prospek_hari_1"] == 45


def test_belum_bisa_menunda_dan_tidak_merespons_berhenti(
    client, create_customer, create_unit, make_transaction, db_session
):
    customer = create_customer(nama="Pelanggan Belum Bisa")
    unit = create_unit(customer["id"], nopol="B 8110 BBS")
    record_id = _record_id(make_transaction(unit["id"], bergaransi=False))
    _shift(db_session, record_id, 30)

    item = next(
        row for row in _items(client, jenis="prospek")
        if row["customer_id"] == customer["id"]
    )
    first = client.post(
        f"/api/followup/items/{item['id']}/followup",
        json={"status": "DIBUKA"},
    )
    assert first.status_code == 200, first.text

    delayed = client.post(
        f"/api/followup/items/{item['id']}/status",
        json={"status": "MASIH_KENDALA", "tunda_hari": 14},
    )
    assert delayed.status_code == 200, delayed.text
    assert delayed.json()["tunda_sampai"]
    client.put(
        "/api/settings/ops",
        json={"cooldown_hari": 0, "maks_pesan_bulan": 5, "maks_pesan_hari": 5},
    )

    blocked = client.post(
        f"/api/followup/items/{item['id']}/followup",
        json={"status": "DIBUKA"},
    )
    assert blocked.status_code == 409, blocked.text
    assert "ditunda" in blocked.json()["detail"].lower()

    from services import followup_service

    moment = datetime.combine(date.today(), time(10, 0))
    for offset in (16, 24):
        db_session.rollback()
        followup_service.follow_up(
            db_session,
            item["id"],
            "DIBUKA",
            OWNER,
            now=moment + timedelta(days=offset),
        )

    db_session.expire_all()
    row = db_session.get(FollowupItem, item["id"])
    assert row.status == "ARSIP"
    assert "Tidak merespons" in (row.alasan_arsip or "")
    assert row.no_response_count >= 3


def test_garansi_h_tidak_diulang_setelah_h7_dibalas(
    client, create_customer, create_unit, make_transaction, db_session
):
    from services import followup_service

    answered_customer = create_customer(nama="Garansi Dibalas")
    answered_unit = create_unit(answered_customer["id"], nopol="B 8111 GAR")
    expiry = date.today() + timedelta(days=10)
    answered_id = _record_id(make_transaction(answered_unit["id"]))
    record = db_session.get(ServiceRecord, answered_id)
    record.garansi_sampai = expiry
    db_session.commit()

    h7 = expiry - timedelta(days=7)
    moment_h7 = datetime.combine(h7, time(10, 0))
    db_session.rollback()
    items = followup_service.list_items(
        db_session, jenis="garansi", today=h7, now=moment_h7
    )["items"]
    item = next(row for row in items if row["customer_id"] == answered_customer["id"])
    assert item["jatuh_tempo"] == h7

    db_session.rollback()
    followup_service.follow_up(
        db_session, item["id"], "DIBUKA", OWNER, now=moment_h7
    )

    moment_h = datetime.combine(expiry, time(10, 0))
    db_session.rollback()
    after = followup_service.list_items(
        db_session, jenis="garansi", today=expiry, now=moment_h
    )["items"]
    answered_row = next(
        row for row in after if row["customer_id"] == answered_customer["id"]
    )
    assert answered_row["bisa_followup"] is False
    assert "H-7" in answered_row["bisa_alasan"]

    other_customer = create_customer(nama="Garansi Belum Dibalas")
    other_unit = create_unit(other_customer["id"], nopol="B 8112 GAR")
    other_id = _record_id(make_transaction(other_unit["id"]))
    other_record = db_session.get(ServiceRecord, other_id)
    other_record.garansi_sampai = expiry
    db_session.commit()
    db_session.rollback()
    other = followup_service.list_items(
        db_session, jenis="garansi", today=expiry, now=moment_h
    )["items"]
    other_row = next(
        row for row in other if row["customer_id"] == other_customer["id"]
    )
    assert other_row["bisa_followup"] is True
    assert other_row["jatuh_tempo"] == expiry


def test_sudah_bayar_menolak_sisa_dan_menutup_item(
    client, create_customer, create_unit, make_transaction
):
    customer, _unit, record_id = _credit(
        client, create_customer, create_unit, make_transaction
    )
    items = _items(client, jenis="piutang")
    item = next(row for row in items if row["customer_id"] == customer["id"])

    blocked = client.post(
        f"/api/followup/items/{item['id']}/status",
        json={"status": "SUDAH_BAYAR"},
    )
    assert blocked.status_code == 400, blocked.text
    assert "lunas" in blocked.json()["detail"].lower()

    payment = client.post(
        f"/api/service-records/{record_id}/payments",
        json={"nominal": "100000", "metode": "CASH"},
    )
    assert payment.status_code in (200, 201), payment.text

    closed = client.post(
        f"/api/followup/items/{item['id']}/status",
        json={"status": "SUDAH_BAYAR"},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "SUDAH_BAYAR"
    assert _items(client, jenis="piutang") == []
