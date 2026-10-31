"""Endpoint pesan WhatsApp dan log upaya (Tahap 12)."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.deps import require_auth
from api.schemas import (
    WhatsAppAttemptIn,
    WhatsAppAttemptOut,
    WhatsAppLogOut,
)
from database.session import get_db
from services import whatsapp_service
from services.auth_service import Operator

router = APIRouter(tags=["WhatsApp"], dependencies=[Depends(require_auth)])


@router.post(
    "/service-records/{record_id}/whatsapp",
    response_model=WhatsAppAttemptOut,
    status_code=201,
)
def record_whatsapp_attempt(
    record_id: int,
    payload: WhatsAppAttemptIn,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_auth),
):
    log, wa_text, link = whatsapp_service.log_attempt(
        db,
        record_id,
        payload.status,
        operator,
        catatan=payload.catatan,
    )
    return WhatsAppAttemptOut(
        status=log.status,
        nomor_masked=log.nomor_masked,
        link=link,
        wa_text=wa_text,
        log=WhatsAppLogOut.model_validate(log),
    )


@router.get(
    "/service-records/{record_id}/whatsapp-logs",
    response_model=List[WhatsAppLogOut],
)
def list_record_whatsapp_logs(record_id: int, db: Session = Depends(get_db)):
    return [
        WhatsAppLogOut.model_validate(log)
        for log in whatsapp_service.list_logs(db, record_id=record_id)
    ]


@router.get("/whatsapp/logs", response_model=List[WhatsAppLogOut])
def list_whatsapp_logs(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return [
        WhatsAppLogOut.model_validate(log)
        for log in whatsapp_service.list_logs(db, limit=limit)
    ]
