# Rencana Pengembangan Tahap Final — PusatkuPOS

Status: **final** — 2026-11-03. Belum diimplementasikan.

## Identitas produk

- Nama produk baru: **PusatkuPOS**.
- Nama ini dipakai untuk aplikasi Flutter Android, Windows EXE, dan Mac.
- Aplikasi 2.7.0 yang berjalan sekarang tetap **BengkelPOS Radiator** (web).
  Multi-toko dan fitur premium dibangun di aplikasi ini lebih dulu sebagai kanal
  uji web, lalu dibawa ke PusatkuPOS Flutter.
- Package Android, nama database, dan format backup aplikasi lama tidak diubah
  pada tahap ini agar update dan data pengguna tetap aman.

## Tujuan

Aplikasi kasir bengkel yang berjalan di **Android, Windows (EXE), dan Mac**.
Semua platform **offline-first**: kasir, stok, nota, struk, laporan, dan backup
berjalan penuh tanpa internet. Pertukaran data lewat API relay hanya lapisan
premium dan tidak pernah menjadi syarat transaksi.

APK/EXE/aplikasi Mac tidak lagi membawa runtime Python, FastAPI, Chaquopy,
site-packages, backend zip, atau frontend web. Aplikasi dibangun sebagai
aplikasi lintas platform yang nyata, bukan WebView wrapper.

## Keputusan final

- **Teknologi:** Flutter + Dart untuk UI dan logika bisnis.
- **Distribusi modular patuh Play dan App Store:** paket dasar berisi shell dan
  seluruh logika fitur. Saat login pertama, yang diunduh hanya paket resource per
  peran (layout, aset, label, konfigurasi tampilan), bukan kode. Android memakai
  Play Asset Delivery; iOS masa depan memakai unduhan aset/On-Demand Resources;
  Windows memakai CDN bertanda tangan. Tidak ada dex/JAR/so, tidak ada
  self-update, dan paket tidak boleh menambah fitur yang tidak ada di shell.
- **Langganan Android:** fitur digital dijual sebagai langganan lewat Google
  Play Billing; restore, acknowledge, perpanjangan, dan pembatalan berjalan.
  Windows/macOS memakai penyedia saat tahap lisensi. Tidak ada tautan pembayaran
  digital eksternal yang melanggar kebijakan Play.
- **Database lokal:** SQLite melalui drift/FFI. Satu sumber kebenaran lokal di
  semua platform. Setiap database memiliki `database_id` unik yang hanya dipakai
  mencatat pemakaian trial; ID ini tidak mengikat pemilik atau perangkat.
- **Paket:** AAB Android lewat Play (APK sideload fallback penuh/split),
  installer EXE Windows, `.app`/`.dmg` macOS.
- **Tanpa Python:** backend Python tidak ikut ke paket baru. Versi lama hanya
  menjadi acuan perilaku; data lamanya tidak wajib dimigrasikan. Setelah Flutter
  stabil, aplikasi Python lama **disimpan** sebagai arsip/acuan dan tidak
  dihapus.
- **Data awal:** belum ada konsumen. Data dummy/pengembangan boleh dimulai
  ulang; migrasi data lama bukan syarat rilis.
- **Skema database:** dirancang baru untuk PusatkuPOS; tidak ada kewajiban
  kompatibilitas dengan database 2.x.
- **Gratis:** satu perangkat, lokal penuh, tanpa panggilan API data. Paket
  resource dasar diunduh satu kali; setelah terpasang, aplikasi berjalan offline.
- **Premium:** fitur Karyawan, Supplier, Follow up, semua tombol WhatsApp, dan
  backup otomatis; offline-first. Premium dijual sebagai **langganan bulanan**,
  bukan sekali bayar. Batas perangkat mengikuti paket (contoh arah:
  Rp10.000/bulan = 2 perangkat); jumlah toko tetap tanpa batas.
- **Data terkunci:** saat langganan berakhir atau turun paket, data Karyawan,
  Supplier, dan Follow up lama tetap dapat dibaca dan diekspor; hanya
  tambah/ubah data dan aksi premium yang diblokir.
- **Akun:** pemilik memakai Google dan memiliki ID owner unik global 8 karakter
  acak (huruf kecil/angka, tanpa `0`, `1`, `l`, `o`) yang ditampilkan sebagai
  kartu teks + tombol salin + QR. Karyawan login dengan ID owner + username +
  password tanpa Google. Password minimal 8 karakter, unik antar karyawan satu
  owner, dan direset pemilik; pemilik dapat memakai tombol acak untuk mengisi
  password otomatis lalu tombol salin semua untuk mengirim ID owner + username +
  password sekaligus. Password hanya tampil sekali. PIN 6 digit diatur karyawan
  sendiri.
