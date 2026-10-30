"""Endpoint konfigurasi printer per perangkat.

Dapat dibaca semua operator yang sudah masuk karena tombol cetak dipakai
kasir. Menulis konfigurasi juga tersedia untuk operator lokal yang sama;
tidak ada data transaksi yang disentuh di sini.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from api.deps import require_auth
from api.schemas import PrinterConfigIn, PrinterConfigOut
from services import printer_settings_service

router = APIRouter(
    tags=["Printer"],
    dependencies=[Depends(require_auth)],
)


@router.get(
    "/printer/config",
    response_model=PrinterConfigOut,
)
def get_printer_config():
    return PrinterConfigOut(**printer_settings_service.get_printer_config())


@router.put(
    "/printer/config",
    response_model=PrinterConfigOut,
)
def update_printer_config(payload: PrinterConfigIn):
    return PrinterConfigOut(
        **printer_settings_service.update_printer_config(payload.model_dump())
    )
