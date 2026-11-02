"""Backup otomatis dengan format database, Excel, atau CSV."""
from __future__ import annotations

import csv
import io
import os
import zipfile
from datetime import datetime

import pytest
from openpyxl import load_workbook

from config import settings
from services import backup_service, settings_service, telegram_backup_service

BOT_TOKEN = "123456789:ABCdefghijklmnopqrstuvwxyz"


@pytest.fixture(autouse=True)
def clean_backup_dir():
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    for path in settings.backup_dir.glob("bengkel_radiator_*"):
        path.unlink()
    yield
    for path in settings.backup_dir.glob("bengkel_radiator_*"):
        path.unlink()


def configure_telegram(client, enabled=True, **overrides):
    payload = {
        "enabled": enabled,
        "jam": "21:00",
        "chat_id": "987654321",
        "bot_token": BOT_TOKEN,
    }
    payload.update(overrides)
    response = client.put("/api/settings/telegram", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def backup_files():
    return set(settings.backup_dir.glob("bengkel_radiator_*"))


def sheet_rows(workbook, name):
    rows = workbook[name].iter_rows(values_only=True)
    header = list(next(rows))
    return [dict(zip(header, row)) for row in rows]


def test_default_backup_tetap_database(client):
    assert client.get("/api/config").json()["backup"]["format"] == "db"

    before = backup_files()
    response = client.post("/api/admin/scheduled-backup")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "ok"
    assert body["filename"].endswith(".db")
    path = settings.backup_dir / body["filename"]
    assert path.read_bytes().startswith(b"SQLite format 3\x00")
    assert backup_files() - before == {path}


def test_format_tersimpan_dan_format_tidak_dikenal_ditolak(client):
    configure_telegram(client, enabled=False, format="xlsx")
    config = client.get("/api/config").json()
    assert config["backup"]["format"] == "xlsx"

    invalid = client.put(
        "/api/settings/telegram",
        json={
            "enabled": True,
            "jam": "21:00",
            "chat_id": "987654321",
            "bot_token": BOT_TOKEN,
            "format": "pdf",
        },
    )
    assert invalid.status_code == 400
    assert "db, xlsx, atau csv" in invalid.json()["detail"]
    assert client.get("/api/config").json()["backup"]["format"] == "xlsx"


def test_backup_excel_berisi_data_dan_redaksi_rahasia(
    client, db_session, create_customer
):
    create_customer(nama="Siti Ekspor Excel")
    configure_telegram(client, enabled=False, format="xlsx")
    db_session.expire_all()
    pin_hash = settings_service.get_setting(db_session, "auth.pin_hash")
    assert pin_hash

    response = client.post("/api/admin/scheduled-backup")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["filename"].endswith(".xlsx")

    path = settings.backup_dir / body["filename"]
    assert path.read_bytes().startswith(b"PK")
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        assert "Info" in workbook.sheetnames
        assert "customers" in workbook.sheetnames
        assert "app_settings" in workbook.sheetnames

        info = sheet_rows(workbook, "Info")
        pemulihan = next(row for row in info if row["Keterangan"] == "Pemulihan")
        assert "Bukan berkas pemulihan" in pemulihan["Nilai"]

        customers = sheet_rows(workbook, "customers")
        assert any(row["nama"] == "Siti Ekspor Excel" for row in customers)

        app_settings = {
            row["key"]: row["value"] for row in sheet_rows(workbook, "app_settings")
        }
        assert not app_settings.get("auth.pin_hash")
        assert not app_settings.get("telegram.bot_token")
        assert not app_settings.get("telegram.chat_id")
        assert pin_hash not in str(app_settings)
    finally:
        workbook.close()


def test_backup_csv_zip_berisi_satu_csv_per_tabel(
    client, db_session, create_customer
):
    create_customer(nama="Budi Ekspor CSV")
    configure_telegram(client, enabled=False, format="csv")
    db_session.expire_all()
    pin_hash = settings_service.get_setting(db_session, "auth.pin_hash")

    response = client.post("/api/admin/scheduled-backup")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["filename"].endswith("_csv.zip")

    path = settings.backup_dir / body["filename"]
    assert path.read_bytes().startswith(b"PK")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        assert "Info.txt" in names
        assert "customers.csv" in names
        assert "app_settings.csv" in names

        info = archive.read("Info.txt").decode("utf-8")
        assert "Bukan berkas pemulihan" in info

        customers = archive.read("customers.csv").decode("utf-8-sig")
        assert "Budi Ekspor CSV" in customers

        app_settings_text = archive.read("app_settings.csv").decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(app_settings_text)))
        values = {row["key"]: row["value"] for row in rows}
        assert values["auth.pin_hash"] == ""
        assert values["telegram.bot_token"] == ""
        assert pin_hash not in app_settings_text


