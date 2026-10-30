"""TC-13 s/d TC-16: masa garansi, servis tanpa garansi, klaim aktif/kedaluwarsa."""
from __future__ import annotations

from datetime import date, timedelta

from database.models import ServiceRecord


def _receipt_text(body) -> str:
    return "\n".join(body["receipt"]["struk_58"])


def test_tc13_garansi_satu_bulan_tepat_30_hari(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    today = date.today()

    response = make_transaction(unit["id"], bergaransi=True, garansi_bulan=1)

    assert response.status_code == 201, response.text
    body = response.json()
    record = body["record"]
    expected = today + timedelta(days=30)
    assert record["bergaransi"] is True
    assert record["garansi_sampai"] == expected.isoformat()
    assert record["garansi_aktif"] is True
    assert record["warranty_status"] == "AKTIF"
    receipt = _receipt_text(body)
    assert "BERGARANSI" in receipt
    assert expected.strftime("%d/%m/%Y") in receipt
    assert body["receipt"]["catatan_garansi"]


def test_tc14_servis_tanpa_garansi(client, create_customer, create_unit, make_transaction):
    customer = create_customer()
    unit = create_unit(customer["id"])

    response = make_transaction(unit["id"], bergaransi=False)

    assert response.status_code == 201, response.text
    body = response.json()
    record = body["record"]
    assert record["bergaransi"] is False
    assert record["garansi_sampai"] is None
    assert record["catatan_garansi"] is None
    assert record["garansi_aktif"] is False
    assert record["warranty_status"] == "TANPA GARANSI"
    assert "TANPA GARANSI" in _receipt_text(body)


def test_tc15_klaim_garansi_masa_aktif_berhasil(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    transaction = make_transaction(unit["id"]).json()
    record_id = transaction["record"]["id"]

    response = client.put(f"/api/service-records/{record_id}/claim")

    assert response.status_code == 200, response.text
    record = response.json()
    assert record["status_klaim"] == "Sudah claim"
    assert record["tanggal_klaim"] == date.today().isoformat()
    assert record["warranty_status"] == "SUDAH CLAIM"
    assert record["garansi_aktif"] is False

    repeated = client.put(f"/api/service-records/{record_id}/claim")
    assert repeated.status_code == 409
    assert "sudah pernah" in repeated.json()["detail"].lower()


def test_tc16_klaim_garansi_kedaluwarsa_ditolak(
    client, create_customer, create_unit, make_transaction, db_session
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    transaction = make_transaction(unit["id"]).json()
    record_id = transaction["record"]["id"]

    # Simulasikan nota lama yang masa garansinya sudah lewat satu hari.
    record = db_session.get(ServiceRecord, record_id)
    record.garansi_sampai = date.today() - timedelta(days=1)
    db_session.commit()

    response = client.put(f"/api/service-records/{record_id}/claim")

    assert response.status_code == 400, response.text
    assert "Masa garansi telah habis" in response.json()["detail"]

    summary = client.get(f"/api/service-records/{record_id}").json()
    assert summary["status_klaim"] == "Belum claim"
    assert summary["tanggal_klaim"] is None
    assert summary["garansi_aktif"] is False
    assert summary["warranty_status"] == "KEDALUWARSA"


def test_klaim_nota_tanpa_garansi_ditolak(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    transaction = make_transaction(unit["id"], bergaransi=False).json()

    response = client.put(
        f"/api/service-records/{transaction['record']['id']}/claim"
    )
    assert response.status_code == 400
    assert "tidak memiliki garansi" in response.json()["detail"]


def test_tanggal_garansi_kustom_di_masa_lalu_ditolak(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer()
    unit = create_unit(customer["id"])

    response = make_transaction(
        unit["id"],
        garansi_sampai=(date.today() - timedelta(days=2)).isoformat(),
    )
    assert response.status_code == 400
    assert "masa lalu" in response.json()["detail"]
