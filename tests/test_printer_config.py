"""Konfigurasi printer lokal: validasi, persistensi, dan keamanan data.

Konfigurasi printer menyimpan identitas perangkat (MAC/IP) sehingga ditulis
ke berkas lokal di luar database backup. Menghapus/mengganti printer tidak
boleh menyentuh transaksi, pelanggan, atau stok.
"""
from __future__ import annotations

import json

import pytest

from config import settings

ENDPOINT = "/api/printer/config"


def printer(**overrides):
    data = {
        "id": "printer-kasir",
        "name": "Printer Kasir",
        "connection_type": "BLUETOOTH",
        "paper_width": 58,
        "print_mode": "ESCPOS",
        "encoding": "CP437",
        "address": "AA:BB:CC:DD:EE:FF",
        "ip": None,
        "port": None,
        "last_status": "SAVED",
        "last_connected_at": None,
        "last_error": None,
    }
    data.update(overrides)
    return data


def config(*printers, primary_id=None):
    return {"printers": list(printers), "primary_id": primary_id}


def test_default_kosong(client):
    response = client.get(ENDPOINT)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["version"] == 1
    assert body["printers"] == []
    assert body["primary_id"] is None


def test_simpan_dan_baca_ulang(client):
    payload = config(printer(), primary_id="printer-kasir")
    saved = client.put(ENDPOINT, json=payload)
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["primary_id"] == "printer-kasir"
    assert body["printers"][0]["name"] == "Printer Kasir"
    assert body["printers"][0]["address"] == "AA:BB:CC:DD:EE:FF"
    assert body["updated_at"]

    reread = client.get(ENDPOINT).json()
    assert reread["primary_id"] == "printer-kasir"
    assert reread["printers"][0]["id"] == "printer-kasir"


def test_tersimpan_setelah_aplikasi_dibuka_ulang(client, anon_client):
    saved = client.put(ENDPOINT, json=config(printer(), primary_id="printer-kasir"))
    assert saved.status_code == 200, saved.text

    login = anon_client.post("/api/auth/login", json={"pin": "2468"})
    assert login.status_code == 200, login.text
    body = anon_client.get(ENDPOINT).json()
    assert [item["id"] for item in body["printers"]] == ["printer-kasir"]


def test_ganti_printer_utama_tanpa_menghapus_printer_lain(client):
    first = printer(id="printer-a", name="Printer A")
    second = printer(
        id="printer-b",
        name="Printer B",
        address="11:22:33:44:55:66",
    )
    saved = client.put(
        ENDPOINT, json=config(first, second, primary_id="printer-a")
    )
    assert saved.status_code == 200, saved.text

    switched = client.put(
        ENDPOINT, json=config(first, second, primary_id="printer-b")
    )
    assert switched.status_code == 200, switched.text
    body = client.get(ENDPOINT).json()
    assert body["primary_id"] == "printer-b"
    assert {item["id"] for item in body["printers"]} == {
        "printer-a",
        "printer-b",
    }


def test_status_koneksi_hidup_tidak_tersimpan_setelah_muat_ulang(client):
    payload = config(
        printer(last_status="CONNECTED", last_connected_at="2026-10-31T08:00:00Z"),
        primary_id="printer-kasir",
    )
    assert client.put(ENDPOINT, json=payload).status_code == 200

    body = client.get(ENDPOINT).json()
    assert body["printers"][0]["last_status"] == "SAVED"
    # Waktu koneksi terakhir tetap tersimpan untuk ditampilkan.
    assert body["printers"][0]["last_connected_at"] == "2026-10-31T08:00:00Z"


