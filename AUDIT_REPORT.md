# LAPORAN AUDIT — BengkelPOS Radiator

**Tanggal audit:** 30 Oktober 2026  
**Mode:** audit read-only (tidak ada kode yang diubah, dihapus, atau di-refactor)  
**Varian yang diaudit:** Web lokal (PC, FastAPI + SQLite di browser) dan APK Android (FastAPI + SQLite di dalam HP via Chaquopy)  
**Status:** selesai — audit awal; temuan ditindaklanjuti lewat rangkaian
perbaikan ARC-* yang terlihat di riwayat Git

> Dokumen ini adalah audit ulang dengan konteks dua varian produk, menggantikan
> dua berkas audit lama (`LAPORAN_AUDIT_BUG_SECURITY_BISNIS.md` dan
> `RENCANA_PERBAIKAN_AUDIT.md`) yang sudah dihapus dari repo. Isinya memuat
> temuan terbaru, termasuk pemeriksaan khusus APK, path database,
> backup/restore, migrasi skema, lifecycle Android, dan kesetaraan perilaku
> bisnis. Karena ditulis sebelum perbaikan, beberapa temuan di bawah sudah
> tidak berlaku pada kode saat ini; riwayat commit adalah sumber status terkini.

---

## 0. Ringkasan Eksekutif

- **Tidak ada perubahan kode.** Hanya membaca, menjalankan test pada database terisolasi, dan membuat dokumen ini.
- **Test otomatis lulus di dua stack:** 64 test lulus pada stack desktop terbaru (Pydantic 2.14.2 / FastAPI 0.162.0 / SQLAlchemy 2.1.6 / uvicorn 0.54.0) dan 64 test lulus pada stack pin APK (Python 3.10 / Pydantic 1.10.18 / FastAPI 0.115.0 / SQLAlchemy 2.0.36 / uvicorn 0.30.6).
- **Namun test belum mencakup hal paling berbahaya:** konkurensi nomor nota, konkurensi stok, retensi backup, kegagalan restore saat server hidup, pencetakan/download di WebView, dan migrasi skema.
- **Temuan: 29 total — 2 Kritis, 11 Tinggi, 10 Sedang, 6 Rendah.**
- **Risiko terbesar untuk pemilik usaha (non-teknis):**
  1. File backup menumpuk tanpa pembersihan; retry Telegram tiap 10 menit membuat file baru. Storage HP/PC bisa penuh dan transaksi baru gagal disimpan (**K-01**).
  2. Web lokal default bind ke `0.0.0.0` tanpa login/PIN; hampir semua endpoint baca/tulis terbuka untuk siapa pun di Wi-Fi toko (**K-02**).
  3. Dua transaksi bersamaan dapat menghasilkan HTTP 500 karena nomor nota bentrok, sehingga penjualan tidak tercatat (**T-01**); ditambah tidak ada idempotensi sehingga retry bisa mencatat penjualan ganda (**T-11**).
  4. Di APK, cetak struk tidak berfungsi dan tombol Backup melaporkan “berhasil” padahal file tidak tersimpan (**T-02**, **T-03**).
  5. Restore backup menghapus token Telegram secara diam-diam, sehingga backup otomatis berhenti (**T-04**), dan belum ada mekanisme migrasi skema untuk update aplikasi (**T-05**).

---

## 1. Kepatuhan Aturan Audit

| Aturan | Status |
|---|---|
| Tidak mengubah/menghapus/refactor kode sebelum disetujui | **Dipatuhi.** Hanya `AUDIT_REPORT.md` yang dibuat. |
| Tidak membaca/menampilkan `.env` asli atau database asli | **Dipatuhi.** Yang dibaca hanya `.env.example`. Uji dinamis memakai database sementara di `%TEMP%` dengan `BACKUP_DIR` sementara. |
| Tidak `git push`, tidak ganti branch tanpa izin | **Dipatuhi.** Branch tetap `main`; tidak ada push. |
| Tidak install paket global | **Dipatuhi.** Hanya memakai `.venv` proyek dan virtualenv sementara yang sudah ada. |
| Menandai “perlu verifikasi” jika tidak yakin | **Dipatuhi.** Semua temuan APK yang tidak bisa dijalankan di mesin ini ditandai eksplisit. |
| Setelah laporan selesai berhenti dan menunggu instruksi | **Dipatuhi.** |

---

## 2. TAHAP 1 — Pemetaan

### 2.1 Struktur proyek (yang diaudit)

```
config.py                 # Settings dari .env + default
run.py                    # runner desktop (script, bukan modul ASGI)
requirements.txt          # dependensi desktop (Pydantic v2)
api/
  app.py                  # create_app, lifespan, CORS, static mount, /api/health, /api/config
  deps.py                 # require_admin_token (fail-closed)
  schemas.py              # skema Pydantic v1/v2-compatible
  pos_routes.py           # transaksi POS, riwayat, struk, klaim garansi
  customer_routes.py      # pelanggan & unit
  stock_routes.py         # stok & harga jasa
  report_routes.py        # laporan, backup, restore
  settings_routes.py      # identitas bengkel & Telegram
services/
  pos_service.py          # atomisitas transaksi, nomor nota, potong stok
  pricing_service.py      # Decimal, diskon, pembayaran, laba kotor
  stock_service.py        # CRUD stok & jasa
  customer_service.py     # validasi pelanggan/unit, label radiator
  warranty_service.py     # masa garansi & klaim
  receipt_service.py      # struk 58/80 mm + ESC/POS + ringkasan nota
  report_service.py       # laporan harian/periode/part terjual
  settings_service.py     # identitas & konfigurasi Telegram
  backup_service.py       # backup SQLite, redaksi token, restore
  telegram_backup_service.py # penjadwal & pengiriman Telegram
repositories/             # query SQLAlchemy
database/
  models.py               # 8 tabel
  session.py              # engine, session, migrasi ringan
  seed.py                 # seed stok/jasa default
frontend/
  index.html, css/style.css
  js/app.js               # SPA kasir
  js/api-client.js        # wrapper fetch
  js/bluetooth-printer.js # Web Bluetooth ESC/POS
android/
  app/src/main/java/...   # PIN, WebView, BackendManager, BackendInstaller, reset
  app/src/main/python/bootstrap.py # uvicorn in-process
  app/build.gradle.kts    # Chaquopy + pin dependensi APK
tests/                    # 64 test backend
```

### 2.2 Alur request (10 baris)

1. Browser (PC) atau WebView (APK) membuka `/`; FastAPI mengembalikan `frontend/index.html` (`api/app.py:154-164`).
2. `app.js` memanggil endpoint `/api/...` lewat `fetch` di `frontend/js/api-client.js`.
3. FastAPI memvalidasi body dengan skema Pydantic (`api/schemas.py`).
4. Router memanggil service terkait (`pos_service`, `stock_service`, `customer_service`, `report_service`, `settings_service`).
5. Service memakai repository SQLAlchemy (`repositories/*`) untuk membaca/menulis model.
6. Engine SQLite global (`database/session.py:45`) memakai `check_same_thread=False` dan `PRAGMA foreign_keys=ON`.
7. Perhitungan uang memakai `Decimal` + kuantisasi `ROUND_HALF_UP` (`services/utils.py:40-50`, `services/pricing_service.py`).
8. Transaksi POS dibungkus `with db.begin()` agar nota + item + potong stok atomik (`services/pos_service.py:55`).
9. Respons diserialisasi Pydantic; `Money` selalu string dua desimal di v1 maupun v2 (`api/schemas.py:20-81`).
10. Frontend merender dengan `esc()` (anti-XSS) lalu mencetak struk via Web Bluetooth atau print browser (`frontend/js/app.js:1326-1439`).

### 2.3 Git dan keberadaan Android

- `git branch -a` → hanya `main`, `remotes/origin/HEAD -> origin/main`, `remotes/origin/main`.
- `git status --short` → bersih (tidak ada perubahan yang belum di-commit).
- **`android/` ADA dan terlacak di `main`.** Premis bahwa folder Android belum ada di main sudah tidak berlaku. Karena hanya ada satu branch, tidak ada pertanyaan perpindahan branch.
- Wrapper Gradle (`gradlew`, `gradlew.bat`, `gradle-wrapper.jar`) tidak ada di repo; ini sudah didokumentasikan di `android/README_APK.md:69-71`.

---

## 3. TAHAP 2 — Uji Otomatis dan Hasil

### 3.1 Hasil perintah

