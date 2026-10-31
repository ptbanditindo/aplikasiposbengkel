"""Tahap 6: label barang dibuat saat transaksi dan dicetak di bawah nota."""
from __future__ import annotations

import re

from database.models import VehicleOrUnit
from services.escpos_service import ReceiptBuilder
from services.receipt_service import _append_label_strips


def _text(receipt) -> str:
    return "\n".join(receipt["struk_58"])


def _codes(body) -> list[str]:
    return [label["kode"] for label in body["receipt"]["labels"]]


def _radiator_unit(create_unit, customer_id, tipe="Radiator Fortuner"):
    return create_unit(
        customer_id,
        unit_type="RADIATOR_ONLY",
        nopol=None,
        jenis_mobil=None,
        tahun_mobil=None,
        tipe_radiator=tipe,
    )


def test_label_baru_dibuat_saat_transaksi_bukan_saat_unit(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer(nama="Dkdk", nomor_hp="08928183920")
    unit = _radiator_unit(create_unit, customer["id"])
    assert unit["label_radiator"] is None

    response = make_transaction(unit["id"])
    assert response.status_code == 201, response.text
    body = response.json()
    receipt = body["receipt"]

    codes = _codes(body)
    assert len(codes) == 1
    assert re.fullmatch(r"RAD-\d{8}-001", codes[0])
    assert receipt["labels"][0]["nama"] == "Radiator Fortuner"
    assert receipt["labels"][0]["unit"] == "[BAWA RADIATOR SAJA]"

    text = _text(receipt)
    assert "- - - - - - - - - - - - - - -" in text
    assert "POTONG DI SINI" in text
    assert "Pelanggan: Dkdk" in text
    assert "No. HP: 08928183920" in text
    assert "Unit: [BAWA RADIATOR SAJA]" in text
    assert codes[0] in text
    assert "(Radiator Fortuner)" in text
    assert all(len(line) <= 32 for line in receipt["struk_58"])
    assert all(len(line) <= 48 for line in receipt["struk_80"])

    listed = client.get(f"/api/customers/{customer['id']}/units").json()
    assert listed[0]["label_radiator"] == codes[0]


def test_label_berurutan_per_hari_dan_cetak_ulang_tetap(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer(nama="Dhaniar", nomor_hp="082117836284")
    first_unit = _radiator_unit(create_unit, customer["id"], "Radiator Fortuner")
    second_unit = _radiator_unit(create_unit, customer["id"], "Radiator Genset")

    first = make_transaction(first_unit["id"]).json()
    second = make_transaction(second_unit["id"]).json()
    first_code = _codes(first)[0]
    second_code = _codes(second)[0]

    prefix = first_code.rsplit("-", 1)[0]
    assert first_code == f"{prefix}-001"
    assert second_code == f"{prefix}-002"

    record_id = first["record"]["id"]
    reprint_a = client.get(f"/api/service-records/{record_id}/receipt").json()
    reprint_b = client.get(f"/api/service-records/{record_id}/receipt").json()
    assert [label["kode"] for label in reprint_a["labels"]] == [first_code]
    assert reprint_a["struk_58"] == reprint_b["struk_58"]
    assert reprint_a["escpos_58_base64"] == reprint_b["escpos_58_base64"]


def test_transaksi_kedua_unit_yang_sama_tidak_menambah_urutan(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer(nama="Unit Berulang", nomor_hp="081200000070")
    first_unit = _radiator_unit(create_unit, customer["id"], "Radiator Avanza")
    other_unit = _radiator_unit(create_unit, customer["id"], "Radiator Panther")

    first_code = _codes(make_transaction(first_unit["id"]).json())[0]
    repeat_code = _codes(make_transaction(first_unit["id"]).json())[0]
    other_code = _codes(make_transaction(other_unit["id"]).json())[0]

    prefix = first_code.rsplit("-", 1)[0]
    assert repeat_code == first_code
    assert other_code == f"{prefix}-002"


def test_label_mobil_memakai_nopol_dan_model(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer(nama="Pemilik Mobil", nomor_hp="081200000071")
    unit = create_unit(customer["id"], nopol="B 1234 ABC", jenis_mobil="Avanza")

    body = make_transaction(unit["id"]).json()
    label = body["receipt"]["labels"][0]

    assert re.fullmatch(r"RAD-\d{8}-001", label["kode"])
    assert label["unit"] == "B 1234 ABC (Avanza)"
    assert label["nama"] == "Radiator Avanza"
    assert "Unit: B 1234 ABC (Avanza)" in _text(body["receipt"])


def test_label_lama_tidak_diganti_saat_transaksi(
    db_session, create_customer, create_unit, make_transaction
):
    customer = create_customer(nama="Unit Lama", nomor_hp="081200000072")
    unit = _radiator_unit(create_unit, customer["id"], "Radiator Lama")
    old_code = "RAD-20200101-777"
    row = db_session.get(VehicleOrUnit, unit["id"])
    row.label_radiator = old_code
    db_session.commit()

    body = make_transaction(unit["id"]).json()
    assert _codes(body) == [old_code]
    assert old_code in _text(body["receipt"])


def test_void_dan_retur_memakai_kode_label_yang_sama(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer(nama="Klaim", nomor_hp="081200000073")
    void_unit = _radiator_unit(create_unit, customer["id"], "Radiator Void")
    return_unit = _radiator_unit(create_unit, customer["id"], "Radiator Retur")

    void_body = make_transaction(void_unit["id"]).json()
    void_code = _codes(void_body)[0]
    voided = client.post(
        f"/api/service-records/{void_body['record']['id']}/void",
        json={"alasan": "Salah input"},
    )
    assert voided.status_code == 200, voided.text
    after_void = client.get(
        f"/api/service-records/{void_body['record']['id']}/receipt"
    ).json()
    assert [label["kode"] for label in after_void["labels"]] == [void_code]

    return_body = make_transaction(return_unit["id"]).json()
    return_code = _codes(return_body)[0]
    job_id = return_body["receipt"]["jobs"][0]["id"]
    returned = client.post(
        f"/api/service-records/{return_body['record']['id']}/returns",
        json={
            "alasan": "Pekerjaan dibatalkan",
            "items": [{"service_job_id": job_id, "jumlah": 1}],
        },
    )
    assert returned.status_code == 201, returned.text
    after_return = client.get(
        f"/api/service-records/{return_body['record']['id']}/receipt"
    ).json()
    assert [label["kode"] for label in after_return["labels"]] == [return_code]


def test_beberapa_strip_label_dicetak_terpisah():
    builder = ReceiptBuilder(32)
    labels = [
        {
            "kode": "RAD-20261031-001",
            "nama": "Radiator Fortuner",
            "unit": "[BAWA RADIATOR SAJA]",
            "customer_nama": "Dhaniar",
            "customer_hp": "082117836284",
        },
        {
            "kode": "RAD-20261031-002",
            "nama": "Radiator Genset",
            "unit": "[BAWA RADIATOR SAJA]",
            "customer_nama": "Dhaniar",
            "customer_hp": "082117836284",
        },
    ]
    _append_label_strips(builder, labels)
    lines = builder.lines()
    text = "\n".join(lines)

    assert text.count("POTONG DI SINI") == 1
    assert text.count("Pelanggan: Dhaniar") == 2
    assert "RAD-20261031-001" in text
    assert "RAD-20261031-002" in text
    assert all(len(line) <= 32 for line in lines)
