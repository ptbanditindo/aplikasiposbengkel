"""Cadangan & pemulihan basis data SQLite.

Ref: PRD NFR-DAT-02 / TC-20.
"""
from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from config import settings
from services.errors import BusinessValidationError

REQUIRED_TABLES = {
    "customers",
    "vehicle_or_units",
    "stock_items",
    "harga_jasa",
    "service_records",
    "service_jobs",
    "service_parts",
}

BACKUP_GLOB = "bengkel_radiator_*.db"
RESTORE_GLOB = "sebelum_restore_*.db"
RESTORE_BACKUP_KEEP = 3
MIN_FREE_MARGIN_BYTES = 20 * 1024 * 1024


def _prune(pattern: str, keep: int) -> None:
    files = sorted(
        settings.backup_dir.glob(pattern),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old in files[keep:]:
        old.unlink(missing_ok=True)


def prune_backups() -> None:
    """Simpan hanya backup terbaru sesuai retensi, termasuk salinan pra-restore."""
    _prune(BACKUP_GLOB, settings.backup_keep)
    _prune(RESTORE_GLOB, RESTORE_BACKUP_KEEP)


def _ensure_free_space(source: Path) -> None:
    needed = source.stat().st_size * 2 + MIN_FREE_MARGIN_BYTES
    free = shutil.disk_usage(str(settings.backup_dir)).free
    if free < needed:
        raise BusinessValidationError(
            "Ruang penyimpanan tidak cukup untuk membuat backup. "
            f"Butuh sekitar {needed // (1024 * 1024)} MB ruang kosong; "
            f"tersedia {free // (1024 * 1024)} MB. "
            "Hapus berkas lain lalu coba lagi."
        )


def database_file_path() -> Path:
    from database.session import engine

    database = engine.url.database
    if not database or not str(database).endswith(".db"):
        raise BusinessValidationError("Backup hanya tersedia untuk basis data SQLite.")
    return Path(database)


def _redact_secrets(path: Path) -> None:
    """Token bot tidak boleh ikut tersimpan di file backup yang dibagikan.

    `secure_delete` menimpa isi halaman yang dihapus, lalu `VACUUM` menulis ulang
    file sehingga sisa token tidak tertinggal di free page.
    """
    connection = sqlite3.connect(str(path))
    try:
        connection.execute("PRAGMA secure_delete = ON")
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "app_settings" in tables:
            connection.execute(
                "UPDATE app_settings SET value = '' WHERE key = 'telegram.bot_token'"
            )
            connection.commit()
            connection.execute("VACUUM")
    finally:
        connection.close()


def create_backup() -> Path:
    """Salin database memakai sqlite3 backup API (aman saat file aktif)."""
    source_path = database_file_path()
    if not source_path.exists():
        raise BusinessValidationError("Berkas basis data belum tersedia.")

    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    _ensure_free_space(source_path)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    destination = settings.backup_dir / f"bengkel_radiator_{stamp}.db"

    source = sqlite3.connect(str(source_path))
    try:
        target = sqlite3.connect(str(destination))
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()

    _redact_secrets(destination)
    prune_backups()
    return destination


def restore_backup(file_bytes: bytes) -> None:
    """Pulihkan database dari bytes SQLite yang diunggah (validasi header)."""
    if not file_bytes:
        raise BusinessValidationError("Berkas backup kosong.")
    if not file_bytes.startswith(b"SQLite format 3\x00"):
        raise BusinessValidationError("Berkas bukan database SQLite yang valid.")

    target = database_file_path()
    temp_path = target.with_suffix(".restore.tmp")
    temp_path.write_bytes(file_bytes)

    try:
        check = sqlite3.connect(str(temp_path))
        try:
            integrity = check.execute("PRAGMA integrity_check").fetchone()
            tables = {
                row[0]
                for row in check.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        finally:
            check.close()

        if not integrity or integrity[0] != "ok":
            raise BusinessValidationError(
                "Database backup rusak (integrity check gagal)."
            )
        missing = REQUIRED_TABLES - tables
        if missing:
            raise BusinessValidationError(
                "Berkas bukan backup BengkelPOS Radiator: tabel "
                + ", ".join(sorted(missing))
                + " tidak ditemukan."
            )
    except BusinessValidationError:
        temp_path.unlink(missing_ok=True)
        raise
    except sqlite3.DatabaseError as exc:
        temp_path.unlink(missing_ok=True)
        raise BusinessValidationError(f"Database backup rusak: {exc}") from exc

    from database import session as db_session

    if target.exists():
        settings.backup_dir.mkdir(parents=True, exist_ok=True)
        safety = settings.backup_dir / (
            "sebelum_restore_"
            + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            + ".db"
        )
        shutil.copy2(target, safety)
        _redact_secrets(safety)

    db_session.engine.dispose()
    shutil.move(str(temp_path), str(target))
    db_session.init_db()

    from database.seed import seed_defaults
    from services import settings_service

    with db_session.SessionLocal() as db:
        seed_defaults(db)

    # Backup sengaja tidak menyimpan token; tandai agar UI meminta token ulang
    # bila konfigurasi aktif tidak lagi lengkap setelah restore.
    with db_session.SessionLocal() as db:
        config = settings_service.get_telegram_config(db)
        settings_service.set_setting(
            db,
            "telegram.needs_reconfig",
            "" if config["bot_token"] and config["chat_id"] else "1",
        )
        db.commit()

    prune_backups()
