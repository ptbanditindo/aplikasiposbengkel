"""Tahap 3: hasil follow up pelanggan dari seluruh pesan."""
from __future__ import annotations

from datetime import datetime, timedelta

from database.models import FollowupItem, WhatsAppLog


def _log(db, customer_id, when):
    row = WhatsAppLog(
        customer_id=customer_id,
        nomor_masked="0812****",
        jenis="followup",
        status="DIBUKA",
        pesan="Pesan uji",
        operator="Pemilik",
        created_at=when,
    )
    db.add(row)
    db.commit()


def _item(db, customer_id, status, when, key):
    row = FollowupItem(
        jenis="prospek",
        item_key=key,
        customer_id=customer_id,
        judul="Prospek uji",
        status=status,
        followup_terakhir=when,
        updated_at=when,
        created_at=when,
    )
    db.add(row)
    db.commit()


def test_hasil_followup_memakai_pesan_dan_hasil_terbaru(
    client, create_customer, create_unit, make_transaction, db_session
):
    yesterday = datetime.now() - timedelta(days=1)
    today = datetime.now()

    balik = create_customer(nama="Hasil Balik")
    balik_unit = create_unit(balik["id"], nopol="B 8301 BAL")
    _log(db_session, balik["id"], yesterday)
    make_transaction(balik_unit["id"])

    bagus = create_customer(nama="Hasil Bagus")
    _log(db_session, bagus["id"], yesterday)

    masalah = create_customer(nama="Hasil Masalah")
    _log(db_session, masalah["id"], yesterday)
    _item(db_session, masalah["id"], "MASIH_KENDALA", today, "hasil:masalah")

    tolak = create_customer(nama="Hasil Tolak")
    _log(db_session, tolak["id"], yesterday)
    _item(db_session, tolak["id"], "TIDAK_DATANG", today, "hasil:tolak")

    response = client.get("/api/followup/results")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["balik_lagi"] == 1
    assert body["masih_bagus"] == 1
    assert body["bermasalah"] == 1
    assert body["menolak"] == 1


def test_hasil_followup_menghitung_pelanggan_sekali(
    client, create_customer, db_session
):
    customer = create_customer(nama="Hasil Satu Pelanggan")
    yesterday = datetime.now() - timedelta(days=1)
    _log(db_session, customer["id"], yesterday)
    _log(db_session, customer["id"], yesterday + timedelta(hours=1))
    body = client.get("/api/followup/results").json()
    assert body["masih_bagus"] == 1
