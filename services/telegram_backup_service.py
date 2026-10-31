"""Backup penuh database ke Telegram, manual maupun terjadwal.

Setiap pengiriman berisi satu file SQLite lengkap (seluruh data) dengan nama
rentang tanggal data, sehingga tidak ada file terpisah yang tumpang tindih.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import settings
from database.models import (
    AuditEvent,
    Customer,
    HargaJasa,
    ServiceJob,
    ServicePart,
    ServiceRecord,
    ServiceReturn,
    StockItem,
    StockMovement,
    VehicleOrUnit,
)
from database.session import SessionLocal
from services import backup_service, settings_service
from services.errors import BusinessValidationError
from services.maintenance import gate
from services.utils import sanitize_ascii

logger = logging.getLogger(__name__)

RETRY_MINUTES = 10
MAX_DOCUMENT_BYTES = 50 * 1024 * 1024  # batas kirim dokumen Bot API Telegram
PENDING_BACKUP_KEY = "telegram.pending_backup_path"
PENDING_BACKUP_DATE_KEY = "telegram.pending_backup_date"
PENDING_BACKUP_STAMP_KEY = "telegram.pending_backup_stamp"

# Tabel berisi data yang harus ikut snapshot. Jumlah baris mendeteksi data
# baru; `updated_at` mendeteksi perubahan pada baris yang sudah ada.
_STAMP_COUNT_MODELS = (
    Customer,
    VehicleOrUnit,
    StockItem,
    HargaJasa,
    ServiceRecord,
    ServiceJob,
    ServicePart,
    ServiceReturn,
    StockMovement,
    AuditEvent,
)
_STAMP_UPDATED_MODELS = (
    Customer,
    VehicleOrUnit,
    StockItem,
    HargaJasa,
    ServiceRecord,
)

# Satu backup pada satu waktu: endpoint terjadwal, pengiriman manual, dan
# penjadwal Python tidak boleh saling menimpa file atau mengirim dua kali.
BACKUP_LOCK = threading.RLock()


def _safe_backup_path(raw: str) -> Optional[Path]:
    if not raw:
        return None
    path = Path(raw)
    try:
        path.resolve().relative_to(settings.backup_dir.resolve())
    except (OSError, ValueError):
        return None
    return path


def _clear_pending_backup(db: Session) -> None:
    settings_service.set_setting(db, PENDING_BACKUP_KEY, "")
    settings_service.set_setting(db, PENDING_BACKUP_DATE_KEY, "")
    settings_service.set_setting(db, PENDING_BACKUP_STAMP_KEY, "")


def _data_stamp(db: Session) -> str:
    """Ringkasan isi data untuk mendeteksi snapshot yang sudah basi."""
    parts = []
    for model in _STAMP_COUNT_MODELS:
        count = db.scalar(select(func.count()).select_from(model)) or 0
        parts.append(f"{model.__tablename__}={count}")
    for model in _STAMP_UPDATED_MODELS:
        latest = db.scalar(select(func.max(model.updated_at)))
        parts.append(
            f"{model.__tablename__}@{latest.isoformat() if latest else ''}"
        )
    # Identitas bengkel ikut ke dalam snapshot, jadi perubahan nama/tagline
    # juga harus membuat snapshot baru.
    info = settings_service.get_bengkel_info(db)
    parts.append("bengkel=" + "|".join(f"{k}:{info[k]}" for k in sorted(info)))
    return "|".join(parts)


def _pending_backup(db: Session) -> Optional[Path]:
    """Pakai ulang snapshot hari ini hanya bila isinya masih sama dengan data.

    Snapshot lama tetap tersimpan di folder backup; yang dibatalkan hanya
    pemakaian ulang untuk pengiriman agar nota baru tidak tertinggal.
    """
    raw = settings_service.get_setting(db, PENDING_BACKUP_KEY)
    if not raw:
        return None

    path = _safe_backup_path(raw)
    stored_date = settings_service.get_setting(db, PENDING_BACKUP_DATE_KEY)
    stored_stamp = settings_service.get_setting(db, PENDING_BACKUP_STAMP_KEY)
    if (
        path is None
        or stored_date != date.today().isoformat()
        or not path.exists()
        or stored_stamp != _data_stamp(db)
    ):
        _clear_pending_backup(db)
        db.commit()
        return None
    return path


def _create_snapshot(db: Session) -> Path:
    """Buat snapshot baru dan catat stempel data saat snapshot diambil."""
    stamp = _data_stamp(db)
    path = backup_service.create_backup()
    settings_service.set_setting(db, PENDING_BACKUP_KEY, str(path))
    settings_service.set_setting(
        db, PENDING_BACKUP_DATE_KEY, date.today().isoformat()
    )
    settings_service.set_setting(db, PENDING_BACKUP_STAMP_KEY, stamp)
    db.commit()
    return path


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
    """Kirim snapshot database lengkap ke Telegram milik owner.

    Tombol "Backup sekarang" selalu mengirim data sampai detik itu: snapshot
    lama hanya dipakai bila isinya masih identik, termasuk identitas bengkel.
    """
    with BACKUP_LOCK:
        config = settings_service.get_telegram_config(db)
        if not config["bot_token"] or not config["chat_id"]:
            raise BusinessValidationError(
                "Bot token dan chat ID Telegram belum diatur di menu Pengaturan."
            )
        return _send_snapshot(db, _pending_backup(db) or _create_snapshot(db))


def run_manual_backup(db: Session) -> Dict[str, Any]:
    """Simpan snapshot terkini, lalu kirim ke Telegram bila sudah diatur.

    Tombol "Kirim backup sekarang" selalu menyimpan salinan lokal terlebih
    dahulu. Kegagalan Telegram dilaporkan pada hasil, tetapi file lokal tetap
    ada dan bisa disalin ke folder pilihan pengguna.
    """
    with BACKUP_LOCK:
        config = settings_service.get_telegram_config(db)
        ready = bool(config["bot_token"] and config["chat_id"])
        now = datetime.now()
        try:
            path = _pending_backup(db) or _create_snapshot(db)
        except (BusinessValidationError, OSError) as exc:
            message = str(exc)
            _record_backup_status(db, now, "failed", error=message, touch_local=False)
            raise

        jumlah_nota = db.scalar(select(func.count()).select_from(ServiceRecord)) or 0
        if not ready:
            _record_backup_status(db, now, "ok", filename=path.name)
            return {
                "status": "ok",
                "local_saved": True,
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "created_at": now.isoformat(timespec="seconds"),
                "telegram_ready": False,
                "telegram_sent": False,
                "telegram_error": None,
                "jumlah_nota": jumlah_nota,
                "message": "Backup lokal tersimpan. Telegram belum diatur.",
            }

        try:
            _send_snapshot(db, path)
        except BusinessValidationError as exc:
            message = str(exc)
            _record_backup_status(db, now, "failed", error=message, filename=path.name)
            return {
                "status": "failed",
                "local_saved": True,
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "created_at": now.isoformat(timespec="seconds"),
                "telegram_ready": True,
                "telegram_sent": False,
                "telegram_error": message,
                "jumlah_nota": jumlah_nota,
                "message": "Backup lokal tersimpan; pengiriman Telegram gagal.",
            }

        _record_backup_status(db, now, "ok", filename=path.name, telegram_sent=True)
        return {
            "status": "ok",
            "local_saved": True,
            "filename": path.name,
            "size_bytes": path.stat().st_size,
            "created_at": now.isoformat(timespec="seconds"),
            "telegram_ready": True,
            "telegram_sent": True,
            "telegram_error": None,
            "jumlah_nota": jumlah_nota,
            "message": "Backup tersimpan dan terkirim ke Telegram.",
        }


def _send_snapshot(db: Session, backup_path: Path) -> Dict[str, Any]:
    config = settings_service.get_telegram_config(db)
    if not config["bot_token"] or not config["chat_id"]:
        raise BusinessValidationError(
            "Bot token dan chat ID Telegram belum diatur di menu Pengaturan."
        )

    start, end = data_range(db)
    if backup_path.stat().st_size > MAX_DOCUMENT_BYTES:
        # Snapshot lokal tetap disimpan; hanya pengiriman Telegram yang batal.
        _clear_pending_backup(db)
        db.commit()
        raise BusinessValidationError(
            "Backup lokal tersimpan, tetapi ukuran melebihi 50 MB (batas kirim "
            "bot Telegram). Unduh backup manual dari menu Pengaturan."
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
    # Snapshot lokal tidak dihapus setelah terkirim: backup lokal adalah
    # artefak utama, sedangkan Telegram hanya pengiriman tambahan.
    _clear_pending_backup(db)
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
        "backup_path": backup_path,
    }


def _same_day_backup(db: Session, moment: datetime) -> Optional[Path]:
    """Cari snapshot lokal hari ini agar percobaan ulang tidak membuat duplikat."""
    pending = _pending_backup(db)
    if pending is not None:
        return pending

    stored_name = settings_service.get_setting(
        db, settings_service.BACKUP_LAST_FILENAME_KEY
    )
    path = _safe_backup_path(stored_name)
    if path is None and stored_name:
        # Backend menyimpan nama berkas (bukan path) untuk ditampilkan di UI.
        candidate = settings.backup_dir / Path(stored_name).name
        if candidate.exists():
            path = candidate
    last_at = settings_service.get_setting(
        db, settings_service.BACKUP_LAST_AT_KEY
    )
    if (
        path is not None
        and path.exists()
        and last_at[:10] == moment.date().isoformat()
    ):
        return path
    return None


def _record_backup_status(
    db: Session,
    moment: datetime,
    status: str,
    *,
    error: str = "",
    filename: str = "",
    touch_local: bool = True,
    telegram_sent: bool = False,
) -> None:
    stamp = moment.isoformat(timespec="seconds")
    if touch_local:
        settings_service.set_setting(
            db, settings_service.BACKUP_LAST_AT_KEY, stamp
        )
        settings_service.set_setting(
            db, settings_service.BACKUP_LAST_FILENAME_KEY, filename
        )
    settings_service.set_setting(db, settings_service.BACKUP_LAST_STATUS_KEY, status)
    settings_service.set_setting(
        db, settings_service.BACKUP_LAST_ERROR_KEY, error[:300]
    )
    if telegram_sent:
        settings_service.set_setting(
            db, settings_service.BACKUP_LAST_TELEGRAM_KEY, stamp
        )
    db.commit()


def _scheduled_response(
    status: str,
    moment: datetime,
    *,
    path: Optional[Path] = None,
    local_saved: bool = False,
    telegram_enabled: bool = False,
    telegram_sent: bool = False,
    telegram_error: Optional[str] = None,
    message: str = "",
) -> Dict[str, Any]:
    size = path.stat().st_size if path is not None and path.exists() else 0
    return {
        "status": status,
        "local_saved": local_saved,
        "filename": path.name if size else None,
        "size_bytes": size,
        "created_at": moment.isoformat(timespec="seconds"),
        "telegram_enabled": telegram_enabled,
        "telegram_sent": telegram_sent,
        "telegram_error": telegram_error,
        "message": message,
    }


def run_scheduled_backup_now(
    db: Session, now: Optional[datetime] = None
) -> Dict[str, Any]:
    """Satu putaran backup terjadwal yang aman dipanggil WorkManager.

    Urutan wajib: simpan snapshot lokal dulu, baru coba kirim ke Telegram.
    Kegagalan Telegram tidak menghapus snapshot; percobaan ulang memakai file
    yang sama hanya selama belum ada data baru, sehingga tidak ada berkas
    ganda sekaligus tidak ada nota yang tertinggal.
    """
    moment = now or datetime.now()
    if not BACKUP_LOCK.acquire(blocking=False):
        return _scheduled_response(
            "busy",
            moment,
            message="Backup lain sedang berjalan; coba lagi nanti.",
        )

    try:
        config = settings_service.get_telegram_config(db)
        telegram_enabled = bool(config.get("enabled"))
        telegram_ready = bool(
            telegram_enabled and config.get("bot_token") and config.get("chat_id")
        )

        last_sent = _parse_datetime(config.get("last_sent_at"))
        sent_today = bool(
            telegram_ready
            and last_sent is not None
            and last_sent.date() == moment.date()
        )

        if sent_today or not telegram_ready:
            path = _same_day_backup(db, moment)
            if path is None:
                try:
                    path = _create_snapshot(db)
                except (BusinessValidationError, OSError) as exc:
                    message = str(exc)
                    _record_backup_status(
                        db, moment, "failed", error=message, touch_local=False
                    )
                    return _scheduled_response(
                        "failed",
                        moment,
                        telegram_enabled=telegram_enabled,
                        telegram_error=message if telegram_ready else None,
                        message=message,
                    )
            _record_backup_status(
                db, moment, "ok", filename=path.name, telegram_sent=sent_today
            )
            return _scheduled_response(
                "ok",
                moment,
                path=path,
                local_saved=True,
                telegram_enabled=telegram_enabled,
                telegram_sent=sent_today,
                message=(
                    "Backup lokal tersimpan; hari ini sudah dikirim ke Telegram."
                    if sent_today
                    else "Backup lokal tersimpan."
                ),
            )

        # Perlu kirim sekarang: snapshot wajib memuat seluruh data terkini.
        snapshot = _pending_backup(db)
        if snapshot is None:
            try:
                snapshot = _create_snapshot(db)
            except (BusinessValidationError, OSError) as exc:
                message = str(exc)
                _record_backup_status(
                    db, moment, "failed", error=message, touch_local=False
                )
                return _scheduled_response(
                    "failed",
                    moment,
                    telegram_enabled=telegram_enabled,
                    telegram_error=message,
                    message=message,
                )

        try:
            _send_snapshot(db, snapshot)
        except BusinessValidationError as exc:
            message = str(exc)
            _record_backup_status(
                db, moment, "failed", error=message, filename=snapshot.name
            )
            return _scheduled_response(
                "failed",
                moment,
                path=snapshot,
                local_saved=True,
                telegram_enabled=True,
                telegram_error=message,
                message="Backup lokal tersimpan; pengiriman Telegram gagal.",
            )

        _record_backup_status(
            db, moment, "ok", filename=snapshot.name, telegram_sent=True
        )
        return _scheduled_response(
            "ok",
            moment,
            path=snapshot,
            local_saved=True,
            telegram_enabled=True,
            telegram_sent=True,
            message="Backup tersimpan dan terkirim ke Telegram.",
        )
    finally:
        BACKUP_LOCK.release()


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


def local_backup_due(now: datetime, config: Dict[str, Any], last_local_at: Any) -> bool:
    """True bila snapshot lokal harian belum dibuat setelah jam jadwal.

    Jadwal lokal memakai jam yang sama dengan pengaturan Telegram, tetapi tidak
    bergantung pada status aktif Telegram.
    """
    target = _parse_jam(config.get("jam") or "21:00")
    if target is None:
        return False
    last = _parse_datetime(last_local_at)
    return now.time() >= target and (last is None or last.date() < now.date())


def run_scheduled_backup(now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    moment = now or datetime.now()
    with SessionLocal() as db:
        config = settings_service.get_telegram_config(db)
        last_local_at = settings_service.get_setting(
            db, settings_service.BACKUP_LAST_AT_KEY
        )
        # Backup lokal selalu terjadwal; pengiriman Telegram hanya tambahan.
        if not (
            local_backup_due(moment, config, last_local_at)
            or should_send(moment, config)
        ):
            return None
        try:
            return run_scheduled_backup_now(db, moment)
        except BusinessValidationError as exc:
            logger.warning("Backup terjadwal gagal: %s", exc)
            return None


async def scheduler_loop() -> None:
    """Cek jadwal tiap menit selama aplikasi berjalan."""
    while True:
        try:
            await asyncio.sleep(60)
            # Ikut mode maintenance: backup tidak boleh menulis saat restore.
            if not gate.try_enter():
                continue
            try:
                await asyncio.to_thread(run_scheduled_backup)
            finally:
                gate.leave()
        except asyncio.CancelledError:
            raise
        except Exception:  # jangan sampai loop berhenti karena satu kegagalan
            logger.exception("Penjadwal backup Telegram gagal dijalankan")


__all__ = [
    "BACKUP_LOCK",
    "backup_filename",
    "data_range",
    "local_backup_due",
    "run_scheduled_backup",
    "run_scheduled_backup_now",
    "scheduler_loop",
    "send_backup",
    "should_send",
]
