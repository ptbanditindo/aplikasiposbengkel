"""Endpoint laporan kas, backup & restore database."""
from __future__ import annotations

import asyncio
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from api.deps import require_auth
from api.schemas import DailyReportOut, PeriodReportOut, SoldPartsReportOut
from config import settings
from database.session import get_db
from services import backup_service, report_service
from services.maintenance import RESTORE_WAIT_TIMEOUT, gate

UPLOAD_CHUNK_SIZE = 1024 * 1024
UPLOAD_PREFIX = "upload_restore_"

router = APIRouter(
    tags=["Laporan & Administrasi"], dependencies=[Depends(require_auth)]
)


@router.get("/reports/daily-cash", response_model=DailyReportOut)
def daily_cash(
    tanggal: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return DailyReportOut.model_validate(
        report_service.daily_report(db, tanggal or date.today())
    )


@router.get("/reports/period", response_model=PeriodReportOut)
def period_report(
    start: date = Query(...),
    end: date = Query(...),
    db: Session = Depends(get_db),
):
    if end < start:
        raise HTTPException(status_code=400, detail="Tanggal akhir sebelum tanggal mulai.")
    if end - start > timedelta(days=366):
        raise HTTPException(status_code=400, detail="Rentang laporan maksimal 366 hari.")
    return PeriodReportOut.model_validate(report_service.period_report(db, start, end))


@router.get("/reports/sold-parts", response_model=SoldPartsReportOut)
def sold_parts(
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Riwayat part terjual per penjualan; tanpa tanggal = seluruh riwayat."""
    if (start is None) != (end is None):
        raise HTTPException(
            status_code=400,
            detail="Isi tanggal mulai dan akhir, atau kosongkan keduanya.",
        )
    if start is not None and end is not None:
        if end < start:
            raise HTTPException(
                status_code=400, detail="Tanggal akhir sebelum tanggal mulai."
            )
        if end - start > timedelta(days=366):
            raise HTTPException(
                status_code=400, detail="Rentang laporan maksimal 366 hari."
            )
    return SoldPartsReportOut.model_validate(
        report_service.sold_parts_report(db, start, end)
    )


@router.post(
    "/admin/backup",
    response_class=FileResponse,
)
def backup_database():
    """Unduh salinan database SQLite (Ref: PRD TC-20)."""
    path = backup_service.create_backup()
    return FileResponse(
        path=str(path),
        media_type="application/x-sqlite3",
        filename=path.name,
    )


async def _save_upload(file: UploadFile, max_bytes: int) -> Path:
    """Alirkan unggahan ke berkas sementara tanpa memuat seluruh isi ke RAM."""
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(
        prefix=UPLOAD_PREFIX, suffix=".db", dir=str(settings.backup_dir)
    )
    os.close(handle)
    path = Path(name)
    size = 0
    try:
        with path.open("wb") as target:
            while True:
                chunk = await file.read(UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            "Berkas backup terlalu besar. Batas unggah restore "
                            f"{max_bytes // (1024 * 1024)} MB."
                        ),
                    )
                target.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="Berkas backup kosong.")
        return path
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


@router.post(
    "/admin/restore",
)
async def restore_database(file: UploadFile = File(...)):
    batas = settings.backup_max_restore_mb * 1024 * 1024
    temp_path = await _save_upload(file, batas)
    try:
        mulai = await asyncio.to_thread(gate.begin_restore, RESTORE_WAIT_TIMEOUT)
        if not mulai:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Restore lain sedang berjalan atau masih ada transaksi "
                    "aktif. Tunggu sebentar lalu coba lagi."
                ),
            )
        try:
            await asyncio.to_thread(backup_service.restore_backup, temp_path)
        finally:
            gate.end_restore()
    finally:
        temp_path.unlink(missing_ok=True)
    return {"status": "ok", "message": "Database berhasil dipulihkan."}
