"""Logika bisnis pelanggan & unit servis (mobil / radiator copotan)."""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Customer, VehicleOrUnit
from database.session import begin_immediate
from repositories import customer_repository as repo
from services import audit_service
from services.auth_service import Operator
from services.errors import BusinessValidationError, NotFoundError
from services.utils import clean_text, normalize_nopol, normalize_phone

VALID_UNIT_TYPES = {
    "MOBIL",
    "MOTOR_LENGKAP",
    "PART_MOBIL",
    "PART_MOTOR",
    # Legacy: part mobil tanpa nopol yang sudah terlanjur tersimpan.
    "RADIATOR_ONLY",
    # Unit walk-in internal untuk pembelian sparepart tanpa kendaraan.
    "SPAREPART",
}
COMPLETE_UNIT_TYPES = {"MOBIL", "MOTOR_LENGKAP"}
PART_UNIT_TYPES = {"PART_MOBIL", "PART_MOTOR", "RADIATOR_ONLY"}
WALKIN_CUSTOMER_NAME = "Pelanggan Umum"
WALKIN_CUSTOMER_ADDRESS = "Pembelian sparepart"
WALKIN_UNIT_TYPE = "SPAREPART"

def is_walkin_customer(customer: Customer) -> bool:
    return (
        customer.nama == WALKIN_CUSTOMER_NAME
        and (customer.alamat or "") == WALKIN_CUSTOMER_ADDRESS
    )


def get_or_create_walkin_unit(
    db: Session, customer_id: Optional[int] = None
) -> VehicleOrUnit:
    """Unit netral untuk penjualan sparepart tanpa data kendaraan."""
    customer: Optional[Customer] = None
    if customer_id:
        customer = db.get(Customer, int(customer_id))
        if customer is None:
            raise NotFoundError("Pelanggan tidak ditemukan.")
    else:
        customer = db.scalar(
            select(Customer).where(
                Customer.nama == WALKIN_CUSTOMER_NAME,
                Customer.alamat == WALKIN_CUSTOMER_ADDRESS,
            )
        )
        if customer is None:
            customer = Customer(
                nama=WALKIN_CUSTOMER_NAME,
                nomor_hp="",
                alamat=WALKIN_CUSTOMER_ADDRESS,
            )
            db.add(customer)
            db.flush()

    unit = db.scalar(
        select(VehicleOrUnit)
        .where(
            VehicleOrUnit.customer_id == customer.id,
            VehicleOrUnit.unit_type == WALKIN_UNIT_TYPE,
            VehicleOrUnit.archived_at.is_(None),
        )
        .order_by(VehicleOrUnit.id.asc())
    )
    if unit is None:
        unit = VehicleOrUnit(
            customer_id=customer.id,
            unit_type=WALKIN_UNIT_TYPE,
            keterangan="Pembelian sparepart",
        )
        db.add(unit)
        db.flush()
    return unit


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
    customers = repo.list_customers_with_units(db, query, limit)
    return [
        customer
        for customer in customers
        if not is_walkin_customer(customer)
    ]


def list_units(db: Session, customer_id: int) -> List[VehicleOrUnit]:
    if repo.get_customer(db, customer_id) is None:
        raise NotFoundError("Pelanggan tidak ditemukan.")
    return [
        unit
        for unit in repo.list_units(db, customer_id)
        if unit.unit_type != WALKIN_UNIT_TYPE
    ]


def _label_prefix(unit_type: str) -> str:
    # Kode RAD dipertahankan untuk part mobil lama agar riwayat tetap terbaca.
    return "PRT" if unit_type == "PART_MOTOR" else "RAD"


