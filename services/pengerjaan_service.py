"""Follow-up kendaraan selesai untuk nota dengan penanda unit ditinggal.

Nota yang dicatat dengan opsi "Unit ditinggal" membuat satu baris di
`pengerjaan_nota`. Modul ini membaca baris tersebut sebagai daftar unit yang
masih di bengkel, mencatat perubahan status, lalu menutupnya ketika unit sudah
diambil.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from database.models import (
    PengerjaanNota,
    PengerjaanNotaEvent,
    ServiceRecord,
    VehicleOrUnit,
    WhatsAppLog,
)
from services import payment_service
from services.auth_service import Operator
from services.customer_service import describe_unit
from services.errors import BusinessValidationError, ConflictError, NotFoundError

STATUS_DIKERJAKAN = "SEDANG_DIKERJAKAN"
STATUS_MENUNGGU_SPAREPART = "MENUNGGU_SPAREPART"
STATUS_MENUNGGU_PERSETUJUAN = "MENUNGGU_PERSETUJUAN"
STATUS_SIAP_DIAMBIL = "SELESAI_SIAP_DIAMBIL"
STATUS_DIAMBIL = "SUDAH_DIAMBIL"
STATUS_VALUES = {
    STATUS_DIKERJAKAN,
    STATUS_MENUNGGU_SPAREPART,
    STATUS_MENUNGGU_PERSETUJUAN,
    STATUS_SIAP_DIAMBIL,
    STATUS_DIAMBIL,
}
STATUS_LABELS = {
    STATUS_DIKERJAKAN: "Sedang dikerjakan",
    STATUS_MENUNGGU_SPAREPART: "Menunggu sparepart",
    STATUS_MENUNGGU_PERSETUJUAN: "Menunggu persetujuan",
    STATUS_SIAP_DIAMBIL: "Selesai, siap diambil",
    STATUS_DIAMBIL: "Sudah diambil",
}


def _statement():
    return (
        select(PengerjaanNota)
        .join(ServiceRecord, PengerjaanNota.service_record_id == ServiceRecord.id)
        .where(
            PengerjaanNota.diambil_pada.is_(None),
            ServiceRecord.status == "NORMAL",
        )
        .options(
            joinedload(PengerjaanNota.service_record)
            .joinedload(ServiceRecord.unit)
            .joinedload(VehicleOrUnit.customer)
        )
    )


def serialize_item(marker: PengerjaanNota, today: Optional[date] = None) -> Dict[str, Any]:
    record = marker.service_record
    customer = record.unit.customer
    day = today or date.today()
    reference = marker.diambil_pada or marker.dibuat_pada
    days = max((day - reference.date()).days, 0) if reference else 0
    late = bool(
        marker.diambil_pada is None
        and marker.janji_ambil is not None
        and marker.janji_ambil < day
    )
    return {
        "id": marker.id,
        "record_id": record.id,
        "no_nota": record.no_nota,
        "waktu_service": record.waktu_service,
        "customer_id": customer.id,
        "customer_nama": customer.nama,
        "nomor_hp": customer.nomor_hp,
        "unit_deskripsi": describe_unit(record.unit),
        "total_servis": record.total_servis,
        "sisa_bayar": payment_service.record_sisa(record),
        "status_pengerjaan": marker.status_pengerjaan,
        "status_label": STATUS_LABELS.get(marker.status_pengerjaan, marker.status_pengerjaan),
        "janji_ambil": marker.janji_ambil,
        "dibuat_pada": marker.dibuat_pada,
        "diambil_pada": marker.diambil_pada,
        "hari_di_bengkel": days,
        "terlambat": late,
        "catatan_terakhir": None,
    }


def list_items(db: Session) -> Dict[str, Any]:
    """Unit yang masih di bengkel, yang paling lama menunggu lebih dulu."""
    markers = list(
        db.scalars(_statement().order_by(PengerjaanNota.dibuat_pada.asc())).unique()
    )
    record_ids = [marker.service_record_id for marker in markers]
    notified: Dict[int, datetime] = {}
    if record_ids:
        rows = db.execute(
            select(
                WhatsAppLog.service_record_id,
                func.max(WhatsAppLog.created_at),
            )
            .where(
                WhatsAppLog.service_record_id.in_(record_ids),
                WhatsAppLog.jenis == "pengerjaan",
                WhatsAppLog.status == "DIBUKA",
            )
            .group_by(WhatsAppLog.service_record_id)
        ).all()
        notified = {row[0]: row[1] for row in rows}
    items = []
    for marker in markers:
        item = serialize_item(marker)
        dikabari_pada = notified.get(marker.service_record_id)
        if (
            dikabari_pada is not None
            and marker.dibuat_pada is not None
            and dikabari_pada < marker.dibuat_pada
        ):
            dikabari_pada = None
        item["dikabari_pada"] = dikabari_pada
        item["sudah_dikabari"] = dikabari_pada is not None
        items.append(item)
    return {"items": items, "jumlah": len(items)}


def counts(db: Session) -> Dict[str, int]:
    return {"kendaraan_selesai": len(list(db.scalars(_statement()).unique()))}


def _get_marker(db: Session, marker_id: int) -> PengerjaanNota:
    marker = db.get(PengerjaanNota, marker_id)
    if marker is None:
        raise NotFoundError("Penanda pengerjaan tidak ditemukan.")
    return marker


def _add_event(
    db: Session,
    marker: PengerjaanNota,
    from_status: Optional[str],
    to_status: str,
    operator: Operator,
    catatan: Optional[str],
    moment: datetime,
) -> None:
    db.add(
        PengerjaanNotaEvent(
            pengerjaan_id=marker.id,
            from_status=from_status,
            to_status=to_status,
            operator=operator.label,
            catatan=(catatan or "").strip() or None,
            created_at=moment,
        )
    )


def create_marker(
    db: Session,
    record_id: int,
    operator: Operator,
    now: Optional[datetime] = None,
) -> PengerjaanNota:
    """Tandai unit masih di bengkel untuk nota yang belum punya penanda."""
    moment = now or datetime.now()
    with db.begin():
        record = db.get(ServiceRecord, record_id)
        if record is None:
            raise NotFoundError("Nota servis tidak ditemukan.")
        if (record.status or "NORMAL") == "VOID":
            raise ConflictError("Nota sudah dibatalkan.")
        existing = db.scalar(
            select(PengerjaanNota).where(
                PengerjaanNota.service_record_id == record_id
            )
        )
        if existing is not None:
            raise ConflictError("Nota ini sudah memiliki penanda pengerjaan.")
        marker = PengerjaanNota(
            service_record_id=record.id,
            unit_id=record.unit_id,
            customer_id=record.unit.customer_id,
            status_pengerjaan=STATUS_DIKERJAKAN,
            dibuat_pada=moment,
            diubah_pada=moment,
            diubah_oleh=operator.label,
        )
        db.add(marker)
        db.flush()
        _add_event(
            db,
            marker,
            None,
            STATUS_DIKERJAKAN,
            operator,
            "Unit ditandai masih di bengkel.",
            moment,
        )
        db.flush()
    db.refresh(marker)
    return marker


def change_status(
    db: Session,
    marker_id: int,
    status: str,
    operator: Operator,
    janji_ambil: Optional[date] = None,
    catatan: Optional[str] = None,
    now: Optional[datetime] = None,
) -> PengerjaanNota:
    """Ubah status pengerjaan dan simpan riwayatnya."""
    moment = now or datetime.now()
    target = (status or "").strip().upper()
    if target not in STATUS_VALUES:
        raise BusinessValidationError("Status pengerjaan tidak dikenal.")
    with db.begin():
        marker = _get_marker(db, marker_id)
        if (marker.service_record.status or "NORMAL") == "VOID":
            raise ConflictError("Nota sudah dibatalkan.")
        if target == STATUS_DIAMBIL and marker.diambil_pada is not None:
            raise ConflictError("Unit sudah ditandai diambil.")
        if (
            target == STATUS_DIAMBIL
            and payment_service.record_sisa(marker.service_record) > 0
        ):
            raise ConflictError(
                "Unit belum bisa ditandai diambil selama masih ada sisa tagihan."
            )
        previous = marker.status_pengerjaan
        marker.status_pengerjaan = target
        if janji_ambil is not None:
            marker.janji_ambil = janji_ambil
        if target == STATUS_DIAMBIL:
            marker.diambil_pada = marker.diambil_pada or moment
        else:
            marker.diambil_pada = None
        marker.diubah_pada = moment
        marker.diubah_oleh = operator.label
        if target != previous:
            _add_event(
                db,
                marker,
                previous,
                target,
                operator,
                catatan,
                moment,
            )
        db.flush()
    db.refresh(marker)
    return marker


def mark_taken(
    db: Session,
    marker_id: int,
    operator: Operator,
    now: Optional[datetime] = None,
) -> PengerjaanNota:
    """Tutup penanda setelah pelanggan mengambil unit."""
    return change_status(
        db,
        marker_id,
        STATUS_DIAMBIL,
        operator,
        catatan="Unit sudah diambil pelanggan.",
        now=now,
    )


def get_by_record(db: Session, record_id: int) -> Optional[Dict[str, Any]]:
    marker = db.scalar(
        select(PengerjaanNota).where(
            PengerjaanNota.service_record_id == record_id
        )
    )
    return serialize_item(marker) if marker is not None else None


def detail(db: Session, marker_id: int) -> Dict[str, Any]:
    marker = _get_marker(db, marker_id)
    events: List[PengerjaanNotaEvent] = list(
        db.scalars(
            select(PengerjaanNotaEvent)
            .where(PengerjaanNotaEvent.pengerjaan_id == marker.id)
            .order_by(
                PengerjaanNotaEvent.created_at.asc(),
                PengerjaanNotaEvent.id.asc(),
            )
        ).all()
    )
    return {"item": serialize_item(marker), "events": events}
