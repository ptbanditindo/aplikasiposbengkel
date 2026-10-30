"""T-04: restore tidak boleh menghapus konfigurasi Telegram secara diam-diam."""
from __future__ import annotations

from dataclasses import replace

from config import settings
from services import settings_service

BOT_TOKEN = "123456789:ABCdefghijklmnopqrstuvwxyz"


def _configure(client):
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


def _backup_and_restore(client):
    backup = client.post("/api/admin/backup")
    assert backup.status_code == 200, backup.text
    restore = client.post(
        "/api/admin/restore",
        files={"file": ("backup.db", backup.content, "application/x-sqlite3")},
    )
    assert restore.status_code == 200, restore.text


def test_restore_memakai_fallback_env(client, monkeypatch):
    monkeypatch.setattr(
        settings_service,
        "settings",
        replace(
            settings,
            telegram_bot_token=BOT_TOKEN,
            telegram_chat_id="555000111",
            telegram_backup_enabled=True,
            telegram_backup_time="21:00",
        ),
    )
    _configure(client)
    _backup_and_restore(client)

    telegram = client.get("/api/config").json()["telegram"]
    assert telegram["configured"] is True
    assert telegram["needs_reconfig"] is False
    assert telegram["chat_id"] == "987654321"


def test_restore_tanpa_token_menandai_perlu_konfigurasi(client):
    _configure(client)
    _backup_and_restore(client)

    telegram = client.get("/api/config").json()["telegram"]
    assert telegram["configured"] is False
    assert telegram["needs_reconfig"] is True


def test_simpan_token_kembali_menghapus_penanda(client):
    _configure(client)
    _backup_and_restore(client)
    assert client.get("/api/config").json()["telegram"]["needs_reconfig"] is True

    saved = client.put(
        "/api/settings/telegram",
        json={
            "enabled": True,
            "jam": "21:00",
            "chat_id": "987654321",
            "bot_token": BOT_TOKEN,
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["needs_reconfig"] is False

    telegram = client.get("/api/config").json()["telegram"]
    assert telegram["configured"] is True
    assert telegram["needs_reconfig"] is False
