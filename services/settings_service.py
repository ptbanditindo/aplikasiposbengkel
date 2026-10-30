"""Identitas bengkel yang dapat diubah dari aplikasi.

Nilai default berasal dari `.env`; perubahan dari UI disimpan di tabel
`app_settings` dan menimpa default tersebut.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from database.models import AppSetting
from services.errors import BusinessValidationError
from services.utils import clean_text

# field payload -> atribut Settings (nilai default dari .env)
FIELD_TO_ENV = {
    "nama": "bengkel_nama",
    "tagline": "bengkel_tagline",
    "alamat": "bengkel_alamat",
    "telepon": "bengkel_telepon",
    "wa": "bengkel_wa",
    "bank_nama": "bengkel_bank_nama",
    "no_rekening": "bengkel_no_rekening",
    "atas_nama": "bengkel_atas_nama",
}

FIELD_MAX_LENGTH = {
    "nama": 255,
    "tagline": 255,
    "alamat": 500,
    "telepon": 64,
    "wa": 64,
    "bank_nama": 255,
    "no_rekening": 64,
    "atas_nama": 255,
}

KEY_PREFIX = "bengkel."

TELEGRAM_PREFIX = "telegram."
BACKUP_STALE_DAYS = 2
BACKUP_LAST_AT_KEY = "backup.last_local_at"
BACKUP_LAST_FILENAME_KEY = "backup.last_local_filename"
BACKUP_LAST_STATUS_KEY = "backup.last_status"
BACKUP_LAST_ERROR_KEY = "backup.last_error"
BACKUP_LAST_TELEGRAM_KEY = "backup.last_telegram_at"
_TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_BOT_TOKEN_PATTERN = re.compile(r"^\d+:[A-Za-z0-9_-]{10,}$")
_CHAT_ID_PATTERN = re.compile(r"^(-?\d+|@[A-Za-z0-9_]{4,})$")


def default_bengkel_info() -> Dict[str, str]:
    """Identitas dari `.env` saja (tanpa akses database)."""
    return {field: getattr(settings, attr) for field, attr in FIELD_TO_ENV.items()}


def get_bengkel_info(db: Session) -> Dict[str, str]:
    """Gabungkan default .env dengan nilai yang tersimpan di database."""
    info = default_bengkel_info()
    stored = db.scalars(
        select(AppSetting).where(AppSetting.key.like(f"{KEY_PREFIX}%"))
    ).all()
    for row in stored:
        field = row.key[len(KEY_PREFIX):]
        if field in info:
            info[field] = row.value
    return info


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=value))
    else:
        row.value = value


def get_setting(db: Session, key: str, default: str = "") -> str:
    row = db.get(AppSetting, key)
    return row.value if row is not None else default


def update_bengkel_info(db: Session, payload: Dict[str, Any]) -> Dict[str, str]:
    cleaned = {
        field: clean_text(payload.get(field), max_length=FIELD_MAX_LENGTH[field])
        for field in FIELD_TO_ENV
    }
    if len(cleaned["nama"]) < 2:
        raise BusinessValidationError("Nama bengkel minimal 2 karakter.")

    for field, value in cleaned.items():
        set_setting(db, f"{KEY_PREFIX}{field}", value)

    db.commit()
    return get_bengkel_info(db)


def _stored_values(db: Session) -> Dict[str, str]:
    rows = db.scalars(
        select(AppSetting).where(AppSetting.key.like(f"{TELEGRAM_PREFIX}%"))
    ).all()
    return {row.key[len(TELEGRAM_PREFIX):]: row.value for row in rows}


def _stored_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value if value is not None else "").strip().lower()
    if not text:
        return default
    return text in {"1", "true", "yes", "on", "ya"}


def get_telegram_config(db: Session) -> Dict[str, Any]:
    """Konfigurasi bot Telegram (default .env, ditimpa nilai dari UI)."""
    stored = _stored_values(db)
    enabled_default = settings.telegram_backup_enabled
    jam = stored.get("jam") or settings.telegram_backup_time or "21:00"
    return {
        "bot_token": stored.get("bot_token") or settings.telegram_bot_token,
        "chat_id": stored.get("chat_id") or settings.telegram_chat_id,
        "enabled": _stored_bool(stored.get("enabled"), enabled_default),
        "jam": jam,
        "needs_reconfig": _stored_bool(stored.get("needs_reconfig")),
        "last_sent_at": stored.get("last_sent_at", ""),
        "last_attempt_at": stored.get("last_attempt_at", ""),
        "pending_since": stored.get("pending_since", ""),
        "last_error": stored.get("last_error", ""),
    }


def telegram_public_info(config: Dict[str, Any]) -> Dict[str, Any]:
    """Data aman ditampilkan ke UI (tanpa bot token)."""
    return {
        "enabled": bool(config.get("enabled")),
        "jam": config.get("jam") or "21:00",
        "chat_id": config.get("chat_id") or "",
        "configured": bool(config.get("bot_token") and config.get("chat_id")),
        "needs_reconfig": bool(config.get("needs_reconfig")),
        "last_sent_at": config.get("last_sent_at") or None,
        "last_error": config.get("last_error") or None,
    }


def _parse_iso(value: Any) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def get_backup_status(
    db: Session,
    config: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Status backup terakhir + penanda basi untuk peringatan di UI.

    Backup manual Telegram dari versi sebelumnya tidak menulis kunci
    `backup.*`; nilainya jatuh ke `telegram.last_sent_at` agar pengguna lama
    tidak langsung melihat peringatan palsu.
    """
    moment = now or datetime.now()
    telegram = config if config is not None else get_telegram_config(db)
    last_at = (
        get_setting(db, BACKUP_LAST_AT_KEY)
        or telegram.get("last_sent_at")
        or ""
    )
    last_dt = _parse_iso(last_at)
    stale = last_dt is None or moment - last_dt > timedelta(days=BACKUP_STALE_DAYS)
    return {
        "last_local_at": last_at or None,
        "last_local_filename": get_setting(db, BACKUP_LAST_FILENAME_KEY) or None,
        "last_status": get_setting(db, BACKUP_LAST_STATUS_KEY) or None,
        "last_error": get_setting(db, BACKUP_LAST_ERROR_KEY) or None,
        "last_telegram_at": (
            get_setting(db, BACKUP_LAST_TELEGRAM_KEY)
            or telegram.get("last_sent_at")
            or None
        ),
        "stale": stale,
        "stale_days": BACKUP_STALE_DAYS,
    }


