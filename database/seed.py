"""Seed data awal bengkel radiator (idempotent).

Ref: PRD FR-STK-04 & FR-STK-05.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import HargaJasa, StockItem

DEFAULT_STOCK = [
    ("SP-001", "Upper Tank Fiber Avanza", "85000", "135000", 8),
    ("SP-002", "Upper Tank Fiber Innova", "95000", "150000", 6),
    ("SP-003", "Tutup Radiator 0.9", "18000", "35000", 25),
    ("SP-004", "Tutup Radiator 1.1", "20000", "40000", 20),
    ("SP-005", "Coolant Hijau 1 Galon", "55000", "85000", 15),
    ("SP-006", "Coolant Merah 1 Galon", "58000", "90000", 12),
    ("SP-007", "Selang Radiator Atas", "25000", "50000", 20),
    ("SP-008", "Selang Radiator Bawah", "27000", "55000", 18),
    ("SP-009", "Kisi-Kisi Radiator Canter", "120000", "200000", 4),
    ("SP-010", "Lem Radiator / Sealer", "15000", "30000", 30),
    ("SP-011", "Baut & Klem Set", "8000", "15000", 40),
    ("SP-012", "Fan Blade Plastik", "45000", "75000", 3),
]

DEFAULT_JASA = [
    ("Korok / Kuras Kerak Radiator", "150000"),
    ("Las / Patri Kuningan 1 Titik", "50000"),
    ("Ganti Upper Tank", "200000"),
    ("Ganti Lower Tank", "225000"),
    ("Bongkar Pasang Radiator Mobil", "100000"),
    ("Servis Radiator Genset / Alat Berat", "350000"),
    ("Tes Tekanan & Cek Kebocoran", "75000"),
    ("Cuci Radiator", "80000"),
    ("Ganti Selang Radiator", "60000"),
    ("Tambal Kisi-Kisi", "90000"),
]


def seed_defaults(db: Session) -> None:
    stock_count = db.scalar(select(func.count()).select_from(StockItem)) or 0
    if stock_count == 0:
        db.add_all(
            [
                StockItem(
                    kode=kode,
                    nama=nama,
                    harga_modal=Decimal(modal),
                    harga_jual=Decimal(jual),
                    jumlah=jumlah,
                )
                for kode, nama, modal, jual, jumlah in DEFAULT_STOCK
            ]
        )

    jasa_count = db.scalar(select(func.count()).select_from(HargaJasa)) or 0
    if jasa_count == 0:
        db.add_all(
            [
                HargaJasa(nama=nama, harga_standar=Decimal(harga))
                for nama, harga in DEFAULT_JASA
            ]
        )

    db.commit()
