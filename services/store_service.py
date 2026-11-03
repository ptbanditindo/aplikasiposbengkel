"""Operasi toko: database kosong per toko, identitas, dan ganti toko aktif."""
from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from sqlalchemy.orm import Session

from database import session as db_session
from database import store_registry
from database.seed import seed_defaults
from services import entitlement_service, settings_service
from services.errors import (
    BusinessValidationError,
    ConflictError,
    FeatureLockedError,
    NotFoundError,
)
from services.utils import clean_text

DATABASE_ID_KEY = "store.database_id"


def ensure_database_id(
    db: Session, store_id: Optional[str] = None
) -> str:
    value = settings_service.get_setting(db, DATABASE_ID_KEY)
    if not value:
        value = store_registry.new_ulid()
        settings_service.set_setting(db, DATABASE_ID_KEY, value)
        db.commit()
    entry = (
        store_registry.get_store(store_id)
        if store_id is not None
        else store_registry.active_store()
    )
    if entry is None:
        raise RuntimeError("Toko tidak ditemukan saat menyiapkan database_id.")
    if entry.get("database_id") != value:
        store_registry.update_store(entry["store_id"], database_id=value)
    return value


def sync_registry_identity(db: Session, store_id: Optional[str] = None) -> None:
    """Samakan nama/alamat registry dengan identitas toko yang tersimpan."""
    entry = (
        store_registry.get_store(store_id)
        if store_id is not None
        else store_registry.active_store()
    )
    if entry is None:
        return
    info = settings_service.get_bengkel_info(db)
    store_registry.update_store(
        entry["store_id"], nama=info["nama"], alamat=info["alamat"]
    )


def _public(entry: Dict[str, Any], active_id: str) -> Dict[str, Any]:
    try:
        tersedia = store_registry.resolve_database_path(entry).exists()
    except RuntimeError:
        tersedia = False
    return {
        "store_id": entry["store_id"],
        "database_id": entry.get("database_id") or "",
        "nama": entry.get("nama") or "",
        "alamat": entry.get("alamat") or "",
        "aktif": entry["store_id"] == active_id,
        "tersedia": tersedia,
    }


def list_stores(
    allowed_store_ids: Optional[Sequence[str]] = None
) -> Dict[str, Any]:
    data = store_registry.ensure_registry()
    active_id = store_registry.active_store()["store_id"]
    allowed = set(allowed_store_ids) if allowed_store_ids is not None else None
    rows = [
        _public(entry, active_id)
        for entry in store_registry.list_stores(include_missing=True)
        if allowed is None or entry["store_id"] in allowed
    ]
    return {
        "aktif": active_id if allowed is None or active_id in allowed else "",
        "toko": rows,
        "entitlement": entitlement_service.info(),
    }


def create_store(nama: str, alamat: Optional[str]) -> Dict[str, Any]:
    if not entitlement_service.is_premium():
        raise FeatureLockedError(
            entitlement_service.LOCKED_MESSAGE, code="premium_locked"
        )

    cleaned_nama = clean_text(nama, max_length=255)
    if len(cleaned_nama) < 2:
        raise BusinessValidationError("Nama toko minimal 2 karakter.")
    cleaned_alamat = clean_text(alamat, max_length=500) if alamat else ""

    database_id = store_registry.new_ulid()
    target = store_registry.stores_dir() / f"{database_id}.db"
    target.parent.mkdir(parents=True, exist_ok=True)
    bind = db_session.build_engine(f"sqlite:///{target.as_posix()}")
    try:
        db_session.init_db(bind=bind)
        with db_session.store_session(bind) as db:
            seed_defaults(db)
            settings_service.set_setting(db, "bengkel.nama", cleaned_nama)
            settings_service.set_setting(db, "bengkel.alamat", cleaned_alamat)
            settings_service.set_setting(db, DATABASE_ID_KEY, database_id)
            db.commit()
    except Exception:
        bind.dispose()
        target.unlink(missing_ok=True)
        raise
    bind.dispose()

    entry = store_registry.add_store(
        database_id=database_id,
        nama=cleaned_nama,
        alamat=cleaned_alamat,
        database_path=str(target),
    )
    return _public(entry, store_registry.active_store()["store_id"])


def activate_store(store_id: str) -> Dict[str, Any]:
    previous = store_registry.active_store()["store_id"]
    try:
        entry = store_registry.set_active_store(store_id)
    except KeyError as exc:
        raise NotFoundError("Toko tidak ditemukan.") from exc
    except FileNotFoundError as exc:
        raise ConflictError(
            "Berkas database toko tidak tersedia di perangkat ini."
        ) from exc

    try:
        db_session.init_db(bind=db_session.active_engine())
    except Exception:
        store_registry.set_active_store(previous)
        raise

    with db_session.store_session(db_session.active_engine()) as db:
        try:
            ensure_database_id(db, store_id=store_id)
            sync_registry_identity(db, store_id=store_id)
        except Exception:
            store_registry.set_active_store(previous)
            raise
    return _public(store_registry.get_store(store_id) or entry, store_id)


def ensure_startup_state() -> None:
    """Siapkan skema, seed, database_id, dan metadata registry saat mulai."""
    db_session.init_db()
    with db_session.SessionLocal() as db:
        seed_defaults(db)
        ensure_database_id(db, store_id=store_registry.PRIMARY_STORE_ID)
        sync_registry_identity(db, store_id=store_registry.PRIMARY_STORE_ID)

    entry = store_registry.active_store()
    if entry["store_id"] != store_registry.PRIMARY_STORE_ID:
        bind = db_session.active_engine()
        db_session.init_db(bind=bind)
        with db_session.store_session(bind) as db:
            seed_defaults(db)
            ensure_database_id(db, store_id=entry["store_id"])
            sync_registry_identity(db, store_id=entry["store_id"])
