"""Karyawan, penugasan nota, performa, dan komisi per nota."""
from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from database.models import (
    Employee,
    SalaryPayment,
    ServicePart,
    ServiceRecord,
    ServiceRecordCommission,
    ServiceRecordMechanic,
    VehicleOrUnit,
)
from services import employee_debt_service
from services.errors import BusinessValidationError, ConflictError, NotFoundError
from services.utils import clean_text, format_rupiah, money

PERAN_VALUES = {"MEKANIK", "KASIR", "KEDUANYA"}
MODE_VALUES = {"PERSEN", "NOMINAL"}
BASIS_VALUES = {"BARANG", "JASA", "KEDUANYA"}
PAYROLL_VALUES = {
    "TANGGAL",
    "MINGGUAN",
    "DUA_MINGGUAN",
    "TIGA_MINGGUAN",
    "BULANAN",
}
PAYROLL_LABELS = {
    "TANGGAL": "Tanggal",
    "MINGGUAN": "Per minggu",
    "DUA_MINGGUAN": "Per 2 minggu",
    "TIGA_MINGGUAN": "Per 3 minggu",
    "BULANAN": "Bulanan",
}
HARI_LABELS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


def _clean_optional_date(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        raise BusinessValidationError("Tanggal masuk tidak valid.") from exc


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
    komisi_barang_nilai: Any = None,
    komisi_jasa_nilai: Any = None,
    payroll_period: str = "BULANAN",
    payroll_tanggal: Any = 1,
    payroll_hari: Any = 0,
    bank_nama: Optional[str] = "",
    bank_nomor: Optional[str] = "",
    bank_atas_nama: Optional[str] = "",
    tanggal_masuk: Any = None,
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

    # Nilai lama tetap dipakai untuk kompatibilitas API. Bila dua tarif baru
    # tidak dikirim, turunkan keduanya dari basis dan nilai lama.
    if komisi_barang_nilai is None and komisi_jasa_nilai is None:
        if clean_mode == "PERSEN":
            barang_nilai = nilai if clean_basis in {"BARANG", "KEDUANYA"} else Decimal("0.00")
            jasa_nilai = nilai if clean_basis in {"JASA", "KEDUANYA"} else Decimal("0.00")
        else:
            barang_nilai = nilai if clean_basis == "BARANG" else Decimal("0.00")
            jasa_nilai = nilai if clean_basis == "JASA" else Decimal("0.00")
    else:
        try:
            barang_nilai = money(Decimal(str(komisi_barang_nilai or 0)))
            jasa_nilai = money(Decimal(str(komisi_jasa_nilai or 0)))
        except Exception as exc:
            raise BusinessValidationError("Nilai komisi barang/jasa tidak valid.") from exc
    if barang_nilai < 0 or jasa_nilai < 0:
        raise BusinessValidationError("Nilai komisi tidak boleh negatif.")
    if clean_mode == "PERSEN" and (barang_nilai > 100 or jasa_nilai > 100):
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

    clean_payroll = (payroll_period or "BULANAN").strip().upper()
    if clean_payroll not in PAYROLL_VALUES:
        raise BusinessValidationError("Jadwal gajian tidak valid.")
    try:
        payroll_day = int(payroll_tanggal or 1)
    except (TypeError, ValueError) as exc:
        raise BusinessValidationError("Tanggal gajian harus berupa angka.") from exc
    if payroll_day < 1 or payroll_day > 31:
        raise BusinessValidationError("Tanggal gajian harus antara 1 dan 31.")
    try:
        payroll_weekday = int(payroll_hari or 0)
    except (TypeError, ValueError) as exc:
        raise BusinessValidationError("Hari gajian tidak valid.") from exc
    if payroll_weekday < 0 or payroll_weekday > 6:
        raise BusinessValidationError("Hari gajian harus antara Senin dan Minggu.")

    return {
        "nama": clean_nama,
        "peran": clean_peran,
        "nomor_hp": clean_text(nomor_hp, max_length=64, allow_newlines=False) or "",
        "catatan": clean_text(catatan, max_length=500) or None,
        "komisi_mode": clean_mode,
        "komisi_basis": clean_basis,
        "komisi_nilai": nilai,
        "komisi_barang_nilai": barang_nilai,
        "komisi_jasa_nilai": jasa_nilai,
        "jenis_imbalan": clean_imbalan,
        "gaji_bulanan": gaji,
        "payroll_period": clean_payroll,
        "payroll_tanggal": payroll_day,
        "payroll_hari": payroll_weekday,
        "bank_nama": clean_text(bank_nama, max_length=64, allow_newlines=False) or "",
        "bank_nomor": clean_text(bank_nomor, max_length=64, allow_newlines=False) or "",
        "bank_atas_nama": clean_text(bank_atas_nama, max_length=255, allow_newlines=False) or "",
        "tanggal_masuk": _clean_optional_date(tanggal_masuk),
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
        "komisi_barang_nilai": employee.komisi_barang_nilai,
        "komisi_jasa_nilai": employee.komisi_jasa_nilai,
        "jenis_imbalan": employee.jenis_imbalan,
        "gaji_bulanan": employee.gaji_bulanan,
        "payroll_period": employee.payroll_period,
        "payroll_tanggal": employee.payroll_tanggal,
        "payroll_hari": employee.payroll_hari,
        "payroll_label": PAYROLL_LABELS.get(employee.payroll_period, "Bulanan"),
        "bank_nama": employee.bank_nama,
        "bank_nomor": employee.bank_nomor,
        "bank_atas_nama": employee.bank_atas_nama,
        "tanggal_masuk": employee.tanggal_masuk,
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
    komisi_barang_nilai: Any = None,
    komisi_jasa_nilai: Any = None,
    payroll_period: str = "BULANAN",
    payroll_tanggal: Any = 1,
    payroll_hari: Any = 0,
    bank_nama: Optional[str] = "",
    bank_nomor: Optional[str] = "",
    bank_atas_nama: Optional[str] = "",
    tanggal_masuk: Any = None,
) -> Employee:
    clean = _clean_employee(
        nama, peran, nomor_hp, catatan, komisi_mode, komisi_basis, komisi_nilai,
        jenis_imbalan, gaji_bulanan, komisi_barang_nilai, komisi_jasa_nilai,
        payroll_period, payroll_tanggal, payroll_hari,
        bank_nama, bank_nomor, bank_atas_nama, tanggal_masuk,
    )
    employee = Employee(**clean, aktif=bool(aktif))
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


def update_employee(db: Session, employee_id: int, **values: Any) -> Employee:
    employee = get_employee(db, employee_id)
    legacy_changed = any(
        key in values
        for key in ("komisi_mode", "komisi_basis", "komisi_nilai")
    )
    if legacy_changed and "komisi_barang_nilai" not in values and "komisi_jasa_nilai" not in values:
        barang_value = None
        jasa_value = None
    else:
        barang_value = values.get("komisi_barang_nilai", employee.komisi_barang_nilai)
        jasa_value = values.get("komisi_jasa_nilai", employee.komisi_jasa_nilai)
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
        barang_value,
        jasa_value,
        values.get("payroll_period", employee.payroll_period),
        values.get("payroll_tanggal", employee.payroll_tanggal),
        values.get("payroll_hari", employee.payroll_hari),
        values.get("bank_nama", employee.bank_nama),
        values.get("bank_nomor", employee.bank_nomor),
        values.get("bank_atas_nama", employee.bank_atas_nama),
        values.get("tanggal_masuk", employee.tanggal_masuk),
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
            selectinload(ServiceRecord.parts).selectinload(ServicePart.stock_item),
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


def _commission_components(record: ServiceRecord) -> tuple[Decimal, Decimal]:
    """Nilai jasa dan margin sparepart (harga jual - modal) untuk komisi."""
    jasa = Decimal(record.biaya_jasa or 0) - Decimal(record.total_retur_jasa or 0)
    margin = Decimal("0.00")
    for part in record.parts:
        net_qty = int(part.jumlah or 0) - int(getattr(part, "jumlah_retur", 0) or 0)
        if net_qty <= 0:
            continue
        modal = part.harga_modal
        if modal is None and part.stock_item is not None:
            modal = part.stock_item.harga_modal
        if modal is None:
            continue
        margin += (Decimal(part.harga_satuan or 0) - Decimal(modal)) * net_qty
    return money(max(Decimal("0.00"), jasa)), money(margin)


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

    jasa, margin = _commission_components(record)
    barang_nilai = Decimal(employee.komisi_barang_nilai or 0)
    jasa_nilai = Decimal(employee.komisi_jasa_nilai or 0)

    if employee.komisi_mode == "PERSEN":
        # Database lama yang belum memiliki tarif terpisah tetap memakai nilai
        # tunggal sesuai basis lamanya.
        if barang_nilai == 0 and jasa_nilai == 0 and employee.komisi_nilai:
            legacy = Decimal(employee.komisi_nilai or 0)
            if employee.komisi_basis == "BARANG":
                barang_nilai = legacy
            elif employee.komisi_basis == "JASA":
                jasa_nilai = legacy
            else:
                barang_nilai = jasa_nilai = legacy
        amount = (
            margin * barang_nilai / Decimal("100")
            + jasa * jasa_nilai / Decimal("100")
        )
    else:
        if barang_nilai == 0 and jasa_nilai == 0 and employee.komisi_nilai:
            legacy = Decimal(employee.komisi_nilai or 0)
            if employee.komisi_basis == "BARANG":
                amount = legacy if margin > 0 else Decimal("0.00")
            elif employee.komisi_basis == "JASA":
                amount = legacy if jasa > 0 else Decimal("0.00")
            else:
                amount = legacy if (margin > 0 or jasa > 0) else Decimal("0.00")
        else:
            amount = (barang_nilai if margin > 0 else Decimal("0.00")) + (
                jasa_nilai if jasa > 0 else Decimal("0.00")
            )
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
    if start is None and end is None:
        today = date.today()
        last_payment = db.scalar(
            select(SalaryPayment)
            .where(SalaryPayment.employee_id == employee.id)
            .order_by(SalaryPayment.tanggal.desc(), SalaryPayment.id.desc())
        )
        if last_payment is not None:
            start = last_payment.tanggal + timedelta(days=1)
        else:
            start = payroll_cycle_start(employee, today)
            if employee.tanggal_masuk and employee.tanggal_masuk > start:
                start = employee.tanggal_masuk
        end = today
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


def records_for_range(
    db: Session, employee: Employee, start: date, end: date
) -> List[ServiceRecord]:
    return _employee_records(db, employee, start, end)


def salary_due_for_receipt(employee: Employee) -> Decimal:
    return _payroll_salary_due(employee)


def commission_breakdown(
    db: Session, employee: Employee, records: Iterable[ServiceRecord]
) -> List[Dict[str, Any]]:
    """Rincian komisi per nota untuk nota gaji karyawan."""
    rows: List[Dict[str, Any]] = []
    for record in records:
        jasa, margin = _commission_components(record)
        mechanic_ids = [row.employee_id for row in record.mechanics]
        if employee.id in mechanic_ids:
            share = Decimal("1") / Decimal(max(1, len(mechanic_ids)))
            if record.cashier_employee_id == employee.id:
                share = Decimal("1")
        elif record.cashier_employee_id == employee.id:
            share = Decimal("1")
        else:
            continue
        override = next(
            (
                row
                for row in record.commissions
                if row.employee_id == employee.id
            ),
            None,
        )
        manual = override is not None
        nominal_mode = employee.komisi_mode == "NOMINAL"
        if manual:
            total = money(override.nominal)
            goods = Decimal("0.00")
            service = Decimal("0.00")
        elif nominal_mode:
            total = _commission_for(db, employee, record)
            goods = Decimal("0.00")
            service = Decimal("0.00")
        else:
            barang_rate = Decimal(employee.komisi_barang_nilai or 0)
            jasa_rate = Decimal(employee.komisi_jasa_nilai or 0)
            goods = money(margin * barang_rate / Decimal("100") * share)
            service = money(jasa * jasa_rate / Decimal("100") * share)
            total = money(goods + service)
        parts = []
        for part in record.parts:
            net_qty = int(part.jumlah or 0) - int(
                getattr(part, "jumlah_retur", 0) or 0
            )
            if net_qty > 0:
                parts.append(f"{part.nama_part} x{net_qty}")
        jobs = [
            (job.deskripsi or "Jasa") + " x" + str(int(job.jumlah or 0))
            for job in record.jobs
        ]
        rows.append(
            {
                "no_nota": record.no_nota,
                "waktu_service": record.waktu_service,
                "customer_nama": record.unit.customer.nama,
                "unit_deskripsi": record.unit.nopol
                or record.unit.label_radiator
                or "-",
                "jasa": jasa,
                "margin": margin,
                "goods_commission": goods,
                "service_commission": service,
                "total": total,
                "manual": manual,
                "nominal_mode": nominal_mode,
                "share": share,
                "parts": parts,
                "jobs": jobs,
            }
        )
    return rows


def payroll_cycle_start(employee: Employee, today: date) -> date:
    period = employee.payroll_period or "BULANAN"
    if period == "MINGGUAN":
        return today - timedelta(days=6)
    if period == "DUA_MINGGUAN":
        return today - timedelta(days=13)
    if period == "TIGA_MINGGUAN":
        return today - timedelta(days=20)
    return today.replace(day=1)


def _payroll_salary_due(employee: Employee) -> Decimal:
    if (employee.jenis_imbalan or "KOMISI") not in {"GAJI", "KOMISI_GAJI"}:
        return money(0)
    base = Decimal(employee.gaji_bulanan or 0)
    period = employee.payroll_period or "BULANAN"
    if period == "MINGGUAN":
        return money(base * Decimal("7") / Decimal("30"))
    if period == "DUA_MINGGUAN":
        return money(base * Decimal("14") / Decimal("30"))
    if period == "TIGA_MINGGUAN":
        return money(base * Decimal("21") / Decimal("30"))
    return money(base)


def _next_pay_date(employee: Employee, today: date) -> date:
    period = employee.payroll_period or "BULANAN"
    if period in {"MINGGUAN", "DUA_MINGGUAN", "TIGA_MINGGUAN"}:
        target = min(max(0, int(employee.payroll_hari or 0)), 6)
        delta = (target - today.weekday()) % 7
        return today + timedelta(days=delta)
    last_day = calendar.monthrange(today.year, today.month)[1]
    if period == "BULANAN":
        return date(today.year, today.month, last_day)
    day = min(max(1, int(employee.payroll_tanggal or 1)), last_day)
    candidate = date(today.year, today.month, day)
    if candidate < today:
        next_month = today.month + 1
        next_year = today.year + (1 if next_month > 12 else 0)
        next_month = 1 if next_month > 12 else next_month
        last_next = calendar.monthrange(next_year, next_month)[1]
        candidate = date(next_year, next_month, min(day, last_next))
    return candidate


def _has_compensation(employee: Employee) -> bool:
    if (employee.jenis_imbalan or "KOMISI") in {"GAJI", "KOMISI_GAJI"} and Decimal(
        employee.gaji_bulanan or 0
    ) > 0:
        return True
    if Decimal(employee.komisi_barang_nilai or 0) > 0:
        return True
    if Decimal(employee.komisi_jasa_nilai or 0) > 0:
        return True
    return employee.komisi_mode == "NOMINAL" and Decimal(
        employee.komisi_nilai or 0
    ) > 0


def payroll_summary(db: Session, today: Optional[date] = None) -> Dict[str, Any]:
    """Estimasi gaji + komisi yang perlu dibayar pada siklus berjalan."""
    target = today or date.today()
    employees = [
        employee
        for employee in list_employees(db, active_only=True)
        if _has_compensation(employee)
    ]
    if not employees:
        return {
            "today": target,
            "total_due": money(0),
            "count": 0,
            "next_date": None,
            "items": [],
        }

    starts = {employee.id: payroll_cycle_start(employee, target) for employee in employees}
    earliest = min(starts.values())
    payments = list(
        db.scalars(
            select(SalaryPayment).where(
                SalaryPayment.tanggal >= earliest,
                SalaryPayment.tanggal <= target,
            )
        ).all()
    )
    paid: Dict[int, Decimal] = {}
    for payment in payments:
        if payment.employee_id is None:
            continue
        settled = (
            Decimal(payment.nominal or 0)
            + Decimal(payment.potongan_hutang or 0)
            - Decimal(payment.bonus or 0)
        )
        paid[payment.employee_id] = paid.get(
            payment.employee_id, Decimal("0.00")
        ) + max(Decimal("0.00"), settled)
    debt_totals = employee_debt_service.outstanding_by_employee(db)

    items = []
    for employee in employees:
        start = starts[employee.id]
        commission = Decimal("0.00")
        for record in _employee_records(db, employee, start, target):
            commission += _commission_for(db, employee, record)
        salary_due = _payroll_salary_due(employee)
        salary_paid = money(paid.get(employee.id, Decimal("0.00")))
        gross_due = money(
            max(Decimal("0.00"), salary_due + commission - salary_paid)
        )
        debt_total = money(debt_totals.get(employee.id, Decimal("0.00")))
        debt_used = money(min(debt_total, gross_due))
        total_due = money(gross_due - debt_used)
        next_date = _next_pay_date(employee, target)
        days_left = (next_date - target).days
        status = (
            "JATUH_TEMPO"
            if days_left <= 0
            else "SEGERA"
            if days_left <= 3
            else "TERJADWAL"
        )
        items.append(
            {
                "employee_id": employee.id,
                "nama": employee.nama,
                "jadwal": PAYROLL_LABELS.get(
                    employee.payroll_period, "Bulanan"
                )
                + (
                    " · " + HARI_LABELS[int(employee.payroll_hari or 0)]
                    if employee.payroll_period
                    in {"MINGGUAN", "DUA_MINGGUAN", "TIGA_MINGGUAN"}
                    else ""
                ),
                "cycle_start": start,
                "next_date": next_date,
                "days_left": days_left,
                "status": status,
                "salary_due": salary_due,
                "commission_earned": money(commission),
                "salary_paid": salary_paid,
                "debt_total": debt_total,
                "debt_used": debt_used,
                "gross_due": gross_due,
                "total_due": total_due,
                "bank_nama": employee.bank_nama,
                "bank_nomor": employee.bank_nomor,
                "bank_atas_nama": employee.bank_atas_nama,
                "nomor_hp": employee.nomor_hp,
            }
        )

    items.sort(key=lambda row: (Decimal(row["total_due"]) <= 0, -Decimal(row["total_due"]), row["nama"].lower()))
    due_items = [row for row in items if Decimal(row["total_due"]) > 0]
    alert_items = [row for row in due_items if row["status"] in {"JATUH_TEMPO", "SEGERA"}]
    return {
        "today": target,
        "total_due": money(sum((Decimal(row["total_due"]) for row in items), Decimal("0.00"))),
        "count": len(due_items),
        "due_count": len(alert_items),
        "due_total": money(
            sum((Decimal(row["total_due"]) for row in alert_items), Decimal("0.00"))
        ),
        "next_date": min((row["next_date"] for row in due_items), default=None),
        "items": items,
    }


def _record_modal_total(record: ServiceRecord) -> Decimal:
    """Total harga modal sparepart bersih retur pada satu nota."""
    modal = Decimal("0.00")
    for part in record.parts:
        net_qty = int(part.jumlah or 0) - int(getattr(part, "jumlah_retur", 0) or 0)
        if net_qty <= 0:
            continue
        harga = getattr(part, "harga_modal", None)
        if harga is None and part.stock_item is not None:
            harga = part.stock_item.harga_modal
        if harga is None:
            continue
        modal += Decimal(harga) * net_qty
    return money(modal)


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
    total_nota = money(record.total_servis or 0)
    if amount > total_nota:
        raise BusinessValidationError(
            "Komisi tidak boleh melebihi total nota pelanggan. "
            "Maksimal " + format_rupiah(total_nota) + "."
        )
    modal_total = _record_modal_total(record)
    sisa_setelah_modal = money(max(Decimal("0.00"), total_nota - modal_total))
    if amount > sisa_setelah_modal:
        raise BusinessValidationError(
            "Komisi tidak boleh melebihi sisa setelah harga modal. "
            "Harga modal nota " + format_rupiah(modal_total)
            + " harus tetap aman. Maksimal komisi "
            + format_rupiah(sisa_setelah_modal) + "."
        )
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
