"""Karyawan, penugasan nota, performa, dan komisi per nota."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from database.models import (
    Employee,
    ServiceRecord,
    ServiceRecordCommission,
    ServiceRecordMechanic,
    VehicleOrUnit,
)
from services.errors import BusinessValidationError, ConflictError, NotFoundError
from services.utils import clean_text, money

PERAN_VALUES = {"MEKANIK", "KASIR", "KEDUANYA"}
MODE_VALUES = {"PERSEN", "NOMINAL"}
BASIS_VALUES = {"BARANG", "JASA", "KEDUANYA"}


def _clean_employee(
    nama: str,
    peran: str,
    nomor_hp: Optional[str],
    catatan: Optional[str],
    komisi_mode: str,
    komisi_basis: str,
    komisi_nilai: Any,
    jenis_imbalan: str = "KOMISI",
    gaji_bulanan: Any = 0,
) -> Dict[str, Any]:
    clean_nama = clean_text(nama, max_length=255, allow_newlines=False)
    if len(clean_nama) < 2:
        raise BusinessValidationError("Nama karyawan minimal 2 karakter.")
    clean_peran = (peran or "MEKANIK").strip().upper()
    if clean_peran not in PERAN_VALUES:
        raise BusinessValidationError("Peran karyawan harus MEKANIK, KASIR, atau KEDUANYA.")
    clean_mode = (komisi_mode or "PERSEN").strip().upper()
    if clean_mode not in MODE_VALUES:
        raise BusinessValidationError("Mode komisi harus PERSEN atau NOMINAL.")
    clean_basis = (komisi_basis or "KEDUANYA").strip().upper()
    if clean_basis not in BASIS_VALUES:
        raise BusinessValidationError("Basis komisi harus BARANG, JASA, atau KEDUANYA.")
    try:
        nilai = money(Decimal(str(komisi_nilai or 0)))
    except Exception as exc:
        raise BusinessValidationError("Nilai komisi tidak valid.") from exc
    if nilai < 0:
        raise BusinessValidationError("Nilai komisi tidak boleh negatif.")
    if clean_mode == "PERSEN" and nilai > 100:
        raise BusinessValidationError("Persentase komisi maksimal 100.")
    clean_imbalan = (jenis_imbalan or "KOMISI").strip().upper()
    if clean_imbalan not in {"KOMISI", "GAJI", "KOMISI_GAJI"}:
        raise BusinessValidationError(
            "Jenis imbalan harus KOMISI, GAJI, atau KOMISI_GAJI."
        )
    try:
        gaji = money(Decimal(str(gaji_bulanan or 0)))
    except Exception as exc:
        raise BusinessValidationError("Gaji bulanan tidak valid.") from exc
    if gaji < 0:
        raise BusinessValidationError("Gaji bulanan tidak boleh negatif.")
    return {
        "nama": clean_nama,
        "peran": clean_peran,
        "nomor_hp": clean_text(nomor_hp, max_length=64, allow_newlines=False) or "",
        "catatan": clean_text(catatan, max_length=500) or None,
        "komisi_mode": clean_mode,
        "komisi_basis": clean_basis,
        "komisi_nilai": nilai,
        "jenis_imbalan": clean_imbalan,
        "gaji_bulanan": gaji,
    }


def serialize(employee: Employee) -> Dict[str, Any]:
    return {
        "id": employee.id,
        "nama": employee.nama,
        "peran": employee.peran,
        "aktif": bool(employee.aktif),
        "nomor_hp": employee.nomor_hp,
        "catatan": employee.catatan,
        "komisi_mode": employee.komisi_mode,
        "komisi_basis": employee.komisi_basis,
        "komisi_nilai": employee.komisi_nilai,
        "jenis_imbalan": employee.jenis_imbalan,
        "gaji_bulanan": employee.gaji_bulanan,
    }


def list_employees(db: Session, active_only: bool = False) -> List[Employee]:
    statement = select(Employee).order_by(Employee.nama.asc(), Employee.id.asc())
    if active_only:
        statement = statement.where(Employee.aktif.is_(True))
    return list(db.scalars(statement).all())


def get_employee(db: Session, employee_id: int) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise NotFoundError("Karyawan tidak ditemukan.")
    return employee


def create_employee(
    db: Session,
    nama: str,
    peran: str = "MEKANIK",
    nomor_hp: Optional[str] = None,
    catatan: Optional[str] = None,
    aktif: bool = True,
    komisi_mode: str = "PERSEN",
    komisi_basis: str = "KEDUANYA",
    komisi_nilai: Any = 0,
    jenis_imbalan: str = "KOMISI",
    gaji_bulanan: Any = 0,
) -> Employee:
    clean = _clean_employee(
        nama, peran, nomor_hp, catatan, komisi_mode, komisi_basis, komisi_nilai,
        jenis_imbalan, gaji_bulanan,
    )
    employee = Employee(**clean, aktif=bool(aktif))
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


def update_employee(db: Session, employee_id: int, **values: Any) -> Employee:
    employee = get_employee(db, employee_id)
    clean = _clean_employee(
        values.get("nama", employee.nama),
        values.get("peran", employee.peran),
        values.get("nomor_hp", employee.nomor_hp),
        values.get("catatan", employee.catatan),
        values.get("komisi_mode", employee.komisi_mode),
        values.get("komisi_basis", employee.komisi_basis),
        values.get("komisi_nilai", employee.komisi_nilai),
        values.get("jenis_imbalan", employee.jenis_imbalan),
        values.get("gaji_bulanan", employee.gaji_bulanan),
    )
    for key, value in clean.items():
        setattr(employee, key, value)
    if "aktif" in values and values["aktif"] is not None:
        employee.aktif = bool(values["aktif"])
    db.commit()
    db.refresh(employee)
    return employee


def delete_employee(db: Session, employee_id: int) -> None:
    employee = get_employee(db, employee_id)
    db.delete(employee)
    db.commit()


def validate_assignment(
    db: Session,
    cashier_employee_id: Optional[int],
    mechanic_ids: Optional[Iterable[int]],
) -> tuple[Optional[Employee], List[Employee]]:
    cashier = None
    if cashier_employee_id:
        cashier = db.get(Employee, int(cashier_employee_id))
        if cashier is None or not cashier.aktif:
            raise BusinessValidationError("Kasir tidak ditemukan atau nonaktif.")
        if cashier.peran not in {"KASIR", "KEDUANYA"}:
            raise BusinessValidationError("Karyawan yang dipilih bukan kasir.")
    mechanics: List[Employee] = []
    seen: set[int] = set()
    for raw in mechanic_ids or []:
        employee_id = int(raw)
        if employee_id in seen:
            continue
        seen.add(employee_id)
        employee = db.get(Employee, employee_id)
        if employee is None or not employee.aktif:
            raise BusinessValidationError("Mekanik tidak ditemukan atau nonaktif.")
        if employee.peran not in {"MEKANIK", "KEDUANYA"}:
            raise BusinessValidationError("Karyawan yang dipilih bukan mekanik.")
        mechanics.append(employee)
    return cashier, mechanics


def _record_statement(start: Optional[datetime], end: Optional[datetime]):
    statement = (
        select(ServiceRecord)
        .options(
            joinedload(ServiceRecord.unit).joinedload(VehicleOrUnit.customer),
            selectinload(ServiceRecord.jobs),
            selectinload(ServiceRecord.parts),
            selectinload(ServiceRecord.mechanics).joinedload(
                ServiceRecordMechanic.employee
            ),
            selectinload(ServiceRecord.commissions),
        )
        .where(ServiceRecord.status == "NORMAL")
    )
    if start is not None:
        statement = statement.where(ServiceRecord.waktu_service >= start)
    if end is not None:
        statement = statement.where(ServiceRecord.waktu_service < end)
    return statement


def _employee_records(
    db: Session,
    employee: Employee,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> List[ServiceRecord]:
    start_at = datetime.combine(start, time.min) if start else None
    end_at = (
        datetime.combine(end + timedelta(days=1), time.min) if end else None
    )
    records: Dict[int, ServiceRecord] = {}
    if employee.peran in {"MEKANIK", "KEDUANYA"}:
        rows = db.scalars(
            _record_statement(start_at, end_at)
            .join(
                ServiceRecordMechanic,
                ServiceRecordMechanic.service_record_id == ServiceRecord.id,
            )
            .where(ServiceRecordMechanic.employee_id == employee.id)
        ).unique().all()
        for record in rows:
            records[record.id] = record
    if employee.peran in {"KASIR", "KEDUANYA"}:
        rows = db.scalars(
            _record_statement(start_at, end_at).where(
                ServiceRecord.cashier_employee_id == employee.id
            )
        ).unique().all()
        for record in rows:
            records[record.id] = record
    return sorted(records.values(), key=lambda row: (row.waktu_service, row.id), reverse=True)


def _basis_amount(record: ServiceRecord, basis: str) -> Decimal:
    jasa = Decimal(record.biaya_jasa or 0) - Decimal(record.total_retur_jasa or 0)
    part = Decimal(record.total_part or 0) - Decimal(record.total_retur_part or 0)
    if basis == "BARANG":
        return money(part)
    if basis == "JASA":
        return money(jasa)
    return money(jasa + part)


def _commission_for(
    db: Session, employee: Employee, record: ServiceRecord
) -> Decimal:
    if (employee.jenis_imbalan or "KOMISI") == "GAJI":
        return money(0)
    override = next(
        (
            row
            for row in record.commissions
            if row.employee_id == employee.id
        ),
        None,
    )
    if override is not None:
        return money(override.nominal)
    mechanic_ids = [row.employee_id for row in record.mechanics]
    if employee.id in mechanic_ids:
        share = Decimal("1") / Decimal(max(1, len(mechanic_ids)))
        if record.cashier_employee_id == employee.id:
            share = Decimal("1")
    elif record.cashier_employee_id == employee.id:
        share = Decimal("1")
    else:
        return money(0)
    basis = _basis_amount(record, employee.komisi_basis)
    nilai = Decimal(employee.komisi_nilai or 0)
    if employee.komisi_mode == "PERSEN":
        amount = basis * nilai / Decimal("100")
    else:
        amount = nilai
    return money(amount * share)


def record_commission(db: Session, record: ServiceRecord) -> Decimal:
    """Total komisi seluruh karyawan yang terlibat pada satu nota."""
    participants: Dict[int, Employee] = {}
    for link in record.mechanics:
        if link.employee is not None:
            participants[link.employee_id] = link.employee
    if record.cashier_employee is not None:
        participants[record.cashier_employee_id] = record.cashier_employee
    total = Decimal("0.00")
    for employee in participants.values():
        total += _commission_for(db, employee, record)
    return money(total)


def commission_total(
    db: Session, records: Iterable[ServiceRecord]
) -> Decimal:
    total = Decimal("0.00")
    for record in records:
        if (record.status or "NORMAL") == "VOID":
            continue
        total += record_commission(db, record)
    return money(total)


def performance(
    db: Session,
    employee_id: int,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> Dict[str, Any]:
    employee = get_employee(db, employee_id)
    records = _employee_records(db, employee, start, end)
    jasa_qty = 0
    part_qty = 0
    total_nilai = Decimal("0.00")
    customers: set[int] = set()
    komisi_total = Decimal("0.00")
    riwayat = []
    for record in records:
        jasa_qty += sum(int(job.jumlah or 0) for job in record.jobs)
        part_qty += sum(int(part.jumlah or 0) for part in record.parts)
        net = Decimal(record.total_servis or 0) - Decimal(record.total_retur or 0)
        total_nilai += net
        customers.add(record.unit.customer_id)
        komisi = _commission_for(db, employee, record)
        komisi_total += komisi
        riwayat.append(
            {
                "record_id": record.id,
                "no_nota": record.no_nota,
                "waktu_service": record.waktu_service,
                "customer_nama": record.unit.customer.nama,
                "unit_deskripsi": record.unit.nopol
                or record.unit.label_radiator
                or "-",
                "total_servis": money(net),
                "komisi": komisi,
            }
        )
    return {
        "employee": employee,
        "start": start,
        "end": end,
        "jumlah_nota": len(records),
        "jumlah_jasa": jasa_qty,
        "jumlah_part": part_qty,
        "total_nilai": money(total_nilai),
        "pelanggan_unik": len(customers),
        "komisi_total": money(komisi_total),
        "riwayat": riwayat,
    }


def set_commission_override(
    db: Session,
    employee_id: int,
    record_id: int,
    nominal: Any,
) -> ServiceRecordCommission:
    employee = get_employee(db, employee_id)
    record = db.get(ServiceRecord, record_id)
    if record is None:
        raise NotFoundError("Nota tidak ditemukan.")
    participates = record.cashier_employee_id == employee.id or any(
        row.employee_id == employee.id for row in record.mechanics
    )
    if not participates:
        raise BusinessValidationError("Karyawan tidak terlibat pada nota ini.")
    try:
        amount = money(Decimal(str(nominal or 0)))
    except Exception as exc:
        raise BusinessValidationError("Nominal komisi tidak valid.") from exc
    if amount < 0:
        raise BusinessValidationError("Nominal komisi tidak boleh negatif.")
    row = db.scalar(
        select(ServiceRecordCommission).where(
            ServiceRecordCommission.service_record_id == record_id,
            ServiceRecordCommission.employee_id == employee.id,
        )
    )
    if row is None:
        row = ServiceRecordCommission(
            service_record_id=record_id,
            employee_id=employee.id,
            nominal=amount,
        )
        db.add(row)
    else:
        row.nominal = amount
    db.commit()
    db.refresh(row)
    return row
