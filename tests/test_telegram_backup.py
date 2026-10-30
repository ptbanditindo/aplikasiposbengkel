"""Backup otomatis Telegram: konfigurasi UI, kirim file lengkap, penjadwalan."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta

from sqlalchemy import select

from database.models import AppSetting, ServiceRecord
from services import settings_service, telegram_backup_service

ADMIN_HEADERS = {"X-Admin-Token": "test-admin-token"}
BOT_TOKEN = "123456789:ABCdefghijklmnopqrstuvwxyz"


def telegram_payload(**overrides):
    data = {
        "enabled": True,
        "jam": "21:00",
        "chat_id": "987654321",
        "bot_token": BOT_TOKEN,
    }
    data.update(overrides)
    return data


def configure_telegram(client, **overrides):
    response = client.put(
        "/api/settings/telegram",
        json=telegram_payload(**overrides),
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_config_telegram_default_nonaktif(client):
    telegram = client.get("/api/config").json()["telegram"]
    assert telegram == {
        "enabled": False,
        "jam": "21:00",
        "chat_id": "",
        "configured": False,
        "needs_reconfig": False,
        "last_sent_at": None,
        "last_error": None,
    }


def test_simpan_pengaturan_telegram_wajib_token(client, db_session):
    assert (
        client.put("/api/settings/telegram", json=telegram_payload()).status_code
        == 401
    )

    saved = configure_telegram(client, jam="22:30", enabled=True)
    assert saved["enabled"] is True
    assert saved["jam"] == "22:30"
    assert saved["chat_id"] == "987654321"
    assert saved["configured"] is True
    assert "bot_token" not in saved

    config = client.get("/api/config")
    assert config.json()["telegram"]["configured"] is True
    assert BOT_TOKEN not in config.text

    stored = db_session.get(AppSetting, "telegram.bot_token")
    assert stored is not None and stored.value == BOT_TOKEN


def test_token_dan_chat_kosong_mempertahankan_nilai_tersimpan(client):
    configure_telegram(client)

    saved = configure_telegram(
        client, enabled=False, jam="20:00", chat_id="", bot_token=""
    )
    assert saved["enabled"] is False
    assert saved["jam"] == "20:00"
    assert saved["chat_id"] == "987654321"
    assert saved["configured"] is True


def test_jam_token_dan_chat_tidak_valid_ditolak(client):
    invalid_time = client.put(
        "/api/settings/telegram",
        json=telegram_payload(jam="25:00"),
        headers=ADMIN_HEADERS,
    )
    assert invalid_time.status_code == 422

    invalid_token = client.put(
        "/api/settings/telegram",
        json=telegram_payload(bot_token="bukan-token"),
        headers=ADMIN_HEADERS,
    )
    assert invalid_token.status_code == 400
    assert "token" in invalid_token.json()["detail"].lower()

    invalid_chat = client.put(
        "/api/settings/telegram",
        json=telegram_payload(chat_id="@x"),
        headers=ADMIN_HEADERS,
    )
    assert invalid_chat.status_code == 400
    assert "chat id" in invalid_chat.json()["detail"].lower()


def test_kirim_manual_tanpa_konfigurasi_ditolak(client):
    assert client.post("/api/admin/telegram-backup").status_code == 401

    response = client.post("/api/admin/telegram-backup", headers=ADMIN_HEADERS)
    assert response.status_code == 400
    assert "belum diatur" in response.json()["detail"]


def test_kirim_manual_mengirim_database_lengkap(
    client,
    create_customer,
    create_unit,
    make_transaction,
    db_session,
    monkeypatch,
    tmp_path,
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    created = make_transaction(unit["id"])
    assert created.status_code == 201, created.text

    record = db_session.scalars(select(ServiceRecord)).first()
    assert record is not None
    record.waktu_service = datetime(2026, 9, 1, 10, 0)
    db_session.commit()

    configure_telegram(client)

    captured = {}

    def fake_send(token, chat_id, path, filename, caption):
        captured.update(
            token=token,
            chat_id=chat_id,
            filename=filename,
            caption=caption,
            content=path.read_bytes(),
        )

    monkeypatch.setattr(telegram_backup_service, "_send_document", fake_send)

    response = client.post("/api/admin/telegram-backup", headers=ADMIN_HEADERS)
    assert response.status_code == 200, response.text
    body = response.json()

    expected_name = f"bengkel_radiator_20260901-{date.today():%Y%m%d}.db"
    assert body["filename"] == expected_name
    assert body["start"] == "2026-09-01"
    assert body["jumlah_nota"] == 1

    assert captured["token"] == BOT_TOKEN
    assert captured["chat_id"] == "987654321"
    assert captured["filename"] == expected_name
    assert "Data 01/09/2026" in captured["caption"]
    assert "1 nota" in captured["caption"]
    assert captured["content"].startswith(b"SQLite format 3\x00")

    # File yang dikirim adalah database lengkap, bukan hanya data baru.
    backup_file = tmp_path / "received.db"
    backup_file.write_bytes(captured["content"])
    connection = sqlite3.connect(str(backup_file))
    try:
        assert connection.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM service_records").fetchone()[0] == 1
        stored_token = connection.execute(
            "SELECT value FROM app_settings WHERE key = 'telegram.bot_token'"
        ).fetchone()
        assert stored_token == ("",)
    finally:
        connection.close()

    assert BOT_TOKEN not in response.text
    telegram = client.get("/api/config").json()["telegram"]
    assert telegram["last_sent_at"]
    assert telegram["last_error"] is None
    pending = db_session.get(AppSetting, "telegram.pending_since")
    assert pending is None or pending.value == ""


def test_kegagalan_kirim_dicatat_di_status(client, monkeypatch, db_session):
    configure_telegram(client)

    def failing_send(*_args, **_kwargs):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(telegram_backup_service, "_send_document", failing_send)

    response = client.post("/api/admin/telegram-backup", headers=ADMIN_HEADERS)
    assert response.status_code == 400
    assert "Tidak dapat menghubungi Telegram" in response.json()["detail"]

    telegram = client.get("/api/config").json()["telegram"]
    assert telegram["last_sent_at"] is None
    assert "connection refused" in telegram["last_error"]

    pending = db_session.get(AppSetting, "telegram.pending_since")
    assert pending is not None and pending.value


def test_should_send_mengikuti_jadwal_dan_retry():
    base = {
        "enabled": True,
        "jam": "21:00",
        "bot_token": BOT_TOKEN,
        "chat_id": "987654321",
        "last_sent_at": "",
        "last_attempt_at": "",
        "pending_since": "",
    }

    assert not telegram_backup_service.should_send(
        datetime(2026, 10, 30, 20, 59), base
    )
    assert telegram_backup_service.should_send(
        datetime(2026, 10, 30, 21, 0), base
    )

    sent_today = dict(base, last_sent_at="2026-10-30T21:00:00")
    assert not telegram_backup_service.should_send(
        datetime(2026, 10, 30, 21, 5), sent_today
    )

    sent_yesterday = dict(base, last_sent_at="2026-10-29T21:00:00")
    assert not telegram_backup_service.should_send(
        datetime(2026, 10, 30, 8, 0), sent_yesterday
    )
    assert telegram_backup_service.should_send(
        datetime(2026, 10, 30, 21, 0), sent_yesterday
    )

    recent_failure = dict(base, last_attempt_at="2026-10-30T21:00:00")
    assert not telegram_backup_service.should_send(
        datetime(2026, 10, 30, 21, 5), recent_failure
    )
    assert telegram_backup_service.should_send(
        datetime(2026, 10, 30, 21, 15), recent_failure
    )

    assert not telegram_backup_service.should_send(
        datetime(2026, 10, 30, 21, 5), dict(base, enabled=False)
    )
    assert not telegram_backup_service.should_send(
        datetime(2026, 10, 30, 21, 5), dict(base, bot_token="")
    )


def test_backup_terlewat_langsung_dikirim_saat_online_kembali():
    base = {
        "enabled": True,
        "jam": "21:00",
        "bot_token": BOT_TOKEN,
        "chat_id": "987654321",
        "last_sent_at": "",
        "last_attempt_at": "",
        "pending_since": "",
    }

    # Sukses terakhir tanggal 28, sekarang tanggal 30 pagi: jadwal 29 terlewat.
    missed = dict(base, last_sent_at="2026-10-28T21:00:00")
    assert telegram_backup_service.should_send(datetime(2026, 10, 30, 8, 0), missed)

    # Gagal kirim kemarin (belum pernah sukses) juga dianggap terlewat.
    failed_yesterday = dict(
        base,
        last_attempt_at="2026-10-29T21:00:00",
        pending_since="2026-10-29T21:00:00",
    )
    assert telegram_backup_service.should_send(
        datetime(2026, 10, 30, 7, 0), failed_yesterday
    )

    # Retry tetap dibatasi 10 menit agar tidak membanjiri Telegram.
    assert not telegram_backup_service.should_send(
        datetime(2026, 10, 30, 7, 5),
        dict(failed_yesterday, last_attempt_at="2026-10-30T07:00:00"),
    )
    assert telegram_backup_service.should_send(
        datetime(2026, 10, 30, 7, 11),
        dict(failed_yesterday, last_attempt_at="2026-10-30T07:00:00"),
    )

    # Sudah berhasil dikirim pagi ini: tidak dobel, jadwal 21:00 tetap jalan.
    caught_up = dict(base, last_sent_at="2026-10-30T08:00:00")
    assert not telegram_backup_service.should_send(
        datetime(2026, 10, 30, 8, 5), caught_up
    )
    assert telegram_backup_service.should_send(
        datetime(2026, 10, 30, 21, 0), caught_up
    )


def test_penjadwal_mengirim_satu_kali_per_hari(client, monkeypatch):
    configure_telegram(client, jam="00:00")

    calls = []

    def fake_send(token, chat_id, path, filename, caption):
        calls.append(filename)

    monkeypatch.setattr(telegram_backup_service, "_send_document", fake_send)

    moment = datetime(2026, 10, 30, 9, 0)
    first = telegram_backup_service.run_scheduled_backup(moment)
    assert first is not None
    assert len(calls) == 1

    second = telegram_backup_service.run_scheduled_backup(moment + timedelta(hours=1))
    assert second is None
    assert len(calls) == 1


def test_penjadwal_mengirim_backup_terlewat_sebelum_jam(
    client, monkeypatch, db_session
):
    configure_telegram(client, jam="21:00")
    settings_service.set_setting(
        db_session, "telegram.pending_since", "2026-10-29T21:00:00"
    )
    settings_service.set_setting(
        db_session, "telegram.last_attempt_at", "2026-10-29T21:00:00"
    )
    db_session.commit()

    calls = []

    def fake_send(token, chat_id, path, filename, caption):
        calls.append(filename)

    monkeypatch.setattr(telegram_backup_service, "_send_document", fake_send)

    # Jam 08:00, jauh sebelum jadwal 21:00, tetapi jadwal kemarin terlewat.
    result = telegram_backup_service.run_scheduled_backup(
        datetime(2026, 10, 30, 8, 0)
    )
    assert result is not None
    assert len(calls) == 1
    assert client.get("/api/config").json()["telegram"]["last_sent_at"]

    db_session.expire_all()
    pending = db_session.get(AppSetting, "telegram.pending_since")
    assert pending is None or pending.value == ""
