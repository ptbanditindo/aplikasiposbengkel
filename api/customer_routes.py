"""Endpoint pelanggan & unit servis."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.deps import require_auth
from api.schemas import (
    CustomerContactIn,
    CustomerCreate,
    CustomerOut,
    CustomerOverviewOut,
    UnitCreate,
    UnitOut,
    WaLinkOut,
)
from database.models import Customer, VehicleOrUnit
from database.session import get_db
from services import contact_gate_service, customer_service
from services.auth_service import Operator
from services.customer_service import describe_unit
from services.errors import BusinessValidationError, ConflictError, NotFoundError
from services.utils import normalize_whatsapp

router = APIRouter(
    tags=["Pelanggan & Unit"], dependencies=[Depends(require_auth)]
)


def _unit_out(unit: VehicleOrUnit) -> UnitOut:
    data = UnitOut.model_validate(unit)
    data.deskripsi = describe_unit(unit)
    return data


@router.get("/customers/search", response_model=List[CustomerOut])
def search_customers(
    q: str = Query(default="", max_length=100),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return [
        CustomerOut.model_validate(customer)
        for customer in customer_service.search_customers(db, q, limit)
    ]


@router.get("/customers", response_model=List[CustomerOut])
def list_customers(
    q: str = Query(default="", max_length=100),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return [
        CustomerOut.model_validate(customer)
        for customer in customer_service.search_customers(db, q, limit)
    ]


@router.post("/customers", response_model=CustomerOut, status_code=201)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    customer = customer_service.create_customer(
        db, payload.nama, payload.nomor_hp, payload.alamat
    )
    return CustomerOut.model_validate(customer)


@router.get("/customers/overview", response_model=List[CustomerOverviewOut])
def customer_overview(
    q: str = Query(default="", max_length=100),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    customers = customer_service.list_customers_with_units(db, q, limit)
    result = []
    for customer in customers:
        units = sorted(
            (
                unit
                for unit in customer.units
                if unit.archived_at is None and unit.unit_type != "SPAREPART"
            ),
            key=lambda unit: (unit.created_at, unit.id),
            reverse=True,
        )
        unit_items = [_unit_out(unit) for unit in units]
        result.append(
            CustomerOverviewOut(
                id=customer.id,
                sync_id=customer.sync_id,
                nama=customer.nama,
                nomor_hp=customer.nomor_hp,
                alamat=customer.alamat,
                created_at=customer.created_at,
                total_unit=len(unit_items),
                total_mobil=sum(
                    1 for unit in unit_items if unit.unit_type == "MOBIL"
                ),
                total_radiator=sum(
                    1 for unit in unit_items if unit.unit_type == "RADIATOR_ONLY"
                ),
                total_motor=sum(
                    1 for unit in unit_items if unit.unit_type == "MOTOR_LENGKAP"
                ),
                total_part_mobil=sum(
                    1 for unit in unit_items if unit.unit_type == "PART_MOBIL"
                ),
                total_part_motor=sum(
                    1 for unit in unit_items if unit.unit_type == "PART_MOTOR"
                ),
                units=unit_items,
            )
        )
    return result


@router.get("/customers/{customer_id}/units", response_model=List[UnitOut])
def list_units(customer_id: int, db: Session = Depends(get_db)):
    units = customer_service.list_units(db, customer_id)
    return [_unit_out(unit) for unit in units]


@router.delete("/units/{unit_id}", status_code=204)
def archive_unit(
    unit_id: int,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_auth),
):
    customer_service.archive_unit(db, unit_id, operator)
    return None


@router.post("/units", response_model=UnitOut, status_code=201)
def create_unit(payload: UnitCreate, db: Session = Depends(get_db)):
    unit = customer_service.create_unit(
        db,
        customer_id=payload.customer_id,
        unit_type=payload.unit_type,
        nopol=payload.nopol,
        jenis_mobil=payload.jenis_mobil,
        tahun_mobil=payload.tahun_mobil,
        tipe_radiator=payload.tipe_radiator,
        keterangan=payload.keterangan,
        nama_barang=payload.nama_barang,
        nomor_seri=payload.nomor_seri,
        kondisi=payload.kondisi,
        kendaraan_asal=payload.kendaraan_asal,
    )
    return _unit_out(unit)


@router.put("/customers/{customer_id}/contact", response_model=CustomerOut)
def update_customer_contact(
    customer_id: int,
    payload: CustomerContactIn,
    db: Session = Depends(get_db),
):
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise NotFoundError("Pelanggan tidak ditemukan.")
    if payload.wa_consent is not None:
        customer.wa_consent = bool(payload.wa_consent)
    if payload.do_not_contact is not None:
        customer.do_not_contact = bool(payload.do_not_contact)
    db.commit()
    db.refresh(customer)
    return CustomerOut.model_validate(customer)


@router.get("/customers/{customer_id}/wa-link", response_model=WaLinkOut)
def customer_wa_link(
    customer_id: int,
    jenis: str = Query(default="chat"),
    db: Session = Depends(get_db),
):
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise NotFoundError("Pelanggan tidak ditemukan.")
    allowed, reason, warning = contact_gate_service.wa_gate(
        db, customer, (jenis or "chat").strip().lower()
    )
    if not allowed:
        raise ConflictError(reason)
    digits = normalize_whatsapp(customer.nomor_hp)
    if not digits:
        raise BusinessValidationError("Nomor WhatsApp pelanggan belum valid.")
    return WaLinkOut(link="https://wa.me/" + digits, peringatan=warning)
