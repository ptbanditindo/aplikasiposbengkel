"""Stub entitlement Fase 1: paket free/premium dari registry lokal.

Nilai sebenarnya nanti berasal dari lisensi. Selama pilot web, registry lokal
cukup untuk menguji gating tulis tanpa mengunci data lama.
"""
from __future__ import annotations

from typing import Any, Dict

from database import store_registry
from services.errors import FeatureLockedError

PREMIUM_WRITE_PREFIXES = (
    "/api/employees",
    "/api/employee-debts",
    "/api/payroll",
    "/api/salary-payments",
    "/api/suppliers",
)

PREMIUM_ROUTES = {
    ("POST", "/api/stores"),
    ("PUT", "/api/settings/telegram"),
    ("POST", "/api/admin/scheduled-backup"),
    ("POST", "/api/admin/telegram-backup"),
}

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

LOCKED_MESSAGE = (
    "Fitur ini hanya tersedia di paket premium. Data lama tetap dapat dibaca "
    "dan diekspor."
)


def get_plan() -> str:
    return store_registry.get_plan()


def set_plan(plan: str) -> str:
    return store_registry.set_plan(plan)


def is_premium() -> bool:
    return get_plan() == "premium"


def info() -> Dict[str, Any]:
    plan = get_plan()
    return {"plan": plan, "premium": plan == "premium"}


def _normalized(path: str) -> str:
    cleaned = (path or "/").rstrip("/")
    return cleaned or "/"


def _is_premium_target(method: str, path: str) -> bool:
    method = method.upper()
    normalized = _normalized(path)
    if (method, normalized) in PREMIUM_ROUTES:
        return True
    return any(
        normalized == prefix or normalized.startswith(prefix + "/")
        for prefix in PREMIUM_WRITE_PREFIXES
    )


def guard_request(method: str, path: str) -> None:
    """Tolak aksi tulis premium saat paket gratis; GET tetap boleh."""
    if method.upper() not in UNSAFE_METHODS:
        return
    if not path.startswith("/api"):
        return
    if is_premium():
        return
    if _is_premium_target(method, path):
        raise FeatureLockedError(LOCKED_MESSAGE, code="premium_locked")
