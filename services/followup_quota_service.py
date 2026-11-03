"""Kuota Follow up gratis: 20 kredit WhatsApp per `database_id`.

Counter disimpan di database toko sendiri (`followup.wa_used`) dan bersifat
monoton. Tidak ada sinkronisasi ke server; salinan/restore database membawa
counter yang sama. Premium tidak memotong kredit.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from database import session as db_session
from database.models import AppSetting
from database.session import store_session
from services import entitlement_service, settings_service, store_service
from services.errors import FeatureLockedError

FREE_LIMIT = 20
USED_KEY = "followup.wa_used"

QUOTA_LOCKED_MESSAGE = (
    "Kuota Follow up gratis (20 kredit WhatsApp) sudah habis. "
    "Data lama tetap dapat dibaca dan diekspor."
)


def ensure_database_id(db: Session) -> str:
    return store_service.ensure_database_id(db)


def _used(db: Session) -> int:
    raw = settings_service.get_setting(db, USED_KEY, "0")
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 0


def status(db: Session, database_id: Optional[str] = None) -> Dict[str, Any]:
    plan = entitlement_service.get_plan()
    premium = plan == "premium"
    database_id = database_id or ensure_database_id(db)
    used = _used(db)
    limit: Optional[int] = None if premium else FREE_LIMIT
    remaining: Optional[int] = None if premium else max(0, FREE_LIMIT - used)
    return {
        "plan": plan,
        "database_id": database_id,
        "batas": limit,
        "terpakai": used,
        "sisa": remaining,
        "terkunci": (not premium and used >= FREE_LIMIT),
    }


def ensure_available(db: Session) -> Dict[str, Any]:
    """Tolak aksi Follow up sebelum log/link dibuat saat kredit habis.

    Pemeriksaan memakai sesi singkat sendiri agar tidak membuka transaksi pada
    sesi request; beberapa layanan Follow up memakai `db.begin()`.
    """
    bind = db.get_bind()
    engine = getattr(bind, "engine", bind)
    fresh = store_session(engine)
    try:
        current = status(fresh)
    finally:
        fresh.close()
    if current["terkunci"]:
        raise FeatureLockedError(
            QUOTA_LOCKED_MESSAGE, code="followup_quota_habis"
        )
    return current


def consume(db: Session) -> Dict[str, Any]:
    """Potong satu kredit saat tautan wa.me akan dibuka.

    Premium tidak memotong. Gratis yang sudah habis ditolak sebelum link
    dibuat agar tautan tidak pernah terbuka tanpa kredit.
    """
    current = ensure_available(db)
    if current["plan"] == "premium":
        return current
    used = _increment_atomic(db)
    return {
        "plan": "free",
        "database_id": current["database_id"],
        "batas": FREE_LIMIT,
        "terpakai": used,
        "sisa": max(0, FREE_LIMIT - used),
        "terkunci": used >= FREE_LIMIT,
    }


def _increment_atomic(db: Session) -> int:
    """Naikkan counter di bawah kunci tulis agar dua link tidak memakai satu kredit."""
    bind = db.get_bind()
    engine = getattr(bind, "engine", bind)
    table = AppSetting.__tablename__
    fresh = store_session(engine)
    try:
        db_session.begin_immediate(fresh)
        fresh.execute(
            text(
                f"INSERT INTO {table} (key, value, updated_at) "
                "VALUES (:key, '0', CURRENT_TIMESTAMP) "
                "ON CONFLICT(key) DO NOTHING"
            ),
            {"key": USED_KEY},
        )
        updated = fresh.execute(
            text(
                f"UPDATE {table} SET value = CAST(value AS INTEGER) + 1, "
                "updated_at = CURRENT_TIMESTAMP "
                "WHERE key = :key AND CAST(value AS INTEGER) < :limit"
            ),
            {"key": USED_KEY, "limit": FREE_LIMIT},
        )
        used = fresh.execute(
            text(f"SELECT value FROM {table} WHERE key = :key"),
            {"key": USED_KEY},
        ).scalar_one()
        if updated.rowcount != 1 or int(used) > FREE_LIMIT:
            fresh.rollback()
            raise FeatureLockedError(
                QUOTA_LOCKED_MESSAGE, code="followup_quota_habis"
            )
        fresh.commit()
        return int(used)
    except Exception:
        fresh.rollback()
        raise
    finally:
        fresh.close()
