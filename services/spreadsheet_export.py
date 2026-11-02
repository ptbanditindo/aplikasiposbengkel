"""Ekspor data SQLite ke Excel/CSV untuk backup yang mudah dibaca.

Berkas hasil ekspor bukan berkas pemulihan. Pemulihan tetap memakai backup
database SQLite (`.db`). Rahasia autentikasi dan Telegram diredaksi.
"""
from __future__ import annotations

import base64
import csv
import io
import re
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

from openpyxl import Workbook

# Karakter yang ditolak Excel/openpyxl. Tab, newline, dan carriage return tetap
# dipertahankan karena masih sah di dalam sel.
ILLEGAL_XML_CHARS = re.compile(r"[\000-\010\013\014\016-\037]")
INVALID_SHEET_CHARS = re.compile(r"[\\/*?:\[\]]")
MAX_CELL_CHARS = 32767
MAX_DATA_ROWS = 1_048_575


class SpreadsheetLimitError(ValueError):
    """Data terlalu besar untuk satu lembar Excel."""


def _sanitize_text(value: object) -> str:
    text = ILLEGAL_XML_CHARS.sub("", str(value))
    if len(text) > MAX_CELL_CHARS:
        text = text[: MAX_CELL_CHARS - 16] + " ... [dipotong]"
    return text


def _cell_value(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, bytes):
        return "base64:" + base64.b64encode(value).decode("ascii")
    if isinstance(value, str):
        return _sanitize_text(value)
    return value


def _csv_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return "base64:" + base64.b64encode(value).decode("ascii")
    if isinstance(value, str):
        return ILLEGAL_XML_CHARS.sub("", value)
    return value


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _read_tables(connection: sqlite3.Connection) -> list[tuple[str, list[str]]]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    tables: list[tuple[str, list[str]]] = []
    for (name,) in rows:
        columns = [
            row[1]
            for row in connection.execute(
                f"PRAGMA table_info({_quote(str(name))})"
            ).fetchall()
        ]
        if columns:
            tables.append((str(name), columns))
    return tables


def _table_rows(
    connection: sqlite3.Connection,
    table: str,
    columns: Sequence[str],
    redacted_settings: set[str],
) -> Iterable[tuple[object, ...]]:
    is_settings = table == "app_settings"
    key_index = columns.index("key") if is_settings and "key" in columns else None
    value_index = (
        columns.index("value") if is_settings and "value" in columns else None
    )
    query = f"SELECT * FROM {_quote(table)}"
    for row in connection.execute(query):
        if key_index is not None and value_index is not None:
            key = str(row[key_index] or "")
            if (
                key.startswith("auth.")
                or key in redacted_settings
                or key == "telegram.pending_backup_path"
            ):
                row = list(row)
                row[value_index] = ""
                row = tuple(row)
        yield tuple(_cell_value(value) for value in row)


def _unique_sheet_name(raw: str, used: set[str]) -> str:
    name = INVALID_SHEET_CHARS.sub("_", raw).strip() or "Sheet"
    name = name[:31]
    candidate = name
    suffix = 2
    while candidate.lower() in used:
        tail = f"_{suffix}"
        candidate = name[: 31 - len(tail)] + tail
        suffix += 1
    used.add(candidate.lower())
    return candidate


def _info_rows(created_at: datetime, table_counts: list[tuple[str, int]]):
    yield ("Keterangan", "Nilai")
    yield ("Dibuat", created_at.strftime("%Y-%m-%d %H:%M:%S"))
    yield ("Aplikasi", "BengkelPOS Radiator")
    yield ("Format", "Excel (.xlsx)")
    yield (
        "Pemulihan",
        "Bukan berkas pemulihan. Gunakan backup database (.db) untuk memulihkan.",
    )
    yield (
        "Rahasia",
        "PIN, sesi, dan token Telegram tidak disertakan dalam berkas ini.",
    )
    yield ("", "")
    yield ("Tabel", "Jumlah baris")
    for table, count in table_counts:
        yield (table, count)


def write_xlsx(
    source_path: Path,
    destination: Path,
    redacted_settings: set[str],
) -> None:
    """Tulis seluruh tabel database ke satu workbook, satu lembar per tabel."""
    created_at = datetime.now()
    connection = sqlite3.connect(str(source_path))
    try:
        tables = _read_tables(connection)
        counts: list[tuple[str, int]] = []
        for table, _columns in tables:
            count = connection.execute(
                f"SELECT COUNT(*) FROM {_quote(table)}"
            ).fetchone()[0]
            counts.append((table, int(count or 0)))

        workbook = Workbook(write_only=True)
        info = workbook.create_sheet("Info")
        for row in _info_rows(created_at, counts):
            info.append(list(row))

        used = {"info"}
        for table, columns in tables:
            count = dict(counts)[table]
            if count > MAX_DATA_ROWS:
                raise SpreadsheetLimitError(
                    f"Tabel {table} berisi {count} baris, melebihi batas Excel. "
                    "Pilih format CSV."
                )
            sheet = workbook.create_sheet(_unique_sheet_name(table, used))
            sheet.append([_sanitize_text(column) for column in columns])
            for row in _table_rows(connection, table, columns, redacted_settings):
                sheet.append(list(row))
        workbook.save(destination)
    finally:
        connection.close()


def _csv_bytes(
    connection: sqlite3.Connection,
    table: str,
    columns: Sequence[str],
    redacted_settings: set[str],
) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([_sanitize_text(column) for column in columns])
    for row in _table_rows(connection, table, columns, redacted_settings):
        writer.writerow([_csv_value(value) for value in row])
    # BOM agar Excel di Windows membaca UTF-8 dengan benar.
    return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")


def write_csv_zip(
    source_path: Path,
    destination: Path,
    redacted_settings: set[str],
) -> None:
    """Tulis seluruh tabel ke ZIP berisi satu CSV per tabel + Info.txt."""
    created_at = datetime.now()
    connection = sqlite3.connect(str(source_path))
    try:
        tables = _read_tables(connection)
        counts: list[tuple[str, int]] = []
        for table, _columns in tables:
            count = connection.execute(
                f"SELECT COUNT(*) FROM {_quote(table)}"
            ).fetchone()[0]
            counts.append((table, int(count or 0)))

        used: set[str] = set()
        info_lines = [
            "BengkelPOS Radiator - ekspor spreadsheet",
            f"Dibuat: {created_at:%Y-%m-%d %H:%M:%S}",
            "Format: CSV (.zip), satu berkas per tabel",
            "Bukan berkas pemulihan. Gunakan backup database (.db) untuk memulihkan.",
            "PIN, sesi, dan token Telegram tidak disertakan.",
            "",
            "Tabel, jumlah baris:",
        ]
        info_lines.extend(f"{table}, {count}" for table, count in counts)

        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("Info.txt", "\n".join(info_lines).encode("utf-8"))
            for table, columns in tables:
                file_name = _unique_sheet_name(table, used) + ".csv"
                archive.writestr(
                    file_name,
                    _csv_bytes(connection, table, columns, redacted_settings),
                )
    finally:
        connection.close()


__all__ = ["SpreadsheetLimitError", "write_csv_zip", "write_xlsx"]
