"""Repository stok sparepart & master tarif jasa."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import HargaJasa, StockItem, StockMovement


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


def list_movements(
    db: Session,
    stock_item_id: Optional[int] = None,
    service_record_id: Optional[int] = None,
    limit: int = 200,
) -> List[StockMovement]:
    statement = select(StockMovement)
    if stock_item_id is not None:
        statement = statement.where(StockMovement.stock_item_id == stock_item_id)
    if service_record_id is not None:
        statement = statement.where(
            StockMovement.service_record_id == service_record_id
        )
    statement = statement.order_by(
        StockMovement.created_at.asc(), StockMovement.id.asc()
    ).limit(int(limit))
    return list(db.scalars(statement).all())
