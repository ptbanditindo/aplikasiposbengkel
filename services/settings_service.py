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


def display_receipt_settings(db: Session) -> Dict[str, bool]:
    show = get_receipt_settings(db)
    if not get_ops_settings(db).get("karyawan_aktif", True):
        show["kasir"] = False
        show["mekanik"] = False
    return show


def get_receipt_settings(db: Session) -> Dict[str, bool]:
    stored = {
        row.key[len(RECEIPT_PREFIX):]: row.value
        for row in db.scalars(
            select(AppSetting).where(AppSetting.key.like(f"{RECEIPT_PREFIX}%"))
        ).all()
    }
    result: Dict[str, bool] = {}
    for field in RECEIPT_FIELDS:
        raw = str(stored.get(field, "1")).strip().lower()
        result[field] = raw not in {"0", "false", "off", "no"}
    return result


def update_receipt_settings(
    db: Session, payload: Dict[str, Any]
) -> Dict[str, bool]:
    for field in RECEIPT_FIELDS:
        if field in payload and payload[field] is not None:
            set_setting(db, f"{RECEIPT_PREFIX}{field}", "1" if payload[field] else "0")
    db.commit()
    return get_receipt_settings(db)


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


RECEIPT_PREFIX = "receipt."
RECEIPT_FIELDS = (
    "tagline", "alamat", "kontak", "no_nota", "tanggal", "kasir", "mekanik",
    "pelanggan", "hp", "unit", "keluhan", "catatan", "jasa", "part",
    "total_jasa", "total_part", "diskon", "grand_total", "metode", "bayar",
    "kembalian", "status_bayar", "garansi", "rekening", "footer",
)

OPS_PREFIX = "ops."
OPS_INT_KEYS = {
    "tempo_hari": (1, 365, 7),
    "prospek_hari": (1, 365, 7),
    "cooldown_hari": (0, 90, 7),
    "garansi_akan_habis_hari": (1, 90, 7),
    "servis_berkala_awal_hari": (1, 90, 14),
    "piutang_jeda_hari": (1, 90, 14),
    "piutang_maks_pengingat": (1, 12, 3),
    "prospek_hari_1": (7, 180, 30),
    "prospek_hari_2": (30, 365, 60),
    "prospek_hari_3": (60, 540, 90),
    "garansi_arsip_hari": (1, 90, 7),
    "belum_bisa_hari": (1, 60, 14),
    "belum_bisa_panjang_hari": (7, 120, 28),
    "maks_pesan_hari": (1, 5, 1),
    "maks_pesan_bulan": (1, 20, 2),
    "jeda_prospek_servis_hari": (1, 90, 7),
    "maks_tidak_merespons": (1, 10, 3),
    "stok_minimum_default": (0, 1000000, 3),
}
OPS_TIME_KEYS = {
    "followup_jam_mulai": "08:00",
    "followup_jam_selesai": "20:00",
}
OPS_BOOL_KEYS = {
    "karyawan_aktif": True,
    "supplier_aktif": True,
}
OPS_TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def get_ops_settings(db: Session) -> Dict[str, Any]:
    """Pengaturan operasional Tahap 11-13 (pembayaran, follow-up, WhatsApp)."""
    stored = {
        row.key[len(OPS_PREFIX):]: row.value
        for row in db.scalars(
            select(AppSetting).where(AppSetting.key.like(f"{OPS_PREFIX}%"))
        ).all()
    }
    result: Dict[str, Any] = {}
    for key, (_low, _high, default) in OPS_INT_KEYS.items():
        raw = stored.get(key, "")
        try:
            result[key] = int(raw) if raw != "" else default
        except (TypeError, ValueError):
            result[key] = default
    for key, default in OPS_TIME_KEYS.items():
        raw = stored.get(key, "")
        result[key] = raw if OPS_TIME_PATTERN.match(raw or "") else default
    for key, default in OPS_BOOL_KEYS.items():
        raw = str(stored.get(key, "1" if default else "0")).strip().lower()
        result[key] = raw not in {"0", "false", "off", "no"}
    return result


def _time_minutes(value: str, fallback: int) -> int:
    if not OPS_TIME_PATTERN.match(value or ""):
        return fallback
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def followup_window(ops: Dict[str, Any]) -> tuple[int, int]:
    return (
        _time_minutes(ops.get("followup_jam_mulai", "08:00"), 8 * 60),
        _time_minutes(ops.get("followup_jam_selesai", "20:00"), 20 * 60),
    )


def followup_window_label(ops: Dict[str, Any]) -> str:
    start, end = followup_window(ops)

    def fmt(minutes: int) -> str:
        return f"{minutes // 60:02d}.{minutes % 60:02d}"

    return f"{fmt(start)}-{fmt(end)}"


def within_followup_window(
    ops: Dict[str, Any], moment: Optional[datetime] = None
) -> bool:
    start, end = followup_window(ops)
    if start == end:
        return True
    current = moment or datetime.now()
    minutes = current.hour * 60 + current.minute
    if start < end:
        return start <= minutes < end
    return minutes >= start or minutes < end


def followup_window_message(ops: Dict[str, Any]) -> str:
    return (
        "Follow up hanya bisa dilakukan antara pukul "
        f"{followup_window_label(ops)}."
    )


def update_ops_settings(db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    current = get_ops_settings(db)
    cleaned: Dict[str, str] = {}
    for key, (low, high, _default) in OPS_INT_KEYS.items():
        raw = payload.get(key, current[key])
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise BusinessValidationError(f"Nilai {key} harus berupa angka.")
        if not low <= value <= high:
            raise BusinessValidationError(
                f"Nilai {key} harus antara {low} dan {high}."
            )
        cleaned[f"{OPS_PREFIX}{key}"] = str(value)
    for key, default in OPS_TIME_KEYS.items():
        raw = payload.get(key, current[key])
        value = str(raw if raw is not None else default).strip()
        if not OPS_TIME_PATTERN.match(value):
            raise BusinessValidationError(
                f"Nilai {key} harus berformat HH:MM."
            )
        cleaned[f"{OPS_PREFIX}{key}"] = value
    for key, default in OPS_BOOL_KEYS.items():
        raw = payload.get(key, current[key])
        if isinstance(raw, bool):
            value = raw
        elif str(raw).strip().lower() in {"1", "true", "on", "yes"}:
            value = True
        elif str(raw).strip().lower() in {"0", "false", "off", "no"}:
            value = False
        else:
            value = default
        cleaned[f"{OPS_PREFIX}{key}"] = "1" if value else "0"
    if (
        cleaned[f"{OPS_PREFIX}followup_jam_mulai"]
        == cleaned[f"{OPS_PREFIX}followup_jam_selesai"]
    ):
        raise BusinessValidationError(
            "Jam mulai dan jam selesai follow up tidak boleh sama."
        )
    for key, value in cleaned.items():
        set_setting(db, key, value)
    db.commit()
    return get_ops_settings(db)


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
