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

    class StrictBase(CompatBase):
        """Menolak field tak dikenal, mis. identitas operator dari frontend."""

        model_config = ConfigDict(extra="forbid")

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

    class StrictBase(CompatBase):
        class Config(CompatBase.Config):
            extra = "forbid"

    class ORMModel(CompatBase):
        pass

    def _pattern(regex: str) -> Dict[str, Any]:
        return {"regex": regex}


# --- CUSTOMER & UNIT ---
class CustomerCreate(CompatBase):
    nama: str = Field(..., min_length=2, max_length=255)
    nomor_hp: str = Field(..., max_length=64)
    alamat: Optional[str] = Field(default=None, max_length=500)
    wa_consent: bool = True


class CustomerOut(ORMModel):
    id: int
    nama: str
    nomor_hp: str
    alamat: Optional[str] = None
    wa_consent: bool = True
    created_at: datetime


class CustomerConsentIn(StrictBase):
    wa_consent: bool


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
    interval_servis_bulan: int = Field(default=0, ge=0, le=120)


class StockItemUpdate(CompatBase):
    kode: Optional[str] = Field(default=None, max_length=64)
    nama: Optional[str] = Field(default=None, min_length=2, max_length=255)
    harga_modal: Optional[Decimal] = Field(default=None, ge=0)
    harga_jual: Optional[Decimal] = Field(default=None, ge=0)
    jumlah: Optional[int] = Field(default=None, ge=0)
    interval_servis_bulan: Optional[int] = Field(default=None, ge=0, le=120)
    alasan: Optional[str] = Field(default=None, max_length=255)


class StockItemOut(ORMModel):
    id: int
    kode: Optional[str] = None
    nama: str
    harga_modal: Money
    harga_jual: Money
    jumlah: int
    interval_servis_bulan: int = 0


class HargaJasaCreate(CompatBase):
    nama: str = Field(..., min_length=2, max_length=255)
    harga_standar: Decimal = Field(..., ge=0)
    interval_servis_bulan: int = Field(default=0, ge=0, le=120)


class HargaJasaUpdate(CompatBase):
    nama: Optional[str] = Field(default=None, min_length=2, max_length=255)
    harga_standar: Optional[Decimal] = Field(default=None, ge=0)
    interval_servis_bulan: Optional[int] = Field(default=None, ge=0, le=120)


class HargaJasaOut(ORMModel):
    id: int
    nama: str
    harga_standar: Money
    interval_servis_bulan: int = 0


# --- TRANSAKSI POS ---
class ServiceJobInput(CompatBase):
    harga_jasa_id: Optional[int] = None
    deskripsi: str = Field(..., min_length=1, max_length=255)
    jumlah: int = Field(default=1, ge=1)
    harga: Decimal = Field(..., ge=0)
    interval_servis_bulan: Optional[int] = Field(default=None, ge=0, le=120)


class ServicePartInput(CompatBase):
    stock_item_id: Optional[int] = None
    nama_part: str = Field(default="", max_length=255)
    jumlah: int = Field(default=1, ge=1)
    harga_satuan: Decimal = Field(..., ge=0)
    harga_modal: Optional[Decimal] = Field(default=None, ge=0)
    interval_servis_bulan: Optional[int] = Field(default=None, ge=0, le=120)


class CreateServiceTransactionRequest(CompatBase):
    unit_id: int = Field(..., gt=0)
    request_id: Optional[str] = Field(default=None, min_length=8, max_length=64)
    keluhan_awal: str = Field(..., min_length=1, max_length=2000)
    catatan_pengerjaan: Optional[str] = Field(default=None, max_length=2000)
    diskon: Decimal = Field(default=Decimal("0.00"), ge=0)
    metode_bayar: str = Field(default="CASH", **_pattern("^(CASH|TRANSFER)$"))
    bayar: Decimal = Field(default=Decimal("0.00"), ge=0)
    jenis_bayar: str = Field(default="LUNAS", **_pattern("^(LUNAS|DP)$"))
    dp: Decimal = Field(default=Decimal("0.00"), ge=0)
    jatuh_tempo: Optional[date] = None
    bergaransi: bool = True
    garansi_bulan: int = Field(default=1, ge=1, le=120)
    garansi_sampai: Optional[date] = None
    catatan_garansi: Optional[str] = Field(default=None, max_length=1000)
    izinkan_stok_minus: bool = False
    jobs: List[ServiceJobInput] = Field(default_factory=list)
    parts: List[ServicePartInput] = Field(default_factory=list)


