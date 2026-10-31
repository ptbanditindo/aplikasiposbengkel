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
    Index,
    Integer,
    Numeric,
    String,
    Text,
    event,
    text,
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
    # Izin mengirim pesan WhatsApp (Tahap 12). Dapat dimatikan per pelanggan.
    wa_consent: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
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
    label_radiator: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, unique=True, index=True
    )
    tipe_radiator: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    keterangan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Soft delete: unit disembunyikan dari pilihan, riwayat nota tetap ada.
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
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
    # 0 = Nonaktif; bulan interval servis berkala (P-10).
    interval_servis_bulan: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
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
    # 0 = Nonaktif; bulan interval servis berkala (Tahap 13).
    interval_servis_bulan: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
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
    # LUNAS | BELUM_LUNAS. Nota VOID selalu dianggap lunas untuk perhitungan
    # piutang; status void dibaca dari kolom `status`.
    status_bayar: Mapped[str] = mapped_column(
        String(16), default="LUNAS", nullable=False, index=True
    )
    # LUNAS | DP | KREDIT (jenis kesepakatan pembayaran saat nota dibuat).
    jenis_bayar: Mapped[str] = mapped_column(
        String(16), default="LUNAS", nullable=False
    )
    jatuh_tempo: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    # Rencana pembayaran untuk nota kredit (null bila bukan kredit).
    rencana_bayar: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    total_dibayar: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    bergaransi: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    garansi_sampai: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    catatan_garansi: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_klaim: Mapped[str] = mapped_column(
        String(32), default="Belum claim", nullable=False
    )
    tanggal_klaim: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # NORMAL | VOID. Nota VOID tetap tersimpan sebagai riwayat, tetapi tidak
    # dihitung sebagai penjualan pada laporan.
    status: Mapped[str] = mapped_column(
        String(16), default="NORMAL", nullable=False, index=True
    )
    void_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    voided_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Akumulasi retur (nilai deal) agar laporan tidak perlu memuat seluruh
    # baris retur untuk setiap nota.
    total_retur: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    total_retur_jasa: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    total_retur_part: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    retur_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
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
    returns: Mapped[List["ServiceReturn"]] = relationship(
        back_populates="service_record",
        cascade="all, delete-orphan",
        order_by="ServiceReturn.created_at",
    )
    payments: Mapped[List["ServicePayment"]] = relationship(
        back_populates="service_record",
        cascade="all, delete-orphan",
        order_by="ServicePayment.waktu, ServicePayment.id",
    )
    whatsapp_logs: Mapped[List["WhatsAppLog"]] = relationship(
        back_populates="service_record",
        cascade="all, delete-orphan",
        order_by="WhatsAppLog.created_at, WhatsAppLog.id",
    )


class ServicePayment(Base):
    """Buku pembayaran nota: DP, pelunasan, dan refund (append-only)."""

    __tablename__ = "service_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_record_id: Mapped[int] = mapped_column(
        ForeignKey("service_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # DP | PELUNASAN | REFUND (refund bernilai negatif)
    jenis: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    metode: Mapped[str] = mapped_column(String(16), nullable=False)  # CASH | TRANSFER
    nominal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    waktu: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, index=True
    )
    operator: Mapped[str] = mapped_column(String(64), default="Kasir", nullable=False)
    catatan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    service_record: Mapped["ServiceRecord"] = relationship(back_populates="payments")


class WhatsAppLog(Base):
    """Catatan upaya membuka WhatsApp (append-only, Tahap 12).

    Aplikasi tidak mengirim pesan sendiri; baris ini mencatat apakah jendela
    WhatsApp dibuka, dibatalkan, atau nomor tidak tersedia.
    """

    __tablename__ = "wa_message_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_record_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("service_records.id", ondelete="CASCADE"), nullable=True, index=True
    )
    customer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    nomor_masked: Mapped[str] = mapped_column(String(32), nullable=False)
    # struk | followup | garansi | piutang
    jenis: Mapped[str] = mapped_column(
        String(16), default="struk", nullable=False
    )
    # DIBUKA | DIBATALKAN | TIDAK_TERSEDIA
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    pesan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    operator: Mapped[str] = mapped_column(String(64), default="Kasir", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, index=True
    )

    service_record: Mapped[Optional["ServiceRecord"]] = relationship(
        back_populates="whatsapp_logs"
    )


