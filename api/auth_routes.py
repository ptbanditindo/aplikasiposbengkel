"""Endpoint autentikasi web lokal: status, setup PIN, login, logout.

Router ini sengaja tidak memakai dependency sesi agar layar setup/login bisa
diakses sebelum pengguna masuk.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from api.deps import require_owner
from api.schemas import AuthStatusOut, PinRequest
from config import settings
from database.session import get_db
from services import auth_service
from services.auth_service import Operator

router = APIRouter(prefix="/auth", tags=["Autentikasi"])


def _status_payload(db: Session, request: Request) -> AuthStatusOut:
    operator = None
    if settings.auth_mode == "session-pin":
        configured = auth_service.pin_configured(db)
        operator = auth_service.verify_session_token(
            db, request.cookies.get(auth_service.COOKIE_NAME)
        )
    else:
        configured = False

    return AuthStatusOut(
        mode=settings.auth_mode,
        pin_configured=configured,
        authenticated=operator is not None,
        locked_seconds=auth_service.lock_remaining(db),
        kasir_configured=auth_service.kasir_configured(db),
        operator_id=operator.id if operator else None,
        role=operator.role if operator else None,
        operator_label=operator.label if operator else None,
    )


def _require_session_mode() -> None:
    if settings.auth_mode != "session-pin":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Autentikasi PIN tidak dipakai pada mode ini.",
        )


def _attach_session(response: Response, db: Session, operator: Operator) -> None:
    token = auth_service.create_session_token(db, operator)
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
    _attach_session(response, db, auth_service.OWNER)
    return {"status": "ok"}


@router.post("/login")
def login(
    payload: PinRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    _require_session_mode()
    operator = auth_service.verify_pin(db, payload.pin)
    _attach_session(response, db, operator)
    return {"status": "ok"}


@router.put("/kasir-pin")
def set_kasir_pin(
    payload: PinRequest,
    db: Session = Depends(get_db),
    _owner: Operator = Depends(require_owner),
):
    _require_session_mode()
    auth_service.set_kasir_pin(db, payload.pin)
    return {"status": "ok", "kasir_configured": True}


@router.delete("/kasir-pin")
def delete_kasir_pin(
    db: Session = Depends(get_db),
    _owner: Operator = Depends(require_owner),
):
    _require_session_mode()
    auth_service.clear_kasir_pin(db)
    return {"status": "ok", "kasir_configured": False}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(auth_service.COOKIE_NAME, path="/")
    return {"status": "ok"}
