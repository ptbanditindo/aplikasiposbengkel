"""ID publik relay; format ULID yang sama dengan aplikasi lokal."""
from __future__ import annotations

import secrets
import time
from typing import Optional

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_ulid(now: Optional[float] = None) -> str:
    milliseconds = int((now if now is not None else time.time()) * 1000)
    stamp = ""
    for _ in range(10):
        stamp = ALPHABET[milliseconds & 31] + stamp
        milliseconds >>= 5
    return stamp + "".join(secrets.choice(ALPHABET) for _ in range(16))
