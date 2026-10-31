"""Endpoint DP, pelunasan, dan piutang pelanggan (Tahap 11)."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from api.deps import require_auth
from api.schemas import (
    PaymentCreate,
    PaymentOut,
    PaymentResultOut,
    ReceiptOut,
    ReceivablesOut,
    ServiceRecordOut,
)
from database.session import get_db
from services import payment_service, settings_service
from services.auth_service import Operator
from services.receipt_service import build_receipt_payload, record_summary

router = APIRouter(
    tags=["Pembayaran & Piutang"], dependencies=[Depends(require_auth)]
)


@router.get(
    "/service-records/{record_id}/payments",
    response_model=List[PaymentOut],
)
def list_payments(record_id: int, db: Session = Depends(get_db)):
    return [
        PaymentOut.model_validate(payment)
        for payment in payment_service.list_payments(db, record_id)
    ]


@router.post(
    "/service-records/{record_id}/payments",
    response_model=PaymentResultOut,
)
def create_payment(
    record_id: int,
    payload: PaymentCreate,
    response: Response,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_auth),
):
    payment, record, created = payment_service.record_payment(
        db,
        record_id,
        nominal=payload.nominal,
        metode=payload.metode,
        operator=operator,
        catatan=payload.catatan,
        request_id=payload.request_id,
    )
    response.status_code = 201 if created else 200
    receipt = ReceiptOut.model_validate(
        build_receipt_payload(
            record,
            settings_service.get_bengkel_info(db),
            payment=payment,
            wa_template=settings_service.get_ops_settings(db)["wa_template"],
        )
    )
    return PaymentResultOut(
        payment=PaymentOut.model_validate(payment),
        record=ServiceRecordOut.model_validate(record_summary(record)),
        receipt=receipt,
        status_bayar=record.status_bayar,
        sisa_bayar=payment_service.record_sisa(record),
    )


@router.get("/receivables", response_model=ReceivablesOut)
def list_receivables(
    customer_id: Optional[int] = Query(default=None, gt=0),
    db: Session = Depends(get_db),
):
    return ReceivablesOut.model_validate(
        payment_service.receivables(db, customer_id=customer_id)
    )


@router.get(
    "/customers/{customer_id}/receivables",
    response_model=ReceivablesOut,
)
def list_customer_receivables(customer_id: int, db: Session = Depends(get_db)):
    return ReceivablesOut.model_validate(
        payment_service.receivables(db, customer_id=customer_id)
    )
