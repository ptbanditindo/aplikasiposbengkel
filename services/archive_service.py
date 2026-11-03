"""Arsip semua toko (ZIP) dengan manifest, checksum, dan restore all-or-nothing.

Arsip memuat database setiap toko apa adanya setelah rahasia autentikasi
diredaksi. Pemulihan menulis ke berkas bertahap lalu mengganti seluruh database
hanya bila semua berkas lolos pemeriksaan; bila gagal, salinan pengaman
dikembalikan (K-10/K-11).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import APP_VERSION, settings
from database import migrations as schema_migrations
from database import session as db_session
from database import store_registry
from services import backup_service, entitlement_service, license_service
from services.errors import BusinessValidationError, FeatureLockedError

ARCHIVE_FORMAT = 1
ARCHIVE_GLOB = "bengkel_radiator_semua_*"
ARCHIVE_KEEP = 3
MANIFEST_NAME = "manifest.json"
STORE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

PRESERVED_SETTING_KEYS = tuple(backup_service.AUTH_ROLLBACK_KEYS) + (
    "telegram.bot_token",
    "telegram.chat_id",
    "telegram.needs_reconfig",
)


def _require_premium() -> None:
    if not entitlement_service.is_premium():
        raise FeatureLockedError(
            entitlement_service.LOCKED_MESSAGE, code="premium_locked"
        )


def _copy_database(source: Path, destination: Path) -> None:
    connection = sqlite3.connect(str(source))
    try:
        target = sqlite3.connect(str(destination))
        try:
            connection.backup(target)
        finally:
            target.close()
    finally:
        connection.close()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prune_archives() -> None:
    files = sorted(
        settings.backup_dir.glob(ARCHIVE_GLOB),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old in files[ARCHIVE_KEEP:]:
        old.unlink(missing_ok=True)


def list_archives() -> List[Dict[str, Any]]:
    if not settings.backup_dir.exists():
        return []
    rows = []
    for path in sorted(
        settings.backup_dir.glob(ARCHIVE_GLOB),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ):
        rows.append(
            {
                "filename": path.name,
                "size": path.stat().st_size,
                "created_at": datetime.fromtimestamp(
                    path.stat().st_mtime
                ).isoformat(timespec="seconds"),
            }
        )
    return rows


def create_archive() -> Path:
    """Buat satu ZIP berisi database seluruh toko yang tersedia."""
    _require_premium()
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    destination = settings.backup_dir / f"bengkel_radiator_semua_{stamp}.zip"
    staging = Path(tempfile.mkdtemp(prefix=".arsip_", dir=str(settings.backup_dir)))

    owner_id = ""
    with db_session.SessionLocal() as db:
        owner = license_service.get_owner(db)
        owner_id = owner.owner_id if owner else ""

    entries: List[Dict[str, Any]] = []
    primary_path = db_session.main_database_path()
    try:
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
            for index, entry in enumerate(
                store_registry.list_stores(include_missing=True)
            ):
                try:
                    source = store_registry.resolve_database_path(entry)
                except RuntimeError:
                    continue
                if not source.exists():
                    continue
                is_primary = entry["store_id"] == store_registry.PRIMARY_STORE_ID
                if is_primary and source.resolve() != primary_path.resolve():
                    source = primary_path
                copy = staging / f"store_{index}.db"
                _copy_database(source, copy)
                backup_service._redact_secrets(copy)

                store_settings = backup_service._read_settings(
                    copy, ("store.database_id",)
                )
                database_id = (
                    store_settings.get("store.database_id")
                    or entry.get("database_id")
                    or entry["store_id"]
                )
                filename = f"stores/{entry['store_id']}.db"
                archive.write(copy, filename)
                entries.append(
                    {
                        "store_id": entry["store_id"],
                        "database_id": database_id,
                        "nama": entry.get("nama") or "",
                        "alamat": entry.get("alamat") or "",
                        "primary": is_primary,
                        "filename": filename,
                        "sha256": _sha256(copy),
                        "size": copy.stat().st_size,
                    }
                )

        if not entries:
            raise BusinessValidationError(
                "Tidak ada database toko yang dapat diarsipkan."
            )
        manifest = {
            "format": ARCHIVE_FORMAT,
            "app_version": APP_VERSION,
            "schema_version": schema_migrations.SCHEMA_VERSION,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "owner_id": owner_id,
            "plan": entitlement_service.get_plan(),
            "active_store_id": store_registry.active_store()["store_id"],
            "stores": entries,
        }
        with zipfile.ZipFile(destination, "a", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                MANIFEST_NAME,
                json.dumps(manifest, ensure_ascii=False, indent=2),
            )
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    prune_archives()
    return destination


def read_manifest(archive_path: Path) -> Dict[str, Any]:
    path = Path(archive_path)
    if not path.exists() or path.stat().st_size == 0:
        raise BusinessValidationError("Berkas arsip tidak ditemukan atau kosong.")
    if not zipfile.is_zipfile(path):
        raise BusinessValidationError("Berkas arsip bukan ZIP yang valid.")
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        if MANIFEST_NAME not in names:
            raise BusinessValidationError("Arsip tidak memiliki manifest.")
        try:
            manifest = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise BusinessValidationError("Manifest arsip tidak dapat dibaca.") from exc
    if not isinstance(manifest, dict) or manifest.get("format") != ARCHIVE_FORMAT:
        raise BusinessValidationError("Versi arsip tidak didukung.")
    stores = manifest.get("stores")
    if not isinstance(stores, list) or not stores:
        raise BusinessValidationError("Arsip tidak memuat toko.")
    for entry in stores:
        store_id = str(entry.get("store_id") or "")
        filename = str(entry.get("filename") or "")
        if not STORE_NAME_PATTERN.match(store_id):
            raise BusinessValidationError("Nama toko pada manifest tidak valid.")
        if not filename.startswith("stores/") or ".." in filename.split("/"):
            raise BusinessValidationError("Berkas toko pada manifest tidak valid.")
        if not str(entry.get("sha256") or ""):
            raise BusinessValidationError("Checksum toko pada manifest tidak ada.")
    return manifest


def _target_path(entry: Dict[str, Any]) -> Path:
    if entry.get("primary"):
        return db_session.main_database_path()
    database_id = str(entry.get("database_id") or entry.get("store_id") or "")
    if not STORE_NAME_PATTERN.match(database_id):
        raise BusinessValidationError("Nama database toko tidak valid.")
    return store_registry.stores_dir() / f"{database_id}.db"


def _safety_copy(source: Path, suffix: str, staging: Path) -> Optional[Path]:
    if not source.exists():
        return None
    destination = staging / f"safety_{suffix}.db"
    _copy_database(source, destination)
    return destination


def restore_archive(archive_path: Path) -> Dict[str, Any]:
    """Pulihkan seluruh toko dari arsip; gagal di tengah = kembali ke semula."""
    _require_premium()
    manifest = read_manifest(Path(archive_path))
    staging = Path(
        tempfile.mkdtemp(prefix=".restore_arsip_", dir=str(settings.backup_dir))
    )
    original_registry = store_registry.registry_path().read_bytes()
    targets: List[tuple[Path, Path, Dict[str, Any]]] = []
    safety: Dict[str, Optional[Path]] = {}
    primary_in_archive = False
    try:
        with zipfile.ZipFile(Path(archive_path)) as archive:
            for entry in manifest["stores"]:
                filename = str(entry["filename"])
                extracted = staging / f"in_{len(targets)}.db"
                with archive.open(filename) as source, extracted.open("wb") as target:
                    shutil.copyfileobj(source, target)
                if _sha256(extracted) != str(entry["sha256"]):
                    raise BusinessValidationError(
                        f"Checksum arsip toko {entry['store_id']} tidak cocok."
                    )
                backup_service._validate_backup(extracted)
                target_path = _target_path(entry)
                primary_in_archive = primary_in_archive or bool(entry.get("primary"))
                targets.append((extracted, target_path, entry))
                safety[str(target_path)] = _safety_copy(
                    target_path, str(len(targets)), staging
                )

        preserved: Dict[str, str] = {}
        if primary_in_archive:
            primary = db_session.main_database_path()
            if primary.exists():
                preserved = backup_service._read_settings(
                    primary, PRESERVED_SETTING_KEYS
                )

        db_session.dispose_store_engines()
        db_session.engine.dispose()
        for _, target_path, _ in targets:
            target_path.parent.mkdir(parents=True, exist_ok=True)
        for extracted, target_path, _ in targets:
            shutil.copy2(extracted, target_path)

        registry_entries = [
            {
                "store_id": entry["store_id"],
                "database_id": entry.get("database_id") or entry["store_id"],
                "nama": entry.get("nama") or "",
                "alamat": entry.get("alamat") or "",
                "database_path": str(target_path),
            }
            for _, target_path, entry in targets
        ]
        store_registry.upsert_stores(
            registry_entries,
            active_store_id=str(manifest.get("active_store_id") or ""),
        )

        db_session.init_db()
        for _, target_path, entry in targets:
            if entry.get("primary"):
                continue
            bind = db_session.build_engine(f"sqlite:///{target_path.as_posix()}")
            try:
                db_session.init_db(bind=bind)
            finally:
                bind.dispose()

        if preserved:
            backup_service._write_settings(
                db_session.main_database_path(), preserved
            )
    except Exception:
        db_session.dispose_store_engines()
        db_session.engine.dispose()
        for target, copy in safety.items():
            if copy is None:
                Path(target).unlink(missing_ok=True)
            elif copy.exists():
                shutil.copy2(copy, target)
        try:
            store_registry.registry_path().write_text(
                original_registry.decode("utf-8"), encoding="utf-8"
            )
            store_registry.reset_cache()
        except OSError:
            pass
        db_session.init_db()
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        prune_archives()

    restored = [
        {
            "store_id": entry["store_id"],
            "database_id": entry.get("database_id") or "",
            "nama": entry.get("nama") or "",
        }
        for _, _, entry in targets
    ]
    return {
        "status": "ok",
        "stores": restored,
        "active_store_id": store_registry.active_store()["store_id"],
        "archive_created_at": manifest.get("created_at"),
    }
