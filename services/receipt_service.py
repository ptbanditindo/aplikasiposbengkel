"""Penyusun data struk & ringkasan transaksi servis."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List

from config import settings
from database.models import ServiceRecord
from services import settings_service, warranty_service
from services.customer_service import describe_unit
from services.escpos_service import ReceiptBuilder
from services.utils import format_rupiah, money


def _net_qty(item) -> int:
    return max(int(item.jumlah) - int(getattr(item, "jumlah_retur", 0) or 0), 0)


def _is_void(record: ServiceRecord) -> bool:
    return (getattr(record, "status", "NORMAL") or "NORMAL") == "VOID"


def _total_neto(record: ServiceRecord):
    if _is_void(record):
        return money(Decimal("0.00"))
    return money(record.total_servis - (record.total_retur or Decimal("0.00")))


def _duration_label(record: ServiceRecord) -> str:
    if not record.garansi_sampai:
        return ""
    days = (record.garansi_sampai - record.waktu_service.date()).days
    months = max(1, round(days / 30))
    return f" ({months} Bulan)"


def _build(
    record: ServiceRecord, width: int, bengkel: Dict[str, str]
) -> ReceiptBuilder:
    unit = record.unit
    customer = unit.customer

    b = ReceiptBuilder(width)
    b.divider("=")
    b.center(bengkel["nama"], bold=True, double=True)
    if bengkel["tagline"]:
        b.center(bengkel["tagline"])
    if bengkel["alamat"]:
        b.center(bengkel["alamat"])
    contact = bengkel["wa"] or bengkel["telepon"]
    if contact and contact != "-":
        b.center(f"Telp/WA: {contact}")
    b.divider("=")

    b.kv("No. Nota", record.no_nota)
    b.kv("Tanggal", record.waktu_service.strftime("%d/%m/%Y %H:%M"))
    b.kv("Kasir", "Kasir")
    if _is_void(record):
        b.divider("-")
        b.center("*** NOTA DIBATALKAN (VOID) ***", bold=True)
        if record.void_reason:
            b.field("Alasan", record.void_reason)
        if record.voided_at:
            b.field("Waktu void", record.voided_at.strftime("%d/%m/%Y %H:%M"))
        if record.voided_by:
            b.field("Oleh", record.voided_by)
    b.divider("-")

    b.field("Pelanggan", customer.nama)
    b.field("No. HP", customer.nomor_hp)
    b.field("Unit", describe_unit(unit))
    b.field("Keluhan", record.keluhan_awal or "-")
    if record.catatan_pengerjaan:
        b.field("Catatan", record.catatan_pengerjaan)
    b.divider("-")

    if record.jobs:
        b.add("JASA:", bold=True)
        for job in record.jobs:
            b.item(job.deskripsi, job.jumlah, job.harga, job.subtotal)
    if record.parts:
        b.add("PART:", bold=True)
        for part in record.parts:
            b.item(part.nama_part, part.jumlah, part.harga_satuan, part.subtotal)
    if not record.jobs and not record.parts:
        b.add("(tidak ada rincian pengerjaan)")

    b.divider("-")
    b.kv("Total Jasa", format_rupiah(record.biaya_jasa))
    b.kv("Total Part", format_rupiah(record.total_part))
    if record.diskon and record.diskon > 0:
        b.kv("Diskon", "-" + format_rupiah(record.diskon))
    b.kv("Grand Total", format_rupiah(record.total_servis), bold=True, double=True)
    total_retur = record.total_retur or Decimal("0.00")
    if total_retur > 0 or _is_void(record):
        b.kv("Retur", "-" + format_rupiah(total_retur))
        b.kv("Total Neto", format_rupiah(_total_neto(record)), bold=True)

    if record.metode_bayar == "TRANSFER":
        b.kv("Metode Bayar", "TRANSFER BANK")
    else:
        b.kv("Metode Bayar", "CASH / TUNAI")
    b.kv("Bayar", format_rupiah(record.bayar))
    b.kv("Kembali", format_rupiah(record.kembalian))

    b.divider("-")
    b.add("GARANSI SERVIS:", bold=True)
    if _is_void(record):
        b.kv("Status", "DIBATALKAN")
    elif record.bergaransi and record.garansi_sampai:
        b.kv("Status", "BERGARANSI")
        b.kv(
            "Sampai",
            record.garansi_sampai.strftime("%d/%m/%Y") + _duration_label(record),
        )
        if record.catatan_garansi:
            b.field("Catatan", record.catatan_garansi)
    else:
        b.kv("Status", "TANPA GARANSI")

    b.divider("-")
    b.add("REKENING BENGKEL (TRANSFER):", bold=True)
    b.add(f"{bengkel['bank_nama']}: {bengkel['no_rekening']}")
    b.add(f"a/n {bengkel['atas_nama']}")

    b.divider("-")
    b.center("Simpan struk ini sebagai")
    b.center("kartu bukti garansi!")
    b.center("")
    b.center("Terima kasih!")
    b.divider("=")
    return b


def build_receipt_payload(
    record: ServiceRecord, bengkel: Dict[str, str] | None = None
) -> Dict[str, Any]:
    """Data lengkap struk (58mm & 80mm) untuk reprint / cetak Bluetooth."""
    unit = record.unit
    customer = unit.customer
    info = bengkel or settings_service.default_bengkel_info()

    builder_58 = _build(record, 32, info)
    builder_80 = _build(record, 48, info)

    jobs: List[Dict[str, Any]] = [
        {
            "id": job.id,
            "deskripsi": job.deskripsi,
            "jumlah": job.jumlah,
            "jumlah_retur": int(job.jumlah_retur or 0),
            "harga": job.harga,
            "subtotal": job.subtotal,
        }
        for job in record.jobs
    ]
    parts: List[Dict[str, Any]] = [
        {
            "id": part.id,
            "nama_part": part.nama_part,
            "jumlah": part.jumlah,
            "jumlah_retur": int(part.jumlah_retur or 0),
            "harga_satuan": part.harga_satuan,
            "subtotal": part.subtotal,
        }
        for part in record.parts
    ]

    return {
        "id": record.id,
        "no_nota": record.no_nota,
        "waktu_service": record.waktu_service,
        "customer_nama": customer.nama,
        "customer_hp": customer.nomor_hp,
        "unit_deskripsi": describe_unit(unit),
        "keluhan_awal": record.keluhan_awal,
        "catatan_pengerjaan": record.catatan_pengerjaan,
        "biaya_jasa": record.biaya_jasa,
        "total_part": record.total_part,
        "diskon": record.diskon,
        "total_servis": record.total_servis,
        "metode_bayar": record.metode_bayar,
        "bayar": record.bayar,
        "kembalian": record.kembalian,
        "bergaransi": record.bergaransi,
        "garansi_sampai": record.garansi_sampai,
        "catatan_garansi": record.catatan_garansi,
        "status_klaim": record.status_klaim,
        "tanggal_klaim": record.tanggal_klaim,
        "garansi_aktif": warranty_service.is_active(record),
        "warranty_status": warranty_service.warranty_status(record),
        "status": record.status or "NORMAL",
        "void_reason": record.void_reason,
        "voided_at": record.voided_at,
        "voided_by": record.voided_by,
        "total_retur": record.total_retur or Decimal("0.00"),
        "retur_count": int(record.retur_count or 0),
        "total_neto": _total_neto(record),
        "jobs": jobs,
        "parts": parts,
        "bengkel_nama": info["nama"],
        "bengkel_tagline": info["tagline"],
        "bengkel_alamat": info["alamat"],
        "bengkel_telepon": info["telepon"],
        "bengkel_wa": info["wa"],
        "bengkel_bank_nama": info["bank_nama"],
        "bengkel_no_rekening": info["no_rekening"],
        "bengkel_atas_nama": info["atas_nama"],
        "printer_paper_width": settings.printer_paper_width,
        "struk_58": builder_58.lines(),
        "struk_80": builder_80.lines(),
        "escpos_58_base64": builder_58.to_base64(),
        "escpos_80_base64": builder_80.to_base64(),
    }


def record_summary(record: ServiceRecord) -> Dict[str, Any]:
    """Ringkasan nota untuk tabel riwayat & dasbor."""
    unit = record.unit
    customer = unit.customer
    status = record.status or "NORMAL"
    laba_kotor = Decimal("0.00")
    modal_tidak_diketahui = False
    modal_estimasi = False
    if status != "VOID":
        for part in record.parts:
            net_qty = _net_qty(part)
            if net_qty <= 0:
                continue
            if part.harga_modal_estimasi:
                modal_estimasi = True
            modal = part.harga_modal
            if modal is None and part.stock_item is not None:
                modal = part.stock_item.harga_modal
            if modal is None:
                modal_tidak_diketahui = True
                continue
            laba_kotor += (part.harga_satuan - modal) * net_qty
    return {
        "id": record.id,
        "no_nota": record.no_nota,
        "waktu_service": record.waktu_service,
        "unit_id": unit.id,
        "customer_id": customer.id,
        "customer_nama": customer.nama,
        "customer_hp": customer.nomor_hp,
        "unit_deskripsi": describe_unit(unit),
        "keluhan_awal": record.keluhan_awal,
        "biaya_jasa": record.biaya_jasa,
        "total_part": record.total_part,
        "diskon": record.diskon,
        "total_servis": record.total_servis,
        "metode_bayar": record.metode_bayar,
        "bayar": record.bayar,
        "kembalian": record.kembalian,
        "bergaransi": record.bergaransi,
        "garansi_sampai": record.garansi_sampai,
        "catatan_garansi": record.catatan_garansi,
        "status_klaim": record.status_klaim,
        "tanggal_klaim": record.tanggal_klaim,
        "garansi_aktif": warranty_service.is_active(record),
        "warranty_status": warranty_service.warranty_status(record),
        "jumlah_item": len(record.jobs) + len(record.parts),
        "laba_kotor": laba_kotor,
        "modal_tidak_diketahui": modal_tidak_diketahui,
        "modal_estimasi": modal_estimasi,
        "status": status,
        "void_reason": record.void_reason,
        "voided_at": record.voided_at,
        "voided_by": record.voided_by,
        "total_retur": record.total_retur or Decimal("0.00"),
        "retur_count": int(record.retur_count or 0),
        "total_neto": _total_neto(record),
    }


__all__ = ["build_receipt_payload", "record_summary", "Decimal"]
