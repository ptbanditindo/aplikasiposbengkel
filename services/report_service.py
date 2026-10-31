"""Agregasi laporan kas harian & periode."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Dict, List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import FollowupItem, ServicePayment, ServiceRecord, VehicleOrUnit
from repositories import service_record_repository as record_repo
from services import followup_service, settings_service, warranty_service
from services.customer_service import describe_unit
from services.receipt_service import record_summary
from services.utils import money


def _is_void(record: ServiceRecord) -> bool:
    return (record.status or "NORMAL") == "VOID"


def _summarize_records(
    db: Session,
    records: List[ServiceRecord],
    payments: List[ServicePayment] | None = None,
) -> Dict[str, Any]:
    total_cash = Decimal("0.00")
    total_transfer = Decimal("0.00")
    penerimaan_cash = Decimal("0.00")
    penerimaan_transfer = Decimal("0.00")
    total_jasa = Decimal("0.00")
    total_part = Decimal("0.00")
    total_diskon = Decimal("0.00")
    total_retur = Decimal("0.00")
    total_void = Decimal("0.00")
    laba_kotor = Decimal("0.00")
    units = set()
    active_warranty = 0
    transaksi_tanpa_modal = 0
    transaksi_modal_estimasi = 0
    jumlah_retur = 0
    jumlah_void = 0

    normal_records = [record for record in records if not _is_void(record)]
    void_records = [record for record in records if _is_void(record)]

    for record in normal_records:
        units.add(record.unit_id)
        if warranty_service.is_active(record):
            active_warranty += 1
        modal_lengkap = True
        modal_estimasi = False
        retur = record.total_retur or Decimal("0.00")
        total_retur += retur
        jumlah_retur += int(record.retur_count or 0)
        # Retur jasa/part mengurangi komponen laporan sesuai jenisnya.
        total_jasa += record.biaya_jasa - (record.total_retur_jasa or Decimal("0.00"))
        total_part += record.total_part - (record.total_retur_part or Decimal("0.00"))
        total_diskon += record.diskon
        net_revenue = record.total_servis - retur
        if record.metode_bayar == "TRANSFER":
            total_transfer += net_revenue
        else:
            total_cash += net_revenue

        for part in record.parts:
            net_qty = int(part.jumlah) - int(getattr(part, "jumlah_retur", 0) or 0)
            if net_qty <= 0:
                continue
            if part.harga_modal_estimasi:
                modal_estimasi = True
            modal = part.harga_modal
            if modal is None and part.stock_item is not None:
                modal = part.stock_item.harga_modal
            if modal is None:
                modal_lengkap = False
                continue
            laba_kotor += (part.harga_satuan - modal) * net_qty
        if not modal_lengkap:
            transaksi_tanpa_modal += 1
        if modal_estimasi:
            transaksi_modal_estimasi += 1

    # VOID tidak dihitung sebagai penjualan, tetapi nilainya tetap dilaporkan
    # sebagai pengurang/informasi agar koreksi tidak menghapus jejak.
    for record in void_records:
        total_void += record.total_servis
        jumlah_void += 1

    # Uang diterima berasal dari buku pembayaran (DP/pelunasan/refund), bukan
    # dari nilai nota, agar pendapatan tidak dihitung dua kali.
    for payment in payments or []:
        nominal = Decimal(payment.nominal or 0)
        if payment.metode == "TRANSFER":
            penerimaan_transfer += nominal
        else:
            penerimaan_cash += nominal

    return {
        "jumlah_transaksi": len(normal_records),
        "jumlah_unit_servis": len(units),
        "total_omset": money(total_cash + total_transfer),
        "total_cash": money(total_cash),
        "total_transfer": money(total_transfer),
        "total_jasa": money(total_jasa),
        "total_part": money(total_part),
        "total_diskon": money(total_diskon),
        "laba_kotor": money(laba_kotor),
        "garansi_aktif": int(active_warranty),
        "transaksi_tanpa_modal": transaksi_tanpa_modal,
        "transaksi_modal_estimasi": transaksi_modal_estimasi,
        "total_retur": money(total_retur),
        "jumlah_retur": jumlah_retur,
        "total_void": money(total_void),
        "jumlah_void": jumlah_void,
        "penerimaan_cash": money(penerimaan_cash),
        "penerimaan_transfer": money(penerimaan_transfer),
        "penerimaan_total": money(penerimaan_cash + penerimaan_transfer),
        "transaksi": [record_summary(record) for record in normal_records],
    }


def _payments_between(
    db: Session, start: datetime, end: datetime
) -> List[ServicePayment]:
    statement = (
        select(ServicePayment)
        .where(ServicePayment.waktu >= start, ServicePayment.waktu < end)
        .order_by(ServicePayment.waktu.asc(), ServicePayment.id.asc())
    )
    return list(db.scalars(statement).all())


def _ops_snapshot(db: Session, today: date) -> Dict[str, Any]:
    """Kartu operasional dasbor (kondisi saat ini, bukan periode laporan)."""
    sisa = func.max(
        ServiceRecord.total_servis
        - func.coalesce(ServiceRecord.total_retur, 0)
        - func.coalesce(ServiceRecord.total_dibayar, 0),
        0,
    )
    piutang = db.execute(
        select(
            func.count(ServiceRecord.id),
            func.count(func.distinct(VehicleOrUnit.customer_id)),
            func.coalesce(func.sum(sisa), 0),
        )
        .join(VehicleOrUnit, ServiceRecord.unit_id == VehicleOrUnit.id)
        .where(
            ServiceRecord.status == "NORMAL",
            ServiceRecord.status_bayar == "BELUM_LUNAS",
            sisa > 0,
        )
    ).one()
    ops = settings_service.get_ops_settings(db)
    batas_garansi = today + timedelta(days=int(ops["garansi_akan_habis_hari"]))
    garansi_akan_habis = db.scalar(
        select(func.count(ServiceRecord.id)).where(
            ServiceRecord.status == "NORMAL",
            ServiceRecord.bergaransi.is_(True),
            ServiceRecord.status_klaim != "Sudah claim",
            ServiceRecord.garansi_sampai.is_not(None),
            ServiceRecord.garansi_sampai >= today,
            ServiceRecord.garansi_sampai <= batas_garansi,
        )
    )
    terjadwal = db.scalar(
        select(func.count(FollowupItem.id)).where(
            FollowupItem.jenis == followup_service.JENIS_GARANSI,
            FollowupItem.status == followup_service.STATUS_AKAN_DATANG,
        )
    )
    return {
        "piutang_count": int(piutang[0] or 0),
        "piutang_customers": int(piutang[1] or 0),
        "piutang_total": money(piutang[2] or 0),
        "garansi_akan_habis": max(
            0, int(garansi_akan_habis or 0) - int(terjadwal or 0)
        ),
    }


def daily_report(db: Session, day: date | None = None) -> Dict[str, Any]:
    target = day or date.today()
    start = datetime.combine(target, time.min)
    end = start + timedelta(days=1)
    records = record_repo.records_between(db, start, end)
    payments = _payments_between(db, start, end)
    summary = _summarize_records(db, records, payments)
    summary["tanggal"] = target
    # Sinkronkan item follow-up dulu agar kartu garansi memakai status terbaru.
    summary.update(followup_service.counts(db, date.today()))
    summary.update(_ops_snapshot(db, date.today()))
    return summary


def period_report(db: Session, start_day: date, end_day: date) -> Dict[str, Any]:
    start = datetime.combine(start_day, time.min)
    end = datetime.combine(end_day + timedelta(days=1), time.min)
    records = record_repo.records_between(db, start, end)
    payments = _payments_between(db, start, end)
    summary = _summarize_records(db, records, payments)

    by_day: Dict[date, List[ServiceRecord]] = {}
    for record in records:
        by_day.setdefault(record.waktu_service.date(), []).append(record)
    payments_by_day: Dict[date, List[ServicePayment]] = {}
    for payment in payments:
        payments_by_day.setdefault(payment.waktu.date(), []).append(payment)

    daily: List[Dict[str, Any]] = []
    cursor = start_day
    while cursor <= end_day:
        daily_summary = _summarize_records(
            db, by_day.get(cursor, []), payments_by_day.get(cursor, [])
        )
        daily_summary.pop("transaksi", None)
        daily_summary["tanggal"] = cursor
        daily.append(daily_summary)
        cursor += timedelta(days=1)

    summary["start"] = start_day
    summary["end"] = end_day
    summary["harian"] = daily
    summary.update(_ops_snapshot(db, date.today()))
    return summary


def all_time_report(db: Session) -> Dict[str, Any]:
    """Seluruh riwayat sejak nota tertua, tanpa memotong periode kosong."""
    oldest = db.scalar(select(func.min(ServiceRecord.waktu_service)))
    today = date.today()
    if oldest is None:
        summary = _summarize_records(db, [], [])
        summary["start"] = today
        summary["end"] = today
        summary["harian"] = []
        summary.update(_ops_snapshot(db, today))
        return summary
    return period_report(db, oldest.date(), today)


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
        if _is_void(record):
            continue
        unit_desc = describe_unit(record.unit)
        customer_nama = record.unit.customer.nama if record.unit.customer else "-"
        for part in record.parts:
            retur_qty = int(getattr(part, "jumlah_retur", 0) or 0)
            net_qty = int(part.jumlah) - retur_qty
            if net_qty <= 0:
                continue
            subtotal = money(part.harga_satuan * net_qty)
            total_qty += net_qty
            total_nilai += subtotal
            items.append(
                {
                    "id": part.id,
                    "service_record_id": record.id,
                    "no_nota": record.no_nota,
                    "waktu_service": record.waktu_service,
                    "nama_part": part.nama_part,
                    "jumlah": net_qty,
                    "jumlah_retur": retur_qty,
                    "harga_satuan": part.harga_satuan,
                    "subtotal": subtotal,
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
