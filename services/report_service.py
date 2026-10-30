"""Agregasi laporan kas harian & periode."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from database.models import ServiceRecord, StockItem
from repositories import service_record_repository as record_repo
from services import warranty_service
from services.customer_service import describe_unit
from services.receipt_service import record_summary
from services.utils import money


def _summarize_records(db: Session, records: List[ServiceRecord]) -> Dict[str, Any]:
    total_cash = Decimal("0.00")
    total_transfer = Decimal("0.00")
    total_jasa = Decimal("0.00")
    total_part = Decimal("0.00")
    total_diskon = Decimal("0.00")
    laba_kotor = Decimal("0.00")
    units = set()
    active_warranty = 0

    stock_cache: Dict[int, StockItem | None] = {}

    for record in records:
        units.add(record.unit_id)
        if warranty_service.is_active(record):
            active_warranty += 1
        total_jasa += record.biaya_jasa
        total_part += record.total_part
        total_diskon += record.diskon
        if record.metode_bayar == "TRANSFER":
            total_transfer += record.total_servis
        else:
            total_cash += record.total_servis

        for part in record.parts:
            modal = part.harga_modal
            if modal is None and part.stock_item_id is not None:
                if part.stock_item_id not in stock_cache:
                    stock_cache[part.stock_item_id] = db.get(
                        StockItem, part.stock_item_id
                    )
                stock = stock_cache[part.stock_item_id]
                if stock is not None:
                    modal = stock.harga_modal
            if modal is not None:
                laba_kotor += (part.harga_satuan - modal) * part.jumlah

    return {
        "jumlah_transaksi": len(records),
        "jumlah_unit_servis": len(units),
        "total_omset": money(total_cash + total_transfer),
        "total_cash": money(total_cash),
        "total_transfer": money(total_transfer),
        "total_jasa": money(total_jasa),
        "total_part": money(total_part),
        "total_diskon": money(total_diskon),
        "laba_kotor": money(laba_kotor),
        "garansi_aktif": int(active_warranty),
        "transaksi": [record_summary(record) for record in records],
    }


def daily_report(db: Session, day: date | None = None) -> Dict[str, Any]:
    target = day or date.today()
    start = datetime.combine(target, time.min)
    end = start + timedelta(days=1)
    records = record_repo.records_between(db, start, end)
    summary = _summarize_records(db, records)
    summary["tanggal"] = target
    return summary


def period_report(db: Session, start_day: date, end_day: date) -> Dict[str, Any]:
    start = datetime.combine(start_day, time.min)
    end = datetime.combine(end_day + timedelta(days=1), time.min)
    records = record_repo.records_between(db, start, end)
    summary = _summarize_records(db, records)

    daily: List[Dict[str, Any]] = []
    cursor = start_day
    while cursor <= end_day:
        day_records = [
            record for record in records if record.waktu_service.date() == cursor
        ]
        daily_summary = _summarize_records(db, day_records)
        daily_summary.pop("transaksi", None)
        daily_summary["tanggal"] = cursor
        daily.append(daily_summary)
        cursor += timedelta(days=1)

    summary["start"] = start_day
    summary["end"] = end_day
    summary["harian"] = daily
    return summary


def sold_parts_report(
    db: Session, start_day: date | None = None, end_day: date | None = None
) -> Dict[str, Any]:
    """
    Riwayat part terjual, satu baris per penjualan (bukan agregasi),
    memakai harga deal akhir (ServicePart.harga_satuan).
    """
    if start_day is not None and end_day is not None:
        start = datetime.combine(start_day, time.min)
        end = datetime.combine(end_day + timedelta(days=1), time.min)
        records = record_repo.records_between(db, start, end)
    else:
        records = record_repo.all_records(db)

    items: List[Dict[str, Any]] = []
    total_qty = 0
    total_nilai = Decimal("0.00")

    for record in records:
        unit_desc = describe_unit(record.unit)
        customer_nama = record.unit.customer.nama if record.unit.customer else "-"
        for part in record.parts:
            total_qty += part.jumlah
            total_nilai += part.subtotal
            items.append(
                {
                    "id": part.id,
                    "service_record_id": record.id,
                    "no_nota": record.no_nota,
                    "waktu_service": record.waktu_service,
                    "nama_part": part.nama_part,
                    "jumlah": part.jumlah,
                    "harga_satuan": part.harga_satuan,
                    "subtotal": part.subtotal,
                    "customer_nama": customer_nama,
                    "unit_deskripsi": unit_desc,
                }
            )

    # Barang sama dikelompokkan berurutan; di dalam kelompok urut waktu penjualan.
    items.sort(
        key=lambda item: (
            item["nama_part"].strip().lower(),
            item["waktu_service"],
            item["service_record_id"],
            item["id"],
        )
    )

    return {
        "jumlah_penjualan": len(items),
        "total_qty": total_qty,
        "total_nilai": money(total_nilai),
        "items": items,
    }
