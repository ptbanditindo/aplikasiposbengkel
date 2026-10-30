"""Dependency FastAPI: autentikasi semua endpoint /api.

Mode `session-pin` (web lokal) memakai cookie sesi dari login PIN kasir.
Dependency ini memakai sesi database sendiri yang singkat agar tidak
membuka transaksi pada sesi request (POS memakai `db.begin()`).
"""
from __future__ import annotations

from fastapi import HTTPException, Request, status

from config import settings
from database.session import SessionLocal
from services import auth_service


def require_auth(request: Request) -> None:
    if settings.auth_mode == "session-pin":
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

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Mode autentikasi server tidak dikenal.",
    )
