"""Backup manual "sampai detik ini" dan unduh ulang file backup."""
from __future__ import annotations

import sqlite3

from config import settings
from services import telegram_backup_service

BOT_TOKEN = "123456789:ABCdefghijklmnopqrstuvwxyz"


def configure_telegram(client):
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


def service_count(path) -> int:
    connection = sqlite3.connect(str(path))
    try:
        return connection.execute(
            "SELECT COUNT(*) FROM service_records"
        ).fetchone()[0]
    finally:
        connection.close()


def test_backup_now_tanpa_telegram_tetap_menyimpan_lokal(
    client,
    anon_client,
    create_customer,
    create_unit,
    make_transaction,
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    assert make_transaction(unit["id"]).status_code == 201

    assert anon_client.post("/api/admin/backup-now").status_code == 401

    response = client.post("/api/admin/backup-now")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["local_saved"] is True
    assert body["telegram_ready"] is False
    assert body["telegram_sent"] is False
    assert body["telegram_error"] is None
    assert body["jumlah_nota"] == 1

    path = settings.backup_dir / body["filename"]
    assert path.is_file()
    assert service_count(path) == 1

    backup = client.get("/api/config").json()["backup"]
    assert backup["last_local_at"]
    assert backup["last_local_filename"] == body["filename"]


def test_backup_now_mengirim_file_lengkap_ke_telegram(
    client,
    create_customer,
    create_unit,
    make_transaction,
    monkeypatch,
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    for _ in range(3):
        assert make_transaction(unit["id"]).status_code == 201
    configure_telegram(client)

    captured = {}

    def fake_send(token, chat_id, path, filename, caption):
        captured["content"] = path.read_bytes()
        captured["caption"] = caption

    monkeypatch.setattr(telegram_backup_service, "_send_document", fake_send)

    response = client.post("/api/admin/backup-now")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["telegram_sent"] is True
    assert body["jumlah_nota"] == 3
    assert "3 nota" in captured["caption"]

    path = settings.backup_dir / body["filename"]
    assert path.is_file()
    assert service_count(path) == 3
    assert captured["content"].startswith(b"SQLite format 3\x00")


def test_backup_now_gagal_telegram_tetap_menyimpan_lokal(
    client,
    create_customer,
    create_unit,
    make_transaction,
    monkeypatch,
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    assert make_transaction(unit["id"]).status_code == 201
    configure_telegram(client)

    def failing_send(*_args, **_kwargs):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(telegram_backup_service, "_send_document", failing_send)

    response = client.post("/api/admin/backup-now")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "failed"
    assert body["local_saved"] is True
    assert body["telegram_sent"] is False
    assert "Telegram" in body["telegram_error"]

    path = settings.backup_dir / body["filename"]
    assert path.is_file()
    assert service_count(path) == 1

    backup = client.get("/api/config").json()["backup"]
    assert backup["last_local_at"]
    assert backup["last_status"] == "failed"


def test_unduh_file_backup_tervalidasi(client, anon_client):
    created = client.post("/api/admin/backup")
    assert created.status_code == 200, created.text
    name = next(settings.backup_dir.glob("bengkel_radiator_*.db")).name

    assert anon_client.get(f"/api/admin/backup/file/{name}").status_code == 401

    downloaded = client.get(f"/api/admin/backup/file/{name}")
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content.startswith(b"SQLite format 3\x00")

    assert client.get("/api/admin/backup/file/bukan_backup.db").status_code == 400
    assert (
        client.get("/api/admin/backup/file/bengkel_radiator_99999999_000000.db")
        .status_code
        == 404
    )
