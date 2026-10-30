"""Endpoint pengaturan identitas bengkel (khusus admin)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.deps import require_auth
from api.schemas import (
    BengkelInfoIn,
    BengkelInfoOut,
    TelegramInfoOut,
    TelegramSettingsIn,
)
from database.session import get_db
from services import settings_service, telegram_backup_service

router = APIRouter(tags=["Pengaturan"], dependencies=[Depends(require_auth)])


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
