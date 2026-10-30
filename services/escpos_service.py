"""Generator layout struk & byte ESC/POS 58mm/80mm.

Ref: PRD BAB 6 & FR-PRN-04 s/d FR-PRN-06.
"""
from __future__ import annotations

import base64
import textwrap
from typing import List, Tuple

from services.utils import format_rupiah, format_short_money, sanitize_ascii

INIT = b"\x1b\x40"
FEED_AND_CUT = b"\n\n\n" + b"\x1d\x56\x42\x00"
ALIGN = {
    "left": b"\x1b\x61\x00",
    "center": b"\x1b\x61\x01",
    "right": b"\x1b\x61\x02",
}

Item = Tuple[str, str, bool, bool]  # text, align, bold, double


class ReceiptBuilder:
    """Menyusun baris teks sekaligus byte perintah ESC/POS."""

    def __init__(self, width: int = 32):
        self.width = width
        self._items: List[Item] = []

    def _columns(self, double: bool) -> int:
        """Double-width memakai dua kolom fisik per karakter."""
        return self.width // 2 if double else self.width

    def _raw(self, line: str, align: str = "left", bold: bool = False, double: bool = False) -> None:
        # Semua baris dijamin <= lebar kertas efektif (Ref: TC-17).
        self._items.append((line[: self._columns(double)], align, bold, double))

    def add(self, text: str = "", align: str = "left", bold: bool = False, double: bool = False) -> None:
        clean = sanitize_ascii(text)
        if not clean:
            self._raw("", align, bold, double)
            return
        for line in textwrap.wrap(
            clean,
            width=self._columns(double),
            break_long_words=True,
            break_on_hyphens=False,
        ):
            self._raw(line, align, bold, double)

    def center(self, text: str, bold: bool = False, double: bool = False) -> None:
        self.add(text, align="center", bold=bold, double=double)

    def divider(self, char: str = "-") -> None:
        self._raw(char * self.width)

    def kv(self, label: str, value: str, bold: bool = False, double: bool = False) -> None:
        left = sanitize_ascii(label)
        right = sanitize_ascii(value)
        limit = self._columns(double)
        if len(left) + len(right) + 1 <= limit:
            self._raw(
                left + " " * (limit - len(left) - len(right)) + right,
                bold=bold,
                double=double,
            )
            return
        for line in textwrap.wrap(left, width=limit) or [""]:
            self._raw(line, bold=bold, double=double)
        self._raw(right, align="right", bold=bold, double=double)

    def field(self, label: str, value: str) -> None:
        prefix = f"{sanitize_ascii(label)}: "
        clean = sanitize_ascii(value)
        available = max(1, self.width - len(prefix))
        chunks = textwrap.wrap(
            clean, width=available, break_long_words=True, break_on_hyphens=False
        ) or [""]
        self._raw(prefix + chunks[0])
        for chunk in chunks[1:]:
            self._raw(" " * len(prefix) + chunk)

    def item(self, name: str, qty: int, price, subtotal) -> None:
        clean_name = sanitize_ascii(name)
        chunks = textwrap.wrap(
            clean_name,
            width=max(1, self.width - 2),
            break_long_words=True,
            break_on_hyphens=False,
        ) or [""]
        self._raw("- " + chunks[0])
        for chunk in chunks[1:]:
            self._raw("  " + chunk)

        left = f"  {qty} x {format_short_money(price)}"
        right = format_short_money(subtotal)
        if len(left) + len(right) + 1 <= self.width:
            self._raw(left + " " * (self.width - len(left) - len(right)) + right)
        else:
            self._raw(left)
            self._raw(right, align="right")

    def lines(self) -> List[str]:
        return [item[0] for item in self._items]

    def to_escpos(self) -> bytes:
        out = bytearray(INIT)
        current_align = None
        current_bold = None
        for text, align, bold, double in self._items:
            if align != current_align:
                out += ALIGN[align]
                current_align = align
            if bold != current_bold:
                out += b"\x1b\x45\x01" if bold else b"\x1b\x45\x00"
                current_bold = bold
            out += (b"\x1d\x21\x01" if double else b"\x1d\x21\x00")
            out += text.encode("ascii", "replace") + b"\n"
        out += FEED_AND_CUT
        return bytes(out)

    def to_base64(self) -> str:
        return base64.b64encode(self.to_escpos()).decode("ascii")


def escpos_from_lines(lines: List[str], width: int = 32) -> bytes:
    """Helper pengujian: bangun byte dari baris teks polos."""
    builder = ReceiptBuilder(width)
    for line in lines:
        builder._raw(sanitize_ascii(line))
    return builder.to_escpos()


def format_lines_for_web(lines: List[str]) -> str:
    return "\n".join(lines)


__all__ = [
    "ReceiptBuilder",
    "escpos_from_lines",
    "format_lines_for_web",
    "format_rupiah",
]
