"""Logika bisnis pelanggan & unit servis (mobil / radiator copotan)."""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from database.models import Customer, VehicleOrUnit
from database.session import begin_immediate
from repositories import customer_repository as repo
from services import audit_service
from services.auth_service import Operator
from services.errors import BusinessValidationError, NotFoundError
from services.utils import clean_text, normalize_nopol, normalize_phone

VALID_UNIT_TYPES = {"MOBIL", "RADIATOR_ONLY"}


def create_customer(
    db: Session,
    nama: str,
    nomor_hp: str,
    alamat: Optional[str] = None,
) -> Customer:
    clean_nama = clean_text(nama, max_length=255, allow_newlines=False)
    if len(clean_nama) < 2:
        raise BusinessValidationError("Nama pelanggan minimal 2 karakter.")

    phone = normalize_phone(nomor_hp)
    if not (8 <= len(phone) <= 15):
        raise BusinessValidationError("Nomor HP tidak valid (8-15 digit).")

    clean_alamat = clean_text(alamat, max_length=500) or None
    return repo.create_customer(db, clean_nama, phone, clean_alamat)


def archive_unit(
    db: Session,
    unit_id: int,
    operator: Optional[Operator] = None,
) -> VehicleOrUnit:
    """Soft delete unit: sembunyikan dari pilihan tanpa memutus riwayat nota."""
    with db.begin():
        begin_immediate(db)
        unit = repo.get_unit(db, unit_id)
        if unit is None:
            raise NotFoundError("Unit servis tidak ditemukan.")
        if unit.archived_at is not None:
            db.flush()
        else:
            unit.archived_at = datetime.now()
            if operator is not None:
                audit_service.record_event(
                    db,
                    operator,
                    audit_service.ACTION_UNIT,
                    audit_service.REFERENCE_UNIT,
                    reference_id=str(unit.id),
                    reason="Unit dihapus dari daftar",
                )
            db.flush()
    db.refresh(unit)
    return unit


def search_customers(db: Session, query: str = "", limit: int = 20) -> List[Customer]:
    return repo.search_customers(db, query, limit)


def list_customers_with_units(
    db: Session, query: str = "", limit: int = 100
) -> List[Customer]:
    return repo.list_customers_with_units(db, query, limit)


def list_units(db: Session, customer_id: int) -> List[VehicleOrUnit]:
    if repo.get_customer(db, customer_id) is None:
        raise NotFoundError("Pelanggan tidak ditemukan.")
    return repo.list_units(db, customer_id)


def _next_radiator_label(db: Session, today: date) -> str:
    """Generator label fisik unik RAD-YYYYMMDD-XXX.

    Ref: PRD FR-UNIT-04 / TC-05.
    """
    prefix = f"RAD-{today:%Y%m%d}-"
    highest = 0
    for label in repo.labels_with_prefix(db, prefix):
        suffix = label[len(prefix):]
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return f"{prefix}{highest + 1:03d}"


def ensure_unit_label(db: Session, unit: VehicleOrUnit, today: date) -> str:
    """Buat label barang saat transaksi pertama, lalu pakai ulang selamanya.

    Label lama tidak pernah diganti. Pemanggil harus sudah memegang kunci tulis
    (BEGIN IMMEDIATE) agar urutan harian tidak bertabrakan.
    """
    if unit.label_radiator:
        return unit.label_radiator
    unit.label_radiator = _next_radiator_label(db, today)
    db.flush()
    return unit.label_radiator


def create_unit(
    db: Session,
    customer_id: int,
    unit_type: str,
    nopol: Optional[str] = None,
    jenis_mobil: Optional[str] = None,
    tahun_mobil: Optional[int] = None,
    tipe_radiator: Optional[str] = None,
    keterangan: Optional[str] = None,
) -> VehicleOrUnit:
    normalized_type = (unit_type or "").strip().upper()
    if normalized_type not in VALID_UNIT_TYPES:
        raise BusinessValidationError("Jenis unit harus MOBIL atau RADIATOR_ONLY.")

    if tahun_mobil is not None and not (1900 <= int(tahun_mobil) <= 2100):
        raise BusinessValidationError("Tahun mobil tidak valid.")

    clean_jenis = clean_text(jenis_mobil, max_length=255, allow_newlines=False) or None
    clean_tipe = clean_text(tipe_radiator, max_length=255, allow_newlines=False) or None
    clean_ket = clean_text(keterangan, max_length=1000) or None

    if normalized_type == "MOBIL":
        normalized_nopol = normalize_nopol(nopol)
        if not normalized_nopol:
            raise BusinessValidationError("Nomor polisi wajib diisi untuk unit mobil.")
        if len(normalized_nopol) > 32:
            raise BusinessValidationError("Nomor polisi terlalu panjang.")
        with db.begin():
            begin_immediate(db)
            if repo.get_customer(db, customer_id) is None:
                raise NotFoundError("Pelanggan tidak ditemukan.")
            unit = VehicleOrUnit(
                customer_id=customer_id,
                unit_type="MOBIL",
                nopol=normalized_nopol,
                jenis_mobil=clean_jenis,
                tahun_mobil=int(tahun_mobil) if tahun_mobil is not None else None,
                label_radiator=None,
                tipe_radiator=None,
                keterangan=clean_ket,
            )
            db.add(unit)
            db.flush()
        db.refresh(unit)
        return unit

    # Ref: PRD FR-UNIT-04 - radiator copotan tanpa nopol. Label fisik baru
    # dibuat saat transaksi pertama agar nomor barang mengikuti nota.
    with db.begin():
        begin_immediate(db)
        if repo.get_customer(db, customer_id) is None:
            raise NotFoundError("Pelanggan tidak ditemukan.")
        unit = VehicleOrUnit(
            customer_id=customer_id,
            unit_type="RADIATOR_ONLY",
            nopol=None,
            jenis_mobil=None,
            tahun_mobil=None,
            label_radiator=None,
            tipe_radiator=clean_tipe,
            keterangan=clean_ket,
        )
        db.add(unit)
        db.flush()
    db.refresh(unit)
    return unit


def describe_unit(unit: VehicleOrUnit) -> str:
    """Deskripsi unit untuk struk / riwayat."""
    if unit.unit_type == "MOBIL":
        text = unit.nopol or "-"
        if unit.jenis_mobil:
            text += f" ({unit.jenis_mobil})"
        return text
    text = "[BAWA RADIATOR SAJA]"
    if unit.label_radiator:
        text += f" {unit.label_radiator}"
    if unit.tipe_radiator:
        text += f" ({unit.tipe_radiator})"
    return text
