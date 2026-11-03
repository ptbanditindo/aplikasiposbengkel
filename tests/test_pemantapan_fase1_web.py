"""Pemantapan formal Fase 1 web: multi-toko, isolasi, gating, dan kuota.

Skenario merujuk K-03, K-04, K-05, dan K-09 di RENCANA_MULTI_TOKO_PREMIUM.md.
Batas web (K-01): tidak menguji akun, lisensi, relay, atau perangkat.
"""
from __future__ import annotations

import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from database import session as db_session
from database import store_registry
from database.models import AppSetting
from services import followup_quota_service, store_service


def _stores(client):
    response = client.get("/api/stores")
    assert response.status_code == 200, response.text
    return response.json()


def _create_store(client, nama, alamat="Jl. Cabang"):
    response = client.post(
        "/api/stores", json={"nama": nama, "alamat": alamat}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _activate(client, store_id):
    response = client.post(f"/api/stores/{store_id}/activate")
    assert response.status_code == 200, response.text
    return response.json()


def _names(client, path):
    response = client.get(path)
    assert response.status_code == 200, response.text
    return sorted(row["nama"] for row in response.json())


def _daily_count(client):
    response = client.get(
        "/api/reports/daily-cash",
        params={"tanggal": date.today().isoformat()},
    )
    assert response.status_code == 200, response.text
    return len(response.json()["transaksi"])


def test_isolasi_tiga_toko_semua_data(client, create_customer, create_unit, make_transaction):
    primary = _stores(client)["aktif"]
    utama = create_customer(nama="Pelanggan Utama", nomor_hp="0811-0000-001")
    unit_utama = create_unit(utama["id"], nopol="B 1001 UTA")
    assert make_transaction(unit_utama["id"]).status_code == 201
    assert client.post(
        "/api/employees", json={"nama": "Karyawan Utama", "peran": "KASIR"}
    ).status_code == 201
    assert client.post(
        "/api/suppliers", json={"nama": "Supplier Utama"}
    ).status_code == 201
    assert client.post(
        "/api/stock", json={"nama": "Part Utama", "jumlah": 3}
    ).status_code == 201

    cabang_b = _create_store(client, "Cabang B", "Jl. B No. 2")
    _activate(client, cabang_b["store_id"])
    pelanggan_b = create_customer(nama="Pelanggan B", nomor_hp="0811-0000-002")
    unit_b = create_unit(pelanggan_b["id"], nopol="B 1002 BCD")
    assert make_transaction(unit_b["id"]).status_code == 201
    assert client.post(
        "/api/employees", json={"nama": "Karyawan B", "peran": "KASIR"}
    ).status_code == 201
    assert client.post(
        "/api/suppliers", json={"nama": "Supplier B"}
    ).status_code == 201
    assert client.post(
        "/api/stock", json={"nama": "Part B", "jumlah": 9}
    ).status_code == 201

    cabang_c = _create_store(client, "Cabang C", "Jl. C No. 3")
    _activate(client, cabang_c["store_id"])
    create_customer(nama="Pelanggan C", nomor_hp="0811-0000-003")
    assert client.get("/api/service-records").json() == []
    assert _names(client, "/api/employees") == []
    assert _names(client, "/api/suppliers") == []
    part_c = [row["nama"] for row in client.get("/api/stock").json()]
    assert "Part Utama" not in part_c
    assert "Part B" not in part_c

    for store_id, pelanggan, karyawan, supplier, transaksi in (
        (primary, "Pelanggan Utama", "Karyawan Utama", "Supplier Utama", 1),
        (cabang_b["store_id"], "Pelanggan B", "Karyawan B", "Supplier B", 1),
        (cabang_c["store_id"], "Pelanggan C", None, None, 0),
    ):
        _activate(client, store_id)
        assert _names(client, "/api/customers") == [pelanggan]
        assert _daily_count(client) == transaksi
        assert _names(client, "/api/employees") == ([karyawan] if karyawan else [])
        assert _names(client, "/api/suppliers") == ([supplier] if supplier else [])


def test_registry_rusak_memulihkan_toko_utama_tanpa_mencampur(client, create_customer):
    primary = store_registry.PRIMARY_STORE_ID
    create_customer(nama="Pelanggan Utama")
    cabang = _create_store(client, "Cabang Rusak")
    _activate(client, cabang["store_id"])
    create_customer(nama="Pelanggan Cabang")

    store_registry.registry_path().write_text("{rusak", encoding="utf-8")
    store_registry._cached = None
    store_registry._cached_mtime_ns = -1

    data = _stores(client)
    assert data["aktif"] == primary
    assert [row["store_id"] for row in data["toko"]] == [primary]
    assert _names(client, "/api/customers") == ["Pelanggan Utama"]
    assert list(store_registry.stores_dir().glob("registry.rusak-*.json")), (
        "Registry rusak harus disisihkan agar bisa diperiksa."
    )


def test_toko_hilang_dilaporkan_dan_tidak_bisa_diaktifkan(client, create_customer):
    primary = store_registry.PRIMARY_STORE_ID
    cabang = _create_store(client, "Cabang Hilang")
    _activate(client, cabang["store_id"])
    create_customer(nama="Pelanggan Cabang")

    db_session.dispose_store_engines()
    entry = store_registry.get_store(cabang["store_id"])
    assert entry is not None
    store_registry.resolve_database_path(entry).unlink()

    data = _stores(client)
    row = next(item for item in data["toko"] if item["store_id"] == cabang["store_id"])
    assert row["tersedia"] is False
    assert data["aktif"] == primary, "Toko aktif yang hilang kembali ke toko utama."

    activate = client.post(f"/api/stores/{cabang['store_id']}/activate")
    assert activate.status_code == 409, activate.text
    assert "tidak tersedia" in activate.json()["detail"].lower()
    assert _stores(client)["aktif"] == primary


def test_startup_mempertahankan_identitas_toko_aktif(client):
    cabang = _create_store(client, "Cabang Stabil", "Jl. Stabil No. 7")
    _activate(client, cabang["store_id"])
    before = store_registry.get_store(cabang["store_id"])

    store_service.ensure_startup_state()

    after = store_registry.get_store(cabang["store_id"])
    assert after["database_id"] == before["database_id"]
    assert after["nama"] == "Cabang Stabil"
    assert after["alamat"] == "Jl. Stabil No. 7"
    with db_session.store_session(db_session.active_engine()) as db:
        assert store_service.ensure_database_id(db) == before["database_id"]


def test_free_baca_dan_ekspor_terbuka_tulis_premium_terkunci(client, create_customer):
    create_customer(nama="Pelanggan Lama")
    assert client.post(
        "/api/employees", json={"nama": "Budi", "peran": "KASIR"}
    ).status_code == 201
    assert client.post(
        "/api/suppliers", json={"nama": "Supplier Lama"}
    ).status_code == 201

    store_registry.set_plan("free")

    assert _names(client, "/api/customers") == ["Pelanggan Lama"]
    assert _names(client, "/api/employees") == ["Budi"]
    assert _names(client, "/api/suppliers") == ["Supplier Lama"]

    terkunci = (
        ("/api/stores", {"nama": "Cabang Terlarang", "alamat": "Jl. X"}),
        ("/api/employees", {"nama": "Karyawan Baru", "peran": "KASIR"}),
        ("/api/suppliers", {"nama": "Supplier Baru"}),
        ("/api/employee-debts", {"employee_id": 1, "jumlah": "10000"}),
        ("/api/salary-payments", {"employee_id": 1, "jumlah": "10000"}),
    )
    for path, payload in terkunci:
        response = client.post(path, json=payload)
        assert response.status_code == 403, (path, response.text)
        assert response.json()["code"] == "premium_locked"

    for path in ("/api/admin/scheduled-backup", "/api/admin/telegram-backup"):
        response = client.post(path)
        assert response.status_code == 403, (path, response.text)

    telegram = client.put(
        "/api/settings/telegram", json={"enabled": False, "jam": "21:00"}
    )
    assert telegram.status_code == 403
    assert telegram.json()["code"] == "premium_locked"

    assert client.post(
        "/api/customers",
        json={"nama": "Pelanggan Baru", "nomor_hp": "0812-0000-9999"},
    ).status_code == 201

    for fmt in ("db", "xlsx", "csv"):
        backup = client.post("/api/admin/backup", params={"format": fmt})
        assert backup.status_code == 200, (fmt, backup.text)
        assert backup.content


def test_kuota_baru_untuk_database_toko_baru(client):
    store_registry.set_plan("free")
    with db_session.SessionLocal() as db:
        for _ in range(5):
            followup_quota_service.consume(db)
        assert followup_quota_service.status(db)["sisa"] == 15

    store_registry.set_plan("premium")
    cabang = _create_store(client, "Cabang Kuota")
    _activate(client, cabang["store_id"])
    store_registry.set_plan("free")

    config = client.get("/api/config")
    assert config.status_code == 200, config.text
    kuota = config.json()["kuota_followup"]
    assert kuota["database_id"] == cabang["database_id"]
    assert kuota["terpakai"] == 0
    assert kuota["sisa"] == followup_quota_service.FREE_LIMIT
    assert kuota["terkunci"] is False


def test_salinan_berkas_membawa_database_id_dan_kuota(client, tmp_path):
    store_registry.set_plan("free")
    with db_session.SessionLocal() as db:
        for _ in range(3):
            followup_quota_service.consume(db)
        asli = followup_quota_service.status(db)

    salinan = tmp_path / "salinan_bengkel.db"
    shutil.copy2(db_session.active_database_path(), salinan)
    engine = db_session.build_engine(f"sqlite:///{salinan.as_posix()}")
    try:
        with db_session.store_session(engine) as db:
            status = followup_quota_service.status(db)
    finally:
        engine.dispose()

    assert status["database_id"] == asli["database_id"]
    assert status["terpakai"] == 3
    assert status["sisa"] == followup_quota_service.FREE_LIMIT - 3


def test_kuota_atomik_saat_lima_tautan_dibuka_bersamaan(monkeypatch):
    store_registry.set_plan("free")
    jumlah = 5
    barrier = threading.Barrier(jumlah)
    asli = followup_quota_service.ensure_available

    def tertahan(db):
        current = asli(db)
        barrier.wait(timeout=10)
        return current

    monkeypatch.setattr(followup_quota_service, "ensure_available", tertahan)
    engine = db_session.engine

    def buka_tautan(_):
        with db_session.store_session(engine) as db:
            return followup_quota_service.consume(db)["terpakai"]

    with ThreadPoolExecutor(max_workers=jumlah) as pool:
        hasil = sorted(pool.map(buka_tautan, range(jumlah)))

    assert hasil == list(range(1, jumlah + 1)), hasil
    with db_session.SessionLocal() as db:
        row = db.get(AppSetting, followup_quota_service.USED_KEY)
    assert row is not None
    assert int(row.value) == jumlah