def update_telegram_config(db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    enabled = bool(payload.get("enabled"))
    jam = clean_text(payload.get("jam"), max_length=5) or "21:00"
    if not _TIME_PATTERN.match(jam):
        raise BusinessValidationError("Jam backup harus berformat HH:MM (contoh 21:00).")

    token = clean_text(payload.get("bot_token"), max_length=200)
    chat_id = clean_text(payload.get("chat_id"), max_length=64)
    if token and not _BOT_TOKEN_PATTERN.match(token):
        raise BusinessValidationError(
            "Format bot token Telegram tidak valid (contoh 123456789:AA...)."
        )
    if chat_id and not _CHAT_ID_PATTERN.match(chat_id):
        raise BusinessValidationError(
            "Format chat ID Telegram tidak valid (contoh 123456789 atau @namachannel)."
        )

    # Token/chat ID kosong berarti pertahankan nilai yang sudah tersimpan.
    if token:
        set_setting(db, f"{TELEGRAM_PREFIX}bot_token", token)
    if chat_id:
        set_setting(db, f"{TELEGRAM_PREFIX}chat_id", chat_id)
    set_setting(db, f"{TELEGRAM_PREFIX}enabled", "1" if enabled else "0")
    set_setting(db, f"{TELEGRAM_PREFIX}jam", jam)
    set_setting(db, f"{TELEGRAM_PREFIX}last_error", "")
    db.commit()

    config = get_telegram_config(db)
    if config["bot_token"] and config["chat_id"]:
        set_setting(db, f"{TELEGRAM_PREFIX}needs_reconfig", "")
        db.commit()
        config = get_telegram_config(db)
    return config
