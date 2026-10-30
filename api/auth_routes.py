"""Endpoint autentikasi web lokal: status, setup PIN, login, logout.

Router ini sengaja tidak memakai dependency sesi agar layar setup/login bisa
diakses sebelum pengguna masuk.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from api.schemas import AuthStatusOut, PinRequest
from config import settings
from database.session import get_db
from services import auth_service

router = APIRouter(prefix="/auth", tags=["Autentikasi"])


def _status_payload(db: Session, request: Request) -> AuthStatusOut:
    if settings.auth_mode == "session-pin":
        configured = auth_service.pin_configured(db)
        authenticated = auth_service.verify_session_token(
            db, request.cookies.get(auth_service.COOKIE_NAME)
        )
    else:
        configured = False
        authenticated = False

    return AuthStatusOut(
        mode=settings.auth_mode,
        pin_configured=configured,
        authenticated=authenticated,
        locked_seconds=auth_service.lock_remaining(db),
    )


def _require_session_mode() -> None:
    if settings.auth_mode != "session-pin":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Autentikasi PIN tidak dipakai pada mode ini.",
        )


def _attach_session(response: Response, db: Session) -> None:
    token = auth_service.create_session_token(db)
    response.set_cookie(
        auth_service.COOKIE_NAME,
        token,
        max_age=auth_service.SESSION_TTL_SECONDS,
        httponly=True,
        samesite="strict",
        path="/",
        secure=False,
    )


@router.get("/status", response_model=AuthStatusOut)
def auth_status(request: Request, db: Session = Depends(get_db)):
    return _status_payload(db, request)


@router.post("/setup", status_code=201)
def setup_pin(
    payload: PinRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    _require_session_mode()
    auth_service.setup_pin(db, payload.pin)
    _attach_session(response, db)
    return {"status": "ok"}


@router.post("/login")
def login(
    payload: PinRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    _require_session_mode()
    auth_service.verify_pin(db, payload.pin)
    _attach_session(response, db)
    return {"status": "ok"}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(auth_service.COOKIE_NAME, path="/")
    return {"status": "ok"}
