"""Cadangan & pemulihan basis data SQLite.

Ref: PRD NFR-DAT-02 / TC-20.
"""
from __future__ import annotations

import logging
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from config import settings
from services.errors import BusinessValidationError

logger = logging.getLogger(__name__)

REQUIRED_TABLES = {
    "customers",
    "vehicle_or_units",
    "stock_items",
    "harga_jasa",
    "service_records",
    "service_jobs",
    "service_parts",
}

# Kolom inti yang harus ada sejak versi pertama. Kolom hasil migrasi
# (mis. service_parts.harga_modal) tidak diwajibkan agar backup lama tetap sah.
REQUIRED_COLUMNS = {
    "customers": {"id", "nama", "nomor_hp", "alamat"},
    "vehicle_or_units": {"id", "customer_id", "unit_type", "label_radiator"},
    "stock_items": {"id", "kode", "nama", "harga_jual", "jumlah"},
    "harga_jasa": {"id", "nama", "harga_standar"},
    "service_records": {"id", "unit_id", "no_nota", "waktu_service"},
    "service_jobs": {"id", "service_record_id", "deskripsi"},
    "service_parts": {"id", "service_record_id", "nama_part"},
}

BACKUP_GLOB = "bengkel_radiator_*.db"
RESTORE_GLOB = "sebelum_restore_*.db"
MIGRATION_GLOB = "sebelum_migrasi_*.db"
RESTORE_BACKUP_KEEP = 3
MIGRATION_BACKUP_KEEP = 3
MIN_FREE_MARGIN_BYTES = 20 * 1024 * 1024

# Rahasia yang tidak boleh ikut ke berkas backup yang dapat dibagikan.
# Konfigurasi bisnis (bengkel.*) dan data transaksi tetap disalin apa adanya.
SENSITIVE_SETTING_KEYS = (
    "auth.pin_hash",
    "auth.pin_salt",
    "auth.pin_epoch",
    "auth.kasir_pin_hash",
    "auth.kasir_pin_salt",
    "auth.kasir_pin_epoch",
    "auth.session_secret",
    "telegram.bot_token",
    "telegram.chat_id",
)

# Rahasia yang diredaksi dari salinan pra-restore, tetapi harus dikembalikan
# bila restore gagal agar PIN dan sesi pengguna tidak ikut hilang.
AUTH_ROLLBACK_KEYS = (
    "auth.pin_hash",
    "auth.pin_salt",
    "auth.pin_iterations",
    "auth.pin_epoch",
    "auth.kasir_pin_hash",
    "auth.kasir_pin_salt",
    "auth.kasir_pin_iterations",
    "auth.kasir_pin_epoch",
    "auth.session_secret",
    "auth.failed_attempts",
    "auth.lock_until",
)


def _read_settings(path: Path, keys) -> dict:
    connection = sqlite3.connect(str(path))
    try:
        rows = dict(
            connection.execute("SELECT key, value FROM app_settings").fetchall()
        )
    finally:
        connection.close()
    return {key: rows[key] for key in keys if key in rows}


