"""Konfigurasi aplikasi BengkelPOS Radiator.

Seluruh identitas bengkel, rekening bank, dan rahasia dimuat dari variabel
lingkungan (.env). Tidak ada nilai sensitif yang di-hardcode di kode.
Ref: PRD NFR-SEC-01, PROMPT_AUDIT FASE 1.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _as_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "ya"}


def _as_int(name: str, default: int) -> int:
    try:
        return int(str(os.getenv(name, default)).strip())
    except (TypeError, ValueError):
        return default


def _as_path(name: str, default: str) -> Path:
    raw = os.getenv(name, default)
    path = Path(raw)
    if not path.is_absolute():
        path = (BASE_DIR / path).resolve()
    return path


@dataclass(frozen=True)
class Settings:
    app_env: str
    app_host: str
    app_port: int
    auth_mode: str
    ui_access_token: str

    database_url: str

    bengkel_nama: str
    bengkel_tagline: str
    bengkel_alamat: str
    bengkel_telepon: str
    bengkel_wa: str

    bengkel_bank_nama: str
    bengkel_no_rekening: str
    bengkel_atas_nama: str

    printer_paper_width: int
    printer_encoding: str
    printer_auto_cut: bool
    printer_open_drawer: bool

    default_garansi_bulan: int
    garansi_syarat: str

    backup_dir: Path
    backup_keep: int

    telegram_bot_token: str
    telegram_chat_id: str
    telegram_backup_enabled: bool
    telegram_backup_time: str
    telegram_api_base: str

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def admin_token_required(self) -> bool:
        return bool(self.ui_access_token.strip())


def load_settings() -> Settings:
    # Ref: PRD FR-PRN-05 / FR-POS-07 - identitas bengkel & rekening transfer
    return Settings(
        app_env=os.getenv("APP_ENV", "development").strip(),
        app_host=os.getenv("APP_HOST", "127.0.0.1").strip(),
        app_port=_as_int("APP_PORT", 8000),
        auth_mode=os.getenv("AUTH_MODE", "session-pin").strip().lower(),
        ui_access_token=os.getenv("UI_ACCESS_TOKEN", "").strip(),
        database_url=os.getenv(
            "DATABASE_URL", "sqlite:///./data/bengkel_radiator.db"
        ).strip(),
        bengkel_nama=os.getenv("BENGKEL_NAMA", "BENGKEL RADIATOR").strip(),
        bengkel_tagline=os.getenv(
            "BENGKEL_TAGLINE", "Spesialis Servis, Korok & Las Radiator"
        ).strip(),
        bengkel_alamat=os.getenv("BENGKEL_ALAMAT", "-").strip(),
        bengkel_telepon=os.getenv("BENGKEL_TELEPON", "-").strip(),
        bengkel_wa=os.getenv("BENGKEL_WA", "-").strip(),
        bengkel_bank_nama=os.getenv("BENGKEL_BANK_NAMA", "-").strip(),
        bengkel_no_rekening=os.getenv("BENGKEL_NO_REKENING", "-").strip(),
        bengkel_atas_nama=os.getenv("BENGKEL_ATAS_NAMA", "-").strip(),
        printer_paper_width=_as_int("PRINTER_PAPER_WIDTH", 58),
        printer_encoding=os.getenv("PRINTER_DEFAULT_ENCODING", "CP437").strip(),
        printer_auto_cut=_as_bool("PRINTER_AUTO_CUT", False),
        printer_open_drawer=_as_bool("PRINTER_OPEN_DRAWER", False),
        default_garansi_bulan=_as_int("DEFAULT_GARANSI_BULAN", 1),
        garansi_syarat=os.getenv(
            "GARANSI_SYARAT_STANDAR",
            "Garansi kebocoran berlaku pada titik pengerjaan las & penggantian tangki baru.",
        ).strip(),
        backup_dir=_as_path("BACKUP_DIR", "./backups"),
        backup_keep=max(1, _as_int("BACKUP_KEEP", 14)),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        telegram_backup_enabled=_as_bool("TELEGRAM_BACKUP_ENABLED", False),
        telegram_backup_time=os.getenv("TELEGRAM_BACKUP_TIME", "21:00").strip(),
        telegram_api_base=os.getenv(
            "TELEGRAM_API_BASE", "https://api.telegram.org"
        ).strip(),
    )


settings = load_settings()

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
SUPPORTED_AUTH_MODES = frozenset({"session-pin"})


def validate_runtime(candidate: Settings | None = None) -> None:
    """Gagal cepat dengan pesan jelas bila konfigurasi membuka akses jaringan.

    Web lokal hanya untuk PC kasir itu sendiri; bind ke `0.0.0.0` atau IP LAN
    ditolak agar data bengkel tidak terbuka untuk perangkat lain.
    """
    runtime = candidate or settings

    host = runtime.app_host.strip().lower()
    if host not in LOOPBACK_HOSTS:
        raise RuntimeError(
            f"APP_HOST '{runtime.app_host}' tidak diizinkan. Web lokal hanya "
            "boleh diakses dari PC ini: gunakan APP_HOST=127.0.0.1."
        )

    if runtime.auth_mode not in SUPPORTED_AUTH_MODES:
        raise RuntimeError(
            f"AUTH_MODE '{runtime.auth_mode}' tidak dikenal. Gunakan salah "
            f"satu dari: {', '.join(sorted(SUPPORTED_AUTH_MODES))}."
        )

