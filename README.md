# BengkelPOS Radiator

Aplikasi kasir dan manajemen servis untuk bengkel radiator: multi-unit per
pelanggan, stok sparepart, tarif jasa, nota servis, garansi, pembatalan dan
retur, laporan harian, serta cetak struk thermal. Berjalan **offline** di
komputer/laptop (web lokal) dan juga bisa dipaketkan menjadi **APK Android**
dengan backend Python tertanam.

Backend FastAPI + SQLAlchemy (SQLite) melayani frontend SPA (HTML/CSS/JS tanpa
build step) di `http://127.0.0.1:8000`.

## Fitur

- **Pelanggan & unit** — satu pelanggan bisa punya banyak mobil/radiator;
  pencarian cepat, ringkasan jumlah unit per pelanggan, dan riwayat servis
  pelanggan yang bisa dibuka langsung dari kartu pelanggan.
- **Transaksi servis (POS)** — jasa + sparepart dalam satu nota, diskon,
  pembayaran CASH/TRANSFER, kembalian, validasi stok, serta opsi izinkan stok
  minus. Zona input jasa dan sparepart dibedakan warna agar kasir tidak salah
  memasukkan item, dan kolom uang otomatis memakai pemisah ribuan
  (`1.000.000`) saat diketik. Setelah nota tersimpan, strip label barang ikut
  tercetak di bawah garis potong.
- **Label barang** — strip label memuat pelanggan, nomor HP, unit, jenis barang,
  dan kode `RAD-YYYYMMDD-NNN` yang berurutan per hari mulai `001`. Kode dibuat
  sekali saat transaksi pertama, lalu dipakai ulang pada cetak ulang, void, dan
  retur. Unit lama yang sudah berlabel tetap memakai kodenya; unit tanpa label
  mendapat kode saat transaksi pertamanya tercatat.
- **Pembatalan dan retur** — nota bisa dibatalkan (VOID) atau diretur sebagian
  maupun seluruhnya. Stok dikembalikan secara atomik lewat ledger pergerakan
  stok, bukan dengan menyunting angka stok manual.
- **Garansi** — masa garansi per nota (bulan bebas), status aktif/kadaluarsa,
  catatan klaim, dan klaim yang hanya bisa dilakukan sekali.
- **DP & piutang** — nota bisa dibayar sebagian sebagai DP dengan jatuh tempo,
  lalu dilunasi bertahap dari detail nota. Daftar piutang per pelanggan
  menampilkan sisa, umur piutang, dan nota yang belum lunas.
- **WhatsApp manual** — tombol WhatsApp membuka pratinjau pesan dan tautan
  `wa.me`; kasir tetap menekan kirim sendiri. Setiap upaya dicatat, nomor
  ditampilkan tersamarkan, dan pesan hanya aktif bila pelanggan memberi izin.
- **Follow-up & servis berkala** — papan tindak lanjut untuk piutang, garansi
  yang akan habis, servis berkala, dan prospek pelanggan. Setiap tarif jasa
  punya interval servis (bulan) yang dapat diubah; nilainya disalin ke nota
  saat dikerjakan dan menjadi pengingat servis berikutnya.
- **Stok & tarif jasa** — harga modal/jual, penyesuaian jumlah, interval servis
  berkala per jasa, snapshot modal saat part dipakai, dan proteksi hapus item
  yang sudah dipakai transaksi. Daftar stok memakai baris lebih rapat agar
  lebih banyak item terlihat; tabel jasa, riwayat, dan laporan tidak ikut
  dirapatkan.
- **Laporan** — kas harian, rekap periode, penjualan sparepart, laba kotor,
  rincian per metode bayar, dan laporan semua waktu.
- **Printer universal** — kelola beberapa printer dari Pengaturan: Bluetooth
  (SPP), Wi-Fi/LAN (TCP 9100), USB OTG, cetak lewat layanan Android, dan cetak
  lewat browser. Mendukung kertas 58/80 mm, tes cetak, serta printer utama.
- **Backup & pemulihan** — snapshot SQLite lengkap (pelanggan, unit, riwayat
  servis, transaksi keuangan, stok, pengaturan), pemulihan dengan validasi
  skema dan salinan pengaman otomatis, backup lokal harian, serta pengiriman
  opsional ke Telegram.
- **Pengaturan** — identitas bengkel, rekening transfer, token/jadwal Telegram,
  printer, dan batas kunci aplikasi dapat diubah dari UI tanpa mengedit `.env`.
- **Tampilan terang/gelap** — antarmuka berbasis kertas putih dengan aksen
  warna pada angka dan status penting; pilihan Terang atau Gelap tersimpan per
  perangkat di Pengaturan dan langsung berlaku tanpa memuat ulang halaman.
- **APK Android** — gerbang PIN 6 angka native (PBKDF2 + salt, lockout
  bertingkat), shell WebView, backend berjalan di dalam aplikasi. Saat server
  disiapkan, layar menampilkan indikator loading lingkaran. Layar utama
  dapat di-screenshot dan direkam; hanya layar PIN yang diproteksi. Layar
  mengikuti area aman (status bar, navigation bar, dan notch) sehingga kontrol
  tidak tertutup sistem, dan warna status bar ikut tema terang/gelap.

## Menjalankan versi web/desktop

Prasyarat: Python 3.10 atau lebih baru (diverifikasi pada Python 3.12.10).

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env      # Windows: copy .env.example .env
```

Sesuaikan `.env` bila perlu (default sudah aman untuk satu PC kasir), lalu:

```bash
python run.py
```

Buka `http://127.0.0.1:8000`. Saat pertama kali dibuka, aplikasi meminta Anda
membuat PIN kasir 4&ndash;12 angka. Data tersimpan di
`data/bengkel_radiator.db`, backup di `backups/`, dan konfigurasi printer di
`data/printer_config.json`.

## Konfigurasi penting (`.env`)

| Variabel | Fungsi |
| --- | --- |
| `APP_HOST` | Alamat server. Hanya `127.0.0.1`, `localhost`, atau `::1` yang diterima; nilai lain menggagalkan startup. |
| `APP_PORT` | Port web lokal (default 8000). |
| `AUTH_MODE` | `session-pin` untuk versi web/desktop; `install-token` diisi otomatis oleh APK. |
| `DATABASE_URL` | Default `sqlite:///./data/bengkel_radiator.db`. |
| `BENGKEL_*` | Identitas bengkel & rekening; nilai awal, bisa diubah dari menu Pengaturan. |
| `DEFAULT_GARANSI_BULAN`, `GARANSI_SYARAT_STANDAR` | Nilai awal garansi untuk nota baru. |
| `PRINTER_PAPER_WIDTH`, `PRINTER_DEFAULT_ENCODING` | Default kertas (58/80 mm) dan encoding teks struk. |
| `PRINTER_CONFIG_PATH` | Berkas konfigurasi printer per perangkat (default `./data/printer_config.json`), di luar database dan backup. |
| `BACKUP_DIR` | Folder backup lokal. |
| `BACKUP_KEEP` | Jumlah file backup terakhir yang disimpan (default 14). |
| `BACKUP_MAX_RESTORE_MB` | Batas ukuran berkas restore yang diunggah (default 64 MB). |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Nilai awal backup Telegram; bisa diisi dari Pengaturan. |
| `TELEGRAM_BACKUP_ENABLED`, `TELEGRAM_BACKUP_TIME` | Sakelar dan jam pengiriman harian Telegram (default 21:00). |
| `BACKUP_SCHEDULER` | `python` untuk versi desktop (default). APK memakai `workmanager`, diisi otomatis oleh `bootstrap.py`. |

Backup lokal harian selalu dibuat. Di versi desktop, penjadwal berjalan selama
aplikasi terbuka; di APK, WorkManager menjalankan jadwal harian dan dapat
menyalakan backend sebentar untuk membuat snapshot. Pengiriman Telegram adalah
tambahan opsional: bila token dan Chat ID diisi, file snapshot yang sama dikirim
ke chat bot. Nilai `APP_ENV=test` mematikan penjadwal agar test tidak berjalan
latar.

`.env` **tidak pernah** ikut di-commit; hanya `.env.example`. Identitas bengkel
dan konfigurasi Telegram yang disimpan lewat UI berada di database dan
menimpa nilai default `.env`.

## Keamanan akses web

Web lokal hanya untuk PC kasir itu sendiri; tidak ada mode LAN. Server menolak
startup bila `APP_HOST` bukan loopback, menolak header `Host` asing, menolak
permintaan tulis dari `Origin` lain, dan mematikan `/docs`, `/redoc`, serta
`/openapi.json`.

Akses aplikasi dijaga PIN kasir:

- PIN dibuat saat aplikasi pertama kali dibuka dan disimpan sebagai hash
  PBKDF2 + salt di database (bukan plaintext).
- Login menghasilkan cookie sesi `HttpOnly` + `SameSite=Strict` berlaku 12 jam;
  semua endpoint `/api` mensyaratkan sesi tersebut, kecuali `/api/health` dan
  endpoint setup/login.
- Salah PIN 5 kali memicu jeda bertahap (30 detik, berlipat hingga 15 menit).
- Lupa PIN: jalankan `python reset_pin.py` di PC kasir. Skrip hanya menghapus
  hash PIN setelah konfirmasi; pelanggan, transaksi, stok, dan pengaturan tidak
  tersentuh. Buka ulang aplikasi untuk membuat PIN baru.

## APK Android

