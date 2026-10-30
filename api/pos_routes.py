"""Endpoint transaksi POS, riwayat servis, cetak ulang & klaim garansi."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.schemas import (
    CreateServiceTransactionRequest,
    ReceiptOut,
    ServiceRecordOut,
    TransactionResponse,
)
from database.session import get_db
from repositories import service_record_repository as record_repo
from services import pos_service, settings_service, warranty_service
from services.errors import NotFoundError
from services.receipt_service import build_receipt_payload, record_summary

router = APIRouter(tags=["Transaksi & Servis"])


@router.post("/pos/transaction", response_model=TransactionResponse, status_code=201)
def create_transaction(
    payload: CreateServiceTransactionRequest, db: Session = Depends(get_db)
):
    result = pos_service.create_transaction(db, payload)
    receipt = ReceiptOut.model_validate(
        build_receipt_payload(result.record, settings_service.get_bengkel_info(db))
    )
    summary = ServiceRecordOut.model_validate(record_summary(result.record))
    return TransactionResponse(
        record=summary,
        receipt=receipt,
        warnings=result.warnings,
        laba_kotor=result.laba_kotor,
    )


@router.get("/service-records", response_model=List[ServiceRecordOut])
def list_service_records(
    q: str = Query(default="", max_length=100),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    records = record_repo.list_records(db, q, limit)
    return [
        ServiceRecordOut.model_validate(record_summary(record)) for record in records
    ]


@router.get("/service-records/{record_id}", response_model=ServiceRecordOut)
def get_service_record(record_id: int, db: Session = Depends(get_db)):
    record = record_repo.get_record(db, record_id)
    if record is None:
        raise NotFoundError("Nota servis tidak ditemukan.")
    return ServiceRecordOut.model_validate(record_summary(record))


@router.get("/service-records/{record_id}/receipt", response_model=ReceiptOut)
def get_receipt(record_id: int, db: Session = Depends(get_db)):
    record = record_repo.get_record(db, record_id)
    if record is None:
        raise NotFoundError("Nota servis tidak ditemukan.")
    return ReceiptOut.model_validate(
        build_receipt_payload(record, settings_service.get_bengkel_info(db))
    )


@router.put("/service-records/{record_id}/claim", response_model=ServiceRecordOut)
def claim_warranty(record_id: int, db: Session = Depends(get_db)):
    record = warranty_service.claim_warranty(db, record_id)
    return ServiceRecordOut.model_validate(record_summary(record))
