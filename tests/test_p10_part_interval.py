"""P-10: interval servis berkala untuk sparepart (master dan snapshot nota)."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from config import settings
from database.base import Base
from database.models import Customer, ServicePart, ServiceRecord, StockItem
from database.session import build_engine, init_db
from services import backup_service
from services.followup_service import add_months


def _create_stock(client, kode, interval):
    response = client.post(
        "/api/stock",
        json={
            "kode": kode,
            "nama": f"Part {kode}",
            "harga_modal": "40000",
            "harga_jual": "60000",
            "jumlah": 10,
            "interval_servis_bulan": interval,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _shift_record(db_session, record_id, service_day):
    record = db_session.get(ServiceRecord, record_id)
    record.waktu_service = datetime.combine(service_day, time(9, 0))
    db_session.commit()


def _servis_items(client, customer_id=None):
    params = {"jenis": "servis_berkala"}
    if customer_id is not None:
        params["customer_id"] = customer_id
    response = client.get("/api/followup/items", params=params)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def test_stok_interval_crud_dan_validasi(client):
    created = {}
    for interval in (0, 6, 120):
        item = _create_stock(client, f"P10-{interval}", interval)
        created[interval] = item
        assert item["interval_servis_bulan"] == interval

    updated = client.put(
        f"/api/stock/{created[0]['id']}",
        json={"interval_servis_bulan": 12},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["interval_servis_bulan"] == 12

    too_big = client.post(
        "/api/stock",
        json={"nama": "Part Lebih", "interval_servis_bulan": 121},
    )
    assert too_big.status_code == 422

    negative = client.put(
        f"/api/stock/{created[6]['id']}",
        json={"interval_servis_bulan": -1},
    )
    assert negative.status_code == 422

    listed = client.get("/api/stock").json()
    stored = next(row for row in listed if row["id"] == created[6]["id"])
    assert stored["interval_servis_bulan"] == 6


def test_transaksi_part_simpan_snapshot_interval(
    client, create_customer, create_unit, make_transaction, db_session
):
    stock = _create_stock(client, "P10-SNAP", 6)
    customer = create_customer(nama="Pelanggan Snapshot Part")
    unit = create_unit(customer["id"], nopol="B 7201 SNP")

    response = make_transaction(
        unit["id"],
        jobs=[{"deskripsi": "Pasang part", "jumlah": 1, "harga": "20000"}],
        parts=[
            {
                "stock_item_id": stock["id"],
                "nama_part": stock["nama"],
                "jumlah": 1,
                "harga_satuan": "60000",
            }
        ],
    )
    assert response.status_code == 201, response.text
    record_id = response.json()["record"]["id"]
    part = (
        db_session.query(ServicePart)
        .filter_by(service_record_id=record_id)
        .one()
    )
    assert part.interval_servis_bulan == 6

    body = response.json()
    assert body["receipt"]["parts"][0]["interval_servis_bulan"] == 6

    # Mengubah master tidak boleh mengubah snapshot nota lama.
    client.put(
        f"/api/stock/{stock['id']}",
        json={"interval_servis_bulan": 12},
    )
    db_session.expire_all()
    part = (
        db_session.query(ServicePart)
        .filter_by(service_record_id=record_id)
        .one()
    )
    assert part.interval_servis_bulan == 6

    # Payload boleh menimpa interval untuk satu nota.
    override = make_transaction(
        unit["id"],
        jobs=[{"deskripsi": "Pasang part", "jumlah": 1, "harga": "20000"}],
        parts=[
            {
                "stock_item_id": stock["id"],
                "nama_part": stock["nama"],
                "jumlah": 1,
                "harga_satuan": "60000",
                "interval_servis_bulan": 2,
            }
        ],
    )
    assert override.status_code == 201, override.text
    second_part = (
        db_session.query(ServicePart)
        .filter_by(service_record_id=override.json()["record"]["id"])
        .one()
    )
    assert second_part.interval_servis_bulan == 2


def test_followup_servis_berkala_muncul_dari_part(
    client, create_customer, create_unit, make_transaction, db_session
):
    stock = _create_stock(client, "P10-FU", 3)
    customer = create_customer(nama="Pelanggan Part Berkala")
    unit = create_unit(customer["id"], nopol="B 7202 FU")
    response = make_transaction(
        unit["id"],
        jobs=[{"deskripsi": "Servis umum", "jumlah": 1, "harga": "30000"}],
        parts=[
            {
                "stock_item_id": stock["id"],
                "nama_part": stock["nama"],
                "jumlah": 1,
                "harga_satuan": "60000",
            }
        ],
    )
    assert response.status_code == 201, response.text
    record_id = response.json()["record"]["id"]
    _shift_record(db_session, record_id, add_months(date.today(), -3))

    items = _servis_items(client, customer_id=customer["id"])
    assert len(items) == 1
    item = items[0]
    assert item["jenis"] == "servis_berkala"
    assert item["rincian"][0]["jenis_item"] == "sparepart"
    assert item["rincian"][0]["nama"] == stock["nama"]
    assert item["rincian"][0]["pekerjaan"] == f"Sparepart {stock['nama']}"
    assert item["rincian"][0]["interval_bulan"] == 3
    assert item["rincian"][0]["jatuh_tempo"] == item["jatuh_tempo"]


def test_jasa_dan_part_interval_tetap_satu_item_per_pelanggan(
    client, create_customer, create_unit, make_transaction, db_session
):
    stock = _create_stock(client, "P10-BOTH", 3)
    jasa = client.post(
        "/api/harga-jasa",
        json={"nama": "Cuci Radiator", "harga_standar": "100000", "interval_servis_bulan": 3},
    ).json()
    customer = create_customer(nama="Pelanggan Jasa Part")
    unit = create_unit(customer["id"], nopol="B 7203 JP")
    response = make_transaction(
        unit["id"],
        jobs=[
            {
                "harga_jasa_id": jasa["id"],
                "deskripsi": "Cuci Radiator",
                "jumlah": 1,
                "harga": "100000",
            }
        ],
        parts=[
            {
                "stock_item_id": stock["id"],
                "nama_part": stock["nama"],
                "jumlah": 1,
                "harga_satuan": "60000",
            }
        ],
    )
    assert response.status_code == 201, response.text
    _shift_record(db_session, response.json()["record"]["id"], add_months(date.today(), -3))

    items = _servis_items(client, customer_id=customer["id"])
    assert len(items) == 1
    assert {row["jenis_item"] for row in items[0]["rincian"]} == {"jasa", "sparepart"}


def test_part_tanpa_interval_tidak_memunculkan_pengingat(
    client, create_customer, create_unit, make_transaction, db_session
):
    stock = _create_stock(client, "P10-NONE", 0)
    customer = create_customer(nama="Pelanggan Part Tanpa Interval")
    unit = create_unit(customer["id"], nopol="B 7204 NONE")
    response = make_transaction(
        unit["id"],
        jobs=[{"deskripsi": "Servis umum", "jumlah": 1, "harga": "30000"}],
        parts=[
            {
                "stock_item_id": stock["id"],
                "nama_part": stock["nama"],
                "jumlah": 1,
                "harga_satuan": "60000",
            }
        ],
    )
    assert response.status_code == 201, response.text
    _shift_record(
        db_session,
        response.json()["record"]["id"],
        date.today() - timedelta(days=400),
    )
    assert _servis_items(client, customer_id=customer["id"]) == []


def test_migrasi_11_ke_12_menambah_kolom_tanpa_kehilangan_data(
    tmp_path, monkeypatch
):
    from database import migrations

    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(
        backup_service, "settings", replace(settings, backup_dir=backup_dir)
    )
    legacy = build_engine(f"sqlite:///{(tmp_path / 'legacy_p10.db').as_posix()}")
    Base.metadata.create_all(legacy)
    with Session(legacy) as db:
        customer = Customer(nama="Pelanggan P10 Lama", nomor_hp="081200000099")
        db.add(customer)
        db.flush()
        db.add(
            StockItem(
                kode="P10-LEGACY",
                nama="Part Lama",
                harga_modal=1000,
                harga_jual=2000,
                jumlah=4,
            )
        )
        db.commit()

    with legacy.begin() as conn:
        conn.exec_driver_sql(
            "ALTER TABLE stock_items DROP COLUMN interval_servis_bulan"
        )
        conn.exec_driver_sql(
            "ALTER TABLE service_parts DROP COLUMN interval_servis_bulan"
        )
        conn.exec_driver_sql("PRAGMA user_version = 11")

    init_db(legacy)

    with legacy.connect() as conn:
        assert (
            conn.exec_driver_sql("PRAGMA user_version").scalar()
            == migrations.SCHEMA_VERSION
        )
        stock_columns = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(stock_items)")
        }
        part_columns = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(service_parts)")
        }
        assert "interval_servis_bulan" in stock_columns
        assert "interval_servis_bulan" in part_columns
        assert conn.exec_driver_sql(
            "SELECT nama FROM stock_items WHERE kode = 'P10-LEGACY'"
        ).scalar() == "Part Lama"
        assert conn.exec_driver_sql(
            "SELECT interval_servis_bulan FROM stock_items WHERE kode = 'P10-LEGACY'"
        ).scalar() == 0
