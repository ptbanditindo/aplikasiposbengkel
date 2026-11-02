"""Kuota Follow up gratis: 20 kredit WhatsApp per `database_id`.

Counter disimpan di database toko sendiri (`followup.wa_used`) dan bersifat
monoton. Tidak ada sinkronisasi ke server; salinan/restore database membawa
counter yang sama. Premium tidak memotong kredit.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

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
    used = current["terpakai"]
    settings_service.set_setting(db, USED_KEY, str(used + 1))
    db.commit()
    return {
        **current,
        "terpakai": used + 1,
        "sisa": max(0, FREE_LIMIT - (used + 1)),
        "terkunci": used + 1 >= FREE_LIMIT,
    }
