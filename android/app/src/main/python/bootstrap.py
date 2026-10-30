"""Menjalankan backend FastAPI di dalam proses Android (Chaquopy).

Dipanggil dari BackendManager.kt:
    start(backend_dir, files_dir, port, admin_token)
    stop()

Modul backend di-purge setiap start/stop supaya konfigurasi (DATABASE_URL,
AUTH_MODE, APP_INSTALL_TOKEN) dan engine SQLAlchemy dibangun ulang dengan
benar setelah reset data di proses yang sama.
"""
from __future__ import annotations

import os
import sys
import threading

_BACKEND_MODULES = ("api", "services", "repositories", "database", "config")

_server = None
_thread = None


def _purge_backend_modules() -> None:
    for name in list(sys.modules):
        if name.split(".", 1)[0] in _BACKEND_MODULES:
            del sys.modules[name]


def start(backend_dir: str, files_dir: str, port: int, admin_token: str) -> None:
    global _server, _thread
    if _server is not None and _thread is not None and _thread.is_alive():
        return

    os.environ["APP_ENV"] = "production"
    os.environ["APP_HOST"] = "127.0.0.1"
    os.environ["APP_PORT"] = str(port)
    os.environ["DATABASE_URL"] = (
        "sqlite:///" + os.path.join(files_dir, "data", "bengkel_radiator.db")
    )
    os.environ["BACKUP_DIR"] = os.path.join(files_dir, "backups")
    # Konfigurasi printer harus berada di direktori tulis milik aplikasi,
    # bukan direktori aset backend yang bersifat sementara.
    os.environ["PRINTER_CONFIG_PATH"] = os.path.join(
        files_dir, "data", "printer_config.json"
    )
    # Penjadwalan dipegang WorkManager Android, bukan thread Python yang ikut
    # mati saat proses aplikasi dibunuh sistem.
    os.environ["BACKUP_SCHEDULER"] = "workmanager"
    # APK memakai PIN native + token per-instalasi, bukan PIN web.
    os.environ["AUTH_MODE"] = "install-token"
    os.environ["APP_INSTALL_TOKEN"] = admin_token

    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    _purge_backend_modules()

    import uvicorn

    from api.app import app

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        log_config=None,
        access_log=False,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="bengkel-uvicorn", daemon=True)
    _server, _thread = server, thread
    thread.start()


def is_alive() -> bool:
    """True bila thread uvicorn masih hidup (dipakai BackendManager)."""
    return _thread is not None and _thread.is_alive()


def stop() -> None:
    global _server, _thread
    server, thread = _server, _thread
    _server = None
    _thread = None
    if server is not None:
        server.should_exit = True
        if thread is not None:
            thread.join(timeout=15)
        try:
            from database.session import engine

            engine.dispose()
        except Exception:
            pass
    _purge_backend_modules()
