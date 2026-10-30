"""Transaksi kasir atomik: harga deal, potong stok, nomor nota.

Ref: PRD FR-POS-01 s/d FR-POS-08.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from config import settings
from database.models import (
    HargaJasa,
    ServiceJob,
    ServicePart,
    ServiceRecord,
    StockItem,
    VehicleOrUnit,
)
from repositories import service_record_repository as record_repo
from services import pricing_service, warranty_service
from services.errors import (
    BusinessValidationError,
    InsufficientStockError,
    NotFoundError,
)
from services.utils import clean_text, money


@dataclass
class TransactionResult:
    record: ServiceRecord
    warnings: List[str] = field(default_factory=list)
    laba_kotor: Decimal = Decimal("0.00")


def _next_nota(db: Session, day: date) -> str:
    """Nomor nota unik harian INV-YYYYMMDD-XXXX (Ref: FR-POS-01)."""
    prefix = f"INV-{day:%Y%m%d}-"
    highest = 0
    for nota in record_repo.nota_prefix_exists(db, prefix):
        suffix = nota[len(prefix):]
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return f"{prefix}{highest + 1:04d}"


def create_transaction(db: Session, payload: Any) -> TransactionResult:
    warnings: List[str] = []

    # Ref: FR-POS-08 - seluruh proses dalam satu transaksi database atomik.
    with db.begin():
        unit = db.get(VehicleOrUnit, payload.unit_id)
        if unit is None:
            raise NotFoundError("Unit servis tidak ditemukan.")

        keluhan = clean_text(payload.keluhan_awal, max_length=2000)
        if not keluhan:
            raise BusinessValidationError("Keluhan awal pelanggan wajib diisi.")
        if not payload.jobs and not payload.parts:
            raise BusinessValidationError(
                "Transaksi harus memiliki minimal satu jasa atau sparepart."
            )

        job_lines: List[Dict[str, Any]] = []
        for job in payload.jobs:
            qty = int(job.jumlah)
            if qty < 1:
                raise BusinessValidationError("Jumlah jasa minimal 1.")
            price = money(job.harga)
            if price < 0:
                raise BusinessValidationError("Harga jasa tidak boleh negatif.")
            description = clean_text(job.deskripsi, max_length=255, allow_newlines=False)
            if not description:
                raise BusinessValidationError("Deskripsi jasa wajib diisi.")
            if job.harga_jasa_id is not None and db.get(HargaJasa, job.harga_jasa_id) is None:
                raise NotFoundError("Master tarif jasa tidak ditemukan.")
            job_lines.append(
                {
                    "harga_jasa_id": job.harga_jasa_id,
                    "deskripsi": description,
                    "jumlah": qty,
                    "harga": price,
                }
            )

        part_lines: List[Dict[str, Any]] = []
        stock_items: Dict[int, StockItem] = {}
        stock_needed: Dict[int, int] = {}

        for part in payload.parts:
            qty = int(part.jumlah)
            if qty < 1:
                raise BusinessValidationError("Jumlah sparepart minimal 1.")
            price = money(part.harga_satuan)
            if price < 0:
                raise BusinessValidationError("Harga sparepart tidak boleh negatif.")

            stock = None
            if part.stock_item_id is not None:
                stock = db.get(StockItem, part.stock_item_id)
                if stock is None:
                    raise NotFoundError("Sparepart gudang tidak ditemukan.")
                stock_items[stock.id] = stock
                stock_needed[stock.id] = stock_needed.get(stock.id, 0) + qty

            name = clean_text(part.nama_part, max_length=255, allow_newlines=False)
            if not name and stock is not None:
                name = stock.nama
            if not name:
                raise BusinessValidationError("Nama sparepart wajib diisi.")

            part_lines.append(
                {
                    "stock_item_id": stock.id if stock is not None else None,
                    "nama_part": name,
                    "jumlah": qty,
                    "harga_satuan": price,
                    "harga_modal": stock.harga_modal if stock is not None else None,
                }
            )

        insufficient: List[Dict[str, Any]] = []
        for stock_id, needed in stock_needed.items():
            stock = stock_items[stock_id]
            if stock.jumlah < needed:
                insufficient.append(
                    {
                        "stock_item_id": stock.id,
                        "nama": stock.nama,
                        "diminta": needed,
                        "tersedia": stock.jumlah,
                    }
                )

        allow_negative = bool(getattr(payload, "izinkan_stok_minus", False))
        if insufficient and not allow_negative:
            raise InsufficientStockError(insufficient)
        for item in insufficient:
            warnings.append(
                f"Stok {item['nama']} tersedia {item['tersedia']}, "
                f"diminta {item['diminta']}; transaksi disimpan dengan stok minus."
            )

        totals = pricing_service.compute_invoice(
            job_lines, part_lines, payload.diskon
        )
        payment = pricing_service.compute_payment(
            totals["total_servis"], payload.metode_bayar, payload.bayar
        )

        garansi_sampai: date | None = None
        catatan_garansi: str | None = None
        if payload.bergaransi:
            custom_date = getattr(payload, "garansi_sampai", None)
            garansi_sampai = warranty_service.warranty_end_date(
                payload.garansi_bulan, custom_date
            )
            if garansi_sampai < date.today():
                raise BusinessValidationError(
                    "Tanggal akhir garansi tidak boleh di masa lalu."
                )
            catatan_garansi = clean_text(
                payload.catatan_garansi or settings.garansi_syarat,
                max_length=1000,
            )

        now = datetime.now()
        record = ServiceRecord(
            unit_id=unit.id,
            no_nota=_next_nota(db, now.date()),
            waktu_service=now,
            keluhan_awal=keluhan,
            catatan_pengerjaan=clean_text(payload.catatan_pengerjaan, max_length=2000)
            or None,
            biaya_jasa=totals["biaya_jasa"],
            total_part=totals["total_part"],
            diskon=totals["diskon"],
            total_servis=totals["total_servis"],
            metode_bayar=payload.metode_bayar.strip().upper(),
            bayar=payment["bayar"],
            kembalian=payment["kembalian"],
            bergaransi=bool(payload.bergaransi),
            garansi_sampai=garansi_sampai,
            catatan_garansi=catatan_garansi,
            status_klaim="Belum claim",
        )
        db.add(record)
        db.flush()

        for line in job_lines:
            db.add(
                ServiceJob(
                    service_record_id=record.id,
                    harga_jasa_id=line["harga_jasa_id"],
                    deskripsi=line["deskripsi"],
                    jumlah=line["jumlah"],
                    harga=line["harga"],
                    subtotal=money(Decimal(line["jumlah"]) * line["harga"]),
                )
            )

        for line in part_lines:
            db.add(
                ServicePart(
                    service_record_id=record.id,
                    stock_item_id=line["stock_item_id"],
                    nama_part=line["nama_part"],
                    jumlah=line["jumlah"],
                    harga_satuan=line["harga_satuan"],
                    subtotal=money(Decimal(line["jumlah"]) * line["harga_satuan"]),
                    harga_modal=line["harga_modal"],
                )
            )

        # Ref: FR-POS-04 - potong stok gudang otomatis & atomik.
        for stock_id, needed in stock_needed.items():
            stock_items[stock_id].jumlah -= needed

        record_id = record.id

    laba_kotor = pricing_service.calculate_gross_profit(part_lines)
    record = db.get(ServiceRecord, record_id)
    return TransactionResult(record=record, warnings=warnings, laba_kotor=laba_kotor)
