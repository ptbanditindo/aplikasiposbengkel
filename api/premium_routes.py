"""Endpoint premium web: lisensi, akun karyawan, perangkat, relay, arsip."""
from __future__ import annotations

import asyncio
import os
import re
import tempfile
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from api.deps import require_auth, require_owner
from api.schemas import (
    AccountCreateIn,
    AccountUpdateIn,
    ApplyEnvelopeIn,
    ConflictResolveIn,
    DeviceRegisterIn,
    EnvelopeSubmitIn,
    HubSetIn,
    LicenseActivateIn,
    LicenseRenewIn,
    OutboxEnqueueIn,
    PasswordResetIn,
    RecoveryIn,
    SnapshotApplyIn,
    SnapshotCreateIn,
    StoreKeyRegisterIn,
    StoreKeyRotateIn,
)
from config import settings
from database import store_registry
from database.models import RelayEnvelope, utcnow
from database.session import SessionLocal, get_db, get_primary_db
from services import (
    account_service,
    archive_service,
    audit_service,
    backup_service,
    device_service,
    entitlement_service,
    license_service,
    premium_crypto,
    sync_service,
)
from services.auth_service import Operator
from services.errors import (
    BusinessValidationError,
    FeatureLockedError,
    NotFoundError,
)
from services.maintenance import RESTORE_WAIT_TIMEOUT, gate

router = APIRouter(tags=["Premium"])

ARCHIVE_NAME = re.compile(r"bengkel_radiator_semua_[0-9_]+\.zip")
UPLOAD_CHUNK = 1024 * 1024


def _premium() -> None:
    if not entitlement_service.is_premium():
        raise FeatureLockedError(
            entitlement_service.LOCKED_MESSAGE, code="premium_locked"
        )


def _active_store() -> str:
    return store_registry.active_store()["store_id"]


def _assigned(db: Session, device_id: str, store_id: str) -> None:
    device = device_service.get_device(db, device_id)
    if device.revoked_at is not None:
        raise FeatureLockedError(
            "Perangkat sudah dicabut.", code="device_revoked"
        )
    stores = [row.store_id for row in device_service.device_stores(db, device.id)]
    if store_id not in stores:
        raise FeatureLockedError(
            "Perangkat tidak ditugaskan ke toko ini.", code="store_not_assigned"
        )


# --- Lisensi dan identitas owner -----------------------------------------


@router.get("/premium/status")
def premium_status(
    db: Session = Depends(get_primary_db),
    _operator: Operator = Depends(require_owner),
):
    return license_service.status(db)


@router.get("/premium/plans")
def premium_plans(_operator: Operator = Depends(require_owner)):
    return {
        "plans": [
            {
                "id": "premium",
                "nama": "Premium",
                "deskripsi": (
                    "Semua fitur bengkel, multi-toko, akun karyawan, perangkat, "
                    "sinkronisasi terenkripsi, dan arsip semua toko."
                ),
            }
        ],
        "free": {
            "nama": "Gratis",
            "deskripsi": "Data lama tetap dapat dibaca, diekspor, dan dicadangkan.",
        },
    }


@router.post("/license/activate")
def activate_license(
    payload: LicenseActivateIn,
    db: Session = Depends(get_primary_db),
    operator: Operator = Depends(require_owner),
):
    result = license_service.activate(
        db,
        days=payload.days,
        provider=payload.provider,
        device_limit=payload.device_limit,
    )
    audit_service.record_event(
        db,
        operator,
        audit_service.ACTION_RESTORE,
        audit_service.REFERENCE_DATABASE,
        reference_id="license:activate",
        reason=f"Aktivasi premium {payload.days} hari",
    )
    db.commit()
    return result


@router.post("/license/renew")
def renew_license(
    payload: LicenseRenewIn,
    db: Session = Depends(get_primary_db),
    operator: Operator = Depends(require_owner),
):
    result = license_service.renew(db, days=payload.days)
    audit_service.record_event(
        db,
        operator,
        audit_service.ACTION_RESTORE,
        audit_service.REFERENCE_DATABASE,
        reference_id="license:renew",
        reason=f"Perpanjang premium {payload.days} hari",
    )
    db.commit()
    return result


@router.get("/license/status")
def license_status(
    db: Session = Depends(get_primary_db),
    _operator: Operator = Depends(require_owner),
):
    return license_service.status(db)


@router.get("/license/token")
def license_token(
    db: Session = Depends(get_primary_db),
    _operator: Operator = Depends(require_owner),
):
    row = license_service.get_license(db)
    if row is None or not row.token:
        raise NotFoundError("Lisensi belum aktif.")
    return {
        "token": row.token,
        "expires_at": row.token_expires_at,
        "payload": license_service.verify_token(db, row.token),
    }


