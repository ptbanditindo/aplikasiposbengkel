"""P-03: hapus unit = arsip, riwayat nota tetap utuh."""
from __future__ import annotations

from dataclasses import replace

from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from database import migrations
from database.base import Base
from database.models import AuditEvent, Customer, VehicleOrUnit
from database.session import build_engine, init_db
from services import backup_service


def _units(client, customer_id):
    return client.get(f"/api/customers/{customer_id}/units").json()


def _overview_row(client, customer_id):
    rows = client.get("/api/customers/overview").json()
    return next(row for row in rows if row["id"] == customer_id)


def test_hapus_unit_tanpa_riwayat_hilang_dari_daftar(
    client, create_customer, create_unit
):
    customer = create_customer(nama="Hapus Unit", nomor_hp="081200000080")
    unit = create_unit(customer["id"], nopol="B 8080 HAP")

    response = client.delete(f"/api/units/{unit['id']}")
    assert response.status_code == 204, response.text

    assert _units(client, customer["id"]) == []
    row = _overview_row(client, customer["id"])
    assert row["total_unit"] == 0
    assert row["units"] == []


def test_hapus_unit_beriwayat_tidak_menghapus_nota(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer(nama="Riwayat Aman", nomor_hp="081200000081")
    unit = create_unit(customer["id"], nopol="B 8181 AMN")
    record = make_transaction(unit["id"]).json()["record"]

    response = client.delete(f"/api/units/{unit['id']}")
    assert response.status_code == 204, response.text

    assert _units(client, customer["id"]) == []
    detail = client.get(f"/api/service-records/{record['id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["unit_id"] == unit["id"]
    assert "B 8181 AMN" in detail.json()["unit_deskripsi"]

    receipt = client.get(f"/api/service-records/{record['id']}/receipt")
    assert receipt.status_code == 200, receipt.text


def test_transaksi_baru_menolak_unit_terarsip(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer(nama="Tolak Arsip", nomor_hp="081200000082")
    unit = create_unit(customer["id"], nopol="B 8282 ARS")
    assert client.delete(f"/api/units/{unit['id']}").status_code == 204

    response = make_transaction(unit["id"])
    assert response.status_code == 400, response.text
    assert "sudah dihapus" in response.json()["detail"]


def test_arsip_unit_mencatat_audit(
    client, db_session, create_customer, create_unit
):
    customer = create_customer(nama="Audit Unit", nomor_hp="081200000083")
    unit = create_unit(customer["id"], nopol="B 8383 AUD")

    assert client.delete(f"/api/units/{unit['id']}").status_code == 204

    db_session.expire_all()
    events = list(
        db_session.scalars(
            select(AuditEvent).where(AuditEvent.action == "UNIT")
        ).all()
    )
    assert len(events) == 1
    assert events[0].reference_id == str(unit["id"])
    assert "dihapus dari daftar" in (events[0].reason or "")

    # Idempoten: hapus ulang tidak menambah audit.
    assert client.delete(f"/api/units/{unit['id']}").status_code == 204
    db_session.expire_all()
    assert (
        len(
            list(
                db_session.scalars(
                    select(AuditEvent).where(AuditEvent.action == "UNIT")
                ).all()
            )
        )
        == 1
    )


def test_migrasi_10_ke_11_menambah_kolom_arsip_tanpa_kehilangan_data(
    tmp_path, monkeypatch
):
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(
        backup_service, "settings", replace(settings, backup_dir=backup_dir)
    )

    legacy = build_engine(f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    Base.metadata.create_all(legacy)
    with Session(legacy) as db:
        customer = Customer(nama="Pelanggan Lama", nomor_hp="081200000084")
        db.add(customer)
        db.commit()
        db.refresh(customer)
        db.add(
            VehicleOrUnit(
                customer_id=customer.id,
                unit_type="MOBIL",
                nopol="B 8484 LMA",
            )
        )
        db.commit()

    # Database versi 10 belum punya kolom arsip.
    with legacy.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE vehicle_or_units DROP COLUMN archived_at")
        conn.exec_driver_sql("PRAGMA user_version = 10")

    init_db(legacy)

    with legacy.connect() as conn:
        columns = {
            row[1]
            for row in conn.exec_driver_sql(
                "PRAGMA table_info(vehicle_or_units)"
            )
        }
        assert "archived_at" in columns
        assert conn.exec_driver_sql(
            "SELECT nopol FROM vehicle_or_units"
        ).scalar() == "B 8484 LMA"
        assert (
            conn.exec_driver_sql("PRAGMA user_version").scalar()
            == migrations.SCHEMA_VERSION
        )

    # Idempoten: startup ulang tidak membuat backup baru.
    init_db(legacy)
    assert len(list(backup_dir.glob("sebelum_migrasi_*.db"))) == 1
