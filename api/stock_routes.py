"""Endpoint master stok sparepart & tarif jasa."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from api.deps import require_auth
from api.schemas import (
    HargaJasaCreate,
    HargaJasaOut,
    HargaJasaUpdate,
    StockItemCreate,
    StockItemOut,
    StockItemUpdate,
)
from database.session import get_db
from services import stock_service

router = APIRouter(
    tags=["Stok & Tarif Jasa"], dependencies=[Depends(require_auth)]
)


@router.get("/stock", response_model=List[StockItemOut])
def list_stock(db: Session = Depends(get_db)):
    return [StockItemOut.model_validate(item) for item in stock_service.list_stock(db)]


@router.post("/stock", response_model=StockItemOut, status_code=201)
def create_stock(payload: StockItemCreate, db: Session = Depends(get_db)):
    item = stock_service.create_stock(
        db,
        nama=payload.nama,
        harga_modal=payload.harga_modal,
        harga_jual=payload.harga_jual,
        jumlah=payload.jumlah,
        kode=payload.kode,
    )
    return StockItemOut.model_validate(item)


@router.put("/stock/{stock_id}", response_model=StockItemOut)
def update_stock(stock_id: int, payload: StockItemUpdate, db: Session = Depends(get_db)):
    item = stock_service.update_stock(
        db, stock_id, **payload.model_dump(exclude_unset=True)
    )
    return StockItemOut.model_validate(item)


@router.delete(
    "/stock/{stock_id}",
    status_code=204,
)
def delete_stock(stock_id: int, db: Session = Depends(get_db)):
    stock_service.delete_stock(db, stock_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/harga-jasa", response_model=List[HargaJasaOut])
def list_jasa(db: Session = Depends(get_db)):
    return [HargaJasaOut.model_validate(item) for item in stock_service.list_jasa(db)]


@router.post("/harga-jasa", response_model=HargaJasaOut, status_code=201)
def create_jasa(payload: HargaJasaCreate, db: Session = Depends(get_db)):
    jasa = stock_service.create_jasa(db, payload.nama, payload.harga_standar)
    return HargaJasaOut.model_validate(jasa)


@router.put("/harga-jasa/{jasa_id}", response_model=HargaJasaOut)
def update_jasa(jasa_id: int, payload: HargaJasaUpdate, db: Session = Depends(get_db)):
    jasa = stock_service.update_jasa(
        db, jasa_id, **payload.model_dump(exclude_unset=True)
    )
    return HargaJasaOut.model_validate(jasa)


@router.delete(
    "/harga-jasa/{jasa_id}",
    status_code=204,
)
def delete_jasa(jasa_id: int, db: Session = Depends(get_db)):
    stock_service.delete_jasa(db, jasa_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
