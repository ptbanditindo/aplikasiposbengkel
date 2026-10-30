"""Dependency FastAPI: proteksi endpoint admin dengan token lokal."""
from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status

from config import settings


def require_admin_token(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    """Ref: PROMPT_AUDIT FASE 1.3 - endpoint sensitif wajib token.

    Token tidak pernah dibandingkan dengan `==` biasa agar tidak bocor lewat
    timing attack. Bila server belum dikonfigurasi, endpoint sensitif ditutup
    total (fail-closed) alih-alih terbuka tanpa autentikasi.
    """
    expected = settings.ui_access_token.strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Token admin belum dikonfigurasi di server. "
                "Set UI_ACCESS_TOKEN pada berkas .env lalu jalankan ulang aplikasi."
            ),
        )

    provided = (x_admin_token or "").strip()
    if not provided or not hmac.compare_digest(
        provided.encode("utf-8", "ignore"), expected.encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token admin tidak valid atau belum diisi.",
        )
