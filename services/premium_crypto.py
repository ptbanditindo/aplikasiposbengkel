"""Primitif kunci premium: tanda tangan, wrapped key, amplop AEAD, dan HLC.

Web dipakai sebagai kanal uji; kunci privat pada produksi Dart disimpan di
secure storage. Modul ini tidak pernah mengirim kunci privat ke antrean relay:
server hanya menerima kunci publik, wrapped store key, dan ciphertext.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from typing import Any, Dict, Tuple

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

STORE_KEY_INFO = b"pusatkupos-store-key-v1"
NONCE_BYTES = 12
WRAP_VERSION = 1


def b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii")


def b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value.encode("ascii"))


def canonical_json(payload: Any) -> bytes:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def generate_signing_keypair() -> Tuple[str, str]:
    private = Ed25519PrivateKey.generate()
    private_raw = private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_raw = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return b64e(private_raw), b64e(public_raw)


def new_store_key() -> bytes:
    return os.urandom(32)


def sign(private_b64: str, payload: bytes) -> str:
    private = Ed25519PrivateKey.from_private_bytes(b64d(private_b64))
    return b64e(private.sign(payload))


def verify(public_b64: str, payload: bytes, signature_b64: str) -> bool:
    try:
        public = Ed25519PublicKey.from_public_bytes(b64d(public_b64))
        public.verify(b64d(signature_b64), payload)
        return True
    except Exception:
        return False


def _shared_key(private: X25519PrivateKey, public_b64: str) -> bytes:
    peer = X25519PublicKey.from_public_bytes(b64d(public_b64))
    shared = private.exchange(peer)
    return HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None, info=STORE_KEY_INFO
    ).derive(shared)


def wrap_store_key(recipient_public_b64: str, store_key: bytes) -> str:
    """Bungkus kunci toko untuk kunci publik perangkat (ECIES X25519+AESGCM)."""
    ephemeral = X25519PrivateKey.generate()
    ephemeral_public = ephemeral.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    key = _shared_key(ephemeral, recipient_public_b64)
    nonce = os.urandom(NONCE_BYTES)
    ciphertext = AESGCM(key).encrypt(nonce, store_key, None)
    return json.dumps(
        {
            "v": WRAP_VERSION,
            "epk": b64e(ephemeral_public),
            "nonce": b64e(nonce),
            "ct": b64e(ciphertext),
        },
        separators=(",", ":"),
    )


def unwrap_store_key(recipient_private_b64: str, wrapped: str) -> bytes:
    blob = json.loads(wrapped)
    private = X25519PrivateKey.from_private_bytes(b64d(recipient_private_b64))
    key = _shared_key(private, blob["epk"])
    return AESGCM(key).decrypt(b64d(blob["nonce"]), b64d(blob["ct"]), None)


def generate_encryption_keypair() -> Tuple[str, str]:
    private = X25519PrivateKey.generate()
    private_raw = private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_raw = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return b64e(private_raw), b64e(public_raw)


def encrypt_payload(key: bytes, plaintext: bytes) -> Tuple[str, str]:
    nonce = os.urandom(NONCE_BYTES)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    return b64e(ciphertext), b64e(nonce)


def decrypt_payload(key: bytes, ciphertext_b64: str, nonce_b64: str) -> bytes:
    return AESGCM(key).decrypt(b64d(nonce_b64), b64d(ciphertext_b64), None)


def _password_key(password: str, salt: bytes, iterations: int = 200_000) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt_with_password(password: str, data: bytes) -> Dict[str, str]:
    salt = os.urandom(16)
    nonce = os.urandom(NONCE_BYTES)
    ciphertext = AESGCM(_password_key(password, salt)).encrypt(nonce, data, None)
    return {
        "salt": b64e(salt),
        "nonce": b64e(nonce),
        "ct": b64e(ciphertext),
    }


def decrypt_with_password(password: str, blob: Dict[str, str]) -> bytes:
    salt = b64d(blob["salt"])
    return AESGCM(_password_key(password, salt)).decrypt(
        b64d(blob["nonce"]), b64d(blob["ct"]), None
    )


def hlc_next(prev_wall: int, prev_counter: int, now_ms: int | None = None) -> Tuple[int, int]:
    """Jam logis hibrida: selalu naik walau jam dinding mundur (K-14)."""
    current = int(time.time() * 1000) if now_ms is None else int(now_ms)
    if current > prev_wall:
        return current, 0
    return int(prev_wall), int(prev_counter) + 1
