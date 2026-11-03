"""Buat dua profil dummy: gratis dan premium, lengkap dengan akun login.

Setiap profil memakai folder datanya sendiri agar registry plan dan database
tidak tercampur:

    data/dummy_free/app.db       PIN pemilik, plan gratis
    data/dummy_premium/app.db    PIN pemilik, lisensi premium, akun karyawan

Skrip menolak berjalan bila path tidak mengandung kata "dummy", sehingga
database kasir asli tidak tersentuh. Data dibuat ulang dari nol setiap kali
dijalankan.

Contoh:
    python tools/seed_dummy_accounts.py
    python tools/seed_dummy_accounts.py --profile premium

Menjalankan aplikasi:
    set "DATABASE_URL=sqlite:///./data/dummy_free/app.db"
    python run.py --port 8001

    set "DATABASE_URL=sqlite:///./data/dummy_premium/app.db"
    python run.py --port 8002
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PROFILES = {
    "free": {
        "folder": "data/dummy_free",
        "plan": "free",
        "nama": "BENGKEL DUMMY GRATIS",
        "alamat": "Jl. Dummy Gratis No. 1, Bandung",
        "owner_pin": "123456",
        "employees": (),
    },
    "premium": {
        "folder": "data/dummy_premium",
        "plan": "premium",
        "nama": "BENGKEL DUMMY PREMIUM",
        "alamat": "Jl. Dummy Premium No. 2, Bandung",
        "owner_pin": "654321",
        "employees": (
            {
                "username": "kasir",
                "nama": "Kasir Demo",
                "role": "KASIR",
                "password": "kasirdemo123",
                "pin": "111111",
                "extra_permissions": ["opname", "stok_masuk", "baca_followup"],
            },
            {
                "username": "mekanik",
                "nama": "Mekanik Demo",
                "role": "MEKANIK",
                "password": "mekanikdemo123",
                "pin": "222222",
                "extra_permissions": ["stok_keluar"],
            },
        ),
    },
}


def _profile_env(name: str) -> dict[str, str]:
    profile = PROFILES[name]
    return {
        "APP_ENV": "development",
        "APP_HOST": "127.0.0.1",
        "AUTH_MODE": "session-pin",
        "ENTITLEMENT_PLAN": "free",
        "DATABASE_URL": f"sqlite:///./{profile['folder']}/app.db",
        "BACKUP_DIR": f"./backups_dummy_{name}",
        "PRINTER_CONFIG_PATH": "./data/printer_config_dummy.json",
        "TELEGRAM_BACKUP_ENABLED": "0",
        "BENGKEL_NAMA": profile["nama"],
        "BENGKEL_ALAMAT": profile["alamat"],
        "BENGKEL_TELEPON": "081200000000",
        "BENGKEL_WA": "081200000000",
    }


def _reset_folder(name: str) -> Path:
    profile = PROFILES[name]
    folder = ROOT / profile["folder"]
    if "dummy" not in folder.as_posix().lower():
        raise SystemExit("Dibatalkan: folder profil bukan folder dummy.")
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    backup_dir = ROOT / f"backups_dummy_{name}"
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    return folder


def seed_one(name: str) -> None:
    profile = PROFILES[name]
    folder = _reset_folder(name)
    os.environ.update(_profile_env(name))
    sys.path.insert(0, str(ROOT))

    from database import store_registry
    from database.seed import seed_defaults
    from database.session import SessionLocal, init_db
    from services import (
        account_service,
        auth_service,
        license_service,
        store_service,
    )

    init_db()
    owner_id = ""
    recovery_code = ""

    with SessionLocal() as db:
        seed_defaults(db)
        store_service.ensure_database_id(
            db, store_id=store_registry.PRIMARY_STORE_ID
        )
        store_service.sync_registry_identity(
            db, store_id=store_registry.PRIMARY_STORE_ID
        )
        auth_service.setup_pin(db, profile["owner_pin"])

        if profile["plan"] == "premium":
            license_data = license_service.activate(
                db, days=365, provider="manual", device_limit=2
            )
            owner_id = license_data["owner_id"]
            recovery_code = license_data["recovery_code"] or ""
            for employee in profile["employees"]:
                created = account_service.create_account(
                    db,
                    actor="owner",
                    username=employee["username"],
                    nama=employee["nama"],
                    role=employee["role"],
                    store_ids=[store_registry.PRIMARY_STORE_ID],
                    extra_permissions=employee["extra_permissions"],
                    password=employee["password"],
                )
                account = account_service.get_account(
                    db, created["akun"]["id"]
                )
                account_service.set_pin(account, employee["pin"])
                # Akun dummy dipakai berulang; alur wajib ganti password tetap
                # berlaku di akun buatan aplikasi.
                account.must_change_password = False
                db.commit()

        store_service.sync_registry_identity(
            db, store_id=store_registry.PRIMARY_STORE_ID
        )

    line = "=" * 62
    print(line)
    print(f"  PROFIL DUMMY: {name.upper()}")
    print(line)
    print(f"  Database     : {folder / 'app.db'}")
    print(f"  Plan         : {profile['plan']}")
    print(f"  PIN pemilik  : {profile['owner_pin']}")
    if profile["plan"] == "premium":
        print(f"  ID owner     : {owner_id}")
        print(f"  Kode pulih   : {recovery_code}")
        print("  Akun karyawan (login hub: username + password + PIN):")
        for employee in profile["employees"]:
            print(
                f"    - {employee['username']} / {employee['password']} / "
                f"PIN {employee['pin']} ({employee['role']})"
            )
    print(line)
    print("  Jalankan:")
    print(
        f'  set "DATABASE_URL=sqlite:///./{profile["folder"]}/app.db"'
    )
    print("  python run.py --port 8001")
    print(line)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Buat profil dan akun dummy gratis/premium."
    )
    parser.add_argument(
        "--profile",
        choices=("free", "premium", "both"),
        default="both",
        help="Profil yang dibuat (default: both).",
    )
    args = parser.parse_args()

    if args.profile == "both":
        for name in ("free", "premium"):
            completed = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--profile", name],
                check=False,
            )
            if completed.returncode != 0:
                return completed.returncode
        return 0

    seed_one(args.profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