class TransactionPreviewRequest(CompatBase):
    diskon: Decimal = Field(default=Decimal("0.00"), ge=0)
    metode_bayar: str = Field(default="CASH", **_pattern("^(CASH|TRANSFER)$"))
    bayar: Decimal = Field(default=Decimal("0.00"), ge=0)
    jenis_bayar: str = Field(default="LUNAS", **_pattern("^(LUNAS|DP)$"))
    dp: Decimal = Field(default=Decimal("0.00"), ge=0)
    jobs: List[ServiceJobInput] = Field(default_factory=list)
    parts: List[ServicePartInput] = Field(default_factory=list)


class TransactionPreviewLineOut(CompatBase):
    subtotal: Money


class TransactionPreviewOut(CompatBase):
    """Pratinjau kasir; nilai final selalu dari transaksi tersimpan."""

    is_final: bool = False
    biaya_jasa: Money
    total_part: Money
    subtotal: Money
    diskon: Money
    total_servis: Money
    bayar: Money
    kembalian: Money
    kekurangan: Money
    jenis_bayar: str = "LUNAS"
    status_bayar: str = "LUNAS"
    sisa_bayar: Money = ZERO_MONEY
    jobs: List[TransactionPreviewLineOut] = Field(default_factory=list)
    parts: List[TransactionPreviewLineOut] = Field(default_factory=list)


class ServiceJobOut(ORMModel):
    id: int
    deskripsi: str
    jumlah: int
    jumlah_retur: int = 0
    harga: Money
    subtotal: Money
    interval_servis_bulan: int = 0


class ServicePartOut(ORMModel):
    id: int
    nama_part: str
    jumlah: int
    jumlah_retur: int = 0
    harga_satuan: Money
    subtotal: Money
    interval_servis_bulan: int = 0


class VoidRequest(StrictBase):
    alasan: str = Field(..., min_length=3, max_length=500)


class ServiceReturnItemInput(CompatBase):
    service_part_id: Optional[int] = Field(default=None, gt=0)
    service_job_id: Optional[int] = Field(default=None, gt=0)
    jumlah: int = Field(..., ge=1)


class CreateServiceReturnRequest(StrictBase):
    alasan: str = Field(..., min_length=3, max_length=500)
    items: List[ServiceReturnItemInput] = Field(default_factory=list)


class ServiceReturnItemOut(ORMModel):
    id: int
    service_part_id: Optional[int] = None
    service_job_id: Optional[int] = None
    stock_item_id: Optional[int] = None
    nama_item: str
    jumlah: int
    harga_satuan: Money
    harga_modal: Optional[Money] = None
    subtotal: Money


class ServiceReturnOut(ORMModel):
    id: int
    service_record_id: int
    alasan: str
    oleh: str
    total_nilai: Money
    created_at: datetime
    items: List[ServiceReturnItemOut] = Field(default_factory=list)


class StockMovementOut(ORMModel):
    id: int
    stock_item_id: Optional[int] = None
    nama_item: Optional[str] = None
    jenis: str
    jumlah: int
    alasan: Optional[str] = None
    oleh: str
    service_record_id: Optional[int] = None
    service_return_id: Optional[int] = None
    created_at: datetime


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
    status_bayar: str = "LUNAS"
    jatuh_tempo: Optional[date] = None
    total_dibayar: Money = ZERO_MONEY
    sisa_bayar: Money = ZERO_MONEY
    bergaransi: bool
    garansi_sampai: Optional[date] = None
    catatan_garansi: Optional[str] = None
    status_klaim: str
    tanggal_klaim: Optional[date] = None
    garansi_aktif: bool
    warranty_status: str
    jumlah_item: int = 0
    laba_kotor: Money = ZERO_MONEY
    modal_tidak_diketahui: bool = False
    modal_estimasi: bool = False
    status: str = "NORMAL"
    void_reason: Optional[str] = None
    voided_at: Optional[datetime] = None
    voided_by: Optional[str] = None
    total_retur: Money = ZERO_MONEY
    retur_count: int = 0
    total_neto: Money = ZERO_MONEY


