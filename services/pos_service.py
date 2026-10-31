"""Transaksi kasir atomik: harga deal, potong stok, nomor nota.

Ref: PRD FR-POS-01 s/d FR-POS-08.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import settings
from database.models import (
    HargaJasa,
    ServiceJob,
    ServicePart,
    ServicePayment,
    ServiceRecord,
    StockItem,
    StockMovement,
    VehicleOrUnit,
)
from database.session import begin_immediate
from repositories import service_record_repository as record_repo
from services import (
    customer_service,
    pricing_service,
    warranty_service,
)
from services.auth_service import Operator
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


def _record_gross_profit(record: ServiceRecord) -> Decimal:
    return pricing_service.calculate_gross_profit(
        [
            {
                "harga_satuan": part.harga_satuan,
                "harga_modal": part.harga_modal,
                "jumlah": part.jumlah,
            }
            for part in record.parts
        ]
    )


def _existing_result(record: ServiceRecord) -> TransactionResult:
    return TransactionResult(
        record=record, warnings=[], laba_kotor=_record_gross_profit(record)
    )


def create_transaction(
    db: Session, payload: Any, operator: Optional[Operator] = None
) -> TransactionResult:
    request_id = (getattr(payload, "request_id", None) or "").strip() or None
    try:
        return _create_transaction_locked(db, payload, request_id, operator)
    except IntegrityError:
        # Balapan request_id yang tidak tertangkap pengecekan awal.
        db.rollback()
        if request_id:
            existing = record_repo.get_record_by_request_id(db, request_id)
            if existing is not None:
                return _existing_result(existing)
        raise


def _create_transaction_locked(
    db: Session,
    payload: Any,
    request_id: str | None,
    operator: Optional[Operator] = None,
) -> TransactionResult:
    warnings: List[str] = []

    # Ref: FR-POS-08 - seluruh proses dalam satu transaksi database atomik.
    with db.begin():
        # Kunci tulis diambil sejak awal agar alokasi nota & stok terserialisasi.
        begin_immediate(db)

        if request_id:
            existing = record_repo.get_record_by_request_id(db, request_id)
            if existing is not None:
                return _existing_result(existing)

        unit = db.get(VehicleOrUnit, payload.unit_id)
        if unit is None:
            raise NotFoundError("Unit servis tidak ditemukan.")
        if unit.archived_at is not None:
            raise BusinessValidationError(
                "Unit ini sudah dihapus dari daftar pelanggan."
            )

        now = datetime.now()
        # Nomor barang hanya untuk radiator copotan; mobil utuh tidak berlabel.
        if unit.unit_type == "RADIATOR_ONLY":
            customer_service.ensure_unit_label(db, unit, now.date())

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
            master: Optional[HargaJasa] = None
            if job.harga_jasa_id is not None:
                master = db.get(HargaJasa, job.harga_jasa_id)
                if master is None:
                    raise NotFoundError("Master tarif jasa tidak ditemukan.")
            interval = getattr(job, "interval_servis_bulan", None)
            if interval is None:
                interval = int(getattr(master, "interval_servis_bulan", 0) or 0)
            interval = int(interval)
            if interval < 0 or interval > 120:
                raise BusinessValidationError(
                    "Interval servis berkala harus antara 0 dan 120 bulan."
                )
            job_lines.append(
                {
                    "harga_jasa_id": job.harga_jasa_id,
                    "deskripsi": description,
                    "jumlah": qty,
                    "harga": price,
                    "interval_servis_bulan": interval,
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

            if stock is not None:
                harga_modal = stock.harga_modal
            else:
                raw_modal = getattr(part, "harga_modal", None)
                harga_modal = money(raw_modal) if raw_modal is not None else None
                if harga_modal is None:
                    warnings.append(
                        f"Modal {name} belum diisi; laba kotor part ini "
                        "tidak dihitung."
                    )

            interval = getattr(part, "interval_servis_bulan", None)
            if interval is None:
                interval = int(getattr(stock, "interval_servis_bulan", 0) or 0)
            interval = int(interval)
            if interval < 0 or interval > 120:
                raise BusinessValidationError(
                    "Interval servis berkala sparepart harus antara 0 dan 120 bulan."
                )

            part_lines.append(
                {
                    "stock_item_id": stock.id if stock is not None else None,
                    "nama_part": name,
                    "jumlah": qty,
                    "harga_satuan": price,
                    "harga_modal": harga_modal,
                    "interval_servis_bulan": interval,
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
        jenis_bayar = (getattr(payload, "jenis_bayar", "LUNAS") or "LUNAS").strip().upper()
        jatuh_tempo: date | None = None
        if jenis_bayar == "DP":
            dp_value = getattr(payload, "dp", None)
            if dp_value is None or money(dp_value) <= 0:
                dp_value = payload.bayar
            payment = pricing_service.compute_dp_payment(
                totals["total_servis"], dp_value
            )
            # Tanggal jatuh tempo opsional; pelunasan dicatat saat selesai.
            jatuh_tempo = getattr(payload, "jatuh_tempo", None)
            if jatuh_tempo is not None and jatuh_tempo < now.date():
                raise BusinessValidationError(
                    "Jatuh tempo tidak boleh di masa lalu."
                )
            status_bayar = "BELUM_LUNAS"
            total_dibayar = payment["bayar"]
        elif jenis_bayar == "LUNAS":
            payment = pricing_service.compute_payment(
                totals["total_servis"], payload.metode_bayar, payload.bayar
            )
            status_bayar = "LUNAS"
            total_dibayar = totals["total_servis"]
        else:
            raise BusinessValidationError("Jenis bayar harus LUNAS atau DP.")

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

        record = ServiceRecord(
            unit_id=unit.id,
            no_nota=record_repo.allocate_nota(db, now.date()),
            request_id=request_id,
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
            status_bayar=status_bayar,
            jatuh_tempo=jatuh_tempo,
            total_dibayar=money(total_dibayar),
            bergaransi=bool(payload.bergaransi),
            garansi_sampai=garansi_sampai,
            catatan_garansi=catatan_garansi,
            status_klaim="Belum claim",
        )
        db.add(record)
        db.flush()

        operator_label = operator.label if operator is not None else "Kasir"
        if money(total_dibayar) > 0:
            db.add(
                ServicePayment(
                    service_record_id=record.id,
                    jenis="DP" if status_bayar == "BELUM_LUNAS" else "PELUNASAN",
                    metode=payload.metode_bayar.strip().upper(),
                    nominal=money(total_dibayar),
                    waktu=now,
                    operator=operator_label,
                    catatan="DP saat nota dibuat"
                    if status_bayar == "BELUM_LUNAS"
                    else "Pembayaran nota",
                )
            )

        for line in job_lines:
            db.add(
                ServiceJob(
                    service_record_id=record.id,
                    harga_jasa_id=line["harga_jasa_id"],
                    deskripsi=line["deskripsi"],
                    jumlah=line["jumlah"],
                    harga=line["harga"],
                    subtotal=money(Decimal(line["jumlah"]) * line["harga"]),
                    interval_servis_bulan=line["interval_servis_bulan"],
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
                    harga_modal_estimasi=False,
                    interval_servis_bulan=line["interval_servis_bulan"],
                )
            )

        # Ref: FR-POS-04 - potong stok gudang atomik lewat UPDATE bersyarat.
        if allow_negative:
            for stock_id, needed in stock_needed.items():
                db.execute(
                    update(StockItem)
                    .where(StockItem.id == stock_id)
                    .values(jumlah=StockItem.jumlah - needed)
                    .execution_options(synchronize_session=False)
                )
        else:
            shortages: List[Dict[str, Any]] = []
            for stock_id, needed in stock_needed.items():
                result = db.execute(
                    update(StockItem)
                    .where(StockItem.id == stock_id, StockItem.jumlah >= needed)
                    .values(jumlah=StockItem.jumlah - needed)
                    .execution_options(synchronize_session=False)
                )
                if result.rowcount == 0:
                    available = db.scalar(
                        select(StockItem.jumlah).where(StockItem.id == stock_id)
                    )
                    shortages.append(
                        {
                            "stock_item_id": stock_id,
                            "nama": stock_items[stock_id].nama,
                            "diminta": needed,
                            "tersedia": int(available or 0),
                        }
                    )
            if shortages:
                raise InsufficientStockError(shortages)

        # S-06: setiap pemakaian stok tercatat di ledger dengan referensi nota.
        for line in part_lines:
            stock_id = line["stock_item_id"]
            if stock_id is None:
                continue
            db.add(
                StockMovement(
                    stock_item_id=stock_id,
                    nama_item=line["nama_part"],
                    jenis="KELUAR",
                    jumlah=-line["jumlah"],
                    alasan=f"Penjualan {record.no_nota}",
                    oleh="Kasir",
                    service_record_id=record.id,
                    created_at=now,
                )
            )

        record_id = record.id

    laba_kotor = pricing_service.calculate_gross_profit(part_lines)
    record = db.get(ServiceRecord, record_id)
    return TransactionResult(record=record, warnings=warnings, laba_kotor=laba_kotor)
