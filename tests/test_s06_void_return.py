"""S-06: void/retur transaksi atomik + ledger pergerakan stok.

Setiap skenario ditulis sebagai kontrak API agar perilaku desktop dan APK
(backend yang sama) teruji tanpa bergantung pada UI.
"""
from __future__ import annotations

from datetime import date

import pytest


def sale(client, make_transaction, unit_id, stock_item_id, *, part_qty=2, job_price="150000"):
    payload_parts = []
    if part_qty:
        payload_parts.append(
            {
                "stock_item_id": stock_item_id,
                "nama_part": "",
                "jumlah": part_qty,
                "harga_satuan": "160000",
            }
        )
    response = make_transaction(
        unit_id,
        jobs=[
            {
                "deskripsi": "Korok / Kuras Kerak Radiator",
                "jumlah": 1,
                "harga": job_price,
            }
        ],
        parts=payload_parts,
    )
    assert response.status_code == 201, response.text
    return response.json()


def part_id(body, index=0):
    return body["receipt"]["parts"][index]["id"]


def job_id(body, index=0):
    return body["receipt"]["jobs"][index]["id"]


def movements(client, stock_item_id):
    response = client.get(
        "/api/stock/movements", params={"stock_item_id": stock_item_id}
    )
    assert response.status_code == 200, response.text
    return response.json()


def ledger_total(client, stock_item_id):
    return sum(row["jumlah"] for row in movements(client, stock_item_id))


