"""Registry toko lokal: daftar toko, toko aktif, dan database_id.

Registry berupa JSON kecil di folder data. Setiap toko menunjuk ke satu berkas
SQLite sendiri. Registry bukan data transaksi; bila rusak, entri utama dibuat
ulang dari `DATABASE_URL` dan toko tambahan yang berkasnya masih ada tetap
didaftarkan ulang secara manual.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import secrets
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import BASE_DIR, settings

logger = logging.getLogger(__name__)

REGISTRY_VERSION = 1
PRIMARY_STORE_ID = "utama"
PLANS = ("free", "premium")
_ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

_lock = threading.RLock()
_cached: Optional[Dict[str, Any]] = None
_cached_mtime_ns: int = -1


def _main_db_path() -> Optional[Path]:
    prefix = "sqlite:///"
    if not settings.database_url.startswith(prefix) or ":memory:" in settings.database_url:
        return None
    raw = settings.database_url[len(prefix):]
    path = Path(raw)
    if not path.is_absolute():
        path = (BASE_DIR / raw).resolve()
    return path


def data_root() -> Path:
    main = _main_db_path()
    if main is None:
        raise RuntimeError("Multi-toko hanya tersedia untuk database SQLite berkas.")
    return main.parent


def stores_dir() -> Path:
    return data_root() / "stores"


def registry_path() -> Path:
    return stores_dir() / "registry.json"


def _relative_database_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(data_root().resolve()).as_posix()
    except ValueError as exc:
        raise RuntimeError("Berkas toko harus berada di folder data aplikasi.") from exc


def resolve_database_path(entry: Dict[str, Any]) -> Path:
    raw = str(entry.get("database_path") or "").strip()
    if not raw:
        raise RuntimeError("Entri toko tidak memiliki berkas database.")
    path = (data_root() / raw).resolve()
    root = data_root().resolve()
    if path != root and root not in path.parents:
        raise RuntimeError("Berkas toko berada di luar folder data aplikasi.")
    return path


def new_ulid(now: Optional[float] = None) -> str:
    """ULID sederhana: 10 karakter waktu + 16 karakter acak Crockford."""
    milliseconds = int((now if now is not None else time.time()) * 1000)
    stamp = ""
    for _ in range(10):
        stamp = _ULID_ALPHABET[milliseconds & 31] + stamp
        milliseconds >>= 5
    return stamp + "".join(secrets.choice(_ULID_ALPHABET) for _ in range(16))


def _primary_entry() -> Dict[str, Any]:
    main = _main_db_path()
    if main is None:
        raise RuntimeError("Multi-toko hanya tersedia untuk database SQLite berkas.")
    return {
        "store_id": PRIMARY_STORE_ID,
        "database_id": "",
        "nama": settings.bengkel_nama,
        "alamat": settings.bengkel_alamat,
        "database_path": _relative_database_path(main),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def _default_registry() -> Dict[str, Any]:
    return {
        "version": REGISTRY_VERSION,
        "plan": settings.entitlement_plan,
        "active_store_id": PRIMARY_STORE_ID,
        "stores": [_primary_entry()],
    }


def _valid_plan(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in PLANS else settings.entitlement_plan


def _normalize(data: Dict[str, Any]) -> Dict[str, Any]:
    stores = data.get("stores")
    if not isinstance(stores, list):
        raise ValueError("stores bukan daftar")
    normalized: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for item in stores:
        if not isinstance(item, dict):
            continue
        store_id = str(item.get("store_id") or "").strip()
        database_path = str(item.get("database_path") or "").strip()
        if not store_id or not database_path or store_id in seen:
            continue
        seen.add(store_id)
        normalized.append(
            {
                "store_id": store_id,
                "database_id": str(item.get("database_id") or "").strip(),
                "nama": str(item.get("nama") or "").strip(),
                "alamat": str(item.get("alamat") or "").strip(),
                "database_path": database_path,
                "created_at": str(item.get("created_at") or ""),
            }
        )
    if not any(row["store_id"] == PRIMARY_STORE_ID for row in normalized):
        normalized.insert(0, _primary_entry())

    active = str(data.get("active_store_id") or "").strip()
    if active not in {row["store_id"] for row in normalized}:
        active = PRIMARY_STORE_ID
    return {
        "version": REGISTRY_VERSION,
        "plan": _valid_plan(data.get("plan")),
        "active_store_id": active,
        "stores": normalized,
    }


def _read_from_disk() -> Optional[Dict[str, Any]]:
    path = registry_path()
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("registry bukan objek")
        return _normalize(raw)
    except (OSError, ValueError) as exc:
        logger.warning("Registry toko rusak (%s); membuat ulang entri utama.", exc)
        backup = path.with_name(
            f"registry.rusak-{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        try:
            path.replace(backup)
        except OSError:
            pass
        return None


def _write(data: Dict[str, Any]) -> Dict[str, Any]:
    stores_dir().mkdir(parents=True, exist_ok=True)
    path = registry_path()
    temporary = path.with_name(path.name + ".new")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(str(temporary), str(path))
    global _cached, _cached_mtime_ns
    _cached = copy.deepcopy(data)
    try:
        _cached_mtime_ns = path.stat().st_mtime_ns
    except OSError:
        _cached_mtime_ns = -1
    return copy.deepcopy(data)


def _load() -> Dict[str, Any]:
    global _cached, _cached_mtime_ns
    with _lock:
        path = registry_path()
        try:
            mtime = path.stat().st_mtime_ns
        except OSError:
            mtime = -1
        if _cached is not None and mtime == _cached_mtime_ns:
            return copy.deepcopy(_cached)

        data = _read_from_disk()
        if data is None:
            data = _default_registry()
        _cached = copy.deepcopy(data)
        _cached_mtime_ns = mtime
        if not path.exists():
            _write(data)
        return copy.deepcopy(data)


def ensure_registry() -> Dict[str, Any]:
    return _load()


def get_plan() -> str:
    return _load()["plan"]


def set_plan(plan: str) -> str:
    value = str(plan or "").strip().lower()
    if value not in PLANS:
        raise ValueError("Paket harus free atau premium.")
    with _lock:
        data = _load()
        data["plan"] = value
        _write(data)
    return value


def list_stores(include_missing: bool = False) -> List[Dict[str, Any]]:
    data = _load()
    rows = []
    for entry in data["stores"]:
        try:
            exists = resolve_database_path(entry).exists()
        except RuntimeError:
            exists = False
        if exists or include_missing:
            row = dict(entry)
            row["tersedia"] = exists
            row["active"] = entry["store_id"] == data["active_store_id"]
            rows.append(row)
    return rows


def get_store(store_id: str) -> Optional[Dict[str, Any]]:
    for entry in _load()["stores"]:
        if entry["store_id"] == store_id:
            return dict(entry)
    return None


def active_store() -> Dict[str, Any]:
    with _lock:
        data = _load()
        entry = next(
            (
                row
                for row in data["stores"]
                if row["store_id"] == data["active_store_id"]
            ),
            None,
        )
        if entry is None:
            data["active_store_id"] = PRIMARY_STORE_ID
            entry = next(
                row for row in data["stores"] if row["store_id"] == PRIMARY_STORE_ID
            )
            _write(data)
            return dict(entry)
        try:
            exists = resolve_database_path(entry).exists()
        except RuntimeError:
            exists = False
        if not exists and entry["store_id"] != PRIMARY_STORE_ID:
            logger.warning(
                "Toko aktif %s tidak ditemukan; kembali ke toko utama.",
                entry["store_id"],
            )
            data["active_store_id"] = PRIMARY_STORE_ID
            _write(data)
            return dict(next(
                row for row in data["stores"] if row["store_id"] == PRIMARY_STORE_ID
            ))
        return dict(entry)


def set_active_store(store_id: str) -> Dict[str, Any]:
    with _lock:
        data = _load()
        entry = next(
            (row for row in data["stores"] if row["store_id"] == store_id), None
        )
        if entry is None:
            raise KeyError(store_id)
        if not resolve_database_path(entry).exists():
            raise FileNotFoundError(store_id)
        data["active_store_id"] = store_id
        _write(data)
        return dict(entry)


def add_store(
    *,
    database_id: str,
    nama: str,
    alamat: str,
    database_path: str,
) -> Dict[str, Any]:
    with _lock:
        data = _load()
        database_path = _relative_database_path(Path(database_path))
        entry = {
            "store_id": database_id,
            "database_id": database_id,
            "nama": nama.strip(),
            "alamat": alamat.strip(),
            "database_path": database_path,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        data["stores"].append(entry)
        _write(data)
        return dict(entry)


def update_store(store_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
    with _lock:
        data = _load()
        entry = next(
            (row for row in data["stores"] if row["store_id"] == store_id), None
        )
        if entry is None:
            return None
        for key in ("database_id", "nama", "alamat"):
            if key in fields and fields[key] is not None:
                entry[key] = str(fields[key]).strip()
        _write(data)
        return dict(entry)


def reset_cache() -> None:
    """Paksa pembacaan ulang registry setelah berkas ditulis di luar API."""
    global _cached, _cached_mtime_ns
    with _lock:
        _cached = None
        _cached_mtime_ns = -1


def upsert_stores(
    entries: List[Dict[str, Any]],
    *,
    active_store_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Daftarkan/segarkan entri toko dari arsip tanpa menghapus toko lain."""
    with _lock:
        data = _load()
        by_id = {row["store_id"]: row for row in data["stores"]}
        for item in entries:
            store_id = str(item.get("store_id") or "").strip()
            raw_path = str(item.get("database_path") or "").strip()
            if not store_id or not raw_path:
                continue
            path = _relative_database_path(Path(raw_path))
            fields = {
                "database_id": str(
                    item.get("database_id") or store_id
                ).strip(),
                "nama": str(item.get("nama") or "").strip(),
                "alamat": str(item.get("alamat") or "").strip(),
                "database_path": path,
            }
            if store_id in by_id:
                by_id[store_id].update(fields)
            else:
                entry = {"store_id": store_id, **fields, "created_at": ""}
                data["stores"].append(entry)
                by_id[store_id] = entry
        if active_store_id and active_store_id in by_id:
            data["active_store_id"] = active_store_id
        _write(data)
        return [dict(row) for row in data["stores"]]


def reset_for_tests() -> Dict[str, Any]:
    """Bersihkan registry dan toko tambahan; hanya untuk APP_ENV=test."""
    if settings.app_env != "test":
        raise RuntimeError("reset_for_tests hanya boleh dipakai saat pengujian.")
    global _cached, _cached_mtime_ns
    with _lock:
        directory = stores_dir()
        if directory.exists():
            for child in directory.iterdir():
                if child.is_file() and (
                    child.name == "registry.json"
                    or child.suffix == ".db"
                    or child.name.startswith("registry.rusak-")
                ):
                    child.unlink(missing_ok=True)
        _cached = None
        _cached_mtime_ns = -1
        return _write(_default_registry())
