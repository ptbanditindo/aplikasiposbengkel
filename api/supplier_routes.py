"""Endpoint supplier dan follow up reseller."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from api.deps import require_auth
from api.schemas import (
    SupplierCreate,
    SupplierFollowupGroupOut,
    SupplierOut,
    SupplierUpdate,
    SupplierWhatsAppIn,
    SupplierWhatsAppOut,
    SupplierWhatsAppPreviewIn,
    SupplierWhatsAppPreviewOut,
    WhatsAppLogOut,
)
from database.session import get_db
from services import settings_service, supplier_service, whatsapp_service
from services.auth_service import Operator

router = APIRouter(
    tags=["Supplier"], dependencies=[Depends(require_auth)]
)


def _out(supplier) -> SupplierOut:
    return SupplierOut(**supplier_service.serialize(supplier))


@router.get("/suppliers", response_model=List[SupplierOut])
def list_suppliers(
    q: str = Query(default="", max_length=100),
    db: Session = Depends(get_db),
):
    return [_out(supplier) for supplier in supplier_service.list_suppliers(db, q)]


@router.get(
    "/suppliers/followup-low-stock",
    response_model=List[SupplierFollowupGroupOut],
)
def followup_low_stock(db: Session = Depends(get_db)):
    return [
        SupplierFollowupGroupOut(**group)
        for group in supplier_service.followup_groups(db)
    ]


@router.post("/suppliers", response_model=SupplierOut, status_code=201)
def create_supplier(payload: SupplierCreate, db: Session = Depends(get_db)):
    supplier = supplier_service.create_supplier(
        db,
        payload.nama,
        nomor_hp=payload.nomor_hp,
        alamat=payload.alamat,
        catatan=payload.catatan,
        aktif=payload.aktif,
        stock_item_ids=payload.stock_item_ids,
    )
    return _out(supplier)


@router.put("/suppliers/{supplier_id}", response_model=SupplierOut)
def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    db: Session = Depends(get_db),
):
    supplier = supplier_service.update_supplier(
        db, supplier_id, **payload.model_dump(exclude_unset=True)
    )
    return _out(supplier)


@router.delete("/suppliers/{supplier_id}", status_code=204)
def delete_supplier(supplier_id: int, db: Session = Depends(get_db)):
    supplier_service.delete_supplier(db, supplier_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/suppliers/{supplier_id}/whatsapp-preview",
    response_model=SupplierWhatsAppPreviewOut,
)
def supplier_whatsapp_preview(
    supplier_id: int,
    payload: SupplierWhatsAppPreviewIn,
    db: Session = Depends(get_db),
    _operator: Operator = Depends(require_auth),
):
    supplier = supplier_service.get_supplier(db, supplier_id)
    items = supplier_service.low_stock_items_for_supplier(
        db, supplier_id, payload.stock_item_ids
    )
    if not items:
        items = [
            {"nama": item.nama}
            for link in supplier.items
            if (item := link.stock_item) is not None
            and (not payload.stock_item_ids or item.id in payload.stock_item_ids)
        ]
    info = settings_service.get_bengkel_info(db)
    db.rollback()
    return SupplierWhatsAppPreviewOut(
        supplier_id=supplier.id,
        nama=supplier.nama,
        nomor=supplier.nomor_hp or "",
        wa_text=whatsapp_service.supplier_wa_text(supplier, items, info),
    )


@router.post(
    "/suppliers/{supplier_id}/whatsapp",
    response_model=SupplierWhatsAppOut,
    status_code=201,
)
def supplier_whatsapp(
    supplier_id: int,
    payload: SupplierWhatsAppIn,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_auth),
):
    items = supplier_service.low_stock_items_for_supplier(
        db, supplier_id, payload.stock_item_ids
    )
    if not items:
        items = [
            {
                "nama": item.nama,
                "jumlah": int(item.jumlah or 0),
                "minimum_efektif": 0,
                "status": "HABIS" if int(item.jumlah or 0) <= 0 else "MENIPIS",
            }
            for link in supplier.items
            if (item := link.stock_item) is not None
            and (not payload.stock_item_ids or item.id in payload.stock_item_ids)
        ]
    db.rollback()
    log, text, link = whatsapp_service.log_supplier_attempt(
        db,
        supplier_id,
        items,
        operator,
        status=payload.status,
        pesan=payload.pesan,
    )
    return SupplierWhatsAppOut(
        status=log.status,
        nomor_masked=log.nomor_masked,
        link=link,
        wa_text=text,
        log=WhatsAppLogOut.model_validate(log),
    )
