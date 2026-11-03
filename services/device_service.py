"""Perangkat premium, batas slot owner, hub uang per toko, dan pencabutan (K-12)."""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import timedelta
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import store_registry
from database.models import (
    Device,
    DeviceStore,
    EmployeeAccount,
    utcnow,
)
from services import license_service, premium_crypto
from services.errors import (
    BusinessValidationError,
    ConflictError,
    FeatureLockedError,
    NotFoundError,
)

RELEASE_WINDOW = timedelta(hours=72)
DEFAULT_DEVICE_LIMIT = 2


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now():
    return utcnow()


def _iso(value) -> str:
    return value.isoformat() if value is not None else ""


def _public_keys(device: Device) -> tuple[str, str]:
    try:
        data = json.loads(device.public_key or "{}")
        if isinstance(data, dict):
            return str(data.get("sign") or ""), str(data.get("encrypt") or "")
    except ValueError:
        pass
    return device.public_key or "", ""


def signing_key(device: Device) -> str:
    return _public_keys(device)[0]


def encryption_key(device: Device) -> str:
    return _public_keys(device)[1]


def _store_ids(db: Session, device: Device) -> List[str]:
    return [
        row.store_id
        for row in db.execute(
            select(DeviceStore)
            .where(DeviceStore.device_id == device.id)
            .order_by(DeviceStore.store_id)
        ).scalars()
    ]


def device_stores(db: Session, device_id: str) -> Sequence[DeviceStore]:
    return list(
        db.execute(
            select(DeviceStore)
            .where(DeviceStore.device_id == device_id)
            .order_by(DeviceStore.store_id)
        ).scalars()
    )


def _owner_device_limit(db: Session) -> int:
    row = license_service.get_license(db)
    return row.device_limit if row is not None else DEFAULT_DEVICE_LIMIT


def _owner_device_count(db: Session) -> int:
    return len(
        db.execute(
            select(Device.id).where(
                Device.kind == "owner", Device.revoked_at.is_(None)
            )
        ).all()
    )


def list_devices(db: Session) -> List[Dict[str, Any]]:
    rows = db.execute(select(Device).order_by(Device.created_at)).scalars()
    result: List[Dict[str, Any]] = []
    for device in rows:
        store_ids = _store_ids(db, device)
        result.append(
            {
                "id": device.id,
                "nama": device.nama,
                "kind": device.kind,
                "employee_account_id": device.employee_account_id,
                "public_key": signing_key(device),
                "stores": store_ids,
                "created_at": _iso(device.created_at),
                "last_seen_at": _iso(device.last_seen_at),
                "revoked_at": _iso(device.revoked_at),
                "revoked_reason": device.revoked_reason,
                "online": device.revoked_at is None
                and device.last_seen_at is not None
                and (_now() - device.last_seen_at) < timedelta(minutes=10),
            }
        )
    return result


def get_device(db: Session, device_id: str) -> Device:
    device = db.get(Device, device_id)
    if device is None:
        raise NotFoundError("Perangkat tidak ditemukan.")
    return device


def _assign_stores(db: Session, device: Device, store_ids: Sequence[str]) -> None:
    available = {row["store_id"] for row in store_registry.list_stores(include_missing=True)}
    wanted = [str(item).strip() for item in store_ids if str(item).strip()]
    if not wanted:
        wanted = sorted(available) if device.kind == "owner" else []
    for store_id in wanted:
        if store_id not in available:
            raise BusinessValidationError(f"Toko '{store_id}' tidak dikenal.")
        exists = db.get(DeviceStore, (device.id, store_id))
        if exists is None:
            db.add(DeviceStore(device_id=device.id, store_id=store_id))


def register_device(
    db: Session,
    *,
    nama: str,
    kind: str = "owner",
    public_key: str = "",
    encryption_key: str = "",
    employee_account_id: Optional[int] = None,
    store_ids: Optional[Sequence[str]] = None,
    device_id: Optional[str] = None,
) -> Dict[str, Any]:
    kind_value = (kind or "owner").strip().lower()
    if kind_value not in {"owner", "employee"}:
        raise BusinessValidationError("Jenis perangkat harus owner atau employee.")
    if kind_value == "owner":
        limit = _owner_device_limit(db)
        if _owner_device_count(db) >= limit:
            raise FeatureLockedError(
                f"Batas {limit} perangkat owner paket ini sudah terpakai. "
                "Cabut perangkat lama untuk membebaskan slot.",
                code="device_limit",
            )
    else:
        if employee_account_id is None:
            raise BusinessValidationError("Perangkat karyawan wajib terikat akun.")
        account = db.get(EmployeeAccount, employee_account_id)
        if account is None or not account.aktif:
            raise BusinessValidationError("Akun karyawan tidak aktif.")

    owner = license_service.get_owner(db)
    if owner is None:
        raise BusinessValidationError("Aktifkan premium terlebih dahulu.")
    token = secrets.token_urlsafe(32)
    device = Device(
        id=device_id or store_registry.new_ulid(),
        owner_id=owner.owner_id,
        nama=(nama or "").strip()[:255] or "Perangkat",
        kind=kind_value,
        employee_account_id=employee_account_id,
        public_key=json.dumps(
            {"sign": public_key, "encrypt": encryption_key},
            separators=(",", ":"),
        ),
        token_hash=_hash_token(token),
    )
    db.add(device)
    db.flush()
    _assign_stores(db, device, store_ids or [])
    db.commit()
    return {
        "device": next(
            row for row in list_devices(db) if row["id"] == device.id
        ),
        "token": token,
    }


