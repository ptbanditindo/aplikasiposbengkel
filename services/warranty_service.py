"""Logika masa garansi servis & klaim.

Ref: PRD FR-WAR-01 s/d FR-WAR-05.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy import update
from sqlalchemy.orm import Session

from config import settings
from database.models import ServiceRecord
from database.session import begin_immediate
from repositories import service_record_repository as repo
from services.errors import ConflictError, NotFoundError, WarrantyError


def warranty_end_date(
    months: Optional[int],
    custom_date: Optional[date] = None,
    today: Optional[date] = None,
) -> date:
    """Hitung tanggal akhir garansi.

    Ref: TC-13 - garansi 1 bulan = tepat 30 hari kalender ke depan.
    """
    if custom_date is not None:
        return custom_date
    base = today or date.today()
    duration_months = int(months) if months is not None else 0
    if duration_months < 1:
        duration_months = settings.default_garansi_bulan or 1
    return base + timedelta(days=30 * duration_months)


def is_active(record: ServiceRecord, today: Optional[date] = None) -> bool:
    if not record.bergaransi or record.garansi_sampai is None:
        return False
    if record.status_klaim == "Sudah claim":
        return False
    return (today or date.today()) <= record.garansi_sampai


def warranty_status(record: ServiceRecord, today: Optional[date] = None) -> str:
    if not record.bergaransi or record.garansi_sampai is None:
        return "TANPA GARANSI"
    if record.status_klaim == "Sudah claim":
        return "SUDAH CLAIM"
    if is_active(record, today):
        return "AKTIF"
    return "KEDALUWARSA"


def claim_warranty(
    db: Session, record_id: int, today: Optional[date] = None
) -> ServiceRecord:
    day = today or date.today()

    # Ref: R-01 - kunci tulis sejak awal agar dua klaim terserialisasi.
    with db.begin():
        begin_immediate(db)
        record = repo.get_record(db, record_id)
        if record is None:
            raise NotFoundError("Nota servis tidak ditemukan.")

        if not record.bergaransi or record.garansi_sampai is None:
            raise WarrantyError("Transaksi ini tidak memiliki garansi servis.")
        if record.status_klaim == "Sudah claim":
            raise ConflictError("Garansi untuk nota ini sudah pernah diklaim.")
        if day > record.garansi_sampai:
            raise WarrantyError(
                f"Masa garansi telah habis pada {record.garansi_sampai:%d/%m/%Y}."
            )

        result = db.execute(
            update(ServiceRecord)
            .where(
                ServiceRecord.id == record_id,
                ServiceRecord.status_klaim != "Sudah claim",
            )
            .values(status_klaim="Sudah claim", tanggal_klaim=day)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 0:
            raise ConflictError("Garansi untuk nota ini sudah pernah diklaim.")

    db.refresh(record)
    return record
