"""Endpoint transaksi POS, riwayat servis, cetak ulang & klaim garansi."""
from __future__ import annotations

from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.deps import require_auth
from api.schemas import (
    CreateServiceReturnRequest,
    CreateServiceTransactionRequest,
    ReceiptOut,
    ServiceRecordOut,
    ServiceReturnOut,
    TransactionPreviewLineOut,
    TransactionPreviewOut,
    TransactionPreviewRequest,
    TransactionResponse,
    VoidRequest,
)
from database.session import get_db
from repositories import service_record_repository as record_repo
from services import (
    pos_service,
    pricing_service,
    settings_service,
    void_return_service,
    warranty_service,
)
from services.errors import NotFoundError
from services.auth_service import Operator
from services.receipt_service import build_receipt_payload, record_summary

router = APIRouter(
    tags=["Transaksi & Servis"], dependencies=[Depends(require_auth)]
)


@router.post("/pos/transaction", response_model=TransactionResponse, status_code=201)
def create_transaction(
    payload: CreateServiceTransactionRequest,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_auth),
):
    result = pos_service.create_transaction(db, payload, operator)
    receipt = ReceiptOut.model_validate(
        build_receipt_payload(
            result.record,
            settings_service.get_bengkel_info(db),
            wa_template=settings_service.get_ops_settings(db)["wa_template"],
        )
    )
    summary = ServiceRecordOut.model_validate(record_summary(result.record))
    return TransactionResponse(
        record=summary,
        receipt=receipt,
        warnings=result.warnings,
        laba_kotor=result.laba_kotor,
    )


@router.post("/pos/preview", response_model=TransactionPreviewOut)
def preview_transaction(payload: TransactionPreviewRequest):
    """Pratinjau total kasir memakai mesin harga yang sama dengan penyimpanan."""
    job_lines = [
        {"jumlah": job.jumlah, "harga": job.harga} for job in payload.jobs
    ]
    part_lines = [
        {"jumlah": part.jumlah, "harga_satuan": part.harga_satuan}
        for part in payload.parts
    ]
    totals = pricing_service.compute_invoice(
        job_lines, part_lines, payload.diskon
    )
    jenis_bayar = (payload.jenis_bayar or "LUNAS").strip().upper()
    if jenis_bayar == "DP":
        dp_value = payload.dp if payload.dp is not None else payload.bayar
        if Decimal(str(dp_value or 0)) <= 0:
            # Pratinjau tetap menampilkan total saat DP belum diisi; simpan
            # transaksi tetap memakai aturan DP yang ketat.
            payment = {
                "bayar": Decimal("0.00"),
                "kembalian": Decimal("0.00"),
                "sisa": totals["total_servis"],
            }
        else:
            payment = pricing_service.compute_dp_payment(
                totals["total_servis"], dp_value
            )
        payment["kekurangan"] = Decimal("0.00")
        status_bayar = "BELUM_LUNAS"
        sisa_bayar = payment["sisa"]
    else:
        payment = pricing_service.compute_payment_preview(
            totals["total_servis"], payload.metode_bayar, payload.bayar
        )
        status_bayar = "LUNAS"
        sisa_bayar = Decimal("0.00")
    return TransactionPreviewOut(
        is_final=False,
        biaya_jasa=totals["biaya_jasa"],
        total_part=totals["total_part"],
        subtotal=totals["subtotal"],
        diskon=totals["diskon"],
        total_servis=totals["total_servis"],
        bayar=payment["bayar"],
        kembalian=payment["kembalian"],
        kekurangan=payment["kekurangan"],
        jenis_bayar=jenis_bayar,
        status_bayar=status_bayar,
        sisa_bayar=sisa_bayar,
        jobs=[
            TransactionPreviewLineOut(
                subtotal=pricing_service.line_subtotal(
                    line["jumlah"], line["harga"]
                )
            )
            for line in job_lines
        ],
        parts=[
            TransactionPreviewLineOut(
                subtotal=pricing_service.line_subtotal(
                    line["jumlah"], line["harga_satuan"]
                )
            )
            for line in part_lines
        ],
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
        build_receipt_payload(
            record,
            settings_service.get_bengkel_info(db),
            wa_template=settings_service.get_ops_settings(db)["wa_template"],
        )
    )


@router.put("/service-records/{record_id}/claim", response_model=ServiceRecordOut)
def claim_warranty(record_id: int, db: Session = Depends(get_db)):
    record = warranty_service.claim_warranty(db, record_id)
    return ServiceRecordOut.model_validate(record_summary(record))


@router.post("/service-records/{record_id}/void", response_model=ServiceRecordOut)
def void_service_record(
    record_id: int,
    payload: VoidRequest,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_auth),
):
    record = void_return_service.void_record(
        db, record_id, payload.alasan, operator
    )
    return ServiceRecordOut.model_validate(record_summary(record))


@router.post(
    "/service-records/{record_id}/returns",
    response_model=ServiceReturnOut,
    status_code=201,
)
def create_service_return(
    record_id: int,
    payload: CreateServiceReturnRequest,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_auth),
):
    retur = void_return_service.create_return(
        db,
        record_id,
        payload.alasan,
        payload.items,
        operator,
    )
    return ServiceReturnOut.model_validate(retur)


@router.get(
    "/service-records/{record_id}/returns",
    response_model=List[ServiceReturnOut],
)
def list_service_returns(record_id: int, db: Session = Depends(get_db)):
    return [
        ServiceReturnOut.model_validate(retur)
        for retur in void_return_service.list_returns(db, record_id)
    ]
