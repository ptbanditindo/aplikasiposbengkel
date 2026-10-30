"""K-02: web lokal hanya dari PC ini, ber-PIN, tanpa dokumentasi terbuka."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import func, select

from api import (
    customer_routes,
    pos_routes,
    report_routes,
    settings_routes,
    stock_routes,
)
from api.app import app  # noqa: F401  (memastikan validasi runtime & wiring diimpor)
from config import settings, validate_runtime
from database.models import AppSetting, Customer
from database.session import SessionLocal, engine


def _clear_pin():
    with SessionLocal() as db:
        db.query(AppSetting).filter(AppSetting.key.like("auth.%")).delete(
            synchronize_session=False
        )
        db.commit()


def _api_routes():
    routers = (
        customer_routes.router,
        pos_routes.router,
        report_routes.router,
        settings_routes.router,
        stock_routes.router,
    )
    for router in routers:
        for route in router.routes:
            path = getattr(route, "path", "")
            methods = getattr(route, "methods", None) or set()
            method = next(
                (item for item in ("POST", "PUT", "DELETE", "GET") if item in methods),
                None,
            )
            if method and path:
                yield method, "/api" + path


def test_app_host_non_loopback_ditolak():
    with pytest.raises(RuntimeError) as exc:
        validate_runtime(replace(settings, app_host="0.0.0.0"))
    assert "127.0.0.1" in str(exc.value)


def test_auth_mode_tidak_dikenal_ditolak():
    with pytest.raises(RuntimeError):
        validate_runtime(replace(settings, auth_mode="buka-saja"))


def test_dokumentasi_dan_openapi_dimatikan(client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404, path


def test_health_tetap_terbuka(anon_client):
    response = anon_client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_semua_route_api_menolak_tanpa_sesi(anon_client):
    checked = 0
    for method, path in _api_routes():
        url = path.replace("{stock_id}", "1")
        url = url.replace("{jasa_id}", "1")
        url = url.replace("{record_id}", "1")
        url = url.replace("{customer_id}", "1")
        response = anon_client.request(method, url, json={})
        assert response.status_code == 401, (method, url, response.status_code)
        checked += 1
    assert checked >= 20


def test_host_asing_ditolak(anon_client):
    foreign = anon_client.get("/api/health", headers={"Host": "evil.example:8000"})
    assert foreign.status_code == 400

    wrong_port = anon_client.get("/api/health", headers={"Host": "127.0.0.1:9999"})
    assert wrong_port.status_code == 400


def test_origin_asing_pada_request_tulis_ditolak(anon_client):
    foreign = anon_client.post(
        "/api/auth/logout", headers={"Origin": "https://jahat.example"}
    )
    assert foreign.status_code == 403

    allowed = anon_client.post(
        "/api/auth/logout", headers={"Origin": "http://127.0.0.1:8000"}
    )
    assert allowed.status_code == 200


def test_setup_pin_dan_login_memakai_cookie_sesi(anon_client):
    _clear_pin()
    status = anon_client.get("/api/auth/status").json()
    assert status["mode"] == "session-pin"
    assert status["pin_configured"] is False

    weak = anon_client.post("/api/auth/setup", json={"pin": "12"})
    assert weak.status_code == 422

    letters = anon_client.post("/api/auth/setup", json={"pin": "abcdef"})
    assert letters.status_code == 400

    setup = anon_client.post("/api/auth/setup", json={"pin": "2468"})
    assert setup.status_code == 201, setup.text
    cookie = setup.headers.get("set-cookie", "").lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie

    assert anon_client.get("/api/stock").status_code == 200

    assert anon_client.post("/api/auth/logout").status_code == 200
    assert anon_client.get("/api/stock").status_code == 401

    wrong = anon_client.post("/api/auth/login", json={"pin": "9999"})
    assert wrong.status_code == 401

    login = anon_client.post("/api/auth/login", json={"pin": "2468"})
    assert login.status_code == 200, login.text
    assert anon_client.get("/api/stock").status_code == 200


def test_percobaan_pin_salah_dibatasi(anon_client):
    _clear_pin()
    assert anon_client.post("/api/auth/setup", json={"pin": "2468"}).status_code == 201

    for attempt in range(4):
        response = anon_client.post("/api/auth/login", json={"pin": "0000"})
        assert response.status_code == 401, attempt

    fifth = anon_client.post("/api/auth/login", json={"pin": "0000"})
    assert fifth.status_code == 429
    assert fifth.headers.get("retry-after")
    assert "Coba lagi" in fifth.json()["detail"]

    locked = anon_client.post("/api/auth/login", json={"pin": "2468"})
    assert locked.status_code == 429


def test_reset_pin_hanya_menghapus_kredensial(client):
    from reset_pin import clear_pin

    created = client.post(
        "/api/customers",
        json={"nama": "Pelanggan Tetap", "nomor_hp": "081200001111"},
    )
    assert created.status_code == 201, created.text

    deleted = clear_pin(Path(engine.url.database))
    assert deleted >= 3

    with SessionLocal() as db:
        keys = db.scalars(select(AppSetting.key)).all()
        assert not any(key.startswith("auth.") for key in keys)
        assert db.scalar(select(func.count()).select_from(Customer)) == 1
