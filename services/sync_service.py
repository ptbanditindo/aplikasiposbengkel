"""Relay dan sinkronisasi premium: outbox, amplop terenkripsi, snapshot, konflik.

Server hanya menyimpan ciphertext. Verifikasi tanda tangan memakai kunci publik
perangkat; isi delta hanya dapat dibuka oleh perangkat yang memegang kunci toko.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session

from database import session as db_session
from database import store_registry
from database.models import (
    AppliedDelta,
    Device,
    DeviceKeyWrap,
    DeviceStore,
    EmployeeAccount,
    OutboxItem,
    PermissionSnapshot,
    RelayAck,
    RelayEnvelope,
    RelaySnapshot,
    StockItem,
    StoreHub,
    StoreKey,
    SyncConflict,
    SyncPeerState,
    utcnow,
)
from services import account_service, device_service, license_service, premium_crypto
from services.errors import (
    BusinessValidationError,
    ConflictError,
    FeatureLockedError,
    NotFoundError,
)

ENVELOPE_TTL = timedelta(days=90)
MONEY_ENTITIES = frozenset({"payment", "nota", "retur", "void", "piutang"})


def _now() -> datetime:
    return utcnow()


def _require_premium() -> None:
    from services import entitlement_service

    if not entitlement_service.is_premium():
        raise FeatureLockedError(
            entitlement_service.LOCKED_MESSAGE, code="premium_locked"
        )


def _device(db: Session, device_id: str) -> Device:
    device = db.get(Device, device_id)
    if device is None or device.revoked_at is not None:
        raise NotFoundError("Perangkat tidak aktif atau tidak terdaftar.")
    return device


def _assigned(db: Session, device_id: str, store_id: str) -> None:
    row = db.get(DeviceStore, (device_id, store_id))
    if row is None:
        raise FeatureLockedError(
            "Perangkat tidak ditugaskan ke toko ini.", code="store_not_assigned"
        )


def _owner_id(db: Session) -> str:
    owner = license_service.get_owner(db)
    if owner is None:
        raise BusinessValidationError("ID owner belum diterbitkan.")
    return owner.owner_id


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


def sign_envelope(device_private_b64: str, fields: Dict[str, Any]) -> str:
    return premium_crypto.sign(
        device_private_b64, _envelope_canonical(**fields)
    )


def build_envelope(
    *,
    device_private_b64: str,
    store_key: bytes,
    store_id: str,
    sender_device_id: str,
    recipient_device_id: str,
    seq: int,
    hlc_wall: int,
    hlc_counter: int,
    idempotency_key: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    plaintext = premium_crypto.canonical_json(
        {
            "entity": payload.get("entity"),
            "action": payload.get("action"),
            "entity_id": payload.get("entity_id", ""),
            "payload": payload.get("payload", {}),
            "seq": int(seq),
            "hlc_wall": int(hlc_wall),
            "hlc_counter": int(hlc_counter),
            "idempotency_key": idempotency_key,
        }
    )
    ciphertext, nonce = premium_crypto.encrypt_payload(store_key, plaintext)
    fields = {
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
    return {
        **fields,
        "signature": sign_envelope(device_private_b64, fields),
    }


def submit_envelope(
    db: Session,
    *,
    store_id: str,
    sender_device_id: str,
    recipient_device_id: str = "",
    seq: int,
    hlc_wall: int,
    hlc_counter: int,
    idempotency_key: str,
    ciphertext: str,
    nonce: str,
    signature: str,
) -> Dict[str, Any]:
    _require_premium()
    sender = _device(db, sender_device_id)
    _assigned(db, sender_device_id, store_id)
    if recipient_device_id:
        recipient = _device(db, recipient_device_id)
        _assigned(db, recipient.id, store_id)
        if recipient.id == sender.id:
            raise BusinessValidationError("Penerima amplop tidak boleh pengirim.")
    canonical = _envelope_canonical(
        store_id=store_id,
        sender_device_id=sender_device_id,
        recipient_device_id=recipient_device_id,
        seq=seq,
        hlc_wall=hlc_wall,
        hlc_counter=hlc_counter,
        idempotency_key=idempotency_key,
        ciphertext=ciphertext,
        nonce=nonce,
    )
    if not premium_crypto.verify(
        device_service.signing_key(sender), canonical, signature
    ):
        raise BusinessValidationError("Tanda tangan amplop tidak valid.")
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
            RelayEnvelope.sender_device_id == sender_device_id,
            RelayEnvelope.seq == int(seq),
        )
    ).scalar_one_or_none()
    if duplicate_seq is not None:
        raise ConflictError(
            "Nomor urut perangkat sudah dipakai untuk delta lain."
        )
    envelope = RelayEnvelope(
        id=store_registry.new_ulid(),
        owner_id=_owner_id(db),
        store_id=store_id,
        sender_device_id=sender_device_id,
        recipient_device_id=recipient_device_id or "",
        seq=int(seq),
        hlc_wall=int(hlc_wall),
        hlc_counter=int(hlc_counter),
        idempotency_key=idempotency_key or store_registry.new_ulid(),
        ciphertext=ciphertext,
        nonce=nonce,
        signature=signature,
        expires_at=_now() + ENVELOPE_TTL,
    )
    db.add(envelope)
    db.commit()
    return {"envelope": _public_envelope(envelope), "created": True}


def _public_envelope(row: RelayEnvelope) -> Dict[str, Any]:
    return {
        "id": row.id,
        "store_id": row.store_id,
        "sender_device_id": row.sender_device_id,
        "recipient_device_id": row.recipient_device_id,
        "seq": row.seq,
        "hlc_wall": row.hlc_wall,
        "hlc_counter": row.hlc_counter,
        "idempotency_key": row.idempotency_key,
        "ciphertext": row.ciphertext,
        "nonce": row.nonce,
        "signature": row.signature,
        "created_at": row.created_at,
        "expires_at": row.expires_at,
    }


def list_envelopes(
    db: Session,
    *,
    device_id: str,
    store_id: Optional[str] = None,
    since: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    _require_premium()
    device = _device(db, device_id)
    query = select(RelayEnvelope).where(
        RelayEnvelope.recipient_device_id.in_(["", device.id]),
        RelayEnvelope.sender_device_id != device.id,
        RelayEnvelope.expires_at >= _now(),
        ~exists().where(
            RelayAck.envelope_id == RelayEnvelope.id,
            RelayAck.device_id == device.id,
        ),
    )
    if store_id:
        _assigned(db, device.id, store_id)
        query = query.where(RelayEnvelope.store_id == store_id)
    else:
        assigned = [
            row.store_id
            for row in db.execute(
                select(DeviceStore).where(DeviceStore.device_id == device.id)
            ).scalars()
        ]
        query = query.where(RelayEnvelope.store_id.in_(assigned or [""]))
    if since is not None:
        query = query.where(RelayEnvelope.created_at >= since)
    query = query.order_by(RelayEnvelope.hlc_wall, RelayEnvelope.hlc_counter)
    return [_public_envelope(row) for row in db.execute(query).scalars()]


def ack_envelope(db: Session, envelope_id: str, device_id: str) -> Dict[str, Any]:
    envelope = db.get(RelayEnvelope, envelope_id)
    if envelope is None:
        raise NotFoundError("Amplop tidak ditemukan.")
    _device(db, device_id)
    _assigned(db, device_id, envelope.store_id)
    if db.get(RelayAck, (envelope_id, device_id)) is None:
        db.add(RelayAck(envelope_id=envelope_id, device_id=device_id))
        db.flush()
    if envelope.recipient_device_id:
        candidate_ids = [envelope.recipient_device_id]
    else:
        candidate_ids = [
            row.device_id
            for row in db.execute(
                select(DeviceStore).where(DeviceStore.store_id == envelope.store_id)
            ).scalars()
        ]
    active_recipients = [
        row_id
        for row_id in candidate_ids
        if row_id != envelope.sender_device_id
        and (db.get(Device, row_id) is not None)
        and db.get(Device, row_id).revoked_at is None
    ]
    acked = {
        row.device_id
        for row in db.execute(
            select(RelayAck).where(RelayAck.envelope_id == envelope_id)
        ).scalars()
    }
    if not active_recipients or set(active_recipients).issubset(acked):
        # Semua penerima aktif sudah mengakui delta; ciphertext tidak perlu
        # disimpan lagi (K-13). Outbox pengirim tetap dipertahankan.
        db.execute(delete(RelayAck).where(RelayAck.envelope_id == envelope_id))
        db.delete(envelope)
        db.commit()
        return {"envelope_id": envelope_id, "acked": True, "complete": True}
    db.commit()
    return {"envelope_id": envelope_id, "acked": True, "complete": False}


def purge_expired(db: Session) -> int:
    """Hapus amplop setelah TTL; outbox pengirim tidak ikut terhapus (K-13)."""
    expired = [
        row.id
        for row in db.execute(
            select(RelayEnvelope).where(RelayEnvelope.expires_at < _now())
        ).scalars()
    ]
    if expired:
        db.execute(delete(RelayAck).where(RelayAck.envelope_id.in_(expired)))
        db.execute(delete(RelayEnvelope).where(RelayEnvelope.id.in_(expired)))
        db.commit()
    return len(expired)


# --- Outbox lokal ---------------------------------------------------------


def _next_seq(store_db: Session, device_id: str) -> int:
    last = store_db.execute(
        select(OutboxItem.seq)
        .where(OutboxItem.device_id == device_id)
        .order_by(OutboxItem.seq.desc())
    ).scalars().first()
    return int(last or 0) + 1


def _next_hlc(store_db: Session, device_id: str) -> tuple[int, int]:
    row = store_db.execute(
        select(OutboxItem)
        .where(OutboxItem.device_id == device_id)
        .order_by(OutboxItem.hlc_wall.desc(), OutboxItem.hlc_counter.desc())
    ).scalars().first()
    prev = (row.hlc_wall, row.hlc_counter) if row is not None else (0, 0)
    return premium_crypto.hlc_next(prev[0], prev[1])


def enqueue(
    store_db: Session,
    *,
    device_id: str,
    entity: str,
    action: str,
    payload: Dict[str, Any],
    entity_id: str = "",
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    if idempotency_key:
        existing = store_db.execute(
            select(OutboxItem).where(
                OutboxItem.idempotency_key == idempotency_key
            )
        ).scalar_one_or_none()
        if existing is not None:
            return _public_outbox(existing)
    seq = _next_seq(store_db, device_id)
    wall, counter = _next_hlc(store_db, device_id)
    key = idempotency_key or premium_crypto.sha256_hex(
        premium_crypto.canonical_json(
            {
                "device_id": device_id,
                "seq": seq,
                "entity": entity,
                "entity_id": entity_id,
                "action": action,
                "payload": payload,
            }
        )
    )
    item = OutboxItem(
        device_id=device_id,
        seq=seq,
        hlc_wall=wall,
        hlc_counter=counter,
        idempotency_key=key,
        entity=entity,
        entity_id=str(entity_id),
        action=action,
        payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
        status="pending",
    )
    store_db.add(item)
    store_db.commit()
    return _public_outbox(item)


def _public_outbox(row: OutboxItem) -> Dict[str, Any]:
    return {
        "id": row.id,
        "device_id": row.device_id,
        "seq": row.seq,
        "hlc_wall": row.hlc_wall,
        "hlc_counter": row.hlc_counter,
        "idempotency_key": row.idempotency_key,
        "entity": row.entity,
        "entity_id": row.entity_id,
        "action": row.action,
        "payload": json.loads(row.payload_json or "{}"),
        "status": row.status,
        "retry_count": row.retry_count,
        "error": row.error,
        "created_at": row.created_at,
        "sent_at": row.sent_at,
        "acked_at": row.acked_at,
    }


def list_outbox(
    store_db: Session, device_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    query = select(OutboxItem)
    if device_id:
        query = query.where(OutboxItem.device_id == device_id)
    rows = store_db.execute(
        query.order_by(OutboxItem.seq.desc())
    ).scalars()
    return [_public_outbox(row) for row in rows]


def list_conflicts(
    store_db: Session, *, unresolved_only: bool = True
) -> List[Dict[str, Any]]:
    query = select(SyncConflict)
    if unresolved_only:
        query = query.where(SyncConflict.resolved_at.is_(None))
    rows = store_db.execute(
        query.order_by(SyncConflict.created_at.desc())
    ).scalars()
    return [
        {
            "id": row.id,
            "outbox_id": row.outbox_id,
            "entity": row.entity,
            "entity_id": row.entity_id,
            "reason": row.reason,
            "detail": json.loads(row.detail_json or "{}"),
            "created_at": row.created_at,
            "resolved_at": row.resolved_at,
        }
        for row in rows
    ]


def resolve_conflict(
    store_db: Session, conflict_id: int, resolution: str
) -> Dict[str, Any]:
    row = store_db.get(SyncConflict, conflict_id)
    if row is None:
        raise NotFoundError("Konflik sinkronisasi tidak ditemukan.")
    row.resolved_at = _now()
    row.reason = f"{row.reason}:{resolution}"[:64]
    store_db.commit()
    return {"id": row.id, "resolved_at": row.resolved_at, "resolution": resolution}


def pending(store_db: Session, device_id: Optional[str] = None) -> List[OutboxItem]:
    query = select(OutboxItem).where(OutboxItem.status == "pending")
    if device_id:
        query = query.where(OutboxItem.device_id == device_id)
    return list(store_db.execute(query.order_by(OutboxItem.seq)).scalars())


def mark_sent(item: OutboxItem) -> None:
    item.status = "sent"
    item.sent_at = _now()


def mark_acked(item: OutboxItem) -> None:
    item.status = "acked"
    item.acked_at = _now()
    item.error = ""


def mark_conflict(item: OutboxItem, reason: str) -> None:
    item.status = "conflict"
    item.error = reason


def sync_status(db: Session, store_db: Session, device_id: Optional[str] = None) -> Dict[str, Any]:
    query = select(OutboxItem)
    if device_id:
        query = query.where(OutboxItem.device_id == device_id)
    items = list(store_db.execute(query).scalars())
    pending_items = [item for item in items if item.status == "pending"]
    conflicts = list(
        store_db.execute(
            select(SyncConflict).where(SyncConflict.resolved_at.is_(None))
        ).scalars()
    )
    last = max(
        (item.acked_at for item in items if item.acked_at is not None),
        default=None,
    )
    assigned = []
    if device_id:
        assigned = [
            row.store_id
            for row in db.execute(
                select(DeviceStore).where(DeviceStore.device_id == device_id)
            ).scalars()
        ]
    peers = []
    for store_id in assigned:
        peer_ids = [
            row.device_id
            for row in db.execute(
                select(DeviceStore).where(DeviceStore.store_id == store_id)
            ).scalars()
        ]
        peers.append(
            {
                "store_id": store_id,
                "devices": peer_ids,
                "pending": len(pending_items),
            }
        )
    return {
        "device_id": device_id or "",
        "pending": len(pending_items),
        "oldest_pending_at": min(
            (item.created_at for item in pending_items), default=None
        ),
        "last_sync_at": last,
        "conflicts": len(conflicts),
        "peers": peers,
        "complete": len(pending_items) == 0 and len(conflicts) == 0,
    }


# --- Kunci toko -----------------------------------------------------------


def register_store_keys(
    db: Session,
    *,
    store_id: str,
    store_key: bytes,
    device_ids: Iterable[str],
    owner_private_key: str,
    hub_device_id: str = "",
) -> Dict[str, Any]:
    _require_premium()
    created = []
    for device_id in device_ids:
        device = _device(db, device_id)
        encryption = device_service.encryption_key(device)
        if not encryption:
            continue
        wrapped = premium_crypto.wrap_store_key(encryption, store_key)
        payload = {"store_id": store_id, "device_id": device.id, "wrapped_key": wrapped}
        signature = premium_crypto.sign(
            owner_private_key, premium_crypto.canonical_json(payload)
        )
        row = db.get(DeviceKeyWrap, (store_id, device.id))
        if row is None:
            row = DeviceKeyWrap(store_id=store_id, device_id=device.id)
            db.add(row)
        row.wrapped_key = wrapped
        row.owner_signature = signature
        db.flush()
        created.append(device.id)
    hub = hub_device_id or ""
    if not hub:
        hub_row = db.get(StoreHub, store_id)
        hub = hub_row.device_id if hub_row is not None else ""
    if hub:
        hub_device = _device(db, hub)
        encryption = device_service.encryption_key(hub_device)
        if encryption:
            wrapped = premium_crypto.wrap_store_key(encryption, store_key)
            signature = premium_crypto.sign(
                owner_private_key,
                premium_crypto.canonical_json(
                    {"store_id": store_id, "device_id": hub, "wrapped_key": wrapped}
                ),
            )
            key_row = db.get(StoreKey, store_id)
            if key_row is None:
                key_row = StoreKey(store_id=store_id)
                db.add(key_row)
            key_row.wrapped_key = wrapped
            key_row.hub_device_id = hub
            key_row.owner_signature = signature
    db.commit()
    return {"store_id": store_id, "devices": created, "hub_device_id": hub}


def store_key_wrap(db: Session, store_id: str, device_id: str) -> Dict[str, Any]:
    _require_premium()
    _device(db, device_id)
    _assigned(db, device_id, store_id)
    row = db.get(DeviceKeyWrap, (store_id, device_id))
    if row is None:
        raise NotFoundError("Kunci toko belum dibungkus untuk perangkat ini.")
    return {
        "store_id": store_id,
        "device_id": device_id,
        "wrapped_key": row.wrapped_key,
        "owner_signature": row.owner_signature,
    }


def _active_assigned_devices(db: Session, store_id: str) -> List[str]:
    ids = [
        row.device_id
        for row in db.execute(
            select(DeviceStore).where(DeviceStore.store_id == store_id)
        ).scalars()
    ]
    active: List[str] = []
    for device_id in ids:
        device = db.get(Device, device_id)
        if device is not None and device.revoked_at is None:
            active.append(device_id)
    return active


def _requeue_outbox_for_rekey(store_id: str) -> int:
    """Tandai outbox terkirim untuk dikirim ulang dengan kunci baru (K-22)."""
    entry = store_registry.get_store(store_id)
    if entry is None:
        raise NotFoundError("Toko tidak ditemukan.")
    path = store_registry.resolve_database_path(entry)
    if not path.exists():
        return 0
    owned_engine = None
    if entry.get("store_id") == store_registry.PRIMARY_STORE_ID:
        bind = db_session.engine
    else:
        owned_engine = db_session.build_engine(f"sqlite:///{path.as_posix()}")
        bind = owned_engine
    try:
        with db_session.store_session(bind) as store_db:
            items = list(
                store_db.execute(
                    select(OutboxItem).where(OutboxItem.status.in_(("pending", "sent")))
                ).scalars()
            )
            for item in items:
                item.status = "pending"
                item.sent_at = None
                item.error = "Kunci toko berubah; kirim ulang dengan kunci baru."
            store_db.commit()
            return len(items)
    finally:
        if owned_engine is not None:
            owned_engine.dispose()


def rotate_store_key(
    db: Session,
    *,
    store_id: str,
    store_key: bytes,
    device_ids: Iterable[str],
    owner_private_key: str,
    hub_device_id: str = "",
) -> Dict[str, Any]:
    """Ganti kunci toko setelah pencabutan perangkat (K-22).

    Kunci baru hanya dibungkus untuk perangkat aktif yang masih ditugaskan.
    Amplop dan snapshot lama dihapus karena tidak dapat dibuka dengan kunci baru;
    outbox lokal ditandai agar dikirim ulang dengan enkripsi baru.
    """
    _require_premium()
    targets: List[str] = []
    for device_id in device_ids:
        device = _device(db, device_id)
        _assigned(db, device.id, store_id)
        if device.id not in targets:
            targets.append(device.id)
    if not targets:
        targets = _active_assigned_devices(db, store_id)
    if not targets:
        raise BusinessValidationError(
            "Tidak ada perangkat aktif yang dapat menerima kunci baru."
        )

    hub_row = db.get(StoreHub, store_id)
    hub = hub_device_id or (hub_row.device_id if hub_row is not None else "")
    if hub:
        hub_device = _device(db, hub)
        _assigned(db, hub_device.id, store_id)
        if hub_device.id not in targets:
            targets.append(hub_device.id)

    # Bungkus lama milik perangkat yang dicabut/dikeluarkan harus hilang.
    stale = [
        row
        for row in db.execute(
            select(DeviceKeyWrap).where(DeviceKeyWrap.store_id == store_id)
        ).scalars()
        if row.device_id not in targets
    ]
    for row in stale:
        db.delete(row)
    db.flush()

    register_store_keys(
        db,
        store_id=store_id,
        store_key=store_key,
        device_ids=targets,
        owner_private_key=owner_private_key,
        hub_device_id=hub,
    )

    rotated_at = _now()
    key_row = db.get(StoreKey, store_id)
    if key_row is not None:
        key_row.rotated_at = rotated_at
    for row in db.execute(
        select(DeviceKeyWrap).where(DeviceKeyWrap.store_id == store_id)
    ).scalars():
        row.rotated_at = rotated_at
    envelopes = db.execute(
        delete(RelayEnvelope).where(RelayEnvelope.store_id == store_id)
    ).rowcount or 0
    snapshots = db.execute(
        delete(RelaySnapshot).where(RelaySnapshot.store_id == store_id)
    ).rowcount or 0
    db.commit()

    requeued = _requeue_outbox_for_rekey(store_id)
    return {
        "store_id": store_id,
        "devices": targets,
        "hub_device_id": hub,
        "rotated_at": rotated_at,
        "dropped_envelopes": envelopes,
        "dropped_snapshots": snapshots,
        "requeued_outbox": requeued,
    }


# --- Verifikasi dan penerapan delta --------------------------------------


def verify_and_decrypt(
    db: Session, envelope: RelayEnvelope, store_key: bytes
) -> Dict[str, Any]:
    sender = _device(db, envelope.sender_device_id)
    canonical = _envelope_canonical(
        store_id=envelope.store_id,
        sender_device_id=envelope.sender_device_id,
        recipient_device_id=envelope.recipient_device_id,
        seq=envelope.seq,
        hlc_wall=envelope.hlc_wall,
        hlc_counter=envelope.hlc_counter,
        idempotency_key=envelope.idempotency_key,
        ciphertext=envelope.ciphertext,
        nonce=envelope.nonce,
    )
    if not premium_crypto.verify(
        device_service.signing_key(sender), canonical, envelope.signature
    ):
        raise BusinessValidationError("Tanda tangan delta tidak valid.")
    plaintext = premium_crypto.decrypt_payload(
        store_key, envelope.ciphertext, envelope.nonce
    )
    return json.loads(plaintext.decode("utf-8"))


def _hub_allows(db: Session, envelope: RelayEnvelope) -> bool:
    hub = db.get(StoreHub, envelope.store_id)
    return (
        hub is not None
        and hub.device_id == envelope.sender_device_id
        and hub.mode != "pending"
    )


def _apply_payload(
    store_db: Session,
    *,
    entity: str,
    action: str,
    entity_id: str,
    payload: Dict[str, Any],
    idempotency_key: str,
    envelope_id: str = "",
) -> str:
    if store_db.get(AppliedDelta, idempotency_key) is not None:
        return "duplicate"
    if entity == "stock":
        item = store_db.get(StockItem, int(payload.get("stock_item_id") or 0))
        if item is None:
            raise NotFoundError("Barang stok pada delta tidak ditemukan.")
        if action == "delta":
            item.jumlah = int(item.jumlah or 0) + int(payload.get("qty") or 0)
        elif action == "opname":
            base = int(payload.get("base_jumlah") or 0)
            if int(item.jumlah or 0) != base:
                raise ConflictError("opname_bentrok")
            item.jumlah = int(payload.get("jumlah") or 0)
        else:
            raise BusinessValidationError("Aksi stok tidak dikenal.")
    elif entity in MONEY_ENTITIES:
        # Uang hanya diterima dari hub; nilai sudah ditulis di hub dan delta
        # di sini hanya menandai bahwa penerima sudah menerapkannya.
        if action not in {"apply", "nota", "payment", "retur", "void"}:
            raise BusinessValidationError("Aksi uang tidak dikenal.")
    else:
        raise BusinessValidationError(f"Entitas delta '{entity}' tidak dikenal.")
    store_db.add(
        AppliedDelta(
            idempotency_key=idempotency_key,
            envelope_id=envelope_id,
            entity=entity,
            entity_id=entity_id,
        )
    )
    return "applied"


def _verify_employee_permission(
    db: Session, device: Device, envelope: RelayEnvelope, data: Dict[str, Any]
) -> None:
    """Karyawan hanya boleh mengirim delta yang diizinkan snapshot bertanda tangan."""
    if device.kind != "employee" or not device.employee_account_id:
        return
    account = db.get(EmployeeAccount, device.employee_account_id)
    if account is None or not account.aktif:
        raise FeatureLockedError("Akun karyawan tidak aktif.", code="account_inactive")
    if envelope.store_id not in account_service.assigned_stores(account):
        raise FeatureLockedError(
            "Karyawan tidak ditugaskan ke toko ini.", code="store_not_assigned"
        )
    snapshot = db.execute(
        select(PermissionSnapshot)
        .where(PermissionSnapshot.employee_account_id == account.id)
        .order_by(PermissionSnapshot.version.desc())
    ).scalars().first()
    if snapshot is None:
        raise FeatureLockedError(
            "Snapshot izin karyawan belum tersedia.", code="permission_missing"
        )
    payload = json.loads(snapshot.payload_json or "{}")
    if not account_service.verify_snapshot(db, payload, snapshot.signature):
        raise FeatureLockedError(
            "Tanda tangan snapshot izin tidak valid.", code="permission_invalid"
        )
    if int(payload.get("permission_version") or 0) != int(
        account.permission_version or 0
    ):
        raise FeatureLockedError(
            "Izin karyawan sudah berubah; minta sinkronisasi ulang.",
            code="permission_stale",
        )
    if envelope.store_id not in (payload.get("stores") or []):
        raise FeatureLockedError(
            "Toko tidak tercantum pada izin karyawan.", code="store_not_assigned"
        )

    entity = str(data.get("entity") or "")
    action = str(data.get("action") or "")
    required: tuple[str, ...] = ()
    if entity == "stock" and action == "opname":
        required = ("opname",)
    elif entity == "stock" and action == "delta":
        qty = int((data.get("payload") or {}).get("qty") or 0)
        required = ("stok_masuk",) if qty > 0 else ("stok_keluar",)
    if required and not set(required) & set(payload.get("permissions") or []):
        raise FeatureLockedError(
            "Izin karyawan tidak mencukupi untuk delta ini.",
            code="permission_denied",
        )


def apply_envelope(
    db: Session,
    store_db: Session,
    *,
    envelope_id: str,
    device_id: str,
    store_key: bytes,
) -> Dict[str, Any]:
    _require_premium()
    device = _device(db, device_id)
    envelope = db.get(RelayEnvelope, envelope_id)
    if envelope is None:
        # Amplop yang sudah diakui semua penerima dihapus; ulangan tetap
        # dilaporkan idempoten lewat catatan delta yang sudah diterapkan.
        applied = store_db.execute(
            select(AppliedDelta).where(AppliedDelta.envelope_id == envelope_id)
        ).scalars().first()
        if applied is not None:
            return {"status": "duplicate", "envelope_id": envelope_id}
        raise NotFoundError("Amplop tidak ditemukan.")
    _assigned(db, device.id, envelope.store_id)
    if envelope.recipient_device_id and envelope.recipient_device_id != device.id:
        raise BusinessValidationError("Amplop bukan untuk perangkat ini.")
    if envelope.expires_at < _now():
        raise ConflictError("Amplop sudah melewati TTL; minta snapshot dari hub.")
    if envelope.idempotency_key in {
        row.idempotency_key
        for row in store_db.execute(select(AppliedDelta)).scalars()
    }:
        return {"status": "duplicate", "envelope_id": envelope_id}
    data = verify_and_decrypt(db, envelope, store_key)
    _verify_employee_permission(db, device, envelope, data)
    entity = str(data.get("entity") or "")
    action = str(data.get("action") or "")
    if entity in MONEY_ENTITIES and not _hub_allows(db, envelope):
        raise FeatureLockedError(
            "Delta uang hanya diterima dari hub toko aktif.", code="not_hub"
        )
    try:
        status = _apply_payload(
            store_db,
            entity=entity,
            action=action,
            entity_id=str(data.get("entity_id") or ""),
            payload=data.get("payload") or {},
            idempotency_key=envelope.idempotency_key,
            envelope_id=envelope.id,
        )
        store_db.commit()
    except ConflictError as exc:
        store_db.rollback()
        conflict = SyncConflict(
            entity=entity,
            entity_id=str(data.get("entity_id") or ""),
            reason=str(exc),
            detail_json=json.dumps(data, ensure_ascii=False, sort_keys=True),
        )
        store_db.add(conflict)
        store_db.commit()
        return {"status": "conflict", "reason": str(exc)}
    ack_envelope(db, envelope_id, device.id)
    return {"status": status, "envelope_id": envelope_id}


def replay_outbox(store_db: Session) -> Dict[str, int]:
    """Putar ulang outbox pending setelah snapshot diterapkan (K-22)."""
    applied = 0
    conflicts = 0
    for item in pending(store_db):
        try:
            result = _apply_payload(
                store_db,
                entity=item.entity,
                action=item.action,
                entity_id=item.entity_id,
                payload=json.loads(item.payload_json or "{}"),
                idempotency_key=item.idempotency_key,
            )
            if result in {"applied", "duplicate"}:
                mark_acked(item)
                applied += 1
        except ConflictError as exc:
            mark_conflict(item, str(exc))
            store_db.add(
                SyncConflict(
                    outbox_id=item.id,
                    entity=item.entity,
                    entity_id=item.entity_id,
                    reason=str(exc),
                    detail_json=item.payload_json,
                )
            )
            conflicts += 1
        except Exception as exc:  # pragma: no cover - dicatat untuk retry
            item.retry_count = int(item.retry_count or 0) + 1
            item.error = str(exc)[:500]
    store_db.commit()
    return {"applied": applied, "conflicts": conflicts}


# --- Snapshot -------------------------------------------------------------


def _store_path(store_id: str) -> Path:
    entry = store_registry.get_store(store_id)
    if entry is None:
        raise NotFoundError("Toko tidak ditemukan.")
    return store_registry.resolve_database_path(entry)


# Tabel milik instalasi (lisensi, kunci, antrean) tidak ikut snapshot toko.
# Kalau ikut, menerapkan snapshot hub akan menghapus identitas owner di perangkat
# penerima atau menimpa outbox lokal yang belum terkirim.
LOCAL_ONLY_TABLES = (
    "applied_deltas",
    "sync_peer_states",
    "sync_conflicts",
    "outbox_items",
    "relay_snapshots",
    "relay_acks",
    "relay_envelopes",
    "device_key_wraps",
    "store_keys",
    "permission_snapshots",
    "hub_audits",
    "store_hubs",
    "device_stores",
    "devices",
    "login_guards",
    "permission_audits",
    "employee_accounts",
    "licenses",
    "owner_identity",
)


def _snapshot_copy(path: Path) -> Path:
    """Salinan konsisten berisi data toko saja, tanpa metadata instalasi."""
    handle, name = tempfile.mkstemp(suffix=".db", prefix="snapshot_")
    os.close(handle)
    temp = Path(name)
    source = sqlite3.connect(str(path))
    try:
        target = sqlite3.connect(str(temp))
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()

    connection = sqlite3.connect(str(temp))
    try:
        connection.execute("PRAGMA foreign_keys = OFF")
        for table in LOCAL_ONLY_TABLES:
            connection.execute(f'DROP TABLE IF EXISTS "{table}"')
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if "app_settings" in tables:
            connection.execute(
                "DELETE FROM app_settings WHERE key LIKE 'auth.%' "
                "OR key LIKE 'telegram.%' OR key = 'store.database_id'"
            )
        connection.commit()
        connection.execute("VACUUM")
    finally:
        connection.close()
    return temp


def _apply_business_tables(target_path: Path, snapshot_path: Path) -> None:
    """Salin tabel data toko dari snapshot; tabel instalasi target dipertahankan."""
    connection = sqlite3.connect(str(target_path))
    try:
        connection.execute("PRAGMA foreign_keys = OFF")
        # Rahasia lokal dan identitas database tidak boleh ikut tertimpa data hub.
        preserved_settings = connection.execute(
            "SELECT key, value FROM app_settings "
            "WHERE key LIKE 'auth.%' OR key LIKE 'telegram.%' "
            "OR key = 'store.database_id'"
        ).fetchall()
        connection.execute("ATTACH DATABASE ? AS snap", (str(snapshot_path),))
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM snap.sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        with connection:
            for table in tables:
                target_columns = {
                    row[1]
                    for row in connection.execute(
                        f'PRAGMA main.table_info("{table}")'
                    )
                }
                snapshot_columns = [
                    row[1]
                    for row in connection.execute(
                        f'PRAGMA snap.table_info("{table}")'
                    )
                    if row[1] in target_columns
                ]
                if not snapshot_columns:
                    continue
                columns = ", ".join(f'"{name}"' for name in snapshot_columns)
                connection.execute(f'DELETE FROM main."{table}"')
                connection.execute(
                    f'INSERT INTO main."{table}" ({columns}) '
                    f'SELECT {columns} FROM snap."{table}"'
                )
            has_sequence = connection.execute(
                "SELECT 1 FROM snap.sqlite_master WHERE name = 'sqlite_sequence'"
            ).fetchone()
            if has_sequence:
                connection.execute("DELETE FROM main.sqlite_sequence")
                connection.execute(
                    "INSERT INTO main.sqlite_sequence "
                    "SELECT name, seq FROM snap.sqlite_sequence "
                    "WHERE name NOT LIKE 'sqlite_%'"
                )
            if preserved_settings:
                connection.executemany(
                    "INSERT OR REPLACE INTO main.app_settings "
                    "(key, value, updated_at) "
                    "VALUES (?, ?, CURRENT_TIMESTAMP)",
                    preserved_settings,
                )
        connection.execute("DETACH DATABASE snap")
    finally:
        connection.close()


def create_snapshot(
    db: Session,
    *,
    store_id: str,
    device_id: str,
    store_key: bytes,
    device_private_key: str,
    hlc_wall: int = 0,
    hlc_counter: int = 0,
) -> Dict[str, Any]:
    _require_premium()
    _device(db, device_id)
    _assigned(db, device_id, store_id)
    hub = db.get(StoreHub, store_id)
    if hub is None or hub.device_id != device_id or hub.mode == "pending":
        raise FeatureLockedError("Snapshot hanya dibuat oleh hub toko.", code="not_hub")
    snapshot_file = _snapshot_copy(_store_path(store_id))
    try:
        raw = snapshot_file.read_bytes()
    finally:
        snapshot_file.unlink(missing_ok=True)
    checksum = premium_crypto.sha256_hex(raw)
    ciphertext, nonce = premium_crypto.encrypt_payload(store_key, raw)
    signature = premium_crypto.sign(
        device_private_key,
        premium_crypto.canonical_json(
            {
                "store_id": store_id,
                "device_id": device_id,
                "checksum": checksum,
                "hlc_wall": int(hlc_wall),
                "hlc_counter": int(hlc_counter),
            }
        ),
    )
    row = RelaySnapshot(
        id=store_registry.new_ulid(),
        owner_id=_owner_id(db),
        store_id=store_id,
        device_id=device_id,
        hlc_wall=int(hlc_wall),
        hlc_counter=int(hlc_counter),
        ciphertext=ciphertext,
        nonce=nonce,
        signature=signature,
        checksum=checksum,
        expires_at=_now() + ENVELOPE_TTL,
    )
    db.add(row)
    db.commit()
    return {"id": row.id, "checksum": checksum, "expires_at": row.expires_at}


def get_snapshot(db: Session, *, store_id: str, device_id: str) -> Dict[str, Any]:
    _device(db, device_id)
    _assigned(db, device_id, store_id)
    row = db.execute(
        select(RelaySnapshot)
        .where(RelaySnapshot.store_id == store_id)
        .order_by(RelaySnapshot.created_at.desc())
    ).scalars().first()
    if row is None or row.expires_at < _now():
        raise NotFoundError("Snapshot tidak tersedia atau sudah melewati TTL.")
    return {
        "id": row.id,
        "store_id": row.store_id,
        "device_id": row.device_id,
        "ciphertext": row.ciphertext,
        "nonce": row.nonce,
        "signature": row.signature,
        "checksum": row.checksum,
        "hlc_wall": row.hlc_wall,
        "hlc_counter": row.hlc_counter,
        "created_at": row.created_at,
        "expires_at": row.expires_at,
    }


def apply_snapshot(
    db: Session,
    *,
    store_id: str,
    device_id: str,
    snapshot_id: str,
    store_key: bytes,
) -> Dict[str, Any]:
    """Terapkan snapshot atomik lalu putar ulang outbox lokal (K-22)."""
    _require_premium()
    target_device = _device(db, device_id)
    _assigned(db, device_id, store_id)
    snap = db.get(RelaySnapshot, snapshot_id)
    if snap is None or snap.store_id != store_id:
        raise NotFoundError("Snapshot tidak ditemukan.")
    sender = _device(db, snap.device_id)
    canonical = premium_crypto.canonical_json(
        {
            "store_id": snap.store_id,
            "device_id": snap.device_id,
            "checksum": snap.checksum,
            "hlc_wall": snap.hlc_wall,
            "hlc_counter": snap.hlc_counter,
        }
    )
    if not premium_crypto.verify(
        device_service.signing_key(sender), canonical, snap.signature
    ):
        raise BusinessValidationError("Tanda tangan snapshot tidak valid.")
    raw = premium_crypto.decrypt_payload(store_key, snap.ciphertext, snap.nonce)
    if premium_crypto.sha256_hex(raw) != snap.checksum:
        raise BusinessValidationError("Checksum snapshot tidak cocok.")
    active_id = store_registry.active_store()["store_id"]
    if store_id != active_id:
        raise BusinessValidationError(
            "Snapshot hanya dapat diterapkan pada toko aktif perangkat ini."
        )

    handle, name = tempfile.mkstemp(suffix=".db", prefix="apply_snapshot_")
    os.close(handle)
    staged = Path(name)
    staged.write_bytes(raw)
    try:
        check = sqlite3.connect(str(staged))
        try:
            integrity = check.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise BusinessValidationError("Snapshot rusak (integrity check gagal).")
            tables = {
                row[0]
                for row in check.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "stock_items" not in tables:
                raise BusinessValidationError("Snapshot bukan database toko yang sah.")
        finally:
            check.close()

        # Lepaskan transaksi baca sesi metadata agar penulisan tabel toko tidak
        # menunggu lock SQLite yang sedang dipegang sesi ini.
        db.commit()
        path = _store_path(store_id)
        _apply_business_tables(path, staged)

        # Outbox dan tabel instalasi sengaja tidak ikut disalin snapshot,
        # sehingga antrean lokal tetap ada lalu diputar ulang di atas data hub.
        store_bind = db_session.active_engine()
        with db_session.store_session(store_bind) as restored:
            replay = replay_outbox(restored)
    finally:
        staged.unlink(missing_ok=True)

    return {
        "status": "applied",
        "snapshot_id": snapshot_id,
        "store_id": store_id,
        "replayed": replay,
        "device": target_device.id,
    }
