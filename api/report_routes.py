"""Endpoint laporan kas, backup & restore database."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from api.deps import require_admin_token
from api.schemas import DailyReportOut, PeriodReportOut, SoldPartsReportOut
from database.session import get_db
from services import backup_service, report_service

router = APIRouter(tags=["Laporan & Administrasi"])


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
    dependencies=[Depends(require_admin_token)],
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


@router.post(
    "/admin/restore",
    dependencies=[Depends(require_admin_token)],
)
async def restore_database(file: UploadFile = File(...)):
    data = await file.read()
    backup_service.restore_backup(data)
    return {"status": "ok", "message": "Database berhasil dipulihkan."}
