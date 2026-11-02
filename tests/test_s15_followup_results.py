"""Tahap 3: hasil follow up pelanggan dari seluruh pesan."""
from __future__ import annotations

from datetime import datetime, timedelta

from database.models import FollowupItem, WhatsAppLog


def _log(db, customer_id, when, jenis="followup"):
    row = WhatsAppLog(
        customer_id=customer_id,
        nomor_masked="0812****",
        jenis=jenis,
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


def test_hasil_followup_dapat_difilter_periode(
    client, create_customer, create_unit, make_transaction, db_session
):
    now = datetime.now()

    lama = create_customer(nama="Hasil Lama")
    lama_unit = create_unit(lama["id"], nopol="B 8401 LAMA")
    _log(db_session, lama["id"], now - timedelta(days=40))
    make_transaction(lama_unit["id"])

    baru = create_customer(nama="Hasil Baru")
    _log(db_session, baru["id"], now - timedelta(days=1))

    start = (now.date() - timedelta(days=6)).isoformat()
    end = now.date().isoformat()
    body = client.get(
        f"/api/followup/results?start={start}&end={end}"
    ).json()
    assert body["balik_lagi"] == 0
    assert body["masih_bagus"] == 1

    semua = client.get("/api/followup/results").json()
    assert semua["balik_lagi"] == 1
    assert semua["masih_bagus"] == 1


def test_hasil_followup_menolak_periode_terbalik(client):
    response = client.get(
        "/api/followup/results?start=2026-01-02&end=2026-01-01"
    )
    assert response.status_code == 400
    assert "Tanggal akhir" in response.json()["detail"]


def test_jumlah_followup_menghitung_pesan_dan_mengabaikan_piutang(
    client, create_customer, db_session
):
    customer = create_customer(nama="Follow Up Dua Pesan")
    when = datetime.now() - timedelta(days=1)
    _log(db_session, customer["id"], when)
    _log(db_session, customer["id"], when + timedelta(hours=1))

    piutang = create_customer(nama="Bukan Hasil Follow Up")
    _log(db_session, piutang["id"], when, jenis="piutang")

    body = client.get("/api/followup/results").json()
    assert body["followup_total"] == 2
    assert body["masih_bagus"] == 1
    assert body["balik_lagi"] == 0
