"""Endpoint pesan WhatsApp dan log upaya (Tahap 12)."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.deps import require_auth
from api.schemas import (
    FollowupQuotaOut,
    WaGateOut,
    WhatsAppAttemptIn,
    WhatsAppAttemptOut,
    WhatsAppLogOut,
)
from database.models import ServiceRecord
from database.session import get_db
from services import contact_gate_service, followup_quota_service, whatsapp_service
from services.auth_service import Operator
from services.errors import NotFoundError

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
        pesan=payload.pesan,
        jenis=payload.jenis,
    )
    return WhatsAppAttemptOut(
        status=log.status,
        nomor_masked=log.nomor_masked,
        link=link,
        wa_text=wa_text,
        peringatan=getattr(log, "peringatan", ""),
        log=WhatsAppLogOut.model_validate(log),
    )


@router.post(
    "/service-records/{record_id}/remind",
    response_model=WhatsAppAttemptOut,
    status_code=201,
)
def remind_receivable(
    record_id: int,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_auth),
):
    followup_quota_service.ensure_available(db)
    log, wa_text, link = whatsapp_service.remind_receivable(
        db, record_id, operator
    )
    kuota = (
        followup_quota_service.consume(db)
        if link
        else followup_quota_service.status(db)
    )
    return WhatsAppAttemptOut(
        status=log.status,
        nomor_masked=log.nomor_masked,
        link=link,
        wa_text=wa_text,
        peringatan=getattr(log, "peringatan", ""),
        log=WhatsAppLogOut.model_validate(log),
        kuota=FollowupQuotaOut(**kuota),
    )


@router.post(
    "/customers/{customer_id}/remind",
    response_model=WhatsAppAttemptOut,
    status_code=201,
)
def remind_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_auth),
):
    followup_quota_service.ensure_available(db)
    log, wa_text, link = whatsapp_service.remind_customer_receivables(
        db, customer_id, operator
    )
    kuota = (
        followup_quota_service.consume(db)
        if link
        else followup_quota_service.status(db)
    )
    return WhatsAppAttemptOut(
        status=log.status,
        nomor_masked=log.nomor_masked,
        link=link,
        wa_text=wa_text,
        peringatan=getattr(log, "peringatan", ""),
        log=WhatsAppLogOut.model_validate(log),
        kuota=FollowupQuotaOut(**kuota),
    )


@router.get("/service-records/{record_id}/wa-gate", response_model=WaGateOut)
def record_wa_gate(
    record_id: int,
    jenis: str = Query(default="struk"),
    db: Session = Depends(get_db),
):
    record = db.get(ServiceRecord, record_id)
    if record is None:
        raise NotFoundError("Nota servis tidak ditemukan.")
    allowed, reason, warning = contact_gate_service.wa_gate(
        db, record.unit.customer, (jenis or "struk").strip().lower()
    )
    return WaGateOut(allowed=allowed, alasan=reason, peringatan=warning)


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