def test_printer_network_menyimpan_ip_dan_port(client):
    payload = config(
        printer(
            id="printer-lan",
            name="Printer LAN",
            connection_type="NETWORK",
            address=None,
            ip="192.168.1.9",
            port=9100,
        ),
        primary_id="printer-lan",
    )
    saved = client.put(ENDPOINT, json=payload)
    assert saved.status_code == 200, saved.text
    stored = saved.json()["printers"][0]
    assert stored["connection_type"] == "NETWORK"
    assert stored["ip"] == "192.168.1.9"
    assert stored["port"] == 9100
    # Alamat Bluetooth tidak dipakai untuk printer jaringan.
    assert stored["address"] == ""

    reread = client.get(ENDPOINT).json()["printers"][0]
    assert reread["ip"] == "192.168.1.9"
    assert reread["port"] == 9100


def test_ganti_port_printer_network_tanpa_menghapus_printer_lain(client):
    lan_a = printer(
        id="lan-a",
        name="Printer LAN A",
        connection_type="NETWORK",
        address=None,
        ip="192.168.1.10",
        port=9100,
    )
    lan_b = printer(
        id="lan-b",
        name="Printer LAN B",
        connection_type="NETWORK",
        address=None,
        ip="192.168.1.11",
        port=6101,
    )
    saved = client.put(
        ENDPOINT, json=config(lan_a, lan_b, primary_id="lan-a")
    )
    assert saved.status_code == 200, saved.text

    lan_a["port"] = 9101
    switched = client.put(
        ENDPOINT, json=config(lan_a, lan_b, primary_id="lan-b")
    )
    assert switched.status_code == 200, switched.text
    body = client.get(ENDPOINT).json()
    assert body["primary_id"] == "lan-b"
    by_id = {item["id"]: item for item in body["printers"]}
    assert set(by_id) == {"lan-a", "lan-b"}
    assert by_id["lan-a"]["port"] == 9101
    assert by_id["lan-b"]["port"] == 6101


def test_printer_usb_menyimpan_identitas_perangkat(client):
    payload = config(
        printer(
            id="printer-usb",
            name="Printer USB OTG",
            connection_type="USB",
            address="usb:04b8:0202",
            ip=None,
            port=None,
            print_mode="ESCPOS",
        ),
        primary_id="printer-usb",
    )
    saved = client.put(ENDPOINT, json=payload)
    assert saved.status_code == 200, saved.text
    stored = saved.json()["printers"][0]
    assert stored["connection_type"] == "USB"
    assert stored["address"] == "usb:04b8:0202"
    # USB OTG tidak memakai IP atau port jaringan.
    assert stored["ip"] == ""
    assert stored["port"] is None
    assert stored["print_mode"] == "ESCPOS"

    reread = client.get(ENDPOINT).json()["printers"][0]
    assert reread["connection_type"] == "USB"
    assert reread["address"] == "usb:04b8:0202"