# --- PEMBAYARAN & PIUTANG ---
class PaymentCreate(StrictBase):
    nominal: Decimal = Field(..., gt=0)
    metode: str = Field(default="CASH", **_pattern("^(CASH|TRANSFER)$"))
    catatan: Optional[str] = Field(default=None, max_length=500)
    request_id: Optional[str] = Field(default=None, min_length=8, max_length=64)


class PaymentOut(ORMModel):
    id: int
    service_record_id: int
    jenis: str
    metode: str
    nominal: Money
    waktu: datetime
    operator: str
    catatan: Optional[str] = None
    request_id: Optional[str] = None


class ReceivableRecordOut(CompatBase):
    id: int
    no_nota: str
    waktu_service: datetime
    metode_bayar: str
    total_servis: Money
    total_neto: Money
    total_dibayar: Money
    sisa_bayar: Money
    jatuh_tempo: Optional[date] = None
    umur_hari: int
    umur_bucket: str
    overdue: bool


class ReceivableCustomerOut(CompatBase):
    customer_id: int
    nama: str
    nomor_hp: str
    jumlah_nota: int
    total_sisa: Money
    jatuh_tempo_terdekat: Optional[date] = None
    umur_tertua_hari: int
    records: List[ReceivableRecordOut] = Field(default_factory=list)


class ReceivablesOut(CompatBase):
    jumlah_pelanggan: int
    jumlah_nota: int
    total_sisa: Money
    items: List[ReceivableCustomerOut] = Field(default_factory=list)


class WhatsAppAttemptIn(StrictBase):
    status: str = Field(..., **_pattern("^(DIBUKA|DIBATALKAN|TIDAK_TERSEDIA)$"))
    catatan: Optional[str] = Field(default=None, max_length=500)
    jenis: str = Field(default="struk", **_pattern("^(struk|piutang)$"))


class WhatsAppLogOut(ORMModel):
    id: int
    service_record_id: Optional[int] = None
    customer_id: Optional[int] = None
    nomor_masked: str
    status: str
    operator: str
    created_at: datetime


class WhatsAppAttemptOut(CompatBase):
    status: str
    nomor_masked: str
    link: str = ""
    wa_text: str = ""
    log: WhatsAppLogOut


# --- FOLLOW-UP TAHAP 13 ---
class FollowupRincianOut(CompatBase):
    no_nota: Optional[str] = None
    tanggal_servis: Optional[date] = None
    umur_hari: Optional[int] = None
    jenis_item: Optional[str] = None
    nama: Optional[str] = None
    pekerjaan: Optional[str] = None
    garansi_sampai: Optional[date] = None
    sisa_hari: Optional[int] = None
    interval_bulan: Optional[int] = None
    jatuh_tempo: Optional[date] = None
    total_servis: Optional[Money] = None
    sisa_bayar: Optional[Money] = None


class FollowupItemOut(CompatBase):
    id: int
    jenis: str
    jenis_label: str
    customer_id: int
    customer_nama: str
    nomor_hp: str
    nomor_masked: str
    wa_consent: bool = True
    unit_id: Optional[int] = None
    unit_deskripsi: str = "-"
    service_record_id: Optional[int] = None
    no_nota: Optional[str] = None
    judul: str
    jatuh_tempo: Optional[date] = None
    sisa_hari: Optional[int] = None
    terlambat: bool = False
    status: str
    status_label: str
    penanggung_jawab: Optional[str] = None
    diambil_pada: Optional[datetime] = None
    followup_terakhir: Optional[datetime] = None
    sudah_followup: bool = False
    janji_bayar: Optional[date] = None
    alasan_arsip: Optional[str] = None
    cooldown_sampai: Optional[datetime] = None
    bisa_followup: bool = True
    rincian: List[FollowupRincianOut] = Field(default_factory=list)