def _write_settings(path: Path, values: dict) -> None:
    if not values:
        return
    connection = sqlite3.connect(str(path))
    try:
        for key, value in values.items():
            connection.execute(
                "UPDATE app_settings SET value = ? WHERE key = ?", (value, key)
            )
        connection.commit()
    finally:
        connection.close()


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
    _prune(MIGRATION_GLOB, MIGRATION_BACKUP_KEEP)


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
    """Rahasia autentikasi & Telegram tidak boleh ikut di file backup.

    `secure_delete` menimpa isi halaman yang dihapus, lalu `VACUUM` menulis ulang
    file sehingga sisa nilai rahasia tidak tertinggal di free page.
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
            for key in SENSITIVE_SETTING_KEYS:
                connection.execute(
                    "UPDATE app_settings SET value = '' WHERE key = ?", (key,)
                )
            connection.commit()
            connection.execute("VACUUM")
    finally:
        connection.close()


def create_migration_backup(source_path: Path) -> Path:
    """Salin database sebelum migrasi skema ringan dijalankan."""
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    _ensure_free_space(source_path)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    destination = settings.backup_dir / f"sebelum_migrasi_{stamp}.db"

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


def _validate_backup(path: Path) -> None:
    """Pastikan berkas adalah SQLite utuh dengan tabel & kolom wajib."""
    try:
        check = sqlite3.connect(str(path))
        try:
            integrity = check.execute("PRAGMA integrity_check").fetchone()
            tables = {
                row[0]
                for row in check.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
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

            missing_columns = []
            for table, required in sorted(REQUIRED_COLUMNS.items()):
                columns = {
                    row[1]
                    for row in check.execute(f"PRAGMA table_info({table})").fetchall()
                }
                for column in sorted(required - columns):
                    missing_columns.append(f"{table}.{column}")
            if missing_columns:
                raise BusinessValidationError(
                    "Berkas backup tidak kompatibel: kolom "
                    + ", ".join(missing_columns)
                    + " tidak ditemukan."
                )
        finally:
            check.close()
    except BusinessValidationError:
        raise
    except sqlite3.DatabaseError as exc:
        raise BusinessValidationError(f"Database backup rusak: {exc}") from exc


def restore_backup(file_path: Path) -> None:
    """Pulihkan database dari berkas SQLite yang sudah dialirkan ke disk."""
    upload = Path(file_path)
    if not upload.exists():
        raise BusinessValidationError("Berkas backup tidak ditemukan.")
    if upload.stat().st_size == 0:
        raise BusinessValidationError("Berkas backup kosong.")
    with upload.open("rb") as handle:
        header = handle.read(16)
    if not header.startswith(b"SQLite format 3\x00"):
        raise BusinessValidationError("Berkas bukan database SQLite yang valid.")

    _validate_backup(upload)

    from database import session as db_session

    target = database_file_path()

    safety = None
    if target.exists():
        settings.backup_dir.mkdir(parents=True, exist_ok=True)
        safety = settings.backup_dir / (
            "sebelum_restore_"
            + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            + ".db"
        )
        shutil.copy2(target, safety)
        _redact_secrets(safety)

    # Siapkan berkas di folder database yang sama agar penggantian atomik.
    # Berkas unggahan juga diredaksi agar backup lama tanpa redaksi tidak
    # memasukkan kembali hash PIN/session secret ke database aktif.
    staged = target.with_name(target.name + ".restore.new")
    try:
        shutil.copy2(upload, staged)
        _redact_secrets(staged)
    except (OSError, sqlite3.DatabaseError) as exc:
        staged.unlink(missing_ok=True)
        raise BusinessValidationError(
            "Gagal menyiapkan berkas restore di folder database."
        ) from exc

    auth_snapshot = _read_settings(target, AUTH_ROLLBACK_KEYS)

    try:
        db_session.engine.dispose()
        os.replace(str(staged), str(target))
        db_session.init_db()
    except Exception as exc:
        staged.unlink(missing_ok=True)
        logger.exception("Restore gagal; mengembalikan database lama")
        if safety is None or not safety.exists():
            raise BusinessValidationError(
                "Restore gagal dan database baru tidak dapat dipakai. "
                "Periksa berkas backup lalu coba lagi."
            ) from exc

        rollback = target.with_name(target.name + ".restore.rollback")
        try:
            db_session.engine.dispose()
            shutil.copy2(safety, rollback)
            os.replace(str(rollback), str(target))
            db_session.init_db()
            # Salinan pengaman diredaksi, jadi kredensial pengguna dikembalikan
            # dari snapshot memori agar PIN/sesi tetap berlaku setelah gagal.
            _write_settings(target, auth_snapshot)
        except Exception:
            rollback.unlink(missing_ok=True)
            logger.exception(
                "Gagal mengembalikan database lama dari %s", safety
            )
            raise BusinessValidationError(
                "Restore gagal dan database lama gagal dipulihkan otomatis. "
                f"Pulihkan manual dari {safety.name} di folder backup."
            ) from exc

        raise BusinessValidationError(
            "Restore gagal. Database lama sudah dikembalikan; "
            "periksa berkas backup lalu coba lagi."
        ) from exc

    from database.seed import mark_seed_done
    from services import auth_service, settings_service

    # Restore harus menyalin kondisi backup apa adanya: tanpa seed ulang.
    with db_session.SessionLocal() as db:
        mark_seed_done(db)

        # Backup tidak membawa hash PIN/sesi; pastikan status terkunci yang
        # mungkin tersimpan di backup tidak membuat aplikasi tak dapat diakses.
        settings_service.set_setting(db, auth_service.FAILED_KEY, "0")
        settings_service.set_setting(db, auth_service.LOCK_UNTIL_KEY, "0")

        # Backup sengaja tidak menyimpan token; tandai agar UI meminta token ulang
        # bila konfigurasi aktif tidak lagi lengkap setelah restore.
        config = settings_service.get_telegram_config(db)
        settings_service.set_setting(
            db,
            "telegram.needs_reconfig",
            "" if config["bot_token"] and config["chat_id"] else "1",
        )
        db.commit()

    prune_backups()
