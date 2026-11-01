"""Hasil follow up pelanggan dari seluruh pesan yang pernah dikirim."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from database.models import (
    FollowupItem,
    ServiceRecord,
    VehicleOrUnit,
    WhatsAppLog,
)
from services import followup_service, whatsapp_service

MESSAGE_JENIS = {
    whatsapp_service.JENIS_FOLLOWUP,
    whatsapp_service.JENIS_GARANSI,
    whatsapp_service.JENIS_PIUTANG,
    whatsapp_service.JENIS_PENGERJAAN,
}
OUTCOME_BALIK = "balik_lagi"
OUTCOME_BAGUS = "masih_bagus"
OUTCOME_MASALAH = "bermasalah"
OUTCOME_TOLAK = "menolak"
PRIORITY = {
    OUTCOME_BALIK: 4,
    OUTCOME_MASALAH: 3,
    OUTCOME_BAGUS: 2,
    OUTCOME_TOLAK: 1,
}


def _latest_messages(db: Session) -> Dict[int, datetime]:
    rows = db.execute(
        select(WhatsAppLog.customer_id, func.max(WhatsAppLog.created_at))
        .where(
            WhatsAppLog.status == whatsapp_service.STATUS_OPENED,
            WhatsAppLog.customer_id.is_not(None),
            WhatsAppLog.jenis.in_(MESSAGE_JENIS),
        )
        .group_by(WhatsAppLog.customer_id)
    ).all()
    return {int(row[0]): row[1] for row in rows if row[0] is not None}


def _outcome_for_customer(
    records: List[ServiceRecord],
    items: List[FollowupItem],
    sent_at: datetime,
) -> Optional[str]:
    events = []
    for record in records:
        if record.waktu_service <= sent_at:
            continue
        events.append((record.waktu_service, OUTCOME_BALIK))
        if (record.status_klaim or "") == "Sudah claim":
            claim_at = record.tanggal_klaim
            moment = (
                datetime.combine(claim_at, datetime.min.time())
                if claim_at is not None
                else record.waktu_service
            )
            events.append((moment, OUTCOME_MASALAH))
    for item in items:
        moment = item.followup_terakhir or item.updated_at
        if moment is None or moment <= sent_at:
            continue
        if item.status == followup_service.STATUS_KENDALA:
            events.append((moment, OUTCOME_MASALAH))
        elif item.status in {
            followup_service.STATUS_TIDAK_DATANG,
            followup_service.STATUS_ARSIP,
        }:
            events.append((moment, OUTCOME_TOLAK))
        elif item.status == followup_service.STATUS_BARU:
            events.append((moment, OUTCOME_BAGUS))
    if not events:
        return OUTCOME_BAGUS
    events.sort(key=lambda row: (row[0], PRIORITY[row[1]]), reverse=True)
    return events[0][1]


def summary(db: Session) -> Dict[str, Any]:
    messages = _latest_messages(db)
    counts = {
        OUTCOME_BALIK: 0,
        OUTCOME_BAGUS: 0,
        OUTCOME_MASALAH: 0,
        OUTCOME_TOLAK: 0,
    }
    if not messages:
        return {"counts": counts, "jumlah": 0}
    customer_ids = list(messages)
    records = list(
        db.scalars(
            select(ServiceRecord)
            .join(VehicleOrUnit, ServiceRecord.unit_id == VehicleOrUnit.id)
            .where(
                VehicleOrUnit.customer_id.in_(customer_ids),
                ServiceRecord.status == "NORMAL",
            )
            .options(joinedload(ServiceRecord.unit))
        ).unique().all()
    )
    records_by_customer: Dict[int, List[ServiceRecord]] = {}
    for record in records:
        records_by_customer.setdefault(record.unit.customer_id, []).append(record)
    items = list(
        db.scalars(
            select(FollowupItem).where(
                FollowupItem.customer_id.in_(customer_ids)
            )
        ).all()
    )
    items_by_customer: Dict[int, List[FollowupItem]] = {}
    for item in items:
        items_by_customer.setdefault(item.customer_id, []).append(item)
    for customer_id, sent_at in messages.items():
        outcome = _outcome_for_customer(
            records_by_customer.get(customer_id, []),
            items_by_customer.get(customer_id, []),
            sent_at,
        )
        if outcome in counts:
            counts[outcome] += 1
    counts["jumlah"] = sum(counts.values())
    return {"counts": counts, "jumlah": counts["jumlah"]}