- **Lisensi offline:** token bertanda tangan + hitung mundur di perangkat; VPS
  tidak menyimpan data bengkel. Jika langganan berakhir saat ada delta pending,
  delta dikirim lebih dulu saat online lalu pengiriman berhenti sampai aktif
  kembali.
- **Ditunda:** sinkronisasi API, multi-device, hub/LAN, mode karyawan, dan
  aplikasi owner terpisah. Multi-device mengikuti batas perangkat paket premium,
  tetapi tetap tahap lanjutan, bukan fitur gratis atau trial.
- **Aplikasi utama:** memuat seluruh core logic; dipakai owner tanpa karyawan
  dan karyawan. Owner tanpa karyawan dapat membuka semua fitur, dengan fitur
  premium terkunci bila akun gratis.
- **Aplikasi owner:** aplikasi terpisah tanpa core logic; hanya ringkasan hari
  ini per toko, laporan, pembuatan akun karyawan, pemberian/pencabutan izin
  tambahan per karyawan, reset password/PIN, pencabutan perangkat, dan riwayat
  perubahan izin.
- **Mode karyawan:** di aplikasi utama; operasional sesuai peran dasar ditambah
  izin tambahan yang diberikan pemilik per akun (contoh: Budi kasir + opname),
  serta menjadi sumber absensi, status pengerjaan, komisi, dan performa. Izin
  tambahan tidak mengubah peran dasar, tarif komisi, atau aturan penulis uang.
- **Rencana terpisah:** multi-toko, login, header toko, fitur premium, dan
  backup semua toko ada di `RENCANA_MULTI_TOKO_PREMIUM.md`; pengujiannya ada di
  `RENCANA_PEMANTAPAN.md`. Implementasi dan uji pertama dilakukan di web
  BengkelPOS Radiator, lalu di-port ke PusatkuPOS Flutter.
- **Apple:** target tahap ini macOS. iOS bukan target tahap ini.

## Arsitektur

- **UI dan logika bisnis** berada di Dart dan dipakai bersama ketiga platform.
- **Shell modular** berisi launcher, login, SQLite, sync, printer, backup, izin,
  pengelola paket resource, dan seluruh logika fitur.
- **Paket resource per peran** berisi layout, aset, label, dan konfigurasi
  tampilan: kasir, stok, servis, laporan, karyawan, supplier, follow up, dan
  ringkasan owner. Paket tidak berisi kode dan tidak menambah fitur; paket hanya
  menampilkan fitur shell yang sudah ada dan diizinkan. Login pertama hanya
  mengunduh paket peran itu; peran tambahan mengunduh paket tambahan dan
  menyimpannya di cache.
- **Android** memakai AAB + Play Asset Delivery untuk paket resource. Tidak ada
  unduhan kode dan tidak ada self-update.
- **iOS masa depan** memakai paket resource yang sama lewat unduhan aset atau
  On-Demand Resources. Tidak ada executable code yang diunduh; ini mengikuti
  App Store Review Guidelines 2.5.2.
- **Windows** memakai installer shell + paket resource bertanda tangan dari CDN.
  Logika uang/stok dan izin tetap di shell; Windows tidak memuat kode Dart/DLL
  baru saat runtime. EXE lebih ringan, tetapi tidak se-extreme paket kode.
- **Paket offline:** setelah paket resource terpasang, fitur berjalan tanpa
  internet. Jika paket belum terpasang dan perangkat offline, fitur terkunci
  dengan pesan jelas; data lain tetap aman.
- **Izin tetap di shell.** Paket yang terpasang tidak membuka akses di luar
  peran; izin tambahan per karyawan bersifat aditif dan tidak dapat memberi akses
  khusus pemilik; permintaan langsung ke data tetap ditolak di lapisan data.
- **Lapisan data** memakai repository/service di atas SQLite; semua perhitungan
  uang memakai decimal dan pembulatan yang sama dengan versi Python.
- **Platform adapter** menangani printer, pemilih folder, file backup, PIN,
  notifikasi lokal, autostart, update, dan integrasi sistem. Android dapat
  memakai kembali sebagian kode Kotlin lama lewat platform channel; Windows dan
  Mac memakai adapter masing-masing.
- **Sinkronisasi premium** memakai antrean lokal (outbox), idempotency, retry,
  dan penggabungan berurutan dengan jam logis (HLC). Banyak akun/perangkat dapat
  menulis offline; saat internet mati, delta pending dan aplikasi wajib
  memberi notifikasi. API mati atau kuota habis tidak menghentikan kasir.
- **Lisensi premium** memakai token bertanda tangan dan hitung mundur offline;
  kegagalan API tidak mengunci transaksi. Saat langganan berakhir dan ada delta
  pending, delta dikirim lebih dulu saat online lalu pengiriman berhenti sampai
  aktif kembali. VPS tidak menyimpan data bengkel.
