"""Konfigurasi printer lokal per perangkat.

Disimpan sebagai berkas JSON di samping database (bukan tabel database) agar
identitas perangkat seperti alamat Bluetooth/IP tidak ikut ke berkas backup
yang dapat dibagikan. Isi berkas divalidasi di service ini; frontend tidak
pernah menyimpan angka transaksi di sini.
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import settings
from services.errors import BusinessValidationError
from services.utils import clean_text

VERSION = 1
MAX_PRINTERS = 8

CONNECTION_TYPES = ("BLUETOOTH", "NETWORK", "USB", "SYSTEM", "WEB")
ALLOWED_MODES = {
    "BLUETOOTH": {"ESCPOS", "TEXT"},
    "NETWORK": {"ESCPOS", "TEXT"},
    "USB": {"ESCPOS", "TEXT"},
    "SYSTEM": {"SYSTEM", "TEXT"},
    "WEB": {"BROWSER", "SYSTEM", "TEXT"},
}
DEFAULT_MODES = {
    "BLUETOOTH": "ESCPOS",
    "NETWORK": "ESCPOS",
    "USB": "ESCPOS",
    "SYSTEM": "SYSTEM",
    "WEB": "BROWSER",
}
PAPER_WIDTHS = (58, 80)
STATUSES = ("CONNECTED", "SAVED", "UNAVAILABLE", "CONNECTING", "ERROR")
# Status ini hanya berlaku selama koneksi hidup. Setelah aplikasi dibuka
# ulang, printer tidak boleh tampil "Terhubung" tanpa koneksi nyata.
LIVE_STATUSES = ("CONNECTED", "CONNECTING")

_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_BT_ADDRESS_PATTERN = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
_ENCODING_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,32}$")

_lock = threading.Lock()


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _parse_timestamp(value: Any, message: str) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BusinessValidationError(message) from exc
    return text


def _path() -> Path:
    return Path(settings.printer_config_path)


def empty_config(warning: Optional[str] = None) -> Dict[str, Any]:
    return {
        "version": VERSION,
        "printers": [],
        "primary_id": None,
        "updated_at": None,
        "warning": warning,
    }


def _normalize_stored(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("konfigurasi bukan objek")
    printers = raw.get("printers")
    if not isinstance(printers, list):
        raise ValueError("daftar printer tidak valid")
    primary_id = raw.get("primary_id")
    if primary_id is not None and not isinstance(primary_id, str):
        raise ValueError("printer utama tidak valid")

    clean: List[Dict[str, Any]] = []
    for item in printers:
        if not isinstance(item, dict):
            raise ValueError("data printer tidak valid")
        printer = dict(item)
        status = str(printer.get("last_status") or "SAVED").upper()
        if status in LIVE_STATUSES:
            status = "SAVED"
        printer["last_status"] = status
        clean.append(printer)

    return {
        "version": VERSION,
        "printers": clean,
        "primary_id": primary_id or None,
        "updated_at": raw.get("updated_at") or None,
        "warning": None,
    }


def get_printer_config() -> Dict[str, Any]:
    """Baca konfigurasi; berkas rusak tidak boleh mematikan aplikasi."""
    path = _path()
    if not path.exists():
        return empty_config()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return _normalize_stored(raw)
    except (OSError, ValueError):
        return empty_config(
            warning=(
                "Konfigurasi printer tidak dapat dibaca. Silakan atur ulang "
                "printer di Pengaturan."
            )
        )


def _clean_printer(
    item: Dict[str, Any],
    existing: Optional[Dict[str, Any]],
    now: str,
) -> Dict[str, Any]:
    printer_id = clean_text(item.get("id"), max_length=64, allow_newlines=False)
    if not _ID_PATTERN.match(printer_id):
        raise BusinessValidationError(
            "ID printer hanya boleh berisi huruf, angka, titik, garis bawah, "
            "atau tanda hubung (maksimal 64 karakter)."
        )

    name = clean_text(item.get("name"), max_length=80, allow_newlines=False)
    if not name:
        raise BusinessValidationError("Nama printer wajib diisi (maksimal 80 karakter).")

    connection_type = clean_text(
        item.get("connection_type"), max_length=16, allow_newlines=False
    ).upper()
    if connection_type not in CONNECTION_TYPES:
        raise BusinessValidationError(
            "Jenis koneksi printer harus BLUETOOTH, NETWORK, USB, SYSTEM, atau WEB."
        )

    paper_width = item.get("paper_width")
    if isinstance(paper_width, bool) or paper_width not in PAPER_WIDTHS:
        raise BusinessValidationError("Lebar kertas printer harus 58 mm atau 80 mm.")

    print_mode = clean_text(
        item.get("print_mode"), max_length=16, allow_newlines=False
    ).upper()
    if not print_mode:
        print_mode = DEFAULT_MODES[connection_type]
    if print_mode not in ALLOWED_MODES[connection_type]:
        raise BusinessValidationError(
            "Mode cetak tidak sesuai untuk jenis koneksi printer ini."
        )

    encoding = clean_text(
        item.get("encoding"), max_length=32, allow_newlines=False
    ).upper()
    if not encoding:
        encoding = settings.printer_encoding.upper()
    if not _ENCODING_PATTERN.match(encoding):
        raise BusinessValidationError("Encoding printer tidak valid.")

    last_status = clean_text(
        item.get("last_status") or "SAVED", max_length=16, allow_newlines=False
    ).upper()
    if last_status not in STATUSES:
        raise BusinessValidationError("Status printer tidak dikenal.")

    address = clean_text(item.get("address"), max_length=255, allow_newlines=False)
    ip = clean_text(item.get("ip"), max_length=255, allow_newlines=False)
    port = item.get("port")
    if isinstance(port, bool):
        port = None

    if connection_type == "BLUETOOTH":
        if not address:
            raise BusinessValidationError(
                "Alamat Bluetooth printer wajib diisi (contoh AA:BB:CC:DD:EE:FF)."
            )
        if not _BT_ADDRESS_PATTERN.match(address):
            raise BusinessValidationError(
                "Format alamat Bluetooth tidak valid (contoh AA:BB:CC:DD:EE:FF)."
            )
        ip, port = "", None
    elif connection_type == "NETWORK":
        if not ip:
            raise BusinessValidationError("IP printer Wi-Fi/LAN wajib diisi.")
        try:
            ipaddress.ip_address(ip)
        except ValueError as exc:
            raise BusinessValidationError(
                "IP printer Wi-Fi/LAN tidak valid (contoh 192.168.1.9)."
            ) from exc
        if port in (None, ""):
            raise BusinessValidationError(
                "Port printer Wi-Fi/LAN wajib diisi (umumnya 9100)."
            )
        if isinstance(port, str) and port.strip().isdigit():
            port = int(port.strip())
        if not isinstance(port, int) or not 1 <= port <= 65535:
            raise BusinessValidationError("Port printer harus 1-65535.")
        address = ""
    elif connection_type == "USB":
        if not address:
            raise BusinessValidationError(
                "Identitas perangkat USB printer wajib diisi."
            )
        ip, port = "", None
    else:  # SYSTEM / WEB tidak memakai alamat perangkat
        address, ip, port = "", "", None

    last_connected_at = _parse_timestamp(
        item.get("last_connected_at"),
        "Waktu koneksi terakhir printer tidak valid.",
    )
    last_error = clean_text(
        item.get("last_error"), max_length=300, allow_newlines=False
    )

    created_at = (existing or {}).get("created_at") or now
    return {
        "id": printer_id,
        "name": name,
        "connection_type": connection_type,
        "paper_width": paper_width,
        "print_mode": print_mode,
        "encoding": encoding,
        "address": address,
        "ip": ip,
        "port": port,
        "last_status": last_status,
        "last_connected_at": last_connected_at,
        "last_error": last_error or None,
        "created_at": created_at,
        "updated_at": now,
    }


def _identity(printer: Dict[str, Any]) -> str:
    connection_type = printer["connection_type"]
    if connection_type in ("BLUETOOTH", "USB"):
        return f"{connection_type}:{printer['address'].upper()}"
    if connection_type == "NETWORK":
        return f"NETWORK:{printer['ip']}:{printer['port']}"
    return f"{connection_type}:{printer['id']}"


def update_printer_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Ganti seluruh konfigurasi printer setelah validasi ketat.

    Menghapus printer hanya menghapus konfigurasinya; data transaksi tidak
    pernah disentuh oleh fungsi ini.
    """
    items = payload.get("printers")
    if not isinstance(items, list):
        raise BusinessValidationError("Daftar printer tidak valid.")
    if len(items) > MAX_PRINTERS:
        raise BusinessValidationError(
            f"Maksimal {MAX_PRINTERS} printer dapat disimpan."
        )

    current = get_printer_config()
    existing_by_id = {item.get("id"): item for item in current["printers"]}
    now = _now_iso()

    cleaned: List[Dict[str, Any]] = []
    seen_ids = set()
    seen_identities = set()
    for item in items:
        if not isinstance(item, dict):
            raise BusinessValidationError("Data printer tidak valid.")
        printer = _clean_printer(item, existing_by_id.get(item.get("id")), now)
        printer_id = printer["id"]
        if printer_id in seen_ids:
            raise BusinessValidationError(
                f"ID printer duplikat: {printer_id}."
            )
        identity = _identity(printer)
        if identity in seen_identities:
            raise BusinessValidationError(
                "Printer duplikat: perangkat yang sama tercatat lebih dari sekali."
            )
        seen_ids.add(printer_id)
        seen_identities.add(identity)
        cleaned.append(printer)

    primary_id = payload.get("primary_id") or None
    if primary_id is not None:
        if not isinstance(primary_id, str) or primary_id not in seen_ids:
            raise BusinessValidationError(
                "Printer utama yang dipilih tidak ditemukan pada daftar."
            )

    result = {
        "version": VERSION,
        "printers": cleaned,
        "primary_id": primary_id,
        "updated_at": now,
        "warning": None,
    }
    _write(result)
    return result


def _write(config: Dict[str, Any]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    directory = str(path.parent)
    fd, temp_name = tempfile.mkstemp(
        dir=directory, prefix=".printer_", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(config, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(temp_name, 0o600)
        except OSError:
            pass
        with _lock:
            os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


__all__ = [
    "MAX_PRINTERS",
    "empty_config",
    "get_printer_config",
    "update_printer_config",
]
