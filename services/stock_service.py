"""Pengelolaan stok sparepart & master tarif jasa."""
from __future__ import annotations

from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from database.models import HargaJasa, StockItem, StockMovement
from repositories import stock_repository as repo
from services.errors import BusinessValidationError, ConflictError, NotFoundError
from services.utils import clean_text, money

LOW_STOCK_THRESHOLD = 3

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


def list_jasa(db: Session) -> List[HargaJasa]:
    return repo.list_jasa(db)


def _validate_stock_fields(
    nama: str,
    harga_modal: Decimal,
    harga_jual: Decimal,
    jumlah: int,
    interval_servis_bulan: int = 0,
) -> tuple[str, Decimal, Decimal, int, int]:
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
    return clean_nama, modal, jual, qty, interval


def create_stock(
    db: Session,
    nama: str,
    harga_modal: Decimal = Decimal("0.00"),
    harga_jual: Decimal = Decimal("0.00"),
    jumlah: int = 0,
    kode: Optional[str] = None,
    interval_servis_bulan: int = 0,
) -> StockItem:
    clean_nama, modal, jual, qty, interval = _validate_stock_fields(
        nama, harga_modal, harga_jual, jumlah, interval_servis_bulan
    )
    clean_kode = clean_text(kode, max_length=64, allow_newlines=False) or None
    if clean_kode and repo.get_stock_by_kode(db, clean_kode):
        raise ConflictError(f"Kode sparepart '{clean_kode}' sudah terdaftar.")

    item = StockItem(
        kode=clean_kode,
        nama=clean_nama,
        harga_modal=modal,
        harga_jual=jual,
        jumlah=qty,
        interval_servis_bulan=interval,
    )
    db.add(item)
    db.flush()
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
    old_qty = item.jumlah

    _reject_null_fields(values, _STOCK_UPDATE_LABELS)

    if "kode" in values:
        new_kode = clean_text(values["kode"], max_length=64, allow_newlines=False) or None
        if new_kode:
            existing = repo.get_stock_by_kode(db, new_kode)
            if existing is not None and existing.id != item.id:
                raise ConflictError(f"Kode sparepart '{new_kode}' sudah terdaftar.")
        item.kode = new_kode

    clean_nama, modal, jual, qty, interval = _validate_stock_fields(
        values.get("nama", item.nama),
        values.get("harga_modal", item.harga_modal),
        values.get("harga_jual", item.harga_jual),
        values.get("jumlah", item.jumlah),
        values.get("interval_servis_bulan", item.interval_servis_bulan),
    )
    item.nama = clean_nama
    item.harga_modal = modal
    item.harga_jual = jual
    item.jumlah = qty
    item.interval_servis_bulan = interval

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


def is_low_stock(item: StockItem) -> bool:
    """Ref: PRD FR-STK-02 - peringatan stok kritis."""
    return item.jumlah <= LOW_STOCK_THRESHOLD
