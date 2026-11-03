"""Runner server relay premium (profil terpisah, K-24)."""
from __future__ import annotations

import argparse
import os

import uvicorn

from config import settings, validate_relay_runtime


def main() -> None:
    parser = argparse.ArgumentParser(description="Jalankan server relay PusatkuPOS")
    parser.add_argument("--host", default=settings.relay_host)
    parser.add_argument("--port", type=int, default=settings.relay_port)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    try:
        validate_relay_runtime()
    except RuntimeError as exc:
        print("=" * 58)
        print("  RELAY TIDAK DAPAT DIJALANKAN")
        print("=" * 58)
        print(f"  {exc}")
        print("=" * 58)
        raise SystemExit(1) from None

    os.environ["RELAY_PORT"] = str(args.port)
    print("=" * 58)
    print("  PusatkuPOS Relay")
    print(f"  Database: {settings.relay_database_url.split('://')[0]}")
    print(f"  Buka: http://{args.host}:{args.port}/relay/health")
    print("  Tekan Ctrl+C untuk berhenti.")
    print("=" * 58)

    uvicorn.run(
        "relay.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
