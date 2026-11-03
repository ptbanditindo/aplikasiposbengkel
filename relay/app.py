"""Aplikasi FastAPI relay (profil terpisah, K-24)."""
from __future__ import annotations

import hashlib
import hmac
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from config import APP_VERSION, settings
from relay import service
from relay.database import get_relay_db, get_engine, init_engine
from relay.migrations import RELAY_SCHEMA_VERSION, apply_relay_migrations
from relay.models import RelayDevice
from relay.schemas import (
    AssignStoresIn,
    ClaimIn,
    EnrollIn,
    EnvelopeIn,
    FeedAckIn,
    KeyWrapIn,
    RevokeIn,
    SnapshotIn,
)

ENROLL_HEADER = "X-Relay-Enroll-Token"
DEVICE_HEADER = "X-Device-Token"


class _RateLimiter:
    def __init__(self, limit: int):
        self.limit = max(1, int(limit))
        self.buckets: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        bucket = [stamp for stamp in self.buckets.get(key, []) if now - stamp < 60]
        if len(bucket) >= self.limit:
            self.buckets[key] = bucket
            return False
        bucket.append(now)
        self.buckets[key] = bucket
        if len(self.buckets) > 4000:
            self.buckets = {
                name: stamps
                for name, stamps in self.buckets.items()
                if stamps and now - stamps[-1] < 60
            }
        return True


limiter = _RateLimiter(settings.relay_rate_limit_per_minute)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    engine = init_engine()
    apply_relay_migrations(engine)
    yield


def _enroll_valid(presented: str) -> bool:
    expected = settings.relay_enroll_token
    if not expected or not presented:
        return False
    return hmac.compare_digest(presented.encode(), expected.encode())


def _client_key(request: Request) -> str:
    token = request.headers.get(DEVICE_HEADER, "")
    if token:
        return "t:" + hashlib.sha256(token.encode()).hexdigest()[:24]
    forwarded = request.headers.get("x-forwarded-for", "")
    host = forwarded.split(",")[0].strip() or (
        request.client.host if request.client else "unknown"
    )
    return "i:" + host


