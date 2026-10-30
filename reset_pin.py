"""Reset PIN kasir web lokal (tanpa menghapus data bengkel).

Jalankan langsung di PC kasir saat server berhenti:

    python reset_pin.py

Skrip meminta konfirmasi, lalu menghapus hanya kunci `auth.*` di
`app_settings`. Data pelanggan, stok, nota, dan backup tidak disentuh. Saat
aplikasi dibuka lagi, layar pembuatan PIN akan muncul.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Optional

from config import BASE_DIR, settings

AUTH_KEY_PREFIX = "auth."
CONFIRMATION = "RESET"


def resolve_database_path(url: Optional[str] = None) -> Optional[Path]:
    raw_url = (url or settings.database_url).strip()
    prefix = "sqlite:///"
    if not raw_url.startswith(prefix) or ":memory:" in raw_url:
        return None
    path = Path(raw_url[len(prefix):])
    if not path.is_absolute():
        path = (BASE_DIR / path).resolve()
    return path


def clear_pin(db_path: Path) -> int:
    """Hapus hash PIN + sesi, kembalikan jumlah kunci yang dihapus."""
    with sqlite3.connect(str(db_path)) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if "app_settings" not in tables:
            raise RuntimeError(
                "Berkas ini bukan database BengkelPOS (tabel app_settings tidak ada)."
            )
        cursor = conn.execute(
            "DELETE FROM app_settings WHERE key LIKE ?", (f"{AUTH_KEY_PREFIX}%",)
        )
        conn.commit()
        return max(0, cursor.rowcount)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Hapus PIN kasir web lokal agar dapat dibuat ulang."
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path database SQLite (default dari DATABASE_URL).",
    )
    args = parser.parse_args(argv)

    db_path = Path(args.db) if args.db else resolve_database_path()
    if db_path is None:
        print(
            "Reset hanya tersedia untuk database SQLite lokal. "
            "DATABASE_URL saat ini bukan berkas SQLite."
        )
        return 2
    if not db_path.exists():
        print(f"Database tidak ditemukan: {db_path}")
        return 2
    if not sys.stdin.isatty():
        print("Jalankan skrip ini langsung dari terminal di PC kasir.")
        return 2

    print("=" * 60)
    print("  RESET PIN KASIR - BengkelPOS Radiator")
    print("=" * 60)
    print(f"  Database : {db_path}")
    print("  Yang dihapus : PIN dan sesi login.")
    print("  Yang tetap   : pelanggan, stok, nota, laporan, backup.")
    print("  Setelah reset, buka aplikasi untuk membuat PIN baru.")
    print("=" * 60)

    if input(f'Ketik "{CONFIRMATION}" untuk melanjutkan: ').strip() != CONFIRMATION:
        print("Dibatalkan. Tidak ada data yang diubah.")
        return 1

    try:
        removed = clear_pin(db_path)
    except (sqlite3.Error, RuntimeError) as exc:
        print(f"Gagal mereset PIN: {exc}")
        return 3

    print(f"PIN dihapus ({removed} kunci kredensial). Data lain tidak disentuh.")
    print("Buka aplikasi dan buat PIN baru.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
