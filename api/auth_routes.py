"""Endpoint autentikasi web lokal: status, setup PIN, login, dan akun karyawan.

Router ini sengaja tidak memakai dependency sesi agar layar setup/login bisa
diakses sebelum pengguna masuk. Login karyawan di hub memakai username +
password + PIN; login perangkat memakai token perangkat di header.
"""
from __future__ import annotations

from dataclasses import replace

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from api.deps import DEVICE_TOKEN_HEADER
from api.schemas import (
    AuthStatusOut,
    EmployeeChangePasswordIn,
    EmployeeDeviceLoginIn,
    EmployeeHubLoginIn,
    EmployeeSetPinIn,
    PinRequest,
)
from config import settings
from database import store_registry
from database.models import EmployeeAccount, StoreHub
from database.session import get_primary_db
from services import (
    account_service,
    auth_service,
    device_service,
    entitlement_service,
)
from services.auth_service import Operator
from services.errors import FeatureLockedError

router = APIRouter(prefix="/auth", tags=["Autentikasi"])


def _status_payload(db: Session, request: Request) -> AuthStatusOut:
    operator = None
    if settings.auth_mode == "session-pin":
        configured = auth_service.pin_configured(db)
        operator = auth_service.verify_session_token(
            db, request.cookies.get(auth_service.COOKIE_NAME)
        )
        if operator is None:
            device_token = request.headers.get(DEVICE_TOKEN_HEADER)
            if device_token and entitlement_service.is_premium():
                device = device_service.device_from_token(db, device_token)
                if device is not None:
                    if device.employee_account_id is not None:
                        account = db.get(
                            EmployeeAccount, device.employee_account_id
                        )
                        if account is not None and account.aktif:
                            operator = auth_service.employee_operator(
                                account, device.id
                            )
                    else:
                        operator = replace(
                            auth_service.OWNER, device_id=device.id
                        )
    else:
        configured = False

    return AuthStatusOut(
        mode=settings.auth_mode,
        pin_configured=configured,
        authenticated=operator is not None,
        locked_seconds=auth_service.lock_remaining(db),
        operator_id=operator.id if operator else None,
        operator_label=operator.label if operator else None,
        operator_kind=operator.kind if operator else "owner",
        operator_role=operator.role if operator else "owner",
        permissions=sorted(operator.permissions) if operator else [],
        stores=list(operator.stores) if operator else [],
        device_id=operator.device_id if operator else None,
        must_change_password=(
            operator.must_change_password if operator else False
        ),
    )


def _require_session_mode() -> None:
    if settings.auth_mode != "session-pin":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Autentikasi PIN tidak dipakai pada mode ini.",
        )


def _require_premium() -> None:
    if not entitlement_service.is_premium():
        raise FeatureLockedError(
            entitlement_service.LOCKED_MESSAGE, code="premium_locked"
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


def _employee_from_request(request: Request, db: Session) -> Operator:
    """Karyawan dari sesi hub atau token perangkat (K-07/K-08)."""
    operator = auth_service.verify_session_token(
        db, request.cookies.get(auth_service.COOKIE_NAME)
    )
    if operator is not None:
        return operator
    device = device_service.device_from_token(
        db, request.headers.get(DEVICE_TOKEN_HEADER)
    )
    if (
        device is None
        or device.employee_account_id is None
        or not entitlement_service.is_premium()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesi tidak valid. Silakan masuk kembali.",
            headers={"WWW-Authenticate": "Session"},
        )
    account = db.get(EmployeeAccount, device.employee_account_id)
    if account is None or not account.aktif:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Akun karyawan tidak aktif.",
        )
    return auth_service.employee_operator(account, device.id)


@router.get("/status", response_model=AuthStatusOut)
def auth_status(request: Request, db: Session = Depends(get_primary_db)):
    return _status_payload(db, request)


@router.post("/setup", status_code=201)
def setup_pin(
    payload: PinRequest,
    response: Response,
    db: Session = Depends(get_primary_db),
):
    _require_session_mode()
    auth_service.setup_pin(db, payload.pin)
    _attach_session(response, db, auth_service.OWNER)
    return {"status": "ok"}


@router.post("/login")
def login(
    payload: PinRequest,
    response: Response,
    db: Session = Depends(get_primary_db),
):
    _require_session_mode()
    operator = auth_service.verify_pin(db, payload.pin)
    _attach_session(response, db, operator)
    return {"status": "ok"}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(auth_service.COOKIE_NAME, path="/")
    return {"status": "ok"}


@router.post("/employee/login")
def employee_login(
    payload: EmployeeHubLoginIn,
    response: Response,
    db: Session = Depends(get_primary_db),
):
    """Login karyawan di komputer hub: username + password + PIN."""
    _require_session_mode()
    _require_premium()
    account, pin_set = account_service.authenticate_hub(
        db, payload.username, payload.password, payload.pin
    )
    active_store = store_registry.active_store()["store_id"]
    hub = db.get(StoreHub, active_store)
    device_id = hub.device_id if hub is not None else None
    operator = auth_service.employee_operator(account, device_id)
    _attach_session(response, db, operator)
    return {
        "status": "ok",
        "pin_set": pin_set,
        "must_change_password": operator.must_change_password,
        "device_id": device_id,
    }


@router.post("/device/login")
def device_login(
    payload: EmployeeDeviceLoginIn,
    request: Request,
    db: Session = Depends(get_primary_db),
):
    """Login perangkat karyawan; token perangkat dikirim di header."""
    _require_session_mode()
    _require_premium()
    device = device_service.device_from_token(
        db, request.headers.get(DEVICE_TOKEN_HEADER)
    )
    if device is None or device.kind != "employee":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token perangkat tidak valid atau sudah dicabut.",
        )
    account = account_service.authenticate_device(
        db, payload.owner_id, payload.username, payload.password
    )
    if device.employee_account_id != account.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Perangkat ini tidak terikat ke akun karyawan tersebut.",
        )
    return {
        "status": "ok",
        "device": {
            "id": device.id,
            "nama": device.nama,
            "stores": [
                row.store_id
                for row in device_service.device_stores(db, device.id)
            ],
        },
        "operator": {
            "id": f"employee:{account.id}",
            "username": account.username,
            "nama": account.nama,
            "role": account.role_base,
            "permissions": sorted(account_service.effective_permissions(account)),
            "must_change_password": bool(account.must_change_password),
        },
    }


@router.post("/employee/change-password")
def employee_change_password(
    payload: EmployeeChangePasswordIn,
    request: Request,
    db: Session = Depends(get_primary_db),
):
    operator = _employee_from_request(request, db)
    if operator.kind != "employee" or operator.employee_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hanya akun karyawan yang dapat mengganti password di sini.",
        )
    account_service.change_password(
        db,
        operator.employee_id,
        old_password=payload.old_password,
        new_password=payload.new_password,
    )
    return {"status": "ok"}


@router.post("/employee/pin")
def employee_set_pin(
    payload: EmployeeSetPinIn,
    request: Request,
    db: Session = Depends(get_primary_db),
):
    operator = _employee_from_request(request, db)
    if operator.kind != "employee" or operator.employee_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hanya akun karyawan yang dapat membuat PIN di sini.",
        )
    account_service.set_employee_pin(
        db, operator.employee_id, password=payload.password, pin=payload.pin
    )
    return {"status": "ok"}
