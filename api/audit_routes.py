"""Endpoint baca jejak audit (khusus pemilik)."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.deps import require_owner
from api.schemas import AuditEventOut
from database.session import get_db
from services import audit_service

router = APIRouter(tags=["Audit"], dependencies=[Depends(require_owner)])


@router.get("/audit-events", response_model=List[AuditEventOut])
def list_audit_events(
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return [
        AuditEventOut.model_validate(event)
        for event in audit_service.list_events(db, limit)
    ]
