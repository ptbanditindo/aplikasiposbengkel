"""Penyusun data struk & ringkasan transaksi servis."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List

from config import settings
from database.models import ServiceRecord
from services import warranty_service
from services.customer_service import describe_unit
from services.escpos_service import ReceiptBuilder
from services.utils import format_rupiah


def _duration_label(record: ServiceRecord) -> str:
    if not record.garansi_sampai:
        return ""
    days = (record.garansi_sampai - record.waktu_service.date()).days
    months = max(1, round(days / 30))
    return f" ({months} Bulan)"


def _build(record: ServiceRecord, width: int) -> ReceiptBuilder:
    unit = record.unit
    customer = unit.customer

    b = ReceiptBuilder(width)
    b.divider("=")
    b.center(settings.bengkel_nama, bold=True, double=True)
    if settings.bengkel_tagline:
        b.center(settings.bengkel_tagline)
    if settings.bengkel_alamat:
        b.center(settings.bengkel_alamat)
    contact = settings.bengkel_wa or settings.bengkel_telepon
    if contact and contact != "-":
        b.center(f"Telp/WA: {contact}")
    b.divider("=")

    b.kv("No. Nota", record.no_nota)
    b.kv("Tanggal", record.waktu_service.strftime("%d/%m/%Y %H:%M"))
    b.kv("Kasir", "Kasir")
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

    if record.metode_bayar == "TRANSFER":
        b.kv("Metode Bayar", "TRANSFER BANK")
    else:
        b.kv("Metode Bayar", "CASH / TUNAI")
    b.kv("Bayar", format_rupiah(record.bayar))
    b.kv("Kembali", format_rupiah(record.kembalian))

    b.divider("-")
    b.add("GARANSI SERVIS:", bold=True)
    if record.bergaransi and record.garansi_sampai:
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
    b.add(f"{settings.bengkel_bank_nama}: {settings.bengkel_no_rekening}")
    b.add(f"a/n {settings.bengkel_atas_nama}")

    b.divider("-")
    b.center("Simpan struk ini sebagai")
    b.center("kartu bukti garansi!")
    b.center("")
    b.center("Terima kasih!")
    b.divider("=")
    return b


def build_receipt_payload(record: ServiceRecord) -> Dict[str, Any]:
    """Data lengkap struk (58mm & 80mm) untuk reprint / cetak Bluetooth."""
    unit = record.unit
    customer = unit.customer

    builder_58 = _build(record, 32)
    builder_80 = _build(record, 48)

    jobs: List[Dict[str, Any]] = [
        {
            "id": job.id,
            "deskripsi": job.deskripsi,
            "jumlah": job.jumlah,
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
        "jobs": jobs,
        "parts": parts,
        "bengkel_nama": settings.bengkel_nama,
        "bengkel_tagline": settings.bengkel_tagline,
        "bengkel_alamat": settings.bengkel_alamat,
        "bengkel_telepon": settings.bengkel_telepon,
        "bengkel_wa": settings.bengkel_wa,
        "bengkel_bank_nama": settings.bengkel_bank_nama,
        "bengkel_no_rekening": settings.bengkel_no_rekening,
        "bengkel_atas_nama": settings.bengkel_atas_nama,
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
    laba_kotor = Decimal("0.00")
    for part in record.parts:
        modal = part.harga_modal
        if modal is None and part.stock_item is not None:
            modal = part.stock_item.harga_modal
        if modal is None:
            continue
        laba_kotor += (part.harga_satuan - modal) * part.jumlah
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
    }


__all__ = ["build_receipt_payload", "record_summary", "Decimal"]
