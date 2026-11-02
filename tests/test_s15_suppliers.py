"""Tahap 2: supplier, relasi barang, dan follow up reseller."""
from __future__ import annotations

from database.models import WhatsAppLog


def _stock(client, nama, jumlah=2, minimum=5):
    response = client.post(
        "/api/stock",
        json={
            "nama": nama,
            "harga_modal": "10000",
            "harga_jual": "15000",
            "jumlah": jumlah,
            "stok_minimum": minimum,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_supplier_multi_barang_dan_followup_reseller(client):
    first = _stock(client, "Barang Supplier A", 1, 5)
    second = _stock(client, "Barang Supplier B", 0, 5)
    response = client.post(
        "/api/suppliers",
        json={
            "nama": "Supplier Uji",
            "nomor_hp": "081200001111",
            "stock_item_ids": [first["id"], second["id"]],
        },
    )
    assert response.status_code == 201, response.text
    supplier = response.json()
    assert {item["id"] for item in supplier["items"]} == {first["id"], second["id"]}

    response = client.get("/api/suppliers/followup-low-stock")
    assert response.status_code == 200, response.text
    groups = response.json()
    group = next(row for row in groups if row["supplier_id"] == supplier["id"])
    assert {item["status"] for item in group["items"]} == {"MENIPIS", "HABIS"}

    response = client.post(
        f"/api/suppliers/{supplier['id']}/whatsapp",
        json={"stock_item_ids": [first["id"]], "status": "DIBUKA"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["link"].startswith("https://wa.me/6281200001111")
    assert "Barang Supplier A" in body["wa_text"]
    assert body["log"]["supplier_id"] == supplier["id"]
    from database.session import SessionLocal

    with SessionLocal() as db:
        log = db.query(WhatsAppLog).filter_by(supplier_id=supplier["id"]).one()
        assert log.jenis == "supplier"


def test_preview_pesan_supplier_tanpa_jumlah_stok(client):
    item = _stock(client, "Barang Preview", 1, 5)
    supplier = client.post(
        "/api/suppliers",
        json={
            "nama": "Supplier Preview",
            "nomor_hp": "081200002222",
            "stock_item_ids": [item["id"]],
        },
    ).json()
    response = client.post(
        f"/api/suppliers/{supplier['id']}/whatsapp-preview",
        json={"stock_item_ids": [item["id"]]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    text = body["wa_text"].lower()
    assert "barang preview" in text
    assert "sisa" not in text
    assert "minimum" not in text
    assert "harga" in text
    assert "dikirim" in text
    from database.session import SessionLocal

    with SessionLocal() as db:
        assert (
            db.query(WhatsAppLog).filter_by(supplier_id=supplier["id"]).count() == 0
        )


def test_supplier_tanpa_nomor_tidak_bisa_chat(client):
    item = _stock(client, "Barang Tanpa Nomor", 1, 5)
    supplier = client.post(
        "/api/suppliers",
        json={"nama": "Supplier Tanpa HP", "stock_item_ids": [item["id"]]},
    ).json()
    response = client.post(
        f"/api/suppliers/{supplier['id']}/whatsapp",
        json={"status": "DIBUKA"},
    )
    assert response.status_code == 400, response.text


def test_edit_stok_bisa_memilih_supplier(client):
    supplier = client.post(
        "/api/suppliers",
        json={"nama": "Supplier Pilihan Stok", "nomor_hp": "081200001212"},
    ).json()
    item = client.post(
        "/api/stock",
        json={
            "nama": "Barang Pilihan Supplier",
            "harga_modal": "10000",
            "harga_jual": "15000",
            "jumlah": 2,
            "stok_minimum": 5,
            "supplier_ids": [supplier["id"]],
        },
    )
    assert item.status_code == 201, item.text
    stock_id = item.json()["id"]
    rows = client.get("/api/suppliers").json()
    row = next(row for row in rows if row["id"] == supplier["id"])
    assert stock_id in {entry["id"] for entry in row["items"]}

    updated = client.put(
        f"/api/stock/{stock_id}",
        json={"nama": "Barang Pilihan Supplier", "supplier_ids": []},
    )
    assert updated.status_code == 200, updated.text
    rows = client.get("/api/suppliers").json()
    row = next(row for row in rows if row["id"] == supplier["id"])
    assert stock_id not in {entry["id"] for entry in row["items"]}