class FollowupItem(Base):
    """Pengingat follow-up aktif per pelanggan dan jenis (Tahap 13)."""

    __tablename__ = "followup_items"
    __table_args__ = (
        Index(
            "ux_followup_items_active",
            "jenis",
            "customer_id",
            unique=True,
            sqlite_where=text("status != 'ARSIP'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # prospek | servis_berkala | garansi | piutang
    jenis: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unit_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("vehicle_or_units.id", ondelete="SET NULL"), nullable=True
    )
    service_record_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("service_records.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    judul: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    jatuh_tempo: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(24), default="BARU", nullable=False, index=True
    )
    penanggung_jawab: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    diambil_pada: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    followup_terakhir: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    janji_bayar: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    tanggal_service: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    alasan_arsip: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    customer: Mapped["Customer"] = relationship()
    unit: Mapped[Optional["VehicleOrUnit"]] = relationship()
    service_record: Mapped[Optional["ServiceRecord"]] = relationship()
    events: Mapped[List["FollowupEvent"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="FollowupEvent.created_at, FollowupEvent.id",
    )


class FollowupEvent(Base):
    """Riwayat perpindahan status follow-up (append-only)."""

    __tablename__ = "followup_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("followup_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    to_status: Mapped[str] = mapped_column(String(24), nullable=False)
    alasan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    operator: Mapped[str] = mapped_column(String(64), default="Kasir", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, index=True
    )

    item: Mapped["FollowupItem"] = relationship(back_populates="events")


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
    jumlah_retur: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Snapshot interval saat nota disimpan; perubahan master tidak mengubahnya.
    interval_servis_bulan: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

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
    # True bila modal diisi dari backfill migrasi (estimasi harga master),
    # bukan snapshot saat transaksi terjadi.
    harga_modal_estimasi: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    jumlah_retur: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Snapshot interval servis berkala part saat nota disimpan (P-10).
    interval_servis_bulan: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    service_record: Mapped["ServiceRecord"] = relationship(back_populates="parts")
    stock_item: Mapped[Optional["StockItem"]] = relationship()


class ServiceReturn(Base):
    """Satu peristiwa retur untuk sebuah nota (sebagian atau seluruh item)."""

    __tablename__ = "service_returns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_record_id: Mapped[int] = mapped_column(
        ForeignKey("service_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    alasan: Mapped[str] = mapped_column(Text, nullable=False)
    oleh: Mapped[str] = mapped_column(String(64), default="Kasir", nullable=False)
    total_nilai: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    service_record: Mapped["ServiceRecord"] = relationship(back_populates="returns")
    items: Mapped[List["ServiceReturnItem"]] = relationship(
        back_populates="service_return",
        cascade="all, delete-orphan",
        order_by="ServiceReturnItem.id",
    )


class ServiceReturnItem(Base):
    """Rincian item yang diretur: jasa atau sparepart (snapshot nilai deal)."""

    __tablename__ = "service_return_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_return_id: Mapped[int] = mapped_column(
        ForeignKey("service_returns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    service_part_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("service_parts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    service_job_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("service_jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    stock_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("stock_items.id", ondelete="SET NULL"), nullable=True
    )
    nama_item: Mapped[str] = mapped_column(String(255), nullable=False)
    jumlah: Mapped[int] = mapped_column(Integer, nullable=False)
    harga_satuan: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    harga_modal: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    service_return: Mapped["ServiceReturn"] = relationship(back_populates="items")


class StockMovement(Base):
    """Ledger pergerakan stok; jumlah positif = stok bertambah."""

    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("stock_items.id", ondelete="SET NULL"), nullable=True, index=True
    )
    nama_item: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    jenis: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    jumlah: Mapped[int] = mapped_column(Integer, nullable=False)
    alasan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    oleh: Mapped[str] = mapped_column(String(64), default="Kasir", nullable=False)
    service_record_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("service_records.id", ondelete="SET NULL"), nullable=True, index=True
    )
    service_return_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("service_returns.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class AppSetting(Base):
    """Pengaturan aplikasi berbentuk key-value (menimpa default .env)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class AuditEvent(Base):
    """Jejak audit append-only untuk tindakan penting (ARC-15).

    Tidak ada endpoint ubah/hapus; listener di bawah menolak perubahan agar
    riwayat tetap utuh walau ada kode yang mencoba memodifikasi baris.
    """

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operator_id: Mapped[str] = mapped_column(String(64), nullable=False)
    operator_role: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reference_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reference_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default=""
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, index=True
    )


def _reject_audit_change(_mapper, _connection, target):  # pragma: no cover - guard
    raise ValueError(
        f"Audit trail bersifat tetap; perubahan {target!r} ditolak."
    )


event.listen(AuditEvent, "before_update", _reject_audit_change)
event.listen(AuditEvent, "before_delete", _reject_audit_change)

# Buku pembayaran tidak boleh diubah/dihapus diam-diam; koreksi memakai
# refund/void yang tercatat sebagai baris baru.
event.listen(ServicePayment, "before_update", _reject_audit_change)
event.listen(ServicePayment, "before_delete", _reject_audit_change)

# Log WhatsApp juga tidak boleh diubah/dihapus; status baru ditambahkan.
event.listen(WhatsAppLog, "before_update", _reject_audit_change)
event.listen(WhatsAppLog, "before_delete", _reject_audit_change)

# Riwayat perpindahan follow-up tidak boleh diubah/dihapus.
event.listen(FollowupEvent, "before_update", _reject_audit_change)
event.listen(FollowupEvent, "before_delete", _reject_audit_change)
