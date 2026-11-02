# Rencana Pengembangan Tahap Final — PusatkuPOS

Status: **final** — 2026-11-03. Belum diimplementasikan.

## Identitas produk

- Nama produk baru: **PusatkuPOS**.
- Nama ini dipakai untuk aplikasi Flutter Android, Windows EXE, dan Mac.
- Aplikasi 2.7.0 yang berjalan sekarang tetap **BengkelPOS Radiator**.
- Package Android, nama database, dan format backup aplikasi lama tidak diubah
  pada tahap ini agar update dan data pengguna tetap aman.

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
  menjadi acuan perilaku; data lamanya tidak wajib dimigrasikan.
- **Data awal:** belum ada konsumen. Data dummy/pengembangan boleh dimulai
  ulang; migrasi data lama bukan syarat rilis.
- **Gratis:** satu perangkat, lokal penuh, tanpa panggilan API.
- **Premium:** modul Karyawan, Supplier, Follow up, semua tombol WhatsApp, dan
  backup otomatis; tetap satu perangkat dan offline-first.
- **Ditunda:** sinkronisasi API, multi-device, hub/LAN, dan aplikasi
  owner/karyawan. Semua itu tahap jauh, bukan premium awal.
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
- Premium awal tetap lokal dan satu perangkat. Sinkronisasi API, multi-device,
  hub/LAN, dan aplikasi owner/karyawan ditunda ke tahap jauh.
- Free tidak memanggil API developer. Premium hanya memanggil API untuk akun,
  lisensi, atau kuota—bukan untuk menyimpan nota.
- Bila sinkronisasi diaktifkan nanti, status “belum tersinkron” terlihat dan
  dapat dicoba ulang.
- Backup lokal dan restore harus tetap berfungsi tanpa akun dan tanpa internet.
- Jam transaksi memakai waktu lokal; bila sync diaktifkan nanti, waktu server
  dipakai untuk urutan perubahan.

## Ruang lingkup MVP

1. Kasir: pelanggan, unit, jasa, sparepart, pembayaran, nota, dan struk.
2. Stok: masuk/keluar, minimum stok, ringkasan, dan peringatan.
3. Riwayat servis, retur, void, garansi, dan laporan harian.
4. Backup lokal, restore, dan format database/Excel/CSV.
5. PIN/keamanan lokal dan pengaturan bengkel.
6. Printer pada Android dan Windows; Mac menyusul di tahap Mac.
7. Uji parity uang, stok, nomor nota, retur, dan laporan dengan versi Python.
8. Fitur lanjutan—follow-up, supplier, karyawan, komisi—setelah inti stabil.
9. Premium lokal: lisensi, gating modul, kuota WA, dan backup otomatis.
10. Sync API, multi-device, owner/karyawan app: **ditunda**.

## Tahapan

1. **Fondasi Flutter:** struktur proyek, SQLite, model data, uang decimal, dan
   kerangka tes lintas platform.
2. **Inti kasir:** pelanggan, unit, jasa, sparepart, pembayaran, nota, struk.
3. **Stok dan laporan:** pergerakan stok, ringkasan, laporan, retur, void,
   garansi.
4. **Backup dan restore:** backup lokal, restore, dan rollback pengujian.
5. **Android:** PIN, printer, folder backup, WorkManager, APK per ABI/AAB.
6. **Windows EXE:** printer, file backup, installer, dan update.
7. **Mac:** `.app`/`.dmg`, printer, signing, notarization.
8. **Premium lokal:** lisensi, gating modul, kuota WA, dan backup otomatis.
   Sync API, multi-device, owner/karyawan app ditunda.
9. **Uji akhir:** matriks Android/Windows/Mac, offline, backup/restore, dan
   parity.

## Backup dan keamanan data

- Belum ada konsumen; data dummy/pengembangan boleh direset. Backup tetap
  dibuat sebelum menghapus atau mengubah data uji secara besar.
- Backup lokal dan restore harus aman dan dapat diuji tanpa cloud.
- PIN disimpan di penyimpanan aman platform; token premium tidak pernah masuk
  database biasa.
- Data cloud premium dienkripsi dan dipisahkan per tenant.

## Risiko utama

- Rewrite besar; parity uang/stok harus diuji terhadap versi Python.
- Printer dan file picker berbeda di tiap platform; adapter tidak bisa
  disamakan mentah-mentah.
- macOS membutuhkan mesin Mac, Xcode, signing, dan notarization.
- Multi-device premium rawan konflik jika beberapa perangkat menulis transaksi
  saat offline; aturan konflik harus selesai sebelum fitur itu nanti dirilis.
- APK/EXE/Mac akan lebih kecil dari versi Python, tetapi bukan “tanpa kode”;
  ukuran tetap bergantung pada dependensi dan aset.

## Non-goals tahap ini

- iOS.
- Web sebagai target aplikasi.
- Multi-device (ditunda).
- Sinkronisasi cloud sebagai syarat transaksi.
- Mempertahankan Python/Chaquopy di paket baru.
