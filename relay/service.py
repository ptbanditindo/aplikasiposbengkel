"""Layanan relay: autentikasi perangkat, amplop, feed, ack, dan bootstrap.

Relay tidak membuka ciphertext, tidak menerapkan delta, dan tidak menyimpan
data bisnis. Semua fungsi di sini hanya mengelola metadata pengiriman (K-13,
K-23, K-24).
"""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from relay.ids import new_ulid
from relay.models import (
    RelayAck,
    RelayAudit,
    RelayCursor,
    RelayDevice,
    RelayEnvelope,
    RelayFeedCounter,
    RelayKeyWrap,
    RelayOwner,
    RelaySnapshot,
    RelayStoreAssignment,
    utcnow,
)
from services import premium_crypto

ENVELOPE_TTL = timedelta(days=90)
DEFAULT_DEVICE_LIMIT = 2


class RelayError(Exception):
    def __init__(self, message: str, *, status_code: int = 400, code: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


def _now() -> datetime:
    return utcnow()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _iso(value: Optional[datetime]) -> str:
    return value.isoformat() if value is not None else ""


def _audit(
    db: Session,
    *,
    owner_id: str,
    device_id: str = "",
    action: str,
    detail: Optional[Dict[str, Any]] = None,
) -> None:
    db.add(
        RelayAudit(
            owner_id=owner_id,
            device_id=device_id,
            action=action,
            detail=json.dumps(detail or {}, ensure_ascii=False, sort_keys=True)[:2000],
        )
    )


def ensure_owner(
    db: Session,
    owner_id: str,
    *,
    plan: str = "premium",
    license_expires_at: Optional[datetime] = None,
    device_limit: Optional[int] = None,
    signing_public_key: str = "",
) -> RelayOwner:
    owner = db.get(RelayOwner, owner_id)
    if owner is None:
        owner = RelayOwner(
            owner_id=owner_id,
            plan="premium" if plan == "premium" else "free",
            signing_public_key=signing_public_key,
            license_expires_at=license_expires_at,
            device_limit=device_limit or DEFAULT_DEVICE_LIMIT,
        )
        db.add(owner)
        db.flush()
    else:
        if signing_public_key:
            owner.signing_public_key = signing_public_key
        if license_expires_at is not None:
            owner.license_expires_at = license_expires_at
        if device_limit is not None:
            owner.device_limit = device_limit
    return owner


def _active_owner_devices(db: Session, owner_id: str) -> int:
    return len(
        [
            row
            for row in db.execute(
                select(RelayDevice.id).where(
                    RelayDevice.owner_id == owner_id,
                    RelayDevice.kind == "owner",
                    RelayDevice.revoked_at.is_(None),
                )
            ).scalars()
        ]
    )


def _assigned_stores(db: Session, device_id: str) -> List[str]:
    return [
        row.store_id
        for row in db.execute(
            select(RelayStoreAssignment)
            .where(RelayStoreAssignment.device_id == device_id)
            .order_by(RelayStoreAssignment.store_id)
        ).scalars()
    ]


def _assign(db: Session, device: RelayDevice, store_ids: Iterable[str]) -> None:
    for store_id in dict.fromkeys(str(item).strip() for item in store_ids):
        if not store_id:
            continue
        if db.get(RelayStoreAssignment, (device.id, store_id)) is None:
            db.add(
                RelayStoreAssignment(device_id=device.id, store_id=store_id)
            )


def _require_assigned(db: Session, device: RelayDevice, store_id: str) -> None:
    if db.get(RelayStoreAssignment, (device.id, store_id)) is None:
        raise RelayError(
            "Perangkat tidak ditugaskan ke toko ini.",
            status_code=403,
            code="store_not_assigned",
        )


def _device(db: Session, device_id: str) -> RelayDevice:
    device = db.get(RelayDevice, device_id)
    if device is None or device.revoked_at is not None:
        raise RelayError(
            "Perangkat tidak aktif atau tidak terdaftar.",
            status_code=404,
            code="device_not_found",
        )
    return device


def authenticate(db: Session, token: Optional[str]) -> RelayDevice:
    if not token:
        raise RelayError(
            "Token perangkat wajib dikirim.",
            status_code=401,
            code="device_token_required",
        )
    device = db.execute(
        select(RelayDevice).where(RelayDevice.token_hash == _hash_token(token))
    ).scalar_one_or_none()
    if device is None or device.revoked_at is not None:
        raise RelayError(
            "Token perangkat tidak valid.",
            status_code=401,
            code="device_token_invalid",
        )
    device.last_seen_at = _now()
    db.flush()
    return device


def register_device(
    db: Session,
    *,
    owner_id: str,
    nama: str,
    kind: str,
    public_key: str,
    encryption_key: str,
    store_ids: Sequence[str],
    employee_account_id: Optional[int] = None,
    device_id: Optional[str] = None,
    replacement_of: str = "",
    signing_public_key: str = "",
) -> Dict[str, Any]:
    kind_value = (kind or "owner").strip().lower()
    if kind_value not in {"owner", "employee"}:
        raise RelayError("Jenis perangkat harus owner atau employee.")
    owner = ensure_owner(
        db, owner_id, signing_public_key=signing_public_key
    )
    if kind_value == "owner" and not replacement_of:
        if _active_owner_devices(db, owner_id) >= max(1, owner.device_limit):
            raise RelayError(
                "Batas perangkat owner paket ini sudah terpakai.",
                status_code=403,
                code="device_limit",
            )
    if not public_key.strip() or not encryption_key.strip():
        raise RelayError("Kunci publik perangkat wajib diisi.")
    token = secrets.token_urlsafe(32)
    device = RelayDevice(
        id=device_id or new_ulid(),
        owner_id=owner_id,
        nama=(nama or "").strip()[:255] or "Perangkat",
        kind=kind_value,
        employee_account_id=employee_account_id,
        public_key=public_key.strip(),
        encryption_key=encryption_key.strip(),
        token_hash=_hash_token(token),
        replacement_of=replacement_of,
    )
    db.add(device)
    db.flush()
    _assign(db, device, store_ids)
    _audit(
        db,
        owner_id=owner_id,
        device_id=device.id,
        action="device.register",
        detail={"kind": kind_value, "stores": _assigned_stores(db, device.id)},
    )
    db.commit()
    return {"device": public_device(db, device), "token": token}


def public_device(db: Session, device: RelayDevice) -> Dict[str, Any]:
    return {
        "id": device.id,
        "owner_id": device.owner_id,
        "nama": device.nama,
        "kind": device.kind,
        "employee_account_id": device.employee_account_id,
        "public_key": device.public_key,
        "encryption_key": device.encryption_key,
        "stores": _assigned_stores(db, device.id),
        "replacement_of": device.replacement_of,
        "created_at": _iso(device.created_at),
        "last_seen_at": _iso(device.last_seen_at),
        "revoked_at": _iso(device.revoked_at),
    }


def assign_stores(
    db: Session, *, actor: RelayDevice, device_id: str, store_ids: Sequence[str]
) -> Dict[str, Any]:
    if actor.kind != "owner":
        raise RelayError("Hanya perangkat owner yang dapat menugaskan toko.", status_code=403)
    target = _device(db, device_id)
    if target.owner_id != actor.owner_id:
        raise RelayError("Perangkat milik owner lain.", status_code=403)
    _assign(db, target, store_ids)
    _audit(
        db,
        owner_id=actor.owner_id,
        device_id=actor.id,
        action="device.assign_stores",
        detail={"target": target.id, "stores": list(store_ids)},
    )
    db.commit()
    return public_device(db, target)


def revoke_device(
    db: Session, *, actor: RelayDevice, device_id: str, reason: str = ""
) -> Dict[str, Any]:
    target = _device(db, device_id)
    if actor.owner_id != target.owner_id:
        raise RelayError("Perangkat milik owner lain.", status_code=403)
    if actor.kind != "owner" and actor.id != target.id:
        raise RelayError("Hanya owner yang dapat mencabut perangkat lain.", status_code=403)
    target.revoked_at = _now()
    target.revoked_reason = (reason or "dicabut pemilik")[:255]
    _audit(
        db,
        owner_id=actor.owner_id,
        device_id=actor.id,
        action="device.revoke",
        detail={"target": target.id, "reason": target.revoked_reason},
    )
    db.commit()
    return public_device(db, target)


def claim_device(
    db: Session,
    *,
    actor: Optional[RelayDevice],
    old_device_id: str,
    public_key: str,
    encryption_key: str,
    nama: str = "",
) -> Dict[str, Any]:
    """Instal ulang: perangkat baru mengambil slot perangkat lama (K-22)."""
    old = _device(db, old_device_id)
    if actor is not None:
        if actor.owner_id != old.owner_id or actor.kind != "owner":
            raise RelayError(
                "Klaim perangkat hanya oleh owner dari akun yang sama.",
                status_code=403,
                code="owner_only",
            )
    if old.kind != "owner":
        raise RelayError(
            "Klaim slot hanya untuk perangkat owner; perangkat karyawan didaftarkan ulang.",
            status_code=400,
        )
    stores = _assigned_stores(db, old.id)
    old.revoked_at = _now()
    old.revoked_reason = "diganti perangkat baru"
    db.execute(delete(RelayKeyWrap).where(RelayKeyWrap.device_id == old.id))
    db.flush()
    created = register_device(
        db,
        owner_id=old.owner_id,
        nama=nama or old.nama,
        kind=old.kind,
        public_key=public_key,
        encryption_key=encryption_key,
        store_ids=stores,
        employee_account_id=old.employee_account_id,
        replacement_of=old.id,
    )
    _audit(
        db,
        owner_id=old.owner_id,
        device_id=created["device"]["id"],
        action="device.claim",
        detail={"old_device_id": old.id},
    )
    db.commit()
    return created


def put_key_wrap(
    db: Session,
    *,
    signer: RelayDevice,
    store_id: str,
    device_id: str,
    wrapped_key: str,
    signature: str,
) -> Dict[str, Any]:
    if signer.kind != "owner":
        raise RelayError("Hanya owner yang dapat membungkus kunci toko.", status_code=403)
    target = _device(db, device_id)
    if target.owner_id != signer.owner_id:
        raise RelayError("Perangkat milik owner lain.", status_code=403)
    _require_assigned(db, target, store_id)
    payload = premium_crypto.canonical_json(
        {"store_id": store_id, "device_id": target.id, "wrapped_key": wrapped_key}
    )
    owner = db.get(RelayOwner, signer.owner_id)
    verification_key = (
        owner.signing_public_key
        if owner is not None and owner.signing_public_key
        else signer.public_key
    )
    if not premium_crypto.verify(verification_key, payload, signature):
        raise RelayError(
            "Tanda tangan kunci toko tidak valid.",
            status_code=400,
            code="signature_invalid",
        )
    row = db.get(RelayKeyWrap, (store_id, target.id))
    if row is None:
        row = RelayKeyWrap(store_id=store_id, device_id=target.id)
        db.add(row)
    row.wrapped_key = wrapped_key
    row.owner_signature = signature
    row.signed_by_device_id = signer.id
    _audit(
        db,
        owner_id=signer.owner_id,
        device_id=signer.id,
        action="key.wrap",
        detail={"store_id": store_id, "device_id": target.id},
    )
    db.commit()
    return {
        "store_id": store_id,
        "device_id": target.id,
        "wrapped_key": wrapped_key,
        "owner_signature": signature,
    }


def get_key_wrap(
    db: Session, *, device: RelayDevice, store_id: str
) -> Dict[str, Any]:
    _require_assigned(db, device, store_id)
    row = db.get(RelayKeyWrap, (store_id, device.id))
    if row is None:
        raise RelayError(
            "Kunci toko belum dibungkus untuk perangkat ini.",
            status_code=404,
            code="key_wrap_missing",
        )
    return {
        "store_id": store_id,
        "device_id": device.id,
        "wrapped_key": row.wrapped_key,
        "owner_signature": row.owner_signature,
    }


def _envelope_canonical(
    *,
    store_id: str,
    sender_device_id: str,
    recipient_device_id: str,
    seq: int,
    hlc_wall: int,
    hlc_counter: int,
    idempotency_key: str,
    ciphertext: str,
    nonce: str,
) -> bytes:
    return premium_crypto.canonical_json(
        {
            "v": 1,
            "store_id": store_id,
            "sender_device_id": sender_device_id,
            "recipient_device_id": recipient_device_id,
            "seq": int(seq),
            "hlc_wall": int(hlc_wall),
            "hlc_counter": int(hlc_counter),
            "idempotency_key": idempotency_key,
            "ciphertext": ciphertext,
            "nonce": nonce,
        }
    )


def _snapshot_canonical(
    *,
    store_id: str,
    device_id: str,
    checksum: str,
    store_seq: int,
    hlc_wall: int,
    hlc_counter: int,
) -> bytes:
    return premium_crypto.canonical_json(
        {
            "store_id": store_id,
            "device_id": device_id,
            "checksum": checksum,
            "store_seq": int(store_seq),
            "hlc_wall": int(hlc_wall),
            "hlc_counter": int(hlc_counter),
        }
    )


def _counter(db: Session, store_id: str) -> int:
    row = db.get(RelayFeedCounter, store_id)
    return int(row.last_seq or 0) if row is not None else 0


def _next_store_seq(db: Session, store_id: str) -> int:
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as dialect_insert
    else:
        from sqlalchemy.dialects.sqlite import insert as dialect_insert
    statement = (
        dialect_insert(RelayFeedCounter)
        .values(store_id=store_id, last_seq=1)
        .on_conflict_do_update(
            index_elements=[RelayFeedCounter.store_id],
            set_={
                "last_seq": RelayFeedCounter.last_seq + 1,
                "updated_at": _now(),
            },
        )
        .returning(RelayFeedCounter.last_seq)
    )
    return int(db.execute(statement).scalar_one())


def _cursor_value(db: Session, store_id: str, device_id: str) -> int:
    row = db.get(RelayCursor, (store_id, device_id))
    return int(row.last_seq or 0) if row is not None else 0


def _public_envelope(row: RelayEnvelope) -> Dict[str, Any]:
    return {
        "id": row.id,
        "store_id": row.store_id,
        "sender_device_id": row.sender_device_id,
        "recipient_device_id": row.recipient_device_id,
        "seq": row.seq,
        "store_seq": row.store_seq,
        "hlc_wall": row.hlc_wall,
        "hlc_counter": row.hlc_counter,
        "idempotency_key": row.idempotency_key,
        "ciphertext": row.ciphertext,
        "nonce": row.nonce,
        "signature": row.signature,
        "created_at": _iso(row.created_at),
        "expires_at": _iso(row.expires_at),
    }


def submit_envelope(
    db: Session,
    *,
    device: RelayDevice,
    store_id: str,
    sender_device_id: str,
    recipient_device_id: str,
    seq: int,
    hlc_wall: int,
    hlc_counter: int,
    idempotency_key: str,
    ciphertext: str,
    nonce: str,
    signature: str,
) -> Dict[str, Any]:
    if sender_device_id and sender_device_id != device.id:
        raise RelayError("Pengirim amplop harus perangkat yang terautentikasi.", status_code=403)
    _require_assigned(db, device, store_id)
    if recipient_device_id:
        recipient = _device(db, recipient_device_id)
        if recipient.owner_id != device.owner_id:
            raise RelayError("Penerima amplop milik owner lain.", status_code=403)
        _require_assigned(db, recipient, store_id)
        if recipient.id == device.id:
            raise RelayError("Penerima amplop tidak boleh pengirim.")
    canonical = _envelope_canonical(
        store_id=store_id,
        sender_device_id=device.id,
        recipient_device_id=recipient_device_id,
        seq=seq,
        hlc_wall=hlc_wall,
        hlc_counter=hlc_counter,
        idempotency_key=idempotency_key,
        ciphertext=ciphertext,
        nonce=nonce,
    )
    if not premium_crypto.verify(device.public_key, canonical, signature):
        raise RelayError(
            "Tanda tangan amplop tidak valid.",
            status_code=400,
            code="signature_invalid",
        )
    if idempotency_key:
        existing = db.execute(
            select(RelayEnvelope).where(
                RelayEnvelope.idempotency_key == idempotency_key
            )
        ).scalar_one_or_none()
        if existing is not None:
            return {"envelope": _public_envelope(existing), "created": False}
    duplicate_seq = db.execute(
        select(RelayEnvelope).where(
            RelayEnvelope.sender_device_id == device.id,
            RelayEnvelope.seq == int(seq),
        )
    ).scalar_one_or_none()
    if duplicate_seq is not None:
        raise RelayError(
            "Nomor urut perangkat sudah dipakai untuk delta lain.",
            status_code=409,
            code="seq_conflict",
        )
    row = RelayEnvelope(
        id=new_ulid(),
        owner_id=device.owner_id,
        store_id=store_id,
        sender_device_id=device.id,
        recipient_device_id=recipient_device_id or "",
        seq=int(seq),
        store_seq=_next_store_seq(db, store_id),
        hlc_wall=int(hlc_wall),
        hlc_counter=int(hlc_counter),
        idempotency_key=idempotency_key or new_ulid(),
        ciphertext=ciphertext,
        nonce=nonce,
        signature=signature,
        expires_at=_now() + ENVELOPE_TTL,
    )
    db.add(row)
    _audit(
        db,
        owner_id=device.owner_id,
        device_id=device.id,
        action="envelope.submit",
        detail={"store_id": store_id, "store_seq": row.store_seq},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise RelayError(
            "Nomor feed toko sedang dipakai; kirim ulang amplop.",
            status_code=409,
            code="feed_conflict",
        ) from exc
    return {"envelope": _public_envelope(row), "created": True}


def feed(
    db: Session,
    *,
    device: RelayDevice,
    store_id: str,
    since_seq: int = 0,
    limit: int = 200,
) -> Dict[str, Any]:
    _require_assigned(db, device, store_id)
    start = max(0, int(since_seq))
    capped = max(1, min(int(limit), 500))
    rows = list(
        db.execute(
            select(RelayEnvelope)
            .where(
                RelayEnvelope.store_id == store_id,
                RelayEnvelope.store_seq > start,
                RelayEnvelope.sender_device_id != device.id,
                RelayEnvelope.recipient_device_id.in_(["", device.id]),
                RelayEnvelope.expires_at >= _now(),
            )
            .order_by(RelayEnvelope.store_seq)
            .limit(capped + 1)
        ).scalars()
    )
    has_more = len(rows) > capped
    rows = rows[:capped]
    counter = _counter(db, store_id)
    cursor = _cursor_value(db, store_id, device.id)
    oldest = int(rows[0].store_seq) if rows else 0
    if counter <= start:
        snapshot_required = False
    elif not rows:
        snapshot_required = True
    else:
        snapshot_required = oldest > start + 1
    return {
        "store_id": store_id,
        "device_id": device.id,
        "cursor": cursor,
        "since_seq": start,
        "oldest_seq": oldest,
        "latest_seq": counter,
        "next_seq": int(rows[-1].store_seq) if rows else start,
        "has_more": has_more,
        "snapshot_required": snapshot_required,
        "envelopes": [_public_envelope(row) for row in rows],
    }


def _active_recipients(db: Session, envelope: RelayEnvelope) -> List[str]:
    if envelope.recipient_device_id:
        candidate_ids = [envelope.recipient_device_id]
    else:
        candidate_ids = [
            row.device_id
            for row in db.execute(
                select(RelayStoreAssignment).where(
                    RelayStoreAssignment.store_id == envelope.store_id
                )
            ).scalars()
        ]
    active: List[str] = []
    for row_id in candidate_ids:
        if row_id == envelope.sender_device_id:
            continue
        device = db.get(RelayDevice, row_id)
        if device is None or device.revoked_at is not None:
            continue
        if _cursor_value(db, envelope.store_id, row_id) >= int(envelope.store_seq):
            continue
        active.append(row_id)
    return active


def _prune_envelope(db: Session, envelope_id: str) -> int:
    envelope = db.get(RelayEnvelope, envelope_id)
    if envelope is None:
        return 0
    acked = {
        row.device_id
        for row in db.execute(
            select(RelayAck).where(RelayAck.envelope_id == envelope_id)
        ).scalars()
    }
    recipients = _active_recipients(db, envelope)
    if recipients and not set(recipients).issubset(acked):
        return 0
    db.execute(delete(RelayAck).where(RelayAck.envelope_id == envelope_id))
    db.execute(delete(RelayEnvelope).where(RelayEnvelope.id == envelope_id))
    return 1


def ack_feed(
    db: Session, *, device: RelayDevice, store_id: str, last_seq: int
) -> Dict[str, Any]:
    _require_assigned(db, device, store_id)
    target = max(0, int(last_seq))
    counter = _counter(db, store_id)
    if target > counter:
        raise RelayError(
            "Kursor melewati perubahan terakhir toko.",
            status_code=400,
            code="cursor_ahead",
        )
    row = db.get(RelayCursor, (store_id, device.id))
    if row is None:
        row = RelayCursor(store_id=store_id, device_id=device.id, last_seq=0)
        db.add(row)
        db.flush()
    previous = int(row.last_seq or 0)
    touched = [
        envelope_id
        for envelope_id in db.execute(
            select(RelayEnvelope.id).where(
                RelayEnvelope.store_id == store_id,
                RelayEnvelope.store_seq > previous,
                RelayEnvelope.store_seq <= target,
                RelayEnvelope.recipient_device_id.in_(["", device.id]),
            )
        ).scalars()
    ]
    for envelope_id in touched:
        if db.get(RelayAck, (envelope_id, device.id)) is None:
            db.add(RelayAck(envelope_id=envelope_id, device_id=device.id))
    db.flush()
    pruned = sum(_prune_envelope(db, envelope_id) for envelope_id in touched)
    row.last_seq = max(previous, target)
    row.updated_at = _now()
    _audit(
        db,
        owner_id=device.owner_id,
        device_id=device.id,
        action="feed.ack",
        detail={"store_id": store_id, "last_seq": row.last_seq},
    )
    db.commit()
    return {
        "store_id": store_id,
        "device_id": device.id,
        "last_seq": row.last_seq,
        "latest_seq": counter,
        "pruned": pruned,
    }


def create_snapshot(
    db: Session,
    *,
    device: RelayDevice,
    store_id: str,
    store_seq: int,
    ciphertext: str,
    nonce: str,
    signature: str,
    checksum: str,
    hlc_wall: int = 0,
    hlc_counter: int = 0,
) -> Dict[str, Any]:
    _require_assigned(db, device, store_id)
    if device.kind != "owner":
        raise RelayError(
            "Snapshot hanya dibuat dari perangkat owner.",
            status_code=403,
            code="owner_only",
        )
    counter = _counter(db, store_id)
    if int(store_seq) > counter:
        raise RelayError(
            "Posisi snapshot melewati perubahan terakhir toko.",
            status_code=400,
            code="snapshot_ahead",
        )
    canonical = _snapshot_canonical(
        store_id=store_id,
        device_id=device.id,
        checksum=checksum,
        store_seq=int(store_seq),
        hlc_wall=int(hlc_wall),
        hlc_counter=int(hlc_counter),
    )
    if not premium_crypto.verify(device.public_key, canonical, signature):
        raise RelayError(
            "Tanda tangan snapshot tidak valid.",
            status_code=400,
            code="signature_invalid",
        )
    row = RelaySnapshot(
        id=new_ulid(),
        owner_id=device.owner_id,
        store_id=store_id,
        device_id=device.id,
        store_seq=int(store_seq),
        hlc_wall=int(hlc_wall),
        hlc_counter=int(hlc_counter),
        ciphertext=ciphertext,
        nonce=nonce,
        signature=signature,
        checksum=checksum,
        expires_at=_now() + ENVELOPE_TTL,
    )
    db.add(row)
    _audit(
        db,
        owner_id=device.owner_id,
        device_id=device.id,
        action="snapshot.create",
        detail={"store_id": store_id, "store_seq": row.store_seq},
    )
    db.commit()
    return {
        "id": row.id,
        "store_id": store_id,
        "store_seq": row.store_seq,
        "checksum": checksum,
        "expires_at": _iso(row.expires_at),
    }


def _public_snapshot(row: RelaySnapshot) -> Dict[str, Any]:
    return {
        "id": row.id,
        "store_id": row.store_id,
        "device_id": row.device_id,
        "store_seq": row.store_seq,
        "ciphertext": row.ciphertext,
        "nonce": row.nonce,
        "signature": row.signature,
        "checksum": row.checksum,
        "hlc_wall": row.hlc_wall,
        "hlc_counter": row.hlc_counter,
        "created_at": _iso(row.created_at),
        "expires_at": _iso(row.expires_at),
    }


def latest_snapshot(db: Session, *, device: RelayDevice, store_id: str) -> Dict[str, Any]:
    _require_assigned(db, device, store_id)
    row = db.execute(
        select(RelaySnapshot)
        .where(
            RelaySnapshot.store_id == store_id,
            RelaySnapshot.expires_at >= _now(),
        )
        .order_by(RelaySnapshot.created_at.desc())
    ).scalars().first()
    if row is None:
        raise RelayError(
            "Snapshot tidak tersedia atau sudah melewati TTL.",
            status_code=404,
            code="snapshot_missing",
        )
    return _public_snapshot(row)


def bootstrap(db: Session, *, device: RelayDevice, store_id: str) -> Dict[str, Any]:
    """Data awal perangkat baru: wrapped key, snapshot, dan posisi kursor."""
    _require_assigned(db, device, store_id)
    wrap = db.get(RelayKeyWrap, (store_id, device.id))
    cursor = _cursor_value(db, store_id, device.id)
    counter = _counter(db, store_id)
    snapshot = db.execute(
        select(RelaySnapshot)
        .where(
            RelaySnapshot.store_id == store_id,
            RelaySnapshot.expires_at >= _now(),
        )
        .order_by(RelaySnapshot.created_at.desc())
    ).scalars().first()
    usable = snapshot if snapshot is not None and snapshot.store_seq > cursor else None
    return {
        "store_id": store_id,
        "device_id": device.id,
        "wrapped_key": wrap.wrapped_key if wrap is not None else "",
        "owner_signature": wrap.owner_signature if wrap is not None else "",
        "key_wrap_required": wrap is None,
        "cursor": cursor,
        "latest_seq": counter,
        "snapshot_required": bool(counter > cursor and usable is None),
        "snapshot": _public_snapshot(usable) if usable is not None else None,
    }


def purge_expired(db: Session, *, owner_id: Optional[str] = None) -> Dict[str, int]:
    envelope_query = select(RelayEnvelope.id).where(
        RelayEnvelope.expires_at < _now()
    )
    if owner_id:
        envelope_query = envelope_query.where(RelayEnvelope.owner_id == owner_id)
    envelope_ids = list(db.execute(envelope_query).scalars())
    if envelope_ids:
        db.execute(delete(RelayAck).where(RelayAck.envelope_id.in_(envelope_ids)))
        db.execute(delete(RelayEnvelope).where(RelayEnvelope.id.in_(envelope_ids)))
    snapshot_query = delete(RelaySnapshot).where(
        RelaySnapshot.expires_at < _now()
    )
    if owner_id:
        snapshot_query = snapshot_query.where(RelaySnapshot.owner_id == owner_id)
    snapshots = db.execute(snapshot_query).rowcount or 0
    db.commit()
    return {"envelopes": len(envelope_ids), "snapshots": int(snapshots)}
