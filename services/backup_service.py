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


def database_file_path() -> Path:
    from database.session import engine

    database = engine.url.database
    if not database or not str(database).endswith(".db"):
        raise BusinessValidationError("Backup hanya tersedia untuk basis data SQLite.")
    return Path(database)


def create_backup() -> Path:
    """Salin database memakai sqlite3 backup API (aman saat file aktif)."""
    source_path = database_file_path()
    if not source_path.exists():
        raise BusinessValidationError("Berkas basis data belum tersedia.")

    settings.backup_dir.mkdir(parents=True, exist_ok=True)
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
            "sebelum_restore_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".db"
        )
        shutil.copy2(target, safety)

    db_session.engine.dispose()
    shutil.move(str(temp_path), str(target))
    db_session.init_db()

    from database.seed import seed_defaults

    with db_session.SessionLocal() as db:
        seed_defaults(db)