@router.post("/license/recovery")
def recover_owner_key(
    payload: RecoveryIn,
    db: Session = Depends(get_primary_db),
    _operator: Operator = Depends(require_owner),
):
    return {
        "private_key": license_service.recover_private_key(db, payload.code)
    }


@router.delete("/license/owner")
def delete_owner_metadata(
    confirm: str = Query(..., max_length=16),
    db: Session = Depends(get_primary_db),
    operator: Operator = Depends(require_owner),
):
    owner = license_service.get_owner(db)
    if owner is None:
        raise NotFoundError("ID owner belum diterbitkan.")
    if confirm.strip() != owner.owner_id:
        raise BusinessValidationError(
            "Ketik ID owner untuk mengonfirmasi penghapusan metadata akun."
        )
    return license_service.delete_owner_metadata(db, operator.id)


@router.get("/owner-app/summary")
def owner_app_summary(
    db: Session = Depends(get_primary_db),
    _operator: Operator = Depends(require_owner),
):
    _premium()
    status_data = license_service.status(db)
    stores = [
        {
            "store_id": entry["store_id"],
            "database_id": entry.get("database_id") or "",
            "nama": entry.get("nama") or "",
            "aktif": entry["store_id"] == _active_store(),
        }
        for entry in store_registry.list_stores(include_missing=True)
    ]
    payload = {
        "v": 1,
        "owner_id": status_data["owner_id"],
        "plan": status_data["plan"],
        "period_end": (
            status_data["license"]["period_end"].isoformat()
            if status_data["license"]["period_end"]
            else ""
        ),
        "stores": stores,
        "devices": device_service.list_devices(db),
        "created_at": utcnow().isoformat(),
    }
    return {
        "payload": payload,
        "signature": license_service.sign_as_owner(db, payload),
        "public_key": license_service.owner_public_key(db),
    }


# --- Akun karyawan --------------------------------------------------------


@router.get("/accounts/permissions")
def permission_catalog(_operator: Operator = Depends(require_owner)):
    return {
        "roles": [
            {"id": role, "label": account_service.ROLE_LABELS[role]}
            for role in account_service.ROLES
        ],
        "base": {
            role: sorted(values)
            for role, values in account_service.ROLE_PERMISSIONS.items()
        },
        "permissions": account_service.PERMISSIONS,
        "owner_only": sorted(account_service.OWNER_ONLY_PERMISSIONS),
    }


@router.get("/accounts")
def list_accounts(
    db: Session = Depends(get_primary_db),
    _operator: Operator = Depends(require_owner),
):
    return account_service.list_accounts(db)


@router.post("/accounts", status_code=201)
def create_account(
    payload: AccountCreateIn,
    db: Session = Depends(get_primary_db),
    operator: Operator = Depends(require_owner),
):
    _premium()
    return account_service.create_account(
        db,
        actor=operator.id,
        username=payload.username,
        nama=payload.nama,
        role=payload.role,
        store_ids=payload.store_ids,
        extra_permissions=payload.extra_permissions,
        password=payload.password,
    )


@router.put("/accounts/{account_id}")
def update_account(
    account_id: int,
    payload: AccountUpdateIn,
    db: Session = Depends(get_primary_db),
    operator: Operator = Depends(require_owner),
):
    _premium()
    return account_service.update_account(
        db,
        account_id,
        actor=operator.id,
        nama=payload.nama,
        role=payload.role,
        store_ids=payload.store_ids,
        extra_permissions=payload.extra_permissions,
        aktif=payload.aktif,
    )


@router.delete("/accounts/{account_id}")
def deactivate_account(
    account_id: int,
    db: Session = Depends(get_primary_db),
    operator: Operator = Depends(require_owner),
):
    _premium()
    return account_service.update_account(
        db, account_id, actor=operator.id, aktif=False
    )


@router.post("/accounts/{account_id}/password-reset")
def reset_account_password(
    account_id: int,
    payload: PasswordResetIn,
    db: Session = Depends(get_primary_db),
    operator: Operator = Depends(require_owner),
):
    _premium()
    return account_service.reset_password(
        db, account_id, actor=operator.id, password=payload.password
    )


@router.post("/accounts/{account_id}/pin-reset")
def reset_account_pin(
    account_id: int,
    db: Session = Depends(get_primary_db),
    operator: Operator = Depends(require_owner),
):
    _premium()
    return account_service.reset_pin(db, account_id, actor=operator.id)


