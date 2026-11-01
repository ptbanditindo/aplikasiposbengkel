"""Pesan WhatsApp, izin pelanggan, dan log upaya membuka WhatsApp (Tahap 12).

Aplikasi tidak mengirim pesan di latar belakang. Backend hanya menyusun teks,
membuat tautan `wa.me`, dan mencatat status upaya yang dilakukan kasir.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Customer, ServiceRecord, VehicleOrUnit, WhatsAppLog
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

def completion_wa_text(record: ServiceRecord, bengkel: Dict[str, str]) -> str:
    """Satu-satunya sumber kalimat "kendaraan selesai" untuk pelanggan.

    Tidak memakai kata hutang/piutang/tagihan/kekurangan; sisa pembayaran
    disebut sebagai informasi pelunasan saat pengambilan.
    """
    customer = record.unit.customer
    unit = describe_unit(record.unit)
    bengkel_nama = (bengkel.get("nama") or "").strip()
    text = (
        f"Halo Bapak/Ibu {customer.nama}, kendaraan {unit} dengan nota "
        f"{record.no_nota} sudah selesai dikerjakan dan siap diambil"
        + (f" di {bengkel_nama}" if bengkel_nama else "")
        + "."
    )
    sisa = payment_service.record_sisa(record)
    if (record.status or "NORMAL") == "VOID" or sisa <= 0:
        return text + " Terima kasih."

    parts = [text]
    if Decimal(record.total_dibayar or 0) > 0:
        parts.append("Pembayaran awal sudah kami terima.")
    parts.append(
        f"Sisa pembayaran {format_rupiah(sisa)} dapat diselesaikan saat pengambilan."
    )
    parts.append("Terima kasih.")
    return " ".join(parts)


def completion_wa_text_multi(
    records: List[ServiceRecord], bengkel: Dict[str, str]
) -> str:
    """Pesan satu kali untuk semua nota piutang pelanggan yang sama."""
    if not records:
        return ""
    ordered = sorted(
        records, key=lambda record: (record.jatuh_tempo or date.max, record.waktu_service)
    )
    customer = ordered[0].unit.customer
    bengkel_nama = (bengkel.get("nama") or "").strip()
    labels = [
        f"{describe_unit(record.unit)} (nota {record.no_nota})"
        for record in ordered
    ]
    if len(labels) == 2:
        kendaraan = f"{labels[0]} dan {labels[1]}"
    else:
        kendaraan = ", ".join(labels[:-1]) + ", dan " + labels[-1]
    text = (
        f"Halo Bapak/Ibu {customer.nama}, kendaraan {kendaraan} sudah selesai "
        "dikerjakan dan siap diambil"
        + (f" di {bengkel_nama}" if bengkel_nama else "")
        + "."
    )
    if any(Decimal(record.total_dibayar or 0) > 0 for record in ordered):
        text += " Pembayaran awal sudah kami terima."
    total = Decimal("0.00")
    rincian = []
    for record in ordered:
        sisa = payment_service.record_sisa(record)
        total += sisa
        rincian.append(f"nota {record.no_nota} {format_rupiah(sisa)}")
    text += " Rincian sisa pembayaran: " + "; ".join(rincian) + "."
    text += (
        f" Total sisa {format_rupiah(total)} dapat diselesaikan saat pengambilan."
        " Terima kasih."
    )
    return text


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
    jenis: str = JENIS_STRUK,
):
    """Catat upaya WhatsApp nota. Mengembalikan (log, wa_text, link)."""
    normalized_jenis = (jenis or JENIS_STRUK).strip().lower()
    normalized_status = (status or "").strip().upper()
    if normalized_jenis not in {JENIS_STRUK, JENIS_PIUTANG}:
        raise BusinessValidationError(
            "Jenis pesan WhatsApp nota harus struk atau piutang."
        )
    moment = now or datetime.now()
    with db.begin():
        record = db.get(ServiceRecord, record_id)
        if record is None:
            raise NotFoundError("Nota servis tidak ditemukan.")
        info = settings_service.get_bengkel_info(db)
        if normalized_jenis == JENIS_STRUK:
            # Impor lokal agar tidak melingkar: receipt_service memakai layanan ini.
            from services.receipt_service import receipt_wa_text

            message = receipt_wa_text(record, info)
        else:
            message = completion_wa_text(record, info)
        log, link = append_attempt(
            db,
            record.unit.customer,
            jenis=normalized_jenis,
            status=normalized_status,
            message=message,
            operator=operator,
            record=record,
            catatan=catatan,
            now=moment,
        )
        if (
            normalized_jenis == JENIS_PIUTANG
            and normalized_status == STATUS_OPENED
            and (record.status or "NORMAL") == "NORMAL"
            and (record.status_bayar or "LUNAS") == "BELUM_LUNAS"
            and payment_service.record_sisa(record) > 0
        ):
            record.diingatkan_pada = moment
            from services import followup_service

            followup_service.sync_items(db, commit=False)
            followup_service.mark_piutang_followed(
                db,
                record.unit.customer.id,
                moment,
                operator.label,
                "Pemberitahuan kendaraan selesai lewat WhatsApp.",
            )

    db.refresh(log)
    return log, message, link


def remind_receivable(
    db: Session,
    record_id: int,
    operator: Operator,
    now: Optional[datetime] = None,
):
    """Kirim pengingat piutang sekali per siklus jatuh tempo.

    Pengingat hanya boleh dibuka pada hari jatuh tempo atau setelahnya.
    Mengubah jatuh tempo mengosongkan penanda sehingga pengingat aktif lagi.
    """
    moment = now or datetime.now()
    with db.begin():
        record = db.get(ServiceRecord, record_id)
        if record is None:
            raise NotFoundError("Nota servis tidak ditemukan.")
        if (record.status or "NORMAL") == "VOID":
            raise ConflictError("Nota sudah dibatalkan (VOID).")
        if (
            (record.status_bayar or "LUNAS") == "LUNAS"
            or payment_service.record_sisa(record) <= 0
        ):
            raise ConflictError("Nota ini sudah lunas.")
        if record.diingatkan_pada is not None:
            raise ConflictError(
                "Pengingat nota ini sudah dikirim. Ubah jatuh tempo untuk "
                "mengingatkan lagi."
            )
        ops = settings_service.get_ops_settings(db)
        if not settings_service.within_followup_window(ops, moment):
            raise ConflictError(settings_service.followup_window_message(ops))
        if record.jatuh_tempo is not None and moment.date() < record.jatuh_tempo:
            raise BusinessValidationError(
                "Pengingat bisa dikirim mulai "
                f"{record.jatuh_tempo.strftime('%d-%m-%Y')}."
            )
        info = settings_service.get_bengkel_info(db)
        message = completion_wa_text(record, info)
        log, link = append_attempt(
            db,
            record.unit.customer,
            jenis=JENIS_PIUTANG,
            status=STATUS_OPENED,
            message=message,
            operator=operator,
            record=record,
            now=moment,
        )
        record.diingatkan_pada = moment
        from services import followup_service

        followup_service.sync_items(db, commit=False)
        followup_service.mark_piutang_followed(
            db,
            record.unit.customer.id,
            moment,
            operator.label,
            "Pengingat piutang dari daftar piutang.",
        )

    db.refresh(log)
    return log, message, link


def remind_customer_receivables(
    db: Session,
    customer_id: int,
    operator: Operator,
    now: Optional[datetime] = None,
):
    """Kirim satu pengingat untuk semua nota piutang pelanggan."""
    moment = now or datetime.now()
    with db.begin():
        customer = db.get(Customer, customer_id)
        if customer is None:
            raise NotFoundError("Pelanggan tidak ditemukan.")
        rows = list(
            db.scalars(
                select(ServiceRecord)
                .join(VehicleOrUnit, ServiceRecord.unit_id == VehicleOrUnit.id)
                .where(
                    VehicleOrUnit.customer_id == customer_id,
                    ServiceRecord.status == "NORMAL",
                )
                .order_by(
                    ServiceRecord.jatuh_tempo.asc(),
                    ServiceRecord.waktu_service.asc(),
                )
            )
            .unique()
            .all()
        )
        records = [
            record
            for record in rows
            if (record.status_bayar or "LUNAS") == "BELUM_LUNAS"
            and payment_service.record_sisa(record) > 0
        ]
        if not records:
            raise ConflictError("Tidak ada piutang berjalan.")
        pending = [record for record in records if record.diingatkan_pada is None]
        if not pending:
            raise ConflictError(
                "Pengingat pelanggan ini sudah dikirim. Ubah jatuh tempo per "
                "nota untuk mengingatkan lagi."
            )
        ops = settings_service.get_ops_settings(db)
        if not settings_service.within_followup_window(ops, moment):
            raise ConflictError(settings_service.followup_window_message(ops))
        today = moment.date()
        eligible = [
            record
            for record in pending
            if record.jatuh_tempo is None or record.jatuh_tempo <= today
        ]
        if not eligible:
            earliest = min(
                record.jatuh_tempo
                for record in pending
                if record.jatuh_tempo is not None
            )
            raise BusinessValidationError(
                "Pengingat bisa dikirim mulai "
                f"{earliest.strftime('%d-%m-%Y')}."
            )
        info = settings_service.get_bengkel_info(db)
        message = completion_wa_text_multi(records, info)
        log = None
        link = ""
        for record in records:
            log, link = append_attempt(
                db,
                customer,
                jenis=JENIS_PIUTANG,
                status=STATUS_OPENED,
                message=message,
                operator=operator,
                record=record,
                now=moment,
            )
            record.diingatkan_pada = moment
        from services import followup_service

        followup_service.sync_items(db, commit=False)
        followup_service.mark_piutang_followed(
            db,
            customer.id,
            moment,
            operator.label,
            "Pengingat piutang pelanggan.",
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
