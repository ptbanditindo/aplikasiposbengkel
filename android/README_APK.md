# Migrasi Backend Python ke APK (Chaquopy)

Dokumen ini menjelaskan bagaimana backend FastAPI yang sama dengan versi
desktop dijalankan **di dalam** APK Android, tanpa server terpisah.

## Arsitektur

```
PinActivity (gerbang PIN)
  └─ MainActivity (WebView)
       ├─ BackendManager.start()
       │    ├─ BackendInstaller: ekstrak assets/bengkel_backend.zip
       │    │    ke codeCacheDir/backend (sekali per versi aplikasi)
       │    ├─ pilih port bebas 8000-8010
       │    └─ bootstrap.py: uvicorn di 127.0.0.1:<port> (thread Python)
       ├─ BackendHealth: polling GET /api/health pada port itu sampai siap
       ├─ WebView.loadUrl("http://127.0.0.1:<port>/")
       └─ Injeksi window.__BENGKEL_ADMIN_TOKEN__ (per-instalasi)

WorkManager (ScheduledBackupWorker)
  └─ menyalakan backend bila perlu → POST /api/admin/scheduled-backup
     → snapshot lokal harian → salin ke folder pilihan (SAF)
     → kirim Telegram bila diaktifkan
```

- **Kode Python tidak disalin manual.** Gradle task `packageBackend`
  membungkus `config.py`, `api/`, `services/`, `repositories/`, `database/`,
  dan `frontend/` menjadi `bengkel_backend.zip` di folder build, lalu
  menambahkannya sebagai asset. API dan frontend selalu identik dengan repo.
- **Ekstraksi** dilakukan ke `codeCacheDir/backend` agar kode backend tidak
  tercampur data pengguna dan bisa diekstrak ulang tanpa menghapus database.
  Penanda `VERSION` berisi `versionName-versionCode`; naikkan `versionCode`
  setiap kali backend berubah agar ZIP diekstrak ulang.
- **Data pengguna** disimpan di `filesDir/`: database SQLite di
  `files/data/bengkel_radiator.db`, backup di `files/backups/`, dan konfigurasi
  printer di `files/data/printer_config.json`. Salinan backup tambahan ditulis
  ke folder yang dipilih pengguna lewat Storage Access Framework; tanpa
  pilihan folder, salinan jatuh ke Unduhan.
- **Server** hanya mendengarkan `127.0.0.1` pada port bebas pertama di
  8000-8010. `BackendManager` baru menandai server siap setelah `/api/health`
  menjawab, sehingga tombol "Coba lagi" benar-benar memulai ulang bila port
  bentrok atau thread uvicorn mati. Server berhenti otomatis saat proses
  aplikasi dimatikan. Reset PIN tidak menghentikan server dan tidak menyentuh
  database; hanya hash PIN di `EncryptedSharedPreferences` yang dihapus,
  sehingga token instalasi dan data usaha tetap berlaku.
- **Token instalasi**: 32 byte acak per instalasi, disimpan di
  `EncryptedSharedPreferences` (file yang sama dengan PIN), diteruskan ke
  Python lewat `AUTH_MODE=install-token` + `APP_INSTALL_TOKEN` dan disuntikkan
  ke halaman sebagai `window.__BENGKEL_ADMIN_TOKEN__`. Frontend mengirim token
  itu pada setiap request sebagai header `X-Install-Token` tanpa menanyakan ke
  pengguna. APK tidak memakai layar PIN web karena PIN-nya sudah native.
- **Printer** memakai `window.BengkelBridge` untuk Bluetooth SPP, TCP 9100
  (Wi-Fi/LAN), USB bulk (OTG), dan layanan cetak Android. `PrinterManager` di
  frontend memilih adapter sesuai jenis koneksi dan menyimpan konfigurasi lewat
  backend lokal. Cetak browser tetap dipakai di versi desktop.
- **Backup terjadwal** digerakkan `WorkManager` (bukan thread Python/WebView)
  dengan periode 24 jam, initial delay mengikuti jam pengaturan, dan retry
  eksponensial maksimal 5 percobaan. Worker dapat menyalakan backend sebentar
  lalu mematikannya lagi bila aplikasi tidak sedang di depan.