- **Backup lokal** tetap menjadi cadangan utama. Sinkronisasi bukan pengganti
  backup.

## Platform

| Platform | Paket | Catatan |
| --- | --- | --- |
| Android | AAB (Play) | base shell + Play Asset Delivery per peran; paket resource, bukan kode; minSdk 26; printer Bluetooth/USB/Wi-Fi; backup folder/SAF; WorkManager pengganti |
| Windows | Installer EXE | shell + paket resource bertanda tangan; printer USB/jaringan/cetak sistem; file backup; autostart opsional |
| iOS (masa depan) | IPA (App Store) | paket resource yang sama lewat unduhan aset/On-Demand Resources; tanpa executable code; target setelah macOS |
| Mac | `.app` dan `.dmg` | universal Intel/Apple Silicon; printer jaringan/sistem; signing dan notarization |

## Aturan offline-first

- Tidak ada panggilan API di jalur simpan nota, stok, pembayaran, atau struk.
- Semua data inti tersedia setelah aplikasi dibuka tanpa internet.
- Login pertama dan unduhan paket resource peran membutuhkan internet/Play.
  Setelah paket terpasang, fitur berjalan offline.
- Jika paket resource belum terpasang dan perangkat offline, fitur terkunci
  dengan pesan jelas; pengguna dapat mengunduh saat online tanpa kehilangan data.
- Free tier mengunduh paket resource dasar satu kali; unduhan Play bukan
  panggilan API data dan tidak mengirim data bengkel.
- Paket resource tidak menambah fitur atau logika baru; semua logika, izin, dan
  perhitungan uang/stok tetap di shell. Paket hanya mengatur tampilan, label,
  aset, dan konfigurasi tampilan peran.
- Premium berjalan lokal lebih dulu dengan batas perangkat sesuai paket
  langganan. Sinkronisasi API dan multi-device lewat relay, hub/LAN, mode
  karyawan, dan aplikasi owner ditunda ke tahap lanjut.
- Langganan berakhir tidak mengunci kasir atau menghapus data. Data fitur
  Karyawan, Supplier, dan Follow up tetap dapat dibaca/diekspor; delta pending
  dikirim lebih dulu saat online, lalu pengiriman berhenti sampai aktif kembali.
- Free tidak memanggil API. Premium memanggil API hanya untuk akun, lisensi,
  kuota, dan meneruskan delta—bukan untuk menyimpan nota.
- Bila sinkronisasi diaktifkan nanti, status “belum tersinkron” dan jumlah delta
  pending terlihat dan dapat dicoba ulang.
- Relay tidak harus langsung: saat internet mati, delta tetap pending di outbox
  perangkat dan dikirim berurutan saat online.
- Banyak akun karyawan, misalnya 100 akun, dapat mencatat riwayat dan menambah
  stok saat offline. Delta digabung berurutan saat online; stok sementara
  ditandai belum lengkap sampai pending terkirim.
- Pending tidak kedaluwarsa walau internet mati berbulan-bulan. Aplikasi wajib
  menampilkan banner, badge, dan notifikasi sistem berkala selama pending ada;
  notifikasi tidak dapat dimatikan permanen.
- Backup lokal dan restore harus tetap berfungsi tanpa akun dan tanpa internet.
  Backup menyertakan outbox pending.
- Jam transaksi memakai waktu lokal untuk tampilan. Urutan perubahan memakai
  nomor urut perangkat, bukan waktu terima relay.

## Ruang lingkup MVP

Fondasi modular—shell, pengelola paket resource, manifest peran, dan distribusi
paket resource (Play Asset Delivery di Android, ODR/unduhan aset di iOS nanti)—
dikerjakan lebih dulu sebelum fitur peran.

1. Kasir: pelanggan, unit, jasa, sparepart, pembayaran, nota, dan struk.
2. Stok: masuk/keluar, minimum stok, ringkasan, dan peringatan.
3. Riwayat servis, retur, void, garansi, dan laporan harian.
4. Backup lokal, restore, dan format database/Excel/CSV.
5. PIN/keamanan lokal dan pengaturan bengkel.
6. Printer pada Android dan Windows; Mac menyusul di tahap Mac.
7. Uji parity uang, stok, nomor nota, retur, dan laporan dengan versi Python.
8. Fitur lanjutan—follow-up, supplier, karyawan, komisi—setelah inti stabil.
9. Premium lokal: langganan bulanan, batas perangkat per paket, gating fitur,
   kuota WA, dan backup otomatis.
10. Sync API dan multi-device premium (sesuai batas paket), owner/karyawan app:
    **ditunda**.

## Tahapan

1. **Fondasi Flutter:** struktur proyek, SQLite, model data, uang decimal,
   shell modular, pengelola paket resource, dan kerangka tes lintas platform.
