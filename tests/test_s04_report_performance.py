"""S-04: laporan tidak boleh N+1 dan periode tidak boleh O(hari x nota)."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, time, timedelta

from sqlalchemy import event

from database.models import ServiceRecord
from database.session import engine


@contextmanager
def hitung_query():
    statements = []

    def _before(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _before)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", _before)


def _seed_transactions(client, create_customer, create_unit, make_transaction, db_session):
    """24 nota, 3 unit, tersebar merata di 12 hari terakhir, tiap nota 1 part stok."""
    today = date.today()
    units = []
    for index in range(3):
        customer = create_customer(
            nama=f"Pelanggan {index}",
            nomor_hp=f"081200000{index:03d}",
        )
        units.append(
            create_unit(
                customer["id"],
                nopol=f"B 900{index} XYZ",
                jenis_mobil=f"Mobil {index}",
            )
        )

    record_ids = []
    for index in range(24):
        unit = units[index % 3]
        response = make_transaction(
            unit["id"],
            parts=[
                {
                    "stock_item_id": _stock_id(client, "SP-003"),
                    "jumlah": 1,
                    "harga_satuan": "35000",
                }
            ],
        )
        assert response.status_code == 201, response.text
        record_ids.append(response.json()["record"]["id"])

    for index, record_id in enumerate(record_ids):
        record = db_session.get(ServiceRecord, record_id)
        record.waktu_service = datetime.combine(
            today - timedelta(days=index % 12), time(9 + (index // 12), 0)
        )
        db_session.commit()
    return units


def _stock_id(client, kode):
    items = client.get("/api/stock").json()
    return next(item["id"] for item in items if item["kode"] == kode)


def test_s04_riwayat_nota_query_konstan(
    client, create_customer, create_unit, make_transaction, db_session
):
    _seed_transactions(client, create_customer, create_unit, make_transaction, db_session)

    with hitung_query() as statements:
        response = client.get("/api/service-records")

    assert response.status_code == 200, response.text
    assert len(response.json()) == 24
    assert len(statements) <= 12, f"{len(statements)} query untuk 24 nota"


def test_s04_laporan_periode_query_konstan_dan_akurat(
    client, create_customer, create_unit, make_transaction, db_session
):
    _seed_transactions(client, create_customer, create_unit, make_transaction, db_session)
    today = date.today()
    start = today - timedelta(days=11)

    with hitung_query() as statements:
        response = client.get(
            "/api/reports/period",
            params={"start": start.isoformat(), "end": today.isoformat()},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(statements) <= 12, f"{len(statements)} query untuk 24 nota / 12 hari"
    assert body["jumlah_transaksi"] == 24
    assert body["jumlah_unit_servis"] == 3
    assert body["total_omset"] == "4440000.00"
    assert body["total_jasa"] == "3600000.00"
    assert body["total_part"] == "840000.00"
    assert body["garansi_aktif"] == 24

    harian = body["harian"]
    assert len(harian) == 12
    assert sum(row["jumlah_transaksi"] for row in harian) == 24
    assert all(row["jumlah_transaksi"] == 2 for row in harian)
    assert sum(int(row["total_omset"].split(".")[0]) for row in harian) == 4440000
    assert sum(row["garansi_aktif"] for row in harian) == 24


def test_s04_sold_parts_query_konstan_dan_akurat(
    client, create_customer, create_unit, make_transaction, db_session
):
    _seed_transactions(client, create_customer, create_unit, make_transaction, db_session)

    with hitung_query() as statements:
        response = client.get("/api/reports/sold-parts")

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(statements) <= 12, f"{len(statements)} query untuk 24 nota"
    assert body["jumlah_penjualan"] == 24
    assert body["total_qty"] == 24
    assert body["total_nilai"] == "840000.00"
