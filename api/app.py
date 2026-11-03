"""Inisialisasi aplikasi FastAPI BengkelPOS Radiator."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from api import (
    audit_routes,
    auth_routes,
    customer_routes,
    employee_routes,
    followup_routes,
    payment_routes,
    pos_routes,
    premium_routes,
    printer_routes,
    report_routes,
    settings_routes,
    stock_routes,
    store_routes,
    supplier_routes,
    whatsapp_routes,
)
from api.deps import require_auth
from api.schemas import (
    BackupStatusOut,
    BengkelInfoOut,
    ConfigOut,
    EntitlementOut,
    FollowupQuotaOut,
    LicenseInfoOut,
    OperatorOut,
    OpsSettingsOut,
    PremiumStatusOut,
    PrinterInfoOut,
    ReceiptSettingsOut,
    StoreOut,
    TelegramInfoOut,
)
from api.security import UNSAFE_METHODS, allowed_origins, host_header_allowed
from config import (
    APP_VERSION,
    BASE_DIR,
    effective_app_port,
    settings,
    validate_runtime,
)
from database.session import get_db, get_primary_db
from services import (
    entitlement_service,
    followup_quota_service,
    license_service,
    settings_service,
    store_service,
    telegram_backup_service,
)
from services.auth_service import Operator
from services.maintenance import HEALTH_PATH, RESTORE_PATHS, gate
from services.errors import (
    AuthenticationError,
    ConflictError,
    DomainError,
    FeatureLockedError,
    InsufficientStockError,
    NotFoundError,
    RateLimitError,
)

FRONTEND_DIR = BASE_DIR / "frontend"

KELUHAN_PRESETS = [
    "Overheat / panas berlebih",
    "Air radiator tekor",
    "Bocor tangki atas",
    "Bocor tangki bawah",
    "Korok / kuras kerak",
    "Las kisi-kisi bocor",
    "Selang radiator bocor",
    "Kipas tidak berputar",
]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    store_service.ensure_startup_state()
    scheduler = None
    if settings.app_env != "test" and settings.backup_scheduler != "workmanager":
        scheduler = asyncio.create_task(telegram_backup_service.scheduler_loop())
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.cancel()
            with suppress(asyncio.CancelledError):
                await scheduler


def create_app() -> FastAPI:
    validate_runtime()

    app = FastAPI(
        title="BengkelPOS Radiator",
        description=(
            "Sistem kasir, manajemen servis multi-unit & cetak struk "
            "Bluetooth thermal bengkel radiator."
        ),
        version=APP_VERSION,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    # Ref: K-02 - frontend selalu disajikan dari origin yang sama, jadi CORS
    # dimatikan total dan permintaan lintas-origin ditolak oleh middleware.
    @app.middleware("http")
    async def _access_guard(request: Request, call_next):
        port = effective_app_port()
        host_header = request.headers.get("host", "")
        if not host_header_allowed(host_header, port):
            return JSONResponse(
                status_code=400,
                content={
                    "detail": (
                        "Alamat server tidak diizinkan. Buka aplikasi dari "
                        f"http://127.0.0.1:{port} pada PC ini."
                    )
                },
            )

        if request.method in UNSAFE_METHODS:
            origin = request.headers.get("origin", "")
            if origin and origin.rstrip("/") not in allowed_origins(port):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Permintaan dari alamat lain ditolak."
                    },
                )

        path = request.url.path
        if path in RESTORE_PATHS and gate.is_restoring():
            # Restore kedua ditolak sebelum autentikasi: data sesi di database
            # lama mungkin sudah diganti saat restore pertama berjalan.
            return JSONResponse(
                status_code=503,
                content={
                    "detail": (
                        "Sedang memulihkan database. Tunggu sampai proses "
                        "selesai lalu coba lagi."
                    )
                },
            )
        counted = path not in (HEALTH_PATH, *RESTORE_PATHS)
        if counted and not gate.try_enter():
            return JSONResponse(
                status_code=503,
                content={
                    "detail": (
                        "Sedang memulihkan database. Tunggu sampai proses "
                        "selesai lalu coba lagi."
                    )
                },
            )

        try:
            return await call_next(request)
        finally:
            if counted:
                gate.leave()

    @app.exception_handler(NotFoundError)
    async def _not_found(_request: Request, exc: NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(AuthenticationError)
    async def _authentication(_request: Request, exc: AuthenticationError):
        return JSONResponse(
            status_code=401,
            content={"detail": str(exc)},
            headers={"WWW-Authenticate": "Session"},
        )

    @app.exception_handler(RateLimitError)
    async def _rate_limit(_request: Request, exc: RateLimitError):
        return JSONResponse(
            status_code=429,
            content={"detail": str(exc)},
            headers={"Retry-After": str(exc.retry_after)},
        )

    @app.exception_handler(FeatureLockedError)
    async def _feature_locked(_request: Request, exc: FeatureLockedError):
        return JSONResponse(
            status_code=403,
            content={"detail": str(exc), "code": exc.code},
        )

    @app.exception_handler(InsufficientStockError)
    async def _insufficient_stock(_request: Request, exc: InsufficientStockError):
        return JSONResponse(
            status_code=409,
            content={
                "detail": {
                    "message": str(exc),
                    "items": exc.items,
                }
            },
        )

    @app.exception_handler(ConflictError)
    async def _conflict(_request: Request, exc: ConflictError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(DomainError)
    async def _domain(_request: Request, exc: DomainError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    api_prefix = "/api"
    app.include_router(auth_routes.router, prefix=api_prefix)
    app.include_router(customer_routes.router, prefix=api_prefix)
    app.include_router(employee_routes.router, prefix=api_prefix)
    app.include_router(pos_routes.router, prefix=api_prefix)
    app.include_router(payment_routes.router, prefix=api_prefix)
    app.include_router(whatsapp_routes.router, prefix=api_prefix)
    app.include_router(followup_routes.router, prefix=api_prefix)
    app.include_router(stock_routes.router, prefix=api_prefix)
    app.include_router(supplier_routes.router, prefix=api_prefix)
    app.include_router(report_routes.router, prefix=api_prefix)
    app.include_router(settings_routes.router, prefix=api_prefix)
    app.include_router(store_routes.router, prefix=api_prefix)
    app.include_router(premium_routes.router, prefix=api_prefix)
    app.include_router(printer_routes.router, prefix=api_prefix)
    app.include_router(audit_routes.router, prefix=api_prefix)

    @app.get("/api/health", tags=["Sistem"])
    def health():
        return {"status": "ok", "app": "BengkelPOS Radiator", "version": APP_VERSION}

    @app.get(
        "/api/config",
        response_model=ConfigOut,
        tags=["Sistem"],
    )
    def app_config(
        operator: Operator = Depends(require_auth),
        db: Session = Depends(get_db),
        primary_db: Session = Depends(get_primary_db),
    ):
        telegram_config = settings_service.get_telegram_config(db)
        allowed = operator.stores if operator.kind == "employee" else None
        stores = store_service.list_stores(allowed_store_ids=allowed)
        license_info = license_service.status(primary_db)
        plan = entitlement_service.get_plan()
        premium = PremiumStatusOut(
            plan=plan,
            premium=plan == "premium",
            owner_id=license_info["owner_id"],
            owner_public_key=license_info["owner_public_key"],
            license=LicenseInfoOut(**license_info["license"]),
            recovery_pending=license_info["recovery_pending"],
        )
        operator_out = OperatorOut(
            id=operator.id,
            kind=operator.kind,
            role=operator.role,
            label=operator.label,
            permissions=sorted(operator.permissions),
            stores=list(operator.stores),
            device_id=operator.device_id,
            must_change_password=operator.must_change_password,
        )
        return ConfigOut(
            version=APP_VERSION,
            bengkel=BengkelInfoOut(**settings_service.get_bengkel_info(db)),
            telegram=TelegramInfoOut(
                **settings_service.telegram_public_info(telegram_config)
            ),
            backup=BackupStatusOut(
                **settings_service.get_backup_status(db, telegram_config)
            ),
            printer=PrinterInfoOut(
                paper_width=settings.printer_paper_width,
                encoding=settings.printer_encoding,
                auto_cut=settings.printer_auto_cut,
            ),
            default_garansi_bulan=settings.default_garansi_bulan,
            garansi_syarat=settings.garansi_syarat,
            metode_bayar=["CASH", "TRANSFER"],
            keluhan_presets=KELUHAN_PRESETS,
            ops=OpsSettingsOut(**settings_service.get_ops_settings(db)),
            receipt=ReceiptSettingsOut(**settings_service.get_receipt_settings(db)),
            entitlement=EntitlementOut(**stores["entitlement"]),
            stores=[StoreOut(**row) for row in stores["toko"]],
            store_aktif=stores["aktif"],
            kuota_followup=FollowupQuotaOut(
                **followup_quota_service.status(db)
            ),
            operator=operator_out,
            premium=premium,
        )

    if FRONTEND_DIR.exists():
        app.mount(
            "/static",
            StaticFiles(directory=str(FRONTEND_DIR)),
            name="static",
        )

    @app.get("/", include_in_schema=False)
    def index():
        index_file = FRONTEND_DIR / "index.html"
        if not index_file.exists():
            return JSONResponse(
                status_code=503,
                content={"detail": "Frontend belum tersedia."},
            )
        return FileResponse(
            str(index_file), headers={"Cache-Control": "no-store"}
        )

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        icon = FRONTEND_DIR / "favicon.svg"
        if icon.exists():
            return FileResponse(str(icon), media_type="image/svg+xml")
        return JSONResponse(status_code=204, content=None)

    return app


app = create_app()