| Pemeriksaan | Perintah | Hasil |
|---|---|---|
| Test desktop terbaru | `.venv/Scripts/python.exe -m pytest -q` | **64 passed**, 1 warning (deprecation `httpx` di Starlette TestClient) |
| Test stack pin APK | `%TEMP%/apkenv/Scripts/python.exe -m pytest -q` | **64 passed**, 1 warning |
| Versi desktop | — | Python 3.12.10, Pydantic 2.14.2, FastAPI 0.162.0, SQLAlchemy 2.1.6, uvicorn 0.54.0 |
| Versi pin APK | — | Python 3.10, Pydantic 1.10.18, FastAPI 0.115.0, SQLAlchemy 2.0.36, uvicorn 0.30.6 |
| Kompilasi | `python -m compileall -q api services repositories database config.py run.py` | **exit 0**, tidak ada syntax error |
| Linter | `ruff` / `flake8` | Tidak terpasang di venv; **tidak** diinstal global sesuai aturan. Tidak dijalankan. |
| ASGI runner | `uvicorn run:app --host 127.0.0.1 --port 8000` | **Gagal:** `Attribute "app" not found in module "run"`. Ini wajar karena `run.py` adalah script, bukan modul `app`. |
| ASGI yang benar | `uvicorn api.app:app --host 127.0.0.1 --port 8011` | Server hidup; `GET /api/health` → **200**. |
| Android lint/build | `./gradlew lint` / `./gradlew assembleDebug` | **Tidak bisa dijalankan**: `java` dan `gradle` tidak ada di PATH; `gradlew` dan `gradle-wrapper.jar` tidak ada. Build APK ditandai **perlu verifikasi**. |
| Frontend statis | Tanpa `package.json`; pencocokan ID DOM | 193 ID dipakai `app.js`, 209 ID ada di `index.html`, tidak ada ID statis yang hilang (hanya pola dinamis `view-`). |

### 3.2 Uji dinamis pada database terisolasi (bukan database asli)

| Uji | Hasil |
|---|---|
| 10 request transaksi bersamaan | **3× HTTP 201, 7× HTTP 500** dengan `UNIQUE constraint failed: service_records.no_nota` |
| `POST /api/stock` tanpa token | **201** (berhasil membuat stok) |
| `DELETE /api/stock/1` tanpa token | **401** (terproteksi) |
| `PUT /api/service-records/1/claim` tanpa token | **200** (klaim garansi berhasil) |
| `PUT /api/stock/1` body `{"jumlah": null}` | **500** |
| `PUT /api/stock/1` body `{"harga_modal": null}` | **200**, modal menjadi **0.00** |
| Hapus seluruh 12 stok lalu restart | 12 stok default **muncul kembali** |
| Backup lalu restore file yang sama | `telegram.configured` berubah **true → false** (token terhapus) |
| Restore saat 8 pembaca aktif | 370 request OK, 0 error — **belum cukup** untuk menyimpulkan restore aman (lihat T-09) |

### 3.3 Kesimpulan Tahap 2

Kode berjalan dan test suite lulus di dua versi dependensi. Namun, **test suite tidak membuktikan keamanan data**: tidak ada test untuk konkurensi, retensi backup, restore saat aktif, migrasi skema, pencetakan APK, download APK, atau port conflict. Temuan di bawah ini sebagian besar berada di celah tersebut.

---

## 4. TAHAP 3 — Temuan

**Definisi severity yang dipakai:**

- **Kritis** — berpotensi kehilangan/kerusakan data, kebocoran data keuangan/pelanggan, atau produk tidak bisa dipakai untuk transaksi.
- **Tinggi** — integritas data/keamanan serius, fitur inti rusak, atau pemulihan mustahil tanpa bantuan teknis.
- **Sedang** — signifikan tetapi ada workaround, atau berdampak pada laporan/usabilitas.
- **Rendah** — minor, kosmetik, atau risiko jangka panjang.

### 4.1 KRITIS

#### K-01 — File backup menumpuk tanpa retensi; retry Telegram membuat file baru setiap 10 menit

- **Severity:** Kritis
- **Lokasi:** `services/backup_service.py:54-75`, `services/telegram_backup_service.py:27`, `services/telegram_backup_service.py:106`, `services/telegram_backup_service.py:208`, `services/backup_service.py:124-127`, `android/app/src/main/python/bootstrap.py:40`
- **Penjelasan:** `create_backup()` selalu membuat file baru `bengkel_radiator_<timestamp>.db`. Tidak ada kode yang menghapus file lama (satu-satunya `unlink` hanya untuk file sementara restore). `send_backup()` membuat backup **sebelum** mencoba mengirim; jika Telegram gagal, file tetap ada dan `should_send()` mengizinkan percobaan ulang setiap `RETRY_MINUTES = 10`. Artinya, saat internet mati atau token salah, aplikasi membuat **hingga 144 file backup per hari**. Restore juga membuat `sebelum_restore_*.db` yang tidak pernah dibersihkan.
- **Dampak UMKM:** Storage HP/PC penuh tanpa disadari. Saat penuh, SQLite gagal menulis sehingga transaksi baru tidak tercatat, dan backup berikutnya juga gagal. Pemilik non-teknis hanya melihat error/transaksi gagal, lalu mungkin melakukan reset yang justru menghapus data.
- **Reproduksi:** Aktifkan Telegram dengan token salah, biarkan aplikasi hidup sehari; atau klik Backup berkali-kali. Periksa folder `backups/`: jumlah file terus bertambah tanpa batas. (Jangan gunakan token asli.)
- **Perbaikan:** Tambahkan retensi + hapus file setelah sukses/gagal + cek ruang disk sebelum transaksi/backup. Contoh:
```python
def _prune_backups(keep: int = 14) -> None:
    files = sorted(
        settings.backup_dir.glob("bengkel_radiator_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in files[keep:]:
        old.unlink(missing_ok=True)
```
Panggil `_prune_backups()` setelah `create_backup()` dan setelah restore; hapus `backup_path` di blok `finally` setelah percobaan kirim (atau simpan hanya N terakhir). Tambahkan juga pengecekan `shutil.disk_usage(settings.backup_dir).free` sebelum membuat backup.

#### K-02 — Web lokal default `0.0.0.0` tanpa login/PIN; endpoint inti terbuka untuk seluruh jaringan

- **Severity:** Kritis
- **Lokasi:** `config.py:91`, `.env.example:9`, `run.py:30-35`, `api/stock_routes.py:29-47`, `api/stock_routes.py:65-76`, `api/pos_routes.py:24-38`, `api/pos_routes.py:71-74`, `api/customer_routes.py:54-59`, `api/customer_routes.py:103-115`, `api/app.py:70-88`.
- **Penjelasan:** Default `APP_HOST` adalah `0.0.0.0`, sehingga server web mendengarkan di semua interface (Wi-Fi toko/rumah). Hampir semua endpoint **baca dan tulis** tidak memakai `require_admin_token`: buat/ubah stok, buat/ubah harga jasa, buat pelanggan/unit, buat transaksi POS, dan klaim garansi. Yang diproteksi hanya DELETE stok/jasa, pengaturan, backup, dan restore. Dokumentasi `/docs` dan `/openapi.json` juga terbuka. Token admin dikirim lewat HTTP polos di LAN, sehingga bisa disadap.
- **Dampak UMKM:** Siapa pun yang terhubung ke Wi-Fi yang sama (pelanggan, tetangga, perangkat lain) dapat membaca data pelanggan, mengubah harga/stok, membuat transaksi palsu, atau mengklaim garansi tanpa sepengetahuan pemilik. Ini adalah kebocoran data dan manipulasi catatan keuangan.
- **Reproduksi:** Dari perangkat lain di LAN: `curl -X POST http://<IP-PC>:8000/api/stock -H "Content-Type: application/json" -d '{"nama":"X","harga_jual":1,"jumlah":999}'` → 201. Atau `curl -X PUT http://<IP-PC>:8000/api/service-records/1/claim` → 200. (Diuji pada server terisolasi; perilaku sama karena kode route tidak membedakan host.)
- **Perbaikan:** Ubah default menjadi loopback dan wajibkan login untuk mode LAN:
```python
app_host = os.getenv("APP_HOST", "127.0.0.1").strip()
app = FastAPI(..., docs_url=None, redoc_url=None, openapi_url=None)
```
Jika LAN memang dibutuhkan, tambahkan sesi login (cookie/JWT) dan pasang dependency auth di **semua** route `/api` kecuali `/api/health`. Jangan mengandalkan CORS sebagai proteksi; CORS hanya membatasi browser, bukan `curl`.

### 4.2 TINGGI

#### T-01 — Balapan nomor nota: transaksi kedua gagal HTTP 500 dan tidak tercatat

- **Severity:** Tinggi
- **Lokasi:** `services/pos_service.py:40-48`, `services/pos_service.py:174`, `repositories/service_record_repository.py:59-61`, `database/models.py:110`
- **Penjelasan:** `_next_nota()` membaca semua nota berprefix hari itu, mengambil nomor tertinggi, lalu menambah 1. Tidak ada lock, counter atomik, atau retry. Dua request yang berjalan bersamaan membaca nomor yang sama; salah satunya melanggar `UNIQUE(no_nota)` dan menghasilkan 500.
- **Dampak UMKM:** Penjualan tidak tercatat; kasir melihat error dan mungkin mengulang, yang berisiko transaksi ganda (lihat T-11). Pada jam sibuk atau dua perangkat, ini bisa terjadi berulang.
- **Reproduksi:** Kirim 10 `POST /api/pos/transaction` paralel untuk unit/part yang sama. Hasil terukur: **3×201, 7×500** dengan `UNIQUE constraint failed: service_records.no_nota`.
- **Perbaikan:** Gunakan counter atomik per hari, atau retry pada `IntegrityError`:
```python
from sqlalchemy.exc import IntegrityError

for _ in range(5):
    try:
        with db.begin():
            # ... susun record dengan _next_nota() ...
            pass
        break
    except IntegrityError:
        db.rollback()
```
Perbaikan yang lebih kuat: tabel `nota_counters(tanggal PRIMARY KEY, terakhir)` dan `UPDATE ... RETURNING`/`INSERT ... ON CONFLICT` agar penomoran tidak pernah balapan.

