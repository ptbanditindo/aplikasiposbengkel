"""Penyusun data struk & ringkasan transaksi servis."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any, Dict, List

from config import settings
from database.models import ServiceRecord
from services import settings_service, warranty_service, whatsapp_service
from services.customer_service import describe_unit
from services.escpos_service import ReceiptBuilder
from services.utils import format_rupiah, money, normalize_whatsapp


def _net_qty(item) -> int:
    return max(int(item.jumlah) - int(getattr(item, "jumlah_retur", 0) or 0), 0)


def _is_void(record: ServiceRecord) -> bool:
    return (getattr(record, "status", "NORMAL") or "NORMAL") == "VOID"


def _total_neto(record: ServiceRecord):
    if _is_void(record):
        return money(Decimal("0.00"))
    return money(record.total_servis - (record.total_retur or Decimal("0.00")))


def _sisa_bayar(record: ServiceRecord):
    if _is_void(record):
        return money(Decimal("0.00"))
    netto = money(
        max(
            Decimal(record.total_servis or 0)
            - Decimal(record.total_retur or 0),
            Decimal("0.00"),
        )
    )
    return money(max(netto - Decimal(record.total_dibayar or 0), Decimal("0.00")))


def _payment_label(payment) -> str:
    if payment.jenis in {"DP", "UANG_MUKA"}:
        return "Uang muka"
    if payment.jenis == "REFUND":
        return "Refund"
    return "Pembayaran"


def _duration_label(record: ServiceRecord) -> str:
    if not record.garansi_sampai:
        return ""
    days = (record.garansi_sampai - record.waktu_service.date()).days
    months = max(1, round(days / 30))
    return f" ({months} Bulan)"


def _label_item_name(unit) -> str:
    base = (
        getattr(unit, "nama_barang", None)
        or unit.tipe_radiator
        or unit.jenis_mobil
        or ""
    ).strip()
    if not base:
        return "Part"
    # Data radiator lama tetap memakai awalan Radiator agar label historis sama.
    if unit.unit_type == "RADIATOR_ONLY" and "radiator" not in base.lower():
        return f"Radiator {base}"
    return base


def _label_unit_text(unit) -> str:
    if unit.unit_type in {"MOBIL", "MOTOR_LENGKAP"}:
        text = unit.nopol or "-"
        if unit.jenis_mobil:
            text += f" ({unit.jenis_mobil})"
        return text
    if unit.unit_type == "PART_MOTOR":
        return "[PART MOTOR]"
    if unit.unit_type == "PART_MOBIL":
        return "[PART MOBIL]"
    return "[BAWA RADIATOR SAJA]"


def _labels(record: ServiceRecord) -> List[Dict[str, Any]]:
    """Satu strip label untuk setiap barang berlabel pada nota.

    Skema transaksi saat ini hanya memiliki satu unit per nota; daftar tetap
    dipakai agar beberapa strip dapat dicetak bila unit bertambah.
    """
    unit = record.unit
    # Unit lengkap tidak memakai strip label, walau data label lama masih ada.
    if (
        not unit
        or unit.unit_type not in {"PART_MOBIL", "PART_MOTOR", "RADIATOR_ONLY"}
        or not unit.label_radiator
    ):
        return []
    customer = unit.customer
    return [
        {
            "kode": unit.label_radiator,
            "nama": _label_item_name(unit),
            "unit": _label_unit_text(unit),
            "customer_nama": customer.nama,
            "customer_hp": customer.nomor_hp,
        }
    ]


def _append_label_strips(b: ReceiptBuilder, labels: List[Dict[str, Any]]) -> None:
    cut = "- " * (b.width // 2)
    b.add(cut)
    b.center("POTONG DI SINI", bold=True)
    for index, label in enumerate(labels):
        if index:
            b.add(cut)
        b.field("Pelanggan", label["customer_nama"])
        b.field("No. HP", label["customer_hp"])
        b.field("Unit", label["unit"])
        b.add(label["kode"], bold=True)
        b.add(f"({label['nama']})")
    b.divider("=")


def _show_defaults() -> Dict[str, bool]:
    return {field: True for field in settings_service.RECEIPT_FIELDS}


def _build(
    record: ServiceRecord,
    width: int,
    bengkel: Dict[str, str],
    payment=None,
    include_labels: bool = True,
    show: Optional[Dict[str, bool]] = None,
) -> ReceiptBuilder:
    unit = record.unit
    customer = unit.customer
    flags = _show_defaults()
    if show:
        flags.update({key: bool(value) for key, value in show.items() if key in flags})

    b = ReceiptBuilder(width)
    b.divider("=")
    b.center(bengkel["nama"], bold=True, double=True)
    if flags["tagline"] and bengkel["tagline"]:
        b.center(bengkel["tagline"])
    if flags["alamat"] and bengkel["alamat"]:
        b.center(bengkel["alamat"])
    contact = bengkel["wa"] or bengkel["telepon"]
    if flags["kontak"] and contact and contact != "-":
        b.center(f"Telp/WA: {contact}")
    b.divider("=")

    if flags["no_nota"]:
        b.kv("No. Nota", record.no_nota)
    if flags["tanggal"]:
        b.kv("Tanggal", record.waktu_service.strftime("%d/%m/%Y %H:%M"))
    cashier_name = (
        record.cashier_employee.nama
        if getattr(record, "cashier_employee", None) is not None
        else "Tidak dicatat"
    )
    mechanics = [
        row.employee.nama
        for row in getattr(record, "mechanics", []) or []
        if getattr(row, "employee", None) is not None
    ]
    if flags["kasir"]:
        b.kv("Kasir", cashier_name)
    if flags["mekanik"]:
        b.kv("Mekanik", ", ".join(mechanics) or "Tidak dicatat")
    if payment is not None:
        b.center("*** STRUK PELUNASAN ***", bold=True)
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

    if flags["pelanggan"]:
        b.field("Pelanggan", customer.nama)
    if flags["hp"]:
        b.field("No. HP", customer.nomor_hp)
    if flags["unit"]:
        b.field("Unit", describe_unit(unit))
    if flags["keluhan"]:
        b.field("Keluhan", record.keluhan_awal or "-")
    if flags["catatan"] and record.catatan_pengerjaan:
        b.field("Catatan", record.catatan_pengerjaan)
    b.divider("-")

    if flags["jasa"] and record.jobs:
        b.add("JASA:", bold=True)
        for job in record.jobs:
            b.item(job.deskripsi, job.jumlah, job.harga, job.subtotal)
    if flags["part"] and record.parts:
        b.add("PART:", bold=True)
        for part in record.parts:
            b.item(part.nama_part, part.jumlah, part.harga_satuan, part.subtotal)
    if not record.jobs and not record.parts:
        b.add("(tidak ada rincian pengerjaan)")

    b.divider("-")
    if flags["total_jasa"]:
        b.kv("Total Jasa", format_rupiah(record.biaya_jasa))
    if flags["total_part"]:
        b.kv("Total Part", format_rupiah(record.total_part))
    if flags["diskon"] and record.diskon and record.diskon > 0:
        b.kv("Diskon", "-" + format_rupiah(record.diskon))
    if flags["grand_total"]:
        b.kv("Grand Total", format_rupiah(record.total_servis), bold=True, double=True)
    total_retur = record.total_retur or Decimal("0.00")
    if total_retur > 0 or _is_void(record):
        b.kv("Retur", "-" + format_rupiah(total_retur))
        b.kv("Total Neto", format_rupiah(_total_neto(record)), bold=True)

    if flags["metode"]:
        if record.metode_bayar == "TRANSFER":
            b.kv("Metode Bayar", "TRANSFER BANK")
        else:
            b.kv("Metode Bayar", "CASH / TUNAI")
    if flags["bayar"]:
        b.kv("Bayar", format_rupiah(record.bayar))
    if flags["kembalian"]:
        b.kv("Kembali", format_rupiah(record.kembalian))

    sisa = _sisa_bayar(record)
    if flags["status_bayar"] and sisa > 0:
        b.divider("-")
        b.kv("Status Bayar", "BELUM LUNAS", bold=True)
        b.kv("Uang Muka / Dibayar", format_rupiah(record.total_dibayar or 0))
        b.kv("Sisa", format_rupiah(sisa), bold=True)
        if record.jatuh_tempo:
            b.kv("Jatuh Tempo", record.jatuh_tempo.strftime("%d/%m/%Y"))
    elif flags["status_bayar"]:
        b.kv("Status Bayar", "LUNAS")

    payments = list(getattr(record, "payments", []) or [])
    if payment is not None or len(payments) > 1:
        b.divider("-")
        b.add("RIWAYAT PEMBAYARAN:", bold=True)
        for row in payments:
            label = _payment_label(row)
            if row.jenis == "PELUNASAN":
                label = f"Pelunasan {row.metode}"
            b.kv(label, format_rupiah(row.nominal))
        b.kv("Total Dibayar", format_rupiah(record.total_dibayar or 0))
        b.kv("Sisa", format_rupiah(sisa))
        if payment is not None:
            b.kv("Waktu Bayar", payment.waktu.strftime("%d/%m/%Y %H:%M"))
            b.kv("Metode", "TRANSFER BANK" if payment.metode == "TRANSFER" else "CASH / TUNAI")

    if flags["garansi"]:
        b.divider("-")
        if record.sparepart_only:
            b.add("GARANSI SPAREPART:", bold=True)
            if _is_void(record):
                b.kv("Status", "DIBATALKAN")
            else:
                has_tukar = bool(
                    record.garansi_tukar_aktif and record.garansi_tukar_hari
                )
                has_barang = bool(
                    record.garansi_barang_aktif
                    and record.garansi_barang_sampai
                )
                if has_tukar:
                    tukar_sampai = record.waktu_service.date() + timedelta(
                        days=int(record.garansi_tukar_hari)
                    )
                    b.kv(
                        "Garansi tukar",
                        f"{int(record.garansi_tukar_hari)} hari"
                        f" (sampai {tukar_sampai:%d/%m/%Y})",
                    )
                if has_barang:
                    satuan = (record.garansi_barang_satuan or "HARI").lower()
                    b.kv(
                        "Garansi barang",
                        f"{int(record.garansi_barang_nilai)} {satuan}",
                    )
                    b.kv(
                        "Sampai",
                        record.garansi_barang_sampai.strftime("%d/%m/%Y"),
                    )
                if not has_tukar and not has_barang:
                    b.kv("Status", "TANPA GARANSI")
        else:
            b.add("GARANSI SERVIS:", bold=True)
            if _is_void(record):
                b.kv("Status", "DIBATALKAN")
            elif record.bergaransi and record.garansi_sampai:
                b.kv("Status", "BERGARANSI")
                b.kv(
                    "Sampai",
                    record.garansi_sampai.strftime("%d/%m/%Y")
                    + _duration_label(record),
                )
                if record.catatan_garansi:
                    b.field("Catatan", record.catatan_garansi)
            else:
                b.kv("Status", "TANPA GARANSI")

    if flags["rekening"]:
        b.divider("-")
        b.add("REKENING BENGKEL (TRANSFER):", bold=True)
        b.add(f"{bengkel['bank_nama']}: {bengkel['no_rekening']}")
        b.add(f"a/n {bengkel['atas_nama']}")

    if flags["footer"]:
        b.divider("-")
        b.center("Simpan struk ini sebagai")
        b.center("kartu bukti garansi!")
        b.center("")
        b.center("Terima kasih!")
    b.divider("=")
    if include_labels:
        labels = _labels(record)
        if labels:
            _append_label_strips(b, labels)
    return b


def receipt_wa_text(
    record: ServiceRecord,
    bengkel: Dict[str, str],
    show: Optional[Dict[str, bool]] = None,
) -> str:
    """Teks nota lengkap untuk WhatsApp, tanpa strip label potong."""
    builder = _build(record, 32, bengkel, include_labels=False, show=show)
    return "\n".join(line.rstrip() for line in builder.lines()).strip()


def build_receipt_payload(
    record: ServiceRecord,
    bengkel: Dict[str, str] | None = None,
    payment=None,
    show: Optional[Dict[str, bool]] = None,
) -> Dict[str, Any]:
    """Data lengkap struk (58mm & 80mm) untuk reprint / cetak Bluetooth."""
    unit = record.unit
    customer = unit.customer
    info = bengkel or settings_service.default_bengkel_info()

    if show is None:
        show = _show_defaults()
    builder_58 = _build(record, 32, info, payment, show=show)
    builder_80 = _build(record, 48, info, payment, show=show)
    labels = _labels(record)
    sisa = _sisa_bayar(record)
    payments = [
        {
            "id": row.id,
            "service_record_id": row.service_record_id,
            "jenis": row.jenis,
            "metode": row.metode,
            "nominal": row.nominal,
            "waktu": row.waktu,
            "operator": row.operator,
            "catatan": row.catatan,
            "request_id": row.request_id,
        }
        for row in (getattr(record, "payments", []) or [])
    ]

    jobs: List[Dict[str, Any]] = [
        {
            "id": job.id,
            "deskripsi": job.deskripsi,
            "jumlah": job.jumlah,
            "jumlah_retur": int(job.jumlah_retur or 0),
            "harga": job.harga,
            "subtotal": job.subtotal,
            "interval_servis_bulan": int(job.interval_servis_bulan or 0),
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
            "interval_servis_bulan": int(part.interval_servis_bulan or 0),
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
        "cashier_nama": (
            record.cashier_employee.nama
            if getattr(record, "cashier_employee", None) is not None
            else "Tidak dicatat"
        ),
        "mekanik_nama": (
            ", ".join(
                row.employee.nama
                for row in getattr(record, "mechanics", []) or []
                if getattr(row, "employee", None) is not None
            )
            or "Tidak dicatat"
        ),
        "keluhan_awal": record.keluhan_awal,
        "catatan_pengerjaan": record.catatan_pengerjaan,
        "biaya_jasa": record.biaya_jasa,
        "total_part": record.total_part,
        "diskon": record.diskon,
        "total_servis": record.total_servis,
        "metode_bayar": record.metode_bayar,
        "bayar": record.bayar,
        "kembalian": record.kembalian,
        "status_bayar": "LUNAS" if _is_void(record) else (record.status_bayar or "LUNAS"),
        "jenis_bayar": record.jenis_bayar
        or ("KREDIT" if record.status_bayar == "BELUM_LUNAS" else "LUNAS"),
        "jatuh_tempo": record.jatuh_tempo,
        "rencana_bayar": money(record.rencana_bayar or 0),
        "total_dibayar": money(record.total_dibayar or 0),
        "sisa_bayar": sisa,
        "bergaransi": record.bergaransi,
        "garansi_sampai": record.garansi_sampai,
        "catatan_garansi": record.catatan_garansi,
        "sparepart_only": bool(record.sparepart_only),
        "garansi_tukar_aktif": bool(record.garansi_tukar_aktif),
        "garansi_tukar_hari": int(record.garansi_tukar_hari or 0),
        "garansi_barang_aktif": bool(record.garansi_barang_aktif),
        "garansi_barang_nilai": int(record.garansi_barang_nilai or 0),
        "garansi_barang_satuan": record.garansi_barang_satuan or "HARI",
        "garansi_barang_sampai": record.garansi_barang_sampai,
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
        "labels": labels,
        "jobs": jobs,
        "parts": parts,
        "payments": payments,
        "wa_text": receipt_wa_text(record, info, show=show),
        "completion_wa_text": whatsapp_service.completion_wa_text(record, info),
        "customer_wa": normalize_whatsapp(customer.nomor_hp),
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
        "status_bayar": "LUNAS" if status == "VOID" else (record.status_bayar or "LUNAS"),
        "jenis_bayar": record.jenis_bayar
        or ("KREDIT" if record.status_bayar == "BELUM_LUNAS" else "LUNAS"),
        "jatuh_tempo": record.jatuh_tempo,
        "rencana_bayar": money(record.rencana_bayar or 0),
        "total_dibayar": money(record.total_dibayar or 0),
        "sisa_bayar": _sisa_bayar(record),
        "bergaransi": record.bergaransi,
        "garansi_sampai": record.garansi_sampai,
        "catatan_garansi": record.catatan_garansi,
        "sparepart_only": bool(record.sparepart_only),
        "garansi_tukar_aktif": bool(record.garansi_tukar_aktif),
        "garansi_tukar_hari": int(record.garansi_tukar_hari or 0),
        "garansi_barang_aktif": bool(record.garansi_barang_aktif),
        "garansi_barang_nilai": int(record.garansi_barang_nilai or 0),
        "garansi_barang_satuan": record.garansi_barang_satuan or "HARI",
        "garansi_barang_sampai": record.garansi_barang_sampai,
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


__all__ = ["build_receipt_payload", "receipt_wa_text", "record_summary", "Decimal"]