def create_relay_app() -> FastAPI:
    app = FastAPI(
        title="PusatkuPOS Relay",
        version=APP_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def _guard(request: Request, call_next):
        if settings.relay_require_https:
            proto = request.headers.get("x-forwarded-proto", request.url.scheme)
            if proto != "https":
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Relay wajib diakses lewat HTTPS."},
                )
        content_length = request.headers.get("content-length", "")
        if content_length.isdigit():
            limit = settings.relay_max_payload_mb * 1024 * 1024
            if int(content_length) > limit:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Ukuran permintaan melebihi batas relay."},
                )
        if request.url.path != "/relay/health" and not limiter.allow(
            _client_key(request)
        ):
            return JSONResponse(
                status_code=429,
                content={"detail": "Terlalu banyak permintaan. Coba lagi nanti."},
                headers={"Retry-After": "60"},
            )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(service.RelayError)
    async def _relay_error(_request: Request, exc: service.RelayError):
        payload = {"detail": str(exc)}
        if exc.code:
            payload["code"] = exc.code
        return JSONResponse(status_code=exc.status_code, content=payload)

    def _device_actor(
        request: Request, db: Session = Depends(get_relay_db)
    ) -> RelayDevice:
        return service.authenticate(db, request.headers.get(DEVICE_HEADER))

    def _require_enroll(request: Request) -> None:
        if not _enroll_valid(request.headers.get(ENROLL_HEADER, "")):
            raise service.RelayError(
                "Token pendaftaran relay tidak valid.",
                status_code=401,
                code="enroll_token_invalid",
            )

    @app.get("/relay/health")
    def health():
        return {
            "status": "ok",
            "app": "PusatkuPOS Relay",
            "version": APP_VERSION,
            "schema": RELAY_SCHEMA_VERSION,
            "dialect": get_engine().dialect.name,
        }

    @app.post("/relay/devices", status_code=201)
    def enroll_device(
        payload: EnrollIn,
        request: Request,
        db: Session = Depends(get_relay_db),
    ):
        _require_enroll(request)
        return service.register_device(
            db,
            owner_id=payload.owner_id,
            nama=payload.nama,
            kind=payload.kind,
            public_key=payload.public_key,
            encryption_key=payload.encryption_key,
            store_ids=payload.store_ids,
            employee_account_id=payload.employee_account_id,
            signing_public_key=payload.owner_public_key,
        )

    @app.get("/relay/devices/me")
    def current_device(
        device: RelayDevice = Depends(_device_actor),
        db: Session = Depends(get_relay_db),
    ):
        return service.public_device(db, device)

    @app.post("/relay/devices/stores")
    def assign_stores(
        payload: AssignStoresIn,
        device: RelayDevice = Depends(_device_actor),
        db: Session = Depends(get_relay_db),
    ):
        return service.assign_stores(
            db,
            actor=device,
            device_id=payload.device_id,
            store_ids=payload.store_ids,
        )

    @app.post("/relay/devices/{device_id}/revoke")
    def revoke_device(
        device_id: str,
        payload: RevokeIn,
        device: RelayDevice = Depends(_device_actor),
        db: Session = Depends(get_relay_db),
    ):
        return service.revoke_device(
            db, actor=device, device_id=device_id, reason=payload.reason
        )

    @app.post("/relay/devices/claim", status_code=201)
    def claim_device(
        payload: ClaimIn,
        request: Request,
        db: Session = Depends(get_relay_db),
    ):
        actor = None
        token = request.headers.get(DEVICE_HEADER, "")
        if token:
            actor = service.authenticate(db, token)
        elif not _enroll_valid(request.headers.get(ENROLL_HEADER, "")):
            raise service.RelayError(
                "Klaim perangkat memerlukan token perangkat owner.",
                status_code=401,
                code="owner_required",
            )
        return service.claim_device(
            db,
            actor=actor,
            old_device_id=payload.old_device_id,
            public_key=payload.public_key,
            encryption_key=payload.encryption_key,
            nama=payload.nama,
        )

    @app.post("/relay/keys")
    def put_key_wrap(
        payload: KeyWrapIn,
        device: RelayDevice = Depends(_device_actor),
        db: Session = Depends(get_relay_db),
    ):
        return service.put_key_wrap(
            db,
            signer=device,
            store_id=payload.store_id,
            device_id=payload.device_id,
            wrapped_key=payload.wrapped_key,
            signature=payload.signature,
        )

    @app.get("/relay/keys/{store_id}")
    def get_key_wrap(
        store_id: str,
        device: RelayDevice = Depends(_device_actor),
        db: Session = Depends(get_relay_db),
    ):
        return service.get_key_wrap(db, device=device, store_id=store_id)

    @app.post("/relay/envelopes", status_code=201)
    def submit_envelope(
        payload: EnvelopeIn,
        device: RelayDevice = Depends(_device_actor),
        db: Session = Depends(get_relay_db),
    ):
        return service.submit_envelope(db, device=device, **payload.model_dump())

    @app.get("/relay/feed")
    def get_feed(
        store_id: str = Query(..., max_length=32),
        since_seq: int = Query(default=0, ge=0),
        limit: int = Query(default=200, ge=1, le=500),
        device: RelayDevice = Depends(_device_actor),
        db: Session = Depends(get_relay_db),
    ):
        return service.feed(
            db,
            device=device,
            store_id=store_id,
            since_seq=since_seq,
            limit=limit,
        )

    @app.post("/relay/feed/ack")
    def ack_feed(
        payload: FeedAckIn,
        device: RelayDevice = Depends(_device_actor),
        db: Session = Depends(get_relay_db),
    ):
        return service.ack_feed(
            db,
            device=device,
            store_id=payload.store_id,
            last_seq=payload.last_seq,
        )

    @app.post("/relay/snapshots", status_code=201)
    def create_snapshot(
        payload: SnapshotIn,
        device: RelayDevice = Depends(_device_actor),
        db: Session = Depends(get_relay_db),
    ):
        return service.create_snapshot(db, device=device, **payload.model_dump())

    @app.get("/relay/snapshots/{store_id}")
    def latest_snapshot(
        store_id: str,
        device: RelayDevice = Depends(_device_actor),
        db: Session = Depends(get_relay_db),
    ):
        return service.latest_snapshot(db, device=device, store_id=store_id)

    @app.get("/relay/bootstrap")
    def bootstrap(
        store_id: str = Query(..., max_length=32),
        device: RelayDevice = Depends(_device_actor),
        db: Session = Depends(get_relay_db),
    ):
        return service.bootstrap(db, device=device, store_id=store_id)

    @app.post("/relay/purge")
    def purge(request: Request, db: Session = Depends(get_relay_db)):
        _require_enroll(request)
        return service.purge_expired(db)

    return app


app = create_relay_app()
