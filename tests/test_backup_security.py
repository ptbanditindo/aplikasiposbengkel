"""S-07 / ARC-14: rahasia tidak boleh tersisa di backup maupun salinan pra-restore."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from config import settings
from database.session import engine
from services import telegram_backup_service

BOT_TOKEN = "123456789:ABCdefghijklmnopqrstuvwxyz"
SENSITIVE_KEYS = (
    "auth.pin_hash",
    "auth.pin_salt",
    "auth.pin_epoch",
    "auth.session_secret",
    "telegram.bot_token",
    "telegram.chat_id",
)


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


def _settings_values(path):
    connection = sqlite3.connect(str(path))
    try:
        rows = connection.execute("SELECT key, value FROM app_settings").fetchall()
        return {key: value for key, value in rows}
    finally:
        connection.close()


def _assert_redacted(path):
    path = Path(path)
    values = _settings_values(path)
    for key in SENSITIVE_KEYS:
        assert values.get(key, "") == "", f"{key} masih berisi rahasia"
    assert BOT_TOKEN.encode() not in path.read_bytes()


def _latest_backup():
    return sorted(settings.backup_dir.glob("bengkel_radiator_*.db"))[-1]


def test_backup_meredaksi_rahasia_dan_mempertahankan_data_bisnis(client):
    _configure_telegram(client)
    response = client.put(
        "/api/settings/bengkel",
        json={"nama": "BENGKEL BACKUP AMAN", "tagline": "Tetap Ada"},
    )
    assert response.status_code == 200, response.text
    customer = client.post(
        "/api/customers",
        json={"nama": "Pelanggan Backup", "nomor_hp": "08123456789"},
    )
    assert customer.status_code == 201, customer.text

    pin_hash = _settings_values(engine.url.database)["auth.pin_hash"]
    assert pin_hash

    backup = client.post("/api/admin/backup")
    assert backup.status_code == 200, backup.text
    path = _latest_backup()

    _assert_redacted(path)
    values = _settings_values(path)
    assert values["bengkel.nama"] == "BENGKEL BACKUP AMAN"
    assert values["bengkel.tagline"] == "Tetap Ada"

    connection = sqlite3.connect(str(path))
    try:
        assert connection.execute("SELECT COUNT(*) FROM customers").fetchone()[0] >= 1
        assert connection.execute("SELECT COUNT(*) FROM stock_items").fetchone()[0] > 0
    finally:
        connection.close()


def test_restore_meredaksi_backup_lama_dan_memaksa_pin_baru(
    client, anon_client
):
    backup = client.post("/api/admin/backup")
    assert backup.status_code == 200, backup.text

    # Simulasikan backup lama yang belum pernah diredaksi.
    path = _latest_backup()
    connection = sqlite3.connect(str(path))
    try:
        connection.execute(
            "UPDATE app_settings SET value = ? WHERE key = 'auth.pin_hash'",
            ("legacy-hash",),
        )
        connection.execute(
            "UPDATE app_settings SET value = ? WHERE key = 'auth.pin_salt'",
            ("00" * 16,),
        )
        connection.execute(
            "UPDATE app_settings SET value = ? WHERE key = 'auth.session_secret'",
            ("11" * 32,),
        )
        connection.execute(
            "UPDATE app_settings SET value = ? WHERE key = 'telegram.chat_id'",
            ("legacy-chat",),
        )
        connection.commit()
    finally:
        connection.close()

    restore = client.post(
        "/api/admin/restore",
        files={"file": ("backup-lama.db", path.read_bytes(), "application/x-sqlite3")},
    )
    assert restore.status_code == 200, restore.text

    _assert_redacted(engine.url.database)

    status = anon_client.get("/api/auth/status")
    assert status.status_code == 200, status.text
    assert status.json()["pin_configured"] is False

    old_login = anon_client.post("/api/auth/login", json={"pin": "2468"})
    assert old_login.status_code != 200

    setup = anon_client.post("/api/auth/setup", json={"pin": "1357"})
    assert setup.status_code == 201, setup.text
    new_login = anon_client.post("/api/auth/login", json={"pin": "1357"})
    assert new_login.status_code == 200, new_login.text


def test_backup_restore_web_tidak_memakai_pin_lama(client, anon_client):
    backup = client.post("/api/admin/backup")
    assert backup.status_code == 200, backup.text

    restore = client.post(
        "/api/admin/restore",
        files={"file": ("backup.db", backup.content, "application/x-sqlite3")},
    )
    assert restore.status_code == 200, restore.text

    old_login = anon_client.post("/api/auth/login", json={"pin": "2468"})
    assert old_login.status_code != 200
    assert anon_client.get("/api/auth/status").json()["pin_configured"] is False


def test_backup_terjadwal_lokal_meredaksi_rahasia(client):
    before = set(settings.backup_dir.glob("bengkel_radiator_*.db"))

    response = client.post("/api/admin/scheduled-backup")
    assert response.status_code == 200, response.text
    assert response.json()["local_saved"] is True

    created = set(settings.backup_dir.glob("bengkel_radiator_*.db")) - before
    assert len(created) == 1
    _assert_redacted(created.pop())


def test_backup_terkirim_telegram_meredaksi_rahasia(client, monkeypatch, tmp_path):
    _configure_telegram(client)
    captured = {}

    def _capture(token, chat_id, path, filename, caption):
        captured["bytes"] = path.read_bytes()

    monkeypatch.setattr(telegram_backup_service, "_send_document", _capture)

    response = client.post("/api/admin/scheduled-backup")
    assert response.status_code == 200, response.text
    assert response.json()["telegram_sent"] is True

    sent_path = tmp_path / "terkirim.db"
    sent_path.write_bytes(captured["bytes"])
    _assert_redacted(sent_path)
