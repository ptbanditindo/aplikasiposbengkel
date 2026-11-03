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
    do_not_contact: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    units: Mapped[List["VehicleOrUnit"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )


class Supplier(Base):
    """Supplier/reseller barang sparepart."""

    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nama: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    nomor_hp: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    alamat: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    catatan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    items: Mapped[List["SupplierItem"]] = relationship(
        back_populates="supplier", cascade="all, delete-orphan"
    )


class SupplierItem(Base):
    """Barang stok yang disuplai oleh seorang supplier."""

    __tablename__ = "supplier_items"
    __table_args__ = (
        Index(
            "ux_supplier_items_pair",
            "supplier_id",
            "stock_item_id",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stock_item_id: Mapped[int] = mapped_column(
        ForeignKey("stock_items.id", ondelete="CASCADE"), nullable=False, index=True
    )

    supplier: Mapped["Supplier"] = relationship(back_populates="items")
    stock_item: Mapped["StockItem"] = relationship()


class SupplierFollowup(Base):
    """Status follow up reseller per pasangan supplier + barang stok."""

    __tablename__ = "supplier_followups"
    __table_args__ = (
        Index(
            "ux_supplier_followups_pair",
            "supplier_id",
            "stock_item_id",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False
    )
    stock_item_id: Mapped[int] = mapped_column(
        ForeignKey("stock_items.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    catatan: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class VehicleOrUnit(Base):
    __tablename__ = "vehicle_or_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # MOBIL | MOTOR_LENGKAP | PART_MOBIL | PART_MOTOR |
    # RADIATOR_ONLY (legacy) | SPAREPART (unit walk-in internal)
    unit_type: Mapped[str] = mapped_column(String(32), nullable=False)
    nopol: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    # Merek/model untuk unit lengkap; merek/ukuran untuk part.
    jenis_mobil: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tahun_mobil: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    label_radiator: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, unique=True, index=True
    )
    # Tipe/ukuran part. Nama kolom dipertahankan untuk data lama.
    tipe_radiator: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Field bebas khusus part: nama barang, nomor seri, kondisi, asal kendaraan.
    nama_barang: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    nomor_seri: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    kondisi: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    kendaraan_asal: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
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
    # NULL = ikut batas bawaan Pengaturan; 0 = nonaktif; >0 = batas item.
    stok_minimum: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    barcode_rows: Mapped[List["StockBarcode"]] = relationship(
        back_populates="stock_item",
        cascade="all, delete-orphan",
        order_by="StockBarcode.id",
    )

    @property
    def barcodes(self) -> List[str]:
        return [row.barcode for row in self.barcode_rows]


class StockBarcode(Base):
    """Alias barcode/QR untuk satu barang stok.

    Satu nilai barcode hanya boleh menunjuk satu barang. `stock_items.kode`
    tetap menjadi kode utama dan ikut dicari saat scan.
    """

    __tablename__ = "stock_barcodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_item_id: Mapped[int] = mapped_column(
        ForeignKey("stock_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    barcode: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    stock_item: Mapped["StockItem"] = relationship(back_populates="barcode_rows")


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


class Employee(Base):
    """Karyawan operasional: mekanik, kasir, atau keduanya."""

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nama: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    peran: Mapped[str] = mapped_column(
        String(16), default="MEKANIK", nullable=False, index=True
    )  # MEKANIK | KASIR | KEDUANYA
    # KOMISI | GAJI | KOMISI_GAJI
    jenis_imbalan: Mapped[str] = mapped_column(
        String(16), default="KOMISI", nullable=False
    )
    gaji_bulanan: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    nomor_hp: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    tanggal_masuk: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    catatan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    komisi_mode: Mapped[str] = mapped_column(
        String(16), default="PERSEN", nullable=False
    )  # PERSEN | NOMINAL
    komisi_basis: Mapped[str] = mapped_column(
        String(16), default="KEDUANYA", nullable=False
    )  # BARANG | JASA | KEDUANYA
    komisi_nilai: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    # Tarif terpisah: barang dihitung dari margin (jual - modal), jasa dari nilai jasa.
    komisi_barang_nilai: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    komisi_jasa_nilai: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    # TANGGAL | MINGGUAN | DUA_MINGGUAN | TIGA_MINGGUAN | BULANAN
    payroll_period: Mapped[str] = mapped_column(
        String(16), default="BULANAN", nullable=False
    )
    payroll_tanggal: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # 0=Senin ... 6=Minggu untuk jadwal mingguan/2 mingguan/3 mingguan.
    payroll_hari: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bank_nama: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    bank_nomor: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    bank_atas_nama: Mapped[str] = mapped_column(
        String(255), default="", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class EmployeeDebt(Base):
    """Hutang/uang muka karyawan yang dipotong dari gaji atau komisi."""

    __tablename__ = "employee_debts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True
    )
    nama_karyawan: Mapped[str] = mapped_column(String(255), nullable=False)
    tanggal: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    nominal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    terbayar: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    keterangan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    employee: Mapped[Optional["Employee"]] = relationship()


class SalaryPayment(Base):
    """Pembayaran gaji aktual per karyawan dan periode.

    Nama karyawan disimpan sebagai snapshot agar riwayat tetap terbaca
    setelah karyawan dihapus.
    """

    __tablename__ = "salary_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True
    )
    nama_karyawan: Mapped[str] = mapped_column(String(255), nullable=False)
    periode: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    tanggal: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    cycle_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    nominal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    potongan_hutang: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    bonus: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    bonus_keterangan: Mapped[str] = mapped_column(
        String(255), default="", nullable=False
    )
    cicilan_hutang: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    metode: Mapped[str] = mapped_column(
        String(16), default="CASH", nullable=False
    )  # CASH | TRANSFER
    catatan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    employee: Mapped[Optional["Employee"]] = relationship()


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
    # LUNAS | KREDIT (DP hanya pada nota lama sebelum jenis ini dihapus).
    jenis_bayar: Mapped[str] = mapped_column(
        String(16), default="LUNAS", nullable=False
    )
    jatuh_tempo: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    # Waktu pengingat piutang dikirim; dikosongkan saat jatuh tempo diubah.
    diingatkan_pada: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    piutang_reminder_ke: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    piutang_next_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    piutang_perlu_telepon: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
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
    # Penjualan sparepart tanpa servis dan garansi khusus barang.
    sparepart_only: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    garansi_tukar_aktif: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    garansi_tukar_hari: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    garansi_barang_aktif: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    garansi_barang_nilai: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    garansi_barang_satuan: Mapped[str] = mapped_column(
        String(8), default="HARI", nullable=False
    )
    garansi_barang_sampai: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True
    )
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

    cashier_employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cashier_employee: Mapped[Optional["Employee"]] = relationship(
        foreign_keys=[cashier_employee_id]
    )
    mechanics: Mapped[List["ServiceRecordMechanic"]] = relationship(
        back_populates="service_record", cascade="all, delete-orphan"
    )
    commissions: Mapped[List["ServiceRecordCommission"]] = relationship(
        back_populates="service_record", cascade="all, delete-orphan"
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


class ServiceRecordMechanic(Base):
    """Mekanik yang mengerjakan satu nota."""

    __tablename__ = "service_record_mechanics"
    __table_args__ = (
        Index(
            "ux_service_record_mechanics_pair",
            "service_record_id",
            "employee_id",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_record_id: Mapped[int] = mapped_column(
        ForeignKey("service_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    urutan: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    service_record: Mapped["ServiceRecord"] = relationship(back_populates="mechanics")
    employee: Mapped["Employee"] = relationship()


class ServiceRecordCommission(Base):
    """Nominal komisi manual per nota dan karyawan."""

    __tablename__ = "service_record_commissions"
    __table_args__ = (
        Index(
            "ux_service_record_commissions_pair",
            "service_record_id",
            "employee_id",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_record_id: Mapped[int] = mapped_column(
        ForeignKey("service_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nominal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    service_record: Mapped["ServiceRecord"] = relationship(back_populates="commissions")
    employee: Mapped["Employee"] = relationship()


class ServicePayment(Base):
    """Buku pembayaran nota: uang muka, pelunasan, dan refund (append-only)."""

    __tablename__ = "service_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_record_id: Mapped[int] = mapped_column(
        ForeignKey("service_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # UANG_MUKA | PELUNASAN | REFUND (DP hanya pada nota lama)
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


class PengerjaanNota(Base):
    """Penanda unit masih di bengkel untuk follow-up kendaraan selesai.

    Satu baris per nota. Dibuat saat kasir menyalakan opsi "Unit ditinggal"
    pada pencatatan servis, dan ditutup saat unit sudah diambil pelanggan.
    """

    __tablename__ = "pengerjaan_nota"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_record_id: Mapped[int] = mapped_column(
        ForeignKey("service_records.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    unit_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("vehicle_or_units.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    customer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # SEDANG_DIKERJAKAN | MENUNGGU_SPAREPART | MENUNGGU_PERSETUJUAN |
    # SELESAI_SIAP_DIAMBIL | SUDAH_DIAMBIL
    status_pengerjaan: Mapped[str] = mapped_column(
        String(24),
        default="SEDANG_DIKERJAKAN",
        nullable=False,
        index=True,
    )
    janji_ambil: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    diambil_pada: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    dibuat_pada: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    diubah_pada: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )
    diubah_oleh: Mapped[str] = mapped_column(
        String(64), default="Kasir", nullable=False
    )

    service_record: Mapped["ServiceRecord"] = relationship()
    unit: Mapped[Optional["VehicleOrUnit"]] = relationship()
    customer: Mapped[Optional["Customer"]] = relationship()
    events: Mapped[List["PengerjaanNotaEvent"]] = relationship(
        back_populates="pengerjaan",
        cascade="all, delete-orphan",
        order_by="PengerjaanNotaEvent.created_at, PengerjaanNotaEvent.id",
    )


class PengerjaanNotaEvent(Base):
    """Riwayat perubahan status pengerjaan unit."""

    __tablename__ = "pengerjaan_nota_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pengerjaan_id: Mapped[int] = mapped_column(
        ForeignKey("pengerjaan_nota.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    to_status: Mapped[str] = mapped_column(String(24), nullable=False)
    operator: Mapped[str] = mapped_column(String(64), default="Pemilik", nullable=False)
    catatan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, index=True
    )

    pengerjaan: Mapped["PengerjaanNota"] = relationship(back_populates="events")


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
    followup_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("followup_items.id", ondelete="SET NULL"), nullable=True, index=True
    )
    customer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    supplier_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    nomor_masked: Mapped[str] = mapped_column(String(32), nullable=False)
    # struk | followup | garansi | piutang | pengerjaan
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
    supplier: Mapped[Optional["Supplier"]] = relationship()


class FollowupItem(Base):
    """Pengingat follow-up aktif per pelanggan dan jenis (Tahap 13)."""

    __tablename__ = "followup_items"
    __table_args__ = (
        Index(
            "ux_followup_items_key_active",
            "item_key",
            unique=True,
            sqlite_where=text("status != 'ARSIP' AND item_key IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # prospek | servis_berkala | garansi | piutang
    jenis: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    item_key: Mapped[Optional[str]] = mapped_column(String(180), nullable=True, index=True)
    stage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    interval_bulan: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    item_nama: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    item_kind: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    reference_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    no_response_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    perlu_telepon: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tunda_sampai: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
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
    followup_terakhir: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    janji_bayar: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    tanggal_service: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    alasan_arsip: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    cycle_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
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
    jenis: Mapped[str] = mapped_column(
        String(16), default="RETUR", nullable=False
    )
    ganti_nama: Mapped[str] = mapped_column(
        String(255), default="", nullable=False
    )
    ganti_jumlah: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    ganti_service_part_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("service_parts.id", ondelete="SET NULL"), nullable=True
    )
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


class OwnerIdentity(Base):
    """Identitas owner premium tunggal per instalasi (K-06, K-22).

    Kunci privat owner disimpan terenkripsi dengan rahasia lokal; salinan
    pemulihan memakai kode pemulihan yang hanya ditampilkan sekali.
    """

    __tablename__ = "owner_identity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    owner_id: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    public_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    private_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    private_key_salt: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    recovery_blob: Mapped[str] = mapped_column(Text, nullable=False, default="")
    recovery_salt: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    recovery_code_hash: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    rotated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class EmployeeAccount(Base):
    """Akun karyawan premium: kredensial, peran dasar, izin tambahan (K-07)."""

    __tablename__ = "employee_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    nama: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    role_base: Mapped[str] = mapped_column(String(16), nullable=False, default="KASIR")
    store_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    extra_permissions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    password_hash: Mapped[str] = mapped_column(Text, nullable=False, default="")
    password_salt: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    password_iterations: Mapped[int] = mapped_column(
        Integer, nullable=False, default=120_000
    )
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    pin_hash: Mapped[str] = mapped_column(Text, nullable=False, default="")
    pin_salt: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    pin_iterations: Mapped[int] = mapped_column(
        Integer, nullable=False, default=120_000
    )
    aktif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lock_until: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    permission_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class PermissionAudit(Base):
    """Riwayat perubahan akun/izin; append-only (K-07)."""

    __tablename__ = "permission_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    employee_account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employee_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    username: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    before_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    after_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, index=True
    )


class LoginGuard(Base):
    """Pembatas percobaan login per cakupan (username hub / owner+username)."""

    __tablename__ = "login_guards"

    scope_key: Mapped[str] = mapped_column(String(200), primary_key=True)
    failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lock_until: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class License(Base):
    """Lisensi langganan premium lokal dengan token bertanda tangan (K-11)."""

    __tablename__ = "licenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    plan: Mapped[str] = mapped_column(String(16), nullable=False, default="premium")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    provider: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    device_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    token: Mapped[str] = mapped_column(Text, nullable=False, default="")
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    max_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class Device(Base):
    """Perangkat terdaftar premium; kunci publik saja (K-12, K-15)."""

    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    nama: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="owner")
    employee_account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employee_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    public_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked_reason: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    release_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class DeviceStore(Base):
    """Toko yang ditugaskan ke satu perangkat (K-12, K-22)."""

    __tablename__ = "device_stores"

    device_id: Mapped[str] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True
    )
    store_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class StoreHub(Base):
    """Tepat satu hub uang per toko (K-12)."""

    __tablename__ = "store_hubs"

    store_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(32), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    previous_device_id: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    quarantine: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class HubAudit(Base):
    """Audit perpindahan flag hub."""

    __tablename__ = "hub_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    from_device_id: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    to_device_id: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    actor: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class PermissionSnapshot(Base):
    """Salinan izin bertanda tangan owner untuk perangkat (K-07, K-15)."""

    __tablename__ = "permission_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_account_id: Mapped[int] = mapped_column(
        ForeignKey("employee_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        Index("ux_permission_snapshot_account_version", "employee_account_id", "version", unique=True),
    )


class StoreKey(Base):
    """Kunci toko yang dibungkus untuk hub; server tidak menyimpan kunci polos."""

    __tablename__ = "store_keys"

    store_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    wrapped_key: Mapped[str] = mapped_column(Text, nullable=False)
    hub_device_id: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    owner_signature: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    rotated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class DeviceKeyWrap(Base):
    """Kunci toko yang dibungkus untuk tiap perangkat (K-22)."""

    __tablename__ = "device_key_wraps"

    store_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    wrapped_key: Mapped[str] = mapped_column(Text, nullable=False)
    owner_signature: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    rotated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class RelayEnvelope(Base):
    """Amplop delta terenkripsi end-to-end; server tidak dapat membacanya."""

    __tablename__ = "relay_envelopes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sender_device_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    recipient_device_id: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    hlc_wall: Mapped[int] = mapped_column(Integer, nullable=False)
    hlc_counter: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True
    )
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    nonce: Mapped[str] = mapped_column(String(64), nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    acked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ux_relay_device_seq", "sender_device_id", "seq", unique=True),
    )


class RelayAck(Base):
    """Konfirmasi penerima agar amplop boleh dihapus (K-13)."""

    __tablename__ = "relay_acks"

    envelope_id: Mapped[str] = mapped_column(
        ForeignKey("relay_envelopes.id", ondelete="CASCADE"), primary_key=True
    )
    device_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    acked_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class RelaySnapshot(Base):
    """Snapshot terenkripsi dari hub; disajikan sebagai ciphertext saja."""

    __tablename__ = "relay_snapshots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(String(32), nullable=False)
    hlc_wall: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hlc_counter: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    nonce: Mapped[str] = mapped_column(String(64), nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class OutboxItem(Base):
    """Outbox lokal per perangkat; idempoten dan tidak kedaluwarsa (K-14)."""

    __tablename__ = "outbox_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hlc_wall: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hlc_counter: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idempotency_key: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True
    )
    entity: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", index=True
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    acked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class SyncConflict(Base):
    """Konflik stok/uang yang ditandai, bukan ditimpa (K-14)."""

    __tablename__ = "sync_conflicts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    outbox_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    entity: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    detail_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, index=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class SyncPeerState(Base):
    """Penanda sinkronisasi per perangkat untuk status pendek/terkirim."""

    __tablename__ = "sync_peer_states"

    device_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    last_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class AppliedDelta(Base):
    """Penanda delta yang sudah diterapkan agar replay tidak menggandakan."""

    __tablename__ = "applied_deltas"

    idempotency_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    envelope_id: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    entity: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


def _reject_immutable_change(_mapper, _connection, target):  # pragma: no cover - guard
    raise ValueError(f"Rekaman audit bersifat tetap; perubahan {target!r} ditolak.")


event.listen(PermissionAudit, "before_update", _reject_immutable_change)
event.listen(PermissionAudit, "before_delete", _reject_immutable_change)
event.listen(HubAudit, "before_update", _reject_immutable_change)
event.listen(HubAudit, "before_delete", _reject_immutable_change)
