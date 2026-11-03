"""Skema relay: metadata pengiriman dan ciphertext, tanpa data bisnis."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.utcnow()


class RelayBase(DeclarativeBase):
    """Base terpisah agar tabel relay tidak pernah ikut metadata aplikasi lokal."""


class RelaySchemaVersion(RelayBase):
    __tablename__ = "relay_schema_version"

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )


class RelayOwner(RelayBase):
    """Akun owner di relay; bukan salinan database bengkel."""

    __tablename__ = "relay_owners"

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    plan: Mapped[str] = mapped_column(String(16), nullable=False, default="premium")
    signing_public_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    license_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    device_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )


class RelayDevice(RelayBase):
    __tablename__ = "relay_devices"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("relay_owners.owner_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nama: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="owner")
    employee_account_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    public_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    encryption_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    token_hash: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True
    )
    replacement_of: Mapped[str] = mapped_column(
        String(32), nullable=False, default=""
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked_reason: Mapped[str] = mapped_column(
        String(255), nullable=False, default=""
    )


class RelayStoreAssignment(RelayBase):
    __tablename__ = "relay_store_assignments"

    device_id: Mapped[str] = mapped_column(
        ForeignKey("relay_devices.id", ondelete="CASCADE"), primary_key=True
    )
    store_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )


class RelayKeyWrap(RelayBase):
    """Kunci toko terbungkus; relay tidak memegang kunci polos."""

    __tablename__ = "relay_key_wraps"

    store_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    device_id: Mapped[str] = mapped_column(
        ForeignKey("relay_devices.id", ondelete="CASCADE"), primary_key=True
    )
    wrapped_key: Mapped[str] = mapped_column(Text, nullable=False)
    owner_signature: Mapped[str] = mapped_column(Text, nullable=False, default="")
    signed_by_device_id: Mapped[str] = mapped_column(
        String(32), nullable=False, default=""
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    rotated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class RelaySnapshot(RelayBase):
    __tablename__ = "relay_snapshots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(String(32), nullable=False)
    store_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hlc_wall: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hlc_counter: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    nonce: Mapped[str] = mapped_column(String(64), nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class RelayEnvelope(RelayBase):
    __tablename__ = "relay_envelopes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sender_device_id: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )
    recipient_device_id: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    store_seq: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    hlc_wall: Mapped[int] = mapped_column(Integer, nullable=False)
    hlc_counter: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True
    )
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    nonce: Mapped[str] = mapped_column(String(64), nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        Index("ux_relay_device_seq", "sender_device_id", "seq", unique=True),
        Index("ux_relay_store_seq", "store_id", "store_seq", unique=True),
    )


class RelayAck(RelayBase):
    __tablename__ = "relay_acks"

    envelope_id: Mapped[str] = mapped_column(
        ForeignKey("relay_envelopes.id", ondelete="CASCADE"), primary_key=True
    )
    device_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    acked_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )


class RelayCursor(RelayBase):
    __tablename__ = "relay_cursors"

    store_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    last_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class RelayFeedCounter(RelayBase):
    __tablename__ = "relay_feed_counters"

    store_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    last_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class RelayAudit(RelayBase):
    __tablename__ = "relay_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, index=True
    )
