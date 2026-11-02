"""Endpoint follow-up, servis berkala, garansi, dan piutang (Tahap 13)."""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.deps import require_auth
from api.schemas import (
    FollowupActionResultOut,
    FollowupCountsOut,
    FollowupDetailOut,
    FollowupItemOut,
    FollowupListOut,
    FollowupQuotaOut,
    FollowupResultOut,
    FollowupStatusIn,
    PengerjaanDetailOut,
    PengerjaanEventOut,
    PengerjaanItemOut,
    PengerjaanListOut,
    PengerjaanMarkerIn,
    PengerjaanStatusIn,
    PengerjaanStatusOut,
    WhatsAppAttemptIn,
    WhatsAppLogOut,
)
from database.session import get_db
from services import (
    followup_quota_service,
    followup_result_service,
    followup_service,
    pengerjaan_service,
    settings_service,
    whatsapp_service,
)
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


@router.get("/followup/quota", response_model=FollowupQuotaOut)
def followup_quota(db: Session = Depends(get_db)):
    return FollowupQuotaOut(**followup_quota_service.status(db))


@router.get("/pengerjaan", response_model=PengerjaanListOut)
def list_pengerjaan(db: Session = Depends(get_db)):
    return PengerjaanListOut.model_validate(pengerjaan_service.list_items(db))


@router.post("/pengerjaan", response_model=PengerjaanItemOut, status_code=201)
def create_pengerjaan(
    payload: PengerjaanMarkerIn,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_auth),
):
    marker = pengerjaan_service.create_marker(db, payload.record_id, operator)
    return PengerjaanItemOut.model_validate(
        pengerjaan_service.serialize_item(marker)
    )


@router.get(
    "/pengerjaan/by-record/{record_id}",
    response_model=Optional[PengerjaanItemOut],
)
def pengerjaan_by_record(record_id: int, db: Session = Depends(get_db)):
    result = pengerjaan_service.get_by_record(db, record_id)
    if result is None:
        return None
    return PengerjaanItemOut.model_validate(result)


@router.get("/pengerjaan/{marker_id}", response_model=PengerjaanDetailOut)
def pengerjaan_detail(marker_id: int, db: Session = Depends(get_db)):
    return PengerjaanDetailOut.model_validate(
        pengerjaan_service.detail(db, marker_id)
    )


@router.post(
    "/pengerjaan/{marker_id}/status",
    response_model=PengerjaanStatusOut,
)
def change_pengerjaan_status(
    marker_id: int,
    payload: PengerjaanStatusIn,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_auth),
):
    marker = pengerjaan_service.change_status(
        db,
        marker_id,
        payload.status,
        operator,
        janji_ambil=payload.janji_ambil,
        catatan=payload.catatan,
    )
    info = settings_service.get_bengkel_info(db)
    text = whatsapp_service.pengerjaan_status_wa_text(
        marker.service_record, marker.status_pengerjaan, info
    )
    link = whatsapp_service.build_link(
        marker.service_record.unit.customer.nomor_hp, text
    )
    return PengerjaanStatusOut(
        item=PengerjaanItemOut.model_validate(
            pengerjaan_service.serialize_item(marker)
        ),
        wa_text=text,
        link=link,
    )


@router.post("/pengerjaan/{marker_id}/diambil", response_model=PengerjaanItemOut)
def mark_pengerjaan_taken(
    marker_id: int,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_auth),
):
    marker = pengerjaan_service.mark_taken(db, marker_id, operator)
    return PengerjaanItemOut.model_validate(pengerjaan_service.serialize_item(marker))


@router.get("/followup/results", response_model=FollowupResultOut)
def followup_results(
    start: Optional[date] = Query(default=None),
    end: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
):
    if start is not None and end is not None and end < start:
        raise HTTPException(
            status_code=400, detail="Tanggal akhir sebelum tanggal mulai."
        )
    summary = followup_result_service.summary(db, start=start, end=end)
    data = summary["counts"]
    return FollowupResultOut(
        followup_total=summary.get("followup_total", 0),
        balik_lagi=data.get("balik_lagi", 0),
        masih_bagus=data.get("masih_bagus", 0),
        bermasalah=data.get("bermasalah", 0),
        menolak=data.get("menolak", 0),
    )


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
    followup_quota_service.ensure_available(db)
    result = followup_service.follow_up(
        db,
        item_id,
        payload.status,
        operator,
        catatan=payload.catatan,
        pesan=payload.pesan,
    )
    kuota = (
        followup_quota_service.consume(db)
        if result.get("link")
        else followup_quota_service.status(db)
    )
    return FollowupActionResultOut(
        item=_item_out(db, result["item"]),
        wa_text=result["wa_text"],
        link=result["link"],
        peringatan=getattr(result["log"], "peringatan", ""),
        log=WhatsAppLogOut.model_validate(result["log"]),
        kuota=FollowupQuotaOut(**kuota),
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
        tunda_hari=payload.tunda_hari,
    )
    return _item_out(db, item)
