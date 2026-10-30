"""T-11: idempotensi transaksi lewat request_id."""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

REQUEST_ID = "uji-idempoten-0001"


def _payload(unit_id: int, stock_id: int, qty: int = 1, request_id: str | None = None):
    body = {
        "unit_id": unit_id,
        "keluhan_awal": "Uji idempotensi",
        "metode_bayar": "TRANSFER",
        "jobs": [{"deskripsi": "Korok Radiator", "jumlah": 1, "harga": "150000"}],
        "parts": [
            {
                "stock_item_id": stock_id,
                "nama_part": "",
                "jumlah": qty,
                "harga_satuan": "135000",
            }
        ],
    }
    if request_id is not None:
        body["request_id"] = request_id
    return body


def test_t11_request_id_sama_tidak_menggandakan_nota_dan_stok(
    client, create_customer, create_unit, stock
):
    customer = create_customer(nama="Pelanggan Idempoten", nomor_hp="081200000040")
    unit = create_unit(customer["id"], nopol="B 2040 IDM")
    item = stock("SP-001")
    initial = item["jumlah"]

    first = client.post(
        "/api/pos/transaction",
        json=_payload(unit["id"], item["id"], 2, REQUEST_ID),
    )
    assert first.status_code == 201, first.text
    second = client.post(
        "/api/pos/transaction",
        json=_payload(unit["id"], item["id"], 2, REQUEST_ID),
    )
    assert second.status_code == 201, second.text

    assert second.json()["record"]["id"] == first.json()["record"]["id"]
    assert second.json()["record"]["no_nota"] == first.json()["record"]["no_nota"]
    assert stock("SP-001")["jumlah"] == initial - 2
    assert len(client.get("/api/service-records").json()) == 1


def test_t11_request_id_sama_secara_paralel_hanya_satu_nota(
    client, create_customer, create_unit, stock
):
    customer = create_customer(nama="Pelanggan Race ID", nomor_hp="081200000041")
    unit = create_unit(customer["id"], nopol="B 2041 IDM")
    item = stock("SP-001")
    initial = item["jumlah"]
    barrier = threading.Barrier(2)

    def submit(_index: int):
        barrier.wait(timeout=30)
        try:
            response = client.post(
                "/api/pos/transaction",
                json=_payload(unit["id"], item["id"], 1, "uji-race-id-0001"),
            )
        except Exception:  # noqa: BLE001
            return None
        return response

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(submit, range(2)))

    assert all(response is not None for response in responses)
    assert [response.status_code for response in responses] == [201, 201]
    bodies = [response.json()["record"] for response in responses]
    assert bodies[0]["id"] == bodies[1]["id"]
    assert len(client.get("/api/service-records").json()) == 1
    assert stock("SP-001")["jumlah"] == initial - 1


def test_t11_request_id_berbeda_membuat_nota_baru(
    client, create_customer, create_unit, stock
):
    customer = create_customer(nama="Pelanggan ID Beda", nomor_hp="081200000042")
    unit = create_unit(customer["id"], nopol="B 2042 IDM")
    item = stock("SP-001")

    first = client.post(
        "/api/pos/transaction",
        json=_payload(unit["id"], item["id"], 1, "uji-id-beda-0001"),
    )
    second = client.post(
        "/api/pos/transaction",
        json=_payload(unit["id"], item["id"], 1, "uji-id-beda-0002"),
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["record"]["id"] != second.json()["record"]["id"]
    assert len(client.get("/api/service-records").json()) == 2


def test_t11_request_id_terlalu_pendek_ditolak_tanpa_efek_samping(
    client, create_customer, create_unit, stock
):
    customer = create_customer(nama="Pelanggan ID Pendek", nomor_hp="081200000043")
    unit = create_unit(customer["id"], nopol="B 2043 IDM")
    item = stock("SP-001")
    initial = item["jumlah"]

    response = client.post(
        "/api/pos/transaction",
        json=_payload(unit["id"], item["id"], 1, "pendek"),
    )

    assert response.status_code == 422
    assert stock("SP-001")["jumlah"] == initial
    assert client.get("/api/service-records").json() == []


def test_t11_tanpa_request_id_tetap_kompatibel(
    client, create_customer, create_unit, stock
):
    customer = create_customer(nama="Pelanggan Lama", nomor_hp="081200000044")
    unit = create_unit(customer["id"], nopol="B 2044 IDM")
    item = stock("SP-001")

    first = client.post(
        "/api/pos/transaction", json=_payload(unit["id"], item["id"], 1)
    )
    second = client.post(
        "/api/pos/transaction", json=_payload(unit["id"], item["id"], 1)
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["record"]["id"] != second.json()["record"]["id"]