- **Tampilan dan area aman**: UI 2.2 memakai dasar kertas putih dengan aksen
  warna pada angka dan status. Pilihan Terang/Gelap di Pengaturan disimpan di
  `localStorage` (`bengkel.theme`) dan diteruskan ke shell lewat
  `BengkelPin.applyChromeTheme` agar warna status bar dan navigation bar ikut
  berubah. `MainActivity` memakai edge-to-edge dengan padding
  `systemBars() or displayCutout()` pada `appRoot`, sehingga konten tidak
  tertutup status bar atau notch. Di kasir, blok jasa dan sparepart diberi latar
  tipis berbeda, detail pelanggan menampilkan riwayat servis, dan kolom uang
  memakai pemisah ribuan otomatis.

## Versi Python dan dependensi

Chaquopy **16.0.0** dipakai karena mendukung AGP 8.6.x (Chaquopy 17
mensyaratkan AGP 9). Target runtime Python 3.10; Python 3.12.10 dipakai sebagai
build Python untuk pip.

Pydantic v2 tidak bisa dipakai di Chaquopy karena `pydantic-core` ditulis dalam
Rust. Karena itu APK memakai pin pure-Python berikut di
`android/app/build.gradle.kts`:

| Paket | Versi |
| --- | --- |
| fastapi | 0.115.0 |
| starlette | 0.38.6 |
| pydantic | 1.10.18 |
| uvicorn | 0.30.6 |
| SQLAlchemy | 2.0.36 |
| httpx | 0.27.2 |
| python-multipart | 0.0.9 |
| python-dotenv | 1.0.1 |

`api/schemas.py` dibuat kompatibel untuk v1 dan v2:

- `Money` menjadi string dua desimal di kedua versi.
- `model_validate()` / `model_dump()` tersedia sebagai shim di v1.
- `pattern` (v2) dipetakan ke `regex` (v1).

Versi desktop di `requirements.txt` memakai pydantic v2 dan FastAPI terbaru
yang diverifikasi. Seluruh **226 test** lulus di kedua jalur (v2 dan v1 +
FastAPI 0.115).

Semua paket dipasang dengan `options("--no-deps")` dan daftar eksplisit di
`android/app/build.gradle.kts`, sehingga pip hanya mengunduh wheel
`py3-none-any` (tidak ada kompilasi native seperti greenlet/uvloop).
`uvloop` dan `httptools` tidak dipakai; uvicorn berjalan dengan asyncio biasa.

## Prasyarat build

- JDK 17 dan Android SDK 35.
- Python 3.10+ di mesin build. Chaquopy memakai interpreter host untuk
  menjalankan pip; tidak perlu sama dengan target.
- Koneksi internet saat build pertama (unduh runtime Python Chaquopy + wheel).
- `gradle/wrapper/gradle-wrapper.jar` sudah ada di repo, jadi `./gradlew`
  langsung bisa dipakai.
- Arahkan SDK lewat `ANDROID_HOME`/`ANDROID_SDK_ROOT` atau berkas
  `android/local.properties` (`sdk.dir=...`). Berkas itu bersifat lokal dan
  tidak di-commit. Toolchain portabel yang dipakai saat pengembangan ada di
  `android/.toolchain/` (diabaikan Git).

```bash
cd android
./gradlew test          # unit test Kotlin (JVM)
./gradlew assembleDebug # APK debug
```

APK debug ada di `android/app/build/outputs/apk/debug/app-debug.apk`.

ABI yang dibangun: `arm64-v8a` (mayoritas HP modern), `armeabi-v7a`
(HP lama), dan `x86_64` (emulator). Menambah ABI memperbesar ukuran APK.

## Hasil build terakhir

- Berkas: `android/app/build/outputs/apk/debug/app-debug.apk`
- Ukuran: 45.034.812 byte
- SHA-256: `64d45743dc97f929f0b60c2c2ba90a1455fd7bb8ec11813f2c1ebcde5251123f`
- Paket: `com.bengkelpos.radiator`, versionName `2.2.2`, versionCode `5`,
  minSdk 26, targetSdk 35, debug-signed.
