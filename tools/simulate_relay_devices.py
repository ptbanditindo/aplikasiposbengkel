"""Simulasi 6 perangkat pada relay: kirim delta, tertinggal, mengejar, lalu ack.

Jalankan:
    python tools/simulate_relay_devices.py

Skrip memakai database relay SQLite sementara di memori dan tidak menyentuh
database kasir. Fokus: counter feed, kursor, hapus-setelah-ack, dan bukti bahwa
server tidak menyisakan amplop setelah semua perangkat mengakui.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("RELAY_ENROLL_TOKEN", "simulasi-relay-lokal")
os.environ.setdefault("RELAY_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("RELAY_REQUIRE_HTTPS", "0")

from fastapi.testclient import TestClient  # noqa: E402

from config import settings  # noqa: E402
from relay.app import app  # noqa: E402
from relay.database import get_engine, session_factory  # noqa: E402
from relay.models import RelayEnvelope, RelayFeedCounter  # noqa: E402
from services import premium_crypto  # noqa: E402

STORE_ID = "TOKO-SIMULASI"
DEVICES = (
    ("owner-1", "owner", 2),
    ("owner-kedua", "owner", 0),
    ("kasir-1", "employee", 0),
    ("kasir-2", "employee", 0),
    ("mekanik-1", "employee", 0),
    ("mekanik-2", "employee", 0),
)


def _enroll(client: TestClient, nama: str, kind: str, account_id: int):
    sign_private, sign_public = premium_crypto.generate_signing_keypair()
    enc_private, enc_public = premium_crypto.generate_encryption_keypair()
    response = client.post(
        "/relay/devices",
        headers={"X-Relay-Enroll-Token": settings.relay_enroll_token},
        json={
            "owner_id": "OWNER-SIMULASI",
            "nama": nama,
            "kind": kind,
            "public_key": sign_public,
            "encryption_key": enc_public,
            "owner_public_key": sign_public if nama == "owner-1" else "",
            "store_ids": [STORE_ID],
            "employee_account_id": account_id or None,
        },
    )
    response.raise_for_status()
    data = response.json()
    return {
        "nama": nama,
        "id": data["device"]["id"],
        "token": data["token"],
        "sign_private": sign_private,
        "sign_public": sign_public,
        "enc_private": enc_private,
        "enc_public": enc_public,
        "seq": 0,
    }


def _send_envelope(client: TestClient, device, store_key: bytes, index: int) -> None:
    device["seq"] += 1
    plaintext = premium_crypto.canonical_json(
        {
            "entity": "stock",
            "action": "delta",
            "entity_id": f"sim-{index}",
            "payload": {"qty": 1},
            "seq": device["seq"],
            "hlc_wall": index,
            "hlc_counter": 0,
            "idempotency_key": f"sim-{index}",
        }
    )
    ciphertext, nonce = premium_crypto.encrypt_payload(store_key, plaintext)
    fields = {
        "store_id": STORE_ID,
        "sender_device_id": device["id"],
        "recipient_device_id": "",
        "seq": device["seq"],
        "hlc_wall": index,
        "hlc_counter": 0,
        "idempotency_key": f"sim-{index}",
        "ciphertext": ciphertext,
        "nonce": nonce,
    }
    canonical = premium_crypto.canonical_json({"v": 1, **fields})
    signature = premium_crypto.sign(device["sign_private"], canonical)
    response = client.post(
        "/relay/envelopes",
        headers={"X-Device-Token": device["token"]},
        json={**fields, "signature": signature},
    )
    response.raise_for_status()


def _catch_up(client: TestClient, device) -> int:
    cursor = 0
    applied = 0
    while True:
        response = client.get(
            "/relay/feed",
            headers={"X-Device-Token": device["token"]},
            params={"store_id": STORE_ID, "since_seq": cursor, "limit": 50},
        )
        response.raise_for_status()
        data = response.json()
        envelopes = data.get("envelopes") or []
        applied += len(envelopes)
        cursor = data.get("next_seq") or cursor
        if envelopes:
            ack = client.post(
                "/relay/feed/ack",
                headers={"X-Device-Token": device["token"]},
                json={"store_id": STORE_ID, "last_seq": cursor},
            )
            ack.raise_for_status()
        if not data.get("has_more"):
            break
    return applied


def main() -> int:
    with TestClient(app) as client:
        devices = [_enroll(client, nama, kind, account) for nama, kind, account in DEVICES]
        owner = devices[0]
        store_key = premium_crypto.new_store_key()

        for target in devices:
            wrapped = premium_crypto.wrap_store_key(
                target["enc_public"], store_key
            )
            signature = premium_crypto.sign(
                owner["sign_private"],
                premium_crypto.canonical_json(
                    {
                        "store_id": STORE_ID,
                        "device_id": target["id"],
                        "wrapped_key": wrapped,
                    }
                ),
            )
            response = client.post(
                "/relay/keys",
                headers={"X-Device-Token": owner["token"]},
                json={
                    "store_id": STORE_ID,
                    "device_id": target["id"],
                    "wrapped_key": wrapped,
                    "signature": signature,
                },
            )
            response.raise_for_status()

        for index, device in enumerate(devices, start=1):
            _send_envelope(client, device, store_key, index)

        total_applied = 0
        for device in devices:
            total_applied += _catch_up(client, device)

        # Perangkat terakhir tertinggal: kirim delta baru dan pastikan yang
        # sudah ack sebelumnya dapat mengejar tanpa mengulang.
        _send_envelope(client, owner, store_key, 99)
        for device in devices[1:]:
            total_applied += _catch_up(client, device)
        total_applied += _catch_up(client, owner)

        factory = session_factory()
        with factory() as db:
            remaining = db.query(RelayEnvelope).count()
            counter = db.get(RelayFeedCounter, STORE_ID)
            print(
                json.dumps(
                    {
                        "devices": len(devices),
                        "envelopes_applied": total_applied,
                        "remaining_envelopes": remaining,
                        "feed_counter": counter.last_seq if counter else 0,
                        "database": str(get_engine().url).split("://")[0],
                    },
                    indent=2,
                )
            )
            if remaining != 0:
                return 1
            if not counter or counter.last_seq != 7:
                return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
