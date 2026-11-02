"""Pengelolaan stok sparepart & master tarif jasa."""
from __future__ import annotations

import re
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import (
    HargaJasa,
    StockBarcode,
    StockItem,
    StockMovement,
    Supplier,
    SupplierItem,
)
from database.session import begin_immediate
from repositories import stock_repository as repo
from services.errors import BusinessValidationError, ConflictError, NotFoundError
from services.utils import clean_text, money

_BARCODE_PATTERN = re.compile(r"^[\x20-\x7E]+$")

_STOCK_UPDATE_LABELS = {
    "nama": "Nama",
    "harga_modal": "Harga modal",
    "harga_jual": "Harga jual",
    "jumlah": "Jumlah",
    "interval_servis_bulan": "Interval servis",
}
_JASA_UPDATE_LABELS = {
    "nama": "Nama",
    "harga_standar": "Harga standar",
    "interval_servis_bulan": "Interval servis",
}


def _reject_null_fields(values: dict, labels: dict[str, str]) -> None:
    for field, label in labels.items():
        if field in values and values[field] is None:
            raise BusinessValidationError(f"{label} tidak boleh kosong (null).")


def list_stock(db: Session) -> List[StockItem]:
    return repo.list_stock(db)


def normalize_barcode(value: Optional[str]) -> Optional[str]:
    """Validasi kode scanner: 1-128 karakter ASCII yang dapat dicetak."""
    text = clean_text(value, max_length=128, allow_newlines=False) or None
    if not text:
        return None
    if not _BARCODE_PATTERN.fullmatch(text):
        raise BusinessValidationError(
            "Barcode hanya boleh berisi huruf, angka, dan simbol tanpa spasi baris."
        )
    return text


def _clean_barcodes(
    db: Session, values: Optional[List[str]], stock_item_id: Optional[int] = None
) -> List[str]:
    if not values:
        return []
    cleaned: List[str] = []
    seen = set()
    for raw in values:
        code = normalize_barcode(raw)
        if not code or code in seen:
            continue
        alias = repo.get_barcode(db, code)
        if alias is not None and alias.stock_item_id != stock_item_id:
            raise ConflictError(f"Barcode '{code}' sudah dipakai barang lain.")
        other = repo.get_stock_by_kode(db, code)
        if other is not None and other.id != stock_item_id:
            raise ConflictError(f"Barcode '{code}' sudah dipakai barang lain.")
        seen.add(code)
        cleaned.append(code)
    return cleaned


def _replace_barcodes(db: Session, item: StockItem, barcodes: List[str]) -> None:
    db.query(StockBarcode).filter(
        StockBarcode.stock_item_id == item.id
    ).delete(synchronize_session=False)
    for code in barcodes:
        db.add(StockBarcode(stock_item_id=item.id, barcode=code))
    db.flush()


def resolve_barcode(db: Session, code: str) -> Tuple[Optional[StockItem], str]:
    """Cari barang dari barcode alias lebih dulu, lalu kode utama."""
    normalized = normalize_barcode(code)
    if not normalized:
        return None, ""
    item = repo.get_stock_by_barcode(db, normalized)
    if item is not None:
        return item, "barcode"
    item = repo.get_stock_by_kode(db, normalized)
    if item is not None:
        return item, "kode"
    return None, ""


def list_barcodes(db: Session, stock_id: int) -> List[str]:
    item = repo.get_stock(db, stock_id)
    if item is None:
        raise NotFoundError("Sparepart tidak ditemukan.")
    return [row.barcode for row in repo.list_barcodes(db, stock_id)]


def list_jasa(db: Session) -> List[HargaJasa]:
    return repo.list_jasa(db)


def _validate_stock_fields(
    nama: str,
    harga_modal: Decimal,
    harga_jual: Decimal,
    jumlah: int,
    interval_servis_bulan: int = 0,
    stok_minimum: Optional[int] = None,
) -> tuple[str, Decimal, Decimal, int, int, Optional[int]]:
    clean_nama = clean_text(nama, max_length=255, allow_newlines=False)
    if len(clean_nama) < 2:
        raise BusinessValidationError("Nama sparepart minimal 2 karakter.")
    modal = money(harga_modal)
    jual = money(harga_jual)
    if modal < 0 or jual < 0:
        raise BusinessValidationError("Harga tidak boleh negatif.")
    qty = int(jumlah)
    if qty < 0:
        raise BusinessValidationError("Jumlah stok tidak boleh negatif.")
    interval = _clean_interval(interval_servis_bulan)
    minimum = _clean_minimum(stok_minimum)
    return clean_nama, modal, jual, qty, interval, minimum


