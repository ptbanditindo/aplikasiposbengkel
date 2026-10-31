"""Jejak audit append-only (ARC-15).

Setiap tindakan penting dicatat dengan identitas operator yang berasal dari
sesi/principal terautentikasi, bukan dari input frontend. Tidak ada fungsi
ubah/hapus; listener model menolak perubahan baris audit.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import AuditEvent
from services.auth_service import Operator

ACTION_VOID = "VOID"
ACTION_RETURN = "RETURN"
ACTION_RESTORE = "RESTORE"
ACTION_PAYMENT = "PAYMENT"
ACTION_FOLLOWUP = "FOLLOWUP"
ACTION_WHATSAPP = "WHATSAPP"

REFERENCE_SERVICE_RECORD = "SERVICE_RECORD"
REFERENCE_DATABASE = "DATABASE"
REFERENCE_FOLLOWUP = "FOLLOWUP"
REFERENCE_CUSTOMER = "CUSTOMER"


def record_event(
    db: Session,
    operator: Operator,
    action: str,
    reference_type: str,
    reference_id: str = "",
    reason: Optional[str] = None,
    now: Optional[datetime] = None,
) -> AuditEvent:
    event = AuditEvent(
        operator_id=operator.id,
        operator_role=operator.role,
        action=action,
        reference_type=reference_type,
        reference_id=str(reference_id or ""),
        reason=reason,
        created_at=now or datetime.now(),
    )
    db.add(event)
    return event


def list_events(db: Session, limit: int = 200) -> List[AuditEvent]:
    statement = (
        select(AuditEvent)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(max(1, min(limit, 1000)))
    )
    return list(db.scalars(statement).all())
