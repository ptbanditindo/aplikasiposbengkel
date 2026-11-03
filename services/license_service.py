"""Lisensi premium, ID owner, kunci owner, dan hitung mundur offline (K-06/K-11/K-22)."""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from database import store_registry
from database.models import (
    Device,
    DeviceKeyWrap,
    DeviceStore,
    EmployeeAccount,
    HubAudit,
    License,
    LoginGuard,
    OutboxItem,
    OwnerIdentity,
    PermissionSnapshot,
    RelayAck,
    RelayEnvelope,
    RelaySnapshot,
    StoreHub,
    StoreKey,
    SyncConflict,
    SyncPeerState,
    utcnow,
)
from services import premium_crypto, settings_service
from services.errors import BusinessValidationError, ConflictError, NotFoundError

LICENSE_ID = 1
OWNER_ID_LENGTH = 8
OWNER_ID_ALPHABET = "23456789abcdefghijkmnpqrstuvwxyz"
DEFAULT_DEVICE_LIMIT = 2
DEFAULT_PERIOD_DAYS = 30
MAX_PERIOD_DAYS = 366
CLOCK_TOLERANCE = timedelta(minutes=5)
RECOVERY_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
RECOVERY_CODE_LENGTH = 16


def _now() -> datetime:
    return utcnow()


def _new_owner_id(db: Session) -> str:
    for _ in range(50):
        candidate = "".join(
            secrets.choice(OWNER_ID_ALPHABET) for _ in range(OWNER_ID_LENGTH)
        )
        exists = db.execute(
            select(OwnerIdentity.id).where(OwnerIdentity.owner_id == candidate)
        ).first()
        if exists is None:
            return candidate
    raise RuntimeError("Gagal membuat ID owner unik.")


def _new_recovery_code() -> str:
    return "".join(
        secrets.choice(RECOVERY_CODE_ALPHABET) for _ in range(RECOVERY_CODE_LENGTH)
    )


def _local_secret(db: Session) -> str:
    raw = settings_service.get_setting(db, "auth.session_secret")
    if not raw:
        raw = secrets.token_hex(32)
        settings_service.set_setting(db, "auth.session_secret", raw)
        db.commit()
    return raw


def _local_key(db: Session) -> bytes:
    return hashlib.sha256(_local_secret(db).encode("utf-8")).digest()


def _seal_local(db: Session, data: bytes) -> Dict[str, str]:
    return premium_crypto.encrypt_with_password(_local_secret(db), data)


def _open_local(db: Session, blob: Dict[str, str]) -> bytes:
    return premium_crypto.decrypt_with_password(_local_secret(db), blob)


def get_owner(db: Session) -> Optional[OwnerIdentity]:
    return db.get(OwnerIdentity, 1)


def ensure_owner(db: Session) -> tuple[OwnerIdentity, Optional[str]]:
    """Buat identitas owner sekali; kode pemulihan hanya dikembalikan sekali."""
    existing = get_owner(db)
    if existing is not None:
        return existing, None

    owner_id = _new_owner_id(db)
    private_b64, public_b64 = premium_crypto.generate_signing_keypair()
    private_raw = premium_crypto.b64d(private_b64)
    sealed = _seal_local(db, private_raw)
    recovery_code = _new_recovery_code()
    recovery_blob = premium_crypto.encrypt_with_password(recovery_code, private_raw)
    recovery_salt = secrets.token_hex(16)
    recovery_hash = hashlib.pbkdf2_hmac(
        "sha256", recovery_code.encode("utf-8"), bytes.fromhex(recovery_salt), 120_000
    ).hex()

    owner = OwnerIdentity(
        id=1,
        owner_id=owner_id,
        public_key=public_b64,
        private_key_encrypted=json.dumps(sealed),
        private_key_salt=sealed["salt"],
        recovery_blob=json.dumps(recovery_blob),
        recovery_salt=recovery_salt,
        recovery_code_hash=recovery_hash,
    )
    db.add(owner)
    db.commit()
    return owner, recovery_code


def owner_public_key(db: Session) -> str:
    owner = get_owner(db)
    if owner is None:
        raise NotFoundError("ID owner belum diterbitkan. Aktifkan premium dahulu.")
    return owner.public_key


def owner_private_key(db: Session) -> str:
    owner = get_owner(db)
    if owner is None:
        raise NotFoundError("ID owner belum diterbitkan. Aktifkan premium dahulu.")
    raw = _open_local(db, json.loads(owner.private_key_encrypted))
    return premium_crypto.b64e(raw)


def sign_as_owner(db: Session, payload: Any) -> str:
    return premium_crypto.sign(
        owner_private_key(db), premium_crypto.canonical_json(payload)
    )


def verify_recovery_code(db: Session, code: str) -> bool:
    owner = get_owner(db)
    if owner is None:
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        (code or "").strip().upper().encode("utf-8"),
        bytes.fromhex(owner.recovery_salt),
        120_000,
    ).hex()
    return hmac.compare_digest(candidate, owner.recovery_code_hash)


def recover_private_key(db: Session, code: str) -> str:
    if not verify_recovery_code(db, code):
        raise BusinessValidationError("Kode pemulihan tidak cocok.")
    owner = get_owner(db)
    raw = premium_crypto.decrypt_with_password(
        (code or "").strip().upper(), json.loads(owner.recovery_blob)
    )
    return premium_crypto.b64e(raw)


def get_license(db: Session) -> Optional[License]:
    return db.get(License, LICENSE_ID)


