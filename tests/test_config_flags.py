"""S-09: flag backup lokal/secret_key yang tidak dipakai tidak boleh menyesatkan."""
from __future__ import annotations

from config import BASE_DIR, settings


def test_setting_tidak_menyediakan_flag_yang_tidak_dipakai():
    assert not hasattr(settings, "auto_backup_enabled")
    assert not hasattr(settings, "secret_key")


def test_env_example_hanya_menjanjikan_backup_telegram():
    text = (BASE_DIR / ".env.example").read_text(encoding="utf-8")
    assert "AUTO_BACKUP_ENABLED" not in text
    assert "SECRET_KEY" not in text
    assert "BACKUP_KEEP" in text