@pytest.mark.parametrize(
    "payload, pesan",
    [
        (config(printer(id="printer#1")), "ID"),
        (
            config(
                printer(id="sama"),
                printer(id="sama", address="11:22:33:44:55:66"),
            ),
            "duplikat",
        ),
        (
            config(
                printer(id="a", address="AA:BB:CC:DD:EE:FF"),
                printer(id="b", address="AA:BB:CC:DD:EE:FF"),
            ),
            "duplikat",
        ),
        (config(printer(connection_type="THERMAL")), "Jenis koneksi"),
        (config(printer(paper_width=57)), "Lebar kertas"),
        (config(printer(name="   ")), "Nama printer"),
        (config(printer(address=None)), "Alamat Bluetooth"),
        (
            config(
                printer(
                    id="lan",
                    connection_type="NETWORK",
                    address=None,
                    ip=None,
                    port=9100,
                )
            ),
            "IP",
        ),
        (
            config(
                printer(
                    id="lan",
                    connection_type="NETWORK",
                    address=None,
                    ip="192.168.1.9",
                    port=None,
                )
            ),
            "Port",
        ),
        (
            config(
                printer(
                    id="usb",
                    connection_type="USB",
                    address=None,
                )
            ),
            "USB",
        ),
        (
            config(
                printer(
                    id="lan",
                    connection_type="NETWORK",
                    address=None,
                    ip="192.168.1.999",
                    port=9100,
                )
            ),
            "IP",
        ),
        (
            config(
                printer(
                    id="lan",
                    connection_type="NETWORK",
                    address=None,
                    ip="printer.local",
                    port=9100,
                )
            ),
            "IP",
        ),
        (
            config(
                printer(
                    id="lan",
                    connection_type="NETWORK",
                    address=None,
                    ip="192.168.1.9",
                    port=70000,
                )
            ),
            "Port",
        ),
        (
            config(
                printer(
                    id="lan-a",
                    connection_type="NETWORK",
                    address=None,
                    ip="192.168.1.9",
                    port=9100,
                ),
                printer(
                    id="lan-b",
                    connection_type="NETWORK",
                    address=None,
                    ip="192.168.1.9",
                    port=9100,
                ),
            ),
            "duplikat",
        ),
        (
            config(printer(last_status="MENYALA")),
            "Status",
        ),
        (
            config(printer(print_mode="BROWSER")),
            "Mode cetak",
        ),
        (config(printer(), primary_id="tidak-ada"), "utama"),
    ],
)
def test_validasi_konfigurasi_printer(client, payload, pesan):
    response = client.put(ENDPOINT, json=payload)
    assert response.status_code == 400, response.text
    assert pesan in response.json()["detail"]
    # Konfigurasi lama tidak berubah saat payload ditolak.
    assert client.get(ENDPOINT).json()["printers"] == []


def test_batas_jumlah_printer(client):
    printers = [
        printer(id=f"p{i}", address=f"AA:BB:CC:DD:EE:{i:02X}")
        for i in range(9)
    ]
    response = client.put(ENDPOINT, json=config(*printers))
    assert response.status_code == 400, response.text
    assert "Maksimal" in response.json()["detail"]


def test_field_tidak_dikenal_ditolak(client):
    payload = printer()
    payload["token_rahasia"] = "x"
    response = client.put(ENDPOINT, json=config(payload))
    assert response.status_code == 422, response.text


def test_wajib_sesi(anon_client):
    assert anon_client.get(ENDPOINT).status_code == 401
    assert anon_client.put(ENDPOINT, json=config()).status_code == 401


def test_hapus_printer_tidak_menghapus_transaksi(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer()
    unit = create_unit(customer["id"])
    created = make_transaction(unit["id"])
    assert created.status_code == 201, created.text
    nota = created.json()["record"]["no_nota"]
    total = created.json()["record"]["total_servis"]

    saved = client.put(ENDPOINT, json=config(printer(), primary_id="printer-kasir"))
    assert saved.status_code == 200, saved.text

    removed = client.put(ENDPOINT, json=config())
    assert removed.status_code == 200, removed.text
    assert removed.json()["printers"] == []
    assert removed.json()["primary_id"] is None

    records = client.get("/api/service-records").json()
    assert [item["no_nota"] for item in records] == [nota]
    receipt = client.get(f"/api/service-records/{records[0]['id']}/receipt")
    assert receipt.status_code == 200, receipt.text
    assert receipt.json()["total_servis"] == total


def test_berkas_rusak_tidak_membuat_aplikasi_gagal(client):
    path = settings.printer_config_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{bukan json", encoding="utf-8")

    response = client.get(ENDPOINT)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["printers"] == []
    assert "tidak dapat dibaca" in body["warning"]

    fixed = client.put(
        ENDPOINT, json=config(printer(), primary_id="printer-kasir")
    )
    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["warning"] is None
    assert client.get(ENDPOINT).json()["primary_id"] == "printer-kasir"


def test_identitas_tersimpan_di_luar_database(client):
    assert client.put(ENDPOINT, json=config(printer())).status_code == 200
    path = settings.printer_config_path
    assert path.exists()
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["printers"][0]["address"] == "AA:BB:CC:DD:EE:FF"
    # Bukan tabel app_settings/database, sehingga tidak ikut backup DB.
    assert path.name != "bengkel_test.db"
