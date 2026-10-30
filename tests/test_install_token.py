"""T-10: token per-instalasi APK untuk semua endpoint /api."""
from __future__ import annotations

from dataclasses import replace

import pytest

import api.auth_routes as auth_routes
import api.deps as deps
from config import settings

INSTALL_TOKEN = "uji-install-token-0123456789abcdef"
HEADERS = {"X-Install-Token": INSTALL_TOKEN}


@pytest.fixture()
def install_mode(monkeypatch):
    runtime = replace(
        settings,
        auth_mode="install-token",
        app_install_token=INSTALL_TOKEN,
    )
    monkeypatch.setattr(deps, "settings", runtime)
    monkeypatch.setattr(auth_routes, "settings", runtime)
    return HEADERS


def test_tanpa_token_ditolak(install_mode, anon_client):
    assert anon_client.get("/api/config").status_code == 401
    assert anon_client.get("/api/stock").status_code == 401
    response = anon_client.post("/api/customers", json={"nama": "Tanpa Token"})
    assert response.status_code == 401


def test_token_salah_ditolak(install_mode, anon_client):
    wrong = {"X-Install-Token": "token-palsu"}
    assert anon_client.get("/api/config", headers=wrong).status_code == 401


def test_sesi_pin_web_tidak_berlaku_di_mode_apk(install_mode, client):
    # `client` memegang cookie sesi PIN dari fixture; mode APK tetap butuh token.
    assert client.get("/api/config").status_code == 401


def test_token_benar_membuka_baca_dan_tulis(install_mode, anon_client):
    assert anon_client.get("/api/config", headers=install_mode).status_code == 200
    created = anon_client.post(
        "/api/customers",
        json={"nama": "Pelanggan APK", "nomor_hp": "081200000088"},
        headers=install_mode,
    )
    assert created.status_code == 201, created.text
    assert anon_client.get("/api/stock", headers=install_mode).status_code == 200


def test_health_tetap_terbuka(install_mode, anon_client):
    assert anon_client.get("/api/health").status_code == 200


def test_token_kosong_fail_closed(monkeypatch, anon_client):
    runtime = replace(settings, auth_mode="install-token", app_install_token="")
    monkeypatch.setattr(deps, "settings", runtime)
    assert anon_client.get("/api/config").status_code == 401
    assert (
        anon_client.get(
            "/api/config", headers={"X-Install-Token": ""}
        ).status_code
        == 401
    )


def test_mode_apk_tanpa_layar_pin_web(install_mode, anon_client):
    body = anon_client.get("/api/auth/status").json()
    assert body["mode"] == "install-token"
    assert body["authenticated"] is False
    assert anon_client.post("/api/auth/setup", json={"pin": "2468"}).status_code == 404
    assert anon_client.post("/api/auth/login", json={"pin": "2468"}).status_code == 404
