"""S-01: field null pada PUT stok/jasa ditolak tanpa mengubah data."""
from __future__ import annotations

import pytest

STOCK_FIELDS = [
    ("nama", "Nama"),
    ("harga_modal", "Harga modal"),
    ("harga_jual", "Harga jual"),
    ("jumlah", "Jumlah"),
]

JASA_FIELDS = [
    ("nama", "Nama"),
    ("harga_standar", "Harga standar"),
]


def _stock_state(client, stock_id: int) -> dict:
    items = client.get("/api/stock").json()
    item = next(row for row in items if row["id"] == stock_id)
    return {
        "nama": item["nama"],
        "harga_modal": item["harga_modal"],
        "harga_jual": item["harga_jual"],
        "jumlah": item["jumlah"],
    }


def _jasa_state(client, jasa_id: int) -> dict:
    items = client.get("/api/harga-jasa").json()
    item = next(row for row in items if row["id"] == jasa_id)
    return {"nama": item["nama"], "harga_standar": item["harga_standar"]}


@pytest.mark.parametrize(("field", "label"), STOCK_FIELDS)
def test_s01_put_stock_dengan_null_ditolak_400(client, stock, field, label):
    item = stock("SP-001")
    before = _stock_state(client, item["id"])

    response = client.put(f"/api/stock/{item['id']}", json={field: None})

    assert response.status_code == 400, response.text
    assert label.lower() in response.json()["detail"].lower()
    assert "kosong" in response.json()["detail"].lower()
    assert _stock_state(client, item["id"]) == before


@pytest.mark.parametrize(("field", "label"), JASA_FIELDS)
def test_s01_put_jasa_dengan_null_ditolak_400(client, jasa, field, label):
    item = jasa("Korok / Kuras Kerak Radiator")
    before = _jasa_state(client, item["id"])

    response = client.put(f"/api/harga-jasa/{item['id']}", json={field: None})

    assert response.status_code == 400, response.text
    assert label.lower() in response.json()["detail"].lower()
    assert "kosong" in response.json()["detail"].lower()
    assert _jasa_state(client, item["id"]) == before


def test_s01_field_absen_tidak_mengubah_nilai_lain(client, stock, jasa):
    item = stock("SP-001")
    before = _stock_state(client, item["id"])

    updated = client.put(f"/api/stock/{item['id']}", json={"nama": "Upper Tank Baru"})
    assert updated.status_code == 200, updated.text
    after = _stock_state(client, item["id"])
    assert after["nama"] == "Upper Tank Baru"
    assert after["harga_modal"] == before["harga_modal"]
    assert after["harga_jual"] == before["harga_jual"]
    assert after["jumlah"] == before["jumlah"]

    master = jasa("Korok / Kuras Kerak Radiator")
    jasa_before = _jasa_state(client, master["id"])
    changed = client.put(
        f"/api/harga-jasa/{master['id']}", json={"harga_standar": "165000"}
    )
    assert changed.status_code == 200, changed.text
    jasa_after = _jasa_state(client, master["id"])
    assert jasa_after["harga_standar"] == "165000.00"
    assert jasa_after["nama"] == jasa_before["nama"]
