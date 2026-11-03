"""Rangkaian E2E penuh dari instalasi baru: gratis, premium, karyawan, backup, relay, offline."""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx

from services import premium_crypto
from services.sync_service import build_envelope

BASE = "http://127.0.0.1:8020"
RELAY = "http://127.0.0.1:8120"
ENROLL = "e2e-final-relay-token"
DATA = ROOT / "data" / "dummy_e2e_final"
BACKUPS = ROOT / "backups" / "dummy_e2e_final"
PROFILE = DATA / "browser_profile"
app_proc = None
relay_proc = None
results: list[tuple[str, bool, str]] = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), str(detail)[:300]))
    print(("PASS" if cond else "FAIL"), name, detail)


def wait_health(url: str, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.4)
    raise RuntimeError(f"Server tidak siap: {url}")


def start_app():
    global app_proc
    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": "test",
            "DATABASE_URL": f"sqlite:///{(DATA / 'app.db').as_posix()}",
            "BACKUP_DIR": str(BACKUPS),
        }
    )
    log = open(DATA / "app.log", "ab")
    app_proc = subprocess.Popen(
        [sys.executable, "run.py", "--port", "8020"],
        cwd=ROOT,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    wait_health(BASE + "/api/health")


def stop_app():
    global app_proc
    if app_proc is not None:
        app_proc.terminate()
        try:
            app_proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            app_proc.kill()
        app_proc = None


def start_relay():
    global relay_proc
    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": "test",
            "RELAY_DATABASE_URL": f"sqlite:///{(DATA / 'relay.db').as_posix()}",
            "RELAY_ENROLL_TOKEN": ENROLL,
            "RELAY_REQUIRE_HTTPS": "0",
        }
    )
    log = open(DATA / "relay.log", "ab")
    relay_proc = subprocess.Popen(
        [sys.executable, "run_relay.py", "--port", "8120"],
        cwd=ROOT,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    wait_health(RELAY + "/relay/health")


def stop_relay():
    global relay_proc
    if relay_proc is not None:
        relay_proc.terminate()
        try:
            relay_proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            relay_proc.kill()
        relay_proc = None


@contextlib.contextmanager
def owner_client():
    client = httpx.Client(base_url=BASE, timeout=60)
    try:
        response = client.post("/api/auth/login", json={"pin": "123456"})
        assert response.status_code == 200, response.text
        yield client
    finally:
        client.close()


def main() -> int:
    if DATA.exists():
        shutil.rmtree(DATA)
    if BACKUPS.exists():
        shutil.rmtree(BACKUPS)
    DATA.mkdir(parents=True)
    BACKUPS.mkdir(parents=True)
    start_relay()
    start_app()
    try:
        # ---------- 0. Instal baru + setup PIN lewat browser ----------
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                str(PROFILE),
                channel="chrome",
                headless=True,
                viewport={"width": 1280, "height": 900},
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(BASE + "/", wait_until="networkidle")
            check("fresh install shows PIN setup", page.locator("#authSetup").is_visible())
            page.fill("#authSetupPin", "123456")
            page.fill("#authSetupPinConfirm", "123456")
            page.click("#authSetupSubmit")
            page.wait_for_selector("#authGate", state="hidden", timeout=15000)
            page.wait_for_timeout(1200)
            check("setup PIN opens dashboard", page.locator("#view-dashboard").is_visible())
            page.evaluate("navigator.serviceWorker.ready")
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(1200)
            check(
                "service worker controls app",
                page.evaluate("Boolean(navigator.serviceWorker.controller)"),
            )
            context.close()

        with owner_client() as owner:
            config = owner.get("/api/config").json()
            check("fresh app is free", config["premium"]["plan"] == "free", config["premium"]["plan"])
            check("fresh app has one store", len(config["stores"]) == 1)
            customer = owner.post(
                "/api/customers",
                json={"nama": "Pelanggan Final Gratis", "nomor_hp": "081300000001"},
            )
            check("free create customer", customer.status_code == 201, customer.status_code)
            customer_id = customer.json()["id"]
            unit = owner.post(
                "/api/units",
                json={
                    "customer_id": customer_id,
                    "unit_type": "MOBIL",
                    "nopol": "D 2001 FIN",
                    "jenis_mobil": "Avanza",
                    "tahun_mobil": 2016,
                },
            )
            check("free create unit", unit.status_code == 201, unit.status_code)
            unit_id = unit.json()["id"]
            stock = owner.get("/api/stock").json()
            transaksi = owner.post(
                "/api/pos/transaction",
                json={
                    "unit_id": unit_id,
                    "keluhan_awal": "Radiator bocor final",
                    "jobs": [{"deskripsi": "Korok Final", "jumlah": 1, "harga": "150000"}],
                    "parts": [
                        {
                            "stock_item_id": stock[0]["id"],
                            "nama_part": "",
                            "jumlah": 1,
                            "harga_satuan": str(stock[0]["harga_jual"]),
                        }
                    ],
                    "metode_bayar": "CASH",
                    "bayar": "500000",
                    "request_id": "final-free-trx-0001",
                },
            )
            check("free transaction", transaksi.status_code == 201, transaksi.text[:160])
            if transaksi.status_code == 201:
                check(
                    "free note number numeric",
                    transaksi.json()["record"]["no_nota"].isdigit(),
                    transaksi.json()["record"]["no_nota"],
                )
            check("free daily report", owner.get("/api/reports/daily-cash").status_code == 200)
            check(
                "free quota 20",
                owner.get("/api/followup/quota").json().get("sisa") == 20,
            )
            blocked_store = owner.post("/api/stores", json={"nama": "Toko Terkunci"})
            check(
                "free add store blocked",
                blocked_store.status_code == 403
                and blocked_store.json().get("code") == "premium_locked",
                blocked_store.status_code,
            )
            backup = owner.post("/api/admin/backup?format=db")
            check(
                "free manual backup",
                backup.status_code == 200 and backup.content[:16] == b"SQLite format 3\x00",
                len(backup.content),
            )

            # ---------- 1. Premium ----------
            license_data = owner.post(
                "/api/license/activate",
                json={"days": 30, "provider": "manual", "device_limit": 2},
            )
            check("activate premium", license_data.status_code == 200, license_data.text[:120])
            license_data = license_data.json()
            owner_id = license_data["owner_id"]
            recovery_code = license_data["recovery_code"]
            config = owner.get("/api/config").json()
            check("plan is premium", config["premium"]["plan"] == "premium")
            owner_public = config["premium"]["owner_public_key"]
            primary = config["stores"][0]["store_id"]
            store = owner.post("/api/stores", json={"nama": "Toko Final Kedua", "alamat": "Jl. Final 2"})
            check("add second store", store.status_code == 201, store.text[:120])
            store2 = store.json()["store_id"]
            owner.post(f"/api/stores/{store2}/activate")
            owner.post("/api/customers", json={"nama": "Pelanggan Final Cabang", "nomor_hp": "081300000002"})
            owner.post(f"/api/stores/{primary}/activate")
            names = [row["nama"] for row in owner.get("/api/customers").json()]
            check("store isolation", "Pelanggan Final Cabang" not in names, names)
            account = owner.post(
                "/api/accounts",
                json={
                    "username": "kasir_final",
                    "nama": "Kasir Final",
                    "role": "KASIR",
                    "store_ids": [primary],
                    "extra_permissions": ["opname", "stok_masuk"],
                    "password": "KasirFinal123",
                },
            )
            check("create employee account", account.status_code == 201, account.text[:120])
            account_id = account.json()["akun"]["id"]

            # ---------- 2. Perangkat, kunci, feed, snapshot, klaim ----------
            d1 = owner.post(
                "/api/devices",
                json={"nama": "HP Final 1", "kind": "owner", "generate_keys": True, "store_ids": [primary]},
            )
            d2 = owner.post(
                "/api/devices",
                json={"nama": "HP Final 2", "kind": "owner", "generate_keys": True, "store_ids": [primary]},
            )
            d3 = owner.post(
                "/api/devices",
                json={"nama": "HP Final 3", "kind": "owner", "generate_keys": True, "store_ids": [primary]},
            )
            check("register owner device 1", d1.status_code == 201, d1.status_code)
            check("register owner device 2", d2.status_code == 201, d2.status_code)
            check(
                "third owner device blocked",
                d3.status_code == 403 and d3.json().get("code") == "device_limit",
                d3.status_code,
            )
            d1 = d1.json()
            d2 = d2.json()
            dev1, keys1 = d1["device"], d1["private_keys"]
            dev2 = d2["device"]
            keys = owner.post(
                "/api/devices/keys",
                json={
                    "store_id": primary,
                    "device_ids": [dev1["id"], dev2["id"]],
                    "primary_device_id": dev1["id"],
                    "store_key": "",
                },
            )
            check("register store key", keys.status_code == 200, keys.status_code)
            store_key_b64 = keys.json()["store_key"]
            store_key = premium_crypto.b64d(store_key_b64)
            boot = owner.get(
                "/api/sync/bootstrap",
                params={"store_id": primary, "device_id": dev2["id"]},
            )
            check(
                "bootstrap returns wrapped key",
                boot.status_code == 200 and bool(boot.json().get("wrapped_key")),
                boot.text[:120],
            )
            envelope = build_envelope(
                device_private_b64=keys1["sign"],
                store_key=store_key,
                store_id=primary,
                sender_device_id=dev1["id"],
                recipient_device_id="",
                seq=1,
                hlc_wall=1000,
                hlc_counter=0,
                idempotency_key="final-envelope-0001",
                payload={
                    "entity": "stock",
                    "action": "delta",
                    "entity_id": "final-stock",
                    "payload": {"stock_item_id": stock[0]["id"], "qty": 1},
                },
            )
            submit = owner.post(
                "/api/sync/envelopes",
                json={
                    "store_id": primary,
                    "sender_device_id": dev1["id"],
                    "recipient_device_id": "",
                    "seq": 1,
                    "hlc_wall": 1000,
                    "hlc_counter": 0,
                    "idempotency_key": "final-envelope-0001",
                    "ciphertext": envelope["ciphertext"],
                    "nonce": envelope["nonce"],
                    "signature": envelope["signature"],
                },
            )
            check("submit envelope", submit.status_code == 201, submit.status_code)
            device_client = httpx.Client(
                base_url=BASE, timeout=40, headers={"X-Device-Token": d2["token"]}
            )
            feed = device_client.get(
                "/api/sync/feed",
                params={"device_id": dev2["id"], "store_id": primary, "since_seq": 0},
            )
            check(
                "device feed receives envelope",
                feed.status_code == 200 and len(feed.json()["envelopes"]) == 1,
                feed.status_code,
            )
            ack = device_client.post(
                "/api/sync/feed/ack",
                json={
                    "device_id": dev2["id"],
                    "store_id": primary,
                    "last_seq": feed.json()["next_seq"],
                },
            )
            check("feed ack prunes ciphertext", ack.status_code == 200 and ack.json().get("pruned") == 1, ack.text[:120])
            conn = sqlite3.connect(DATA / "app.db")
            left = conn.execute("SELECT COUNT(*) FROM relay_envelopes").fetchone()[0]
            counter = conn.execute(
                "SELECT last_seq FROM store_feed_counters WHERE store_id=?", (primary,)
            ).fetchone()
            conn.close()
            check("envelope deleted", left == 0, left)
            check("counter permanent", counter and counter[0] == 1, counter)
            snapshot = owner.post(
                "/api/sync/snapshots",
                json={
                    "store_id": primary,
                    "device_id": dev1["id"],
                    "store_key": store_key_b64,
                    "device_private_key": keys1["sign"],
                    "hlc_wall": 1100,
                },
            )
            check("snapshot store_seq", snapshot.status_code == 201 and snapshot.json().get("store_seq") == 1, snapshot.text[:120])
            claim = owner.post(
                "/api/devices/claim",
                json={"old_device_id": dev2["id"], "nama": "HP Final 2 Baru", "generate_keys": True},
            )
            check("claim reinstalled device", claim.status_code == 201, claim.status_code)
            new_dev = claim.json()["device"]
            boot_new = owner.get(
                "/api/sync/bootstrap",
                params={"store_id": primary, "device_id": new_dev["id"]},
            )
            check(
                "new device requires key wrap",
                boot_new.status_code == 200
                and boot_new.json().get("key_wrap_required") is True
                and boot_new.json().get("snapshot", {}).get("store_seq") == 1,
                boot_new.text[:160],
            )
            owner.post(
                "/api/devices/keys",
                json={
                    "store_id": primary,
                    "device_ids": [new_dev["id"]],
                    "primary_device_id": dev1["id"],
                    "store_key": store_key_b64,
                },
            )
            boot_new2 = owner.get(
                "/api/sync/bootstrap",
                params={"store_id": primary, "device_id": new_dev["id"]},
            )
            applied = owner.post(
                "/api/sync/snapshots/apply",
                json={
                    "device_id": new_dev["id"],
                    "snapshot_id": boot_new2.json()["snapshot"]["id"],
                    "store_key": store_key_b64,
                },
            )
            check(
                "apply snapshot sets cursor",
                applied.status_code == 200 and applied.json().get("cursor") == 1,
                applied.text[:120],
            )

            # ---------- 3. Karyawan ----------
            emp = owner.post(
                "/api/devices",
                json={
                    "nama": "HP Final Kasir",
                    "kind": "employee",
                    "employee_account_id": account_id,
                    "generate_keys": True,
                    "store_ids": [primary],
                },
            )
            check("register employee device", emp.status_code == 201, emp.status_code)
            emp = emp.json()
            emp_client = httpx.Client(
                base_url=BASE, timeout=40, headers={"X-Device-Token": emp["token"]}
            )
            login = emp_client.post(
                "/api/auth/device/login",
                json={
                    "owner_id": owner_id,
                    "username": "kasir_final",
                    "password": "KasirFinal123",
                },
            )
            check("employee device login", login.status_code == 200, login.status_code)
            change = emp_client.post(
                "/api/auth/employee/change-password",
                json={"old_password": "KasirFinal123", "new_password": "KasirFinal456"},
            )
            check("employee changes initial password", change.status_code == 200, change.status_code)
            emp_cfg = emp_client.get("/api/config")
            check(
                "employee permissions",
                emp_cfg.status_code == 200
                and emp_cfg.json()["operator"]["kind"] == "employee"
                and "opname" in emp_cfg.json()["operator"]["permissions"],
                emp_cfg.status_code,
            )
            emp_trx = emp_client.post(
                "/api/pos/transaction",
                json={
                    "unit_id": unit_id,
                    "keluhan_awal": "Nota karyawan final",
                    "jobs": [{"deskripsi": "Servis Karyawan Final", "jumlah": 1, "harga": "120000"}],
                    "parts": [
                        {
                            "stock_item_id": stock[1]["id"],
                            "nama_part": "",
                            "jumlah": 1,
                            "harga_satuan": str(stock[1]["harga_jual"]),
                        }
                    ],
                    "metode_bayar": "CASH",
                    "bayar": "300000",
                    "request_id": "final-employee-trx-0001",
                },
            )
            check("employee creates nota", emp_trx.status_code == 201, emp_trx.text[:160])
            record_id = emp_trx.json()["record"]["id"] if emp_trx.status_code == 201 else 0
            if record_id:
                check(
                    "employee note has device prefix",
                    "-" in emp_trx.json()["record"]["no_nota"],
                    emp_trx.json()["record"]["no_nota"],
                )
                void = emp_client.post(
                    f"/api/service-records/{record_id}/void",
                    json={"alasan": "Uji void karyawan final"},
                )
                check(
                    "employee cashier can void",
                    void.status_code == 200,
                    void.text[:120],
                )
            owner_only = emp_client.get("/api/accounts")
            check(
                "employee owner route blocked",
                owner_only.status_code == 403 and owner_only.json().get("code") == "owner_only",
                owner_only.status_code,
            )
            hub_client = httpx.Client(base_url=BASE, timeout=40)
            hub_login = hub_client.post(
                "/api/auth/employee/login",
                json={"username": "kasir_final", "password": "KasirFinal456", "pin": "654321"},
            )
            check("employee login", hub_login.status_code == 200, hub_login.text[:120])

        # ---------- 4. UI premium dan karyawan ----------
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            errors = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.goto(BASE + "/", wait_until="networkidle")
            page.fill("#authLoginPin", "123456")
            page.click("#authLoginSubmit")
            page.wait_for_selector("#authGate", state="hidden", timeout=15000)
            page.wait_for_timeout(1200)
            page.click("#premiumNavTab")
            page.wait_for_timeout(1200)
            check(
                "premium UI shows owner id",
                "Premium" in page.locator("#premiumLicenseCard").inner_text()
                and owner_id in page.locator("#premiumLicenseCard").inner_text(),
            )
            page.click("#storeSwitchBtn")
            page.wait_for_selector("#storeModal", state="visible", timeout=8000)
            page.click("#storeAddToggle")
            page.fill("#storeAddName", "Toko UI Final")
            page.fill("#storeAddAddress", "Jl. UI Final")
            page.click("#storeAddSave")
            try:
                page.wait_for_function(
                    "document.querySelector('#storeList').innerText.includes('Toko UI Final')",
                    timeout=8000,
                )
                ui_store_added = True
            except Exception:
                ui_store_added = False
            check(
                "store added from UI",
                ui_store_added,
                page.locator("#storeAddError").inner_text(),
            )
            page.click("#storeModalDismiss")
            page.wait_for_timeout(400)
            page.click("#archiveBackupAllBtn")
            page.wait_for_timeout(3500)
            check(
                "backup all from UI",
                "Cadangan semua toko dibuat" in page.locator("#toastContainer").inner_text()
                or "bengkel_radiator_semua" in page.locator("#archiveList").inner_text(),
            )
            check("premium UI no console errors", not errors, errors[:3])
            browser.close()

        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            failures = []
            page.on("response", lambda r: failures.append((r.status, r.url)) if r.status >= 400 else None)
            page.goto(BASE + "/", wait_until="networkidle")
            page.click("#authEmployeeToggle")
            page.fill("#authEmployeeUser", "kasir_final")
            page.fill("#authEmployeePassword", "KasirFinal456")
            page.fill("#authEmployeePin", "654321")
            page.click("#authEmployeeSubmit")
            page.wait_for_selector("#authGate", state="hidden", timeout=15000)
            page.wait_for_timeout(1800)
            check(
                "employee UI identity",
                page.locator("#sessionLabel").inner_text() == "Kasir Final",
                page.locator("#sessionLabel").inner_text(),
            )
            check("employee UI hides owner menu", not page.locator("#premiumNavTab").is_visible())
            check("employee UI no failed requests", not failures, failures[:3])
            browser.close()

        # ---------- 5. Backup semua toko + restore ----------
        with owner_client() as owner:
            owner.post(f"/api/stores/{primary}/activate")
            owner.post("/api/customers", json={"nama": "Marker Final Sebelum", "nomor_hp": "081300000010"})
            owner.post(f"/api/stores/{store2}/activate")
            owner.post("/api/customers", json={"nama": "Marker Final Cabang", "nomor_hp": "081300000011"})
            owner.post(f"/api/stores/{primary}/activate")
            backup = owner.post("/api/admin/backup-all")
            check("backup all stores", backup.status_code == 200, len(backup.content))
            archive_path = DATA / "backup_all.zip"
            archive_path.write_bytes(backup.content)
            with zipfile.ZipFile(archive_path) as archive:
                names = archive.namelist()
                manifest = json.loads(archive.read("manifest.json"))
            archived_ids = {entry["store_id"] for entry in manifest["stores"]}
            check(
                "archive manifest and stores",
                "manifest.json" in names
                and len(manifest["stores"]) >= 2
                and {primary, store2}.issubset(archived_ids),
                sorted(archived_ids),
            )
            check(
                "archive checksums",
                all(entry.get("sha256") for entry in manifest["stores"]),
            )
            owner.post("/api/customers", json={"nama": "Marker Final Sesudah", "nomor_hp": "081300000012"})
            restore = owner.post(
                "/api/admin/restore-all",
                files={"file": ("backup_all.zip", backup.content, "application/zip")},
            )
            check("restore all stores", restore.status_code == 200, restore.text[:120])
            names_primary = [row["nama"] for row in owner.get("/api/customers").json()]
            check(
                "restore keeps pre-backup data",
                "Marker Final Sebelum" in names_primary
                and "Marker Final Sesudah" not in names_primary,
                names_primary,
            )
            owner.post(f"/api/stores/{store2}/activate")
            check(
                "restore keeps second store data",
                any(row["nama"] == "Marker Final Cabang" for row in owner.get("/api/customers").json()),
            )
            owner.post(f"/api/stores/{primary}/activate")
            hub_after = httpx.Client(base_url=BASE, timeout=40)
            after_login = hub_after.post(
                "/api/auth/employee/login",
                json={"username": "kasir_final", "password": "KasirFinal456", "pin": "654321"},
            )
            check("employee credentials survive restore", after_login.status_code == 200, after_login.status_code)
            token_after = emp_client.get("/api/config")
            check("device token survives restore", token_after.status_code == 200, token_after.status_code)
            # ZIP rusak harus rollback.
            broken_bytes = bytearray(backup.content)
            mid = len(broken_bytes) // 2
            broken_bytes[mid : mid + 8] = b"BROKEN!!"
            broken = owner.post(
                "/api/admin/restore-all",
                files={"file": ("broken.zip", bytes(broken_bytes), "application/zip")},
            )
            check("broken archive rejected", broken.status_code in (400, 409), broken.status_code)
            names_rollback = [row["nama"] for row in owner.get("/api/customers").json()]
            check("rollback keeps data", "Marker Final Sebelum" in names_rollback, names_rollback)

        # ---------- 6. Relay nyata ----------
        with owner_client() as owner:
            recovery = owner.post("/api/license/recovery", json={"code": recovery_code})
            check("owner recovery key", recovery.status_code == 200, recovery.status_code)
            owner_private = recovery.json()["private_key"]

        def enroll(client, nama, kind, pub, enc):
            response = client.post(
                "/relay/devices",
                headers={"X-Relay-Enroll-Token": ENROLL},
                json={
                    "owner_id": owner_id,
                    "nama": nama,
                    "kind": kind,
                    "public_key": pub,
                    "encryption_key": enc,
                    "owner_public_key": owner_public,
                    "store_ids": [store2],
                },
            )
            check(f"relay enroll {nama}", response.status_code == 201, response.text[:120])
            return response.json()

        with httpx.Client(base_url=RELAY, timeout=40) as relay:
            sign1, pub1 = premium_crypto.generate_signing_keypair()
            enc1, encpub1 = premium_crypto.generate_encryption_keypair()
            r1 = enroll(relay, "Relay Final 1", "owner", pub1, encpub1)
            sign2, pub2 = premium_crypto.generate_signing_keypair()
            enc2, encpub2 = premium_crypto.generate_encryption_keypair()
            r2 = enroll(relay, "Relay Final 2", "owner", pub2, encpub2)
            t1, t2 = r1["token"], r2["token"]
            id1, id2 = r1["device"]["id"], r2["device"]["id"]
            key = premium_crypto.new_store_key()
            for target, encpub in ((id1, encpub1), (id2, encpub2)):
                wrapped = premium_crypto.wrap_store_key(encpub, key)
                signature = premium_crypto.sign(
                    owner_private,
                    premium_crypto.canonical_json(
                        {"store_id": store2, "device_id": target, "wrapped_key": wrapped}
                    ),
                )
                response = relay.post(
                    "/relay/keys",
                    headers={"X-Device-Token": t1},
                    json={
                        "store_id": store2,
                        "device_id": target,
                        "wrapped_key": wrapped,
                        "signature": signature,
                    },
                )
                check(f"relay wrap {target[-4:]}", response.status_code == 200, response.status_code)
            fields = {
                "store_id": store2,
                "sender_device_id": id1,
                "recipient_device_id": "",
                "seq": 1,
                "hlc_wall": 9000,
                "hlc_counter": 0,
                "idempotency_key": "relay-final-0001",
            }
            ciphertext, nonce = premium_crypto.encrypt_payload(
                key, premium_crypto.canonical_json({"entity": "stock", "qty": 2})
            )
            signature = premium_crypto.sign(
                sign1,
                premium_crypto.canonical_json(
                    {"v": 1, **fields, "ciphertext": ciphertext, "nonce": nonce}
                ),
            )
            sent = relay.post(
                "/relay/envelopes",
                headers={"X-Device-Token": t1},
                json={**fields, "ciphertext": ciphertext, "nonce": nonce, "signature": signature},
            )
            check("relay submit envelope", sent.status_code == 201, sent.status_code)
            feed = relay.get(
                "/relay/feed",
                headers={"X-Device-Token": t2},
                params={"store_id": store2, "since_seq": 0},
            )
            check(
                "relay feed",
                feed.status_code == 200 and len(feed.json()["envelopes"]) == 1,
                feed.status_code,
            )
            ack = relay.post(
                "/relay/feed/ack",
                headers={"X-Device-Token": t2},
                json={"store_id": store2, "last_seq": feed.json()["next_seq"]},
            )
            check("relay ack prunes", ack.status_code == 200 and ack.json().get("pruned") == 1, ack.text[:120])
            conn = sqlite3.connect(DATA / "relay.db")
            relay_left = conn.execute("SELECT COUNT(*) FROM relay_envelopes").fetchone()[0]
            relay_counter = conn.execute(
                "SELECT last_seq FROM relay_feed_counters WHERE store_id=?", (store2,)
            ).fetchone()
            conn.close()
            check("relay ciphertext removed", relay_left == 0, relay_left)
            check("relay counter permanent", relay_counter and relay_counter[0] == 1, relay_counter)
            boot = relay.get(
                "/relay/bootstrap",
                headers={"X-Device-Token": t2},
                params={"store_id": store2},
            )
            check(
                "relay bootstrap wrapped key",
                boot.status_code == 200 and bool(boot.json().get("wrapped_key")),
                boot.status_code,
            )
            sign3, pub3 = premium_crypto.generate_signing_keypair()
            enc3, encpub3 = premium_crypto.generate_encryption_keypair()
            claim = relay.post(
                "/relay/devices/claim",
                headers={"X-Device-Token": t1},
                json={
                    "old_device_id": id2,
                    "public_key": pub3,
                    "encryption_key": encpub3,
                    "nama": "Relay Final 2 Baru",
                },
            )
            check("relay claim", claim.status_code == 201, claim.status_code)
            id3, t3 = claim.json()["device"]["id"], claim.json()["token"]
            check(
                "relay revoked token rejected",
                relay.get("/relay/devices/me", headers={"X-Device-Token": t2}).status_code == 401,
            )
            boot3 = relay.get(
                "/relay/bootstrap",
                headers={"X-Device-Token": t3},
                params={"store_id": store2},
            )
            check(
                "relay new device needs rewrap",
                boot3.status_code == 200 and boot3.json().get("key_wrap_required") is True,
                boot3.text[:120],
            )
            wrapped3 = premium_crypto.wrap_store_key(encpub3, key)
            signature3 = premium_crypto.sign(
                owner_private,
                premium_crypto.canonical_json(
                    {"store_id": store2, "device_id": id3, "wrapped_key": wrapped3}
                ),
            )
            relay.post(
                "/relay/keys",
                headers={"X-Device-Token": t1},
                json={
                    "store_id": store2,
                    "device_id": id3,
                    "wrapped_key": wrapped3,
                    "signature": signature3,
                },
            )
            boot3b = relay.get(
                "/relay/bootstrap",
                headers={"X-Device-Token": t3},
                params={"store_id": store2},
            )
            check(
                "relay bootstrap after rewrap",
                boot3b.status_code == 200 and bool(boot3b.json().get("wrapped_key")),
                boot3b.status_code,
            )

        # ---------- 7. Offline PWA + antrean ----------
        with owner_client() as owner:
            customers = owner.get("/api/customers").json()
            customer = None
            unit = None
            for candidate in customers:
                units = owner.get(f"/api/customers/{candidate['id']}/units").json()
                if units:
                    customer = candidate
                    unit = units[0]
                    break
            stock = owner.get("/api/stock").json()[0]
            payload = {
                "unit_id": unit["id"],
                "keluhan_awal": "Transaksi offline final",
                "jobs": [{"deskripsi": "Offline Final", "jumlah": 1, "harga": "90000"}],
                "parts": [
                    {
                        "stock_item_id": stock["id"],
                        "nama_part": "",
                        "jumlah": 1,
                        "harga_satuan": str(stock["harga_jual"]),
                    }
                ],
                "metode_bayar": "CASH",
                "bayar": "200000",
                "request_id": "final-offline-trx-0001",
            }
        stop_app()
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                str(PROFILE),
                channel="chrome",
                headless=True,
                viewport={"width": 1280, "height": 900},
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(BASE + "/", wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(1500)
            check("offline shell loads", page.title().startswith("BENGKEL RADIATOR"))
            auth_probe = page.evaluate(
                "fetch('/api/auth/status').then(r=>r.status).catch(()=>'offline')"
            )
            check("auth status is not served from cache", auth_probe == "offline", auth_probe)
            check(
                "offline session marker exists",
                page.evaluate("Boolean(localStorage.getItem('bengkel.offlineSession'))"),
            )
            queued = page.evaluate("(payload)=>API.createTransaction(payload)", payload)
            count = page.evaluate("OfflineQueue.count()")
            check(
                "offline transaction queued",
                queued.get("offline_queued") is True and count == 1,
                queued,
            )
            check("offline banner visible", page.locator("#offlineBanner").is_visible())
            context.close()
        start_app()
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                str(PROFILE),
                channel="chrome",
                headless=True,
                viewport={"width": 1280, "height": 900},
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(BASE + "/", wait_until="networkidle")
            page.wait_for_timeout(1000)
            flush = page.evaluate("OfflineQueue.flush()")
            page.wait_for_timeout(800)
            check(
                "offline queue flushes",
                flush.get("sent") == 1 and page.evaluate("OfflineQueue.count()") == 0,
                flush,
            )
            page.click("#sessionLogout")
            page.wait_for_timeout(1500)
            check(
                "logout clears offline session",
                page.evaluate("!localStorage.getItem('bengkel.offlineSession')"),
            )
            context.close()
        conn = sqlite3.connect(DATA / "app.db")
        offline_record = conn.execute(
            "SELECT no_nota FROM service_records WHERE request_id=?",
            ("final-offline-trx-0001",),
        ).fetchone()
        conn.close()
        check("offline transaction reaches server", offline_record is not None, offline_record)
    finally:
        stop_app()
        stop_relay()

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"TOTAL {passed}/{len(results)}")
    report = DATA / "report.json"
    report.write_text(
        json.dumps(
            {
                "passed": passed,
                "total": len(results),
                "results": [
                    {"name": name, "ok": ok, "detail": detail}
                    for name, ok, detail in results
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