#### T-02 — APK tidak bisa mencetak struk sama sekali

- **Severity:** Tinggi
- **Lokasi:** `frontend/js/app.js:1326-1379`, `frontend/js/app.js:1382-1439`, `frontend/js/app.js:2954-2959`, `android/app/src/main/java/com/bengkelpos/radiator/MainActivity.kt:127-145`
- **Penjelasan:** Di WebView Android, `navigator.bluetooth` tidak tersedia, sehingga `BluetoothPrinter.isSupported()` false. `printReceipt()` lalu jatuh ke `browserPrint()`. `browserPrint()` memanggil `window.open()`, tetapi WebView disetel `javaScriptCanOpenWindowsAutomatically = false` dan `setSupportMultipleWindows(false)`, sehingga popup diblokir. Fallback iframe memanggil `frame.contentWindow.print()`, yang di WebView Android tidak diimplementasikan (no-op). Tidak ada `WebChromeClient`/`PrintManager` native.
- **Dampak UMKM:** Varian APK — yang ditujukan untuk pemilik yang hanya punya HP — tidak dapat mencetak struk atau bukti garansi. Ini menghilangkan fungsi inti kasir dan membuat bukti servis tidak bisa diberikan.
- **Reproduksi:** Simpan transaksi di APK (auto-print) atau buka struk lalu tekan “Cetak”; tidak ada struk yang keluar dan tidak ada pesan error yang jelas. **Perlu verifikasi di perangkat** karena APK belum bisa di-build di mesin audit.
- **Perbaikan:** Tambahkan jembatan native untuk mencetak:
```kotlin
@JavascriptInterface
fun printHtml(html: String) {
    val wv = WebView(this@MainActivity)
    wv.loadDataWithBaseURL(null, html, "text/html", "utf-8", null)
    val adapter = wv.createPrintDocumentAdapter("Struk")
    val pm = getSystemService(Context.PRINT_SERVICE) as PrintManager
    pm.print("Struk Bengkel", adapter, PrintAttributes.Builder().build())
}
```
Untuk printer thermal, implementasikan ESC/POS lewat Bluetooth Classic/USB di sisi Kotlin, lalu panggil dari JS. Jangan biarkan fallback `window.open` tanpa pesan error.

#### T-03 — Tombol Backup di APK melaporkan “berhasil diunduh” tetapi file tidak tersimpan

- **Severity:** Tinggi
- **Lokasi:** `frontend/js/app.js:2802-2815`, `frontend/js/api-client.js:182-224`, `android/app/src/main/java/com/bengkelpos/radiator/MainActivity.kt:127-203`
- **Penjelasan:** `downloadBackup()` membuat `Blob`, `URL.createObjectURL`, lalu `link.click()`. WebView Android tidak memiliki `DownloadListener` dan tidak menangani blob download secara default; klik tersebut tidak menghasilkan file. Namun frontend langsung menampilkan toast “File backup database berhasil diunduh.”
- **Dampak UMKM:** Pemilik mengira sudah punya backup, padahal tidak ada file. Saat HP hilang/rusak atau data terhapus, tidak ada yang bisa dipulihkan — persis risiko terbesar yang ingin dicegah.
- **Reproduksi:** Di APK: Pengaturan → Backup; toast sukses; periksa folder Downloads/Files → tidak ada file. **Perlu verifikasi di perangkat** karena APK belum bisa di-build di mesin audit; secara kode, tidak ada penanganan download.
- **Perbaikan:** Tangani download secara native:
```kotlin
webView.setDownloadListener { url, _, contentDisposition, mimeType, _ ->
    // Untuk blob:, minta JS mengirim base64 lewat bridge dan tulis ke MediaStore/SAF.
    // Untuk http(s), gunakan DownloadManager.
}
```
Ubah frontend agar hanya menampilkan sukses setelah native mengonfirmasi file tertulis. Untuk blob, gunakan `window.BengkelNative.saveFile(filename, base64)`.

#### T-04 — Restore backup menghapus token Telegram; backup otomatis berhenti diam-diam

- **Severity:** Tinggi
- **Lokasi:** `services/backup_service.py:35-51`, `services/backup_service.py:74`, `services/settings_service.py:118`, `services/telegram_backup_service.py:100-103`
- **Penjelasan:** Backup meredaksi `telegram.bot_token` menjadi string kosong. Saat file itu di-restore, baris `app_settings` berisi `''`. `get_telegram_config()` memakai `stored.get("bot_token", settings.telegram_bot_token)`; karena key ada (walau kosong), nilai `''` menang dan default `.env` tidak dipakai. `configured` menjadi false dan `send_backup()` menolak mengirim.
- **Dampak UMKM:** Setelah restore (misalnya setelah ganti HP atau reset), pemilik mengira backup otomatis tetap berjalan. Padahal tidak; tidak ada notifikasi. Backup terakhir bisa jadi sudah lama, dan kehilangan data berikutnya tidak terlindungi.
- **Reproduksi:** Isi token/chat, lakukan backup, restore file yang sama, lalu `GET /api/config` → `telegram.configured: false`. Terukur: true → false.
- **Perbaikan:** Perlakukan nilai kosong sebagai “tidak diatur”, dan beri peringatan setelah restore:
```python
"bot_token": stored.get("bot_token") or settings.telegram_bot_token,
"chat_id": stored.get("chat_id") or settings.telegram_chat_id,
```
Setelah restore, jika `configured` false, tampilkan banner “Token Telegram perlu diisi ulang” di menu Pengaturan. Jangan menyimpan token ke backup yang dibagikan; gunakan fallback dari konfigurasi aman/keystore.

#### T-05 — Tidak ada versi skema atau migrasi umum; update APK berisiko membuat data lama tidak terbaca

- **Severity:** Tinggi
- **Lokasi:** `database/session.py:63-99`, `api/app.py:55-57`, `database/models.py`
- **Penjelasan:** `init_db()` hanya menjalankan `Base.metadata.create_all()` (tidak mengubah tabel lama) dan satu migrasi khusus `service_parts.harga_modal`. Tidak ada `schema_version`, tidak ada daftar migrasi berurutan, dan tidak ada pengecekan saat startup. Jika versi baru menambah kolom/tabel/index, database lama di `filesDir` tetap tanpa kolom itu; query langsung `OperationalError: no such column`.
- **Dampak UMKM:** Setelah update APK, aplikasi bisa gagal membuka data lama. Pemilik non-teknis mungkin memilih “Lupa PIN → reset” (menghapus data) atau restore backup (yang juga bisa menghapus token). Ini adalah jalur kehilangan data yang nyata, meski belum terjadi pada skema saat ini.
- **Reproduksi:** Tambahkan satu kolom ke model, jalankan kode baru terhadap database lama; query yang memakai kolom itu akan 500/gagal start. **Perlu verifikasi** pada percobaan skema baru.
- **Perbaikan:** Gunakan `PRAGMA user_version` + migrasi berurutan, dan backup otomatis sebelum migrasi:
```python
MIGRATIONS = [(1, _migrate_001), (2, _migrate_002)]

def _apply_migrations(conn) -> None:
    current = conn.exec_driver_sql("PRAGMA user_version").scalar() or 0
    for version, migrate in MIGRATIONS:
        if version > current:
            migrate(conn)
            conn.exec_driver_sql(f"PRAGMA user_version={version}")
```
Jalankan sebelum melayani request; jika gagal, tampilkan pesan jelas dan jangan sentuh data. Simpan backup `pre_migrate_*.db` dengan retensi.

#### T-06 — Server dan penjadwal backup mati saat proses aplikasi dibunuh (tidak ada foreground service/WorkManager)

