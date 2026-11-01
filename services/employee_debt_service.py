"""Hutang/uang muka karyawan dan pemotongannya dari gaji atau komisi."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from database.models import Employee, EmployeeDebt
from services.errors import BusinessValidationError, NotFoundError
from services.utils import clean_text, money


def _clean_date(value: Any) -> date:
    if value is None or value == "":
        return date.today()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        raise BusinessValidationError("Tanggal hutang tidak valid.") from exc


def _clean_nominal(value: Any) -> Decimal:
    try:
        nominal = money(Decimal(str(value or 0)))
    except Exception as exc:
        raise BusinessValidationError("Nominal hutang tidak valid.") from exc
    if nominal <= 0:
        raise BusinessValidationError("Nominal hutang harus lebih dari 0.")
    return nominal


def _get_employee(db: Session, employee_id: int) -> Employee:
    employee = db.get(Employee, int(employee_id or 0))
    if employee is None:
        raise NotFoundError("Karyawan tidak ditemukan.")
    return employee


def serialize(debt: EmployeeDebt) -> Dict[str, Any]:
    nominal = money(debt.nominal)
    terbayar = money(debt.terbayar)
    sisa = money(max(Decimal("0.00"), nominal - terbayar))
    return {
        "id": debt.id,
        "employee_id": debt.employee_id,
        "nama_karyawan": (
            debt.employee.nama if debt.employee is not None else debt.nama_karyawan
        ),
        "tanggal": debt.tanggal,
        "nominal": nominal,
        "terbayar": terbayar,
        "sisa": sisa,
        "keterangan": debt.keterangan,
        "lunas": sisa <= 0,
    }


def list_debts(
    db: Session,
    employee_id: Optional[int] = None,
    outstanding_only: bool = False,
) -> List[EmployeeDebt]:
    statement = (
        select(EmployeeDebt)
        .options(joinedload(EmployeeDebt.employee))
        .order_by(EmployeeDebt.tanggal.desc(), EmployeeDebt.id.desc())
    )
    if employee_id:
        statement = statement.where(EmployeeDebt.employee_id == int(employee_id))
    if outstanding_only:
        statement = statement.where(EmployeeDebt.terbayar < EmployeeDebt.nominal)
    return list(db.scalars(statement).all())


def create_debt(
    db: Session,
    employee_id: int,
    nominal: Any,
    tanggal: Any = None,
    keterangan: Optional[str] = None,
) -> EmployeeDebt:
    employee = _get_employee(db, employee_id)
    debt = EmployeeDebt(
        employee_id=employee.id,
        nama_karyawan=employee.nama,
        tanggal=_clean_date(tanggal),
        nominal=_clean_nominal(nominal),
        terbayar=Decimal("0.00"),
        keterangan=clean_text(keterangan, max_length=500) or None,
    )
    db.add(debt)
    db.commit()
    db.refresh(debt)
    return debt


def get_debt(db: Session, debt_id: int) -> EmployeeDebt:
    debt = db.get(EmployeeDebt, debt_id)
    if debt is None:
        raise NotFoundError("Hutang karyawan tidak ditemukan.")
    return debt


def update_debt(db: Session, debt_id: int, **values: Any) -> EmployeeDebt:
    debt = get_debt(db, debt_id)
    if "employee_id" in values and values["employee_id"] is not None:
        employee = _get_employee(db, values["employee_id"])
        debt.employee_id = employee.id
        debt.nama_karyawan = employee.nama
    if "tanggal" in values:
        if values["tanggal"] is None:
            raise BusinessValidationError("Tanggal hutang tidak boleh kosong.")
        debt.tanggal = _clean_date(values["tanggal"])
    if "nominal" in values:
        if values["nominal"] is None:
            raise BusinessValidationError("Nominal hutang tidak boleh kosong.")
        nominal = _clean_nominal(values["nominal"])
        if nominal < Decimal(debt.terbayar or 0):
            raise BusinessValidationError(
                "Nominal hutang tidak boleh lebih kecil dari yang sudah dipotong."
            )
        debt.nominal = nominal
    if "keterangan" in values:
        debt.keterangan = clean_text(values["keterangan"], max_length=500) or None
    db.commit()
    db.refresh(debt)
    return debt


def delete_debt(db: Session, debt_id: int) -> None:
    debt = get_debt(db, debt_id)
    if Decimal(debt.terbayar or 0) > 0:
        raise BusinessValidationError(
            "Hutang yang sudah dipotong tidak bisa dihapus."
        )
    db.delete(debt)
    db.commit()


def outstanding_by_employee(db: Session) -> Dict[int, Decimal]:
    result: Dict[int, Decimal] = {}
    for debt in list_debts(db, outstanding_only=True):
        if debt.employee_id is None:
            continue
        sisa = Decimal(debt.nominal or 0) - Decimal(debt.terbayar or 0)
        result[debt.employee_id] = result.get(debt.employee_id, Decimal("0.00")) + sisa
    return {key: money(value) for key, value in result.items()}


def settle_debts(
    db: Session, employee_id: int, amount: Any
) -> Decimal:
    remaining = money(Decimal(str(amount or 0)))
    if remaining <= 0:
        return money(0)
    applied = Decimal("0.00")
    debts = db.scalars(
        select(EmployeeDebt)
        .where(
            EmployeeDebt.employee_id == employee_id,
            EmployeeDebt.terbayar < EmployeeDebt.nominal,
        )
        .order_by(EmployeeDebt.tanggal.asc(), EmployeeDebt.id.asc())
    ).all()
    for debt in debts:
        if remaining <= 0:
            break
        sisa = Decimal(debt.nominal or 0) - Decimal(debt.terbayar or 0)
        if sisa <= 0:
            continue
        used = min(sisa, remaining)
        debt.terbayar = money(Decimal(debt.terbayar or 0) + used)
        applied += used
        remaining -= used
    db.flush()
    return money(applied)
