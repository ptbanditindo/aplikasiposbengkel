"""Model SQLAlchemy 2.0 - 7 entitas relasional.

Ref: PRD BAB 4.2.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nama: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    nomor_hp: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    alamat: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    units: Mapped[List["VehicleOrUnit"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )


class VehicleOrUnit(Base):
    __tablename__ = "vehicle_or_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    unit_type: Mapped[str] = mapped_column(String(32), nullable=False)  # MOBIL | RADIATOR_ONLY
    nopol: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    jenis_mobil: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tahun_mobil: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    label_radiator: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    tipe_radiator: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    keterangan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    customer: Mapped["Customer"] = relationship(back_populates="units")
    service_records: Mapped[List["ServiceRecord"]] = relationship(back_populates="unit")


class StockItem(Base):
    __tablename__ = "stock_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kode: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True)
    nama: Mapped[str] = mapped_column(String(255), nullable=False)
    harga_modal: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    harga_jual: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    jumlah: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class HargaJasa(Base):
    __tablename__ = "harga_jasa"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nama: Mapped[str] = mapped_column(String(255), nullable=False)
    harga_standar: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class NotaCounter(Base):
    """Counter nomor nota harian yang dinaikkan secara atomik."""

    __tablename__ = "nota_counters"

    tanggal: Mapped[str] = mapped_column(String(8), primary_key=True)
    terakhir: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ServiceRecord(Base):
    __tablename__ = "service_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[int] = mapped_column(
        ForeignKey("vehicle_or_units.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    no_nota: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    request_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    waktu_service: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, index=True
    )
    keluhan_awal: Mapped[str] = mapped_column(Text, nullable=False)
    catatan_pengerjaan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    biaya_jasa: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    total_part: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    diskon: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    total_servis: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    metode_bayar: Mapped[str] = mapped_column(
        String(32), default="CASH", nullable=False
    )  # CASH | TRANSFER
    bayar: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    kembalian: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    bergaransi: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    garansi_sampai: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    catatan_garansi: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_klaim: Mapped[str] = mapped_column(
        String(32), default="Belum claim", nullable=False
    )
    tanggal_klaim: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    unit: Mapped["VehicleOrUnit"] = relationship(back_populates="service_records")
    jobs: Mapped[List["ServiceJob"]] = relationship(
        back_populates="service_record", cascade="all, delete-orphan"
    )
    parts: Mapped[List["ServicePart"]] = relationship(
        back_populates="service_record", cascade="all, delete-orphan"
    )


class ServiceJob(Base):
    __tablename__ = "service_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_record_id: Mapped[int] = mapped_column(
        ForeignKey("service_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    harga_jasa_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("harga_jasa.id", ondelete="SET NULL"), nullable=True
    )
    deskripsi: Mapped[str] = mapped_column(String(255), nullable=False)
    jumlah: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    harga: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)  # harga deal
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    service_record: Mapped["ServiceRecord"] = relationship(back_populates="jobs")


class ServicePart(Base):
    __tablename__ = "service_parts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_record_id: Mapped[int] = mapped_column(
        ForeignKey("service_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stock_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("stock_items.id", ondelete="SET NULL"), nullable=True
    )
    nama_part: Mapped[str] = mapped_column(String(255), nullable=False)
    jumlah: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    harga_satuan: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)  # harga deal
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # Snapshot modal saat penjualan agar laba kotor historis tidak berubah
    # ketika master stok diubah/dihapus.
    harga_modal: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 2), nullable=True
    )

    service_record: Mapped["ServiceRecord"] = relationship(back_populates="parts")
    stock_item: Mapped[Optional["StockItem"]] = relationship()


class AppSetting(Base):
    """Pengaturan aplikasi berbentuk key-value (menimpa default .env)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )
