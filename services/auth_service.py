"""PIN kasir web lokal: hash PBKDF2, sesi bertanda tangan, dan jeda brute-force.

Ref: K-02. PIN disimpan sebagai hash + salt di `app_settings`, tidak pernah
plaintext. Sesi berupa cookie HttpOnly bertanda tangan HMAC; kunci tanda tangan
dan epok PIN disimpan di database sehingga reset PIN membatalkan sesi lama.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from typing import NoReturn, Optional

from sqlalchemy.orm import Session

from services import settings_service
from services.errors import (
    AuthenticationError,
    BusinessValidationError,
    ConflictError,
    RateLimitError,
)

COOKIE_NAME = "bengkel_session"

PIN_HASH_KEY = "auth.pin_hash"
PIN_SALT_KEY = "auth.pin_salt"
PIN_ITER_KEY = "auth.pin_iterations"
PIN_EPOCH_KEY = "auth.pin_epoch"
SESSION_SECRET_KEY = "auth.session_secret"
FAILED_KEY = "auth.failed_attempts"
LOCK_UNTIL_KEY = "auth.lock_until"

KASIR_HASH_KEY = "auth.kasir_pin_hash"
KASIR_SALT_KEY = "auth.kasir_pin_salt"
KASIR_ITER_KEY = "auth.kasir_pin_iterations"
KASIR_EPOCH_KEY = "auth.kasir_pin_epoch"

OWNER_ROLE = "owner"
KASIR_ROLE = "kasir"


@dataclass(frozen=True)
class Operator:
    """Principal yang sudah terverifikasi backend (ARC-15)."""

    id: str
    role: str
    label: str


OWNER = Operator(id="owner", role=OWNER_ROLE, label="Pemilik")
KASIR = Operator(id="kasir", role=KASIR_ROLE, label="Kasir")
_OPERATORS = {(OWNER.id, OWNER.role): OWNER, (KASIR.id, KASIR.role): KASIR}

PIN_MIN_LENGTH = 4
PIN_MAX_LENGTH = 12
PBKDF2_ITERATIONS = 120_000
PBKDF2_ALGORITHM = "sha256"

MAX_FAILURES = 5
BASE_LOCK_SECONDS = 30
MAX_LOCK_SECONDS = 900
SESSION_TTL_SECONDS = 12 * 60 * 60


def _now() -> int:
    return int(time.time())


def _clean_pin(pin: str) -> str:
    value = (pin or "").strip()
    if not value.isdigit():
        raise BusinessValidationError("PIN hanya boleh berisi angka.")
    if not PIN_MIN_LENGTH <= len(value) <= PIN_MAX_LENGTH:
        raise BusinessValidationError(
            f"PIN harus {PIN_MIN_LENGTH}-{PIN_MAX_LENGTH} angka."
        )
    return value


def _hash_pin(pin: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM, pin.encode("utf-8"), salt, iterations
    )


def pin_configured(db: Session) -> bool:
    return bool(settings_service.get_setting(db, PIN_HASH_KEY))


def kasir_configured(db: Session) -> bool:
    return bool(settings_service.get_setting(db, KASIR_HASH_KEY))


def _store_pin(db: Session, value: str, hash_key: str, salt_key: str, iter_key: str) -> None:
    salt = secrets.token_bytes(16)
    digest = _hash_pin(value, salt, PBKDF2_ITERATIONS)
    settings_service.set_setting(db, salt_key, salt.hex())
    settings_service.set_setting(db, iter_key, str(PBKDF2_ITERATIONS))
    settings_service.set_setting(db, hash_key, digest.hex())


def _pin_matches(db: Session, value: str, hash_key: str, salt_key: str, iter_key: str) -> bool:
    stored_hash = settings_service.get_setting(db, hash_key)
    if not stored_hash:
        return False
    try:
        salt = bytes.fromhex(settings_service.get_setting(db, salt_key))
    except ValueError:
        return False
    try:
        iterations = int(settings_service.get_setting(db, iter_key))
    except (TypeError, ValueError):
        iterations = PBKDF2_ITERATIONS
    candidate = _hash_pin(value, salt, iterations)
    return hmac.compare_digest(candidate.hex(), stored_hash)


def _clear_kasir(db: Session) -> None:
    for key in (KASIR_HASH_KEY, KASIR_SALT_KEY, KASIR_ITER_KEY, KASIR_EPOCH_KEY):
        settings_service.set_setting(db, key, "")


def _epoch_key(role: str) -> str:
    return KASIR_EPOCH_KEY if role == KASIR_ROLE else PIN_EPOCH_KEY


def _epoch(db: Session, role: str) -> str:
    return settings_service.get_setting(db, _epoch_key(role))



def lock_remaining(db: Session) -> int:
    raw = settings_service.get_setting(db, LOCK_UNTIL_KEY)
    try:
        until = int(raw)
    except (TypeError, ValueError):
        return 0
    return max(0, until - _now())


def _reset_guard(db: Session) -> None:
    settings_service.set_setting(db, FAILED_KEY, "0")
    settings_service.set_setting(db, LOCK_UNTIL_KEY, "0")


def setup_pin(db: Session, pin: str) -> None:
    if pin_configured(db):
        raise ConflictError(
            "PIN kasir sudah dibuat. Masukkan PIN untuk membuka aplikasi."
        )
    value = _clean_pin(pin)
    _store_pin(db, value, PIN_HASH_KEY, PIN_SALT_KEY, PIN_ITER_KEY)
    settings_service.set_setting(db, PIN_EPOCH_KEY, secrets.token_hex(8))
    settings_service.set_setting(db, SESSION_SECRET_KEY, secrets.token_hex(32))
    # Kredensial kasir lama tidak boleh tetap berlaku setelah pemilik baru
    # membuat PIN (mis. setelah reset total).
    _clear_kasir(db)
    _reset_guard(db)
    db.commit()


def set_kasir_pin(db: Session, pin: str) -> None:
    """Buat/ganti PIN kasir. Hanya dipanggil setelah otorisasi owner."""
    if not pin_configured(db):
        raise ConflictError("PIN pemilik belum dibuat.")
    value = _clean_pin(pin)
    if _pin_matches(db, value, PIN_HASH_KEY, PIN_SALT_KEY, PIN_ITER_KEY):
        raise BusinessValidationError(
            "PIN kasir tidak boleh sama dengan PIN pemilik."
        )
    _store_pin(db, value, KASIR_HASH_KEY, KASIR_SALT_KEY, KASIR_ITER_KEY)
    settings_service.set_setting(db, KASIR_EPOCH_KEY, secrets.token_hex(8))
    db.commit()


def clear_kasir_pin(db: Session) -> None:
    _clear_kasir(db)
    db.commit()


def _record_failure(db: Session) -> NoReturn:
    try:
        failures = int(settings_service.get_setting(db, FAILED_KEY)) + 1
    except (TypeError, ValueError):
        failures = 1
    settings_service.set_setting(db, FAILED_KEY, str(failures))

    if failures >= MAX_FAILURES:
        delay = min(
            BASE_LOCK_SECONDS * (2 ** (failures - MAX_FAILURES)),
            MAX_LOCK_SECONDS,
        )
        settings_service.set_setting(db, LOCK_UNTIL_KEY, str(_now() + delay))
        db.commit()
        raise RateLimitError(delay)

    db.commit()
    raise AuthenticationError(
        f"PIN salah. Sisa percobaan sebelum jeda: {MAX_FAILURES - failures}."
    )


def authenticate_pin(db: Session, pin: str) -> Operator:
    """Tentukan operator dari PIN yang cocok; identitas tidak dari frontend."""
    remaining = lock_remaining(db)
    if remaining:
        raise RateLimitError(remaining)

    if not pin_configured(db):
        raise AuthenticationError(
            "PIN kasir belum dibuat. Muat ulang halaman untuk membuat PIN."
        )

    value = (pin or "").strip()
    if _pin_matches(db, value, PIN_HASH_KEY, PIN_SALT_KEY, PIN_ITER_KEY):
        _reset_guard(db)
        db.commit()
        return OWNER
    if kasir_configured(db) and _pin_matches(
        db, value, KASIR_HASH_KEY, KASIR_SALT_KEY, KASIR_ITER_KEY
    ):
        _reset_guard(db)
        db.commit()
        return KASIR

    _record_failure(db)


def verify_pin(db: Session, pin: str) -> Operator:
    return authenticate_pin(db, pin)


def _session_secret(db: Session) -> Optional[bytes]:
    raw = settings_service.get_setting(db, SESSION_SECRET_KEY)
    if not raw:
        return None
    try:
        return bytes.fromhex(raw)
    except ValueError:
        return None


def create_session_token(db: Session, operator: Operator = OWNER) -> str:
    secret = _session_secret(db)
    epoch = _epoch(db, operator.role)
    if secret is None or not epoch:
        raise AuthenticationError("PIN kasir belum dibuat.")
    expires = _now() + SESSION_TTL_SECONDS
    payload = f"v2.{operator.id}.{operator.role}.{epoch}.{expires}"
    signature = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def verify_session_token(db: Session, token: Optional[str]) -> Optional[Operator]:
    """Kembalikan operator pemilik sesi, atau None bila tidak valid."""
    if not token:
        return None
    try:
        payload, signature = token.rsplit(".", 1)
        parts = payload.split(".")
    except ValueError:
        return None

    if parts[:1] == ["v2"] and len(parts) == 5:
        _, operator_id, role, epoch, expires = parts
        operator = _OPERATORS.get((operator_id, role))
    elif parts[:1] == ["v1"] and len(parts) == 3:
        # Sesi lama (sebelum ARC-15) tetap diterima sebagai pemilik.
        _, epoch, expires = parts
        operator = OWNER
    else:
        return None
    if operator is None:
        return None
    try:
        expiry = int(expires)
    except ValueError:
        return None
    if expiry < _now():
        return None
    if not hmac.compare_digest(epoch, _epoch(db, operator.role)):
        return None
    secret = _session_secret(db)
    if secret is None:
        return None
    expected = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(
        signature.encode("utf-8"), expected.encode("utf-8")
    ):
        return None
    return operator