def _sign_token(db: Session, license_row: License) -> str:
    payload = {
        "v": 1,
        "owner_id": get_owner(db).owner_id,
        "plan": "premium",
        "period_end": license_row.current_period_end.isoformat(),
        "device_limit": license_row.device_limit,
        "provider": license_row.provider,
        "issued_at": _now().isoformat(),
    }
    raw = premium_crypto.canonical_json(payload)
    signature = premium_crypto.sign(owner_private_key(db), raw)
    return f"{premium_crypto.b64e(raw)}.{signature}"


def verify_token(db: Session, token: str) -> Dict[str, Any]:
    owner = get_owner(db)
    if owner is None:
        raise BusinessValidationError("Token lisensi tidak dapat diverifikasi.")
    try:
        payload_b64, signature = token.split(".", 1)
        raw = premium_crypto.b64d(payload_b64)
    except (ValueError, TypeError) as exc:
        raise BusinessValidationError("Format token lisensi tidak valid.") from exc
    if not premium_crypto.verify(owner.public_key, raw, signature):
        raise BusinessValidationError("Tanda tangan token lisensi tidak valid.")
    payload = json.loads(raw.decode("utf-8"))
    try:
        period_end = datetime.fromisoformat(payload["period_end"])
    except (KeyError, ValueError) as exc:
        raise BusinessValidationError("Isi token lisensi tidak valid.") from exc
    if period_end < _now():
        raise BusinessValidationError("Token lisensi sudah kedaluwarsa.")
    return payload


def activate(
    db: Session,
    *,
    days: int = DEFAULT_PERIOD_DAYS,
    provider: str = "manual",
    device_limit: int = DEFAULT_DEVICE_LIMIT,
) -> Dict[str, Any]:
    days = max(1, min(int(days), MAX_PERIOD_DAYS))
    device_limit = max(1, int(device_limit))
    owner, recovery_code = ensure_owner(db)
    now = _now()
    row = get_license(db)
    if row is None:
        row = License(
            id=LICENSE_ID,
            plan="premium",
            status="active",
            provider=(provider or "manual").strip().lower()[:16],
            started_at=now,
            current_period_end=now + timedelta(days=days),
            device_limit=device_limit,
            last_verified_at=now,
            max_seen_at=now,
        )
        db.add(row)
    else:
        base = row.current_period_end if row.current_period_end > now else now
        row.plan = "premium"
        row.status = "active"
        row.provider = (provider or row.provider or "manual").strip().lower()[:16]
        row.current_period_end = base + timedelta(days=days)
        row.device_limit = device_limit
        row.last_verified_at = now
        row.max_seen_at = max(row.max_seen_at or now, now)
    db.flush()
    row.token = _sign_token(db, row)
    row.token_expires_at = row.current_period_end
    store_registry.set_plan("premium")
    db.commit()
    return {
        "status": "active",
        "owner_id": owner.owner_id,
        "recovery_code": recovery_code,
        "period_end": row.current_period_end,
        "device_limit": row.device_limit,
        "token": row.token,
    }


def renew(db: Session, *, days: int = DEFAULT_PERIOD_DAYS) -> Dict[str, Any]:
    row = get_license(db)
    if row is None:
        return activate(db, days=days)
    return activate(db, days=days, provider=row.provider, device_limit=row.device_limit)


def expire_if_needed(db: Session) -> bool:
    row = get_license(db)
    if row is None or row.status != "active":
        return False
    if row.current_period_end >= _now():
        return False
    row.status = "expired"
    db.commit()
    store_registry.set_plan("free")
    return True


def effective_plan() -> Optional[str]:
    """Plan dari lisensi; None berarti pakai stub registry (uji/pengembangan)."""
    from database.session import SessionLocal

    with SessionLocal() as db:
        row = get_license(db)
        if row is None:
            return None
        if row.status != "active" or row.current_period_end < _now():
            return "free"
        return "premium"


def status(db: Session) -> Dict[str, Any]:
    expire_if_needed(db)
    owner = get_owner(db)
    row = get_license(db)
    now = _now()
    clock_warning = False
    if row is not None:
        last_seen = row.max_seen_at or now
        if now < last_seen - CLOCK_TOLERANCE:
            clock_warning = True
        else:
            row.max_seen_at = max(last_seen, now)
            row.last_verified_at = now
            db.commit()
    premium = (
        row is not None
        and row.status == "active"
        and row.current_period_end >= now
    )
    return {
        "plan": "premium" if premium else "free",
        "premium": premium,
        "owner_id": owner.owner_id if owner else "",
        "owner_public_key": owner.public_key if owner else "",
        "license": {
            "status": row.status if row else "none",
            "provider": row.provider if row else "",
            "period_end": row.current_period_end if row else None,
            "device_limit": row.device_limit if row else 0,
            "days_left": max(0, (row.current_period_end - now).days)
            if row
            else 0,
            "clock_warning": clock_warning,
            "offline": True,
        },
        "recovery_pending": owner is None,
    }


def delete_owner_metadata(db: Session, operator_id: str) -> Dict[str, Any]:
    """Hapus metadata akun premium; data bengkel lokal tidak disentuh (K-18)."""
    counts: Dict[str, int] = {}
    for model in (
        RelayAck,
        RelayEnvelope,
        RelaySnapshot,
        DeviceKeyWrap,
        StoreKey,
        SyncConflict,
        SyncPeerState,
        OutboxItem,
        DeviceStore,
        HubAudit,
        PermissionSnapshot,
        Device,
        LoginGuard,
        EmployeeAccount,
        License,
        OwnerIdentity,
    ):
        result = db.execute(delete(model))
        counts[model.__tablename__] = result.rowcount or 0
    db.commit()
    store_registry.set_plan("free")
    return {"deleted": counts, "business_data": "tetap tersimpan di perangkat"}
