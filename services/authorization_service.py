"""Pemeriksaan izin permintaan langsung di lapisan data (K-07, K-12)."""
from __future__ import annotations

from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from database import store_registry
from services import device_service
from services.errors import FeatureLockedError

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

OWNER_ONLY_PREFIXES = (
    "/api/employees",
    "/api/employee-debts",
    "/api/payroll",
    "/api/salary-payments",
    "/api/settings",
    "/api/admin",
    "/api/audit-events",
    "/api/premium",
    "/api/accounts",
    "/api/license",
    "/api/devices",
    "/api/backup",
    "/api/owner-app",
)

MONEY_WRITE_PATHS = (
    ("POST", "/api/pos/transaction"),
    ("POST", "/api/service-records/"),
    ("PUT", "/api/service-records/"),
)

MONEY_WRITE_SUFFIXES = ("/payments", "/void", "/returns", "/exchange")

EXEMPT_ACTIVE_STORE = (
    "/api/auth",
    "/api/config",
    "/api/stores",
    "/api/premium",
    "/api/license",
    "/api/sync",
)

PASSWORD_CHANGE_ALLOWED = (
    "/api/auth/status",
    "/api/auth/logout",
    "/api/auth/employee/change-password",
    "/api/config",
)

PERMISSION_RULES = (
    ("/api/followup", "baca_followup"),
    ("/api/whatsapp", "baca_followup"),
)

REPORT_READ_PREFIX = "/api/reports"


def _normalized(path: str) -> str:
    cleaned = (path or "/").rstrip("/")
    return cleaned or "/"


def _matches(path: str, prefix: str) -> bool:
    root = prefix.rstrip("/")
    return path == root or path.startswith(root + "/")


def _owner_only(method: str, path: str) -> bool:
    if any(_matches(path, prefix) for prefix in OWNER_ONLY_PREFIXES):
        return True
    if method.upper() in UNSAFE_METHODS and _matches(path, "/api/stores"):
        return True
    if method.upper() in UNSAFE_METHODS and _matches(path, "/api/suppliers"):
        return True
    if method.upper() in UNSAFE_METHODS and _matches(path, "/api/harga-jasa"):
        return True
    if method.upper() in UNSAFE_METHODS and _matches(path, "/api/stock"):
        # Stok masuk dan opname punya izin tambahan; ubah master stok owner.
        return not (path.endswith("/in") or path.endswith("/opname"))
    return False


def _is_money_write(method: str, path: str) -> bool:
    if method.upper() not in UNSAFE_METHODS:
        return False
    if any(
        method.upper() == allowed_method and _matches(path, prefix)
        for allowed_method, prefix in MONEY_WRITE_PATHS
    ):
        return True
    if _matches(path, "/api/service-records") and path.endswith(MONEY_WRITE_SUFFIXES):
        return True
    return False


def _permission_required(method: str, path: str) -> Optional[str]:
    if path == "/api/stock/opname":
        return "opname"
    if path.endswith("/in") and _matches(path, "/api/stock"):
        return "stok_masuk"
    if method.upper() in UNSAFE_METHODS and path == "/api/stock":
        return "stok_masuk"
    if _matches(path, REPORT_READ_PREFIX):
        if path.endswith("/export") or path.endswith("/print"):
            return "cetak_laporan"
        return "lihat_laporan"
    for prefix, permission in PERMISSION_RULES:
        if _matches(path, prefix):
            return permission
    if _matches(path, "/api/suppliers") and method.upper() == "GET":
        return "baca_supplier"
    return None


def assert_allowed(
    db: Session,
    operator: Any,
    method: str,
    path: str,
    *,
    active_store_id: Optional[str] = None,
) -> None:
    normalized = _normalized(path)
    if not normalized.startswith("/api"):
        return

    if getattr(operator, "kind", "owner") == "owner":
        return

    if getattr(operator, "must_change_password", False) and not any(
        _matches(normalized, allowed) for allowed in PASSWORD_CHANGE_ALLOWED
    ):
        raise FeatureLockedError(
            "Ganti password awal terlebih dahulu sebelum memakai aplikasi.",
            code="password_change_required",
        )

    if _owner_only(method, normalized):
        raise FeatureLockedError(
            "Tindakan ini hanya untuk pemilik bengkel.", code="owner_only"
        )

    permission = _permission_required(method, normalized)
    if permission is not None and permission not in set(
        getattr(operator, "permissions", ())
    ):
        raise FeatureLockedError(
            "Izin tambahan untuk tindakan ini belum diberikan pemilik.",
            code="permission_denied",
        )

    if _is_money_write(method, normalized):
        device_service.assert_money_write(db, operator, active_store_id)

    if not any(_matches(normalized, prefix) for prefix in EXEMPT_ACTIVE_STORE):
        store_id = active_store_id or store_registry.active_store()["store_id"]
        device_service.assert_store_access(db, operator, store_id)
