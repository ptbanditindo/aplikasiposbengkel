"""R-01: klaim garansi atomik; klaim kedua harus 409 dan tidak menimpa tanggal."""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from database.models import ServiceRecord


def test_r01_klaim_kedua_409_tanpa_menimpa_tanggal(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    record_id = make_transaction(unit["id"]).json()["record"]["id"]

    first = client.put(f"/api/service-records/{record_id}/claim")
    assert first.status_code == 200, first.text
    first_date = first.json()["tanggal_klaim"]

    second = client.put(f"/api/service-records/{record_id}/claim")
    assert second.status_code == 409, second.text
    assert "sudah pernah" in second.json()["detail"].lower()

    detail = client.get(f"/api/service-records/{record_id}").json()
    assert detail["status_klaim"] == "Sudah claim"
    assert detail["tanggal_klaim"] == first_date


def test_r01_tanggal_klaim_pertama_tidak_ditimpa(
    client, create_customer, create_unit, make_transaction, db_session
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    record_id = make_transaction(unit["id"]).json()["record"]["id"]

    old_date = date.today() - timedelta(days=10)
    record = db_session.get(ServiceRecord, record_id)
    record.status_klaim = "Sudah claim"
    record.tanggal_klaim = old_date
    db_session.commit()

    response = client.put(f"/api/service-records/{record_id}/claim")
    assert response.status_code == 409, response.text

    detail = client.get(f"/api/service-records/{record_id}").json()
    assert detail["tanggal_klaim"] == old_date.isoformat()


def test_r01_dua_klaim_paralel_hanya_satu_sukses(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    record_id = make_transaction(unit["id"]).json()["record"]["id"]

    barrier = threading.Barrier(2)

    def submit(_index: int) -> int:
        barrier.wait(timeout=30)
        try:
            response = client.put(f"/api/service-records/{record_id}/claim")
        except Exception:  # noqa: BLE001 - setara respons HTTP 500
            return 500
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(submit, range(2)))

    assert sorted(statuses) == [200, 409], statuses

    detail = client.get(f"/api/service-records/{record_id}").json()
    assert detail["status_klaim"] == "Sudah claim"
    assert detail["tanggal_klaim"] == date.today().isoformat()