@router.get("/accounts/{account_id}/audit")
def account_audit(
    account_id: int,
    db: Session = Depends(get_primary_db),
    _operator: Operator = Depends(require_owner),
):
    return account_service.audit_rows(db, account_id)


@router.get("/accounts/{account_id}/snapshot")
def account_snapshot(
    account_id: int,
    db: Session = Depends(get_primary_db),
    _operator: Operator = Depends(require_owner),
):
    return account_service.latest_snapshot(db, account_id)


# --- Perangkat dan hub ----------------------------------------------------


@router.get("/devices")
def list_devices(
    db: Session = Depends(get_primary_db),
    _operator: Operator = Depends(require_owner),
):
    return device_service.list_devices(db)


@router.post("/devices", status_code=201)
def register_device(
    payload: DeviceRegisterIn,
    db: Session = Depends(get_primary_db),
    _operator: Operator = Depends(require_owner),
):
    _premium()
    private_keys = None
    public_key = payload.public_key.strip()
    encryption_key = payload.encryption_key.strip()
    if payload.generate_keys or not public_key or not encryption_key:
        sign_private, sign_public = premium_crypto.generate_signing_keypair()
        enc_private, enc_public = premium_crypto.generate_encryption_keypair()
        public_key = sign_public
        encryption_key = enc_public
        private_keys = {"sign": sign_private, "encrypt": enc_private}
    result = device_service.register_device(
        db,
        nama=payload.nama,
        kind=payload.kind,
        public_key=public_key,
        encryption_key=encryption_key,
        employee_account_id=payload.employee_account_id,
        store_ids=payload.store_ids,
    )
    result["private_keys"] = private_keys
    result["private_keys_note"] = (
        "Kunci privat hanya ditampilkan sekali. Penyimpanan aman perangkat "
        "belum dapat dibuktikan di web; jangan bagikan nilai ini."
    )
    return result


@router.post("/devices/web-hub")
def register_web_hub(
    db: Session = Depends(get_primary_db),
    operator: Operator = Depends(require_owner),
):
    _premium()
    return device_service.ensure_web_hub(db, operator.id)


@router.post("/devices/{device_id}/revoke")
def revoke_device(
    device_id: str,
    reason: str = Query(default="", max_length=255),
    db: Session = Depends(get_primary_db),
    operator: Operator = Depends(require_owner),
):
    _premium()
    return device_service.revoke_device(
        db, device_id, actor=operator.id, reason=reason
    )


@router.post("/devices/{device_id}/release")
def release_device(
    device_id: str,
    db: Session = Depends(get_primary_db),
    operator: Operator = Depends(require_owner),
):
    _premium()
    return device_service.release_device(db, device_id, actor=operator.id)


@router.get("/devices/hub")
def get_hub(
    store_id: str = Query(default="", max_length=32),
    db: Session = Depends(get_primary_db),
    _operator: Operator = Depends(require_owner),
):
    target = store_id or _active_store()
    row = device_service.hub_for_store(db, target)
    return {
        "store_id": target,
        "device_id": row.device_id if row else "",
        "mode": row.mode if row else "none",
        "quarantine": bool(row.quarantine) if row else False,
        "previous_device_id": row.previous_device_id if row else "",
    }


@router.post("/devices/hub")
def set_hub(
    payload: HubSetIn,
    db: Session = Depends(get_primary_db),
    operator: Operator = Depends(require_owner),
):
    _premium()
    return device_service.set_hub(
        db,
        store_id=payload.store_id,
        device_id=payload.device_id,
        actor=operator.id,
        force=payload.force,
        online=payload.online,
    )


@router.post("/devices/keys")
def register_store_keys(
    payload: StoreKeyRegisterIn,
    db: Session = Depends(get_primary_db),
    _operator: Operator = Depends(require_owner),
):
    _premium()
    generated = None
    if payload.store_key.strip():
        key = premium_crypto.b64d(payload.store_key.strip())
    else:
        key = premium_crypto.new_store_key()
        generated = premium_crypto.b64e(key)
    result = sync_service.register_store_keys(
        db,
        store_id=payload.store_id,
        store_key=key,
        device_ids=payload.device_ids,
        owner_private_key=license_service.owner_private_key(db),
        hub_device_id=payload.hub_device_id,
    )
    result["store_key"] = generated
    return result


