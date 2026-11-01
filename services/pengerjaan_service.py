"""Follow-up kendaraan selesai untuk nota dengan penanda unit ditinggal.

Nota yang dicatat dengan opsi "Unit ditinggal" membuat satu baris di
`pengerjaan_nota`. Modul ini membaca baris tersebut sebagai daftar unit yang
masih di bengkel, dipakai kasir untuk mengabari pelanggan saat pengerjaan
selesai, lalu menutupnya ketika unit sudah diambil.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from database.models import (
    PengerjaanNota,
    ServiceRecord,
    VehicleOrUnit,
    WhatsAppLog,
)
from services import payment_service
from services.auth_service import Operator
from services.customer_service import describe_unit
from services.errors import ConflictError, NotFoundError

STATUS_DIKERJAKAN = "SEDANG_DIKERJAKAN"
STATUS_DIAMBIL = "SUDAH_DIAMBIL"


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


def serialize_item(marker: PengerjaanNota) -> Dict[str, Any]:
    record = marker.service_record
    customer = record.unit.customer
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
        "janji_ambil": marker.janji_ambil,
        "dibuat_pada": marker.dibuat_pada,
        "diambil_pada": marker.diambil_pada,
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
                WhatsAppLog.jenis == "piutang",
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


def mark_taken(
    db: Session,
    marker_id: int,
    operator: Operator,
    now: Optional[datetime] = None,
) -> PengerjaanNota:
    """Tutup penanda setelah pelanggan mengambil unit."""
    moment = now or datetime.now()
    with db.begin():
        marker = db.get(PengerjaanNota, marker_id)
        if marker is None:
            raise NotFoundError("Penanda pengerjaan tidak ditemukan.")
        if marker.diambil_pada is not None:
            raise ConflictError("Unit sudah ditandai diambil.")
        if (marker.service_record.status or "NORMAL") == "VOID":
            raise ConflictError("Nota sudah dibatalkan.")
        marker.diambil_pada = moment
        marker.status_pengerjaan = STATUS_DIAMBIL
        marker.diubah_pada = moment
        marker.diubah_oleh = operator.label
        db.flush()
    db.refresh(marker)
    return marker
