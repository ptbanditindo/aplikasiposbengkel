"""Tahap 7: pengaturan struk per bagian."""
from __future__ import annotations


def test_pengaturan_struk_default_semua_tampil(client):
    response = client.get("/api/settings/receipt")
    assert response.status_code == 200, response.text
    body = response.json()
    assert all(body.values()) is True


def test_toggle_struk_mematikan_bagian_dan_berlaku_untuk_wa(
    client, create_customer, create_unit, make_transaction
):
    customer = create_customer(nama="Pelanggan Struk")
    unit = create_unit(customer["id"], nopol="B 8501 STR")
    response = make_transaction(
        unit["id"],
        jobs=[{"deskripsi": "Servis Radiator", "jumlah": 1, "harga": "100000"}],
    )
    assert response.status_code == 201, response.text
    record_id = response.json()["record"]["id"]

    response = client.put(
        "/api/settings/receipt",
        json={"jasa": False, "kasir": False, "garansi": False},
    )
    assert response.status_code == 200, response.text
    assert response.json()["jasa"] is False
    assert response.json()["part"] is True

    receipt = client.get(f"/api/service-records/{record_id}/receipt").json()
    text = "\n".join(receipt["struk_58"])
    assert "JASA:" not in text
    assert "GARANSI SERVIS:" not in text
    assert "Kasir" not in text
    assert receipt["wa_text"] == "\n".join(receipt["struk_58"]).strip()
    assert "JASA:" not in receipt["wa_text"]

    client.put(
        "/api/settings/receipt",
        json={
            "tagline": False,
            "alamat": False,
            "kontak": False,
            "no_nota": False,
            "tanggal": False,
            "kasir": False,
            "mekanik": False,
            "pelanggan": False,
            "hp": False,
            "unit": False,
            "keluhan": False,
            "catatan": False,
            "jasa": False,
            "part": False,
            "total_jasa": False,
            "total_part": False,
            "diskon": False,
            "grand_total": False,
            "metode": False,
            "bayar": False,
            "kembalian": False,
            "status_bayar": False,
            "garansi": False,
            "rekening": False,
            "footer": False,
        },
    )
    receipt = client.get(f"/api/service-records/{record_id}/receipt").json()
    text = "\n".join(receipt["struk_58"])
    assert "BENGKEL RADIATOR" in text
    assert "TEST" in text


def test_toggle_karyawan_off_menyembunyikan_nama_karyawan(
    client, create_customer, create_unit, make_transaction
):
    employee = client.post(
        "/api/employees",
        json={
            "nama": "Karyawan Toggle",
            "peran": "KEDUANYA",
            "aktif": True,
            "komisi_mode": "PERSEN",
            "komisi_basis": "JASA",
            "komisi_nilai": "0",
        },
    ).json()
    customer = create_customer(nama="Pelanggan Toggle")
    unit = create_unit(customer["id"], nopol="B 8502 TGL")
    response = make_transaction(
        unit["id"],
        cashier_employee_id=employee["id"],
        mechanic_ids=[employee["id"]],
    )
    assert response.status_code == 201, response.text
    record_id = response.json()["record"]["id"]

    response = client.put(
        "/api/settings/ops", json={"karyawan_aktif": False}
    )
    assert response.status_code == 200, response.text
    receipt = client.get(f"/api/service-records/{record_id}/receipt").json()
    text = "\n".join(receipt["struk_58"])
    assert "Kasir" not in text
    assert "Mekanik" not in text