# --- VOID -----------------------------------------------------------------
def test_s06_void_atomik_mengembalikan_stok_dan_menyimpan_audit(
    client, create_customer, create_unit, make_transaction, stock
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    item = stock("SP-001")
    awal = item["jumlah"]
    body = sale(client, make_transaction, unit["id"], item["id"], part_qty=2)
    record = body["record"]
    assert record["status"] == "NORMAL"
    assert record["total_neto"] == record["total_servis"]
    assert stock("SP-001")["jumlah"] == awal - 2

    response = client.post(
        f"/api/service-records/{record['id']}/void",
        json={"alasan": "Salah input pelanggan"},
    )

    assert response.status_code == 200, response.text
    voided = response.json()
    assert voided["status"] == "VOID"
    assert voided["void_reason"] == "Salah input pelanggan"
    assert voided["voided_by"] == "Pemilik"
    assert voided["voided_at"]
    assert voided["total_neto"] == "0.00"
    assert voided["garansi_aktif"] is False
    assert voided["warranty_status"] == "DIBATALKAN"

    # Stok kembali tepat sekali dan ledger mencatat VOID.
    assert stock("SP-001")["jumlah"] == awal
    assert ledger_total(client, item["id"]) == stock("SP-001")["jumlah"]
    void_moves = [row for row in movements(client, item["id"]) if row["jenis"] == "VOID"]
    assert len(void_moves) == 1
    assert void_moves[0]["jumlah"] == 2
    assert void_moves[0]["service_record_id"] == record["id"]
    assert "Salah input pelanggan" in (void_moves[0]["alasan"] or "")
    assert void_moves[0]["oleh"] == "Pemilik"

    # Nota tidak dihapus; riwayat dan rincian tetap tersedia.
    history = client.get("/api/service-records").json()
    assert len(history) == 1
    assert history[0]["id"] == record["id"]
    assert history[0]["status"] == "VOID"
    receipt = client.get(f"/api/service-records/{record['id']}/receipt")
    assert receipt.status_code == 200
    assert receipt.json()["status"] == "VOID"
    assert receipt.json()["parts"][0]["jumlah"] == 2
    assert any("DIBATALKAN" in line.upper() for line in receipt.json()["struk_58"])

    claim = client.put(f"/api/service-records/{record['id']}/claim")
    assert claim.status_code == 409
    assert "void" in claim.json()["detail"].lower()


def test_s06_void_gagal_tidak_merusak_stok_dan_status(
    client, create_customer, create_unit, make_transaction, stock, monkeypatch
):
    from services import void_return_service

    customer = create_customer()
    unit = create_unit(customer["id"])
    item = stock("SP-001")
    awal = item["jumlah"]
    body = sale(client, make_transaction, unit["id"], item["id"], part_qty=2)
    record_id = body["record"]["id"]
    setelah_jual = stock("SP-001")["jumlah"]
    assert setelah_jual == awal - 2

    class Boom:
        def __init__(self, **_kwargs):
            raise RuntimeError("simulasi gagal menulis ledger")

    monkeypatch.setattr(void_return_service, "StockMovement", Boom)

    with pytest.raises(RuntimeError):
        client.post(
            f"/api/service-records/{record_id}/void",
            json={"alasan": "Salah input"},
        )

    detail = client.get(f"/api/service-records/{record_id}").json()
    assert detail["status"] == "NORMAL"
    assert detail["void_reason"] is None
    assert stock("SP-001")["jumlah"] == setelah_jual
    assert ledger_total(client, item["id"]) == setelah_jual

    report = client.get(
        "/api/reports/daily-cash", params={"tanggal": date.today().isoformat()}
    ).json()
    assert report["jumlah_transaksi"] == 1


def test_s06_void_dua_kali_dan_retur_setelah_void_ditolak(
    client, create_customer, create_unit, make_transaction, stock
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    item = stock("SP-001")
    awal = item["jumlah"]
    body = sale(client, make_transaction, unit["id"], item["id"], part_qty=2)
    record_id = body["record"]["id"]

    first = client.post(
        f"/api/service-records/{record_id}/void", json={"alasan": "Nota batal"}
    )
    assert first.status_code == 200, first.text

    second = client.post(
        f"/api/service-records/{record_id}/void", json={"alasan": "Batal lagi"}
    )
    assert second.status_code == 409

    retur = client.post(
        f"/api/service-records/{record_id}/returns",
        json={
            "alasan": "Barang tidak cocok",
            "items": [{"service_part_id": part_id(body), "jumlah": 1}],
        },
    )
    assert retur.status_code == 409
    assert stock("SP-001")["jumlah"] == awal
    assert ledger_total(client, item["id"]) == awal


# --- RETUR ----------------------------------------------------------------
def test_s06_retur_sebagian_atomik_stok_dan_nilai(
    client, create_customer, create_unit, make_transaction, stock
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    item = stock("SP-001")
    awal = item["jumlah"]
    body = sale(client, make_transaction, unit["id"], item["id"], part_qty=3)
    record = body["record"]
    assert stock("SP-001")["jumlah"] == awal - 3

    response = client.post(
        f"/api/service-records/{record['id']}/returns",
        json={
            "alasan": "Barang tidak cocok",
            "items": [{"service_part_id": part_id(body), "jumlah": 1}],
        },
    )

    assert response.status_code == 201, response.text
    retur = response.json()
    assert retur["service_record_id"] == record["id"]
    assert retur["alasan"] == "Barang tidak cocok"
    assert retur["oleh"] == "Pemilik"
    assert retur["total_nilai"] == "160000.00"
    assert retur["items"][0]["nama_item"] == "Upper Tank Fiber Avanza"
    assert retur["items"][0]["jumlah"] == 1
    assert retur["items"][0]["harga_satuan"] == "160000.00"
    assert retur["items"][0]["subtotal"] == "160000.00"

    assert stock("SP-001")["jumlah"] == awal - 2
    assert ledger_total(client, item["id"]) == stock("SP-001")["jumlah"]
    retur_moves = [row for row in movements(client, item["id"]) if row["jenis"] == "RETUR"]
    assert retur_moves[0]["jumlah"] == 1
    assert retur_moves[0]["service_record_id"] == record["id"]
    assert retur_moves[0]["service_return_id"] == retur["id"]

    detail = client.get(f"/api/service-records/{record['id']}").json()
    assert detail["status"] == "NORMAL"
    assert detail["total_retur"] == "160000.00"
    assert detail["retur_count"] == 1
    assert detail["total_neto"] == "470000.00"
    # Harga nota asli tetap (tidak dihapus/ditulis ulang).
    assert detail["total_servis"] == "630000.00"

    listed = client.get(f"/api/service-records/{record['id']}/returns")
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [retur["id"]]


def test_s06_retur_penuh_jasa_dan_part_menolkan_laporan_dan_laba(
    client, create_customer, create_unit, make_transaction, stock
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    item = stock("SP-001")
    awal = item["jumlah"]
    body = sale(client, make_transaction, unit["id"], item["id"], part_qty=2)
    record_id = body["record"]["id"]

    response = client.post(
        f"/api/service-records/{record_id}/returns",
        json={
            "alasan": "Pelanggan membatalkan seluruh pengerjaan",
            "items": [
                {"service_part_id": part_id(body), "jumlah": 2},
                {"service_job_id": job_id(body), "jumlah": 1},
            ],
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["total_nilai"] == "470000.00"

    detail = client.get(f"/api/service-records/{record_id}").json()
    assert detail["total_retur"] == "470000.00"
    assert detail["total_neto"] == "0.00"
    assert detail["retur_count"] == 1
    assert detail["status"] == "NORMAL"
    assert stock("SP-001")["jumlah"] == awal

    daily = client.get(
        "/api/reports/daily-cash", params={"tanggal": date.today().isoformat()}
    ).json()
    assert daily["jumlah_transaksi"] == 1
    assert daily["total_omset"] == "0.00"
    assert daily["total_jasa"] == "0.00"
    assert daily["total_part"] == "0.00"
    assert daily["total_retur"] == "470000.00"
    assert daily["laba_kotor"] == "0.00"

    sold = client.get("/api/reports/sold-parts").json()
    assert sold["jumlah_penjualan"] == 0
    assert sold["total_qty"] == 0
    assert sold["total_nilai"] == "0.00"


def test_s06_retur_melebihi_jumlah_dan_retur_ganda_ditolak(
    client, create_customer, create_unit, make_transaction, stock
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    item = stock("SP-001")
    awal = item["jumlah"]
    body = sale(client, make_transaction, unit["id"], item["id"], part_qty=2)
    record_id = body["record"]["id"]
    setelah_jual = stock("SP-001")["jumlah"]

    terlalu_banyak = client.post(
        f"/api/service-records/{record_id}/returns",
        json={
            "alasan": "Retur melebihi pembelian",
            "items": [{"service_part_id": part_id(body), "jumlah": 3}],
        },
    )
    assert terlalu_banyak.status_code == 400
    assert "melebihi" in terlalu_banyak.json()["detail"].lower()
    assert stock("SP-001")["jumlah"] == setelah_jual
    assert client.get(f"/api/service-records/{record_id}/returns").json() == []
    assert ledger_total(client, item["id"]) == setelah_jual

    penuh = client.post(
        f"/api/service-records/{record_id}/returns",
        json={
            "alasan": "Retur penuh",
            "items": [{"service_part_id": part_id(body), "jumlah": 2}],
        },
    )
    assert penuh.status_code == 201, penuh.text
    assert stock("SP-001")["jumlah"] == awal

    ganda = client.post(
        f"/api/service-records/{record_id}/returns",
        json={
            "alasan": "Retur kedua",
            "items": [{"service_part_id": part_id(body), "jumlah": 1}],
        },
    )
    assert ganda.status_code == 400
    assert stock("SP-001")["jumlah"] == awal
    assert ledger_total(client, item["id"]) == awal

    detail = client.get(f"/api/service-records/{record_id}").json()
    assert detail["retur_count"] == 1
    assert detail["total_retur"] == "320000.00"


def test_s06_retur_gagal_tidak_mengubah_stok_atau_status(
    client, create_customer, create_unit, make_transaction, stock, monkeypatch
):
    from services import void_return_service

    customer = create_customer()
    unit = create_unit(customer["id"])
    item = stock("SP-001")
    body = sale(client, make_transaction, unit["id"], item["id"], part_qty=2)
    record_id = body["record"]["id"]
    setelah_jual = stock("SP-001")["jumlah"]

    class Boom:
        def __init__(self, **_kwargs):
            raise RuntimeError("simulasi gagal menulis ledger retur")

    monkeypatch.setattr(void_return_service, "StockMovement", Boom)

    with pytest.raises(RuntimeError):
        client.post(
            f"/api/service-records/{record_id}/returns",
            json={
                "alasan": "Retur uji rollback",
                "items": [{"service_part_id": part_id(body), "jumlah": 1}],
            },
        )

    assert stock("SP-001")["jumlah"] == setelah_jual
    assert client.get(f"/api/service-records/{record_id}/returns").json() == []
    detail = client.get(f"/api/service-records/{record_id}").json()
    assert detail["total_retur"] == "0.00"
    assert detail["retur_count"] == 0


def test_s06_retur_part_milik_nota_lain_ditolak(
    client, create_customer, create_unit, make_transaction, stock
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    item = stock("SP-007")
    awal = item["jumlah"]
    nota_a = sale(client, make_transaction, unit["id"], item["id"], part_qty=1)
    nota_b = sale(client, make_transaction, unit["id"], item["id"], part_qty=1)

    response = client.post(
        f"/api/service-records/{nota_b['record']['id']}/returns",
        json={
            "alasan": "Part nota lain",
            "items": [{"service_part_id": part_id(nota_a), "jumlah": 1}],
        },
    )
    assert response.status_code == 404
    assert stock("SP-007")["jumlah"] == awal - 2
    assert client.get(
        f"/api/service-records/{nota_b['record']['id']}/returns"
    ).json() == []


# --- LAPORAN --------------------------------------------------------------
def test_s06_void_dikecualikan_dan_retur_mengurangi_semua_laporan(
    client, create_customer, create_unit, make_transaction, stock
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    item = stock("SP-001")
    awal = item["jumlah"]

    # Nota A: jasa 300rb, akan di-VOID.
    nota_a = sale(
        client, make_transaction, unit["id"], item["id"], part_qty=0, job_price="300000"
    )
    a_id = nota_a["record"]["id"]
    void = client.post(
        f"/api/service-records/{a_id}/void", json={"alasan": "Salah input"}
    )
    assert void.status_code == 200, void.text

    # Nota B: jasa 150rb + part 2 x 160rb; retur 1 part.
    nota_b = sale(client, make_transaction, unit["id"], item["id"], part_qty=2)
    b_id = nota_b["record"]["id"]
    retur = client.post(
        f"/api/service-records/{b_id}/returns",
        json={
            "alasan": "Satu part tidak dipakai",
            "items": [{"service_part_id": part_id(nota_b), "jumlah": 1}],
        },
    )
    assert retur.status_code == 201, retur.text

    today = date.today().isoformat()
    daily = client.get("/api/reports/daily-cash", params={"tanggal": today}).json()
    assert daily["jumlah_transaksi"] == 1
    assert daily["jumlah_unit_servis"] == 1
    assert daily["total_omset"] == "310000.00"
    assert daily["total_jasa"] == "150000.00"
    assert daily["total_part"] == "160000.00"
    assert daily["total_retur"] == "160000.00"
    assert daily["jumlah_retur"] == 1
    assert daily["total_void"] == "300000.00"
    assert daily["jumlah_void"] == 1
    # (160.000 deal - 85.000 modal) x 1 sisa = 75.000
    assert daily["laba_kotor"] == "75000.00"
    assert [row["id"] for row in daily["transaksi"]] == [b_id]

    period = client.get(
        "/api/reports/period", params={"start": today, "end": today}
    ).json()
    assert period["total_omset"] == daily["total_omset"]
    assert period["total_retur"] == daily["total_retur"]
    assert period["total_void"] == daily["total_void"]
    assert period["harian"][0]["total_omset"] == daily["total_omset"]
    assert period["harian"][0]["total_void"] == daily["total_void"]

    all_time = client.get("/api/reports/all-time").json()
    assert all_time["jumlah_transaksi"] == 1
    assert all_time["total_omset"] == "310000.00"
    assert all_time["total_void"] == "300000.00"

    sold = client.get(
        "/api/reports/sold-parts", params={"start": today, "end": today}
    ).json()
    assert sold["jumlah_penjualan"] == 1
    assert sold["total_qty"] == 1
    assert sold["total_nilai"] == "160000.00"
    assert sold["items"][0]["service_record_id"] == b_id
    assert sold["items"][0]["jumlah"] == 1
    assert sold["items"][0]["jumlah_retur"] == 1

    history = client.get("/api/service-records").json()
    assert {row["id"]: row["status"] for row in history} == {
        a_id: "VOID",
        b_id: "NORMAL",
    }
    assert stock("SP-001")["jumlah"] == awal - 1


# --- LEDGER STOK ----------------------------------------------------------
def test_s06_ledger_mencatat_masuk_koreksi_dan_penjualan(
    client, create_customer, create_unit, make_transaction, stock
):
    item = stock("SP-001")
    awal = item["jumlah"]
    assert ledger_total(client, item["id"]) == awal

    dibuat = client.post(
        "/api/stock",
        json={
            "kode": "SP-099",
            "nama": "Part Uji Ledger",
            "harga_modal": "10000",
            "harga_jual": "15000",
            "jumlah": 4,
        },
    )
    assert dibuat.status_code == 201, dibuat.text
    baru = dibuat.json()
    rows = movements(client, baru["id"])
    assert [(row["jenis"], row["jumlah"]) for row in rows] == [("MASUK", 4)]
    assert sum(row["jumlah"] for row in rows) == 4

    koreksi = client.put(
        f"/api/stock/{baru['id']}",
        json={"jumlah": 1, "alasan": "Stock opname mingguan"},
    )
    assert koreksi.status_code == 200, koreksi.text
    rows = movements(client, baru["id"])
    koreksi_rows = [row for row in rows if row["jenis"] == "KOREKSI"]
    assert koreksi_rows[0]["jumlah"] == -3
    assert "Stock opname" in koreksi_rows[0]["alasan"]
    assert sum(row["jumlah"] for row in rows) == 1

    customer = create_customer()
    unit = create_unit(customer["id"])
    sale(client, make_transaction, unit["id"], baru["id"], part_qty=1)
    rows = movements(client, baru["id"])
    keluar = [row for row in rows if row["jenis"] == "KELUAR"]
    assert keluar[0]["jumlah"] == -1
    assert keluar[0]["service_record_id"] is not None
    assert sum(row["jumlah"] for row in rows) == 0
