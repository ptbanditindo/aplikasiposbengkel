"""Repository transaksi servis & notanya."""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import or_, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, joinedload, selectinload

from database.models import (
    Customer,
    DeviceNotaCounter,
    NotaCounter,
    ServicePart,
    ServiceRecord,
    ServiceRecordMechanic,
    VehicleOrUnit,
)


def _with_details():
    return (
        selectinload(ServiceRecord.parts).selectinload(ServicePart.stock_item),
        selectinload(ServiceRecord.jobs),
        selectinload(ServiceRecord.unit).selectinload(VehicleOrUnit.customer),
        selectinload(ServiceRecord.mechanics).joinedload(
            ServiceRecordMechanic.employee
        ),
        selectinload(ServiceRecord.commissions),
        joinedload(ServiceRecord.cashier_employee),
    )


def get_record(db: Session, record_id: int) -> Optional[ServiceRecord]:
    return db.get(ServiceRecord, record_id)


def get_record_by_request_id(db: Session, request_id: str) -> Optional[ServiceRecord]:
    statement = select(ServiceRecord).where(ServiceRecord.request_id == request_id)
    return db.scalar(statement)


def list_records(db: Session, query: str = "", limit: int = 200) -> List[ServiceRecord]:
    statement = (
        select(ServiceRecord)
        .join(VehicleOrUnit, ServiceRecord.unit_id == VehicleOrUnit.id)
        .join(Customer, VehicleOrUnit.customer_id == Customer.id)
        .options(*_with_details())
    )
    term = (query or "").strip()
    if term:
        like = f"%{term}%"
        statement = statement.where(
            or_(
                ServiceRecord.no_nota.ilike(like),
                ServiceRecord.keluhan_awal.ilike(like),
                Customer.nama.ilike(like),
                Customer.nomor_hp.ilike(like),
                VehicleOrUnit.nopol.ilike(like),
                VehicleOrUnit.label_radiator.ilike(like),
                VehicleOrUnit.tipe_radiator.ilike(like),
                VehicleOrUnit.nama_barang.ilike(like),
                VehicleOrUnit.nomor_seri.ilike(like),
                VehicleOrUnit.kendaraan_asal.ilike(like),
            )
        )
    statement = statement.order_by(
        ServiceRecord.waktu_service.desc(), ServiceRecord.id.desc()
    ).limit(limit)
    return list(db.scalars(statement).all())


def records_between(db: Session, start: datetime, end: datetime) -> List[ServiceRecord]:
    statement = (
        select(ServiceRecord)
        .where(ServiceRecord.waktu_service >= start, ServiceRecord.waktu_service < end)
        .options(*_with_details())
        .order_by(ServiceRecord.waktu_service.desc(), ServiceRecord.id.desc())
    )
    return list(db.scalars(statement).all())


def all_records(db: Session) -> List[ServiceRecord]:
    statement = (
        select(ServiceRecord)
        .options(*_with_details())
        .order_by(ServiceRecord.waktu_service.desc(), ServiceRecord.id.desc())
    )
    return list(db.scalars(statement).all())


def nota_prefix_exists(db: Session, prefix: str) -> List[str]:
    statement = select(ServiceRecord.no_nota).where(ServiceRecord.no_nota.like(f"{prefix}%"))
    return list(db.scalars(statement).all())


def allocate_numeric_nota(db: Session) -> str:
    """Nomor nota angka berurutan untuk nota baru; nota lama tidak diubah."""
    key = "NUMERIC"
    counter = db.get(NotaCounter, key)
    if counter is None:
        highest = 0
        for nota in db.scalars(select(ServiceRecord.no_nota)).all():
            text = str(nota or "")
            if text.isdigit():
                highest = max(highest, int(text))
        db.execute(
            sqlite_insert(NotaCounter)
            .prefix_with("OR IGNORE")
            .values(tanggal=key, terakhir=highest)
        )
        counter = db.get(NotaCounter, key)
    counter.terakhir += 1
    db.flush()
    return str(counter.terakhir)


def allocate_device_nota(
    db: Session, *, device_id: str, day: date, prefix: str
) -> str:
    """Nomor nota berawalan perangkat, mis. `KSR7X2Q-20261103-0001` (K-12).

    Dipanggil di dalam transaksi tulis sehingga counter tidak balapan.
    """
    key_day = f"{day:%Y%m%d}"
    safe_prefix = "".join(
        char for char in (prefix or "DEV").upper() if char.isalnum()
    )[:8] or "DEV"
    row = db.get(DeviceNotaCounter, (device_id, key_day))
    if row is None:
        pattern = f"{safe_prefix}-{key_day}-%"
        highest = 0
        for nota in db.scalars(
            select(ServiceRecord.no_nota).where(
                ServiceRecord.no_nota.like(pattern)
            )
        ).all():
            suffix = str(nota or "").rsplit("-", 1)[-1]
            if suffix.isdigit():
                highest = max(highest, int(suffix))
        row = DeviceNotaCounter(
            device_id=device_id, tanggal=key_day, terakhir=highest
        )
        db.add(row)
        db.flush()
    row.terakhir += 1
    db.flush()
    return f"{safe_prefix}-{key_day}-{row.terakhir:04d}"


def allocate_nota(db: Session, day: date) -> str:
    """Nomor nota berikutnya dari counter harian yang atomik.

    Harus dipanggil di dalam transaksi tulis (lihat `begin_immediate`).
    Counter lama diinisialisasi dari nota tertinggi yang sudah ada.
    """
    key = f"{day:%Y%m%d}"
    prefix = f"INV-{key}-"
    counter = db.get(NotaCounter, key)
    if counter is None:
        highest = 0
        for nota in nota_prefix_exists(db, prefix):
            suffix = nota[len(prefix):]
            if suffix.isdigit():
                highest = max(highest, int(suffix))
        db.execute(
            sqlite_insert(NotaCounter)
            .prefix_with("OR IGNORE")
            .values(tanggal=key, terakhir=highest)
        )
        counter = db.get(NotaCounter, key)
    counter.terakhir += 1
    db.flush()
    return f"{prefix}{counter.terakhir:04d}"
