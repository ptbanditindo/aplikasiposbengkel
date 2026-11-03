"""Akun karyawan premium: password, PIN, peran, izin tambahan, dan audit (K-07/K-08)."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import store_registry
from database.models import (
    EmployeeAccount,
    LoginGuard,
    PermissionAudit,
    PermissionSnapshot,
    utcnow,
)
from services import license_service, premium_crypto
from services.errors import (
    AuthenticationError,
    BusinessValidationError,
    ConflictError,
    NotFoundError,
    RateLimitError,
)

ROLES = ("KASIR", "MEKANIK", "KEDUANYA")
ROLE_LABELS = {
    "KASIR": "Kasir",
    "MEKANIK": "Mekanik",
    "KEDUANYA": "Kasir & Mekanik",
}

PERMISSIONS: Dict[str, str] = {
    "opname": "Opname stok",
    "stok_masuk": "Stok masuk",
    "stok_keluar": "Stok keluar",
    "lihat_laporan": "Lihat laporan",
    "cetak_laporan": "Cetak laporan",
    "baca_supplier": "Baca supplier",
    "baca_followup": "Baca follow up",
}

ROLE_PERMISSIONS: Dict[str, frozenset[str]] = {
    "KASIR": frozenset({"lihat_laporan"}),
    "MEKANIK": frozenset(),
    "KEDUANYA": frozenset({"lihat_laporan"}),
}

OWNER_ONLY_PERMISSIONS = frozenset(
    {
        "kelola_akun",
        "kelola_perangkat",
        "lisensi",
        "tambah_toko",
        "hapus_data",
        "tarif_komisi",
        "tarif_gaji",
    }
)

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")

MAX_FAILURES = 5
BASE_LOCK_SECONDS = 30
MAX_LOCK_SECONDS = 900
PBKDF2_ITERATIONS = 120_000


def _now_ts() -> int:
    return int(time.time())


def random_password(length: Optional[int] = None) -> str:
    size = length or secrets.choice((10, 11, 12))
    return "".join(secrets.choice(ALPHABET) for _ in range(size))


def _hash(value: str, salt: bytes, iterations: int) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", value.encode("utf-8"), salt, iterations
    ).hex()


def _password_matches(account: EmployeeAccount, password: str) -> bool:
    stored = account.password_hash or ""
    if not stored:
        return False
    try:
        if stored.startswith("$2"):
            return bcrypt.checkpw(
                (password or "").encode("utf-8"), stored.encode("utf-8")
            )
        salt = bytes.fromhex(account.password_salt)
    except (ValueError, TypeError):
        return False
    candidate = _hash(password, salt, account.password_iterations or PBKDF2_ITERATIONS)
    return hmac.compare_digest(candidate, account.password_hash)


def _pin_matches(account: EmployeeAccount, pin: str) -> bool:
    if not account.pin_hash:
        return False
    try:
        salt = bytes.fromhex(account.pin_salt)
    except ValueError:
        return False
    candidate = _hash(pin, salt, account.pin_iterations or PBKDF2_ITERATIONS)
    return hmac.compare_digest(candidate, account.pin_hash)


def set_password(account: EmployeeAccount, password: str, *, must_change: bool = True) -> None:
    if len(password or "") < 8:
        raise BusinessValidationError("Password minimal 8 karakter.")
    raw = (password or "").encode("utf-8")
    if len(raw) > 72:
        raise BusinessValidationError("Password maksimal 72 byte.")
    account.password_hash = bcrypt.hashpw(raw, bcrypt.gensalt(rounds=12)).decode(
        "ascii"
    )
    account.password_salt = ""
    account.password_iterations = 0
    account.must_change_password = must_change


def _clean_pin(pin: str) -> str:
    value = (pin or "").strip()
    if not value.isdigit() or len(value) != 6:
        raise BusinessValidationError("PIN karyawan harus 6 angka.")
    return value


def set_pin(account: EmployeeAccount, pin: str) -> None:
    value = _clean_pin(pin)
    salt = secrets.token_bytes(16)
    account.pin_salt = salt.hex()
    account.pin_iterations = PBKDF2_ITERATIONS
    account.pin_hash = _hash(value, salt, PBKDF2_ITERATIONS)


def _parse_list(raw: str) -> List[str]:
    try:
        value = json.loads(raw or "[]")
    except ValueError:
        return []
    return [str(item) for item in value] if isinstance(value, list) else []


def effective_permissions(account: EmployeeAccount) -> frozenset[str]:
    role = account.role_base if account.role_base in ROLES else "MEKANIK"
    return ROLE_PERMISSIONS[role] | frozenset(_parse_list(account.extra_permissions_json))


def assigned_stores(account: EmployeeAccount) -> tuple[str, ...]:
    return tuple(_parse_list(account.store_ids_json))


def _validate_stores(store_ids: Optional[Sequence[str]]) -> List[str]:
    available = {row["store_id"] for row in store_registry.list_stores(include_missing=True)}
    cleaned: List[str] = []
    for store_id in store_ids or []:
        value = str(store_id).strip()
        if not value:
            continue
        if value not in available:
            raise BusinessValidationError(f"Toko '{value}' tidak dikenal.")
        if value not in cleaned:
            cleaned.append(value)
    return cleaned


def _validate_permissions(extras: Optional[Iterable[str]]) -> List[str]:
    cleaned: List[str] = []
    for permission in extras or []:
        value = str(permission).strip()
        if not value:
            continue
        if value in OWNER_ONLY_PERMISSIONS:
            raise BusinessValidationError(
                "Akses khusus pemilik tidak dapat diberikan lewat izin tambahan."
            )
        if value not in PERMISSIONS:
            raise BusinessValidationError(f"Izin '{value}' tidak dikenal.")
        if value not in cleaned:
            cleaned.append(value)
    return cleaned


def _snapshot_payload(account: EmployeeAccount) -> Dict[str, Any]:
    return {
        "v": 1,
        "account_id": account.id,
        "username": account.username,
        "role": account.role_base,
        "permissions": sorted(effective_permissions(account)),
        "stores": list(assigned_stores(account)),
        "permission_version": account.permission_version,
        "updated_at": (account.updated_at or utcnow()).isoformat(),
    }


def sign_permission_snapshot(db: Session, account: EmployeeAccount) -> PermissionSnapshot:
    payload = _snapshot_payload(account)
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    signature = premium_crypto.sign(
        license_service.owner_private_key(db),
        premium_crypto.canonical_json(payload),
    )
    snapshot = db.execute(
        select(PermissionSnapshot).where(
            PermissionSnapshot.employee_account_id == account.id,
            PermissionSnapshot.version == account.permission_version,
        )
    ).scalar_one_or_none()
    if snapshot is None:
        snapshot = PermissionSnapshot(
            employee_account_id=account.id,
            version=account.permission_version,
            payload_json=payload_json,
            signature=signature,
        )
        db.add(snapshot)
    else:
        snapshot.payload_json = payload_json
        snapshot.signature = signature
    db.flush()
    return snapshot


def _audit(
    db: Session,
    actor: str,
    account: Optional[EmployeeAccount],
    before: Dict[str, Any],
    after: Dict[str, Any],
    note: str = "",
) -> None:
    db.add(
        PermissionAudit(
            actor_id=actor,
            employee_account_id=account.id if account else None,
            username=account.username if account else str(after.get("username") or ""),
            before_json=json.dumps(before, ensure_ascii=False, sort_keys=True),
            after_json=json.dumps(after, ensure_ascii=False, sort_keys=True),
            note=note,
        )
    )


def _public(account: EmployeeAccount) -> Dict[str, Any]:
    return {
        "id": account.id,
        "username": account.username,
        "nama": account.nama,
        "role": account.role_base,
        "role_label": ROLE_LABELS.get(account.role_base, account.role_base),
        "stores": list(assigned_stores(account)),
        "extra_permissions": _parse_list(account.extra_permissions_json),
        "permissions": sorted(effective_permissions(account)),
        "aktif": bool(account.aktif),
        "must_change_password": bool(account.must_change_password),
        "pin_configured": bool(account.pin_hash),
        "last_login_at": account.last_login_at,
        "permission_version": account.permission_version,
    }


def list_accounts(db: Session) -> List[Dict[str, Any]]:
    rows = db.execute(
        select(EmployeeAccount).order_by(EmployeeAccount.username)
    ).scalars()
    return [_public(row) for row in rows]


def get_account(db: Session, account_id: int) -> EmployeeAccount:
    account = db.get(EmployeeAccount, account_id)
    if account is None:
        raise NotFoundError("Akun karyawan tidak ditemukan.")
    return account


def find_by_username(db: Session, username: str) -> Optional[EmployeeAccount]:
    return db.execute(
        select(EmployeeAccount).where(
            EmployeeAccount.username == (username or "").strip().lower()
        )
    ).scalar_one_or_none()


def create_account(
    db: Session,
    *,
    actor: str,
    username: str,
    nama: str = "",
    role: str = "KASIR",
    store_ids: Optional[Sequence[str]] = None,
    extra_permissions: Optional[Iterable[str]] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    clean_username = (username or "").strip().lower()
    if not USERNAME_PATTERN.match(clean_username):
        raise BusinessValidationError(
            "Username 3-32 karakter, huruf kecil/angka/titik/strip, tanpa spasi."
        )
    if find_by_username(db, clean_username) is not None:
        raise ConflictError("Username sudah dipakai di owner ini.")
    role_value = (role or "").strip().upper()
    if role_value not in ROLES:
        raise BusinessValidationError("Peran dasar harus KASIR, MEKANIK, atau KEDUANYA.")
    stores = _validate_stores(store_ids)
    if not stores:
        stores = [store_registry.active_store()["store_id"]]
    extras = _validate_permissions(extra_permissions)
    initial = password or random_password()
    account = EmployeeAccount(
        username=clean_username,
        nama=(nama or "").strip()[:255],
        role_base=role_value,
        store_ids_json=json.dumps(stores),
        extra_permissions_json=json.dumps(extras),
        permission_version=1,
    )
    set_password(account, initial, must_change=True)
    db.add(account)
    db.flush()
    _audit(db, actor, account, {}, _public(account), "buat akun")
    sign_permission_snapshot(db, account)
    db.commit()
    return {"akun": _public(account), "password": initial}


def update_account(
    db: Session,
    account_id: int,
    *,
    actor: str,
    nama: Optional[str] = None,
    role: Optional[str] = None,
    store_ids: Optional[Sequence[str]] = None,
    extra_permissions: Optional[Iterable[str]] = None,
    aktif: Optional[bool] = None,
) -> Dict[str, Any]:
    account = get_account(db, account_id)
    before = _public(account)
    if nama is not None:
        account.nama = str(nama).strip()[:255]
    if role is not None:
        role_value = str(role).strip().upper()
        if role_value not in ROLES:
            raise BusinessValidationError("Peran dasar tidak dikenal.")
        account.role_base = role_value
    if store_ids is not None:
        stores = _validate_stores(store_ids)
        if not stores:
            raise BusinessValidationError("Karyawan minimal ditugaskan ke satu toko.")
        account.store_ids_json = json.dumps(stores)
    if extra_permissions is not None:
        account.extra_permissions_json = json.dumps(
            _validate_permissions(extra_permissions)
        )
    if aktif is not None:
        account.aktif = bool(aktif)
    account.permission_version = (account.permission_version or 1) + 1
    _audit(db, actor, account, before, _public(account), "ubah akun/izin")
    sign_permission_snapshot(db, account)
    db.commit()
    return _public(account)


def reset_password(
    db: Session, account_id: int, *, actor: str, password: Optional[str] = None
) -> Dict[str, Any]:
    account = get_account(db, account_id)
    before = _public(account)
    new_password = password or random_password()
    set_password(account, new_password, must_change=True)
    _audit(db, actor, account, before, _public(account), "reset password")
    db.commit()
    return {"akun": _public(account), "password": new_password}


def reset_pin(db: Session, account_id: int, *, actor: str) -> Dict[str, Any]:
    account = get_account(db, account_id)
    before = _public(account)
    account.pin_hash = ""
    account.pin_salt = ""
    account.pin_iterations = PBKDF2_ITERATIONS
    _audit(db, actor, account, before, _public(account), "reset PIN")
    db.commit()
    return _public(account)


def change_password(
    db: Session, account_id: int, *, old_password: str, new_password: str
) -> EmployeeAccount:
    account = get_account(db, account_id)
    if not _password_matches(account, old_password):
        raise AuthenticationError("Password lama tidak cocok.")
    set_password(account, new_password, must_change=False)
    db.commit()
    return account


def set_employee_pin(db: Session, account_id: int, *, password: str, pin: str) -> EmployeeAccount:
    account = get_account(db, account_id)
    if not _password_matches(account, password):
        raise AuthenticationError("Password tidak cocok.")
    set_pin(account, pin)
    db.commit()
    return account


# --- Login karyawan -------------------------------------------------------


def _guard(db: Session, scope_key: str) -> LoginGuard:
    guard = db.get(LoginGuard, scope_key)
    if guard is None:
        guard = LoginGuard(scope_key=scope_key, failures=0, lock_until=0)
        db.add(guard)
        db.flush()
    return guard


def _check_guard(guard: LoginGuard) -> None:
    remaining = max(0, int(guard.lock_until or 0) - _now_ts())
    if remaining:
        raise RateLimitError(remaining)


def _record_failure(db: Session, guard: LoginGuard) -> None:
    guard.failures = int(guard.failures or 0) + 1
    if guard.failures >= MAX_FAILURES:
        delay = min(
            BASE_LOCK_SECONDS * (2 ** (guard.failures - MAX_FAILURES)),
            MAX_LOCK_SECONDS,
        )
        guard.lock_until = _now_ts() + delay
        db.commit()
        raise RateLimitError(delay)
    db.commit()
    raise AuthenticationError(
        "Username atau kata sandi salah. "
        f"Sisa percobaan sebelum jeda: {MAX_FAILURES - guard.failures}."
    )


def _clear_guard(db: Session, guard: LoginGuard) -> None:
    guard.failures = 0
    guard.lock_until = 0


def authenticate_hub(
    db: Session, username: str, password: str, pin: str
) -> tuple[EmployeeAccount, bool]:
    """Login di hub: username + password + PIN, diverifikasi lokal."""
    scope = "hub:" + (username or "").strip().lower()
    guard = _guard(db, scope)
    _check_guard(guard)
    account = find_by_username(db, username)
    if account is None or not account.aktif or not _password_matches(account, password):
        _record_failure(db, guard)
    pin_set = False
    if not account.pin_hash:
        set_pin(account, pin)
        pin_set = True
    elif not _pin_matches(account, (pin or "").strip()):
        _record_failure(db, guard)
    _clear_guard(db, guard)
    account.last_login_at = utcnow()
    db.commit()
    return account, pin_set


def authenticate_device(
    db: Session, owner_id: str, username: str, password: str
) -> EmployeeAccount:
    """Login perangkat karyawan: ID owner + username + password (online)."""
    owner = license_service.get_owner(db)
    scope = "device:" + (owner_id or "").strip().lower() + ":" + (username or "").strip().lower()
    guard = _guard(db, scope)
    _check_guard(guard)
    account = find_by_username(db, username)
    owner_ok = owner is not None and hmac.compare_digest(
        owner.owner_id, (owner_id or "").strip()
    )
    if (
        not owner_ok
        or account is None
        or not account.aktif
        or not _password_matches(account, password)
    ):
        _record_failure(db, guard)
    _clear_guard(db, guard)
    account.last_login_at = utcnow()
    db.commit()
    return account


def latest_snapshot(db: Session, account_id: int) -> Dict[str, Any]:
    snapshot = db.execute(
        select(PermissionSnapshot)
        .where(PermissionSnapshot.employee_account_id == account_id)
        .order_by(PermissionSnapshot.version.desc())
    ).scalars().first()
    if snapshot is None:
        raise NotFoundError("Snapshot izin belum tersedia.")
    return {
        "account_id": account_id,
        "version": snapshot.version,
        "payload": json.loads(snapshot.payload_json),
        "signature": snapshot.signature,
    }


def verify_snapshot(db: Session, payload: Dict[str, Any], signature: str) -> bool:
    return premium_crypto.verify(
        license_service.owner_public_key(db),
        premium_crypto.canonical_json(payload),
        signature,
    )


def audit_rows(db: Session, account_id: Optional[int] = None) -> List[Dict[str, Any]]:
    query = select(PermissionAudit).order_by(PermissionAudit.created_at.desc())
    if account_id is not None:
        query = query.where(PermissionAudit.employee_account_id == account_id)
    return [
        {
            "id": row.id,
            "actor_id": row.actor_id,
            "username": row.username,
            "before": json.loads(row.before_json or "{}"),
            "after": json.loads(row.after_json or "{}"),
            "note": row.note,
            "created_at": row.created_at,
        }
        for row in db.execute(query).scalars()
    ]
