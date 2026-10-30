"""T-06: backup terjadwal (dipicu WorkManager Android) harus idempoten.

WorkManager memanggil satu endpoint yang:
- selalu membuat snapshot lokal lebih dulu,
- memakai ulang file hari yang sama saat dicoba ulang (tanpa duplikat),
- tetap menyimpan file lokal bila pengiriman Telegram gagal,
- mencatat waktu & status backup terakhir untuk peringatan backup basi.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from config import settings
from services import backup_service, settings_service, telegram_backup_service
from services.errors import BusinessValidationError

BOT_TOKEN = "123456789:ABCdefghijklmnopqrstuvwxyz"


def configure_telegram(client, **overrides):
    payload = {
        "enabled": True,
        "jam": "21:00",
        "chat_id": "987654321",
        "bot_token": BOT_TOKEN,
    }
    payload.update(overrides)
    response = client.put("/api/settings/telegram", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def backup_files():
    return set(settings.backup_dir.glob("bengkel_radiator_*.db"))


def set_setting(db_session, key, value):
    settings_service.set_setting(db_session, key, value)
    db_session.commit()


def test_backup_terjadwal_wajib_sesi(anon_client):
    assert anon_client.post("/api/admin/scheduled-backup").status_code == 401


def test_backup_terjadwal_tersimpan_lokal_tanpa_telegram(client, db_session):
    before = backup_files()

    response = client.post("/api/admin/scheduled-backup")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "ok"
    assert body["local_saved"] is True
    assert body["telegram_enabled"] is False
    assert body["telegram_sent"] is False
    assert body["telegram_error"] is None
    assert body["size_bytes"] > 0

    created = backup_files() - before
    assert len(created) == 1
    path = created.pop()
    assert body["filename"] == path.name
    assert path.read_bytes().startswith(b"SQLite format 3\x00")

    db_session.expire_all()
    assert settings_service.get_setting(db_session, "backup.last_status") == "ok"
    assert settings_service.get_setting(
        db_session, "backup.last_local_filename"
    ) == path.name
    assert settings_service.get_setting(db_session, "backup.last_local_at")

    backup = client.get("/api/config").json()["backup"]
    assert backup["last_status"] == "ok"
    assert backup["last_local_filename"] == path.name
    assert backup["stale"] is False


def test_backup_terjadwal_diulang_tidak_menduplikasi_berkas(client, db_session):
    before = backup_files()

    first = client.post("/api/admin/scheduled-backup")
    assert first.status_code == 200, first.text
    second = client.post("/api/admin/scheduled-backup")
    assert second.status_code == 200, second.text

    assert first.json()["filename"] == second.json()["filename"]
    created = backup_files() - before
    assert len(created) == 1


def test_telegram_gagal_tetap_menyimpan_backup_lokal(
    client, db_session, monkeypatch
):
    configure_telegram(client)

    def failing_send(*_args, **_kwargs):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(telegram_backup_service, "_send_document", failing_send)
    before = backup_files()

    response = client.post("/api/admin/scheduled-backup")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "failed"
    assert body["local_saved"] is True
    assert body["telegram_enabled"] is True
    assert body["telegram_sent"] is False
    assert "connection refused" in body["telegram_error"]

    created = backup_files() - before
    assert len(created) == 1
    path = created.pop()
    assert body["filename"] == path.name
    assert path.exists()

    db_session.expire_all()
    assert settings_service.get_setting(db_session, "backup.last_status") == "failed"
    assert settings_service.get_setting(
        db_session, "backup.last_local_filename"
    ) == path.name
    backup = client.get("/api/config").json()["backup"]
    assert backup["last_status"] == "failed"
    assert "connection refused" in backup["last_error"]

    # Percobaan ulang memakai file yang sama, bukan membuat duplikat.
    retry = client.post("/api/admin/scheduled-backup")
    assert retry.status_code == 200, retry.text
    assert retry.json()["filename"] == path.name
    assert backup_files() - before == {path}


def test_penjadwal_lokal_berjalan_tanpa_telegram(client, db_session):
    telegram = client.get("/api/config").json()["telegram"]
    assert telegram["enabled"] is False

    assert (
        telegram_backup_service.run_scheduled_backup(
            datetime(2026, 10, 30, 20, 0)
        )
        is None
    )

    before = backup_files()
    result = telegram_backup_service.run_scheduled_backup(
        datetime(2026, 10, 30, 21, 0)
    )
    assert result is not None
    assert result["status"] == "ok"
    assert result["local_saved"] is True
    assert result["telegram_enabled"] is False
    assert result["telegram_sent"] is False

    created = backup_files() - before
    assert len(created) == 1
    path = created.pop()
    assert path == settings.backup_dir / result["filename"]

    connection = sqlite3.connect(str(path))
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT COUNT(*) FROM stock_items").fetchone()[0] > 0
    finally:
        connection.close()

    db_session.expire_all()
    assert settings_service.get_setting(db_session, "backup.last_status") == "ok"
    assert (
        settings_service.get_setting(db_session, "backup.last_local_filename")
        == path.name
    )

    # Jadwal hari yang sama tidak membuat snapshot kedua.
    assert (
        telegram_backup_service.run_scheduled_backup(
            datetime(2026, 10, 30, 22, 0)
        )
        is None
    )
    assert backup_files() - before == {path}


def test_telegram_sukses_mencatat_status_dan_tidak_menduplikasi(
    client, db_session, monkeypatch
):
    configure_telegram(client)
    sent = []

    def fake_send(token, chat_id, path, filename, caption):
        sent.append((token, chat_id, filename, caption, path.read_bytes()))

    monkeypatch.setattr(telegram_backup_service, "_send_document", fake_send)
    before = backup_files()

    response = client.post("/api/admin/scheduled-backup")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "ok"
    assert body["local_saved"] is True
    assert body["telegram_enabled"] is True
    assert body["telegram_sent"] is True
    assert body["telegram_error"] is None
    assert len(sent) == 1
    assert sent[0][4].startswith(b"SQLite format 3\x00")

    created = backup_files() - before
    assert len(created) == 1
    path = created.pop()
    assert body["filename"] == path.name
    assert body["size_bytes"] > 0
    assert path.exists()

    db_session.expire_all()
    assert settings_service.get_setting(db_session, "backup.last_status") == "ok"
    assert settings_service.get_setting(db_session, "telegram.last_sent_at")
    assert settings_service.get_setting(db_session, "telegram.last_error") == ""
    assert settings_service.get_setting(db_session, "backup.last_local_at")
    assert (
        settings_service.get_setting(db_session, "backup.last_local_filename")
        == path.name
    )

    # Sudah terkirim hari ini: pemicu berikutnya tidak membuat file baru dan
    # snapshot lokal tetap tersedia.
    again = client.post("/api/admin/scheduled-backup")
    assert again.status_code == 200, again.text
    assert again.json()["status"] == "ok"
    assert again.json()["telegram_sent"] is True
    assert len(sent) == 1
    assert backup_files() - before == {path}


def test_ruang_penyimpanan_penuh_gagal_dengan_aman(client, db_session, monkeypatch):
    def no_space():
        raise BusinessValidationError(
            "Ruang penyimpanan tidak cukup untuk membuat backup."
        )

    monkeypatch.setattr(backup_service, "create_backup", no_space)
    before = backup_files()

    response = client.post("/api/admin/scheduled-backup")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "failed"
    assert body["local_saved"] is False
    assert body["filename"] is None
    assert "Ruang penyimpanan" in body["message"]
    assert backup_files() == before

    db_session.expire_all()
    assert settings_service.get_setting(db_session, "backup.last_status") == "failed"
    assert "Ruang penyimpanan" in settings_service.get_setting(
        db_session, "backup.last_error"
    )


def test_backup_tidak_berjalan_bersamaan(client, db_session):
    before = backup_files()
    assert telegram_backup_service.BACKUP_LOCK.acquire(blocking=False)
    try:
        response = client.post("/api/admin/scheduled-backup")
    finally:
        telegram_backup_service.BACKUP_LOCK.release()

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "busy"
    assert backup_files() == before


def test_config_memberi_peringatan_backup_basi(client, db_session):
    backup = client.get("/api/config").json()["backup"]
    assert backup["last_local_at"] is None
    assert backup["stale"] is True
    assert backup["stale_days"] == 2

    old = (datetime.now() - timedelta(days=3)).isoformat(timespec="seconds")
    set_setting(db_session, "backup.last_local_at", old)
    set_setting(db_session, "backup.last_status", "ok")

    backup = client.get("/api/config").json()["backup"]
    assert backup["last_local_at"] == old
    assert backup["stale"] is True

    response = client.post("/api/admin/scheduled-backup")
    assert response.status_code == 200, response.text

    backup = client.get("/api/config").json()["backup"]
    assert backup["stale"] is False
    assert datetime.fromisoformat(backup["last_local_at"]).date() == datetime.now().date()