- **Severity:** Tinggi
- **Lokasi:** `android/app/src/main/AndroidManifest.xml:9-40` (tidak ada service), `android/app/src/main/python/bootstrap.py:61` (daemon thread), `api/app.py:59-60` (scheduler di proses), `services/telegram_backup_service.py:226-235`
- **Penjelasan:** Uvicorn berjalan sebagai daemon thread di dalam proses aplikasi. Penjadwal Telegram adalah `asyncio` task di proses yang sama. Tidak ada foreground service, `WorkManager`, atau `AlarmManager`. Saat layar mati/aplikasi di latar belakang, Android dapat membunuh proses (terutama di HP RAM kecil); server dan penjadwal ikut mati. Backup “harian 21:00” hanya berjalan jika proses kebetulan hidup; catch-up hanya terjadi saat aplikasi dibuka dan scheduler berjalan.
- **Dampak UMKM:** Pemilik mengandalkan backup otomatis, tetapi backup tidak dikirim karena aplikasi tidak sedang dibuka pada jam tersebut. Jika HP rusak/hilang sebelum aplikasi dibuka lagi, backup terakhir bisa tertinggal beberapa hari.
- **Reproduksi:** Set jam 21:00, tutup aplikasi (swipe away), tunggu lewat jam 21:00 → tidak ada pesan Telegram. **Perlu verifikasi di perangkat** karena perilaku pembunuhan proses bergantung pada OEM/Android.
- **Perbaikan:** Jadwalkan backup dengan `WorkManager`/`AlarmManager` dan jalankan upload di foreground service (atau worker dengan `setForeground`). Contoh konsep:
```kotlin
val work = PeriodicWorkRequestBuilder<BackupWorker>(1, TimeUnit.DAYS).build()
WorkManager.getInstance(context)
    .enqueueUniquePeriodicWork("telegram-backup", ExistingPeriodicWorkPolicy.UPDATE, work)
```
`BackupWorker` memanggil logika backup/Telegram yang sama (lebih baik diekstrak ke endpoint internal atau kode Kotlin). Untuk jam tepat 21:00, gunakan `AlarmManager` yang memicu worker.

#### T-07 — `BackendManager.running` macet; port 8000 bentrok membuat “Coba Lagi” tidak pernah berhasil

- **Severity:** Tinggi
- **Lokasi:** `android/app/src/main/java/com/bengkelpos/radiator/backend/BackendManager.kt:15-36`, `android/app/src/main/python/bootstrap.py:29-63`, `android/app/src/main/java/com/bengkelpos/radiator/MainActivity.kt:206-229`
- **Penjelasan:** `start()` menyetel `running = true` **sebelum** thread uvicorn benar-benar bind. `bootstrap.start()` hanya membuat thread dan langsung kembali; jika `server.run` gagal karena port 8000 sudah dipakai (atau error lain), thread mati tetapi `running` tetap true. Pemanggilan `start()` berikutnya langsung `return`, sehingga tombol “Coba Lagi” tidak melakukan apa pun.
- **Dampak UMKM:** Aplikasi menampilkan “backend error” permanen; satu-satunya jalan adalah force-stop/clear data. Bagi pemilik non-teknis, aplikasi tampak rusak total. Port 8000 cukup umum dipakai aplikasi lain.
- **Reproduksi:** Jalankan proses lain di port 8000, buka APK → error; tekan “Coba Lagi” berulang → tetap error. **Perlu verifikasi di perangkat**, tetapi logikanya pasti dari kode.
- **Perbaikan:** Reset `running` jika health check gagal, dan/atau pilih port dinamis:
```kotlin
val ready = BackendHealth.awaitReady()
if (!ready) synchronized(lock) { running = false }
```
Di `start()`, cek juga `_thread?.isAlive()`; jika tidak hidup, paksa start ulang. Lebih baik: cari port kosong (mis. 8000–8010), oper port itu ke `bootstrap.start` dan ke `BackendHealth`/`APP_URL`.

#### T-08 — Race stok: dua transaksi bersamaan dapat oversell atau kehilangan update stok

- **Severity:** Tinggi (perlu verifikasi)
- **Lokasi:** `services/pos_service.py:126-146`, `services/pos_service.py:219-221`
- **Penjelasan:** Pengecekan `stock.jumlah < needed` dan pengurangan `stock_items[stock_id].jumlah -= needed` dilakukan di dalam transaksi Python, tanpa row lock atau conditional update. Dua transaksi dapat membaca stok yang sama (mis. 1) sebelum salah satunya menulis. Hasilnya bisa: (a) keduanya lolos dan stok menjadi 0 padahal terjual 2 (oversell), atau (b) salah satu mendapat `database is locked`/500, atau (c) update terakhir menimpa update pertama (lost update).
- **Dampak UMKM:** Stok fisik dan catatan tidak cocok; laporan stok/laba salah; barang bisa dijanjikan padahal tidak ada. Ini adalah integritas data inti.
- **Reproduksi:** Stok = 1; kirim dua transaksi paralel qty 1 dengan nomor nota berbeda (untuk menghindari T-01). Amati apakah keduanya 201 dan stok menjadi 0, atau salah satu 500. **Perlu verifikasi** dengan skrip paralel.
- **Perbaikan:** Lakukan pengurangan secara atomik dan cek `rowcount`:
```python
updated = db.execute(
    update(StockItem)
    .where(StockItem.id == sid, StockItem.jumlah >= needed)
    .values(jumlah=StockItem.jumlah - needed)
).rowcount
if updated == 0:
    raise InsufficientStockError([...])
```
Untuk SQLite, gunakan `BEGIN IMMEDIATE` pada awal transaksi agar penulisan diserialisasi. Tangani `izinkan_stok_minus` secara terpisah dengan update tanpa kondisi stok cukup.

#### T-09 — Restore saat server hidup tanpa mode maintenance berisiko kehilangan transaksi yang sedang berjalan

- **Severity:** Tinggi (perlu verifikasi)
- **Lokasi:** `api/report_routes.py:82-89`, `services/backup_service.py:120-136`
- **Penjelasan:** `restore_backup()` menyalin file baru ke `target` setelah `engine.dispose()`. Namun `dispose()` hanya menutup koneksi di pool; sesi yang sedang dipakai request lain tetap hidup. Request yang sedang menulis dapat menulis ke database lama (inode lama di Linux/Android) atau gagal `database is locked`. Di Windows, `shutil.move` ke file yang sedang dibuka bisa gagal. Uji 8 pembaca paralel tidak menghasilkan error, tetapi itu bukan bukti aman untuk penulisan.
- **Dampak UMKM:** Transaksi yang tampak berhasil bisa hilang setelah restore, atau restore gagal di tengah. Karena restore biasanya dilakukan saat panik (data rusak), risiko salah langkah tinggi.
- **Reproduksi:** Mulai transaksi/laporan panjang, lalu `POST /api/admin/restore` bersamaan; amati 500/locked/kehilangan tulisan. **Perlu verifikasi** dengan skenario tulis, bukan hanya baca.
- **Perbaikan:** Aktifkan mode maintenance: set flag global, tolak request baru dengan 503, tunggu request aktif selesai, tutup semua sesi, baru tukar file. Setelah restore, restart server (di APK: hentikan lalu start ulang) agar semua koneksi memakai file baru:
```python
RESTORING = threading.Event()

@app.middleware("http")
async def maintenance(request, call_next):
    if RESTORING.is_set() and request.url.path != "/api/health":
        return JSONResponse({"detail": "Sedang memulihkan database."}, status_code=503)
    return await call_next(request)
```

#### T-10 — API localhost APK dapat diakses aplikasi lain di HP tanpa autentikasi

- **Severity:** Tinggi
- **Lokasi:** `android/app/src/main/python/bootstrap.py:35` (bind `127.0.0.1`), `api/pos_routes.py:24-74`, `api/customer_routes.py:54-115`, `api/stock_routes.py:29-47`, `api/stock_routes.py:65-76`, `MainActivity.kt:265-271`
- **Penjelasan:** Server hanya mendengarkan loopback, tetapi loopback Android **tidak terisolasi per aplikasi**. Aplikasi lain di HP yang memiliki izin `INTERNET` dapat memanggil `http://127.0.0.1:8000`. Endpoint inti (baca pelanggan/transaksi, buat transaksi, ubah stok, klaim garansi) tidak memerlukan token; token admin hanya untuk sebagian aksi. `isLocalUrl` juga menerima semua port localhost, bukan hanya 8000.
- **Dampak UMKM:** Aplikasi berbahaya atau “keyboard/tool” nakal yang terpasang dapat membaca nomor HP pelanggan dan riwayat transaksi, atau memanipulasi stok/garansi. Tidak perlu akses root.
- **Reproduksi:** Dari aplikasi uji/adb di perangkat: `curl http://127.0.0.1:8000/api/service-records` → 200 berisi data. **Perlu verifikasi di perangkat**; secara kode, route tidak memeriksa token.
- **Perbaikan:** Wajibkan token per-instalasi (yang sudah disuntikkan ke WebView) di **semua** route `/api` kecuali `/api/health`, dan batasi `isLocalUrl` ke `http://127.0.0.1:8000` saja. Contoh:
```python
app.include_router(customer_routes.router, prefix=api_prefix, dependencies=[Depends(require_admin_token)])
```
Frontend APK sudah memiliki `window.__BENGKEL_ADMIN_TOKEN__`, jadi tinggal mengirim header di semua request. Untuk web, gunakan sesi login, bukan token yang diketik manual.

#### T-11 — Tidak ada idempotensi transaksi; retry/double-submit dapat mencatat penjualan ganda

- **Severity:** Tinggi
- **Lokasi:** `api/pos_routes.py:24-38`, `api/schemas.py:187-200`, `frontend/js/app.js:1166-1243`, `frontend/js/api-client.js:110-115`
- **Penjelasan:** `state.saving` hanya mencegah klik ganda di **satu tab**. Tidak ada `request_id`/idempotency key di request maupun unique constraint di database. Jika response hilang karena timeout, browser di-refresh, atau dua perangkat mengirim payload yang sama, backend membuat dua `ServiceRecord` dan memotong stok dua kali.
- **Dampak UMKM:** Penjualan dan stok tercatat ganda; laporan omset/laba membengkak; stok fisik berkurang dua kali. Koreksi manual kemudian merusak jejak audit (lihat S-06).
- **Reproduksi:** Kirim dua `POST /api/pos/transaction` dengan payload identik (mis. dari dua tab/perangkat) → dua nota berbeda dibuat. Tidak ada penolakan duplikat.
- **Perbaikan:** Tambahkan `request_id` unik dari klien dan unique index; bila duplikat, kembalikan record yang sudah ada:
```python
class CreateServiceTransactionRequest(CompatBase):
    request_id: str = Field(..., min_length=8, max_length=64)
```
```python
try:
    ...
except IntegrityError:
    existing = db.scalar(select(ServiceRecord).where(ServiceRecord.request_id == payload.request_id))
    if existing:
        return existing
    raise
```
Di frontend, buat `request_id` sekali per percobaan simpan (bukan per retry) dan kirim ulang ID yang sama saat retry.

### 4.3 SEDANG

#### S-01 — Field nullable pada update stok/jasa: `null` menyebabkan 500 atau menimpa harga/modal menjadi 0.00

- **Severity:** Sedang
- **Lokasi:** `api/schemas.py:139-144`, `api/schemas.py:161-163`, `api/stock_routes.py:42-47`, `api/stock_routes.py:71-76`, `services/stock_service.py:85-94`, `services/stock_service.py:129-139`
- **Penjelasan:** `StockItemUpdate.jumlah` bertipe `Optional[int]`, sehingga body `{"jumlah": null}` lolos validasi. Service memakai `values.get("jumlah", item.jumlah)`, yang mengembalikan `None` (key ada), lalu `int(None)` → TypeError → 500. `{"harga_modal": null}` lolos ke `money(None)` → `0.00` dan menimpa modal tanpa error. Hal yang sama terjadi pada `HargaJasaUpdate.harga_standar`.
- **Dampak UMKM:** Edit stok bisa error 500, atau lebih berbahaya, modal/harga jasa berubah menjadi 0 tanpa peringatan. Laba kotor dan harga layanan menjadi salah; pemilik tidak menyadari.
- **Reproduksi:** `PUT /api/stock/1` body `{"jumlah": null}` → 500; body `{"harga_modal": null}` → 200 dan modal 0.00. Terukur pada server terisolasi.
- **Perbaikan:** Tolak `null` untuk field yang dikirim:
```python
for key in ("nama", "harga_modal", "harga_jual", "jumlah"):
    if key in values and values[key] is None:
        raise BusinessValidationError(f"{key} tidak boleh null.")
```
Atau gunakan `model_dump(exclude_unset=True, exclude_none=True)` **hanya jika** perilaku “null = abaikan” memang diinginkan; saat ini perilakunya tidak konsisten (nama → 400, jumlah → 500, modal → 0).

#### S-02 — Master yang sengaja dihapus hidup kembali (seed setiap start dan setiap restore)

- **Severity:** Sedang
- **Lokasi:** `database/seed.py:43-66`, `api/app.py:56-57`, `services/backup_service.py:133-136`
- **Penjelasan:** `seed_defaults()` hanya memeriksa `COUNT(*) == 0`. Jika pemilik menghapus seluruh stok atau seluruh jasa (karena tidak menjual item default), setiap restart akan memasukkan kembali 12 stok/10 jasa default. Restore juga memanggil seed, sehingga backup yang sengaja berisi katalog kosong tidak dipulihkan apa adanya.
- **Dampak UMKM:** Data yang sengaja dihapus muncul lagi; nilai stok/laporan menjadi salah; pemilik tidak bisa memiliki katalog kosong. Setelah restore, kondisi data tidak sama dengan backup.
- **Reproduksi:** Hapus 12 stok, restart aplikasi, `GET /api/stock` → 12 stok default kembali. Terukur.
- **Perbaikan:** Seed hanya sekali pada database baru, dengan penanda:
```python
if settings_service.get_setting(db, "seed.done"):
    return
# ... seed ...
settings_service.set_setting(db, "seed.done", "1")
```
Jangan panggil `seed_defaults()` setelah restore.

#### S-03 — `garansi_aktif` menghitung garansi yang sudah diklaim; status bisa kontradiktif

- **Severity:** Sedang
- **Lokasi:** `services/warranty_service.py:36-49`, `services/report_service.py:52-60`, `services/receipt_service.py:213`
- **Penjelasan:** `is_active()` hanya memeriksa `bergaransi` dan tanggal, tidak memeriksa `status_klaim == "Sudah claim"`. Akibatnya struk bisa menampilkan `garansi_aktif: true` bersamaan dengan `warranty_status: "SUDAH CLAIM"`. Laporan `garansi_aktif` juga menghitung nota yang sudah diklaim. Selain itu, pada laporan periode, angka `garansi_aktif` dihitung global untuk setiap baris harian (bukan per hari).
- **Dampak UMKM:** Pemilik bisa mengabulkan klaim kedua karena melihat “garansi aktif”, atau salah membaca jumlah garansi yang masih berjalan. Laporan garansi tidak akurat.
- **Reproduksi:** Klaim satu nota, lalu buka struk: `garansi_aktif` tetap true dan `warranty_status` SUDAH CLAIM. Laporan tidak berubah setelah klaim.
- **Perbaikan:**
```python
def is_active(record, today=None):
    if record.status_klaim == "Sudah claim":
        return False
    ...
```
Dan filter count dengan `ServiceRecord.status_klaim != "Sudah claim"`; untuk laporan harian, hitung per hari atau ganti label menjadi “garansi aktif saat ini”.

#### S-04 — Query N+1 dan laporan periode O(hari × nota); lambat di HP kelas bawah

- **Severity:** Sedang
- **Lokasi:** `repositories/service_record_repository.py:17-56`, `services/receipt_service.py:179-217`, `services/report_service.py:29-73`, `services/report_service.py:87-108`, `services/report_service.py:111-160`, `api/report_routes.py:41-64`
- **Penjelasan:** `list_records()`, `records_between()`, dan `all_records()` tidak memakai eager loading. `record_summary()` mengakses `record.unit`, `unit.customer`, `record.parts`, `part.stock_item`, dan `record.jobs` secara lazy untuk **setiap** record → N+1 query. `period_report()` memanggil `_summarize_records()` untuk setiap hari dalam rentang (hingga 365 kali), dan setiap panggilan menjalankan query count garansi global. `sold_parts_report()` tanpa tanggal memuat seluruh riwayat ke memori. Riwayat nota juga dibatasi 200 tanpa pagination (`api/pos_routes.py:41-50`).
- **Dampak UMKM:** Di HP kelas bawah dengan ribuan nota, membuka Laporan atau Riwayat bisa memakan waktu lama, memicu ANR, atau kehabisan memori. Pemilik mengira aplikasi hang.
- **Reproduksi:** Isi database dengan beberapa ribu nota, buka laporan 1 tahun dan “Semua waktu”; ukur waktu/ANR. **Perlu verifikasi** dengan data volume produksi.
- **Perbaikan:** Eager loading + agregasi sekali jalan:
```python
stmt = select(ServiceRecord).options(
    selectinload(ServiceRecord.parts),
    selectinload(ServiceRecord.jobs),
    selectinload(ServiceRecord.unit).selectinload(VehicleOrUnit.customer),
)
```
Di `period_report`, kelompokkan record per tanggal dalam satu pass dan hitung ringkasan tanpa memanggil `_summarize_records` 365 kali. Tambahkan pagination untuk riwayat dan sold-parts.

#### S-05 — Restore membaca seluruh file upload ke RAM tanpa batas ukuran

- **Severity:** Sedang
- **Lokasi:** `api/report_routes.py:86-88`, `services/backup_service.py:78-88`
- **Penjelasan:** `data = await file.read()` memuat seluruh isi backup ke memori sebelum validasi. Tidak ada batas ukuran. Di HP 2 GB, upload 50–200 MB dapat menyebabkan OOM/ANR; di PC, ini juga pemborosan.
- **Dampak UMKM:** Restore backup besar gagal di tengah, atau aplikasi crash. Karena restore biasanya dilakukan saat data bermasalah, kegagalan ini memperburuk situasi.
- **Reproduksi:** Upload file besar (atau database valid berukuran besar) ke `/api/admin/restore`; amati lonjakan memori/500. **Perlu verifikasi** dengan file besar.
- **Perbaikan:** Streaming ke file sementara + batas ukuran:
```python
MAX_RESTORE_BYTES = 64 * 1024 * 1024
size = 0
with tempfile.NamedTemporaryFile(delete=False) as tmp:
    while chunk := await file.read(1 << 20):
        size += len(chunk)
        if size > MAX_RESTORE_BYTES:
            raise HTTPException(status_code=413, detail="File backup terlalu besar.")
        tmp.write(chunk)
```
Lalu ubah `restore_backup()` untuk menerima path, bukan bytes.

#### S-06 — Tidak ada void/retur; koreksi stok manual menghapus jejak audit

- **Severity:** Sedang
- **Lokasi:** `api/pos_routes.py:24-74` (tidak ada endpoint void/delete), `services/stock_service.py:72-106`, `services/pos_service.py:219-221`
- **Penjelasan:** Tidak ada fitur pembatalan/retur transaksi. Satu-satunya cara “mengoreksi” adalah mengedit stok manual (`PUT /api/stock/{id}`) atau menghapus stok. Tidak ada tabel ledger pergerakan stok, alasan koreksi, atau status VOID. Nota yang salah tetap masuk laporan.
- **Dampak UMKM:** Salah input tidak bisa dibatalkan dengan benar; stok diedit manual tanpa jejak, sehingga stok fisik dan catatan makin tidak cocok. Laporan omset/laba tetap memuat transaksi yang seharusnya batal.
- **Reproduksi:** Buat transaksi, cari tombol/endpoint batal → tidak ada. Edit stok manual → stok berubah tetapi nota/omset tetap.
- **Perbaikan:** Tambahkan status `VOID` pada `ServiceRecord`, endpoint void yang mengembalikan stok secara atomik, dan ledger `stock_movements` (masuk/keluar/koreksi + alasan + user/waktu). Sertakan `void` dalam laporan sebagai pengurang, bukan menghapus baris.

#### S-07 — Token Telegram plaintext; redaksi backup tidak forensik; salinan `sebelum_restore` tidak diredaksi

- **Severity:** Sedang
- **Lokasi:** `services/settings_service.py:147-163`, `database/models.py:200-204`, `services/backup_service.py:35-51`, `services/backup_service.py:124-127`
- **Penjelasan:** Token bot disimpan sebagai teks biasa di `app_settings`. `_redact_secrets()` menjalankan `UPDATE ... value=''`, tetapi SQLite tidak menghapus isi halaman lama; token bisa tersisa di free page/WAL dan masih dapat ditemukan dengan alat forensik. Salinan keamanan `sebelum_restore_*.db` adalah salinan **tanpa redaksi** dan disimpan tanpa pembersihan.
- **Dampak UMKM:** Jika file backup/salinan bocor atau HP/PC diakses orang lain, token bot bisa diambil dan dipakai untuk mengirim pesan/menyalahgunakan bot. Ini pernah menjadi insiden nyata; risikonya berulang.
- **Reproduksi:** Set token, buat backup, cari string token di file backup setelah redaksi (perlu verifikasi); periksa `sebelum_restore_*.db` → token masih ada.
- **Perbaikan:** Gunakan `PRAGMA secure_delete=ON` + `VACUUM` setelah redaksi; enkripsi backup; hapus/redaksi salinan `sebelum_restore` setelah restore sukses; simpan token di keystore/OS credential store, bukan SQLite. Contoh:
```python
connection.execute("PRAGMA secure_delete=ON")
connection.execute("UPDATE app_settings SET value='' WHERE key='telegram.bot_token'")
connection.execute("VACUUM")
```

#### S-08 — `UI_ACCESS_TOKEN` kosong membuat fitur admin 503; placeholder publik bisa menjadi token yang diketahui

- **Severity:** Sedang (bisa menjadi Tinggi jika `.env` disalin tanpa diubah)
- **Lokasi:** `config.py:94`, `api/deps.py:20-28`, `frontend/js/app.js:2575-2593`, `frontend/js/app.js:2802-2815`, `.env.example:11-12`
- **Penjelasan:** Jika `UI_ACCESS_TOKEN` kosong (mis. `.env` belum dibuat), `require_admin_token()` fail-closed dengan 503. Tetapi `admin_token_required` bernilai false, sehingga frontend tidak meminta token; tombol Backup/Hapus/Pengaturan langsung gagal dengan pesan 503 yang membingungkan. Sebaliknya, jika `.env.example` disalin apa adanya, token adalah string placeholder yang diketahui publik; siapa pun di LAN dapat memakainya untuk DELETE stok/pengaturan/backup/restore.
- **Dampak UMKM:** Fitur admin tidak bisa dipakai tanpa penjelasan, atau (lebih buruk) tindakan destruktif dapat diotorisasi dengan token default yang diketahui.
- **Reproduksi:** Jalankan tanpa `.env`; klik Backup → 503 “Token admin belum dikonfigurasi”. Atau gunakan token placeholder untuk `DELETE /api/stock/1` → 204.
- **Perbaikan:** Tolak startup jika token kosong/placeholder, atau buat token acak saat pertama kali dijalankan dan simpan aman:
```python
if not settings.ui_access_token or settings.ui_access_token.startswith("ganti-dengan-"):
    raise RuntimeError("Set UI_ACCESS_TOKEN yang kuat di .env sebelum menjalankan aplikasi.")
```
Tampilkan pesan yang jelas di UI jika server mengembalikan 503.

#### S-09 — `AUTO_BACKUP_ENABLED` dan `SECRET_KEY` tidak dipakai; rasa aman palsu

- **Severity:** Sedang
- **Lokasi:** `config.py:93`, `config.py:118`, `api/app.py:59-60`, `.env.example` (bagian backup)
- **Penjelasan:** `AUTO_BACKUP_ENABLED=true` ada di `.env.example`, tetapi tidak ada kode yang membacanya untuk menjadwalkan backup lokal. Yang berjalan hanya penjadwal Telegram (jika dikonfigurasi). `SECRET_KEY` juga tidak dipakai untuk apa pun (tidak ada sesi/token bertanda tangan).
- **Dampak UMKM:** Pemilik menyalakan `AUTO_BACKUP_ENABLED` dan mengira backup lokal otomatis berjalan; sebenarnya tidak ada backup sampai Telegram diatur. Jika Telegram tidak diatur, tidak ada backup sama sekali.
- **Reproduksi:** Set `AUTO_BACKUP_ENABLED=true`, tanpa Telegram, jalankan aplikasi beberapa hari → tidak ada file backup baru.
- **Perbaikan:** Implementasikan penjadwal backup lokal dengan retensi, atau hapus flag tersebut dan dokumentasikan bahwa backup otomatis hanya lewat Telegram. Gunakan `SECRET_KEY` untuk sesi login, atau hapus dari konfigurasi agar tidak menyesatkan.

#### S-10 — Part yang tidak terhubung ke stok tidak menyumbang laba kotor (laba understated)

- **Severity:** Sedang
- **Lokasi:** `services/pricing_service.py:76-85`, `services/receipt_service.py:183-190`, `services/report_service.py:39-50`
- **Penjelasan:** Untuk part yang dimasukkan manual (tanpa `stock_item_id`), `harga_modal` bernilai `None`. `calculate_gross_profit()`, `record_summary()`, dan `_summarize_records()` **melewati** baris tersebut sepenuhnya. Artinya, seluruh nilai penjualan part itu tidak dihitung sebagai laba, bukan dihitung dengan modal 0.
- **Dampak UMKM:** Laporan laba kotor terlalu rendah; pemilik bisa salah menilai margin, terutama untuk part yang dibeli di luar stok. Omset tetap benar, tetapi laba tidak.
- **Reproduksi:** Buat transaksi dengan part manual (tanpa stok) senilai Rp100.000; lihat `laba_kotor` → tidak bertambah Rp100.000.
- **Perbaikan:** Wajibkan `harga_modal` untuk part manual, atau tampilkan peringatan “laba tidak dihitung untuk part tanpa modal”, atau hitung dengan modal 0 secara eksplisit dan beri label. Jangan diam-diam melewati baris.

### 4.4 RENDAH

#### R-01 — Klaim garansi tanpa lock/idempotensi; dua klik dapat menimpa tanggal klaim

- **Severity:** Rendah
- **Lokasi:** `services/warranty_service.py:52-74`
- **Penjelasan:** `claim_warranty()` membaca status, lalu menulis `Sudah claim` dan commit. Dua request bersamaan dapat sama-sama lolos pengecekan; hasil akhirnya tetap “Sudah claim”, tetapi `tanggal_klaim` bisa tertimpa. Tidak ada respons “sudah pernah diklaim” untuk request kedua.
- **Dampak UMKM:** Tidak menyebabkan kerugian besar, tetapi status klaim bisa membingungkan.
- **Perbaikan:** Gunakan conditional update `WHERE status_klaim='Belum claim'` dan periksa `rowcount`; kembalikan 409 jika 0.

#### R-02 — Label radiator `_next_radiator_label` dapat duplikat saat request bersamaan

- **Severity:** Rendah
- **Lokasi:** `services/customer_service.py:48-59`, `services/customer_service.py:104-115`, `database/models.py:58`
- **Penjelasan:** Label `RAD-YYYYMMDD-XXX` dihitung dengan scan + 1, tanpa unique constraint dan tanpa retry. Dua unit RADIATOR_ONLY yang dibuat bersamaan bisa mendapat label sama.
- **Dampak UMKM:** Dua radiator fisik bisa memiliki label yang sama; pencarian/identifikasi unit menjadi kacau.
- **Perbaikan:** Tambahkan unique index pada `label_radiator` dan retry saat `IntegrityError`, atau gunakan counter atomik seperti T-01.

#### R-03 — Tidak ada test frontend/APK; wrapper Gradle tidak ada di repo

- **Severity:** Rendah
- **Lokasi:** `tests/` (hanya backend), `android/README_APK.md:69-71`, `android/gradle/wrapper/`
- **Penjelasan:** Tidak ada test otomatis untuk `app.js`, alur cetak, download, atau WebView. `gradlew`, `gradlew.bat`, dan `gradle-wrapper.jar` tidak ada; build APK tidak reproducible dari repo tanpa membuat wrapper terlebih dahulu.
- **Dampak UMKM:** Regresi UI/cetak/backup tidak terdeteksi sampai pengguna menemukannya; build APK bergantung pada langkah manual.
- **Perbaikan:** Tambahkan test end-to-end (Playwright) untuk alur transaksi/backup, dan commit Gradle wrapper (`gradle wrapper --gradle-version 8.7`) beserta CI build.

#### R-04 — `requirements.txt` tidak APK-safe (`uvicorn[standard]`, `pydantic>=2.7`)

- **Severity:** Rendah
- **Lokasi:** `requirements.txt:4-10`, `android/app/build.gradle.kts:79-105`
- **Penjelasan:** `uvicorn[standard]` menarik `uvloop`/`httptools`/`watchfiles` (native), dan `pydantic>=2.7` membutuhkan `pydantic-core` (Rust). Keduanya tidak tersedia di Chaquopy. Build APK sudah benar memakai pin pure-Python terpisah, tetapi tidak ada penjaga yang mencegah seseorang menjalankan `pip install -r requirements.txt` di lingkungan APK.
- **Dampak UMKM:** Jika proses build APK diubah tanpa memahami pin, build bisa gagal atau memasang paket yang tidak kompatibel.
- **Perbaikan:** Pertahankan `build.gradle.kts` sebagai sumber kebenaran; tambahkan komentar/CI check yang membandingkan pin APK dengan versi yang diuji; jangan gunakan `requirements.txt` untuk Chaquopy.

#### R-05 — Laporan “Semua waktu” berhenti di jendela 366 hari pertama yang kosong

- **Severity:** Rendah
- **Lokasi:** `frontend/js/app.js:2347-2361`, `frontend/js/app.js:2318-2345`
- **Penjelasan:** `loadAllTimePeriod()` memecah riwayat menjadi jendela 366 hari dan berhenti pada jendela pertama yang `jumlah_transaksi == 0`. Jika bengkel sempat tutup lebih dari satu tahun, data yang lebih lama tidak akan dimuat. Selain itu, `mergePeriodChunks()` menjumlahkan `jumlah_unit_servis` per chunk, sehingga unit yang sama yang diservis di dua periode dihitung dua kali.
- **Dampak UMKM:** Laporan “Semua waktu” bisa menampilkan omset/unit yang lebih kecil atau jumlah unit yang salah.
- **Perbaikan:** Jangan berhenti pada jendela kosong; gunakan tanggal nota tertua sebagai batas, atau lanjutkan hingga 20 jendela tanpa data. Untuk unit, hitung distinct unit dari data transaksi yang digabung, bukan menjumlahkan angka per chunk.

#### R-06 — Backfill `harga_modal` saat startup dapat mengubah laba historis

- **Severity:** Rendah
- **Lokasi:** `database/session.py:88-93`
- **Penjelasan:** Setiap startup menjalankan `UPDATE service_parts SET harga_modal = (SELECT harga_modal FROM stock_items ...) WHERE harga_modal IS NULL`. Untuk nota lama yang belum memiliki snapshot, modal diisi dengan harga master **saat ini**, bukan harga saat transaksi. Jika harga master sudah berubah, laba historis ikut berubah.
- **Dampak UMKM:** Laba masa lalu bisa naik/turun setelah update harga stok; laporan tidak stabil.
- **Perbaikan:** Lakukan backfill sekali saat migrasi dengan penanda versi, dan catat bahwa nilai itu adalah estimasi. Jangan jalankan backfill berulang setiap startup.

---

## 5. Jawaban Langsung atas Pertanyaan Audit

### 5.1 Apakah ada bug?

**Ya.** Bug yang terkonfirmasi secara dinamis:

- Nomor nota balapan → 7 dari 10 transaksi paralel gagal 500 (T-01).
- `PUT /api/stock` dengan `jumlah: null` → 500; `harga_modal: null` → modal 0.00 (S-01).
- Hapus seluruh stok lalu restart → 12 stok default muncul kembali (S-02).
- Restore backup → konfigurasi Telegram hilang (T-04).
- API stok/pelanggan/transaksi/klaim garansi dapat dipanggil tanpa token (K-02/T-10).

Bug yang pasti dari inspeksi kode (tanpa perlu menjalankan APK):

- APK tidak punya jalur cetak (T-02).
- APK tidak punya `DownloadListener` untuk backup (T-03).
- `BackendManager.running` tidak pernah di-reset saat uvicorn gagal bind (T-07).
- Tidak ada migrasi skema umum (T-05).
- Tidak ada idempotensi transaksi (T-11).

### 5.2 Apakah ada kegagalan security?

**Ya.**

| Area | Temuan | Dampak |
|---|---|---|
| Web lokal di LAN | K-02 | Siapa pun di Wi-Fi dapat membaca/mengubah data, membuat transaksi, klaim garansi; `/docs` terbuka. |
| APK localhost | T-10 | Aplikasi lain di HP dapat mengakses API tanpa token. |
| Token admin | S-08 | Token kosong → fitur admin mati; token placeholder publik → aksi destruktif bisa diotorisasi. |
| Token Telegram | S-07 | Plaintext di SQLite; redaksi backup tidak forensik; salinan `sebelum_restore` tidak diredaksi. |
| Transport | K-02 | Token admin dikirim lewat HTTP polos di LAN, dapat disadap. |

Yang **sudah baik**: `require_admin_token` memakai `hmac.compare_digest` dan fail-closed (503) bila token kosong (`api/deps.py:20-37`); tidak ada SQL injection karena semua query memakai parameter SQLAlchemy; XSS di frontend dimitigasi dengan `esc()`; PIN APK memakai PBKDF2 + EncryptedSharedPreferences, `FLAG_SECURE`, `allowBackup=false`; WebView memblokir URL eksternal dan mematikan akses file.

### 5.3 Apakah ada kecacatan logika bisnis yang bisa membuat database tidak tercatat?

**Ya.** Jalur utama:

| Jalur | Temuan | Akibat |
|---|---|---|
| Dua transaksi bersamaan | T-01 | Satu transaksi gagal 500; penjualan tidak tercatat. |
| Retry/double submit | T-11 | Penjualan tercatat ganda; stok terpotong dua kali. |
| Storage penuh karena backup | K-01 | SQLite gagal menulis; transaksi baru tidak tersimpan. |
| Server APK gagal start/port bentrok | T-07 | Aplikasi tidak bisa dipakai; pemilik mungkin reset dan kehilangan data. |
| Restore saat server hidup | T-09 | Transaksi yang sedang berjalan bisa hilang/locked. |
| Update APK + skema berubah | T-05 | Data lama tidak terbaca; pemilik mungkin reset. |
| Seed saat start/restore | S-02 | Data yang dihapus muncul lagi; restore tidak setia. |
| Backup tidak benar-benar tersimpan (APK) | T-03 | Tidak ada backup saat dibutuhkan. |
| Backup otomatis mati setelah restore | T-04 | Tidak ada backup berikutnya. |
| Backup otomatis tidak jalan saat app ditutup | T-06 | Backup terlewat berhari-hari. |

---

## 6. Kompatibilitas Ganda (Pydantic v1/v2 dan Chaquopy)

| Aspek | Web (desktop) | APK (Chaquopy) | Status |
|---|---|---|---|
| Pydantic | 2.14.2 | 1.10.18 | **Lulus 64 test di keduanya.** Shim `model_validate`/`model_dump`, `Money`, `_pattern()` bekerja. |
| FastAPI | 0.162.0 | 0.115.0 | **Lulus.** Tidak ada API v2-only yang dipakai. |
| SQLAlchemy | 2.1.6 | 2.0.36 | **Lulus.** Sync engine tidak membutuhkan `greenlet`; test lulus tanpa greenlet. |
| uvicorn | 0.54.0 | 0.30.6 | **Lulus.** APK tidak memakai `uvloop`/`httptools`. |
| Native/Rust | `pydantic-core`, `uvloop`, `httptools`, `watchfiles` (via `uvicorn[standard]`) | Tidak ada; semua pin pure-Python | **Aman asalkan build APK memakai `build.gradle.kts`, bukan `requirements.txt`.** |
| Python | 3.12.10 | 3.10 | **Lulus.** Tidak ada sintaks 3.11+ yang dipakai. |
| Decimal/Money | String 2 desimal | String 2 desimal | **Konsisten.** |
| Validasi | Pesan error bisa berbeda detail | Pesan error bisa berbeda detail | Bukan bug; frontend hanya menampilkan `detail`. |

