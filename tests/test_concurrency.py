"""Uji konkurensi transaksi (T-01: nomor nota atomik)."""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from sqlalchemy import text

PARALLEL = 20


def _payload(index: int, unit_id: int) -> dict:
    return {
        "unit_id": unit_id,
        "keluhan_awal": f"Uji paralel {index}",
        "metode_bayar": "TRANSFER",
        "jobs": [
            {"deskripsi": "Korok Radiator", "jumlah": 1, "harga": "150000"}
        ],
        "parts": [],
    }


def test_t01_dua_puluh_transaksi_paralel_sukses_dan_nota_unik(
    client, create_customer, create_unit
):
    customer = create_customer(nama="Pelanggan Paralel", nomor_hp="081200000020")
    unit = create_unit(customer["id"], nopol="B 2020 PAR")

    barrier = threading.Barrier(PARALLEL)

    def submit(index: int) -> int:
        barrier.wait(timeout=30)
        try:
            response = client.post(
                "/api/pos/transaction", json=_payload(index, unit["id"])
            )
        except Exception:  # noqa: BLE001 - setara respons HTTP 500
            return 500
        return response.status_code

    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        statuses = list(pool.map(submit, range(PARALLEL)))

    assert statuses.count(201) == PARALLEL, statuses
    records = client.get("/api/service-records", params={"limit": 500}).json()
    notas = [record["no_nota"] for record in records]
    assert len(notas) == PARALLEL
    assert len(set(notas)) == PARALLEL, notas

    prefix = f"INV-{date.today():%Y%m%d}-"
    assert sorted(notas) == [f"{prefix}{number:04d}" for number in range(1, PARALLEL + 1)]


def _part_payload(unit_id: int, stock_id: int, qty: int) -> dict:
    return {
        "unit_id": unit_id,
        "keluhan_awal": "Uji stok paralel",
        "metode_bayar": "TRANSFER",
        "jobs": [],
        "parts": [
            {
                "stock_item_id": stock_id,
                "nama_part": "",
                "jumlah": qty,
                "harga_satuan": "135000",
            }
        ],
    }


def _set_stock(client, stock_id: int, jumlah: int) -> None:
    response = client.put(f"/api/stock/{stock_id}", json={"jumlah": jumlah})
    assert response.status_code == 200, response.text


def test_t08_stok_satu_dua_transaksi_paralel_hanya_satu_sukses(
    client, create_customer, create_unit, stock
):
    customer = create_customer(nama="Pelanggan Stok A", nomor_hp="081200000022")
    unit = create_unit(customer["id"], nopol="B 2022 STK")
    item = stock("SP-001")
    _set_stock(client, item["id"], 1)

    barrier = threading.Barrier(2)

    def submit(_index: int) -> int:
        barrier.wait(timeout=30)
        try:
            response = client.post(
                "/api/pos/transaction",
                json=_part_payload(unit["id"], item["id"], 1),
            )
        except Exception:  # noqa: BLE001
            return 500
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(submit, range(2)))

    assert sorted(statuses) == [201, 409], statuses
    assert stock("SP-001")["jumlah"] == 0
    assert len(client.get("/api/service-records").json()) == 1


def test_t08_stok_cukup_dua_transaksi_paralel_tanpa_lost_update(
    client, create_customer, create_unit, stock
):
    customer = create_customer(nama="Pelanggan Stok B", nomor_hp="081200000023")
    unit = create_unit(customer["id"], nopol="B 2023 STK")
    item = stock("SP-001")
    _set_stock(client, item["id"], 4)

    barrier = threading.Barrier(2)

    def submit(_index: int) -> int:
        barrier.wait(timeout=30)
        try:
            response = client.post(
                "/api/pos/transaction",
                json=_part_payload(unit["id"], item["id"], 2),
            )
        except Exception:  # noqa: BLE001
            return 500
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(submit, range(2)))

    assert statuses == [201, 201], statuses
    assert stock("SP-001")["jumlah"] == 0
    assert len(client.get("/api/service-records").json()) == 2


def test_t01_counter_dimulai_dari_nota_tertinggi_yang_sudah_ada(
    client, db_session, create_customer, create_unit, make_transaction
):
    customer = create_customer(nama="Pelanggan Counter", nomor_hp="081200000021")
    unit = create_unit(customer["id"], nopol="B 2021 CTR")
    prefix = f"INV-{date.today():%Y%m%d}-"

    first = make_transaction(unit["id"]).json()["record"]["no_nota"]
    assert first == f"{prefix}0001"

    # Simulasikan database lama: counter belum ada saat nota 0001 dibuat.
    db_session.execute(text("DELETE FROM nota_counters"))
    db_session.commit()

    second = make_transaction(unit["id"]).json()["record"]["no_nota"]
    assert second == f"{prefix}0002"
