"""Pemeriksaan lingkup akses web lokal: Host dan Origin.

Mencegah DNS rebinding: server hanya melayani Host loopback dengan port
aplikasi, dan permintaan tulis dari origin asing ditolak.
"""
from __future__ import annotations

from typing import Optional, Tuple

from config import LOOPBACK_HOSTS

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def split_host_header(value: str) -> Tuple[str, Optional[int]]:
    raw = (value or "").strip()
    if not raw:
        return "", None
    if raw.startswith("["):
        end = raw.find("]")
        if end == -1:
            return raw, None
        host = raw[1:end]
        rest = raw[end + 1:]
        if rest.startswith(":") and rest[1:].isdigit():
            return host, int(rest[1:])
        return host, None
    if raw.count(":") == 1:
        host, _, port = raw.partition(":")
        if port.isdigit():
            return host, int(port)
        return host, None
    return raw, None


def host_header_allowed(value: str, port: int) -> bool:
    host, parsed_port = split_host_header(value)
    return host.lower() in LOOPBACK_HOSTS and parsed_port == port


def allowed_origins(port: int) -> set[str]:
    return {
        f"http://127.0.0.1:{port}",
        f"http://localhost:{port}",
        f"http://[::1]:{port}",
    }


def origin_allowed(origin: str, port: int) -> bool:
    if not origin:
        return True
    return origin.rstrip("/") in allowed_origins(port)
