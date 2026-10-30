"""Inisialisasi aplikasi FastAPI BengkelPOS Radiator."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from api import customer_routes, pos_routes, report_routes, stock_routes
from api.schemas import (
    BengkelInfoOut,
    ConfigOut,
    PrinterInfoOut,
)
from config import BASE_DIR, settings
from database.seed import seed_defaults
from database.session import SessionLocal, init_db
from services.errors import (
    ConflictError,
    DomainError,
    InsufficientStockError,
    NotFoundError,
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
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="BengkelPOS Radiator",
        description=(
            "Sistem kasir, manajemen servis multi-unit & cetak struk "
            "Bluetooth thermal bengkel radiator."
        ),
        version=APP_VERSION,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost", "http://127.0.0.1"],
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(NotFoundError)
    async def _not_found(_request: Request, exc: NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

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
    app.include_router(customer_routes.router, prefix=api_prefix)
    app.include_router(pos_routes.router, prefix=api_prefix)
    app.include_router(stock_routes.router, prefix=api_prefix)
    app.include_router(report_routes.router, prefix=api_prefix)

    @app.get("/api/health", tags=["Sistem"])
    def health():
        return {"status": "ok", "app": "BengkelPOS Radiator", "version": APP_VERSION}

    @app.get("/api/config", response_model=ConfigOut, tags=["Sistem"])
    def app_config():
        return ConfigOut(
            version=APP_VERSION,
            bengkel=BengkelInfoOut(
                nama=settings.bengkel_nama,
                tagline=settings.bengkel_tagline,
                alamat=settings.bengkel_alamat,
                telepon=settings.bengkel_telepon,
                wa=settings.bengkel_wa,
                bank_nama=settings.bengkel_bank_nama,
                no_rekening=settings.bengkel_no_rekening,
                atas_nama=settings.bengkel_atas_nama,
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
            admin_token_required=settings.admin_token_required,
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
