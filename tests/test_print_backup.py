"""TC-17 s/d TC-20: format struk ESC/POS, rekening bank, reprint, backup."""
from __future__ import annotations

import base64
import sqlite3



def _transaction_with_long_text(client, create_customer, create_unit, make_transaction):
    customer = create_customer(
        nama="Pelanggan Nama Sangat Panjang Sekali 🚗",
        nomor_hp="081299998888",
    )
    unit = create_unit(
        customer["id"],
        nopol="B 9999 ZZZ",
        jenis_mobil="Toyota Land Cruiser Diesel",
    )
    response = make_transaction(
        unit["id"],
        keluhan_awal=(
            "Radiator bocor parah di bagian tangki atas dan kisi-kisi, "
            "mesin overheat saat perjalanan jauh 🚗🔥"
        ),
        jobs=[
            {
                "deskripsi": "Bongkar Pasang Radiator Mobil Diesel Besar",
                "jumlah": 1,
                "harga": "125000",
            }
        ],
        parts=[
            {
                "nama_part": "Upper Tank Fiber Avanza Original 🚙",
                "jumlah": 2,
                "harga_satuan": "135000",
            }
        ],
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_tc17_format_escpos_58mm_maksimal_32_karakter(
    client, create_customer, create_unit, make_transaction
):
    body = _transaction_with_long_text(
        client, create_customer, create_unit, make_transaction
    )
    receipt = body["receipt"]

    assert receipt["struk_58"]
    assert all(len(line) <= 32 for line in receipt["struk_58"])
    assert all(len(line) <= 48 for line in receipt["struk_80"])

    # Sanitasi ASCII: emoji & karakter non-ASCII tidak boleh lolos ke printer.
    assert all(
        ord(char) < 128 for line in receipt["struk_58"] for char in line
    )
    assert "🚗" not in "\n".join(receipt["struk_58"])

    for key in ("escpos_58_base64", "escpos_80_base64"):
        raw = base64.b64decode(receipt[key])
        assert raw.startswith(b"\x1b\x40")  # ESC @ (init)
        assert raw.endswith(b"\x1d\x56\x42\x00")  # GS V B 0 (feed & cut)

    width_58 = receipt["struk_58"]
    assert "-" * 32 in width_58
    assert "=" * 32 in width_58


def test_escpos_baris_double_width_maksimal_setengah_kertas():
    from services.escpos_service import ReceiptBuilder

    builder_58 = ReceiptBuilder(32)
    builder_58.center("BENGKEL RADIATOR BERKAH", bold=True, double=True)
    builder_58.kv("Grand Total", "Rp 1.250.000", bold=True, double=True)
    assert all(len(line) <= 16 for line in builder_58.lines())

    builder_80 = ReceiptBuilder(48)
    builder_80.center("BENGKEL RADIATOR BERKAH", bold=True, double=True)
    builder_80.kv("Grand Total", "Rp 1.250.000", bold=True, double=True)
    assert all(len(line) <= 24 for line in builder_80.lines())


def test_tc18_rekening_bank_bengkel_tercetak(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    body = make_transaction(unit["id"]).json()
    receipt = body["receipt"]
    text = "\n".join(receipt["struk_58"])

    assert receipt["bengkel_bank_nama"] == "BCA TEST"
    assert receipt["bengkel_no_rekening"] == "987-654-3210"
    assert receipt["bengkel_atas_nama"] == "BENGKEL RADIATOR TEST"
    assert "BCA TEST: 987-654-3210" in text
    assert "a/n BENGKEL RADIATOR TEST" in text
    assert "REKENING BENGKEL" in text


def test_tc19_cetak_ulang_nota_lama(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    created = make_transaction(unit["id"]).json()
    record_id = created["record"]["id"]

    first = client.get(f"/api/service-records/{record_id}/receipt")
    second = client.get(f"/api/service-records/{record_id}/receipt")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["no_nota"] == created["record"]["no_nota"]
    assert first.json()["struk_58"] == second.json()["struk_58"]
    assert first.json()["escpos_58_base64"] == second.json()["escpos_58_base64"]
    assert len(client.get("/api/service-records").json()) == 1

    missing = client.get("/api/service-records/999999/receipt")
    assert missing.status_code == 404


def test_tc20_ekspor_backup_database_sqlite(client, anon_client):
    unauthorized = anon_client.post("/api/admin/backup")
    assert unauthorized.status_code == 401

    response = client.post("/api/admin/backup")
    assert response.status_code == 200, response.text
    assert response.content.startswith(b"SQLite format 3\x00")
    assert "attachment" in response.headers.get("content-disposition", "")

    import tempfile
    from pathlib import Path

    backup_path = Path(tempfile.mkdtemp(prefix="bengkel_backup_check_")) / "backup.db"
    backup_path.write_bytes(response.content)

    connection = sqlite3.connect(str(backup_path))
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert {
            "customers",
            "vehicle_or_units",
            "stock_items",
            "harga_jasa",
            "service_records",
            "service_jobs",
            "service_parts",
        }.issubset(tables)
        assert connection.execute("SELECT COUNT(*) FROM stock_items").fetchone()[0] > 0
    finally:
        connection.close()


def test_restore_backup_roundtrip(client, create_customer):
    customer = create_customer(nama="Sebelum Backup")

    backup = client.post("/api/admin/backup")
    assert backup.status_code == 200

    restore = client.post(
        "/api/admin/restore",
        files={"file": ("backup.db", backup.content, "application/x-sqlite3")},
    )
    assert restore.status_code == 200, restore.text

    restored = client.get("/api/customers/search", params={"q": "Sebelum Backup"})
    assert [item["id"] for item in restored.json()] == [customer["id"]]


def test_restore_menolak_berkas_bukan_sqlite(client):
    response = client.post(
        "/api/admin/restore",
        files={"file": ("palsu.db", b"bukan database", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "SQLite" in response.json()["detail"]


def test_restore_menolak_sqlite_tanpa_skema_aplikasi(client, tmp_path):
    path = tmp_path / "database_lain.db"
    connection = sqlite3.connect(str(path))
    try:
        connection.execute("CREATE TABLE catatan (id INTEGER PRIMARY KEY, isi TEXT)")
        connection.commit()
    finally:
        connection.close()

    response = client.post(
        "/api/admin/restore",
        files={"file": ("database_lain.db", path.read_bytes(), "application/x-sqlite3")},
    )
    assert response.status_code == 400, response.text
    assert "tidak ditemukan" in response.json()["detail"]

    # Database aplikasi tidak boleh tergantikan oleh berkas asing.
    assert client.get("/api/stock").status_code == 200
