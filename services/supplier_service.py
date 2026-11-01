"""Supplier, relasi barang, dan daftar stok menipis per supplier."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from database.models import StockItem, Supplier, SupplierItem
from services import settings_service, stock_service
from services.errors import BusinessValidationError, ConflictError, NotFoundError
from services.utils import clean_text

SUPPLIER_KIND_LOW = "MENIPIS"
SUPPLIER_KIND_OUT = "HABIS"


def _clean_supplier(
    nama: str, nomor_hp: Optional[str], alamat: Optional[str], catatan: Optional[str]
) -> Dict[str, Any]:
    clean_nama = clean_text(nama, max_length=255, allow_newlines=False)
    if len(clean_nama) < 2:
        raise BusinessValidationError("Nama supplier minimal 2 karakter.")
    return {
        "nama": clean_nama,
        "nomor_hp": clean_text(nomor_hp, max_length=64, allow_newlines=False) or "",
        "alamat": clean_text(alamat, max_length=500) or None,
        "catatan": clean_text(catatan, max_length=500) or None,
    }


def _supplier_statement():
    return select(Supplier).options(
        selectinload(Supplier.items).selectinload(SupplierItem.stock_item)
    )


def list_suppliers(db: Session, q: str = "") -> List[Supplier]:
    statement = _supplier_statement().order_by(Supplier.nama.asc(), Supplier.id.asc())
    query = (q or "").strip()
    if query:
        statement = statement.where(
            Supplier.nama.like(f"%{query}%")
            | Supplier.nomor_hp.like(f"%{query}%")
        )
    return list(db.scalars(statement).unique().all())


def get_supplier(db: Session, supplier_id: int) -> Supplier:
    supplier = db.scalar(
        _supplier_statement().where(Supplier.id == supplier_id)
    )
    if supplier is None:
        raise NotFoundError("Supplier tidak ditemukan.")
    return supplier


def serialize(supplier: Supplier) -> Dict[str, Any]:
    items = sorted(
        (link.stock_item for link in supplier.items if link.stock_item is not None),
        key=lambda item: ((item.nama or "").lower(), item.id),
    )
    return {
        "id": supplier.id,
        "nama": supplier.nama,
        "nomor_hp": supplier.nomor_hp,
        "alamat": supplier.alamat,
        "catatan": supplier.catatan,
        "aktif": bool(supplier.aktif),
        "items": [
            {
                "id": item.id,
                "kode": item.kode,
                "nama": item.nama,
                "jumlah": int(item.jumlah or 0),
                "stok_minimum": item.stok_minimum,
                "harga_modal": item.harga_modal,
                "harga_jual": item.harga_jual,
                "interval_servis_bulan": int(item.interval_servis_bulan or 0),
            }
            for item in items
        ],
    }


def create_supplier(
    db: Session,
    nama: str,
    nomor_hp: Optional[str] = None,
    alamat: Optional[str] = None,
    catatan: Optional[str] = None,
    aktif: bool = True,
    stock_item_ids: Optional[Iterable[int]] = None,
) -> Supplier:
    clean = _clean_supplier(nama, nomor_hp, alamat, catatan)
    existing = db.scalar(select(Supplier).where(Supplier.nama == clean["nama"]))
    if existing is not None:
        raise ConflictError("Nama supplier sudah terdaftar.")
    supplier = Supplier(**clean, aktif=bool(aktif))
    db.add(supplier)
    db.flush()
    if stock_item_ids is not None:
        _set_items(db, supplier, stock_item_ids)
    db.commit()
    return get_supplier(db, supplier.id)


def update_supplier(db: Session, supplier_id: int, **values: Any) -> Supplier:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise NotFoundError("Supplier tidak ditemukan.")
    if "nama" in values or "nomor_hp" in values or "alamat" in values or "catatan" in values:
        clean = _clean_supplier(
            values.get("nama", supplier.nama),
            values.get("nomor_hp", supplier.nomor_hp),
            values.get("alamat", supplier.alamat),
            values.get("catatan", supplier.catatan),
        )
        if clean["nama"] != supplier.nama:
            existing = db.scalar(select(Supplier).where(Supplier.nama == clean["nama"]))
            if existing is not None and existing.id != supplier.id:
                raise ConflictError("Nama supplier sudah terdaftar.")
        supplier.nama = clean["nama"]
        supplier.nomor_hp = clean["nomor_hp"]
        supplier.alamat = clean["alamat"]
        supplier.catatan = clean["catatan"]
    if "aktif" in values and values["aktif"] is not None:
        supplier.aktif = bool(values["aktif"])
    if "stock_item_ids" in values and values["stock_item_ids"] is not None:
        _set_items(db, supplier, values["stock_item_ids"])
    db.commit()
    return get_supplier(db, supplier.id)


def delete_supplier(db: Session, supplier_id: int) -> None:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise NotFoundError("Supplier tidak ditemukan.")
    db.delete(supplier)
    db.commit()


def _set_items(db: Session, supplier: Supplier, stock_item_ids: Iterable[int]) -> None:
    unique_ids = sorted({int(value) for value in stock_item_ids if int(value) > 0})
    if unique_ids:
        found = set(
            db.scalars(select(StockItem.id).where(StockItem.id.in_(unique_ids))).all()
        )
        missing = [value for value in unique_ids if value not in found]
        if missing:
            raise BusinessValidationError("Ada barang stok yang tidak ditemukan.")
    db.query(SupplierItem).filter(
        SupplierItem.supplier_id == supplier.id
    ).delete(synchronize_session=False)
    for stock_item_id in unique_ids:
        db.add(
            SupplierItem(
                supplier_id=supplier.id,
                stock_item_id=stock_item_id,
            )
        )
    db.flush()


def followup_groups(db: Session, include_out: bool = True) -> List[Dict[str, Any]]:
    """Barang menipis/habis dikelompokkan per supplier untuk follow up reseller."""
    default_minimum = int(
        settings_service.get_ops_settings(db).get("stok_minimum_default", 3) or 0
    )
    low = stock_service.low_stock(db)
    out = stock_service.stock_out(db) if include_out else []
    alert_items = {item.id: (item, SUPPLIER_KIND_LOW) for item in low}
    for item in out:
        alert_items[item.id] = (item, SUPPLIER_KIND_OUT)
    if not alert_items:
        return []
    supplier_ids = set(
        db.scalars(
            select(SupplierItem.supplier_id).where(
                SupplierItem.stock_item_id.in_(list(alert_items))
            )
        ).all()
    )
    suppliers = list(
        db.scalars(
            _supplier_statement()
            .where(Supplier.id.in_(supplier_ids), Supplier.aktif.is_(True))
            .order_by(Supplier.nama.asc(), Supplier.id.asc())
        ).unique().all()
    )
    groups: List[Dict[str, Any]] = []
    seen_items: set[int] = set()
    for supplier in suppliers:
        items = []
        for link in supplier.items:
            stock_item = link.stock_item
            if stock_item is None or stock_item.id not in alert_items:
                continue
            item, kind = alert_items[stock_item.id]
            seen_items.add(stock_item.id)
            items.append(
                {
                    "id": item.id,
                    "kode": item.kode,
                    "nama": item.nama,
                    "jumlah": int(item.jumlah or 0),
                    "stok_minimum": item.stok_minimum,
                    "minimum_efektif": stock_service.effective_minimum(
                        item, default_minimum
                    ),
                    "status": kind,
                }
            )
        if not items:
            continue
        items.sort(key=lambda row: (row["status"] != SUPPLIER_KIND_OUT, row["nama"].lower()))
        groups.append(
            {
                "supplier_id": supplier.id,
                "nama": supplier.nama,
                "nomor_hp": supplier.nomor_hp,
                "items": items,
            }
        )
    return groups


def low_stock_items_for_supplier(
    db: Session, supplier_id: int, item_ids: Optional[Iterable[int]] = None
) -> List[Dict[str, Any]]:
    supplier = get_supplier(db, supplier_id)
    default_minimum = int(
        settings_service.get_ops_settings(db).get("stok_minimum_default", 3) or 0
    )
    allowed = {int(value) for value in (item_ids or []) if int(value) > 0}
    rows = []
    for link in supplier.items:
        item = link.stock_item
        if item is None:
            continue
        if allowed and item.id not in allowed:
            continue
        if stock_service.is_out_of_stock(item):
            kind = SUPPLIER_KIND_OUT
        elif stock_service.is_low_stock(item, default_minimum):
            kind = SUPPLIER_KIND_LOW
        else:
            continue
        rows.append(
            {
                "id": item.id,
                "kode": item.kode,
                "nama": item.nama,
                "jumlah": int(item.jumlah or 0),
                "minimum_efektif": stock_service.effective_minimum(
                    item, default_minimum
                ),
                "status": kind,
            }
        )
    rows.sort(key=lambda row: (row["status"] != SUPPLIER_KIND_OUT, row["nama"].lower()))
    return rows