def test_telegram_mengirim_format_pilihan(client, monkeypatch):
    configure_telegram(client, format="xlsx")
    sent = []

    def fake_send(token, chat_id, path, filename, caption):
        sent.append((path, filename, caption))

    monkeypatch.setattr(telegram_backup_service, "_send_document", fake_send)

    response = client.post("/api/admin/scheduled-backup")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "ok"
    assert body["telegram_sent"] is True
    assert body["filename"].endswith(".xlsx")
    assert len(sent) == 1
    path, filename, caption = sent[0]
    assert path == settings.backup_dir / body["filename"]
    assert filename.endswith(".xlsx")
    assert "bukan berkas pemulihan" in caption


def test_ganti_format_membuat_snapshot_format_baru(client):
    first = client.post("/api/admin/scheduled-backup")
    assert first.status_code == 200, first.text
    assert first.json()["filename"].endswith(".db")

    configure_telegram(client, enabled=False, format="xlsx")
    second = client.post("/api/admin/scheduled-backup")
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["filename"].endswith(".xlsx")
    assert body["filename"] != first.json()["filename"]
    assert (settings.backup_dir / body["filename"]).exists()


def test_unduh_berkas_mengikuti_mime_format(client):
    configure_telegram(client, enabled=False, format="xlsx")
    xlsx = client.post("/api/admin/scheduled-backup").json()
    download = client.get(f"/api/admin/backup/file/{xlsx['filename']}")
    assert download.status_code == 200
    assert download.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert download.content.startswith(b"PK")

    configure_telegram(client, enabled=False, format="csv")
    csv_zip = client.post("/api/admin/scheduled-backup").json()
    download = client.get(f"/api/admin/backup/file/{csv_zip['filename']}")
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("application/zip")
    assert download.content.startswith(b"PK")


def test_backup_manual_bisa_memilih_format(client):
    default = client.post("/api/admin/backup")
    assert default.status_code == 200
    assert default.content.startswith(b"SQLite format 3\x00")
    assert default.headers["content-type"].startswith("application/x-sqlite3")

    xlsx = client.post("/api/admin/backup?format=xlsx")
    assert xlsx.status_code == 200
    assert xlsx.content.startswith(b"PK")
    assert xlsx.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert ".xlsx" in xlsx.headers["content-disposition"]

    csv_zip = client.post("/api/admin/backup?format=csv")
    assert csv_zip.status_code == 200
    assert csv_zip.content.startswith(b"PK")
    assert csv_zip.headers["content-type"].startswith("application/zip")
    assert "_csv.zip" in csv_zip.headers["content-disposition"]

    invalid = client.post("/api/admin/backup?format=pdf")
    assert invalid.status_code == 400
    assert "db, xlsx, atau csv" in invalid.json()["detail"]


def test_retensi_menghitung_semua_format(client):
    for index in range(settings.backup_keep + 2):
        name = (
            "bengkel_radiator_20260101_0000"
            + str(index)
            + (".xlsx" if index % 2 else "_csv.zip")
        )
        (settings.backup_dir / name).write_bytes(b"backup")
        # Pastikan urutan mtime dapat diprediksi.
        timestamp = datetime(2026, 1, 1, 0, 0, index).timestamp()
        os.utime(settings.backup_dir / name, (timestamp, timestamp))

    backup_service.prune_backups()
    remaining = list(settings.backup_dir.glob("bengkel_radiator_*"))
    assert len(remaining) == settings.backup_keep
