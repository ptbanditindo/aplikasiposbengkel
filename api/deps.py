"""Dependency FastAPI: autentikasi semua endpoint /api.

Mode `session-pin` (web lokal) memakai cookie sesi dari login PIN kasir.
Mode `install-token` (APK) memakai token acak per instalasi yang dikirim lewat
header `X-Install-Token` dan dibandingkan constant-time. Dependency ini memakai
sesi database sendiri yang singkat agar tidak membuka transaksi pada sesi
request (POS memakai `db.begin()`).
"""
from __future__ import annotations

import hmac

from fastapi import HTTPException, Request, status

from config import settings
from database.session import SessionLocal
from services import auth_service

INSTALL_TOKEN_HEADER = "X-Install-Token"


def _install_token_valid(presented: str | None) -> bool:
    expected = settings.app_install_token
    if not expected or not presented:
        return False
    return hmac.compare_digest(
        presented.encode("utf-8"), expected.encode("utf-8")
    )


def require_auth(request: Request) -> None:
    mode = settings.auth_mode

    if mode == "session-pin":
        token = request.cookies.get(auth_service.COOKIE_NAME)
        with SessionLocal() as db:
            valid = auth_service.verify_session_token(db, token)
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Silakan masuk dengan PIN kasir terlebih dahulu.",
                headers={"WWW-Authenticate": "Session"},
            )
        return

    if mode == "install-token":
        presented = request.headers.get(INSTALL_TOKEN_HEADER)
        if not _install_token_valid(presented):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token instalasi aplikasi tidak valid.",
                headers={"WWW-Authenticate": "InstallToken"},
            )
        return

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Mode autentikasi server tidak dikenal.",
    )
