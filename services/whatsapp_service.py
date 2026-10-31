"""Pesan WhatsApp, izin pelanggan, dan log upaya membuka WhatsApp (Tahap 12).

Aplikasi tidak mengirim pesan di latar belakang. Backend hanya menyusun teks,
membuat tautan `wa.me`, dan mencatat status upaya yang dilakukan kasir.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import ServiceRecord, WhatsAppLog
from services import audit_service, payment_service, settings_service
from services.auth_service import Operator
from services.customer_service import describe_unit
from services.errors import BusinessValidationError, ConflictError, NotFoundError
from services.utils import (
    format_rupiah,
    is_valid_whatsapp,
    mask_phone,
    normalize_whatsapp,
)

STATUS_OPENED = "DIBUKA"
STATUS_CANCELLED = "DIBATALKAN"
STATUS_UNAVAILABLE = "TIDAK_TERSEDIA"
VALID_STATUSES = {STATUS_OPENED, STATUS_CANCELLED, STATUS_UNAVAILABLE}

JENIS_STRUK = "struk"
JENIS_FOLLOWUP = "followup"
JENIS_GARANSI = "garansi"
JENIS_PIUTANG = "piutang"
VALID_JENIS = {JENIS_STRUK, JENIS_FOLLOWUP, JENIS_GARANSI, JENIS_PIUTANG}

DEFAULT_TEMPLATE = (
    "Halo {nama}, terima kasih telah servis di {bengkel}.\n"
    "Nota {no_nota} tanggal {tanggal}\n"
    "Unit: {unit}\n"
    "Total: {total}\n"
    "Status bayar: {status_bayar}\n"
    "Sisa bayar: {sisa}\n"
    "Garansi sampai: {garansi}\n\n"
    "Pesan dari {bengkel}."
)


class _SafeDict(dict):
    def __missing__(self, key):  # pragma: no cover - placeholder tak dikenal
        return "{" + key + "}"


def render_template(template: str, values: Dict[str, Any]) -> str:
    base = (template or "").strip() or DEFAULT_TEMPLATE
    return base.format_map(_SafeDict(values)).strip()


def record_values(record: ServiceRecord, bengkel: Dict[str, str]) -> Dict[str, str]:
    customer = record.unit.customer
    sisa = payment_service.record_sisa(record)
    lunas = (record.status or "NORMAL") == "VOID" or sisa <= 0
    garansi = (
        record.garansi_sampai.strftime("%d/%m/%Y")
        if record.bergaransi and record.garansi_sampai
        else "-"
    )
    return {
        "nama": customer.nama,
        "nomor_hp": customer.nomor_hp,
        "unit": describe_unit(record.unit),
        "no_nota": record.no_nota,
        "tanggal": record.waktu_service.strftime("%d/%m/%Y"),
        "total": format_rupiah(record.total_servis),
        "total_neto": format_rupiah(payment_service.record_netto(record)),
        "status_bayar": "LUNAS" if lunas else "BELUM LUNAS",
        "sisa": format_rupiah(sisa),
        "garansi": garansi,
        "keluhan": record.keluhan_awal or "-",
        "bengkel": bengkel.get("nama", ""),
        "alamat": bengkel.get("alamat", ""),
        "telepon": bengkel.get("telepon", ""),
        "wa_bengkel": bengkel.get("wa", ""),
    }


def record_wa_text(
    record: ServiceRecord, bengkel: Dict[str, str], template: str = ""
) -> str:
    return render_template(template, record_values(record, bengkel))


def build_link(nomor: str, message: str) -> str:
    digits = normalize_whatsapp(nomor)
    if not digits:
        return ""
    return f"https://wa.me/{digits}?text={quote(message, safe='')}"


def append_attempt(
    db: Session,
    customer,
    *,
    jenis: str,
    status: str,
    message: str,
    operator: Operator,
    record: Optional[ServiceRecord] = None,
    catatan: Optional[str] = None,
    now: Optional[datetime] = None,
):
    """Tambahkan log WhatsApp tanpa membuka transaksi baru.

    Pemanggil bertanggung jawab atas transaksi; dipakai juga oleh follow-up
    (Tahap 13) yang mencatat beberapa perubahan dalam satu atom.
    """
    normalized = (status or "").strip().upper()
    if normalized not in VALID_STATUSES:
        raise BusinessValidationError(
            "Status WhatsApp harus DIBUKA, DIBATALKAN, atau TIDAK_TERSEDIA."
        )
    normalized_jenis = (jenis or JENIS_STRUK).strip().lower()
    if normalized_jenis not in VALID_JENIS:
        raise BusinessValidationError(
            "Jenis pesan WhatsApp harus struk, followup, garansi, atau piutang."
        )
    if not bool(getattr(customer, "wa_consent", True)):
        raise ConflictError("Pelanggan belum menyetujui pesan WhatsApp.")
    if normalized == STATUS_OPENED and not is_valid_whatsapp(customer.nomor_hp):
        raise BusinessValidationError("Nomor WhatsApp pelanggan tidak valid.")

    link = (
        build_link(customer.nomor_hp, message)
        if normalized == STATUS_OPENED
        else ""
    )
    moment = now or datetime.now()
    log = WhatsAppLog(
        service_record_id=record.id if record is not None else None,
        customer_id=customer.id,
        jenis=normalized_jenis,
        nomor_masked=mask_phone(customer.nomor_hp),
        status=normalized,
        pesan=message,
        operator=operator.label,
        created_at=moment,
    )
    db.add(log)
    audit_service.record_event(
        db,
        operator,
        audit_service.ACTION_WHATSAPP,
        (
            audit_service.REFERENCE_SERVICE_RECORD
            if record is not None
            else audit_service.REFERENCE_CUSTOMER
        ),
        reference_id=record.no_nota if record is not None else str(customer.id),
        reason=f"WhatsApp {normalized_jenis} {normalized}"
        + (f": {catatan}" if catatan else ""),
        now=moment,
    )
    db.flush()
    return log, link


def log_attempt(
    db: Session,
    record_id: int,
    status: str,
    operator: Operator,
    catatan: Optional[str] = None,
    now: Optional[datetime] = None,
):
    """Catat upaya WhatsApp struk. Mengembalikan (log, wa_text, link)."""
    with db.begin():
        record = db.get(ServiceRecord, record_id)
        if record is None:
            raise NotFoundError("Nota servis tidak ditemukan.")
        info = settings_service.get_bengkel_info(db)
        template = settings_service.get_ops_settings(db)["wa_template"]
        message = record_wa_text(record, info, template)
        log, link = append_attempt(
            db,
            record.unit.customer,
            jenis=JENIS_STRUK,
            status=status,
            message=message,
            operator=operator,
            record=record,
            catatan=catatan,
            now=now,
        )

    db.refresh(log)
    return log, message, link


def list_logs(
    db: Session, record_id: Optional[int] = None, limit: int = 100
) -> List[WhatsAppLog]:
    statement = select(WhatsAppLog).order_by(
        WhatsAppLog.created_at.desc(), WhatsAppLog.id.desc()
    )
    if record_id is not None:
        if db.get(ServiceRecord, record_id) is None:
            raise NotFoundError("Nota servis tidak ditemukan.")
        statement = statement.where(WhatsAppLog.service_record_id == record_id)
    return list(db.scalars(statement.limit(max(1, min(limit, 500)))).all())