@router.post("/devices/keys/rotate")
def rotate_store_key(
    payload: StoreKeyRotateIn,
    db: Session = Depends(get_primary_db),
    _operator: Operator = Depends(require_owner),
):
    _premium()
    generated = None
    if payload.store_key.strip():
        key = premium_crypto.b64d(payload.store_key.strip())
    else:
        key = premium_crypto.new_store_key()
        generated = premium_crypto.b64e(key)
    result = sync_service.rotate_store_key(
        db,
        store_id=payload.store_id,
        store_key=key,
        device_ids=payload.device_ids,
        owner_private_key=license_service.owner_private_key(db),
        hub_device_id=payload.hub_device_id,
    )
    result["store_key"] = generated
    return result


@router.get("/devices/keys/{store_id}/{device_id}")
def get_store_key_wrap(
    store_id: str,
    device_id: str,
    db: Session = Depends(get_primary_db),
    _operator: Operator = Depends(require_owner),
):
    _premium()
    return sync_service.store_key_wrap(db, store_id, device_id)


# --- Sinkronisasi ---------------------------------------------------------


@router.get("/sync/status")
def sync_status(
    device_id: str = Query(default="", max_length=32),
    db: Session = Depends(get_primary_db),
    store_db: Session = Depends(get_db),
    _operator: Operator = Depends(require_auth),
):
    _premium()
    if device_id:
        _assigned(db, device_id, _active_store())
    return sync_service.sync_status(db, store_db, device_id or None)


@router.get("/sync/outbox")
def list_outbox(
    device_id: str = Query(default="", max_length=32),
    db: Session = Depends(get_primary_db),
    store_db: Session = Depends(get_db),
    _operator: Operator = Depends(require_auth),
):
    _premium()
    if device_id:
        _assigned(db, device_id, _active_store())
    return sync_service.list_outbox(store_db, device_id or None)


@router.post("/sync/outbox", status_code=201)
def enqueue_outbox(
    payload: OutboxEnqueueIn,
    db: Session = Depends(get_primary_db),
    store_db: Session = Depends(get_db),
    _operator: Operator = Depends(require_auth),
):
    _premium()
    _assigned(db, payload.device_id, _active_store())
    db.commit()
    return sync_service.enqueue(
        store_db,
        device_id=payload.device_id,
        entity=payload.entity,
        action=payload.action,
        payload=payload.payload,
        entity_id=payload.entity_id,
        idempotency_key=payload.idempotency_key,
    )


@router.post("/sync/envelopes", status_code=201)
def submit_envelope(
    payload: EnvelopeSubmitIn,
    db: Session = Depends(get_primary_db),
    _operator: Operator = Depends(require_auth),
):
    _premium()
    return sync_service.submit_envelope(
        db,
        store_id=payload.store_id,
        sender_device_id=payload.sender_device_id,
        recipient_device_id=payload.recipient_device_id,
        seq=payload.seq,
        hlc_wall=payload.hlc_wall,
        hlc_counter=payload.hlc_counter,
        idempotency_key=payload.idempotency_key,
        ciphertext=payload.ciphertext,
        nonce=payload.nonce,
        signature=payload.signature,
    )


@router.get("/sync/envelopes")
def list_envelopes(
    device_id: str = Query(..., max_length=32),
    store_id: str = Query(default="", max_length=32),
    db: Session = Depends(get_primary_db),
    _operator: Operator = Depends(require_auth),
):
    _premium()
    return sync_service.list_envelopes(
        db, device_id=device_id, store_id=store_id or None
    )


@router.post("/sync/envelopes/{envelope_id}/ack")
def ack_envelope(
    envelope_id: str,
    device_id: str = Query(..., max_length=32),
    db: Session = Depends(get_primary_db),
    _operator: Operator = Depends(require_auth),
):
    _premium()
    return sync_service.ack_envelope(db, envelope_id, device_id)


@router.post("/sync/envelopes/{envelope_id}/apply")
def apply_envelope(
    envelope_id: str,
    payload: ApplyEnvelopeIn,
    db: Session = Depends(get_primary_db),
    store_db: Session = Depends(get_db),
    _operator: Operator = Depends(require_auth),
):
    _premium()
    envelope = db.get(RelayEnvelope, envelope_id)
    if envelope is not None and envelope.store_id != _active_store():
        raise BusinessValidationError(
            "Amplop hanya dapat diterapkan pada toko aktif perangkat ini."
        )
    return sync_service.apply_envelope(
        db,
        store_db,
        envelope_id=envelope_id,
        device_id=payload.device_id,
        store_key=premium_crypto.b64d(payload.store_key),
    )


@router.get("/sync/conflicts")
def list_conflicts(
    store_db: Session = Depends(get_db),
    _operator: Operator = Depends(require_auth),
):
    _premium()
    return sync_service.list_conflicts(store_db)


