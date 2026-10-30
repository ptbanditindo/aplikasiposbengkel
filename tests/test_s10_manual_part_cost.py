"""S-10: part manual tanpa stok harus punya snapshot modal & ditandai bila belum diisi."""
from __future__ import annotations

from datetime import date


def _manual_part(harga_satuan="100000", harga_modal=None):
    part = {"nama_part": "Part Kustom", "jumlah": 1, "harga_satuan": harga_satuan}
    if harga_modal is not None:
        part["harga_modal"] = harga_modal
    return part


def test_s10_part_manual_memakai_snapshot_modal_input(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer()
    unit = create_unit(customer["id"])

    response = make_transaction(
        unit["id"], parts=[_manual_part(harga_modal="60000")]
    )

    assert response.status_code == 201, response.text
    body = response.json()
    record = body["record"]
    assert record["laba_kotor"] == "40000.00"
    assert record["modal_tidak_diketahui"] is False

    detail = client.get(f"/api/service-records/{record['id']}").json()
    assert detail["laba_kotor"] == "40000.00"
    assert detail["modal_tidak_diketahui"] is False

    daily = client.get("/api/reports/daily-cash").json()
    assert daily["laba_kotor"] == "40000.00"
    assert daily["transaksi_tanpa_modal"] == 0


def test_s10_part_manual_tanpa_modal_ditandai_bukan_nol_palsu(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    today = date.today().isoformat()

    response = make_transaction(
        unit["id"], parts=[_manual_part(harga_satuan="100000")]
    )

    assert response.status_code == 201, response.text
    body = response.json()
    record = body["record"]
    assert record["laba_kotor"] == "0.00"
    assert record["modal_tidak_diketahui"] is True
    assert any("modal" in warning.lower() for warning in body["warnings"])

    daily = client.get("/api/reports/daily-cash").json()
    assert daily["laba_kotor"] == "0.00"
    assert daily["transaksi_tanpa_modal"] == 1

    period = client.get(
        "/api/reports/period", params={"start": today, "end": today}
    ).json()
    assert period["transaksi_tanpa_modal"] == 1
    assert period["harian"][0]["transaksi_tanpa_modal"] == 1


def test_s10_perubahan_modal_master_tidak_mengubah_laba_historis(
    client, create_customer, create_unit, make_transaction, stock
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    item = stock("SP-001")

    response = make_transaction(
        unit["id"],
        parts=[
            {
                "stock_item_id": item["id"],
                "jumlah": 1,
                "harga_satuan": "135000",
            }
        ],
    )
    assert response.status_code == 201, response.text
    record_id = response.json()["record"]["id"]
    assert response.json()["record"]["laba_kotor"] == "50000.00"

    updated = client.put(
        f"/api/stock/{item['id']}", json={"harga_modal": "120000"}
    )
    assert updated.status_code == 200, updated.text

    detail = client.get(f"/api/service-records/{record_id}").json()
    assert detail["laba_kotor"] == "50000.00"
    assert detail["modal_tidak_diketahui"] is False

    daily = client.get("/api/reports/daily-cash").json()
    assert daily["laba_kotor"] == "50000.00"
