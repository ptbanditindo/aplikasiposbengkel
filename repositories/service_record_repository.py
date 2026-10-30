"""Repository transaksi servis & notanya."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from database.models import Customer, ServiceRecord, VehicleOrUnit


def get_record(db: Session, record_id: int) -> Optional[ServiceRecord]:
    return db.get(ServiceRecord, record_id)


def list_records(db: Session, query: str = "", limit: int = 200) -> List[ServiceRecord]:
    statement = (
        select(ServiceRecord)
        .join(VehicleOrUnit, ServiceRecord.unit_id == VehicleOrUnit.id)
        .join(Customer, VehicleOrUnit.customer_id == Customer.id)
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
        .order_by(ServiceRecord.waktu_service.desc(), ServiceRecord.id.desc())
    )
    return list(db.scalars(statement).all())


def all_records(db: Session) -> List[ServiceRecord]:
    statement = select(ServiceRecord).order_by(
        ServiceRecord.waktu_service.desc(), ServiceRecord.id.desc()
    )
    return list(db.scalars(statement).all())


def nota_prefix_exists(db: Session, prefix: str) -> List[str]:
    statement = select(ServiceRecord.no_nota).where(ServiceRecord.no_nota.like(f"{prefix}%"))
    return list(db.scalars(statement).all())
