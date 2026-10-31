"""TC-01 s/d TC-05: pelanggan, normalisasi, multi-unit, radiator copotan."""
from __future__ import annotations

import pytest


def test_tc01_tambah_pelanggan_valid(client):
    response = client.post(
        "/api/customers",
        json={
            "nama": "  Budi Santoso  ",
            "nomor_hp": "0812-3456-7890",
            "alamat": "Jl. Mawar No. 1",
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["id"] > 0
    assert body["nama"] == "Budi Santoso"
    assert body["nomor_hp"] == "081234567890"
    assert body["alamat"] == "Jl. Mawar No. 1"

    search = client.get("/api/customers/search", params={"q": "budi"})
    assert search.status_code == 200
    assert [item["id"] for item in search.json()] == [body["id"]]

    # Pencarian nomor HP dengan spasi/tanda hubung tetap menemukan pelanggan.
    search_hp = client.get("/api/customers/search", params={"q": "0812 3456"})
    assert [item["id"] for item in search_hp.json()] == [body["id"]]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+62 812-3456-7890", "081234567890"),
        ("81234567890", "081234567890"),
        ("0812 3456 7890", "081234567890"),
        ("0812.3456.7890", "081234567890"),
    ],
)
def test_tc02_normalisasi_nomor_hp(client, raw, expected):
    response = client.post(
        "/api/customers",
        json={"nama": "Pelanggan Normalisasi", "nomor_hp": raw},
    )

    assert response.status_code == 201, response.text
    assert response.json()["nomor_hp"] == expected


def test_tc02_nomor_hp_tidak_valid_ditolak(client):
    response = client.post(
        "/api/customers",
        json={"nama": "Pelanggan Salah", "nomor_hp": "123"},
    )
    assert response.status_code == 400
    assert "Nomor HP" in response.json()["detail"]


def test_tc03_satu_pelanggan_banyak_mobil(client, create_customer, create_unit):
    customer = create_customer(nama="Haji Ahmad", nomor_hp="081200000001")

    units = [
        create_unit(customer["id"], nopol="B 1111 AAA", jenis_mobil="Avanza"),
        create_unit(customer["id"], nopol="B 2222 BBB", jenis_mobil="Innova"),
        create_unit(
            customer["id"],
            unit_type="RADIATOR_ONLY",
            nopol=None,
            jenis_mobil=None,
            tahun_mobil=None,
            tipe_radiator="Radiator Canter",
        ),
    ]

    listed = client.get(f"/api/customers/{customer['id']}/units")
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 3
    assert {unit["id"] for unit in body} == {unit["id"] for unit in units}
    assert {unit["unit_type"] for unit in body} == {"MOBIL", "RADIATOR_ONLY"}
    assert all(unit["customer_id"] == customer["id"] for unit in body)


def test_tc04_normalisasi_nopol_mobil(client, create_customer, create_unit):
    customer = create_customer()

    unit = create_unit(customer["id"], nopol="b@1234  abc")
    assert unit["nopol"] == "B 1234 ABC"
    assert unit["unit_type"] == "MOBIL"
    assert unit["label_radiator"] is None
    assert "B 1234 ABC" in unit["deskripsi"]


def test_tc04_nopol_wajib_untuk_unit_mobil(client, create_customer):
    customer = create_customer()

    response = client.post(
        "/api/units",
        json={
            "customer_id": customer["id"],
            "unit_type": "MOBIL",
            "nopol": "   ",
        },
    )
    assert response.status_code == 400
    assert "Nomor polisi" in response.json()["detail"]


def test_tc05_unit_radiator_copotan_tanpa_nopol(client, create_customer, create_unit):
    customer = create_customer()

    first = create_unit(
        customer["id"],
        unit_type="RADIATOR_ONLY",
        nopol=None,
        jenis_mobil=None,
        tahun_mobil=None,
        tipe_radiator="Radiator Avanza",
    )
    second = create_unit(
        customer["id"],
        unit_type="RADIATOR_ONLY",
        nopol=None,
        jenis_mobil=None,
        tahun_mobil=None,
        tipe_radiator="Radiator Genset",
    )

    assert first["nopol"] is None
    assert second["nopol"] is None
    # Label fisik baru dibuat saat transaksi pertama, bukan saat unit disimpan.
    assert first["label_radiator"] is None
    assert second["label_radiator"] is None
    assert "[BAWA RADIATOR SAJA]" in first["deskripsi"]
    assert first["deskripsi"] != second["deskripsi"]


def test_customer_overview_lists_units_and_counts(
    client, create_customer, create_unit
):
    customer = create_customer(nama="Pak Slamet", nomor_hp="081299990001")
    create_unit(customer["id"], nopol="B 9999 ZZ", jenis_mobil="Panther")
    create_unit(
        customer["id"],
        unit_type="RADIATOR_ONLY",
        nopol=None,
        jenis_mobil=None,
        tahun_mobil=None,
        tipe_radiator="Radiator Panther",
    )

    response = client.get("/api/customers/overview")
    assert response.status_code == 200, response.text
    row = next(item for item in response.json() if item["id"] == customer["id"])

    assert row["nama"] == "Pak Slamet"
    assert row["wa_consent"] is True
    assert row["total_unit"] == 2
    assert row["total_mobil"] == 1
    assert row["total_radiator"] == 1
    assert len(row["units"]) == 2
    assert {unit["unit_type"] for unit in row["units"]} == {
        "MOBIL",
        "RADIATOR_ONLY",
    }
    assert all(unit["deskripsi"] for unit in row["units"])


def test_customer_overview_search_filter(client, create_customer):
    siti = create_customer(nama="Siti Aminah", nomor_hp="081211112222")
    create_customer(nama="Joko Widodo", nomor_hp="081233334444")

    by_name = client.get("/api/customers/overview", params={"q": "siti"})
    assert [item["id"] for item in by_name.json()] == [siti["id"]]

    by_phone = client.get("/api/customers/overview", params={"q": "2222"})
    assert [item["id"] for item in by_phone.json()] == [siti["id"]]

    empty = client.get("/api/customers/overview", params={"q": "tidak-ada"})
    assert empty.json() == []
