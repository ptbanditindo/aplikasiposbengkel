# PIN Aplikasi Android (BengkelPOS Radiator)

Modul PIN untuk rencana APK. Kode ada di `android/` dan belum pernah dikompilasi
di mesin ini (tidak ada JDK, Gradle, Kotlin, maupun Android SDK terpasang).

## Status penting

- Gerbang PIN, reset, dan shell WebView sudah ditulis lengkap.
- Backend Python **sudah dikemas** ke dalam APK memakai Chaquopy 16 (Python
  3.10). Lihat `README_APK.md` untuk arsitektur, build, dan batasannya.
- Reset data menghentikan server lokal lebih dulu (menutup SQLite) sebelum
  menghapus file, lalu server dinyalakan ulang dengan database dan token admin
  baru.
- APK belum bisa diuji di perangkat. Unit test sudah ditulis tetapi belum
  dijalankan di mesin ini (tidak ada JDK/Android SDK).

## Alur yang diimplementasikan

1. **Instalasi pertama** — layar "Buat PIN" 6 angka, lalu "Konfirmasi PIN".
   Jika berbeda, muncul "PIN tidak sama" dan alur kembali ke langkah pertama.
   PIN disimpan sebagai hash + salt, lalu aplikasi terbuka.
2. **Setiap aplikasi dibuka** — `PinActivity` adalah satu-satunya activity
   launcher, sehingga PIN selalu diminta sebelum data tampil. `MainActivity`
   tidak diekspor.
3. **Kembali dari latar belakang** — `PinActivity` diminta lagi bila durasi di
   latar belakang melewati batas. Bawaannya 1 menit dan dapat diubah di
   Pengaturan → "Keamanan aplikasi (APK)" (1/2/5/10/30 menit).
   Ada juga tombol "Kunci sekarang".
4. **PIN salah** — jumlah percobaan disimpan permanen di penyimpanan terenkripsi
   (`commit()`), jadi menutup aplikasi tidak mereset hitungan. Hitungan hanya
   kembali nol setelah PIN benar. Pesan hanya "PIN salah" tanpa petunjuk digit,
   disertai getar dan goyang titik. Keypad dinonaktifkan selama kunci berjalan
   dan hitung mundur ditampilkan.

| Percobaan gagal | Efek |
| --- | --- |
| 1–2 | "PIN salah, sisa percobaan sebelum dikunci: 2 / 1" |
| 3–4 | kunci 30 detik |
| 5–6 | kunci 5 menit |
| 7–9 | kunci 30 menit |
| 10 dan seterusnya | kunci 1 jam pada setiap kegagalan berikutnya |

Durasi kunci memakai dua jam sekaligus (`SystemClock.elapsedRealtime()` dan jam
dinding); sisa waktu diambil yang **terbesar**. Elapsed yang kembali ke nol
(reboot) atau jam dinding yang dimundurkan tidak memperpendek kunci.

5. **Lupa PIN** — dialog peringatan, lalu konfirmasi kedua dengan mengetik
   `RESET`. Setelah itu data lokal dihapus (database, pengaturan, hash PIN,
   data WebView) dan kunci Keystore dihapus, sehingga hash PIN lama tidak bisa
   dipakai lagi. Pengguna membuat PIN baru, lalu memulihkan data dari backup
   Telegram secara manual.

## Penyimpanan dan keamanan

- Hash: PBKDF2-HMAC-SHA256, 210.000 iterasi, salt acak 16 byte, 256-bit output.
  Format tersimpan menyertakan jumlah iterasi agar bisa dinaikkan nanti.
- Hash dan status kunci disimpan di `EncryptedSharedPreferences` (AES256-GCM,
  kunci di Android Keystore). PIN mentah tidak pernah disimpan atau dicatat.
- Layar PIN dan WebView memakai `FLAG_SECURE` (tidak muncul di recents/screenshot).
- `allowBackup="false"` plus `data_extraction_rules.xml` agar hash tidak ikut
  Android Auto Backup / transfer perangkat.
- WebView hanya mengizinkan navigasi ke `127.0.0.1` / `localhost`; tautan
  eksternal diblokir. File dan content access dimatikan, mixed content ditolak.
- `BengkelApp` mencatat waktu aplikasi masuk latar belakang; status sesi hanya
  di memori proses, sehingga proses yang mati selalu meminta PIN lagi.

## Restore setelah reset

Bot Telegram **tidak dapat mengunduh file yang dikirim oleh bot itu sendiri**,
jadi pemulihan otomatis dari chat tidak bisa dilakukan lewat Bot API. Setelah
reset, pengguna harus:

1. Membuka chat Telegram dan mengunduh file `.db` backup terakhir.
2. Membuat PIN baru saat diminta.
3. Membuka Pengaturan → "Pulihkan database" dan memilih file tersebut.

Pemilih file untuk `<input type="file">` sudah ditangani `WebChromeClient` di
`MainActivity`, dengan tipe `*/*` agar file `.db` tetap bisa dipilih.

Konsekuensinya file backup di Telegram memuat seluruh data transaksi. Siapa pun
yang bisa membaca chat bot dapat membaca data itu. Saran: batasi anggota chat,
hapus pesan backup lama setelah diunduh, dan pertimbangkan enkripsi file backup
pada iterasi berikutnya.

## Struktur file

```
android/app/src/main/java/com/bengkelpos/radiator/
  BengkelApp.kt              start Python + pencatat waktu latar belakang
  MainActivity.kt            shell WebView, token admin, jembatan "BengkelPin"
  backend/BackendManager.kt  start/stop server uvicorn
  backend/BackendInstaller.kt ekstrak bengkel_backend.zip ke codeCacheDir
  backend/BackendHealth.kt   polling /api/health sebelum loadUrl()
  pin/PinActivity.kt         layar buat/konfirmasi/buka PIN + reset
  pin/PinStore.kt            hash, hitungan gagal, status kunci, token admin
  pin/PinHasher.kt           PBKDF2 + salt
  pin/LockoutPolicy.kt       tabel durasi kunci
  pin/LockoutState.kt        perhitungan sisa kunci dua jam
  pin/PinSession.kt          status sesi di memori
  pin/PinSettings.kt         batas kunci otomatis (menit)
  pin/LocalDataResetter.kt   hentikan server + hapus data lokal + kunci Keystore
android/app/src/main/python/bootstrap.py   uvicorn di dalam proses APK
android/app/src/test/java/com/bengkelpos/radiator/pin/
  LockoutPolicyTest.kt, LockoutStateTest.kt, PinSessionTest.kt
```

## Build

Prasyarat: JDK 17, Android SDK 35, dan Python 3.10+ di mesin build (dipakai
Chaquopy untuk pip). Berkas `gradle/wrapper/gradle-wrapper.jar` belum ada;
buat sekali dengan Gradle yang terpasang (`gradle wrapper`) atau buka folder
`android/` di Android Studio. Detail lengkap ada di `README_APK.md`.

```bash
cd android
./gradlew test
./gradlew assembleDebug
```

## Belum dikerjakan

- Cetak struk ke printer thermal dari dalam WebView (butuh jembatan native
  ESC/POS; backend sudah menyiapkan teks & base64).
- Tombol "Unduh backup" memakai blob URL di WebView; unduhan blob belum
  ditangani `DownloadListener`, jadi di APK tombol itu belum menyimpan file.
- Ganti PIN dari dalam aplikasi.
- Enkripsi file backup Telegram.
- Verifikasi di perangkat: pembukaan ulang, latar belakang, reboot, ubah jam,
  dan alur reset → restore.
