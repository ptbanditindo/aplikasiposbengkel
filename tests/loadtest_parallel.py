"""Uji beban manual: 20 POST /api/pos/transaction paralel.

Bukan berkas pytest (nama tidak diawali test_), jalankan langsung:
    python tests/loadtest_parallel.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TMP = Path(tempfile.mkdtemp(prefix="bengkelpos_load_"))
os.environ["APP_ENV"] = "test"
os.environ["APP_HOST"] = "127.0.0.1"
os.environ["APP_PORT"] = "8000"
os.environ["AUTH_MODE"] = "session-pin"
os.environ["DATABASE_URL"] = f"sqlite:///{(TMP / 'load.db').as_posix()}"
os.environ["BACKUP_DIR"] = str(TMP / "backups")
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["TELEGRAM_CHAT_ID"] = ""
os.environ["TELEGRAM_BACKUP_ENABLED"] = "false"
os.environ["BENGKEL_NAMA"] = "BENGKEL LOAD TEST"

from fastapi.testclient import TestClient  # noqa: E402

from api.app import app  # noqa: E402
from database.seed import seed_defaults  # noqa: E402
from database.session import SessionLocal, init_db  # noqa: E402

WORKERS = 20
BASE_URL = "http://127.0.0.1:8000"
PIN = "2468"


def main() -> None:
    init_db()
    with SessionLocal() as db:
        seed_defaults(db)

    with TestClient(app, base_url=BASE_URL) as client:
        setup = client.post("/api/auth/setup", json={"pin": PIN})
        if setup.status_code != 201:
            raise SystemExit(f"Gagal membuat PIN uji beban: {setup.status_code}")

        customer = client.post(
            "/api/customers",
            json={"nama": "Pelanggan Beban", "nomor_hp": "081200000099"},
        ).json()
        unit = client.post(
            "/api/units",
            json={
                "customer_id": customer["id"],
                "unit_type": "MOBIL",
                "nopol": "B 9001 LOAD",
                "jenis_mobil": "Avanza",
            },
        ).json()

        def submit(index: int) -> int:
            try:
                response = client.post(
                    "/api/pos/transaction",
                    json={
                        "unit_id": unit["id"],
                        "keluhan_awal": f"Uji beban {index}",
                        "metode_bayar": "TRANSFER",
                        "jobs": [
                            {
                                "deskripsi": "Korok Radiator",
                                "jumlah": 1,
                                "harga": "150000",
                            }
                        ],
                        "parts": [],
                    },
                )
            except Exception as exc:  # noqa: BLE001 - setara HTTP 500 di server
                print(f"  request {index}: exception {type(exc).__name__}")
                return 500
            if response.status_code != 201:
                print(f"  request {index}: HTTP {response.status_code} {response.text[:160]}")
            return response.status_code

        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            statuses = list(pool.map(submit, range(WORKERS)))

        records = client.get("/api/service-records", params={"limit": 500}).json()
        notas = [row["no_nota"] for row in records]
        print(f"status 201 : {statuses.count(201)}")
        print(f"status 500 : {statuses.count(500)}")
        print(f"status lain: {[s for s in statuses if s not in (201, 500)]}")
        print(f"nota tersimpan: {len(notas)}")
        print(f"nota unik     : {len(set(notas))}")
        print(f"duplikat      : {len(notas) - len(set(notas))}")


if __name__ == "__main__":
    main()
