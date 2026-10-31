# PIN Aplikasi Android (BengkelPOS Radiator)

Modul PIN untuk APK. Kode ada di `android/` dan sudah dikompilasi dengan
toolchain portabel di `android/.toolchain` (JDK 17, Gradle 8.7, Android SDK 35,
Python 3.12.10 sebagai build Python).

## Status penting

- Gerbang PIN, reset, dan shell WebView sudah ditulis lengkap.
- Backend Python **sudah dikemas** ke dalam APK memakai Chaquopy 16 (Python
  3.10). Lihat `README_APK.md` untuk arsitektur, build, dan batasannya.
- Reset PIN **hanya menghapus hash PIN**; database, transaksi, stok, backup,
  dan token instalasi tetap utuh. Server lokal tidak perlu dihentikan.
- Unit test JVM sudah dijalankan (150 test lulus, termasuk PIN, backup, dan
  printer). APK Debug v2.2.2 sudah di-build ulang dan memuat perubahan kunci
  otomatis, pemilihan folder backup, serta lingkaran loading saat server
  disiapkan, tetapi perilakunya belum diuji di perangkat fisik.

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
   Waktu masuk latar belakang disimpan ke disk, jadi batas ini tetap berlaku
   ketika sistem mematikan proses aplikasi: membuka kembali sebelum batas tidak
   meminta PIN, melewati batas meminta PIN. Reboot perangkat selalu meminta PIN.
   Tombol "Kunci sekarang" selalu meminta PIN pada pembukaan berikutnya.
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
   `RESET` (tidak peka huruf besar/kecil). Hanya hash PIN yang dihapus; data
   pelanggan, transaksi, stok, backup, dan token instalasi tidak disentuh.
   Pengguna langsung membuat PIN baru di layar yang sama, dan PIN baru langsung
   berlaku setelah aplikasi ditutup dan dibuka lagi.

## Penyimpanan dan keamanan

- Hash: PBKDF2-HMAC-SHA256, 210.000 iterasi, salt acak 16 byte, 256-bit output.
  Format tersimpan menyertakan jumlah iterasi agar bisa dinaikkan nanti.
- Hash dan status kunci disimpan di `EncryptedSharedPreferences` (AES256-GCM,
  kunci di Android Keystore). PIN mentah tidak pernah disimpan atau dicatat.
- Layar PIN memakai `FLAG_SECURE` agar PIN tidak muncul di recents atau screenshot.
  Layar utama (WebView) tidak memakai `FLAG_SECURE`, sehingga nota, laporan, dan
  tampilan operasional lain dapat di-screenshot; `privacyCover` tetap menutup
  pratinjau recents saat aplikasi masuk latar belakang.
- `allowBackup="false"` plus `data_extraction_rules.xml` agar hash tidak ikut
  Android Auto Backup / transfer perangkat.
- WebView hanya mengizinkan navigasi ke `127.0.0.1` / `localhost`; tautan
  eksternal diblokir. File dan content access dimatikan, mixed content ditolak.
- `BengkelApp` mencatat waktu aplikasi masuk latar belakang ke `pin_settings`
  (SharedPreferences biasa, bukan rahasia) beserta penanda "Kunci sekarang".
  Status sesi sendiri tetap di memori proses. Karena penanda latar belakang
  tersimpan, batas kunci otomatis tidak hilang saat proses dimatikan sistem.
  Reboot dikenali dari `elapsedRealtime()` yang kembali lebih kecil dan memaksa
  PIN. Proses yang mati saat aplikasi di depan (crash atau force stop) juga
  meminta PIN karena tidak ada penanda latar belakang yang tersimpan.
- Reset PIN adalah jalur darurat bagi pemilik perangkat, **bukan** pengaman
  terhadap orang yang memegang perangkat. Siapa pun yang bisa mengetik `RESET`
  dapat membuat PIN baru dan membuka data yang sudah ada di perangkat itu.
  Karena itu database APK tetap terlindungi hanya oleh kunci perangkat dan
  akses fisik, bukan oleh PIN.

## Restore database dari backup

Reset PIN tidak menghapus data, jadi pemulihan tidak diperlukan setelah reset.
Restore hanya dipakai bila database memang rusak atau perangkat diganti.

Bot Telegram **tidak dapat mengunduh file yang dikirim oleh bot itu sendiri**,
jadi pemulihan otomatis dari chat tidak bisa dilakukan lewat Bot API. Pengguna
harus:

1. Membuka chat Telegram dan mengunduh file `.db` backup terakhir.
2. Membuka Pengaturan → "Pulihkan database" dan memilih file tersebut.

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
  MainActivity.kt            shell WebView, token instalasi, jembatan "BengkelPin"
  backend/BackendManager.kt  start/stop server uvicorn
  backend/BackendInstaller.kt ekstrak bengkel_backend.zip ke codeCacheDir
  backend/BackendHealth.kt   polling /api/health sebelum loadUrl()
  pin/PinActivity.kt         layar buat/konfirmasi/buka PIN + reset
  pin/PinStore.kt            hash, hitungan gagal, status kunci, clearPin()
  pin/PinHasher.kt           PBKDF2 + salt
  pin/PinEnrollment.kt       pencocokan PIN + konfirmasi sebelum disimpan
  pin/PinResetKeyword.kt     konfirmasi kata kunci RESET
  pin/LockoutPolicy.kt       tabel durasi kunci
  pin/LockoutState.kt        perhitungan sisa kunci dua jam
  pin/PinSession.kt          status sesi di memori + pemulihan setelah proses mati
  pin/SessionStore.kt        kontrak penyimpanan waktu latar belakang
  pin/PinSettings.kt         batas kunci otomatis (menit) + SessionStore
  pin/LocalDataResetter.kt   pembersih data total (tidak dipakai alur reset PIN)
android/app/src/main/python/bootstrap.py   uvicorn di dalam proses APK
android/app/src/test/java/com/bengkelpos/radiator/pin/
  LockoutPolicyTest.kt, LockoutStateTest.kt, PinSessionTest.kt,
  PinHasherTest.kt, PinEnrollmentTest.kt, PinResetKeywordTest.kt
```

## Build

Prasyarat: JDK 17, Android SDK 35, dan Python 3.12.10 di mesin build (dipakai
Chaquopy untuk pip; runtime APK tetap Python 3.10). Toolchain portabel proyek
ada di `android/.toolchain` dan `android/local.properties` menunjuk ke SDK itu.
Detail lengkap ada di `README_APK.md`.

```bash
cd android
./gradlew test
./gradlew assembleDebug
```

## Belum dikerjakan

- Ganti PIN dari dalam aplikasi (saat ini reset lewat kata kunci `RESET`).
- Enkripsi file backup Telegram.
- Verifikasi di perangkat fisik: pembukaan ulang, latar belakang, reboot, ubah
  jam, screenshot layar utama vs layar PIN, serta alur reset → restore.
- Verifikasi cetak pada model printer thermal nyata (jalur Bluetooth, Wi-Fi/LAN,
  USB OTG, dan cetak Android sudah tersedia).
