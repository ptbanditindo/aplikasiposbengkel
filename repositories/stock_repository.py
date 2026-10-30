"""Repository stok sparepart & master tarif jasa."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import HargaJasa, StockItem


def list_stock(db: Session) -> List[StockItem]:
    return list(
        db.scalars(select(StockItem).order_by(StockItem.nama.asc())).all()
    )


def get_stock(db: Session, stock_id: int) -> Optional[StockItem]:
    return db.get(StockItem, stock_id)


def get_stock_by_kode(db: Session, kode: str) -> Optional[StockItem]:
    return db.scalar(select(StockItem).where(StockItem.kode == kode))


def list_jasa(db: Session) -> List[HargaJasa]:
    return list(
        db.scalars(select(HargaJasa).order_by(HargaJasa.nama.asc())).all()
    )


def get_jasa(db: Session, jasa_id: int) -> Optional[HargaJasa]:
    return db.get(HargaJasa, jasa_id)
