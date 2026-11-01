"""Penanda unit ditinggal untuk follow-up kendaraan selesai."""
from __future__ import annotations

from database import migrations as schema_migrations
from database.base import Base
from database.models import PengerjaanNota
from database.session import SessionLocal, build_engine


def _rows():
    with SessionLocal() as db:
        return db.query(PengerjaanNota).order_by(PengerjaanNota.id).all()


def test_unit_ditinggal_lunas_membuat_baris_pengerjaan(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer(nama="Pelanggan Ditinggal")
    unit = create_unit(customer["id"], nopol="B 4001 TGL")

    response = make_transaction(unit["id"], unit_ditinggal=True)
    assert response.status_code == 201, response.text
    record = response.json()["record"]

    rows = _rows()
    assert len(rows) == 1
    row = rows[0]
    assert row.service_record_id == record["id"]
    assert row.unit_id == unit["id"]
    assert row.customer_id == customer["id"]
    assert row.status_pengerjaan == "SEDANG_DIKERJAKAN"
    assert row.diambil_pada is None
    assert row.diubah_oleh == "Kasir"


def test_unit_ditinggal_kredit_membuat_baris_pengerjaan(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer(nama="Pelanggan Kredit Tinggal")
    unit = create_unit(customer["id"], nopol="B 4002 TGL")

    response = make_transaction(
        unit["id"],
        jenis_bayar="KREDIT",
        dp="50000",
        unit_ditinggal=True,
    )
    assert response.status_code == 201, response.text
    record = response.json()["record"]

    rows = _rows()
    assert len(rows) == 1
    assert rows[0].service_record_id == record["id"]
    assert rows[0].status_pengerjaan == "SEDANG_DIKERJAKAN"


def test_tanpa_unit_ditinggal_tidak_membuat_baris(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer(nama="Pelanggan Ambil Sendiri")
    unit = create_unit(customer["id"], nopol="B 4003 TGL")

    response = make_transaction(unit["id"], unit_ditinggal=False)
    assert response.status_code == 201, response.text
    assert _rows() == []


def test_request_id_sama_tidak_menggandakan_baris(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer(nama="Pelanggan Idempoten")
    unit = create_unit(customer["id"], nopol="B 4004 TGL")

    payload = {
        "unit_ditinggal": True,
        "request_id": "pengerjaan-marker-0001",
    }
    first = make_transaction(unit["id"], **payload)
    second = make_transaction(unit["id"], **payload)
    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    assert first.json()["record"]["id"] == second.json()["record"]["id"]
    assert len(_rows()) == 1


def test_migrasi_v15_membuat_tabel_pengerjaan(tmp_path):
    engine = build_engine(f"sqlite:///{(tmp_path / 'legacy_v15.db').as_posix()}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE pengerjaan_nota")
        conn.exec_driver_sql("PRAGMA user_version = 14")

    assert schema_migrations.apply_migrations(engine) == 15
    with engine.connect() as conn:
        table = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='pengerjaan_nota'"
        ).first()
        assert table is not None


def test_daftar_kendaraan_selesai_dan_hitungan_dasbor(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer(nama="Pelanggan Menunggu")
    unit = create_unit(customer["id"], nopol="B 4101 TUN")

    response = make_transaction(unit["id"], unit_ditinggal=True)
    assert response.status_code == 201, response.text
    record = response.json()["record"]

    listing = client.get("/api/pengerjaan")
    assert listing.status_code == 200, listing.text
    data = listing.json()
    assert data["jumlah"] == 1
    item = data["items"][0]
    assert item["record_id"] == record["id"]
    assert item["no_nota"] == record["no_nota"]
    assert item["customer_nama"] == "Pelanggan Menunggu"
    assert item["status_pengerjaan"] == "SEDANG_DIKERJAKAN"
    assert item["diambil_pada"] is None
    assert item["sisa_bayar"] == "0.00"

    daily = client.get("/api/reports/daily-cash")
    assert daily.status_code == 200, daily.text
    assert daily.json()["kendaraan_selesai"] == 1


def test_unit_diambil_menutup_penanda(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer(nama="Pelanggan Ambil Unit")
    unit = create_unit(customer["id"], nopol="B 4102 AMB")
    make_transaction(unit["id"], unit_ditinggal=True)

    marker_id = client.get("/api/pengerjaan").json()["items"][0]["id"]
    response = client.post(f"/api/pengerjaan/{marker_id}/diambil")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status_pengerjaan"] == "SUDAH_DIAMBIL"
    assert body["diambil_pada"]
    assert client.get("/api/pengerjaan").json()["jumlah"] == 0
    assert client.get("/api/reports/daily-cash").json()["kendaraan_selesai"] == 0

    again = client.post(f"/api/pengerjaan/{marker_id}/diambil")
    assert again.status_code == 409, again.text


def test_nota_void_tidak_masuk_kendaraan_selesai(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer(nama="Pelanggan Void")
    unit = create_unit(customer["id"], nopol="B 4103 VOI")
    response = make_transaction(unit["id"], unit_ditinggal=True)
    record = response.json()["record"]

    voided = client.post(
        f"/api/service-records/{record['id']}/void",
        json={"alasan": "Salah input"},
    )
    assert voided.status_code == 200, voided.text
    assert client.get("/api/pengerjaan").json()["jumlah"] == 0
    assert client.get("/api/reports/daily-cash").json()["kendaraan_selesai"] == 0
