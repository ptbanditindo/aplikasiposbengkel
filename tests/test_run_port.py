"""ARC-12: `run.py --port` harus menjadi port yang dilayani dan diizinkan."""
from __future__ import annotations

import os
import sys

import pytest

import run
from config import effective_app_port, set_runtime_port


def test_run_port_override_dipakai_uvicorn_dan_guard(monkeypatch):
    captured = {}

    def fake_run(app, **kwargs):
        captured["app"] = app
        captured["kwargs"] = kwargs

    monkeypatch.setattr(run.uvicorn, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["run.py", "--port", "8011"])
    original_port = os.environ.get("APP_PORT")
    try:
        run.main()
        assert captured["kwargs"]["host"] == "127.0.0.1"
        assert captured["kwargs"]["port"] == 8011
        assert effective_app_port() == 8011
        assert os.environ["APP_PORT"] == "8011"
    finally:
        set_runtime_port(None)
        if original_port is None:
            os.environ.pop("APP_PORT", None)
        else:
            os.environ["APP_PORT"] = original_port


def test_run_menolak_host_non_loopback(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["run.py", "--host", "0.0.0.0"])
    called = {"run": False}

    def fake_run(app, **kwargs):
        called["run"] = True

    monkeypatch.setattr(run.uvicorn, "run", fake_run)
    with pytest.raises(SystemExit):
        run.main()
    assert called["run"] is False
