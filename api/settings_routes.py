"""Endpoint pengaturan identitas bengkel (khusus admin)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.deps import require_owner
from api.schemas import (
    BengkelInfoIn,
    BengkelInfoOut,
    OpsSettingsIn,
    OpsSettingsOut,
    ScheduledBackupOut,
    TelegramInfoOut,
    TelegramSettingsIn,
)
from database.session import get_db
from services import settings_service, telegram_backup_service

router = APIRouter(tags=["Pengaturan"], dependencies=[Depends(require_owner)])


@router.get(
    "/settings/ops",
    response_model=OpsSettingsOut,
)
def get_ops(db: Session = Depends(get_db)):
    return OpsSettingsOut(**settings_service.get_ops_settings(db))


@router.put(
    "/settings/ops",
    response_model=OpsSettingsOut,
)
def update_ops(payload: OpsSettingsIn, db: Session = Depends(get_db)):
    return OpsSettingsOut(
        **settings_service.update_ops_settings(db, payload.model_dump())
    )


@router.put(
    "/settings/bengkel",
    response_model=BengkelInfoOut,
)
def update_bengkel(payload: BengkelInfoIn, db: Session = Depends(get_db)):
    info = settings_service.update_bengkel_info(db, payload.model_dump())
    return BengkelInfoOut(**info)


@router.put(
    "/settings/telegram",
    response_model=TelegramInfoOut,
)
def update_telegram(payload: TelegramSettingsIn, db: Session = Depends(get_db)):
    config = settings_service.update_telegram_config(db, payload.model_dump())
    return TelegramInfoOut(**settings_service.telegram_public_info(config))


@router.post(
    "/admin/scheduled-backup",
    response_model=ScheduledBackupOut,
)
def scheduled_backup(db: Session = Depends(get_db)):
    """Dipicu WorkManager Android; aman diulang tanpa membuat file ganda."""
    return ScheduledBackupOut(
        **telegram_backup_service.run_scheduled_backup_now(db)
    )


@router.post(
    "/admin/backup-now",
)
def backup_now(db: Session = Depends(get_db)):
    """Snapshot terkini + kirim Telegram bila dikonfigurasi; lokal selalu dibuat."""
    return telegram_backup_service.run_manual_backup(db)


@router.post(
    "/admin/telegram-backup",
)
def send_telegram_backup(db: Session = Depends(get_db)):
    result = telegram_backup_service.send_backup(db)
    return {
        "status": "ok",
        "filename": result["filename"],
        "start": result["start"],
        "end": result["end"],
        "sent_at": result["sent_at"],
        "jumlah_nota": result["jumlah_nota"],
    }
