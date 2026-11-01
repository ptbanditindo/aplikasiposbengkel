"""Gerbang pusat pesan pelanggan: izin, jam, DNC, dan batas anti-gangguan.

Semua tautan `wa.me` untuk follow-up, piutang, pengerjaan, dan chat melewati
modul ini agar aturan tidak tersebar di beberapa layanan.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import (
    Customer,
    FollowupItem,
    PengerjaanNota,
    ServiceRecord,
    VehicleOrUnit,
    WhatsAppLog,
)
from services import settings_service, whatsapp_service
from services.errors import ConflictError

PESAN_JENIS = {
    whatsapp_service.JENIS_FOLLOWUP,
    whatsapp_service.JENIS_GARANSI,
    whatsapp_service.JENIS_PIUTANG,
}
DNC_BLOCKED = {whatsapp_service.JENIS_FOLLOWUP, whatsapp_service.JENIS_GARANSI}
OPEN_ITEM_STATUS = {"BARU", "SUDAH_FOLLOWUP", "MASIH_KENDALA"}
CLOSED_STATUS = {"ARSIP", "SELESAI", "TIDAK_DATANG", "AKAN_DATANG", "JANJI_BAYAR"}


def wa_gate(
    db: Session,
    customer: Customer,
    jenis: str,
    moment: Optional[datetime] = None,
) -> Tuple[bool, str, str]:
    """Izin + jam + DNC. Mengembalikan (boleh, alasan, peringatan)."""
    moment = moment or datetime.now()
    ops = settings_service.get_ops_settings(db)
    if not bool(customer.wa_consent):
        return (
            False,
            "Pelanggan belum memberi izin menerima pesan WhatsApp.",
            "",
        )
    if not settings_service.within_followup_window(ops, moment):
        return False, settings_service.followup_window_message(ops), ""
    warning = ""
    if bool(customer.do_not_contact):
        if jenis in DNC_BLOCKED:
            return (
                False,
                "Pelanggan meminta berhenti dihubungi (DNC).",
                "",
            )
        warning = (
            "Pelanggan meminta berhenti dihubungi. Kirim hanya untuk urusan "
            "transaksi yang sedang berjalan."
        )
    return True, "", warning


def _count_message_days(
    db: Session,
    customer_id: int,
    since: datetime,
    until: datetime,
    jenis: Optional[str] = None,
) -> int:
    statement = (
        select(func.count(func.distinct(func.date(WhatsAppLog.created_at))))
        .where(
            WhatsAppLog.customer_id == customer_id,
            WhatsAppLog.status == whatsapp_service.STATUS_OPENED,
            WhatsAppLog.created_at >= since,
            WhatsAppLog.created_at < until,
            WhatsAppLog.jenis.in_(PESAN_JENIS),
        )
    )
    if jenis is not None:
        statement = statement.where(WhatsAppLog.jenis == jenis)
    return int(db.scalar(statement) or 0)


def _last_message_at(
    db: Session, customer_id: int, jenis: str
) -> Optional[datetime]:
    return db.scalar(
        select(func.max(WhatsAppLog.created_at)).where(
            WhatsAppLog.customer_id == customer_id,
            WhatsAppLog.status == whatsapp_service.STATUS_OPENED,
            WhatsAppLog.jenis == jenis,
        )
    )


def _open_pengerjaan_exists(db: Session, customer_id: int) -> bool:
    row = db.scalar(
        select(PengerjaanNota.id)
        .join(ServiceRecord, PengerjaanNota.service_record_id == ServiceRecord.id)
        .join(VehicleOrUnit, ServiceRecord.unit_id == VehicleOrUnit.id)
        .where(
            VehicleOrUnit.customer_id == customer_id,
            PengerjaanNota.diambil_pada.is_(None),
            ServiceRecord.status == "NORMAL",
        )
        .limit(1)
    )
    return row is not None


def _due_item_exists(
    db: Session,
    customer_id: int,
    jenis: str,
    today: date,
    exclude_id: Optional[int],
) -> bool:
    statement = select(FollowupItem.id).where(
        FollowupItem.customer_id == customer_id,
        FollowupItem.jenis == jenis,
        FollowupItem.status.in_(OPEN_ITEM_STATUS),
        FollowupItem.jatuh_tempo.is_not(None),
        FollowupItem.jatuh_tempo <= today,
    )
    if exclude_id is not None:
        statement = statement.where(FollowupItem.id != exclude_id)
    return db.scalar(statement.limit(1)) is not None


def blocked_by_pengerjaan(db: Session, customer_id: int) -> bool:
    return _open_pengerjaan_exists(db, customer_id)


def daily_cap_reason(
    db: Session, customer_id: int, moment: datetime, ops: dict
) -> str:
    max_hari = int(ops.get("maks_pesan_hari", 1))
    start_day = datetime.combine(moment.date(), datetime.min.time())
    tomorrow = start_day + timedelta(days=1)
    if _count_message_days(db, customer_id, start_day, tomorrow) >= max_hari:
        return "Batas pesan hari ini sudah tercapai. Coba lagi besok."
    return ""


def policy_reason(
    db: Session,
    item: FollowupItem,
    moment: datetime,
    ops: dict,
) -> str:
    """Alasan item belum boleh di-follow-up karena prioritas atau batas pesan."""
    today = moment.date()
    max_hari = int(ops.get("maks_pesan_hari", 1))
    max_bulan = int(ops.get("maks_pesan_bulan", 2))
    jeda = int(ops.get("jeda_prospek_servis_hari", 7))

    start_day = datetime.combine(today, datetime.min.time())
    tomorrow = start_day + timedelta(days=1)
    if (
        _count_message_days(db, item.customer_id, start_day, tomorrow)
        >= max_hari
    ):
        return "Batas pesan hari ini sudah tercapai. Coba lagi besok."

    if item.jenis in {"prospek", "servis_berkala"}:
        month_start = start_day - timedelta(days=30)
        if (
            _count_message_days(
                db,
                item.customer_id,
                month_start,
                tomorrow,
                jenis=whatsapp_service.JENIS_FOLLOWUP,
            )
            >= max_bulan
        ):
            return (
                "Batas "
                + str(max_bulan)
                + " pesan per bulan untuk prospek dan servis sudah tercapai."
            )
        last_at = _last_message_at(
            db, item.customer_id, whatsapp_service.JENIS_FOLLOWUP
        )
        if last_at is not None and moment < last_at + timedelta(days=jeda):
            return (
                "Jeda minimal "
                + str(jeda)
                + " hari untuk prospek dan servis belum selesai."
            )

    if item.jenis != "piutang" and _due_item_exists(
        db, item.customer_id, "piutang", today, item.id
    ):
        return "Selesaikan pengingat piutang pelanggan ini lebih dulu."
    if item.jenis in {"garansi", "servis_berkala", "prospek"} and _due_item_exists(
        db, item.customer_id, "garansi", today, item.id
    ):
        return "Pengingat garansi pelanggan ini lebih utama."
    if item.jenis == "prospek" and _due_item_exists(
        db, item.customer_id, "servis_berkala", today, item.id
    ):
        return "Pengingat servis berkala pelanggan ini lebih utama."
    if _open_pengerjaan_exists(db, item.customer_id):
        return "Masih ada unit pelanggan di bengkel. Kabari pengambilan lebih dulu."
    return ""


def ensure_can_open(
    db: Session,
    customer: Customer,
    jenis: str,
    moment: Optional[datetime] = None,
) -> str:
    """Lempar ConflictError bila tautan wa.me tidak boleh dibuat."""
    allowed, reason, warning = wa_gate(db, customer, jenis, moment)
    if not allowed:
        raise ConflictError(reason)
    return warning


def customer_wa_link(
    db: Session,
    customer: Customer,
    moment: Optional[datetime] = None,
) -> Tuple[bool, str, str]:
    """Pemeriksaan untuk tombol Chat tanpa pesan siap kirim."""
    allowed, reason, warning = wa_gate(
        db, customer, whatsapp_service.JENIS_FOLLOWUP, moment
    )
    if not allowed:
        return False, reason, ""
    digits = (customer.nomor_hp or "").strip()
    if not digits:
        return False, "Nomor WhatsApp pelanggan belum diisi.", warning
    return True, "", warning
