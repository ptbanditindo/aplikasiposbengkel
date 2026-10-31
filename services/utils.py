"""Utilitas teks & angka bersama."""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

TWOPLACES = Decimal("0.01")

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SPACES = re.compile(r"\s+")


def clean_text(value: Any, *, max_length: int | None = None, allow_newlines: bool = True) -> str:
    """Bersihkan karakter kontrol & rapikan spasi (bukan escape HTML)."""
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_CHARS.sub("", text)
    if not allow_newlines:
        text = text.replace("\n", " ").replace("\t", " ")
        text = _SPACES.sub(" ", text)
    if max_length is not None:
        text = text[:max_length]
    return text.strip()


def sanitize_ascii(value: Any) -> str:
    """Sanitasi teks untuk printer thermal: ASCII murni, emoji dibuang.

    Ref: PROMPT_AUDIT FASE 5.2.
    """
    text = clean_text(value, allow_newlines=False)
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return _SPACES.sub(" ", ascii_text).strip()


def to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value))


def money(value: Any) -> Decimal:
    """Kuantisasi 2 desimal (half-up) untuk seluruh nominal uang."""
    return to_decimal(value).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def format_rupiah(value: Any) -> str:
    amount = money(value)
    negative = amount < 0
    absolute = abs(amount)
    text = f"{absolute:,.2f}"
    if text.endswith(".00"):
        text = text[:-3]
    text = text.replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-Rp " if negative else "Rp ") + text


def format_short_money(value: Any) -> str:
    """Nominal tanpa prefix Rp untuk kolom struk thermal yang sempit."""
    return format_rupiah(value).replace("Rp ", "")


def normalize_phone(raw: Any) -> str:
    """Normalisasi nomor HP: 0812-3456-7890 / +62 812... -> 081234567890."""
    digits = re.sub(r"\D", "", str(raw or ""))
    if digits.startswith("62"):
        digits = "0" + digits[2:]
    elif digits.startswith("8"):
        digits = "0" + digits
    return digits


def normalize_whatsapp(raw: Any) -> str:
    """Normalisasi nomor WhatsApp: 08… / 8… / +62… menjadi 628…."""
    digits = re.sub(r"\D", "", str(raw or ""))
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    elif digits.startswith("8"):
        digits = "62" + digits
    elif digits.startswith("620"):
        digits = "62" + digits[3:]
    return digits


def is_valid_whatsapp(raw: Any) -> bool:
    digits = normalize_whatsapp(raw)
    return digits.startswith("62") and 10 <= len(digits) <= 15


def mask_phone(raw: Any) -> str:
    digits = re.sub(r"\D", "", str(raw or ""))
    if len(digits) <= 7:
        return "****"
    return digits[:4] + "****" + digits[-3:]


def normalize_nopol(raw: Any) -> str:
    """Normalisasi nopol: 'b 1234 abc' -> 'B 1234 ABC'."""
    text = str(raw or "").upper()
    text = re.sub(r"[^A-Z0-9 ]", " ", text)
    return _SPACES.sub(" ", text).strip()