class FollowupListOut(CompatBase):
    items: List[FollowupItemOut] = Field(default_factory=list)
    jumlah: int = 0


class FollowupCountsOut(CompatBase):
    servis_berkala_due: int = 0
    prospek_count: int = 0
    followup_hari_ini: int = 0
    garansi_akan_habis: int = 0
    piutang_count: int = 0
    piutang_customers: int = 0
    piutang_total: Money = ZERO_MONEY


class FollowupActionResultOut(CompatBase):
    item: FollowupItemOut
    wa_text: str = ""
    link: str = ""
    log: WhatsAppLogOut


class FollowupStatusIn(StrictBase):
    status: str = Field(
        ...,
        **_pattern(
            "^(BARU|SUDAH_FOLLOWUP|JANJI_BAYAR|MASIH_KENDALA|SELESAI|ARSIP)$"
        ),
    )
    alasan: Optional[str] = Field(default=None, max_length=500)
    janji_bayar: Optional[date] = None


class FollowupAssignIn(StrictBase):
    release: bool = False
    alasan: Optional[str] = Field(default=None, max_length=500)


class FollowupEventOut(ORMModel):
    id: int
    item_id: int
    from_status: Optional[str] = None
    to_status: str
    alasan: Optional[str] = None
    operator: str
    created_at: datetime


class FollowupDetailOut(CompatBase):
    item: FollowupItemOut
    events: List[FollowupEventOut] = Field(default_factory=list)
    pesan: str = ""


class FollowupReminderOut(FollowupItemOut):
    pengingat: str = ""


class ReceiptLabelOut(CompatBase):
    kode: str
    nama: str
    unit: str
    customer_nama: str
    customer_hp: str


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
    status_bayar: str = "LUNAS"
    jatuh_tempo: Optional[date] = None
    total_dibayar: Money = ZERO_MONEY
    sisa_bayar: Money = ZERO_MONEY
    bergaransi: bool
    garansi_sampai: Optional[date] = None
    catatan_garansi: Optional[str] = None
    status_klaim: str
    tanggal_klaim: Optional[date] = None
    garansi_aktif: bool
    warranty_status: str
    status: str = "NORMAL"
    void_reason: Optional[str] = None
    voided_at: Optional[datetime] = None
    voided_by: Optional[str] = None
    total_retur: Money = ZERO_MONEY
    retur_count: int = 0
    total_neto: Money = ZERO_MONEY
    labels: List[ReceiptLabelOut] = Field(default_factory=list)
    jobs: List[ServiceJobOut] = Field(default_factory=list)
    parts: List[ServicePartOut] = Field(default_factory=list)
    payments: List[PaymentOut] = Field(default_factory=list)
    wa_text: str = ""
    completion_wa_text: str = ""
    customer_wa: str = ""
    wa_consent: bool = True
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


class PaymentResultOut(CompatBase):
    payment: PaymentOut
    record: ServiceRecordOut
    receipt: ReceiptOut
    status_bayar: str
    sisa_bayar: Money


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
    transaksi_tanpa_modal: int = 0
    transaksi_modal_estimasi: int = 0
    total_retur: Money = ZERO_MONEY
    jumlah_retur: int = 0
    total_void: Money = ZERO_MONEY
    jumlah_void: int = 0
    penerimaan_cash: Money = ZERO_MONEY
    penerimaan_transfer: Money = ZERO_MONEY
    penerimaan_total: Money = ZERO_MONEY
    piutang_count: int = 0
    piutang_customers: int = 0
    piutang_total: Money = ZERO_MONEY
    garansi_akan_habis: int = 0
    servis_berkala_due: int = 0
    followup_hari_ini: int = 0
    prospek_count: int = 0


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
    transaksi_tanpa_modal: int = 0
    transaksi_modal_estimasi: int = 0
    total_retur: Money = ZERO_MONEY
    jumlah_retur: int = 0
    total_void: Money = ZERO_MONEY
    jumlah_void: int = 0
    penerimaan_cash: Money = ZERO_MONEY
    penerimaan_transfer: Money = ZERO_MONEY
    penerimaan_total: Money = ZERO_MONEY
    piutang_count: int = 0
    piutang_customers: int = 0
    piutang_total: Money = ZERO_MONEY
    garansi_akan_habis: int = 0
    servis_berkala_due: int = 0
    followup_hari_ini: int = 0
    prospek_count: int = 0
    transaksi: List[ServiceRecordOut] = Field(default_factory=list)
    harian: List[DailySummaryOut] = Field(default_factory=list)


