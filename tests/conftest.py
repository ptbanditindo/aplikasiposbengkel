"""Konfigurasi pytest & fixture bersama.

Strategi isolasi:
- Variabel lingkungan di-set SEBELUM `config` / `api.app` diimpor.
- Basis data SQLite sementara (file, agar fitur backup dapat diuji).
- Setiap test memulai dari skema kosong + data seed default.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

TEST_ROOT = Path(tempfile.mkdtemp(prefix="bengkelpos_tests_"))
TEST_DB = TEST_ROOT / "bengkel_test.db"
TEST_BACKUP_DIR = TEST_ROOT / "backups"

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["UI_ACCESS_TOKEN"] = "test-admin-token"
os.environ["BACKUP_DIR"] = str(TEST_BACKUP_DIR)
os.environ["BENGKEL_NAMA"] = "BENGKEL RADIATOR TEST"
os.environ["BENGKEL_TAGLINE"] = "Spesialis Servis & Las Radiator"
os.environ["BENGKEL_ALAMAT"] = "Jl. Uji Otomotif No. 1"
os.environ["BENGKEL_TELEPON"] = "081200000000"
os.environ["BENGKEL_WA"] = "081200000000"
os.environ["BENGKEL_BANK_NAMA"] = "BCA TEST"
os.environ["BENGKEL_NO_REKENING"] = "987-654-3210"
os.environ["BENGKEL_ATAS_NAMA"] = "BENGKEL RADIATOR TEST"
os.environ["PRINTER_PAPER_WIDTH"] = "58"
os.environ["DEFAULT_GARANSI_BULAN"] = "1"
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["TELEGRAM_CHAT_ID"] = ""
os.environ["TELEGRAM_BACKUP_ENABLED"] = "false"
os.environ["TELEGRAM_BACKUP_TIME"] = "21:00"

from fastapi.testclient import TestClient  # noqa: E402

from api.app import app  # noqa: E402
from database.base import Base  # noqa: E402
from database.seed import seed_defaults  # noqa: E402
from database.session import SessionLocal, engine  # noqa: E402

ADMIN_HEADERS = {"X-Admin-Token": "test-admin-token"}


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def reset_database(client):
    """Skema bersih + seed standar untuk setiap skenario uji."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_defaults(db)
    yield


@pytest.fixture()
def db_session():
    with SessionLocal() as session:
        yield session


@pytest.fixture()
def create_customer(client):
    def _create(nama="Budi Santoso", nomor_hp="0812-3456-7890", alamat="Jl. Mawar 1"):
        response = client.post(
            "/api/customers",
            json={"nama": nama, "nomor_hp": nomor_hp, "alamat": alamat},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _create


@pytest.fixture()
def create_unit(client):
    def _create(
        customer_id,
        unit_type="MOBIL",
        nopol="B 1234 ABC",
        jenis_mobil="Avanza",
        tahun_mobil=2015,
        tipe_radiator=None,
        keterangan=None,
    ):
        payload = {
            "customer_id": customer_id,
            "unit_type": unit_type,
            "nopol": nopol,
            "jenis_mobil": jenis_mobil,
            "tahun_mobil": tahun_mobil,
            "tipe_radiator": tipe_radiator,
            "keterangan": keterangan,
        }
        response = client.post("/api/units", json=payload)
        assert response.status_code == 201, response.text
        return response.json()

    return _create


@pytest.fixture()
def make_transaction(client):
    def _create(unit_id, jobs=None, parts=None, **overrides):
        payload = {
            "unit_id": unit_id,
            "keluhan_awal": "Overheat / panas berlebih",
            "metode_bayar": "TRANSFER",
            "bergaransi": True,
            "garansi_bulan": 1,
            "jobs": jobs
            if jobs is not None
            else [
                {
                    "deskripsi": "Korok / Kuras Kerak Radiator",
                    "jumlah": 1,
                    "harga": "150000",
                }
            ],
            "parts": parts or [],
        }
        payload.update(overrides)
        return client.post("/api/pos/transaction", json=payload)

    return _create


@pytest.fixture()
def stock(client):
    def _get(kode):
        response = client.get("/api/stock")
        assert response.status_code == 200, response.text
        return next(item for item in response.json() if item["kode"] == kode)

    return _get


@pytest.fixture()
def jasa(client):
    def _get(nama):
        response = client.get("/api/harga-jasa")
        assert response.status_code == 200, response.text
        return next(item for item in response.json() if item["nama"] == nama)

    return _get