@router.post("/sync/conflicts/{conflict_id}/resolve")
def resolve_conflict(
    conflict_id: int,
    payload: ConflictResolveIn,
    store_db: Session = Depends(get_db),
    _operator: Operator = Depends(require_auth),
):
    _premium()
    return sync_service.resolve_conflict(
        store_db, conflict_id, payload.resolution
    )


@router.post("/sync/snapshots", status_code=201)
def create_snapshot(
    payload: SnapshotCreateIn,
    db: Session = Depends(get_primary_db),
    _operator: Operator = Depends(require_auth),
):
    _premium()
    return sync_service.create_snapshot(
        db,
        store_id=payload.store_id,
        device_id=payload.device_id,
        store_key=premium_crypto.b64d(payload.store_key),
        device_private_key=payload.device_private_key,
        hlc_wall=payload.hlc_wall,
        hlc_counter=payload.hlc_counter,
    )


@router.get("/sync/snapshots/{store_id}")
def get_snapshot(
    store_id: str,
    device_id: str = Query(..., max_length=32),
    db: Session = Depends(get_primary_db),
    _operator: Operator = Depends(require_auth),
):
    _premium()
    return sync_service.get_snapshot(db, store_id=store_id, device_id=device_id)


@router.post("/sync/snapshots/apply")
def apply_snapshot(
    payload: SnapshotApplyIn,
    db: Session = Depends(get_primary_db),
    _operator: Operator = Depends(require_auth),
):
    _premium()
    return sync_service.apply_snapshot(
        db,
        store_id=_active_store(),
        device_id=payload.device_id,
        snapshot_id=payload.snapshot_id,
        store_key=premium_crypto.b64d(payload.store_key),
    )


@router.post("/sync/purge")
def purge_envelopes(
    db: Session = Depends(get_primary_db),
    _operator: Operator = Depends(require_owner),
):
    _premium()
    return {"deleted": sync_service.purge_expired(db)}


# --- Arsip semua toko -----------------------------------------------------


@router.post("/admin/backup-all", response_class=FileResponse)
def backup_all(_operator: Operator = Depends(require_owner)):
    _premium()
    path = archive_service.create_archive()
    return FileResponse(
        path=str(path),
        media_type="application/zip",
        filename=path.name,
    )


@router.get("/admin/archives")
def list_archives(
    _operator: Operator = Depends(require_owner),
):
    _premium()
    return archive_service.list_archives()


@router.get("/admin/archives/{filename}", response_class=FileResponse)
def download_archive(
    filename: str,
    _operator: Operator = Depends(require_owner),
):
    _premium()
    if not ARCHIVE_NAME.fullmatch(filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nama arsip tidak valid.",
        )
    path = settings.backup_dir / filename
    if not path.is_file():
        raise NotFoundError("Arsip tidak ditemukan.")
    return FileResponse(
        path=str(path), media_type="application/zip", filename=filename
    )


@router.post("/admin/restore-all")
async def restore_all(
    file: UploadFile = File(...),
    operator: Operator = Depends(require_owner),
):
    _premium()
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(
        prefix="upload_arsip_", suffix=".zip", dir=str(settings.backup_dir)
    )
    os.close(handle)
    temp_path = Path(name)
    size = 0
    try:
        with temp_path.open("wb") as target:
            while True:
                chunk = await file.read(UPLOAD_CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > settings.backup_max_restore_mb * 1024 * 1024:
                    raise HTTPException(
                        status_code=413,
                        detail="Berkas arsip melebihi batas unggah restore.",
                    )
                target.write(chunk)
        if size == 0:
            raise BusinessValidationError("Berkas arsip kosong.")

        started = await asyncio.to_thread(
            gate.begin_restore, RESTORE_WAIT_TIMEOUT
        )
        if not started:
            raise HTTPException(
                status_code=503,
                detail="Restore lain sedang berjalan. Coba lagi sebentar.",
            )
        try:
            result = await asyncio.to_thread(
                archive_service.restore_archive, temp_path
            )
        finally:
            gate.end_restore()
    finally:
        temp_path.unlink(missing_ok=True)
        await file.close()

    try:
        with SessionLocal() as db:
            audit_service.record_event(
                db,
                operator,
                audit_service.ACTION_RESTORE,
                audit_service.REFERENCE_DATABASE,
                reference_id="arsip_semua_toko",
                reason="Pemulihan arsip semua toko",
            )
            db.commit()
    except Exception:  # pragma: no cover - audit tidak menggagalkan restore
        pass
    return {"status": "ok", **result}