class SoldPartOut(CompatBase):
    id: int
    service_record_id: int
    no_nota: str
    waktu_service: datetime
    nama_part: str
    jumlah: int
    jumlah_retur: int = 0
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


class BackupStatusOut(CompatBase):
    last_local_at: Optional[str] = None
    last_local_filename: Optional[str] = None
    last_status: Optional[str] = None
    last_error: Optional[str] = None
    last_telegram_at: Optional[str] = None
    stale: bool = False
    stale_days: int = 2


class OpsSettingsIn(CompatBase):
    tempo_hari: int = Field(default=7, ge=1, le=365)
    prospek_hari: int = Field(default=7, ge=1, le=365)
    cooldown_hari: int = Field(default=7, ge=0, le=90)
    garansi_akan_habis_hari: int = Field(default=7, ge=1, le=90)
    servis_berkala_awal_hari: int = Field(default=14, ge=1, le=90)


class OpsSettingsOut(OpsSettingsIn):
    pass


class ScheduledBackupOut(CompatBase):
    status: str
    local_saved: bool = False
    filename: Optional[str] = None
    size_bytes: int = 0
    created_at: Optional[str] = None
    telegram_enabled: bool = False
    telegram_sent: bool = False
    telegram_error: Optional[str] = None
    message: str = ""


class PrinterInfoOut(CompatBase):
    paper_width: int
    encoding: str
    auto_cut: bool


class PrinterDeviceIn(StrictBase):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=80)
    connection_type: str = Field(max_length=16)
    paper_width: int
    print_mode: Optional[str] = Field(default=None, max_length=16)
    encoding: Optional[str] = Field(default=None, max_length=32)
    address: Optional[str] = Field(default=None, max_length=255)
    ip: Optional[str] = Field(default=None, max_length=255)
    port: Optional[int] = None
    last_status: Optional[str] = Field(default=None, max_length=16)
    last_connected_at: Optional[str] = Field(default=None, max_length=40)
    last_error: Optional[str] = Field(default=None, max_length=300)


class PrinterDeviceOut(PrinterDeviceIn):
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PrinterConfigIn(StrictBase):
    printers: List[PrinterDeviceIn] = Field(default_factory=list)
    primary_id: Optional[str] = Field(default=None, max_length=64)


class PrinterConfigOut(CompatBase):
    version: int
    printers: List[PrinterDeviceOut]
    primary_id: Optional[str] = None
    updated_at: Optional[str] = None
    warning: Optional[str] = None


class ConfigOut(CompatBase):
    version: str
    bengkel: BengkelInfoOut
    telegram: TelegramInfoOut
    backup: BackupStatusOut
    printer: PrinterInfoOut
    default_garansi_bulan: int
    garansi_syarat: str
    metode_bayar: List[str]
    keluhan_presets: List[str]
    ops: OpsSettingsOut = Field(default_factory=OpsSettingsOut)


class PinRequest(CompatBase):
    pin: str = Field(min_length=4, max_length=12)


class AuthStatusOut(CompatBase):
    mode: str
    pin_configured: bool
    authenticated: bool
    locked_seconds: int = 0
    kasir_configured: bool = False
    operator_id: Optional[str] = None
    role: Optional[str] = None
    operator_label: Optional[str] = None


class AuditEventOut(ORMModel):
    id: int
    operator_id: str
    operator_role: str
    action: str
    reference_type: str
    reference_id: str
    reason: Optional[str] = None
    created_at: datetime
