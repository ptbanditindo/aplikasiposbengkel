"""Dependency FastAPI: autentikasi semua endpoint /api.

Mode `session-pin` (web lokal) memakai cookie sesi dari login PIN pemilik.
Mode `install-token` (APK) memakai token acak per instalasi yang dikirim lewat
header `X-Install-Token` dan dibandingkan constant-time. Dependency ini memakai
sesi database sendiri yang singkat agar tidak membuka transaksi pada sesi
request (POS memakai `db.begin()`).
"""
from __future__ import annotations

import hmac
from dataclasses import replace

from fastapi import Depends, HTTPException, Request, status

from config import settings
from database.session import SessionLocal
from database import store_registry
from database.models import EmployeeAccount
from services import (
    auth_service,
    authorization_service,
    device_service,
    entitlement_service,
)
from services.auth_service import Operator

INSTALL_TOKEN_HEADER = "X-Install-Token"
DEVICE_TOKEN_HEADER = "X-Device-Token"


def _install_token_valid(presented: str | None) -> bool:
    expected = settings.app_install_token
    if not expected or not presented:
        return False
    return hmac.compare_digest(
        presented.encode("utf-8"), expected.encode("utf-8")
    )


def _operator_from_device(db, device_token: str | None) -> Operator | None:
    device = device_service.device_from_token(db, device_token)
    if device is None:
        return None
    if not entitlement_service.is_premium():
        return None
    if device.employee_account_id is not None:
        account = db.get(EmployeeAccount, device.employee_account_id)
        if account is None or not account.aktif:
            return None
        return auth_service.employee_operator(account, device.id)
    return replace(auth_service.OWNER, device_id=device.id)


def require_auth(request: Request) -> Operator:
    """Kembalikan principal terautentikasi; identitas tidak dari frontend."""
    mode = settings.auth_mode

    if mode == "session-pin":
        token = request.cookies.get(auth_service.COOKIE_NAME)
        device_token = request.headers.get(DEVICE_TOKEN_HEADER)
        with SessionLocal() as db:
            operator = auth_service.verify_session_token(db, token)
            if operator is None and device_token:
                operator = _operator_from_device(db, device_token)
            if operator is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Silakan masuk dengan PIN pemilik terlebih dahulu.",
                    headers={"WWW-Authenticate": "Session"},
                )
            authorization_service.assert_allowed(
                db,
                operator,
                request.method,
                request.url.path,
                active_store_id=store_registry.active_store()["store_id"],
            )
        entitlement_service.guard_request(request.method, request.url.path)
        return operator

    if mode == "install-token":
        presented = request.headers.get(INSTALL_TOKEN_HEADER)
        if not _install_token_valid(presented):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token instalasi aplikasi tidak valid.",
                headers={"WWW-Authenticate": "InstallToken"},
            )
        # APK adalah perangkat milik bengkel; token acak per instalasi menjadi
        # principal pemilik dengan hak pengelolaan yang sama.
        entitlement_service.guard_request(request.method, request.url.path)
        return auth_service.OWNER

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Mode autentikasi server tidak dikenal.",
    )


def require_owner(operator: Operator = Depends(require_auth)) -> Operator:
    if operator.kind != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tindakan ini hanya untuk pemilik bengkel.",
        )
    return operator
