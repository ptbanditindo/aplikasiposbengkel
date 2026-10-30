"""S-05: unggahan restore dibatasi ukuran, dialirkan, dan divalidasi."""
from __future__ import annotations

import sqlite3
from dataclasses import replace

import pytest

from api import report_routes
from config import settings, load_settings

UPLOAD_GLOB = "upload_restore_*"


@pytest.fixture(autouse=True)
def clean_upload_temp():
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    for path in settings.backup_dir.glob(UPLOAD_GLOB):
        path.unlink()
    yield
    for path in settings.backup_dir.glob(UPLOAD_GLOB):
        path.unlink()


def _upload(client, content: bytes, name: str = "backup.db"):
    return client.post(
        "/api/admin/restore",
        files={"file": (name, content, "application/x-sqlite3")},
    )


def _upload_files():
    return list(settings.backup_dir.glob(UPLOAD_GLOB))


def test_batas_ukuran_restore_dapat_diatur_dari_env(monkeypatch):
    assert load_settings().backup_max_restore_mb == 64

    monkeypatch.setenv("BACKUP_MAX_RESTORE_MB", "32")
    assert load_settings().backup_max_restore_mb == 32


def test_upload_terlalu_besar_ditolak_413_tanpa_file_sementara(
    client, monkeypatch
):
    monkeypatch.setattr(
        report_routes, "settings", replace(settings, backup_max_restore_mb=1)
    )

    content = b"SQLite format 3\x00" + b"\x00" * (1024 * 1024 + 1024)
    response = _upload(client, content)

    assert response.status_code == 413, response.text
    assert "besar" in response.json()["detail"].lower()
    assert _upload_files() == []
    assert client.get("/api/stock").status_code == 200


def test_upload_dibaca_per_bagian_bukan_sekaligus():
    from api.report_routes import UPLOAD_CHUNK_SIZE, _save_upload

    class FakeUpload:
        def __init__(self, data: bytes):
            self._data = data
            self._pos = 0
            self.read_sizes = []
            self.closed = False

        async def read(self, size: int = -1) -> bytes:
            self.read_sizes.append(size)
            if size is None or size < 0:
                size = len(self._data) - self._pos
            chunk = self._data[self._pos : self._pos + size]
            self._pos += len(chunk)
            return chunk

        async def close(self) -> None:
            self.closed = True

    upload = FakeUpload(b"x" * (UPLOAD_CHUNK_SIZE * 2 + 10))
    path = None
    try:
        import asyncio

        path = asyncio.run(
            _save_upload(upload, max_bytes=UPLOAD_CHUNK_SIZE * 4)
        )
        assert upload.read_sizes[0] == UPLOAD_CHUNK_SIZE
        assert all(size == UPLOAD_CHUNK_SIZE for size in upload.read_sizes)
        assert path.stat().st_size == UPLOAD_CHUNK_SIZE * 2 + 10
        assert upload.closed is True
    finally:
        if path is not None:
            path.unlink(missing_ok=True)


def test_backup_tanpa_kolom_wajib_ditolak(client, tmp_path):
    backup = client.post("/api/admin/backup")
    assert backup.status_code == 200

    path = tmp_path / "kolom_hilang.db"
    path.write_bytes(backup.content)
    connection = sqlite3.connect(str(path))
    try:
        connection.execute("ALTER TABLE customers DROP COLUMN alamat")
        connection.commit()
    finally:
        connection.close()

    response = _upload(client, path.read_bytes(), name="kolom_hilang.db")

    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert "kolom" in detail.lower()
    assert "customers.alamat" in detail
    assert _upload_files() == []
    assert client.get("/api/stock").status_code == 200


def test_backup_rusak_ditolak(client):
    backup = client.post("/api/admin/backup")
    assert backup.status_code == 200

    response = _upload(client, backup.content[:120], name="terpotong.db")

    assert response.status_code == 400, response.text
    assert "rusak" in response.json()["detail"].lower()
    assert _upload_files() == []


def test_backup_sah_dipulihkan_tanpa_menyisakan_file_sementara(
    client, create_customer, reauth
):
    customer = create_customer(nama="Pelanggan Sebelum Restore", nomor_hp="081200000080")
    backup = client.post("/api/admin/backup")
    assert backup.status_code == 200

    response = _upload(client, backup.content)

    assert response.status_code == 200, response.text
    assert _upload_files() == []
    reauth()
    hasil = client.get("/api/customers/search", params={"q": "Sebelum Restore"})
    assert [item["id"] for item in hasil.json()] == [customer["id"]]