2. **Modular delivery:** manifest peran, Play Asset Delivery di Android, paket
   resource bertanda tangan di Windows, unduhan aset per peran, cache paket,
   dan ukur ukuran base. Tidak ada unduhan kode yang dieksekusi.
3. **Inti kasir:** pelanggan, unit, jasa, sparepart, pembayaran, nota, struk.
4. **Stok dan laporan:** pergerakan stok, ringkasan, laporan, retur, void,
   garansi.
5. **Backup dan restore:** backup lokal, restore, dan rollback pengujian.
6. **Android:** PIN, printer, folder backup, WorkManager, AAB lewat Play.
7. **Windows EXE:** printer, file backup, installer, dan paket resource.
8. **Mac:** `.app`/`.dmg`, printer, signing, notarization.
9. **Premium lokal:** langganan bulanan, batas perangkat per paket, gating
   fitur, kuota WA, dan backup otomatis. Sync API dan multi-device premium
   (sesuai batas paket), owner/karyawan app ditunda.
10. **Uji akhir:** matriks Android/Windows/Mac, offline, backup/restore, dan
   parity.

## Backup dan keamanan data

- Belum ada konsumen; data dummy/pengembangan boleh direset. Backup tetap
  dibuat sebelum menghapus atau mengubah data uji secara besar.
- Backup lokal dan restore harus aman dan dapat diuji tanpa API.
- PIN disimpan di penyimpanan aman platform; token premium tidak pernah masuk
  database biasa.
- VPS tidak menyimpan data bengkel; API hanya relay pertukaran data antar
  perangkat.

## Risiko utama

- Rewrite besar; parity uang/stok harus diuji terhadap versi Python.
- Printer dan file picker berbeda di tiap platform; adapter tidak bisa
  disamakan mentah-mentah.
- macOS membutuhkan mesin Mac, Xcode, signing, dan notarization.
- Multi-device premium rawan konflik jika beberapa perangkat menulis transaksi
  saat offline; aturan konflik harus selesai sebelum fitur itu nanti dirilis.
- Batas perangkat per paket dapat diakali dengan menyalin database/token;
  perangkat harus terdaftar dan token terikat, dengan penegakan terakhir saat
  online.
- Hitung mundur lisensi offline bergantung pada jam perangkat; jam mundur tidak
  boleh memperpanjang masa aktif dan harus dikoreksi saat online.
- Data fitur terkunci sengaja tetap dibaca/diekspor; akses tulis dan aksi
  premium tetap harus diblokir.
- APK/EXE/Mac akan lebih kecil dari versi Python, tetapi bukan “tanpa kode”;
  ukuran tetap bergantung pada dependensi dan aset.
- Base shell tetap memuat Flutter engine dan seluruh logika fitur; “hanya
  launcher” berarti paket resource peran tidak ikut, bukan ukuran nol. Ukuran
  base wajib diukur sebelum target rilis ditetapkan.
- Windows tidak punya padanan Play Asset Delivery; paket resource bertanda
  tangan tidak menghapus logika dari shell, jadi EXE tidak sekecil base APK.
- Play Asset Delivery hanya berjalan untuk distribusi lewat Play. APK sideload
  memakai APK penuh/split dan tidak mendapat unduhan aset on-demand.
- iOS (App Store) melarang unduhan kode yang dieksekusi. Paket peran harus tetap
  resource/layout/aset, memakai unduhan aset/On-Demand Resources, dan tidak
  boleh menambah fitur yang tidak ada di shell (App Store 2.5.2).
- Login pertama peran membutuhkan internet; jika offline, pengguna belum bisa
  membuka fitur peran tersebut sampai paket resource terpasang.
- Versi paket resource dan shell bisa berbeda; shell wajib menolak paket di
  bawah versi minimum dan menyediakan rollback ke paket bawaan.
- Paket resource yang gagal diunduh atau korup harus bisa diulang tanpa merusak
  data lokal.

## Non-goals tahap ini

- iOS.
- Web sebagai target aplikasi; web 2.7.0 hanya kanal uji fitur sebelum port
  Flutter.
- Modul WebView yang mengeksekusi kode dari CDN; paket peran memakai Play Asset
  Delivery (Android), unduhan aset/ODR (iOS nanti), dan paket resource bertanda
  tangan (Windows).
- Unduhan kode yang dieksekusi di luar toko aplikasi, Play Feature Delivery,
  atau self-update.
- Multi-device pada tahap ini; multi-device premium (sesuai batas paket)
  menyusul bersama relay.
- API/VPS sebagai syarat transaksi.
- Mempertahankan Python/Chaquopy di paket baru. Aplikasi Python lama tetap
  disimpan sebagai arsip, bukan bagian paket baru.