def _next_unit_label(db: Session, today: date, unit_type: str) -> str:
    """Generator label fisik unik per kategori dan tanggal."""
    prefix = f"{_label_prefix(unit_type)}-{today:%Y%m%d}-"
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
    unit.label_radiator = _next_unit_label(db, today, unit.unit_type)
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
    nama_barang: Optional[str] = None,
    nomor_seri: Optional[str] = None,
    kondisi: Optional[str] = None,
    kendaraan_asal: Optional[str] = None,
) -> VehicleOrUnit:
    normalized_type = (unit_type or "").strip().upper()
    if normalized_type not in VALID_UNIT_TYPES:
        raise BusinessValidationError(
            "Jenis unit harus MOBIL, MOTOR_LENGKAP, PART_MOBIL, atau PART_MOTOR."
        )

    if tahun_mobil is not None and not (1900 <= int(tahun_mobil) <= 2100):
        raise BusinessValidationError("Tahun kendaraan tidak valid.")

    clean_jenis = clean_text(jenis_mobil, max_length=255, allow_newlines=False) or None
    clean_tipe = clean_text(tipe_radiator, max_length=255, allow_newlines=False) or None
    clean_ket = clean_text(keterangan, max_length=1000) or None
    clean_barang = clean_text(nama_barang, max_length=255, allow_newlines=False) or None
    clean_seri = clean_text(nomor_seri, max_length=120, allow_newlines=False) or None
    clean_kondisi = clean_text(kondisi, max_length=64, allow_newlines=False) or None
    clean_asal = clean_text(kendaraan_asal, max_length=255, allow_newlines=False) or None

    if normalized_type == "SPAREPART":
        with db.begin():
            begin_immediate(db)
            if repo.get_customer(db, customer_id) is None:
                raise NotFoundError("Pelanggan tidak ditemukan.")
            unit = VehicleOrUnit(
                customer_id=customer_id,
                unit_type="SPAREPART",
                nopol=None,
                jenis_mobil=None,
                tahun_mobil=None,
                label_radiator=None,
                tipe_radiator=None,
                keterangan=clean_ket or "Pembelian sparepart",
            )
            db.add(unit)
            db.flush()
        db.refresh(unit)
        return unit

    if normalized_type in COMPLETE_UNIT_TYPES:
        normalized_nopol = normalize_nopol(nopol)
        if not normalized_nopol:
            raise BusinessValidationError(
                "Nomor polisi wajib diisi untuk unit lengkap."
            )
        if len(normalized_nopol) > 32:
            raise BusinessValidationError("Nomor polisi terlalu panjang.")
        with db.begin():
            begin_immediate(db)
            if repo.get_customer(db, customer_id) is None:
                raise NotFoundError("Pelanggan tidak ditemukan.")
            unit = VehicleOrUnit(
                customer_id=customer_id,
                unit_type=normalized_type,
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

    # Part mobil/motor: bebas nopol. Label fisik baru dibuat saat transaksi
    # pertama agar nomor barang mengikuti nota.
    if normalized_type in {"PART_MOBIL", "PART_MOTOR"} and not clean_barang:
        raise BusinessValidationError("Nama barang wajib diisi untuk part.")
    with db.begin():
        begin_immediate(db)
        if repo.get_customer(db, customer_id) is None:
            raise NotFoundError("Pelanggan tidak ditemukan.")
        unit = VehicleOrUnit(
            customer_id=customer_id,
            unit_type=normalized_type,
            nopol=None,
            jenis_mobil=None,
            tahun_mobil=None,
            label_radiator=None,
            tipe_radiator=clean_tipe,
            nama_barang=clean_barang,
            nomor_seri=clean_seri,
            kondisi=clean_kondisi,
            kendaraan_asal=clean_asal,
            keterangan=clean_ket,
        )
        db.add(unit)
        db.flush()
    db.refresh(unit)
    return unit


def describe_unit(unit: VehicleOrUnit) -> str:
    """Deskripsi unit untuk struk / riwayat."""
    if unit.unit_type == "SPAREPART":
        return unit.keterangan or "Pembelian sparepart"
    if unit.unit_type == "MOBIL":
        text = unit.nopol or "-"
        if unit.jenis_mobil:
            text += f" ({unit.jenis_mobil})"
        return text
    if unit.unit_type == "MOTOR_LENGKAP":
        text = "Motor " + (unit.nopol or "-")
        if unit.jenis_mobil:
            text += f" ({unit.jenis_mobil})"
        return text

    if unit.unit_type == "PART_MOTOR":
        text = "[PART MOTOR]"
    elif unit.unit_type == "PART_MOBIL":
        text = "[PART MOBIL]"
    else:
        text = "[BAWA RADIATOR SAJA]"
    nama = unit.nama_barang or unit.tipe_radiator
    if nama:
        text += f" {nama}"
    if unit.label_radiator:
        text += f" {unit.label_radiator}"
    if unit.nama_barang and unit.tipe_radiator:
        text += f" ({unit.tipe_radiator})"
    return text
