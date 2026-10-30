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
from typing import Optional

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
    salt = secrets.token_bytes(16)
    digest = _hash_pin(value, salt, PBKDF2_ITERATIONS)

    settings_service.set_setting(db, PIN_SALT_KEY, salt.hex())
    settings_service.set_setting(db, PIN_ITER_KEY, str(PBKDF2_ITERATIONS))
    settings_service.set_setting(db, PIN_HASH_KEY, digest.hex())
    settings_service.set_setting(db, PIN_EPOCH_KEY, secrets.token_hex(8))
    settings_service.set_setting(db, SESSION_SECRET_KEY, secrets.token_hex(32))
    _reset_guard(db)
    db.commit()


def verify_pin(db: Session, pin: str) -> None:
    remaining = lock_remaining(db)
    if remaining:
        raise RateLimitError(remaining)

    if not pin_configured(db):
        raise AuthenticationError(
            "PIN kasir belum dibuat. Muat ulang halaman untuk membuat PIN."
        )

    stored_hash = settings_service.get_setting(db, PIN_HASH_KEY)
    stored_salt = bytes.fromhex(settings_service.get_setting(db, PIN_SALT_KEY))
    try:
        iterations = int(settings_service.get_setting(db, PIN_ITER_KEY))
    except (TypeError, ValueError):
        iterations = PBKDF2_ITERATIONS

    candidate = _hash_pin((pin or "").strip(), stored_salt, iterations)
    if hmac.compare_digest(candidate.hex(), stored_hash):
        _reset_guard(db)
        db.commit()
        return

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


def _session_secret(db: Session) -> Optional[bytes]:
    raw = settings_service.get_setting(db, SESSION_SECRET_KEY)
    if not raw:
        return None
    try:
        return bytes.fromhex(raw)
    except ValueError:
        return None


def create_session_token(db: Session) -> str:
    secret = _session_secret(db)
    epoch = settings_service.get_setting(db, PIN_EPOCH_KEY)
    if secret is None or not epoch:
        raise AuthenticationError("PIN kasir belum dibuat.")
    expires = _now() + SESSION_TTL_SECONDS
    payload = f"v1.{epoch}.{expires}"
    signature = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def verify_session_token(db: Session, token: Optional[str]) -> bool:
    if not token:
        return False
    try:
        payload, signature = token.rsplit(".", 1)
        version, epoch, expires = payload.split(".")
        expiry = int(expires)
    except ValueError:
        return False
    if version != "v1" or expiry < _now():
        return False
    if not hmac.compare_digest(
        epoch, settings_service.get_setting(db, PIN_EPOCH_KEY)
    ):
        return False
    secret = _session_secret(db)
    if secret is None:
        return False
    expected = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(
        signature.encode("utf-8"), expected.encode("utf-8")
    )
