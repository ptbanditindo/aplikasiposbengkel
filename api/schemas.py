"""Skema Pydantic (kontrak REST API).

Ref: PRD BAB 5.1.

Kompatibel dengan Pydantic v1 maupun v2:
- Server desktop memakai v2 (requirements.txt).
- APK Android memakai v1 karena pydantic-core (Rust) tidak tersedia di Chaquopy.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

import pydantic
from pydantic import BaseModel, Field

PYDANTIC_V2 = pydantic.VERSION.startswith("2.")

if PYDANTIC_V2:
    from typing import Annotated

    from pydantic import ConfigDict, PlainSerializer

    def _format_money(value: Any) -> str:
        return f"{Decimal(value):.2f}"

    Money = Annotated[
        Decimal,
        PlainSerializer(_format_money, return_type=str, when_used="json"),
    ]
    ZERO_MONEY: Any = Decimal("0.00")

    class CompatBase(BaseModel):
        pass

    class ORMModel(CompatBase):
        model_config = ConfigDict(from_attributes=True)

    def _pattern(regex: str) -> Dict[str, Any]:
        return {"pattern": regex}

else:  # Pydantic v1

    class Money(str):
        """Decimal uang yang diserialisasi sebagai string dua desimal."""

        @classmethod
        def __get_validators__(cls):
            yield cls.validate

        @classmethod
        def validate(cls, value: Any) -> "Money":
            if isinstance(value, Money):
                return value
            return cls(f"{Decimal(value):.2f}")

        @classmethod
        def __modify_schema__(cls, field_schema: Dict[str, Any]) -> None:
            field_schema.update(type="string", example="0.00")

    ZERO_MONEY = Money("0.00")

    class CompatBase(BaseModel):
        class Config:
            orm_mode = True

        @classmethod
        def model_validate(cls, obj: Any, **_kwargs: Any):
            if isinstance(obj, dict):
                return cls.parse_obj(obj)
            return cls.from_orm(obj)

        def model_dump(self, **kwargs: Any) -> Dict[str, Any]:
            return self.dict(**kwargs)

    class ORMModel(CompatBase):
        pass

    def _pattern(regex: str) -> Dict[str, Any]:
        return {"regex": regex}


# --- CUSTOMER & UNIT ---
class CustomerCreate(CompatBase):
    nama: str = Field(..., min_length=2, max_length=255)
    nomor_hp: str = Field(..., max_length=64)
    alamat: Optional[str] = Field(default=None, max_length=500)


class CustomerOut(ORMModel):
    id: int
    nama: str
    nomor_hp: str
    alamat: Optional[str] = None
    created_at: datetime


class UnitCreate(CompatBase):
    customer_id: int = Field(..., gt=0)
    unit_type: str = Field(..., **_pattern("^(MOBIL|RADIATOR_ONLY)$"))
    nopol: Optional[str] = Field(default=None, max_length=32)
    jenis_mobil: Optional[str] = Field(default=None, max_length=255)
    tahun_mobil: Optional[int] = Field(default=None, ge=1900, le=2100)
    tipe_radiator: Optional[str] = Field(default=None, max_length=255)
    keterangan: Optional[str] = Field(default=None, max_length=1000)


class UnitOut(ORMModel):
    id: int
    customer_id: int
    unit_type: str
    nopol: Optional[str] = None
    jenis_mobil: Optional[str] = None
    tahun_mobil: Optional[int] = None
    label_radiator: Optional[str] = None
    tipe_radiator: Optional[str] = None
    keterangan: Optional[str] = None
    deskripsi: Optional[str] = None
    created_at: datetime


class CustomerOverviewOut(CustomerOut):
    total_unit: int
    total_mobil: int
    total_radiator: int
    units: List[UnitOut]


# --- STOCK & JASA ---
class StockItemCreate(CompatBase):
    kode: Optional[str] = Field(default=None, max_length=64)
    nama: str = Field(..., min_length=2, max_length=255)
    harga_modal: Decimal = Field(default=Decimal("0.00"), ge=0)
    harga_jual: Decimal = Field(default=Decimal("0.00"), ge=0)
    jumlah: int = Field(default=0, ge=0)


class StockItemUpdate(CompatBase):
    kode: Optional[str] = Field(default=None, max_length=64)
    nama: Optional[str] = Field(default=None, min_length=2, max_length=255)
    harga_modal: Optional[Decimal] = Field(default=None, ge=0)
    harga_jual: Optional[Decimal] = Field(default=None, ge=0)
    jumlah: Optional[int] = Field(default=None, ge=0)


class StockItemOut(ORMModel):
    id: int
    kode: Optional[str] = None
    nama: str
    harga_modal: Money
    harga_jual: Money
    jumlah: int


class HargaJasaCreate(CompatBase):
    nama: str = Field(..., min_length=2, max_length=255)
    harga_standar: Decimal = Field(..., ge=0)


class HargaJasaUpdate(CompatBase):
    nama: Optional[str] = Field(default=None, min_length=2, max_length=255)
    harga_standar: Optional[Decimal] = Field(default=None, ge=0)


class HargaJasaOut(ORMModel):
    id: int
    nama: str
    harga_standar: Money


# --- TRANSAKSI POS ---
class ServiceJobInput(CompatBase):
    harga_jasa_id: Optional[int] = None
    deskripsi: str = Field(..., min_length=1, max_length=255)
    jumlah: int = Field(default=1, ge=1)
    harga: Decimal = Field(..., ge=0)


class ServicePartInput(CompatBase):
    stock_item_id: Optional[int] = None
    nama_part: str = Field(default="", max_length=255)
    jumlah: int = Field(default=1, ge=1)
    harga_satuan: Decimal = Field(..., ge=0)


class CreateServiceTransactionRequest(CompatBase):
    unit_id: int = Field(..., gt=0)
    request_id: Optional[str] = Field(default=None, min_length=8, max_length=64)
    keluhan_awal: str = Field(..., min_length=1, max_length=2000)
    catatan_pengerjaan: Optional[str] = Field(default=None, max_length=2000)
    diskon: Decimal = Field(default=Decimal("0.00"), ge=0)
    metode_bayar: str = Field(default="CASH", **_pattern("^(CASH|TRANSFER)$"))
    bayar: Decimal = Field(default=Decimal("0.00"), ge=0)
    bergaransi: bool = True
    garansi_bulan: int = Field(default=1, ge=1, le=120)
    garansi_sampai: Optional[date] = None
    catatan_garansi: Optional[str] = Field(default=None, max_length=1000)
    izinkan_stok_minus: bool = False
    jobs: List[ServiceJobInput] = Field(default_factory=list)
    parts: List[ServicePartInput] = Field(default_factory=list)


class ServiceJobOut(ORMModel):
    id: int
    deskripsi: str
    jumlah: int
    harga: Money
    subtotal: Money


class ServicePartOut(ORMModel):
    id: int
    nama_part: str
    jumlah: int
    harga_satuan: Money
    subtotal: Money


class ServiceRecordOut(ORMModel):
    id: int
    no_nota: str
    waktu_service: datetime
    unit_id: int
    customer_id: int
    customer_nama: str
    customer_hp: str
    unit_deskripsi: str
    keluhan_awal: str
    biaya_jasa: Money
    total_part: Money
    diskon: Money
    total_servis: Money
    metode_bayar: str
    bayar: Money
    kembalian: Money
    bergaransi: bool
    garansi_sampai: Optional[date] = None
    catatan_garansi: Optional[str] = None
    status_klaim: str
    tanggal_klaim: Optional[date] = None
    garansi_aktif: bool
    warranty_status: str
    jumlah_item: int = 0
    laba_kotor: Money = ZERO_MONEY


class ReceiptOut(ORMModel):
    id: int
    no_nota: str
    waktu_service: datetime
    customer_nama: str
    customer_hp: str
    unit_deskripsi: str
    keluhan_awal: str
    catatan_pengerjaan: Optional[str] = None
    biaya_jasa: Money
    total_part: Money
    diskon: Money
    total_servis: Money
    metode_bayar: str
    bayar: Money
    kembalian: Money
    bergaransi: bool
    garansi_sampai: Optional[date] = None
    catatan_garansi: Optional[str] = None
    status_klaim: str
    tanggal_klaim: Optional[date] = None
    garansi_aktif: bool
    warranty_status: str
    jobs: List[ServiceJobOut] = Field(default_factory=list)
    parts: List[ServicePartOut] = Field(default_factory=list)
    bengkel_nama: str
    bengkel_tagline: str
    bengkel_alamat: str
    bengkel_telepon: str
    bengkel_wa: str
    bengkel_bank_nama: str
    bengkel_no_rekening: str
    bengkel_atas_nama: str
    printer_paper_width: int
    struk_58: List[str]
    struk_80: List[str]
    escpos_58_base64: str
    escpos_80_base64: str


class TransactionResponse(CompatBase):
    record: ServiceRecordOut
    receipt: ReceiptOut
    warnings: List[str] = Field(default_factory=list)
    laba_kotor: Money


# --- LAPORAN ---
class DailySummaryOut(CompatBase):
    tanggal: date
    jumlah_transaksi: int
    jumlah_unit_servis: int
    total_omset: Money
    total_cash: Money
    total_transfer: Money
    total_jasa: Money
    total_part: Money
    total_diskon: Money
    laba_kotor: Money
    garansi_aktif: int


class DailyReportOut(DailySummaryOut):
    transaksi: List[ServiceRecordOut] = Field(default_factory=list)


class PeriodReportOut(CompatBase):
    start: date
    end: date
    jumlah_transaksi: int
    jumlah_unit_servis: int
    total_omset: Money
    total_cash: Money
    total_transfer: Money
    total_jasa: Money
    total_part: Money
    total_diskon: Money
    laba_kotor: Money
    garansi_aktif: int
    transaksi: List[ServiceRecordOut] = Field(default_factory=list)
    harian: List[DailySummaryOut] = Field(default_factory=list)


class SoldPartOut(CompatBase):
    id: int
    service_record_id: int
    no_nota: str
    waktu_service: datetime
    nama_part: str
    jumlah: int
    harga_satuan: Money
    subtotal: Money
    customer_nama: str
    unit_deskripsi: str


class SoldPartsReportOut(CompatBase):
    jumlah_penjualan: int
    total_qty: int
    total_nilai: Money
    items: List[SoldPartOut] = Field(default_factory=list)


# --- KONFIGURASI PUBLIK ---
class BengkelInfoIn(CompatBase):
    nama: str = Field(..., min_length=2, max_length=255)
    tagline: str = Field(default="", max_length=255)
    alamat: str = Field(default="", max_length=500)
    telepon: str = Field(default="", max_length=64)
    wa: str = Field(default="", max_length=64)
    bank_nama: str = Field(default="", max_length=255)
    no_rekening: str = Field(default="", max_length=64)
    atas_nama: str = Field(default="", max_length=255)


class BengkelInfoOut(CompatBase):
    nama: str
    tagline: str
    alamat: str
    telepon: str
    wa: str
    bank_nama: str
    no_rekening: str
    atas_nama: str


class TelegramSettingsIn(CompatBase):
    enabled: bool = False
    jam: str = Field(default="21:00", **_pattern(r"^([01]\d|2[0-3]):[0-5]\d$"))
    chat_id: str = Field(default="", max_length=64)
    bot_token: str = Field(default="", max_length=200)


class TelegramInfoOut(CompatBase):
    enabled: bool
    jam: str
    chat_id: str
    configured: bool
    needs_reconfig: bool = False
    last_sent_at: Optional[str] = None
    last_error: Optional[str] = None


class PrinterInfoOut(CompatBase):
    paper_width: int
    encoding: str
    auto_cut: bool


class ConfigOut(CompatBase):
    version: str
    bengkel: BengkelInfoOut
    telegram: TelegramInfoOut
    printer: PrinterInfoOut
    default_garansi_bulan: int
    garansi_syarat: str
    metode_bayar: List[str]
    keluhan_presets: List[str]
    admin_token_required: bool
