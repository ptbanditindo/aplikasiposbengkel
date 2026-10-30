# BengkelPOS Radiator

Aplikasi kasir dan manajemen servis untuk bengkel radiator: multi-unit per
pelanggan, stok sparepart, tarif jasa, nota servis, garansi, laporan harian,
serta cetak struk thermal. Berjalan **offline** di komputer/laptop (web lokal)
dan juga bisa dikemas menjadi **APK Android** dengan backend Python tertanam.

Backend FastAPI + SQLAlchemy (SQLite) melayani frontend SPA (HTML/CSS/JS tanpa
build step) di `http://127.0.0.1:8000`.

## Fitur

- **Pelanggan & unit** — satu pelanggan bisa punya banyak mobil/radiator;
  pencarian cepat, ringkasan jumlah unit per pelanggan.
- **Transaksi servis (POS)** — jasa + sparepart dalam satu nota, diskon,
  pembayaran CASH/TRANSFER, kembalian, validasi stok (opsi izinkan stok minus).
- **Garansi** — masa garansi per nota (bulan bebas), status aktif/kadaluarsa,
  catatan klaim, dan penandaan klaim.
- **Stok & tarif jasa** — harga modal/jual, penyesuaian jumlah, proteksi hapus
  item yang sudah dipakai transaksi.
- **Laporan** — kas harian, rekap periode, penjualan sparepart, laba kotor,
  rincian per metode bayar.
- **Struk** — teks 58 mm/80 mm dan payload ESC/POS base64 siap dikirim ke
  printer thermal.
- **Backup & restore** — backup file SQLite, restore dengan validasi skema,
  serta backup otomatis ke Telegram (manual atau terjadwal).
- **Pengaturan** — identitas bengkel, rekening transfer, jam/token Telegram
  dapat diubah dari UI tanpa mengedit `.env`.
- **APK Android** — gerbang PIN 6 angka (hash PBKDF2 + salt, lockout bertingkat),
  shell WebView, backend berjalan di dalam aplikasi.

## Menjalankan versi web/desktop

Prasyarat: Python 3.10+.

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
`data/bengkel_radiator.db`, backup di `backups/`.

## Konfigurasi penting (`.env`)

| Variabel | Fungsi |
| --- | --- |
| `APP_HOST` | Alamat server. Hanya `127.0.0.1`, `localhost`, atau `::1` yang diterima; nilai lain menggagalkan startup. |
| `APP_PORT` | Port web lokal (default 8000). |
| `DATABASE_URL` | Default `sqlite:///./data/bengkel_radiator.db`. |
| `BENGKEL_*` | Identitas bengkel & rekening; nilai awal, bisa diubah dari menu Pengaturan. |
| `BACKUP_DIR` | Folder backup lokal. |
| `BACKUP_KEEP` | Jumlah file backup terakhir yang disimpan (default 14). |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Nilai awal backup Telegram; bisa diisi dari Pengaturan. |

Backup otomatis hanya dikirim lewat Telegram. Tidak ada penjadwal backup lokal;
flag `AUTO_BACKUP_ENABLED` dan `SECRET_KEY` sudah dihapus karena tidak dipakai.

`.env` **tidak pernah** ikut di-commit; hanya `.env.example`. Identitas bengkel
dan konfigurasi Telegram yang disimpan lewat UI berada di database dan
menimpa nilai default `.env`.

## Keamanan akses web

Web lokal hanya untuk PC kasir itu sendiri; tidak ada mode LAN. Server menolak
startup bila `APP_HOST` bukan loopback, menolak header `Host` asing, menolak
permintaan tulis dari `Origin` lain, dan mematikan `/docs`, `/redoc`, serta
`/openapi.json`.

Akses aplikasi dijaga PIN kasir:

- PIN dibuat saat aplikasi pertama kali dibuka, disimpan sebagai hash PBKDF2 +
  salt di database (bukan plaintext).
- Login menghasilkan cookie sesi `HttpOnly` + `SameSite=Strict` berlaka 12 jam;
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

Prasyarat build: JDK 17, Android SDK 35, Python 3.10+ di mesin build.

```bash
cd android
./gradlew assembleDebug
```

Detail arsitektur, versi dependensi, dan batasan ada di
[`android/README_APK.md`](android/README_APK.md). Perilaku PIN, lockout, dan
alur reset ada di [`android/README_PIN.md`](android/README_PIN.md).

Di APK, backend berjalan dengan `AUTH_MODE=install-token`: setiap request
membawa header `X-Install-Token` dari token acak per instalasi yang disimpan
terenkripsi. Shell WebView hanya mengizinkan navigasi ke `http://127.0.0.1`
pada port backend aplikasi; layar PIN web tidak dipakai karena PIN sudah
native.

Batasan APK saat ini: cetak ke printer thermal dari WebView dan tombol unduh
backup berbasis blob belum diimplementasikan; backup terjadwal Telegram hanya
berjalan selama aplikasi terbuka.

## Struktur proyek

```
api/            router FastAPI, skema Pydantic (kompatibel v1 & v2), dependency auth
services/       logika bisnis: POS, laporan, garansi, struk, backup, Telegram
repositories/   akses data SQLAlchemy
database/       engine/session, model, seed
frontend/       SPA (index.html, css, js) yang dilayani backend
android/        proyek APK: PIN, WebView shell, Chaquopy, bootstrap.py
tests/          pytest (API + alur bisnis)
run.py          runner lokal
```

## Pengujian

```bash
pytest -q
```

115 test mencakup transaksi, stok, garansi, laporan, pengaturan, backup/restore,
Telegram, serta pemeriksaan keamanan akses (PIN, sesi, token instalasi,
loopback, host/origin). Suite yang sama lulus di dua jalur
dependensi: Pydantic v2 (desktop) dan Pydantic 1.10 + FastAPI 0.115
(kombinasi yang dipakai APK).

## Keamanan dan data

- PIN kasir di-hash PBKDF2-HMAC-SHA256 + salt; sesi ditandatangani HMAC dengan
  rahasia yang tersimpan di database, sehingga reset PIN membatalkan sesi lama.
- Server hanya mendengar loopback, memvalidasi `Host`, menolak `Origin` asing
  untuk permintaan tulis, dan tidak membuka dokumentasi API otomatis.
- File backup meredaksi token bot Telegram; database aktif tetap menyimpan
  token karena dibutuhkan untuk pengiriman.
- Di APK: hash PIN + salt di EncryptedSharedPreferences, `FLAG_SECURE`,
  `allowBackup=false`, server hanya mendengar `127.0.0.1`.
- Data transaksi tidak dikirim ke layanan pihak ketiga; Telegram hanya dipakai
  bila fitur backup diaktifkan pengguna.

Laporan audit dan rencana perbaikan: [`LAPORAN_AUDIT_BUG_SECURITY_BISNIS.md`](LAPORAN_AUDIT_BUG_SECURITY_BISNIS.md)
dan [`RENCANA_PERBAIKAN_AUDIT.md`](RENCANA_PERBAIKAN_AUDIT.md).