def create_stock(
    db: Session,
    nama: str,
    harga_modal: Decimal = Decimal("0.00"),
    harga_jual: Decimal = Decimal("0.00"),
    jumlah: int = 0,
    kode: Optional[str] = None,
    interval_servis_bulan: int = 0,
    stok_minimum: Optional[int] = None,
    supplier_ids: Optional[List[int]] = None,
    barcodes: Optional[List[str]] = None,
) -> StockItem:
    clean_nama, modal, jual, qty, interval, minimum = _validate_stock_fields(
        nama, harga_modal, harga_jual, jumlah, interval_servis_bulan, stok_minimum
    )
    clean_kode = clean_text(kode, max_length=64, allow_newlines=False) or None
    if clean_kode and repo.get_stock_by_kode(db, clean_kode):
        raise ConflictError(f"Kode sparepart '{clean_kode}' sudah terdaftar.")
    if clean_kode and repo.get_barcode(db, clean_kode):
        raise ConflictError(f"Kode sparepart '{clean_kode}' sudah dipakai barcode.")
    clean_barcodes = _clean_barcodes(db, barcodes)

    item = StockItem(
        kode=clean_kode,
        nama=clean_nama,
        harga_modal=modal,
        harga_jual=jual,
        jumlah=qty,
        interval_servis_bulan=interval,
        stok_minimum=minimum,
    )
    db.add(item)
    db.flush()
    if clean_barcodes:
        _replace_barcodes(db, item, clean_barcodes)
    if supplier_ids is not None:
        _set_suppliers(db, item.id, supplier_ids)
    if qty > 0:
        db.add(
            StockMovement(
                stock_item_id=item.id,
                nama_item=item.nama,
                jenis="MASUK",
                jumlah=qty,
                alasan="Stok awal",
                oleh="Kasir",
            )
        )
    db.commit()
    db.refresh(item)
    return item


def update_stock(db: Session, stock_id: int, **values) -> StockItem:
    item = repo.get_stock(db, stock_id)
    if item is None:
        raise NotFoundError("Sparepart tidak ditemukan.")

    alasan = clean_text(
        values.pop("alasan", None), max_length=255, allow_newlines=False
    ) or "Koreksi stok manual"
    supplier_ids = values.pop("supplier_ids", None)
    raw_barcodes = values.pop("barcodes", None)
    old_qty = item.jumlah

    _reject_null_fields(values, _STOCK_UPDATE_LABELS)

    if "kode" in values:
        new_kode = clean_text(values["kode"], max_length=64, allow_newlines=False) or None
        if new_kode:
            existing = repo.get_stock_by_kode(db, new_kode)
            if existing is not None and existing.id != item.id:
                raise ConflictError(f"Kode sparepart '{new_kode}' sudah terdaftar.")
            alias = repo.get_barcode(db, new_kode)
            if alias is not None and alias.stock_item_id != item.id:
                raise ConflictError(f"Kode sparepart '{new_kode}' sudah dipakai barcode.")
        item.kode = new_kode

    clean_barcodes = (
        _clean_barcodes(db, raw_barcodes, item.id)
        if raw_barcodes is not None
        else None
    )

    clean_nama, modal, jual, qty, interval, minimum = _validate_stock_fields(
        values.get("nama", item.nama),
        values.get("harga_modal", item.harga_modal),
        values.get("harga_jual", item.harga_jual),
        values.get("jumlah", item.jumlah),
        values.get("interval_servis_bulan", item.interval_servis_bulan),
        values.get("stok_minimum", item.stok_minimum),
    )
    item.nama = clean_nama
    item.harga_modal = modal
    item.harga_jual = jual
    item.jumlah = qty
    item.interval_servis_bulan = interval
    item.stok_minimum = minimum
    if clean_barcodes is not None:
        _replace_barcodes(db, item, clean_barcodes)
    if supplier_ids is not None:
        _set_suppliers(db, item.id, supplier_ids)

    # S-06: koreksi manual tidak boleh menghapus jejak audit.
    if qty != old_qty:
        db.add(
            StockMovement(
                stock_item_id=item.id,
                nama_item=item.nama,
                jenis="KOREKSI",
                jumlah=qty - old_qty,
                alasan=alasan,
                oleh="Kasir",
            )
        )

    db.commit()
    db.refresh(item)
    return item


