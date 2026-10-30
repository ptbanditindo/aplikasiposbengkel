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
    auth_routes,
    customer_routes,
    pos_routes,
    report_routes,
    settings_routes,
    stock_routes,
)
from api.deps import require_auth
from api.schemas import (
    BengkelInfoOut,
    ConfigOut,
    PrinterInfoOut,
    TelegramInfoOut,
)
from api.security import UNSAFE_METHODS, allowed_origins, host_header_allowed
from config import BASE_DIR, settings, validate_runtime
from database.seed import seed_defaults
from database.session import SessionLocal, get_db, init_db
from services import settings_service, telegram_backup_service
from services.errors import (
    AuthenticationError,
    ConflictError,
    DomainError,
    InsufficientStockError,
    NotFoundError,
    RateLimitError,
)

FRONTEND_DIR = BASE_DIR / "frontend"
APP_VERSION = "2.0.0"

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
    init_db()
    with SessionLocal() as db:
        seed_defaults(db)
    scheduler = None
    if settings.app_env != "test":
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
        host_header = request.headers.get("host", "")
        if not host_header_allowed(host_header, settings.app_port):
            return JSONResponse(
                status_code=400,
                content={
                    "detail": (
                        "Alamat server tidak diizinkan. Buka aplikasi dari "
                        f"http://127.0.0.1:{settings.app_port} pada PC ini."
                    )
                },
            )

        if request.method in UNSAFE_METHODS:
            origin = request.headers.get("origin", "")
            if origin and origin.rstrip("/") not in allowed_origins(
                settings.app_port
            ):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Permintaan dari alamat lain ditolak."
                    },
                )

        return await call_next(request)

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
    app.include_router(pos_routes.router, prefix=api_prefix)
    app.include_router(stock_routes.router, prefix=api_prefix)
    app.include_router(report_routes.router, prefix=api_prefix)
    app.include_router(settings_routes.router, prefix=api_prefix)

    @app.get("/api/health", tags=["Sistem"])
    def health():
        return {"status": "ok", "app": "BengkelPOS Radiator", "version": APP_VERSION}

    @app.get(
        "/api/config",
        response_model=ConfigOut,
        tags=["Sistem"],
        dependencies=[Depends(require_auth)],
    )
    def app_config(db: Session = Depends(get_db)):
        return ConfigOut(
            version=APP_VERSION,
            bengkel=BengkelInfoOut(**settings_service.get_bengkel_info(db)),
            telegram=TelegramInfoOut(
                **settings_service.telegram_public_info(
                    settings_service.get_telegram_config(db)
                )
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
