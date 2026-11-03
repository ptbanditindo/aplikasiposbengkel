"""Migrasi relay memakai tabel versi, bukan `PRAGMA user_version` (K-24)."""
from __future__ import annotations

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from relay.models import RelayBase, RelaySchemaVersion

RELAY_SCHEMA_VERSION = 1


def apply_relay_migrations(engine: Engine) -> int:
    RelayBase.metadata.create_all(engine)
    with Session(engine, future=True) as db:
        for version in range(1, RELAY_SCHEMA_VERSION + 1):
            if db.get(RelaySchemaVersion, version) is None:
                db.add(RelaySchemaVersion(version=version))
        db.commit()
    return RELAY_SCHEMA_VERSION
