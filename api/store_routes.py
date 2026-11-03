"""Endpoint daftar toko, tambah toko, dan ganti toko aktif (K-09)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import require_auth, require_owner
from api.schemas import StoreCreate, StoreListOut, StoreOut
from services import store_service
from services.auth_service import Operator

router = APIRouter(tags=["Toko"])


@router.get("/stores", response_model=StoreListOut)
def list_stores(operator: Operator = Depends(require_auth)):
    allowed = operator.stores if operator.kind == "employee" else None
    return StoreListOut(**store_service.list_stores(allowed_store_ids=allowed))


@router.post("/stores", response_model=StoreOut, status_code=201)
def create_store(payload: StoreCreate, operator: Operator = Depends(require_owner)):
    return StoreOut(
        **store_service.create_store(payload.nama, payload.alamat)
    )


@router.post("/stores/{store_id}/activate", response_model=StoreOut)
def activate_store(store_id: str, operator: Operator = Depends(require_auth)):
    if operator.kind == "employee" and store_id not in operator.stores:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Karyawan hanya dapat memakai toko yang ditugaskan.",
        )
    return StoreOut(**store_service.activate_store(store_id))
