"""Dependency FastAPI: autentikasi semua endpoint /api.

Mode `session-pin` (web lokal) memakai cookie sesi dari login PIN kasir.
Mode `install-token` (APK) memakai token acak per instalasi yang dikirim lewat
header `X-Install-Token` dan dibandingkan constant-time. Dependency ini memakai
sesi database sendiri yang singkat agar tidak membuka transaksi pada sesi
request (POS memakai `db.begin()`).
"""
from __future__ import annotations

import hmac

from fastapi import Depends, HTTPException, Request, status

from config import settings
from database.session import SessionLocal
from services import auth_service
from services.auth_service import Operator

INSTALL_TOKEN_HEADER = "X-Install-Token"


def _install_token_valid(presented: str | None) -> bool:
    expected = settings.app_install_token
    if not expected or not presented:
        return False
    return hmac.compare_digest(
        presented.encode("utf-8"), expected.encode("utf-8")
    )


def require_auth(request: Request) -> Operator:
    """Kembalikan principal terautentikasi; identitas tidak dari frontend."""
    mode = settings.auth_mode

    if mode == "session-pin":
        token = request.cookies.get(auth_service.COOKIE_NAME)
        with SessionLocal() as db:
            operator = auth_service.verify_session_token(db, token)
        if operator is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Silakan masuk dengan PIN kasir terlebih dahulu.",
                headers={"WWW-Authenticate": "Session"},
            )
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
        return auth_service.OWNER

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Mode autentikasi server tidak dikenal.",
    )


def require_owner(operator: Operator = Depends(require_auth)) -> Operator:
    if operator.role != auth_service.OWNER_ROLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tindakan ini hanya untuk pemilik bengkel.",
        )
    return operator
