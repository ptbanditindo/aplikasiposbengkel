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
       │    └─ bootstrap.py: uvicorn di 127.0.0.1:8000 (thread Python)
       ├─ BackendHealth: polling GET /api/health sampai siap
       ├─ WebView.loadUrl("http://127.0.0.1:8000/")
       └─ Injeksi window.__BENGKEL_ADMIN_TOKEN__ (per-instalasi)
```

- **Kode Python tidak disalin manual.** Gradle task `packageBackend`
  membungkus `config.py`, `api/`, `services/`, `repositories/`, `database/`,
  dan `frontend/` menjadi `bengkel_backend.zip` di folder build, lalu
  menambahkannya sebagai asset. API dan frontend selalu identik dengan repo.
- **Ekstraksi** dilakukan ke `codeCacheDir/backend` agar kode backend tidak
  ikut terhapus saat pengguna memilih "Lupa PIN → reset". Penanda `VERSION`
  berisi `versionName-versionCode`; naikkan `versionCode` setiap kali backend
  berubah agar ZIP diekstrak ulang.
- **Data pengguna** disimpan di `filesDir/`: database SQLite di
  `files/data/bengkel_radiator.db` dan backup di `files/backups/`.
- **Server** hanya mendengarkan `127.0.0.1:8000` dan berhenti otomatis saat
  proses aplikasi dimatikan. Setelah reset data, `LocalDataResetter` memanggil
  `BackendManager.stop()` (menutup koneksi SQLite, dispose engine) sebelum
  menghapus file, lalu `MainActivity` menjalankan server baru dengan database
  kosong dan token admin baru.
- **Token instalasi**: 32 byte acak per instalasi, disimpan di
  `EncryptedSharedPreferences` (file yang sama dengan PIN), diteruskan ke
  Python lewat `AUTH_MODE=install-token` + `APP_INSTALL_TOKEN` dan disuntikkan
  ke halaman sebagai `window.__BENGKEL_ADMIN_TOKEN__`. Frontend mengirim token
  itu pada setiap request sebagai header `X-Install-Token` tanpa menanyakan ke
  pengguna. APK tidak memakai layar PIN web karena PIN-nya sudah native; token
  lama otomatis tidak berlaku setelah reset/restart karena backend dibangun
  ulang.

## Versi Python dan dependensi

Chaquopy **16.0.0** dipakai karena mendukung AGP 8.6.x (Chaquopy 17 mensyaratkan
AGP 9). Target Python 3.10.

Pydantic v2 tidak bisa dipakai di Chaquopy karena `pydantic-core` ditulis dalam
Rust. Karena itu APK memakai **pydantic 1.10.18** (wheel murni Python) dengan
FastAPI 0.115.0. `api/schemas.py` sudah dibuat kompatibel untuk v1 dan v2:

- `Money` menjadi string dua desimal di kedua versi.
- `model_validate()` / `model_dump()` tersedia sebagai shim di v1.
- `pattern` (v2) dipetakan ke `regex` (v1).

Versi desktop di `requirements.txt` tetap memakai pydantic v2; seluruh 119 test
lulus di kedua jalur (v2 dan v1 + FastAPI 0.115).

Semua paket dipasang dengan `options("--no-deps")` dan daftar eksplisit di
`android/app/build.gradle.kts`, sehingga pip hanya mengunduh wheel
`py3-none-any` (tidak ada kompilasi native seperti greenlet/uvloop).
`uvloop` dan `httptools` tidak dipakai; uvicorn berjalan dengan asyncio biasa.

## Prasyarat build

- JDK 17 dan Android SDK 35 (buka folder `android/` di Android Studio).
- Python 3.10 (atau 3.8+) terpasang di mesin build. Chaquopy memakai
  interpreter host untuk menjalankan pip; tidak perlu sama dengan target.
- Koneksi internet saat build pertama (unduh runtime Python Chaquopy + wheel).
- `gradle/wrapper/gradle-wrapper.jar` belum ada di repo. Buat sekali dengan
  Gradle yang terpasang (`gradle wrapper --gradle-version 8.7`) atau buka
  proyek di Android Studio yang akan menambahkannya.

```bash
cd android
./gradlew test          # unit test PIN (JVM)
./gradlew assembleDebug # APK debug
```

APK debug ada di `android/app/build/outputs/apk/debug/app-debug.apk`.

ABI yang dibangun: `arm64-v8a` (mayoritas HP modern), `armeabi-v7a`
(HP lama), dan `x86_64` (emulator). Menambah ABI memperbesar ukuran APK.

## Pemeriksaan di perangkat

1. Instal APK, buat PIN, tunggu teks "Menyiapkan server lokal".
2. Pastikan halaman kasir muncul dan transaksi bisa disimpan.
3. Simpan pengaturan bengkel/Telegram — tidak boleh ada prompt token atau
   layar PIN web di APK.
4. Tutup paksa aplikasi lalu buka lagi: PIN diminta, data tetap ada.
5. Lupa PIN → RESET → buat PIN baru → server berjalan dengan database kosong,
   token instalasi baru, lalu pulihkan backup lewat Pengaturan.
6. Uji ganti jam perangkat dan reboot untuk perilaku kunci PIN.

Jika muncul "Server lokal gagal dijalankan", periksa logcat:

```bash
adb logcat -s python:* AndroidRuntime:E
```

Penyebab umum: interpreter Python build tidak ditemukan, wheel gagal diunduh
saat build, atau ABI perangkat tidak termasuk dalam `abiFilters`.

## Batasan yang masih ada

- **Cetak struk thermal dari WebView belum diimplementasikan.** Backend sudah
  menghasilkan teks 58/80 mm dan ESC/POS base64, tetapi jembatan native ke
  printer Bluetooth/USB (raw ESC/POS) belum ada. `window.print()` WebView juga
  bukan jalur cetak yang cocok untuk printer thermal.
- **Tombol "Unduh backup" (blob URL)** belum ditangani `DownloadListener`,
  jadi di APK file backup tidak tersimpan dari tombol itu. Backup otomatis ke
  Telegram tetap berjalan; restore memakai pemilih file (sudah didukung).
- **Scheduler backup Telegram hanya hidup selama proses aplikasi berjalan.**
  Backup terjadwal jam 21:00 baru terkirim jika aplikasi sedang terbuka;
  backend tidak berjalan sebagai service latar belakang.
- **Proses bisa dimatikan Android** saat aplikasi di latar belakang. Data aman
  di SQLite, dan server dijalankan lagi saat aplikasi dibuka.
- APK belum pernah dikompilasi/diuji di mesin ini (tidak ada JDK/Gradle/SDK).
  Semua validasi yang bisa dilakukan: test backend (64 lulus di pydantic v2
  dan v1), simulasi ekstraksi paket backend + bootstrap uvicorn (health,
  autentikasi token, restart dengan token baru), serta scan sintaks Kotlin/XML.
