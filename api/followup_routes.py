"""Endpoint follow-up, servis berkala, garansi, dan piutang (Tahap 13)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.deps import require_auth
from api.schemas import (
    FollowupActionResultOut,
    FollowupCountsOut,
    FollowupDetailOut,
    FollowupItemOut,
    FollowupListOut,
    FollowupStatusIn,
    PengerjaanItemOut,
    PengerjaanListOut,
    WhatsAppAttemptIn,
    WhatsAppLogOut,
)
from database.session import get_db
from services import followup_service, pengerjaan_service
from services.auth_service import Operator

router = APIRouter(tags=["Follow-up"], dependencies=[Depends(require_auth)])


def _item_out(db: Session, item) -> FollowupItemOut:
    return FollowupItemOut.model_validate(
        followup_service.serialize_item(db, item)
    )


@router.get("/followup/items", response_model=FollowupListOut)
def list_followup_items(
    filter: str = Query(default="semua", max_length=32),
    jenis: Optional[str] = Query(default=None, max_length=24),
    customer_id: Optional[int] = Query(default=None, gt=0),
    status: Optional[str] = Query(default=None, max_length=24),
    exclude_status: Optional[str] = Query(default=None, max_length=24),
    db: Session = Depends(get_db),
):
    return FollowupListOut.model_validate(
        followup_service.list_items(
            db,
            filter=filter,
            jenis=jenis,
            customer_id=customer_id,
            status=status,
            exclude_status=exclude_status,
        )
    )


@router.get("/followup/counts", response_model=FollowupCountsOut)
def followup_counts(db: Session = Depends(get_db)):
    return FollowupCountsOut(**followup_service.counts(db))


@router.get("/pengerjaan", response_model=PengerjaanListOut)
def list_pengerjaan(db: Session = Depends(get_db)):
    return PengerjaanListOut.model_validate(pengerjaan_service.list_items(db))


@router.post("/pengerjaan/{marker_id}/diambil", response_model=PengerjaanItemOut)
def mark_pengerjaan_taken(
    marker_id: int,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_auth),
):
    marker = pengerjaan_service.mark_taken(db, marker_id, operator)
    return PengerjaanItemOut.model_validate(pengerjaan_service.serialize_item(marker))


@router.get("/followup/items/{item_id}", response_model=FollowupDetailOut)
def followup_detail(item_id: int, db: Session = Depends(get_db)):
    return FollowupDetailOut.model_validate(followup_service.detail(db, item_id))


@router.post(
    "/followup/items/{item_id}/followup",
    response_model=FollowupActionResultOut,
)
def record_followup(
    item_id: int,
    payload: WhatsAppAttemptIn,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_auth),
):
    result = followup_service.follow_up(
        db,
        item_id,
        payload.status,
        operator,
        catatan=payload.catatan,
        pesan=payload.pesan,
    )
    return FollowupActionResultOut(
        item=_item_out(db, result["item"]),
        wa_text=result["wa_text"],
        link=result["link"],
        log=WhatsAppLogOut.model_validate(result["log"]),
    )


@router.post(
    "/followup/items/{item_id}/status",
    response_model=FollowupItemOut,
)
def change_followup_status(
    item_id: int,
    payload: FollowupStatusIn,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_auth),
):
    item = followup_service.change_status(
        db,
        item_id,
        payload.status,
        operator,
        alasan=payload.alasan,
        janji_bayar=payload.janji_bayar,
        tanggal_service=payload.tanggal_service,
    )
    return _item_out(db, item)
