"""S-07: token Telegram tidak boleh tersisa di backup maupun salinan pra-restore."""
from __future__ import annotations

import sqlite3

import pytest

from config import settings

BOT_TOKEN = "123456789:ABCdefghijklmnopqrstuvwxyz"


def _configure_telegram(client):
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


def test_backup_tidak_memuat_token_telegram(client):
    _configure_telegram(client)

    response = client.post("/api/admin/backup")
    assert response.status_code == 200, response.text
    assert BOT_TOKEN.encode() not in response.content

    path = sorted(settings.backup_dir.glob("bengkel_radiator_*.db"))[-1]
    connection = sqlite3.connect(str(path))
    try:
        stored = connection.execute(
            "SELECT value FROM app_settings WHERE key = 'telegram.bot_token'"
        ).fetchone()
        assert stored == ("",)
    finally:
        connection.close()


def test_salinan_sebelum_restore_tidak_memuat_token(client):
    _configure_telegram(client)

    backup = client.post("/api/admin/backup")
    assert backup.status_code == 200, backup.text

    restore = client.post(
        "/api/admin/restore",
        files={"file": ("backup.db", backup.content, "application/x-sqlite3")},
    )
    assert restore.status_code == 200, restore.text

    safety = _safety_files()
    assert len(safety) == 1
    assert BOT_TOKEN.encode() not in safety[0].read_bytes()

    connection = sqlite3.connect(str(safety[0]))
    try:
        stored = connection.execute(
            "SELECT value FROM app_settings WHERE key = 'telegram.bot_token'"
        ).fetchone()
        assert stored is None or stored == ("",)
    finally:
        connection.close()