Kode Android ada di `android/`. Backend Python yang sama dibundel sebagai asset
ZIP dan dijalankan di dalam proses aplikasi memakai Chaquopy 16 (Python 3.10),
sehingga tidak perlu server terpisah dan tetap offline.

Prasyarat build: JDK 17, Android SDK 35, dan Python 3.10+ di mesin build.

```bash
cd android
./gradlew test          # unit test Kotlin (JVM)
./gradlew assembleDebug # APK debug
```

Detail arsitektur, versi dependensi, hasil build, dan batasan ada di
[`android/README_APK.md`](android/README_APK.md). Perilaku PIN, lockout, dan
alur reset ada di [`android/README_PIN.md`](android/README_PIN.md). Build debug
terakhir adalah versi **2.2.2** (versionCode 5).

Di APK, backend berjalan dengan `AUTH_MODE=install-token`: setiap request
membawa header `X-Install-Token` dari token acak per instalasi yang disimpan
terenkripsi. Server menolak startup bila token itu kosong atau masih
placeholder `ganti-dengan-...`. Shell WebView hanya mengizinkan navigasi ke
`http://127.0.0.1` pada port backend aplikasi; layar PIN web tidak dipakai
karena PIN sudah native.

Layar utama APK (WebView) **tidak** memakai `FLAG_SECURE`, sehingga nota,
laporan, dan tampilan operasional dapat di-screenshot atau direkam. Layar PIN
tetap memakai `FLAG_SECURE`, dan `privacyCover` menutup pratinjau recents saat
aplikasi masuk latar belakang.

Batasan APK saat ini: printer fisik belum diuji di perangkat nyata (jalur
Bluetooth SPP, TCP 9100, USB OTG, dan cetak Android sudah tersedia), pemulihan
dari Telegram tetap manual (unduh file lalu pilih di Pengaturan), dan proses
aplikasi dapat dimatikan Android saat di latar belakang (data aman di SQLite;
WorkManager tetap menjalankan backup harian).

## Struktur proyek

```
api/            router FastAPI, skema Pydantic (kompatibel v1 & v2), dependency auth
services/       logika bisnis: POS, void/retur, laporan, garansi, struk, printer, backup
repositories/   akses data SQLAlchemy
database/       engine/session, model, migrasi, seed
frontend/       SPA (index.html, css, js) + PrinterManager dan adapter printer
android/        proyek APK: PIN, WebView shell, jembatan printer, Chaquopy, bootstrap.py
tests/          pytest (API + alur bisnis)
run.py          runner lokal
reset_pin.py    pemulihan darurat PIN di PC kasir
```

## Pengujian

```bash
python -m pytest -q
```

272 test mencakup transaksi, DP/pelunasan/piutang, WhatsApp, follow-up dan
servis berkala, void/retur, stok, garansi, laporan, pengaturan, label barang,
printer, backup/restore, Telegram, serta pemeriksaan keamanan akses (PIN,
sesi, token instalasi, loopback, host/origin). Jalur desktop memakai Pydantic
v2; kombinasi APK tetap memakai Pydantic 1.10 + FastAPI 0.115.

Unit test Kotlin untuk PIN, backup, dan printer juga tersedia (150 test):

```bash
cd android
./gradlew test
```

## Keamanan dan data

- PIN kasir di-hash PBKDF2-HMAC-SHA256 + salt; sesi ditandatangani HMAC dengan
  rahasia yang tersimpan di database, sehingga reset PIN membatalkan sesi lama.
- Server hanya mendengar loopback, memvalidasi `Host`, menolak `Origin` asing
  untuk permintaan tulis, dan tidak membuka dokumentasi API otomatis.
- File backup meredaksi token bot Telegram; database aktif tetap menyimpan
  token karena dibutuhkan untuk pengiriman. Konfigurasi printer disimpan di
  berkas terpisah dan tidak ikut masuk database atau backup.
- Di APK: hash PIN + salt di EncryptedSharedPreferences, layar PIN memakai
  `FLAG_SECURE`, `allowBackup=false`, dan server hanya mendengar `127.0.0.1`.
- Data transaksi tidak dikirim ke layanan pihak ketiga; Telegram hanya dipakai
  bila fitur backup diaktifkan pengguna.

Dokumen pendukung:

- [`AUDIT_REPORT.md`](AUDIT_REPORT.md) — audit menyeluruh backend, frontend,
  keamanan, dan APK (potret kondisi sebelum rangkaian perbaikan ARC-*).
- [`INVENTARIS_TEKS_UI.md`](INVENTARIS_TEKS_UI.md) — inventaris seluruh teks
  UI, popup, dan pesan kesalahan.
- [`ATURAN_PEKERJAAN.md`](ATURAN_PEKERJAAN.md) — aturan kerja dan kompatibilitas
  dua lingkungan.
