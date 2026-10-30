"""Backup penuh database ke Telegram, manual maupun terjadwal.

Setiap pengiriman berisi satu file SQLite lengkap (seluruh data) dengan nama
rentang tanggal data, sehingga tidak ada file terpisah yang tumpang tindih.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import settings
from database.models import ServiceRecord
from database.session import SessionLocal
from services import backup_service, settings_service
from services.errors import BusinessValidationError
from services.utils import sanitize_ascii

logger = logging.getLogger(__name__)

RETRY_MINUTES = 10
MAX_DOCUMENT_BYTES = 50 * 1024 * 1024  # batas kirim dokumen Bot API Telegram


def data_range(db: Session) -> tuple[date, date]:
    first = db.scalar(select(func.min(ServiceRecord.waktu_service)))
    end = date.today()
    start = first.date() if first else end
    if start > end:
        start = end
    return start, end


def backup_filename(start: date, end: date) -> str:
    return f"bengkel_radiator_{start:%Y%m%d}-{end:%Y%m%d}.db"


def _caption(db: Session, start: date, end: date) -> str:
    nama = sanitize_ascii(settings_service.get_bengkel_info(db)["nama"])
    jumlah = db.scalar(select(func.count()).select_from(ServiceRecord)) or 0
    return (
        f"Backup {nama}\n"
        f"Data {start:%d/%m/%Y} s/d {end:%d/%m/%Y}\n"
        f"{jumlah} nota tersimpan"
    )


def _send_document(
    token: str,
    chat_id: str,
    path: Path,
    filename: str,
    caption: str,
) -> None:
    url = f"{settings.telegram_api_base.rstrip('/')}/bot{token}/sendDocument"
    with path.open("rb") as handle:
        response = httpx.post(
            url,
            data={"chat_id": chat_id, "caption": caption},
            files={"document": (filename, handle, "application/x-sqlite3")},
            timeout=60.0,
        )

    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if response.status_code != 200 or not payload.get("ok"):
        description = str(
            payload.get("description") or f"HTTP {response.status_code}"
        )
        raise BusinessValidationError(
            "Telegram menolak backup: " + description[:200]
        )


def _scrub_token(message: str, token: str) -> str:
    return message.replace(token, "***") if token else message


def _record_failure(db: Session, message: str, now: datetime) -> None:
    stamp = now.isoformat(timespec="seconds")
    settings_service.set_setting(db, "telegram.last_attempt_at", stamp)
    settings_service.set_setting(db, "telegram.last_error", message[:300])
    if not settings_service.get_setting(db, "telegram.pending_since"):
        settings_service.set_setting(db, "telegram.pending_since", stamp)
    db.commit()


def send_backup(db: Session) -> Dict[str, Any]:
    """Kirim snapshot database lengkap ke Telegram milik owner."""
    config = settings_service.get_telegram_config(db)
    if not config["bot_token"] or not config["chat_id"]:
        raise BusinessValidationError(
            "Bot token dan chat ID Telegram belum diatur di menu Pengaturan."
        )

    start, end = data_range(db)
    backup_path = backup_service.create_backup()
    if backup_path.stat().st_size > MAX_DOCUMENT_BYTES:
        raise BusinessValidationError(
            "Ukuran backup melebihi 50 MB (batas kirim bot Telegram). "
            "Unduh backup manual dari menu Pengaturan."
        )

    filename = backup_filename(start, end)
    caption = _caption(db, start, end)
    now = datetime.now()

    try:
        _send_document(
            config["bot_token"], config["chat_id"], backup_path, filename, caption
        )
    except BusinessValidationError as exc:
        message = _scrub_token(str(exc), config["bot_token"])
        _record_failure(db, message, now)
        raise BusinessValidationError(message) from exc
    except Exception as exc:  # jaringan / DNS / timeout
        message = _scrub_token(
            "Tidak dapat menghubungi Telegram: " + str(exc)[:200],
            config["bot_token"],
        )
        _record_failure(db, message, now)
        raise BusinessValidationError(message) from exc

    sent_at = now.isoformat(timespec="seconds")
    settings_service.set_setting(db, "telegram.last_sent_at", sent_at)
    settings_service.set_setting(db, "telegram.last_attempt_at", sent_at)
    settings_service.set_setting(db, "telegram.pending_since", "")
    settings_service.set_setting(db, "telegram.last_error", "")
    db.commit()

    return {
        "filename": filename,
        "start": start,
        "end": end,
        "sent_at": now,
        "jumlah_nota": db.scalar(select(func.count()).select_from(ServiceRecord)) or 0,
    }


def _parse_jam(value: str) -> Optional[time]:
    try:
        hour, minute = str(value).split(":")
        return time(int(hour), int(minute))
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: Any) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _has_missed_backup(now: datetime, config: Dict[str, Any]) -> bool:
    """True bila ada jadwal backup yang terlewat dan belum tergantikan.

    Sumber bukti: percobaan gagal yang belum pernah sukses (pending_since),
    atau sukses terakhir yang lebih lama dari kemarin (aplikasi sempat mati).
    """
    pending = _parse_datetime(config.get("pending_since"))
    if pending is not None and pending.date() < now.date():
        return True

    last_sent = _parse_datetime(config.get("last_sent_at"))
    return (
        last_sent is not None
        and last_sent.date() < now.date() - timedelta(days=1)
    )


def should_send(now: datetime, config: Dict[str, Any]) -> bool:
    """True bila backup perlu dikirim sekarang.

    Selain jadwal harian, backup yang terlewat (mis. internet mati) langsung
    dikirim begitu aplikasi online kembali, tanpa menunggu jam kirim.
    """
    if not config.get("enabled"):
        return False
    if not config.get("bot_token") or not config.get("chat_id"):
        return False

    target = _parse_jam(config.get("jam") or "21:00")
    if target is None:
        return False

    last_sent = _parse_datetime(config.get("last_sent_at"))
    target_today = datetime.combine(now.date(), target)
    schedule_due = now.time() >= target and (
        last_sent is None or last_sent < target_today
    )
    catch_up_due = _has_missed_backup(now, config) and (
        last_sent is None or last_sent.date() < now.date()
    )
    if not (schedule_due or catch_up_due):
        return False

    attempted = _parse_datetime(config.get("last_attempt_at"))
    if attempted is not None and now - attempted < timedelta(minutes=RETRY_MINUTES):
        return False
    return True


def run_scheduled_backup(now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    moment = now or datetime.now()
    with SessionLocal() as db:
        config = settings_service.get_telegram_config(db)
        if not should_send(moment, config):
            return None
        try:
            return send_backup(db)
        except BusinessValidationError as exc:
            logger.warning("Backup Telegram gagal: %s", exc)
            return None


async def scheduler_loop() -> None:
    """Cek jadwal tiap menit selama aplikasi berjalan."""
    while True:
        try:
            await asyncio.sleep(60)
            await asyncio.to_thread(run_scheduled_backup)
        except asyncio.CancelledError:
            raise
        except Exception:  # jangan sampai loop berhenti karena satu kegagalan
            logger.exception("Penjadwal backup Telegram gagal dijalankan")


__all__ = [
    "backup_filename",
    "data_range",
    "run_scheduled_backup",
    "scheduler_loop",
    "send_backup",
    "should_send",
]
