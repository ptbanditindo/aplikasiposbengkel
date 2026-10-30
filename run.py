"""Runner satu klik BengkelPOS Radiator."""
from __future__ import annotations

import argparse
import os
from dataclasses import replace

import uvicorn

from config import set_runtime_port, settings, validate_runtime


def main() -> None:
    parser = argparse.ArgumentParser(description="Jalankan BengkelPOS Radiator")
    parser.add_argument("--host", default=settings.app_host)
    parser.add_argument("--port", type=int, default=settings.app_port)
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Mode pengembangan (auto reload).",
    )
    args = parser.parse_args()

    try:
        validate_runtime(replace(settings, app_host=args.host))
    except RuntimeError as exc:
        print("=" * 58)
        print("  APLIKASI TIDAK DAPAT DIJALANKAN")
        print("=" * 58)
        print(f"  {exc}")
        print("  Web lokal hanya untuk PC kasir ini, bukan jaringan toko.")
        print("=" * 58)
        raise SystemExit(1) from None

    print("=" * 58)
    print(f"  {settings.bengkel_nama}")
    print("  BengkelPOS Radiator v2.0 - Kasir & Servis Multi-Unit")
    print("=" * 58)
    print(f"  Buka: http://127.0.0.1:{args.port}")
    print("  Tekan Ctrl+C untuk berhenti.")
    print("=" * 58)

    # Host/Origin Guard harus mengizinkan port yang benar-benar dilayani
    # Uvicorn, termasuk saat `--port` berbeda dari APP_PORT. Env dipakai agar
    # subprocess `--reload` membaca port yang sama saat impor ulang config.
    os.environ["APP_PORT"] = str(args.port)
    set_runtime_port(args.port)

    uvicorn.run(
        "api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
