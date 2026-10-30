"""T-09: restore memakai mode maintenance dan tidak bertabrakan dengan request."""
from __future__ import annotations

import threading
import time

from database import session as db_session
from services import report_service


def _restore(client, backup):
    return client.post(
        "/api/admin/restore",
        files={"file": ("backup.db", backup.content, "application/x-sqlite3")},
    )


def _backup(client):
    response = client.post("/api/admin/backup")
    assert response.status_code == 200, response.text
    return response


def test_permintaan_baru_ditolak_503_selama_restore(
    client, create_customer, create_unit, make_transaction, monkeypatch
):
    customer = create_customer(nama="Pelanggan Maintenance", nomor_hp="081200000070")
    unit = create_unit(customer["id"], nopol="B 7070 MNT")
    backup = _backup(client)

    started = threading.Event()
    release = threading.Event()
    real_init = db_session.init_db

    def slow_init(bind=None):
        started.set()
        release.wait(timeout=15)
        return real_init(bind)

    monkeypatch.setattr(db_session, "init_db", slow_init)

    hasil = {}

    def jalankan_restore():
        hasil["restore"] = _restore(client, backup)

    thread = threading.Thread(target=jalankan_restore)
    thread.start()
    assert started.wait(timeout=15), "restore tidak pernah mulai"

    try:
        blocked = client.get("/api/stock")
        assert blocked.status_code == 503, blocked.text
        assert "memulihkan" in blocked.json()["detail"].lower()

        transaksi = make_transaction(unit["id"])
        assert transaksi.status_code == 503, transaksi.text

        # Health check tetap terbuka agar aplikasi tahu server hidup.
        assert client.get("/api/health").status_code == 200
    finally:
        release.set()
        thread.join(timeout=15)

    assert hasil["restore"].status_code == 200, hasil["restore"].text
    assert client.get("/api/stock").status_code == 200


def test_restore_menunggu_permintaan_aktif_selesai(
    client, create_customer, monkeypatch
):
    create_customer(nama="Pelanggan Laporan", nomor_hp="081200000071")
    backup = _backup(client)

    di_dalam = threading.Event()
    selesai = threading.Event()
    real_daily = report_service.daily_report

    def slow_daily(*args, **kwargs):
        di_dalam.set()
        assert selesai.wait(timeout=15)
        return real_daily(*args, **kwargs)

    monkeypatch.setattr(report_service, "daily_report", slow_daily)

    dispose_saat = []
    real_dispose = db_session.engine.dispose

    def probe_dispose(*args, **kwargs):
        dispose_saat.append(selesai.is_set())
        return real_dispose(*args, **kwargs)

    monkeypatch.setattr(db_session.engine, "dispose", probe_dispose)

    hasil = {}

    def jalankan_laporan():
        hasil["laporan"] = client.get("/api/reports/daily-cash")

    laporan_thread = threading.Thread(target=jalankan_laporan)
    laporan_thread.start()
    assert di_dalam.wait(timeout=15), "laporan tidak pernah mulai"

    def jalankan_restore():
        hasil["restore"] = _restore(client, backup)

    restore_thread = threading.Thread(target=jalankan_restore)
    restore_thread.start()
    time.sleep(0.4)
    assert restore_thread.is_alive(), "restore tidak menunggu permintaan aktif"

    selesai.set()
    laporan_thread.join(timeout=15)
    restore_thread.join(timeout=15)

    assert hasil["laporan"].status_code == 200, hasil["laporan"].text
    assert hasil["restore"].status_code == 200, hasil["restore"].text
    assert dispose_saat and all(dispose_saat), (
        "database ditukar saat request lain masih berjalan"
    )


def test_restore_gagal_mengembalikan_database_lama_dan_server_tetap_kuat(
    client, create_customer, monkeypatch
):
    create_customer(nama="Data Sebelum Backup", nomor_hp="081200000072")
    backup = _backup(client)
    create_customer(nama="Data Sesudah Backup", nomor_hp="081200000073")

    real_init = db_session.init_db
    percobaan = []

    def gagal_sekali(bind=None):
        percobaan.append(1)
        if len(percobaan) == 1:
            raise RuntimeError("inisialisasi setelah restore gagal")
        return real_init(bind)

    monkeypatch.setattr(db_session, "init_db", gagal_sekali)

    response = _restore(client, backup)

    assert response.status_code == 400, response.text
    assert "dikembalikan" in response.json()["detail"].lower()

    ditemukan = client.get(
        "/api/customers/search", params={"q": "Data"}
    )
    assert ditemukan.status_code == 200, ditemukan.text
    nama = {item["nama"] for item in ditemukan.json()}
    assert nama == {"Data Sebelum Backup", "Data Sesudah Backup"}

    assert client.get("/api/stock").status_code == 200

    # Database tetap bisa ditulis setelah kegagalan restore.
    dibuat = client.post(
        "/api/customers",
        json={"nama": "Pelanggan Setelah Gagal", "nomor_hp": "081200000074"},
    )
    assert dibuat.status_code == 201, dibuat.text


def test_restore_kedua_ditolak_saat_restore_pertama_berjalan(
    client, create_customer, monkeypatch
):
    backup = _backup(client)

    started = threading.Event()
    release = threading.Event()
    real_init = db_session.init_db

    def slow_init(bind=None):
        started.set()
        release.wait(timeout=15)
        return real_init(bind)

    monkeypatch.setattr(db_session, "init_db", slow_init)

    hasil = {}

    def jalankan_restore():
        hasil["pertama"] = _restore(client, backup)

    thread = threading.Thread(target=jalankan_restore)
    thread.start()
    assert started.wait(timeout=15), "restore pertama tidak pernah mulai"

    try:
        kedua = _restore(client, backup)
        assert kedua.status_code == 503, kedua.text
    finally:
        release.set()
        thread.join(timeout=15)

    assert hasil["pertama"].status_code == 200, hasil["pertama"].text
