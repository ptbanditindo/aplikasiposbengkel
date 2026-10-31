"""Repository data pelanggan & unit servis."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from database.models import Customer, VehicleOrUnit


def search_customers(db: Session, query: str = "", limit: int = 20) -> List[Customer]:
    statement = select(Customer)
    term = (query or "").strip()
    if term:
        like = f"%{term}%"
        digits = "".join(ch for ch in term if ch.isdigit())
        conditions = [Customer.nama.ilike(like), Customer.nomor_hp.ilike(like)]
        if digits:
            conditions.append(Customer.nomor_hp.ilike(f"%{digits}%"))
        statement = statement.where(or_(*conditions))
    statement = statement.order_by(Customer.nama.asc()).limit(limit)
    return list(db.scalars(statement).all())


def list_customers_with_units(
    db: Session, query: str = "", limit: int = 100
) -> List[Customer]:
    statement = select(Customer).options(selectinload(Customer.units))
    term = (query or "").strip()
    if term:
        like = f"%{term}%"
        digits = "".join(ch for ch in term if ch.isdigit())
        conditions = [Customer.nama.ilike(like), Customer.nomor_hp.ilike(like)]
        if digits:
            conditions.append(Customer.nomor_hp.ilike(f"%{digits}%"))
        statement = statement.where(or_(*conditions))
    statement = statement.order_by(Customer.nama.asc()).limit(limit)
    return list(db.scalars(statement).all())



def get_customer(db: Session, customer_id: int) -> Optional[Customer]:
    return db.get(Customer, customer_id)


def create_customer(
    db: Session,
    nama: str,
    nomor_hp: str,
    alamat: Optional[str],
) -> Customer:
    customer = Customer(nama=nama, nomor_hp=nomor_hp, alamat=alamat)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def list_units(db: Session, customer_id: int) -> List[VehicleOrUnit]:
    statement = (
        select(VehicleOrUnit)
        .where(
            VehicleOrUnit.customer_id == customer_id,
            VehicleOrUnit.archived_at.is_(None),
        )
        .order_by(VehicleOrUnit.created_at.desc(), VehicleOrUnit.id.desc())
    )
    return list(db.scalars(statement).all())


def get_unit(db: Session, unit_id: int) -> Optional[VehicleOrUnit]:
    return db.get(VehicleOrUnit, unit_id)


def create_unit(db: Session, **values) -> VehicleOrUnit:
    unit = VehicleOrUnit(**values)
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit


def labels_with_prefix(db: Session, prefix: str) -> List[str]:
    statement = select(VehicleOrUnit.label_radiator).where(
        VehicleOrUnit.label_radiator.like(f"{prefix}%")
    )
    return [label for label in db.scalars(statement).all() if label]
