"""Void nota & retur item dengan pengembalian stok atomik (S-06)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from database.models import (
    ServiceJob,
    ServicePart,
    ServiceRecord,
    ServiceReturn,
    ServiceReturnItem,
    StockItem,
    StockMovement,
)
from database.session import begin_immediate
from services import audit_service, payment_service
from services.auth_service import Operator
from services.errors import (
    BusinessValidationError,
    ConflictError,
    NotFoundError,
)
from services.utils import clean_text, money


@dataclass
class _ReturnLine:
    part: Optional[ServicePart]
    job: Optional[ServiceJob]
    jumlah: int
    nama: str
    harga_satuan: Decimal
    harga_modal: Optional[Decimal]


def _clean_reason(value: str) -> str:
    reason = clean_text(value, max_length=500)
    if len(reason) < 3:
        raise BusinessValidationError("Alasan wajib diisi minimal 3 karakter.")
    return reason


def void_record(
    db: Session,
    record_id: int,
    reason: str,
    operator: Operator,
    now: Optional[datetime] = None,
) -> ServiceRecord:
    """Batalkan nota tanpa menghapusnya dan kembalikan stok part secara atomik."""
    clean_reason = _clean_reason(reason)
    user = operator.label
    moment = now or datetime.now()

    with db.begin():
        begin_immediate(db)
        record = db.get(ServiceRecord, record_id)
        if record is None:
            raise NotFoundError("Nota servis tidak ditemukan.")
        if record.status == "VOID":
            raise ConflictError("Nota ini sudah dibatalkan (VOID).")
        if (record.retur_count or 0) > 0:
            raise ConflictError(
                "Nota sudah memiliki retur; void tidak dapat dilakukan. "
                "Gunakan retur untuk mengembalikan item."
            )

        result = db.execute(
            update(ServiceRecord)
            .where(
                ServiceRecord.id == record_id,
                ServiceRecord.status == "NORMAL",
                ServiceRecord.retur_count == 0,
            )
            .values(
                status="VOID",
                void_reason=clean_reason,
                voided_at=moment,
                voided_by=user,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 0:
            raise ConflictError("Nota ini sudah dibatalkan (VOID).")

        parts = list(
            db.scalars(
                select(ServicePart).where(
                    ServicePart.service_record_id == record_id
                )
            ).all()
        )
        for part in parts:
            if part.stock_item_id is None or part.jumlah <= 0:
                continue
            stock = db.get(StockItem, part.stock_item_id)
            if stock is None:
                continue
            db.execute(
                update(StockItem)
                .where(StockItem.id == stock.id)
                .values(jumlah=StockItem.jumlah + part.jumlah)
                .execution_options(synchronize_session=False)
            )
            db.add(
                StockMovement(
                    stock_item_id=stock.id,
                    nama_item=part.nama_part,
                    jenis="VOID",
                    jumlah=part.jumlah,
                    alasan=f"Void {record.no_nota}: {clean_reason}",
                    oleh=user,
                    service_record_id=record.id,
                    created_at=moment,
                )
            )

        payment_service.refund_void(
            db, record, user, clean_reason, moment
        )

        audit_service.record_event(
            db,
            operator,
            audit_service.ACTION_VOID,
            audit_service.REFERENCE_SERVICE_RECORD,
            reference_id=record.no_nota,
            reason=clean_reason,
            now=moment,
        )

    db.refresh(record)
    return record


def create_return(
    db: Session,
    record_id: int,
    reason: str,
    items: List,
    operator: Operator,
    now: Optional[datetime] = None,
) -> ServiceReturn:
    """Catat retur sebagian/seluruh item dan kembalikan stok part secara atomik.

    Batas retur dihitung dari akumulasi `jumlah_retur`, bukan hanya dari nota
    asli, sehingga retur ganda/berlebih ditolak walau request berulang.
    """
    clean_reason = _clean_reason(reason)
    user = operator.label
    moment = now or datetime.now()
    if not items:
        raise BusinessValidationError("Retur harus memiliki minimal satu item.")

    with db.begin():
        begin_immediate(db)
        record = db.get(ServiceRecord, record_id)
        if record is None:
            raise NotFoundError("Nota servis tidak ditemukan.")
        if record.status == "VOID":
            raise ConflictError(
                "Nota sudah dibatalkan (VOID); retur tidak dapat diproses."
            )

        parts: Dict[int, ServicePart] = {
            part.id: part
            for part in db.scalars(
                select(ServicePart).where(
                    ServicePart.service_record_id == record_id
                )
            ).all()
        }
        jobs: Dict[int, ServiceJob] = {
            job.id: job
            for job in db.scalars(
                select(ServiceJob).where(
                    ServiceJob.service_record_id == record_id
                )
            ).all()
        }

        lines: List[_ReturnLine] = []
        seen: set[tuple[str, int]] = set()
        for item in items:
            part_id = getattr(item, "service_part_id", None)
            job_id = getattr(item, "service_job_id", None)
            if (part_id is None) == (job_id is None):
                raise BusinessValidationError(
                    "Setiap item retur harus memilih tepat satu jasa atau sparepart."
                )
            qty = int(item.jumlah)
            if qty < 1:
                raise BusinessValidationError("Jumlah retur minimal 1.")

            if part_id is not None:
                part = parts.get(part_id)
                if part is None:
                    raise NotFoundError("Item retur bukan bagian dari nota ini.")
                key = ("PART", part.id)
                if key in seen:
                    raise BusinessValidationError("Item retur duplikat.")
                seen.add(key)
                remaining = part.jumlah - (part.jumlah_retur or 0)
                if qty > remaining:
                    raise BusinessValidationError(
                        f"Jumlah retur {part.nama_part} melebihi sisa yang "
                        f"dapat diretur ({remaining})."
                    )
                lines.append(
                    _ReturnLine(
                        part=part,
                        job=None,
                        jumlah=qty,
                        nama=part.nama_part,
                        harga_satuan=part.harga_satuan,
                        harga_modal=part.harga_modal,
                    )
                )
            else:
                job = jobs.get(job_id)
                if job is None:
                    raise NotFoundError("Item retur bukan bagian dari nota ini.")
                key = ("JASA", job.id)
                if key in seen:
                    raise BusinessValidationError("Item retur duplikat.")
                seen.add(key)
                remaining = job.jumlah - (job.jumlah_retur or 0)
                if qty > remaining:
                    raise BusinessValidationError(
                        f"Jumlah retur {job.deskripsi} melebihi sisa yang "
                        f"dapat diretur ({remaining})."
                    )
                lines.append(
                    _ReturnLine(
                        part=None,
                        job=job,
                        jumlah=qty,
                        nama=job.deskripsi,
                        harga_satuan=job.harga,
                        harga_modal=None,
                    )
                )

        retur = ServiceReturn(
            service_record_id=record_id,
            alasan=clean_reason,
            oleh=user,
            total_nilai=Decimal("0.00"),
            created_at=moment,
        )
        db.add(retur)
        db.flush()

        total_nilai = Decimal("0.00")
        total_jasa = Decimal("0.00")
        total_part = Decimal("0.00")

        for line in lines:
            subtotal = money(line.harga_satuan * line.jumlah)
            total_nilai += subtotal
            if line.part is not None:
                total_part += subtotal
                result = db.execute(
                    update(ServicePart)
                    .where(
                        ServicePart.id == line.part.id,
                        ServicePart.jumlah_retur + line.jumlah
                        <= ServicePart.jumlah,
                    )
                    .values(
                        jumlah_retur=ServicePart.jumlah_retur + line.jumlah
                    )
                    .execution_options(synchronize_session=False)
                )
                if result.rowcount == 0:
                    raise BusinessValidationError(
                        f"Jumlah retur {line.nama} melebihi sisa yang "
                        "dapat diretur."
                    )
                if line.part.stock_item_id is not None:
                    stock = db.get(StockItem, line.part.stock_item_id)
                    if stock is not None:
                        db.execute(
                            update(StockItem)
                            .where(StockItem.id == stock.id)
                            .values(jumlah=StockItem.jumlah + line.jumlah)
                            .execution_options(synchronize_session=False)
                        )
                        db.add(
                            StockMovement(
                                stock_item_id=stock.id,
                                nama_item=line.nama,
                                jenis="RETUR",
                                jumlah=line.jumlah,
                                alasan=f"Retur {record.no_nota}: {clean_reason}",
                                oleh=user,
                                service_record_id=record.id,
                                service_return_id=retur.id,
                                created_at=moment,
                            )
                        )
                item_row = ServiceReturnItem(
                    service_return_id=retur.id,
                    service_part_id=line.part.id,
                    stock_item_id=line.part.stock_item_id,
                    nama_item=line.nama,
                    jumlah=line.jumlah,
                    harga_satuan=line.harga_satuan,
                    harga_modal=line.harga_modal,
                    subtotal=subtotal,
                )
            else:
                total_jasa += subtotal
                result = db.execute(
                    update(ServiceJob)
                    .where(
                        ServiceJob.id == line.job.id,
                        ServiceJob.jumlah_retur + line.jumlah <= ServiceJob.jumlah,
                    )
                    .values(jumlah_retur=ServiceJob.jumlah_retur + line.jumlah)
                    .execution_options(synchronize_session=False)
                )
                if result.rowcount == 0:
                    raise BusinessValidationError(
                        f"Jumlah retur {line.nama} melebihi sisa yang "
                        "dapat diretur."
                    )
                item_row = ServiceReturnItem(
                    service_return_id=retur.id,
                    service_job_id=line.job.id,
                    nama_item=line.nama,
                    jumlah=line.jumlah,
                    harga_satuan=line.harga_satuan,
                    harga_modal=None,
                    subtotal=subtotal,
                )
            retur.items.append(item_row)

        total_nilai = money(total_nilai)
        retur.total_nilai = total_nilai
        db.execute(
            update(ServiceRecord)
            .where(ServiceRecord.id == record_id)
            .values(
                total_retur=ServiceRecord.total_retur + total_nilai,
                total_retur_jasa=ServiceRecord.total_retur_jasa + money(total_jasa),
                total_retur_part=ServiceRecord.total_retur_part + money(total_part),
                retur_count=ServiceRecord.retur_count + 1,
            )
            .execution_options(synchronize_session=False)
        )

        # Retur menurunkan nilai neto nota; kelebihan bayar dikembalikan
        # sebagai baris REFUND agar tidak ada saldo piutang negatif.
        netto_setelah_retur = money(
            max(
                Decimal(record.total_servis or 0)
                - (Decimal(record.total_retur or 0) + total_nilai),
                Decimal("0.00"),
            )
        )
        payment_service.refund_excess(
            db,
            record,
            user,
            clean_reason,
            moment,
            netto=netto_setelah_retur,
        )

        audit_service.record_event(
            db,
            operator,
            audit_service.ACTION_RETURN,
            audit_service.REFERENCE_SERVICE_RECORD,
            reference_id=record.no_nota,
            reason=clean_reason,
            now=moment,
        )

    return retur


def list_returns(db: Session, record_id: int) -> List[ServiceReturn]:
    if db.get(ServiceRecord, record_id) is None:
        raise NotFoundError("Nota servis tidak ditemukan.")
    statement = (
        select(ServiceReturn)
        .where(ServiceReturn.service_record_id == record_id)
        .options(selectinload(ServiceReturn.items))
        .order_by(ServiceReturn.created_at.asc(), ServiceReturn.id.asc())
    )
    return list(db.scalars(statement).all())