def delete_stock(db: Session, stock_id: int) -> None:
    item = repo.get_stock(db, stock_id)
    if item is None:
        raise NotFoundError("Sparepart tidak ditemukan.")
    old_qty = item.jumlah
    nama = item.nama
    db.delete(item)
    db.flush()
    if old_qty:
        db.add(
            StockMovement(
                stock_item_id=None,
                nama_item=nama,
                jenis="KOREKSI",
                jumlah=-old_qty,
                alasan="Hapus sparepart",
                oleh="Kasir",
            )
        )
    db.commit()


def add_stock(
    db: Session,
    stock_id: int,
    jumlah: int,
    alasan: Optional[str] = None,
    oleh: str = "Kasir",
) -> StockItem:
    """Tambah stok masuk dari scanner atau form manual."""
    qty = int(jumlah)
    if qty < 1:
        raise BusinessValidationError("Jumlah stok masuk minimal 1.")
    item = repo.get_stock(db, stock_id)
    if item is None:
        raise NotFoundError("Sparepart tidak ditemukan.")
    item.jumlah = int(item.jumlah or 0) + qty
    db.add(
        StockMovement(
            stock_item_id=item.id,
            nama_item=item.nama,
            jenis="MASUK",
            jumlah=qty,
            alasan=clean_text(alasan, max_length=255, allow_newlines=False)
            or "Tambah stok",
            oleh=oleh,
        )
    )
    db.commit()
    db.refresh(item)
    return item


def opname_stock(
    db: Session,
    items: List[dict],
    alasan: Optional[str] = None,
    oleh: str = "Kasir",
) -> List[StockItem]:
    """Sesuaikan stok hasil opname secara atomik.

    Setiap barang hanya boleh muncul sekali; selisih dicatat sebagai KOREKSI.
    """
    if not items:
        raise BusinessValidationError("Tambahkan minimal satu barang opname.")
    seen = set()
    reason = clean_text(alasan, max_length=255, allow_newlines=False) or "Stok opname"
    results: List[StockItem] = []

    with db.begin():
        begin_immediate(db)
        for row in items:
            stock_id = int(row.get("stock_item_id") or 0)
            new_qty = int(row.get("jumlah"))
            if stock_id <= 0:
                raise BusinessValidationError("Barang opname tidak valid.")
            if stock_id in seen:
                raise BusinessValidationError(
                    "Barang opname tidak boleh muncul lebih dari sekali."
                )
            seen.add(stock_id)
            if new_qty < 0:
                raise BusinessValidationError("Jumlah opname tidak boleh negatif.")
            item = db.get(StockItem, stock_id)
            if item is None:
                raise NotFoundError("Sparepart tidak ditemukan.")
            old_qty = int(item.jumlah or 0)
            item.jumlah = new_qty
            if new_qty != old_qty:
                db.add(
                    StockMovement(
                        stock_item_id=item.id,
                        nama_item=item.nama,
                        jenis="KOREKSI",
                        jumlah=new_qty - old_qty,
                        alasan=reason,
                        oleh=oleh,
                    )
                )
            db.flush()
            results.append(item)

    for item in results:
        db.refresh(item)
    return results


def list_movements(
    db: Session,
    stock_item_id: Optional[int] = None,
    service_record_id: Optional[int] = None,
    limit: int = 200,
):
    return repo.list_movements(
        db,
        stock_item_id=stock_item_id,
        service_record_id=service_record_id,
        limit=limit,
    )


def _set_suppliers(
    db: Session, stock_item_id: int, supplier_ids: List[int]
) -> None:
    unique_ids = sorted({int(value) for value in supplier_ids if int(value) > 0})
    if unique_ids:
        found = set(
            db.scalars(select(Supplier.id).where(Supplier.id.in_(unique_ids))).all()
        )
        missing = [value for value in unique_ids if value not in found]
        if missing:
            raise BusinessValidationError("Ada supplier yang tidak ditemukan.")
    db.query(SupplierItem).filter(
        SupplierItem.stock_item_id == stock_item_id
    ).delete(synchronize_session=False)
    for supplier_id in unique_ids:
        db.add(
            SupplierItem(
                supplier_id=supplier_id,
                stock_item_id=stock_item_id,
            )
        )
    db.flush()


