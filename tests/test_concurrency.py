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
