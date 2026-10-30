"""S-03: garansi yang sudah diklaim tidak boleh dihitung sebagai garansi aktif."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from database.models import ServiceRecord


def _move_service_time(db_session, record_id: int, moment: datetime) -> None:
    record = db_session.get(ServiceRecord, record_id)
    assert record is not None
    record.waktu_service = moment
    db_session.commit()


def test_s03_nota_sudah_claim_bukan_garansi_aktif(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    record_id = make_transaction(unit["id"]).json()["record"]["id"]

    claim = client.put(f"/api/service-records/{record_id}/claim")
    assert claim.status_code == 200, claim.text
    assert claim.json()["garansi_aktif"] is False
    assert claim.json()["warranty_status"] == "SUDAH CLAIM"

    detail = client.get(f"/api/service-records/{record_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["garansi_aktif"] is False
    assert detail.json()["warranty_status"] == "SUDAH CLAIM"

    receipt = client.get(f"/api/service-records/{record_id}/receipt")
    assert receipt.status_code == 200, receipt.text
    assert receipt.json()["garansi_aktif"] is False


def test_s03_laporan_harian_mengecualikan_garansi_sudah_claim(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    make_transaction(unit["id"])
    claimed_id = make_transaction(unit["id"]).json()["record"]["id"]
    make_transaction(unit["id"], bergaransi=False)

    claim = client.put(f"/api/service-records/{claimed_id}/claim")
    assert claim.status_code == 200, claim.text

    daily = client.get("/api/reports/daily-cash")
    assert daily.status_code == 200, daily.text
    assert daily.json()["garansi_aktif"] == 1


def test_s03_laporan_periode_menghitung_garansi_per_hari(
    client, create_customer, create_unit, make_transaction, db_session
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    today = date.today()

    make_transaction(unit["id"])
    older_id = make_transaction(unit["id"]).json()["record"]["id"]
    _move_service_time(
        db_session,
        older_id,
        datetime.combine(today - timedelta(days=3), time(10, 0)),
    )
    claimed_id = make_transaction(unit["id"]).json()["record"]["id"]
    claim = client.put(f"/api/service-records/{claimed_id}/claim")
    assert claim.status_code == 200, claim.text

    report = client.get(
        "/api/reports/period",
        params={
            "start": (today - timedelta(days=6)).isoformat(),
            "end": today.isoformat(),
        },
    )
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["garansi_aktif"] == 2

    harian = {row["tanggal"]: row for row in body["harian"]}
    assert harian[today.isoformat()]["garansi_aktif"] == 1
    assert harian[(today - timedelta(days=3)).isoformat()]["garansi_aktif"] == 1
    assert harian[(today - timedelta(days=5)).isoformat()]["garansi_aktif"] == 0