def _clean_minimum(value) -> Optional[int]:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        minimum = int(value)
    except (TypeError, ValueError):
        raise BusinessValidationError("Batas minimum stok harus berupa angka.")
    if minimum < 0 or minimum > 1000000:
        raise BusinessValidationError(
            "Batas minimum stok harus antara 0 dan 1.000.000."
        )
    return minimum


def _minimum_default(db: Session) -> int:
    from services import settings_service

    ops = settings_service.get_ops_settings(db)
    return int(ops.get("stok_minimum_default", 3) or 0)


def effective_minimum(item: StockItem, default: int) -> int:
    if item.stok_minimum is None:
        return default
    return int(item.stok_minimum)


def is_low_stock(item: StockItem, default: int = 0) -> bool:
    minimum = effective_minimum(item, default)
    qty = int(item.jumlah or 0)
    return minimum > 0 and 0 < qty <= minimum


def is_out_of_stock(item: StockItem) -> bool:
    return int(item.jumlah or 0) <= 0


def low_stock(db: Session) -> List[StockItem]:
    default = _minimum_default(db)
    items = [
        item
        for item in repo.list_stock(db)
        if is_low_stock(item, default)
    ]
    items.sort(
        key=lambda item: (
            int(item.jumlah or 0) - effective_minimum(item, default),
            (item.nama or "").lower(),
            item.id,
        )
    )
    return items


def low_stock_count(db: Session) -> int:
    return len(low_stock(db))


def stock_out(db: Session) -> List[StockItem]:
    items = [item for item in repo.list_stock(db) if is_out_of_stock(item)]
    items.sort(key=lambda item: ((item.nama or "").lower(), item.id))
    return items


def stock_out_count(db: Session) -> int:
    return len(stock_out(db))


def _clean_interval(value) -> int:
    try:
        interval = int(value or 0)
    except (TypeError, ValueError):
        raise BusinessValidationError("Interval servis harus berupa angka bulan.")
    if interval < 0 or interval > 120:
        raise BusinessValidationError("Interval servis harus antara 0 dan 120 bulan.")
    return interval


def create_jasa(
    db: Session,
    nama: str,
    harga_standar: Decimal,
    interval_servis_bulan: int = 0,
) -> HargaJasa:
    clean_nama = clean_text(nama, max_length=255, allow_newlines=False)
    if len(clean_nama) < 2:
        raise BusinessValidationError("Nama jasa minimal 2 karakter.")
    harga = money(harga_standar)
    if harga < 0:
        raise BusinessValidationError("Tarif jasa tidak boleh negatif.")
    interval = _clean_interval(interval_servis_bulan)

    jasa = HargaJasa(
        nama=clean_nama,
        harga_standar=harga,
        interval_servis_bulan=interval,
    )
    db.add(jasa)
    db.commit()
    db.refresh(jasa)
    return jasa


def update_jasa(db: Session, jasa_id: int, **values) -> HargaJasa:
    jasa = repo.get_jasa(db, jasa_id)
    if jasa is None:
        raise NotFoundError("Tarif jasa tidak ditemukan.")

    _reject_null_fields(values, _JASA_UPDATE_LABELS)

    clean_nama = clean_text(
        values.get("nama", jasa.nama), max_length=255, allow_newlines=False
    )
    if len(clean_nama) < 2:
        raise BusinessValidationError("Nama jasa minimal 2 karakter.")
    harga = money(values.get("harga_standar", jasa.harga_standar))
    if harga < 0:
        raise BusinessValidationError("Tarif jasa tidak boleh negatif.")
    interval = _clean_interval(
        values.get("interval_servis_bulan", jasa.interval_servis_bulan)
    )

    jasa.nama = clean_nama
    jasa.harga_standar = harga
    jasa.interval_servis_bulan = interval
    db.commit()
    db.refresh(jasa)
    return jasa


def delete_jasa(db: Session, jasa_id: int) -> None:
    jasa = repo.get_jasa(db, jasa_id)
    if jasa is None:
        raise NotFoundError("Tarif jasa tidak ditemukan.")
    db.delete(jasa)
    db.commit()


