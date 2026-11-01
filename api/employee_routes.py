"""Endpoint karyawan, performa, dan komisi per nota."""
from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from api.deps import require_auth
from api.schemas import (
    EmployeeCommissionIn,
    EmployeeCreate,
    EmployeeOut,
    EmployeePerformanceOut,
    EmployeeUpdate,
    PayrollSummaryOut,
    SalaryPaymentCreate,
    SalaryPaymentOut,
    SalaryPaymentUpdate,
)
from database.session import get_db
from services import employee_service, salary_service

router = APIRouter(
    tags=["Karyawan"], dependencies=[Depends(require_auth)]
)


def _out(employee) -> EmployeeOut:
    return EmployeeOut(**employee_service.serialize(employee))


@router.get("/employees", response_model=List[EmployeeOut])
def list_employees(
    active_only: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    return [
        _out(employee)
        for employee in employee_service.list_employees(db, active_only)
    ]


@router.post("/employees", response_model=EmployeeOut, status_code=201)
def create_employee(payload: EmployeeCreate, db: Session = Depends(get_db)):
    employee = employee_service.create_employee(
        db,
        payload.nama,
        peran=payload.peran,
        nomor_hp=payload.nomor_hp,
        catatan=payload.catatan,
        aktif=payload.aktif,
        komisi_mode=payload.komisi_mode,
        komisi_basis=payload.komisi_basis,
        komisi_nilai=payload.komisi_nilai,
        jenis_imbalan=payload.jenis_imbalan,
        gaji_bulanan=payload.gaji_bulanan,
        komisi_barang_nilai=payload.komisi_barang_nilai,
        komisi_jasa_nilai=payload.komisi_jasa_nilai,
        payroll_period=payload.payroll_period,
        payroll_tanggal=payload.payroll_tanggal,
    )
    return _out(employee)


@router.put("/employees/{employee_id}", response_model=EmployeeOut)
def update_employee(
    employee_id: int,
    payload: EmployeeUpdate,
    db: Session = Depends(get_db),
):
    employee = employee_service.update_employee(
        db, employee_id, **payload.model_dump(exclude_unset=True)
    )
    return _out(employee)


@router.delete("/employees/{employee_id}", status_code=204)
def delete_employee(employee_id: int, db: Session = Depends(get_db)):
    employee_service.delete_employee(db, employee_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/payroll/summary", response_model=PayrollSummaryOut)
def payroll_summary(
    today: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
):
    return PayrollSummaryOut(**employee_service.payroll_summary(db, today))


@router.get("/salary-payments", response_model=List[SalaryPaymentOut])
def list_salary_payments(
    start: Optional[date] = Query(default=None),
    end: Optional[date] = Query(default=None),
    employee_id: Optional[int] = Query(default=None),
    limit: int = Query(default=300, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return [
        SalaryPaymentOut(**salary_service.serialize(payment))
        for payment in salary_service.list_payments(
            db, start=start, end=end, employee_id=employee_id, limit=limit
        )
    ]


@router.post("/salary-payments", response_model=SalaryPaymentOut, status_code=201)
def create_salary_payment(
    payload: SalaryPaymentCreate, db: Session = Depends(get_db)
):
    payment = salary_service.create_payment(
        db,
        payload.employee_id,
        payload.periode,
        payload.nominal,
        tanggal=payload.tanggal,
        metode=payload.metode,
        catatan=payload.catatan,
    )
    return SalaryPaymentOut(**salary_service.serialize(payment))


@router.put("/salary-payments/{payment_id}", response_model=SalaryPaymentOut)
def update_salary_payment(
    payment_id: int,
    payload: SalaryPaymentUpdate,
    db: Session = Depends(get_db),
):
    payment = salary_service.update_payment(
        db, payment_id, **payload.model_dump(exclude_unset=True)
    )
    return SalaryPaymentOut(**salary_service.serialize(payment))


@router.delete("/salary-payments/{payment_id}", status_code=204)
def delete_salary_payment(payment_id: int, db: Session = Depends(get_db)):
    salary_service.delete_payment(db, payment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/employees/{employee_id}/performance",
    response_model=EmployeePerformanceOut,
)
def employee_performance(
    employee_id: int,
    start: Optional[date] = Query(default=None),
    end: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
):
    data = employee_service.performance(db, employee_id, start, end)
    data["employee"] = employee_service.serialize(data["employee"])
    return EmployeePerformanceOut(**data)


@router.put(
    "/employees/{employee_id}/commissions/{record_id}",
    response_model=EmployeePerformanceOut,
)
def set_employee_commission(
    employee_id: int,
    record_id: int,
    payload: EmployeeCommissionIn,
    db: Session = Depends(get_db),
):
    employee_service.set_commission_override(
        db, employee_id, record_id, payload.nominal
    )
    data = employee_service.performance(db, employee_id)
    data["employee"] = employee_service.serialize(data["employee"])
    return EmployeePerformanceOut(**data)