**Catatan:** `requirements.txt` **bukan** daftar dependensi APK. Jika seseorang menjalankan `pip install -r requirements.txt` di Chaquopy, build akan mencoba `pydantic-core` (Rust) dan `uvicorn[standard]` (native) dan kemungkinan gagal. Dokumentasikan pemisahan ini dengan jelas (R-04).

---

## 7. Kesetaraan Perilaku Bisnis Web vs APK

Backend yang dipakai **sama** (ZIP dari root repo), sehingga rumus total, diskon, pembayaran, stok, dan laporan berasal dari kode yang sama. Perbedaan yang ada adalah lingkungan, bukan rumus:

| Perilaku | Web | APK | Konsisten? |
|---|---|---|---|
| Total jasa/part/diskon/total | `pricing_service` Decimal | Sama | **Ya** |
| Kembalian CASH/TRANSFER | `pricing_service` | Sama | **Ya** |
| Potong stok | `pos_service` | Sama | **Ya** (race T-08 di keduanya) |
| Nomor nota | `pos_service` | Sama | **Ya** (race T-01 di keduanya) |
| Laporan harian/periode | `report_service` | Sama | **Ya** (N+1 S-04 di keduanya) |
| Garansi | `warranty_service` | Sama | **Ya** (bug S-03 di keduanya) |
| Cetak struk | Browser print / Web Bluetooth | **Tidak berfungsi** | **Tidak** (T-02) |
| Backup manual | Download file | **Tidak tersimpan** | **Tidak** (T-03) |
| Backup otomatis | Telegram (selama server hidup) | Telegram (selama proses hidup) | **Sama-sama bergantung proses hidup** (T-06) |
| Admin token | Dari `.env`/prompt | Disuntik per-instalasi | Berbeda mekanisme; perlu token di semua endpoint (T-10) |
| Host | `0.0.0.0` default | `127.0.0.1` | Berbeda; web berisiko (K-02) |

**Kesimpulan:** Perhitungan bisnis identik karena berbagi service yang sama. Yang tidak identik adalah **kemampuan operasional** (cetak, backup) dan **postur keamanan** (host web). Perbaikan harus menjaga satu sumber logika bisnis; jangan menduplikasi rumus di Kotlin/JS.

---

## 8. Yang Sudah Baik (jangan dirusak saat perbaikan)

- **Uang memakai `Decimal` + `ROUND_HALF_UP`**, bukan float, di backend (`services/utils.py:40-50`, `services/pricing_service.py`).
- **Transaksi POS atomik** dengan `with db.begin()` untuk nota + job + part + potong stok (`services/pos_service.py:55-223`).
- **Validasi stok negatif** dan konfirmasi `izinkan_stok_minus` (`services/pos_service.py:126-146`).
- **`require_admin_token` fail-closed** dan `hmac.compare_digest` (`api/deps.py:20-37`).
- **Tidak ada SQL injection**: semua query memakai bound parameter SQLAlchemy; `exec_driver_sql` hanya SQL statis.
- **XSS dimitigasi** dengan `esc()` untuk `& < > " '` (`frontend/js/app.js:12-28`), termasuk di atribut `value`.
- **Path database aman**: path relatif desktop di-resolve ke `BASE_DIR` (`database/session.py:14-23`); APK memakai `filesDir/data` absolut (`bootstrap.py:37-39`), sehingga tidak hilang saat update dan tidak hardcoded.
- **APK hanya bind `127.0.0.1`** (`bootstrap.py:35`) dan network security config hanya mengizinkan cleartext localhost; ini benar untuk mencegah akses dari jaringan.
- **PIN APK**: PBKDF2, EncryptedSharedPreferences, lockout dua jam, `FLAG_SECURE`, `allowBackup=false`, reset dengan konfirmasi “RESET” — sesuai spesifikasi.
- **Backup memakai sqlite3 backup API** (aman saat DB aktif) dan memvalidasi header/integrity/required tables sebelum restore (`services/backup_service.py:54-118`).
- **Seed idempotent secara count** (meski logikanya bermasalah, S-02) dan **migrasi `harga_modal`** sudah ada untuk data lama.
- **Test suite 64** lulus di dua stack dependensi; ini modal bagus untuk perbaikan berikutnya.

---

## 9. Perlu Verifikasi (belum bisa disimpulkan di mesin audit)

| ID | Yang perlu diverifikasi | Cara |
|---|---|---|
| T-02 | Cetak struk APK benar-benar no-op di WebView | Build APK, simpan transaksi, cek printer/logcat. |
| T-03 | Blob download tidak tersimpan di WebView | Build APK, klik Backup, cek Downloads + logcat. |
| T-06 | Proses dibunuh saat layar mati/background pada OEM tertentu | Uji di HP low-end, tutup aplikasi, tunggu jadwal. |
| T-07 | Port 8000 bentrok → retry macet | Jalankan server lain di 8000, buka APK, tekan Coba Lagi. |
| T-08 | Race stok menghasilkan oversell/lost update | Skrip 2 request paralel qty 1 pada stok 1. |
| T-09 | Restore saat penulisan aktif kehilangan data | Jalankan write loop + restore paralel, bandingkan jumlah nota. |
| S-07 | Token masih ditemukan di file backup setelah redaksi | `strings`/grep pada backup dan `sebelum_restore_*.db` (hati-hati: jangan tampilkan token). |
| S-04 | Waktu laporan pada volume produksi | Ukur dengan 5.000–50.000 nota di HP target. |
| T-05 | Update skema nyata pada DB lama | Salin DB, tambah kolom di model, jalankan versi baru. |

---

## 10. Rekap Severity

| Severity | Jumlah | ID |
|---|---:|---|
| **Kritis** | **2** | K-01, K-02 |
| **Tinggi** | **11** | T-01, T-02, T-03, T-04, T-05, T-06, T-07, T-08, T-09, T-10, T-11 |
| **Sedang** | **10** | S-01, S-02, S-03, S-04, S-05, S-06, S-07, S-08, S-09, S-10 |
| **Rendah** | **6** | R-01, R-02, R-03, R-04, R-05, R-06 |
| **Total** | **29** | — |

---

## 11. Top 5 Prioritas Perbaikan

1. **Amankan backup (K-01, S-07).** Tambahkan retensi file, hapus backup setelah sukses/gagal, cek ruang disk, dan redaksi/secure-delete salinan `sebelum_restore`. Ini mencegah storage penuh yang membuat transaksi baru gagal — risiko paling langsung bagi UMKM.
2. **Tutup akses API (K-02, T-10, S-08).** Ubah default web ke `127.0.0.1`, wajibkan login untuk mode LAN, wajibkan token di semua endpoint APK, matikan `/docs`, dan tolak token placeholder/kosong saat startup.
3. **Buat transaksi benar-benar atomik dan idempoten (T-01, T-08, T-11).** Ganti penomoran nota dengan counter atomik/retry, potong stok dengan conditional update, dan tambahkan `request_id` unik. Ini mencegah penjualan hilang/ganda dan stok salah.
4. **Perbaiki jalur APK yang tidak berfungsi (T-02, T-03, T-07).** Implementasikan cetak native (PrintManager/ESC/POS), download backup native (DownloadListener/SAF), dan reset `running`/pilih port dinamis agar “Coba Lagi” benar-benar bekerja.
5. **Lindungi pemulihan data (T-04, T-05, T-09).** Pertahankan token Telegram setelah restore (atau minta ulang dengan jelas), tambahkan `PRAGMA user_version` + migrasi berurutan + backup pra-migrasi, dan jalankan restore dalam mode maintenance/restart server.

---

## 12. Lampiran — Cakupan Test dan Gap

**Test yang ada (64, lulus di dua stack):** pelanggan/unit, POS/stok/uang/nomor nota, cetak/backup/restore, security/report, settings, Telegram backup, garansi.

**Gap yang belum diuji:**

- Konkurensi nomor nota dan stok (T-01, T-08, T-11).
- Retensi/penumpukan backup dan retry Telegram (K-01).
- Restore saat ada penulisan aktif (T-09).
- Migrasi skema dari versi lama (T-05).
- Pencetakan dan download di WebView APK (T-02, T-03).
- Port conflict/lifecycle/background kill APK (T-06, T-07).
- Frontend end-to-end (tidak ada `package.json`/Playwright).
- Android `lint`/`assembleDebug` (tidak bisa dijalankan tanpa JDK/Gradle/wrapper).

**Berkas yang diperiksa:** `config.py`, `run.py`, `requirements.txt`, `.env.example`, `api/*`, `services/*`, `repositories/*`, `database/*`, `frontend/index.html`, `frontend/js/*`, `frontend/css/style.css`, `android/app/src/main/AndroidManifest.xml`, `android/app/src/main/java/**`, `android/app/src/main/python/bootstrap.py`, `android/app/build.gradle.kts`, `android/build.gradle.kts`, `android/README_APK.md`, `tests/*`.

---

**Akhir laporan.** Tidak ada kode yang diubah, tidak ada commit/push, dan tidak ada branch yang dipindahkan. Menunggu instruksi sebelum melakukan perbaikan.
