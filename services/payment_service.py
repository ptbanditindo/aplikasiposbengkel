"""DP, pelunasan bertahap, refund, dan daftar piutang (Tahap 11)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from database.models import (
    Customer,
    ServicePayment,
    ServiceRecord,
    VehicleOrUnit,
)
from database.session import begin_immediate
from services import audit_service
from services.auth_service import Operator
from services.errors import (
    BusinessValidationError,
    ConflictError,
    NotFoundError,
    PaymentError,
)
from services.utils import clean_text, money


def record_netto(record: ServiceRecord) -> Decimal:
    if (record.status or "NORMAL") == "VOID":
        return money(Decimal("0.00"))
    return money(
        max(
            Decimal(record.total_servis or 0)
            - Decimal(record.total_retur or 0),
            Decimal("0.00"),
        )
    )


def record_sisa(record: ServiceRecord) -> Decimal:
    if (record.status or "NORMAL") == "VOID":
        return money(Decimal("0.00"))
    return money(
        max(record_netto(record) - Decimal(record.total_dibayar or 0), Decimal("0.00"))
    )


def list_payments(db: Session, record_id: int) -> List[ServicePayment]:
    if db.get(ServiceRecord, record_id) is None:
        raise NotFoundError("Nota servis tidak ditemukan.")
    statement = (
        select(ServicePayment)
        .where(ServicePayment.service_record_id == record_id)
        .order_by(ServicePayment.waktu.asc(), ServicePayment.id.asc())
    )
    return list(db.scalars(statement).all())


def record_payment(
    db: Session,
    record_id: int,
    nominal: Any,
    metode: str,
    operator: Operator,
    catatan: Optional[str] = None,
    request_id: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Tuple[ServicePayment, ServiceRecord, bool]:
    """Catat pelunasan atomik. Mengembalikan (payment, record, created)."""
    request_key = (request_id or "").strip() or None
    moment = now or datetime.now()
    method = (metode or "").strip().upper()
    if method not in {"CASH", "TRANSFER"}:
        raise BusinessValidationError("Metode pembayaran harus CASH atau TRANSFER.")
    value = money(nominal)
    if value <= 0:
        raise BusinessValidationError("Nominal pelunasan harus lebih dari Rp 0.")
    note = clean_text(catatan, max_length=500) or None

    try:
        with db.begin():
            begin_immediate(db)
            if request_key:
                existing = db.scalar(
                    select(ServicePayment).where(
                        ServicePayment.request_id == request_key
                    )
                )
                if existing is not None:
                    if existing.service_record_id != record_id:
                        raise ConflictError(
                            "Request pelunasan sudah dipakai untuk nota lain."
                        )
                    record = db.get(ServiceRecord, record_id)
                    return existing, record, False

            record = db.get(ServiceRecord, record_id)
            if record is None:
                raise NotFoundError("Nota servis tidak ditemukan.")
            if (record.status or "NORMAL") == "VOID":
                raise ConflictError("Nota sudah dibatalkan (VOID).")
            sisa = record_sisa(record)
            if sisa <= 0 or (record.status_bayar or "LUNAS") == "LUNAS":
                raise ConflictError("Nota ini sudah lunas.")
            if value > sisa:
                raise PaymentError(
                    f"Nominal melebihi sisa piutang ({sisa:.2f})."
                )

            payment = ServicePayment(
                service_record_id=record.id,
                jenis="PELUNASAN",
                metode=method,
                nominal=value,
                waktu=moment,
                operator=operator.label,
                catatan=note,
                request_id=request_key,
                created_at=moment,
            )
            db.add(payment)

            total_dibayar = money(Decimal(record.total_dibayar or 0) + value)
            record.total_dibayar = total_dibayar
            record.status_bayar = (
                "LUNAS" if record_sisa(record) <= 0 else "BELUM_LUNAS"
            )

            audit_service.record_event(
                db,
                operator,
                audit_service.ACTION_PAYMENT,
                audit_service.REFERENCE_SERVICE_RECORD,
                reference_id=record.no_nota,
                reason=f"Pelunasan {method} Rp {value:.2f}",
                now=moment,
            )
            db.flush()
    except IntegrityError:
        db.rollback()
        if request_key:
            existing = db.scalar(
                select(ServicePayment).where(ServicePayment.request_id == request_key)
            )
            if existing is not None:
                return existing, db.get(ServiceRecord, record_id), False
        raise

    return payment, record, True


def refund_void(
    db: Session, record: ServiceRecord, operator_label: str, reason: str, moment: datetime
) -> Optional[ServicePayment]:
    """Kembalikan seluruh uang yang sudah diterima saat nota di-void."""
    paid = money(record.total_dibayar or 0)
    if paid <= 0:
        record.total_dibayar = money(Decimal("0.00"))
        record.status_bayar = "LUNAS"
        return None
    refund = ServicePayment(
        service_record_id=record.id,
        jenis="REFUND",
        metode=record.metode_bayar or "CASH",
        nominal=money(-paid),
        waktu=moment,
        operator=operator_label,
        catatan=f"Refund void {record.no_nota}: {reason}",
        created_at=moment,
    )
    db.add(refund)
    record.total_dibayar = money(Decimal("0.00"))
    record.status_bayar = "LUNAS"
    return refund


def refund_excess(
    db: Session,
    record: ServiceRecord,
    operator_label: str,
    reason: str,
    moment: datetime,
    netto: Optional[Decimal] = None,
) -> Optional[ServicePayment]:
    """Kembalikan kelebihan bayar setelah retur; tidak pernah negatif."""
    target = money(record_netto(record) if netto is None else netto)
    paid = money(record.total_dibayar or 0)
    refunded: Optional[ServicePayment] = None
    if paid > target:
        excess = money(paid - target)
        refunded = ServicePayment(
            service_record_id=record.id,
            jenis="REFUND",
            metode=record.metode_bayar or "CASH",
            nominal=money(-excess),
            waktu=moment,
            operator=operator_label,
            catatan=f"Refund retur {record.no_nota}: {reason}",
            created_at=moment,
        )
        db.add(refunded)
        paid = target
    record.total_dibayar = money(paid)
    record.status_bayar = "LUNAS" if money(target - paid) <= 0 else "BELUM_LUNAS"
    return refunded


def _age_bucket(days: int) -> str:
    if days <= 7:
        return "0-7"
    if days <= 30:
        return "8-30"
    if days <= 60:
        return "31-60"
    return ">60"


def _unpaid_records(
    db: Session, today: Optional[date] = None, customer_id: Optional[int] = None
) -> List[ServiceRecord]:
    statement = (
        select(ServiceRecord)
        .join(VehicleOrUnit, ServiceRecord.unit_id == VehicleOrUnit.id)
        .join(Customer, VehicleOrUnit.customer_id == Customer.id)
        .options(
            selectinload(ServiceRecord.unit).selectinload(VehicleOrUnit.customer)
        )
        .where(
            ServiceRecord.status == "NORMAL",
            ServiceRecord.status_bayar == "BELUM_LUNAS",
        )
        .order_by(ServiceRecord.jatuh_tempo.asc(), ServiceRecord.waktu_service.asc())
    )
    if customer_id is not None:
        statement = statement.where(Customer.id == customer_id)
    records = list(db.scalars(statement).all())
    return [record for record in records if record_sisa(record) > 0]


def receivables(
    db: Session, today: Optional[date] = None, customer_id: Optional[int] = None
) -> Dict[str, Any]:
    day = today or date.today()
    groups: Dict[int, Dict[str, Any]] = {}
    for record in _unpaid_records(db, day, customer_id):
        customer = record.unit.customer
        group = groups.get(customer.id)
        if group is None:
            group = {
                "customer_id": customer.id,
                "nama": customer.nama,
                "nomor_hp": customer.nomor_hp,
                "jumlah_nota": 0,
                "total_sisa": Decimal("0.00"),
                "jatuh_tempo_terdekat": None,
                "umur_tertua_hari": 0,
                "records": [],
            }
            groups[customer.id] = group

        netto = record_netto(record)
        sisa = record_sisa(record)
        age = max((day - record.waktu_service.date()).days, 0)
        overdue = bool(record.jatuh_tempo and record.jatuh_tempo < day)
        group["jumlah_nota"] += 1
        group["total_sisa"] += sisa
        group["umur_tertua_hari"] = max(group["umur_tertua_hari"], age)
        if record.jatuh_tempo is not None:
            current = group["jatuh_tempo_terdekat"]
            if current is None or record.jatuh_tempo < current:
                group["jatuh_tempo_terdekat"] = record.jatuh_tempo
        group["records"].append(
            {
                "id": record.id,
                "no_nota": record.no_nota,
                "waktu_service": record.waktu_service,
                "metode_bayar": record.metode_bayar,
                "total_servis": record.total_servis,
                "total_neto": netto,
                "total_dibayar": money(record.total_dibayar or 0),
                "sisa_bayar": sisa,
                "jatuh_tempo": record.jatuh_tempo,
                "umur_hari": age,
                "umur_bucket": _age_bucket(age),
                "overdue": overdue,
            }
        )

    items = sorted(
        groups.values(),
        key=lambda item: (-item["total_sisa"], item["nama"].lower()),
    )
    for item in items:
        item["total_sisa"] = money(item["total_sisa"])
        item["records"].sort(
            key=lambda row: (row["jatuh_tempo"] or date.max, row["waktu_service"])
        )
    return {
        "jumlah_pelanggan": len(items),
        "jumlah_nota": sum(item["jumlah_nota"] for item in items),
        "total_sisa": money(sum((item["total_sisa"] for item in items), Decimal("0.00"))),
        "items": items,
    }