def claim_device(
    db: Session,
    *,
    old_device_id: str,
    nama: str,
    public_key: str,
    encryption_key: str,
    actor: str,
) -> Dict[str, Any]:
    """Instal ulang: slot perangkat lama diambil perangkat baru (K-22)."""
    old = get_device(db, old_device_id)
    if old.kind != "owner":
        raise BusinessValidationError(
            "Klaim slot hanya untuk perangkat owner; perangkat karyawan "
            "didaftarkan ulang."
        )
    if old.revoked_at is not None:
        raise ConflictError("Perangkat lama sudah dicabut.")
    stores = _store_ids(db, old)
    revoke_device(db, old.id, actor=actor, reason="diganti perangkat baru")
    return register_device(
        db,
        nama=nama or old.nama,
        kind="owner",
        public_key=public_key,
        encryption_key=encryption_key,
        store_ids=stores,
    )


def revoke_device(
    db: Session, device_id: str, *, actor: str, reason: str = ""
) -> Dict[str, Any]:
    device = get_device(db, device_id)
    if device.revoked_at is None:
        device.revoked_at = _now()
        device.revoked_reason = (reason or "dicabut pemilik")[:255]
        db.commit()
    return next(row for row in list_devices(db) if row["id"] == device.id)


def release_device(
    db: Session, device_id: str, *, actor: str
) -> Dict[str, Any]:
    """Pelepasan slot mandiri maksimal satu kali per 72 jam (K-12)."""
    last = db.execute(
        select(Device.release_used_at)
        .where(Device.release_used_at.is_not(None))
        .order_by(Device.release_used_at.desc())
    ).scalars().first()
    if last is not None and _now() - last < RELEASE_WINDOW:
        remaining = RELEASE_WINDOW - (_now() - last)
        hours = max(1, int(remaining.total_seconds() // 3600))
        raise FeatureLockedError(
            f"Pelepasan slot mandiri hanya sekali per 72 jam. Coba lagi sekitar "
            f"{hours} jam lagi.",
            code="release_window",
        )
    device = get_device(db, device_id)
    device.release_used_at = _now()
    result = revoke_device(db, device_id, actor=actor, reason="pelepasan slot mandiri")
    return result


def assert_cashier_money_access(
    db: Session, operator: Any, store_id: Optional[str] = None
) -> None:
    """Void/retur/piutang boleh ditulis siapa pun yang memiliki akses kasir."""
    if getattr(operator, "kind", "owner") == "owner":
        return
    role = getattr(operator, "role", "")
    if role not in {"KASIR", "KEDUANYA"}:
        raise FeatureLockedError(
            "Peran ini tidak dapat menulis uang.", code="role_money_locked"
        )
    active_store = store_id or store_registry.active_store()["store_id"]
    if active_store not in tuple(getattr(operator, "stores", ())):
        raise FeatureLockedError(
            "Karyawan hanya dapat menulis uang di toko yang ditugaskan.",
            code="store_not_assigned",
        )


def assert_store_access(db: Session, operator: Any, store_id: str) -> None:
    if getattr(operator, "kind", "owner") == "owner":
        return
    if store_id not in tuple(getattr(operator, "stores", ())):
        raise FeatureLockedError(
            "Karyawan hanya dapat membuka toko yang ditugaskan.",
            code="store_not_assigned",
        )


def device_from_token(db: Session, token: Optional[str]) -> Optional[Device]:
    if not token:
        return None
    device = db.execute(
        select(Device).where(Device.token_hash == _hash_token(token))
    ).scalar_one_or_none()
    if device is None or device.revoked_at is not None:
        return None
    device.last_seen_at = _now()
    db.commit()
    return device


def ensure_web_device(db: Session, actor: str) -> Dict[str, Any]:
    """Daftarkan sesi web lokal sebagai perangkat owner bila belum ada."""
    existing = db.execute(
        select(Device).where(Device.kind == "owner", Device.revoked_at.is_(None))
    ).scalars().first()
    if existing is not None:
        return {
            "device": next(
                row for row in list_devices(db) if row["id"] == existing.id
            ),
            "token": None,
            "private_keys": None,
        }
    sign_private, sign_public = premium_crypto.generate_signing_keypair()
    enc_private, enc_public = premium_crypto.generate_encryption_keypair()
    created = register_device(
        db,
        nama="Perangkat web",
        kind="owner",
        public_key=sign_public,
        encryption_key=enc_public,
        store_ids=[],
    )
    created["private_keys"] = {"sign": sign_private, "encrypt": enc_private}
    return created
