"""Exception domain bisnis (dipetakan ke status HTTP oleh api/app.py)."""
from __future__ import annotations

from typing import Any, Dict, List


class DomainError(Exception):
    """Kesalahan bisnis umum."""


class NotFoundError(DomainError):
    """Entitas yang diminta tidak ditemukan."""


class BusinessValidationError(DomainError):
    """Input tidak lolos validasi aturan bisnis."""


class ConflictError(DomainError):
    """Konflik data (duplikat / status tidak valid)."""


class AuthenticationError(DomainError):
    """Sesi atau PIN tidak valid."""


class RateLimitError(DomainError):
    """Terlalu banyak percobaan; pengguna harus menunggu jeda."""

    def __init__(self, retry_after: int):
        self.retry_after = max(1, int(retry_after))
        super().__init__(
            f"Terlalu banyak percobaan PIN. Coba lagi dalam "
            f"{self.retry_after} detik."
        )


class PaymentError(BusinessValidationError):
    """Nominal pembayaran tidak valid."""


class WarrantyError(BusinessValidationError):
    """Klaim garansi tidak dapat diproses."""


class InsufficientStockError(DomainError):
    """Stok gudang tidak mencukupi untuk transaksi."""

    def __init__(self, items: List[Dict[str, Any]]):
        self.items = items
        names = ", ".join(str(item.get("nama")) for item in items)
        super().__init__(
            f"Stok gudang tidak mencukupi untuk: {names}. "
            "Konfirmasi transaksi untuk tetap menyimpan dengan stok minus."
        )
