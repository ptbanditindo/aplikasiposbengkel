"""K-01: retensi backup, pemakaian ulang file Telegram, dan cek ruang disk."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from config import settings
from services import backup_service, telegram_backup_service
from services.errors import BusinessValidationError

BOT_TOKEN = "123456789:ABCdefghijklmnopqrstuvwxyz"


def _backup_files():
    return sorted(settings.backup_dir.glob("bengkel_radiator_*.db"))


def _safety_files():
    return sorted(settings.backup_dir.glob("sebelum_restore_*.db"))


@pytest.fixture(autouse=True)
def clean_backup_dir():
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    for pattern in ("bengkel_radiator_*.db", "sebelum_restore_*.db"):
        for path in settings.backup_dir.glob(pattern):
            path.unlink()
    yield
    for pattern in ("bengkel_radiator_*.db", "sebelum_restore_*.db"):
        for path in settings.backup_dir.glob(pattern):
            path.unlink()


def test_create_backup_memangkas_sampai_batas_retensi(client):
    for _ in range(settings.backup_keep + 3):
        backup_service.create_backup()

    files = _backup_files()
    assert len(files) == settings.backup_keep
    assert settings.backup_keep == 14


def test_restore_memangkas_salinan_sebelum_restore(client):
    backup = client.post("/api/admin/backup")
    assert backup.status_code == 200, backup.text

    for _ in range(5):
        restore = client.post(
            "/api/admin/restore",
            files={"file": ("backup.db", backup.content, "application/x-sqlite3")},
        )
        assert restore.status_code == 200, restore.text

    assert len(_safety_files()) == backup_service.RESTORE_BACKUP_KEEP
    assert backup_service.RESTORE_BACKUP_KEEP == 3


def test_retry_telegram_memakai_ulang_satu_file(client, db_session, monkeypatch):
    response = client.put(
        "/api/settings/telegram",
        json={
            "enabled": True,
            "jam": "21:00",
            "chat_id": "987654321",
            "bot_token": BOT_TOKEN,
        },
    )
    assert response.status_code == 200, response.text

    attempts = []

    def always_fail(*_args, **_kwargs):
        attempts.append(1)
        raise RuntimeError("internet mati")

    monkeypatch.setattr(telegram_backup_service, "_send_document", always_fail)

    for _ in range(5):
        with pytest.raises(BusinessValidationError):
            telegram_backup_service.send_backup(db_session)

    assert len(attempts) == 5
    # Lima percobaan gagal tidak boleh menghasilkan lima file backup.
    assert len(_backup_files()) == 1

    monkeypatch.setattr(
        telegram_backup_service, "_send_document", lambda *_args, **_kwargs: None
    )
    telegram_backup_service.send_backup(db_session)

    # File sementara dihapus setelah berhasil dikirim ke Telegram.
    assert _backup_files() == []


def test_backup_dibatalkan_saat_ruang_disk_kurang(client, monkeypatch):
    monkeypatch.setattr(
        backup_service.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=10**12, used=10**12, free=1024),
    )

    response = client.post("/api/admin/backup")
    assert response.status_code == 400
    assert "ruang" in response.json()["detail"].lower()
    assert _backup_files() == []
