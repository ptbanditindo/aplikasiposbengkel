"""R-05: laporan semua waktu harus mencakup seluruh riwayat walau ada jeda kosong."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from database.models import ServiceRecord


def _create_at(client, make_transaction, unit_id, days_ago, amount, warranty=True):
    record_id = make_transaction(
        unit_id,
        bergaransi=warranty,
        jobs=[{"deskripsi": "Jasa", "jumlah": 1, "harga": str(amount)}],
    ).json()["record"]["id"]
    return record_id


def _move(db_session, record_id, moment):
    record = db_session.get(ServiceRecord, record_id)
    assert record is not None
    record.waktu_service = moment
    db_session.commit()


def test_r05_semua_waktu_tanpa_transaksi(client):
    response = client.get("/api/reports/all-time")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["jumlah_transaksi"] == 0
    assert body["total_omset"] == "0.00"
    assert body["start"] == body["end"] == date.today().isoformat()
    assert body["harian"] == []
    assert body["transaksi"] == []


def test_r05_semua_waktu_menembus_jeda_bertahun_tahun(
    client, create_customer, create_unit, make_transaction, db_session
):
    today = date.today()
    customer = create_customer()
    unit_a = create_unit(customer["id"], nopol="B 5001 OLD")
    customer_b = create_customer(nama="Pelanggan B", nomor_hp="081250000001")
    unit_b = create_unit(customer_b["id"], nopol="B 5002 OLD")

    recent = _create_at(client, make_transaction, unit_a["id"], 0, 100000)
    middle = _create_at(client, make_transaction, unit_a["id"], 900, 200000)
    oldest = _create_at(client, make_transaction, unit_b["id"], 1800, 300000)
    claimed = _create_at(client, make_transaction, unit_a["id"], 1500, 400000)

    _move(db_session, recent, datetime.combine(today, time(10, 0)))
    _move(db_session, middle, datetime.combine(today - timedelta(days=900), time(10, 0)))
    _move(db_session, oldest, datetime.combine(today - timedelta(days=1800), time(10, 0)))
    _move(db_session, claimed, datetime.combine(today - timedelta(days=1500), time(10, 0)))

    claim = client.put(f"/api/service-records/{claimed}/claim")
    assert claim.status_code == 200, claim.text

    response = client.get("/api/reports/all-time")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["jumlah_transaksi"] == 4
    assert body["total_omset"] == "1000000.00"
    assert body["jumlah_unit_servis"] == 2
    assert body["garansi_aktif"] == 3
    assert body["start"] == (today - timedelta(days=1800)).isoformat()
    assert body["end"] == today.isoformat()

    active_days = [row for row in body["harian"] if row["jumlah_transaksi"] > 0]
    assert len(active_days) == 4
    assert sum(row["jumlah_transaksi"] for row in body["harian"]) == 4
    assert sum(int(row["total_omset"].split(".")[0]) for row in body["harian"]) == 1000000
    assert sum(row["garansi_aktif"] for row in body["harian"]) == 3

    # Tidak ada nota yang terhitung ganda di daftar transaksi.
    ids = [record["id"] for record in body["transaksi"]]
    assert len(ids) == len(set(ids)) == 4