- Asset `assets/bengkel_backend.zip`: 210.531 byte, SHA-256
  `d4dd12198fec978466292a54d371967f91540a6cb9a8015e28247a6264f214f7`.
  `services/pos_service.py`, `services/customer_service.py`,
  `services/receipt_service.py`, `frontend/js/app.js`, dan
  `frontend/css/style.css` di dalam ZIP dicocokkan hash-nya dengan working tree
  saat build. ZIP ini memuat label barang yang dicetak di bawah nota, daftar
  stok yang lebih rapat, serta indikator loading berbentuk lingkaran di APK.
- Unit test JVM: **150 test** (Debug) lulus. Pytest backend: **239 test lulus**
  di masing-masing stack (Pydantic v2 dan Pydantic 1.10).
- APK belum dipasang/diuji di perangkat Android fisik.

## Pemeriksaan di perangkat

1. Instal APK, buat PIN. Saat server disiapkan, layar menampilkan lingkaran
   loading tanpa teks "Menyiapkan aplikasi". Bila memasang menimpa APK 2.1,
   versi yang naik memaksa backend diekstrak ulang sehingga tampilan terbaru
   ikut terpakai.
2. Pastikan halaman kasir muncul dan transaksi bisa disimpan.
3. Buka detail pelanggan yang punya nota: bagian Riwayat servis terisi dan
   baris riwayat bisa diketuk untuk membuka detail nota.
4. Di kasir, pastikan blok Jasa dan Sparepart punya latar berbeda dan tombol
   tambahnya tidak tertukar.
5. Ketik `1000000` di kolom uang: nilai tampil menjadi `1.000.000` dan total
   nota tetap dihitung backend seperti biasa.
6. Simpan pengaturan bengkel/Telegram — tidak boleh ada prompt token atau
   layar PIN web di APK.
7. Tutup paksa aplikasi lalu buka lagi: PIN diminta, data tetap ada.
8. Coba screenshot layar kasir/nota (harus berhasil) dan layar PIN (harus
   kosong/hitam karena `FLAG_SECURE`).
9. Buka Pengaturan, ganti Warna aplikasi ke Gelap lalu Terang. Warna status
   bar ikut berubah dan pilihan tetap tersimpan setelah aplikasi dibuka lagi.
10. Pastikan judul halaman dan tombol aksi tidak tertutup status bar, kamera
    punch-hole, atau navigation bar pada perangkat dengan layar penuh.
11. Buka Pengaturan → Printer, tambahkan printer Bluetooth/Wi-Fi/USB, lalu
    lakukan tes cetak pada perangkat nyata.
12. Lupa PIN → RESET → buat PIN baru → data dan token instalasi tetap ada.
13. Uji ganti jam perangkat dan reboot untuk perilaku kunci PIN serta jadwal
    backup WorkManager.

Jika muncul "Server lokal gagal dijalankan", periksa logcat:

```bash
adb logcat -s python:* AndroidRuntime:E
```

Penyebab umum: interpreter Python build tidak ditemukan, wheel gagal diunduh
saat build, atau ABI perangkat tidak termasuk dalam `abiFilters`.

## Batasan yang masih ada

- **Printer fisik belum diuji di perangkat nyata.** Jalur Bluetooth SPP, TCP
  9100, USB OTG, dan Android System Print sudah diimplementasikan dan diuji
  dengan unit test/transport tiruan; perilaku tiap model printer tetap perlu
  verifikasi manual.
- **Backup harian berjalan lewat WorkManager.** Android dapat menunda pekerjaan
  saat baterai rendah; status percobaan terakhir terlihat di Pengaturan.
  Telegram hanya menerima file bila token/Chat ID diisi dan ada internet.
- **Restore dari Telegram manual.** Bot API tidak bisa mengunduh file yang
  dikirim bot itu sendiri, jadi pengguna mengunduh `.db` lalu memilihnya di
  Pengaturan → Pulihkan data. Server lokal dijalankan ulang otomatis setelah
  restore.
- **Proses bisa dimatikan Android** saat aplikasi di latar belakang. Data aman
  di SQLite; server dinyalakan lagi saat aplikasi dibuka atau saat worker
  backup berjalan.
- **Belum ada Release APK**; hanya build Debug yang dipakai untuk verifikasi.
- **Ganti PIN dari dalam aplikasi dan enkripsi file backup Telegram** belum
  dikerjakan.
