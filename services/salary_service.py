"""Pencatatan pembayaran gaji aktual per karyawan dan periode."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from database.models import Employee, SalaryPayment
from services import employee_debt_service, employee_service
from services.errors import BusinessValidationError, ConflictError, NotFoundError
from services.utils import clean_text, money

METODE_VALUES = {"CASH", "TRANSFER"}


def _clean_period(value: Any) -> str:
    text = clean_text(value, max_length=7, allow_newlines=False)
    parts = text.split("-")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        raise BusinessValidationError("Periode gaji harus berformat YYYY-MM.")
    year = int(parts[0])
    month = int(parts[1])
    if year < 2000 or year > 2100 or month < 1 or month > 12:
        raise BusinessValidationError("Periode gaji tidak valid.")
    return f"{year:04d}-{month:02d}"


def _clean_date(value: Any) -> date:
    if value is None or value == "":
        return date.today()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        raise BusinessValidationError("Tanggal pembayaran gaji tidak valid.") from exc


def _clean_metode(value: Any) -> str:
    text = (value or "CASH").strip().upper()
    if text not in METODE_VALUES:
        raise BusinessValidationError("Metode gaji harus CASH atau TRANSFER.")
    return text


def _clean_nominal(value: Any) -> Decimal:
    try:
        nominal = money(Decimal(str(value or 0)))
    except Exception as exc:
        raise BusinessValidationError("Nominal gaji tidak valid.") from exc
    if nominal <= 0:
        raise BusinessValidationError("Nominal gaji harus lebih dari 0.")
    return nominal


def serialize(payment: SalaryPayment) -> Dict[str, Any]:
    nama = payment.employee.nama if payment.employee is not None else payment.nama_karyawan
    return {
        "id": payment.id,
        "employee_id": payment.employee_id,
        "nama_karyawan": nama,
        "periode": payment.periode,
        "tanggal": payment.tanggal,
        "cycle_start": payment.cycle_start,
        "nominal": payment.nominal,
        "potongan_hutang": payment.potongan_hutang,
        "bonus": payment.bonus,
        "bonus_keterangan": payment.bonus_keterangan,
        "cicilan_hutang": payment.cicilan_hutang,
        "metode": payment.metode,
        "catatan": payment.catatan,
        "created_at": payment.created_at,
    }


def list_payments(
    db: Session,
    start: Optional[date] = None,
    end: Optional[date] = None,
    employee_id: Optional[int] = None,
    limit: int = 300,
) -> List[SalaryPayment]:
    statement = (
        select(SalaryPayment)
        .options(joinedload(SalaryPayment.employee))
        .order_by(SalaryPayment.tanggal.desc(), SalaryPayment.id.desc())
        .limit(max(1, min(int(limit or 300), 1000)))
    )
    if start is not None:
        statement = statement.where(SalaryPayment.tanggal >= start)
    if end is not None:
        statement = statement.where(SalaryPayment.tanggal <= end)
    if employee_id:
        statement = statement.where(SalaryPayment.employee_id == int(employee_id))
    return list(db.scalars(statement).all())


def get_payment(db: Session, payment_id: int) -> SalaryPayment:
    payment = db.get(SalaryPayment, payment_id)
    if payment is None:
        raise NotFoundError("Pembayaran gaji tidak ditemukan.")
    return payment


def _get_employee(db: Session, employee_id: int) -> Employee:
    employee = db.get(Employee, int(employee_id or 0))
    if employee is None:
        raise NotFoundError("Karyawan tidak ditemukan.")
    return employee


def create_payment(
    db: Session,
    employee_id: int,
    periode: Any,
    nominal: Any,
    tanggal: Any = None,
    metode: Any = "CASH",
    catatan: Optional[str] = None,
    potongan_hutang: Any = 0,
    bonus: Any = 0,
    bonus_keterangan: Optional[str] = None,
    cicilan_hutang: Any = 0,
) -> SalaryPayment:
    employee = _get_employee(db, employee_id)
    clean_period = _clean_period(periode)
    pay_date = _clean_date(tanggal)
    cycle_start = employee_service.payroll_cycle_start(employee, pay_date)
    existing = db.scalar(
        select(SalaryPayment).where(
            SalaryPayment.employee_id == employee.id,
            SalaryPayment.cycle_start == cycle_start,
        )
    )
    if existing is not None:
        raise ConflictError(
            f"Gaji {employee.nama} untuk siklus {cycle_start.isoformat()} sudah dicatat."
        )
    try:
        potongan = money(Decimal(str(potongan_hutang or 0)))
    except Exception as exc:
        raise BusinessValidationError("Potongan hutang tidak valid.") from exc
    if potongan < 0:
        raise BusinessValidationError("Potongan hutang tidak boleh negatif.")
    outstanding = employee_debt_service.outstanding_by_employee(db).get(
        employee.id, Decimal("0.00")
    )
    try:
        cicilan = money(Decimal(str(cicilan_hutang or 0)))
    except Exception as exc:
        raise BusinessValidationError("Nominal cicilan hutang tidak valid.") from exc
    if cicilan < 0:
        raise BusinessValidationError("Cicilan hutang tidak boleh negatif.")
    if potongan + cicilan > outstanding:
        raise BusinessValidationError(
            "Potongan dan cicilan hutang melebihi sisa hutang karyawan."
        )
    try:
        clean_bonus = money(Decimal(str(bonus or 0)))
    except Exception as exc:
        raise BusinessValidationError("Nominal bonus tidak valid.") from exc
    if clean_bonus < 0:
        raise BusinessValidationError("Nominal bonus tidak boleh negatif.")
    payment = SalaryPayment(
        employee_id=employee.id,
        nama_karyawan=employee.nama,
        periode=clean_period,
        tanggal=pay_date,
        cycle_start=cycle_start,
        nominal=_clean_nominal(nominal),
        potongan_hutang=potongan,
        bonus=clean_bonus,
        bonus_keterangan=clean_text(
            bonus_keterangan, max_length=255, allow_newlines=False
        )
        or "",
        cicilan_hutang=cicilan,
        metode=_clean_metode(metode),
        catatan=clean_text(catatan, max_length=500) or None,
    )
    db.add(payment)
    db.flush()
    if potongan > 0:
        applied = employee_debt_service.settle_debts(
            db, employee.id, potongan
        )
        payment.potongan_hutang = applied
    if cicilan > 0:
        applied_cicilan = employee_debt_service.settle_debts(
            db, employee.id, cicilan
        )
        payment.cicilan_hutang = applied_cicilan
    db.commit()
    db.refresh(payment)
    return payment


def update_payment(db: Session, payment_id: int, **values: Any) -> SalaryPayment:
    payment = get_payment(db, payment_id)
    if "employee_id" in values and values["employee_id"] is not None:
        employee = _get_employee(db, values["employee_id"])
        payment.employee_id = employee.id
        payment.nama_karyawan = employee.nama
    if "periode" in values:
        if values["periode"] is None:
            raise BusinessValidationError("Periode gaji tidak boleh kosong.")
        payment.periode = _clean_period(values["periode"])
    if "tanggal" in values:
        if values["tanggal"] is None:
            raise BusinessValidationError("Tanggal gaji tidak boleh kosong.")
        payment.tanggal = _clean_date(values["tanggal"])
    if "nominal" in values:
        if values["nominal"] is None:
            raise BusinessValidationError("Nominal gaji tidak boleh kosong.")
        payment.nominal = _clean_nominal(values["nominal"])
    if "metode" in values:
        if values["metode"] is None:
            raise BusinessValidationError("Metode gaji tidak boleh kosong.")
        payment.metode = _clean_metode(values["metode"])
    if "catatan" in values:
        payment.catatan = clean_text(values["catatan"], max_length=500) or None
    if "employee_id" in values or "tanggal" in values:
        employee = db.get(Employee, payment.employee_id) if payment.employee_id else None
        if employee is not None:
            payment.cycle_start = employee_service.payroll_cycle_start(
                employee, payment.tanggal
            )
    duplicate = None
    if payment.employee_id and payment.cycle_start is not None:
        duplicate = db.scalar(
            select(SalaryPayment).where(
                SalaryPayment.employee_id == payment.employee_id,
                SalaryPayment.cycle_start == payment.cycle_start,
                SalaryPayment.id != payment.id,
            )
        )
    if duplicate is not None:
        raise ConflictError(
            f"Gaji karyawan ini untuk siklus {payment.cycle_start.isoformat()} sudah dicatat."
        )
    db.commit()
    db.refresh(payment)
    return payment


def delete_payment(db: Session, payment_id: int) -> None:
    payment = get_payment(db, payment_id)
    db.delete(payment)
    db.commit()
