"""Endpoint daftar toko, tambah toko, dan ganti toko aktif (khusus pemilik)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from api.deps import require_owner
from api.schemas import StoreCreate, StoreListOut, StoreOut
from services import store_service

router = APIRouter(
    tags=["Toko"], dependencies=[Depends(require_owner)]
)


@router.get("/stores", response_model=StoreListOut)
def list_stores():
    return StoreListOut(**store_service.list_stores())


@router.post("/stores", response_model=StoreOut, status_code=201)
def create_store(payload: StoreCreate):
    return StoreOut(
        **store_service.create_store(payload.nama, payload.alamat)
    )


@router.post("/stores/{store_id}/activate", response_model=StoreOut)
def activate_store(store_id: str):
    return StoreOut(**store_service.activate_store(store_id))
