# Rencana Pengembangan Akhir

Status: **final** — 2026-11-03. Belum diimplementasikan.

## Tujuan

Aplikasi kasir bengkel yang berjalan di **Android, Windows (EXE), dan Mac**.
Semua platform **offline-first**: kasir, stok, nota, struk, laporan, dan backup
berjalan penuh tanpa internet. Sinkronisasi cloud hanya lapisan premium dan
tidak pernah menjadi syarat transaksi.

APK/EXE/aplikasi Mac tidak lagi membawa runtime Python, FastAPI, Chaquopy,
site-packages, backend zip, atau frontend web. Aplikasi dibangun sebagai
aplikasi lintas platform yang nyata, bukan WebView wrapper.

## Keputusan final

- **Teknologi:** Flutter + Dart untuk UI dan logika bisnis.
- **Database lokal:** SQLite melalui drift/FFI. Satu sumber kebenaran lokal di
  semua platform.
- **Paket:** APK/AAB Android, installer EXE Windows, `.app`/`.dmg` macOS.
- **Tanpa Python:** backend Python tidak ikut ke paket baru. Versi lama hanya
  menjadi acuan perilaku dan migrasi data.
- **Gratis:** satu perangkat, lokal penuh, tanpa panggilan API.
- **Premium:** sinkronisasi API dan multi-device; tetap offline-first.
- **Apple:** target tahap ini macOS. iOS bukan target tahap ini.

## Arsitektur

- **UI dan logika bisnis** berada di Dart dan dipakai bersama ketiga platform.
- **Lapisan data** memakai repository/service di atas SQLite; semua perhitungan
  uang memakai decimal dan pembulatan yang sama dengan versi Python.
- **Platform adapter** menangani printer, pemilih folder, file backup, PIN,
  autostart, update, dan integrasi sistem. Android dapat memakai kembali
  sebagian kode Kotlin lama lewat platform channel; Windows dan Mac memakai
  adapter masing-masing.
- **Sinkronisasi premium** memakai antrean lokal (outbox), idempotency, dan
  retry. API mati atau kuota habis tidak menghentikan kasir.
- **Lisensi premium** memiliki masa tenggang offline; kegagalan API tidak
  mengunci transaksi.
- **Backup lokal** tetap menjadi cadangan utama. Sinkronisasi bukan pengganti
  backup.

## Platform

| Platform | Paket | Catatan |
| --- | --- | --- |
| Android | APK per ABI atau AAB | minSdk 26; printer Bluetooth/USB/Wi-Fi; backup folder/SAF; WorkManager pengganti |
| Windows | Installer EXE | printer USB/jaringan/cetak sistem; file backup; autostart opsional |
| Mac | `.app` dan `.dmg` | universal Intel/Apple Silicon; printer jaringan/sistem; signing dan notarization |

## Aturan offline-first

- Tidak ada panggilan API di jalur simpan nota, stok, pembayaran, atau struk.
- Semua data inti tersedia setelah aplikasi dibuka tanpa internet.
- Sinkronisasi premium berjalan di latar belakang; status “belum tersinkron”
  terlihat dan dapat dicoba ulang.
- Free tidak memanggil API developer. Premium hanya mengaktifkan sync,
  multi-device, owner, dan fitur cloud.
- Backup lokal dan restore harus tetap berfungsi tanpa akun dan tanpa internet.
- Jam transaksi memakai waktu lokal; saat sync, waktu server dipakai untuk
  urutan perubahan.

## Ruang lingkup MVP

1. Kasir: pelanggan, unit, jasa, sparepart, pembayaran, nota, dan struk.
2. Stok: masuk/keluar, minimum stok, ringkasan, dan peringatan.
3. Riwayat servis, retur, void, garansi, dan laporan harian.
4. Backup lokal, restore, dan format database/Excel/CSV.
5. PIN/keamanan lokal dan pengaturan bengkel.
6. Printer pada Android dan Windows; Mac menyusul di tahap Mac.
7. Migrasi database APK/desktop lama.
8. Uji parity uang, stok, nomor nota, retur, dan laporan dengan versi Python.
9. Fitur lanjutan—follow-up, supplier, karyawan, komisi—setelah inti stabil.
10. Premium sync dan multi-device setelah versi lokal stabil.

## Tahapan

1. **Fondasi Flutter:** struktur proyek, SQLite, model data, uang decimal, dan
   kerangka tes lintas platform.
2. **Inti kasir:** pelanggan, unit, jasa, sparepart, pembayaran, nota, struk.
3. **Stok dan laporan:** pergerakan stok, ringkasan, laporan, retur, void,
   garansi.
4. **Backup dan migrasi:** backup lokal, restore, impor database APK/desktop
   lama, rollback.
5. **Android:** PIN, printer, folder backup, WorkManager, APK per ABI/AAB.
6. **Windows EXE:** printer, file backup, installer, dan update.
7. **Mac:** `.app`/`.dmg`, printer, signing, notarization.
8. **Premium:** lisensi, outbox, API sync, multi-device, owner/karyawan.
9. **Uji akhir:** matriks Android/Windows/Mac, offline, migrasi, dan parity.

## Migrasi dan keamanan data

- Backup database lama wajib dibuat sebelum impor.
- Impor harus mempertahankan pelanggan, unit, nota, pembayaran, stok, retur,
  pengaturan, dan riwayat.
- Migrasi harus dapat diulang dan gagal dengan aman tanpa merusak database
  lama.
- PIN disimpan di penyimpanan aman platform; token premium tidak pernah masuk
  database biasa.
- Data cloud premium dienkripsi dan dipisahkan per tenant.

## Risiko utama

- Rewrite besar; parity uang/stok harus diuji terhadap versi Python.
- Printer dan file picker berbeda di tiap platform; adapter tidak bisa
  disamakan mentah-mentah.
- macOS membutuhkan mesin Mac, Xcode, signing, dan notarization.
- Multi-device premium tetap rawan konflik jika beberapa perangkat menulis
  transaksi saat offline; aturan konflik harus selesai sebelum fitur itu
  dirilis.
- APK/EXE/Mac akan lebih kecil dari versi Python, tetapi bukan “tanpa kode”;
  ukuran tetap bergantung pada dependensi dan aset.

## Non-goals tahap ini

- iOS.
- Web sebagai target aplikasi.
- Multi-device gratis.
- Sinkronisasi cloud sebagai syarat transaksi.
- Mempertahankan Python/Chaquopy di paket baru.
