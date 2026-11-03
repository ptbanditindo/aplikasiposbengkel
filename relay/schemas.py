"""Skema request relay (Pydantic v2)."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class EnrollIn(BaseModel):
    owner_id: str = Field(min_length=1, max_length=64)
    nama: str = Field(default="Perangkat", max_length=255)
    kind: str = Field(default="owner", pattern="^(owner|employee)$")
    public_key: str = Field(min_length=1)
    encryption_key: str = Field(min_length=1)
    owner_public_key: str = ""
    store_ids: List[str] = Field(default_factory=list)
    employee_account_id: Optional[int] = None


class AssignStoresIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=32)
    store_ids: List[str] = Field(default_factory=list)


class RevokeIn(BaseModel):
    reason: str = Field(default="", max_length=255)


class ClaimIn(BaseModel):
    old_device_id: str = Field(min_length=1, max_length=32)
    public_key: str = Field(min_length=1)
    encryption_key: str = Field(min_length=1)
    nama: str = Field(default="", max_length=255)


class KeyWrapIn(BaseModel):
    store_id: str = Field(min_length=1, max_length=32)
    device_id: str = Field(min_length=1, max_length=32)
    wrapped_key: str = Field(min_length=1)
    signature: str = Field(min_length=1)


class EnvelopeIn(BaseModel):
    store_id: str = Field(min_length=1, max_length=32)
    sender_device_id: str = Field(min_length=1, max_length=32)
    recipient_device_id: str = Field(default="", max_length=32)
    seq: int = Field(ge=1)
    hlc_wall: int = Field(ge=0)
    hlc_counter: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=128)
    ciphertext: str = Field(min_length=1)
    nonce: str = Field(min_length=1, max_length=64)
    signature: str = Field(min_length=1)


class FeedAckIn(BaseModel):
    store_id: str = Field(min_length=1, max_length=32)
    last_seq: int = Field(ge=0)


class SnapshotIn(BaseModel):
    store_id: str = Field(min_length=1, max_length=32)
    store_seq: int = Field(ge=0)
    ciphertext: str = Field(min_length=1)
    nonce: str = Field(min_length=1, max_length=64)
    signature: str = Field(min_length=1)
    checksum: str = Field(min_length=1, max_length=128)
    hlc_wall: int = Field(default=0, ge=0)
    hlc_counter: int = Field(default=0, ge=0)
