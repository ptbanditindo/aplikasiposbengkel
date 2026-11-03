# Rencana Pengembangan Tahap Final — PusatkuPOS

Status: **final** — 2026-11-03. Aplikasi Flutter belum diimplementasikan.
**Fokus implementasi saat ini hanya web**; prototipe web multi-toko dan premium
Fase 3–7 sudah dibangun dan lulus uji otomatis, tetapi APK/Android dan paket
platform lain belum dikerjakan sampai kode web stabil dan pilot lulus.

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

- **Fokus implementasi:** web lebih dulu. APK/Android dan paket platform lain
  belum dikerjakan sampai kode web stabil dan pilot lulus.
- **Rencana hanya memuat pekerjaan yang belum ada kodenya.** Item yang sudah
  dibuat dipindahkan ke bagian **Status dan riwayat** di
  [`RENCANA_MULTI_TOKO_PREMIUM.md`](RENCANA_MULTI_TOKO_PREMIUM.md).
- **Sumber kebenaran produk:** aturan tier, kuota, akun, izin, backup, lisensi,
  perangkat, relay, kunci, privasi, harga, distribusi, serta model offline-first
  dan Postgres ditetapkan sebagai `K-01`–`K-24` di
  `RENCANA_MULTI_TOKO_PREMIUM.md`. Dokumen ini tidak mengulang aturan tersebut;
  bagian lain hanya merujuk ID-nya.
- **Teknologi:** Flutter + Dart untuk UI dan logika bisnis.
- **Database lokal:** SQLite melalui drift/FFI; satu sumber kebenaran lokal di
  semua platform; `database_id` mengikuti K-05.
- **Distribusi (tahap Flutter, setelah web stabil):** rilis pertama memakai satu
  AAB Android, satu installer Windows, dan satu aplikasi macOS. Ukuran diukur
  lebih dulu; paket aset statis opsional hanya jika pengukuran membuktikan perlu
  (K-17). Tidak ada paket layout, server-driven UI, dex/JAR/so, atau self-update.
- **Paket platform (tahap Flutter):** AAB Android lewat Play (APK sideload
  penuh/split), installer EXE Windows, `.app`/`.dmg` macOS.
- **Tanpa Python di perangkat:** backend Python tidak ikut ke paket aplikasi.
  Server relay tetap layanan Python/FastAPI terpisah dengan PostgreSQL (K-24).
  Aplikasi lama diarsipkan setelah Flutter stabil (K-19); data lamanya tidak
  wajib dimigrasikan.
- **Offline-first:** setiap perangkat menyimpan SQLite lokal dan memproses
  transaksi saat offline; server hanya kotak pos terenkripsi (K-23). Perangkat
  owner adalah salinan lengkap dan sumber snapshot untuk perangkat baru.
- **Data awal:** belum ada konsumen. Data dummy/pengembangan boleh dimulai ulang;
  migrasi data lama bukan syarat rilis.
- **Skema database:** dirancang baru; tidak ada kewajiban kompatibilitas dengan
  database 2.x.
- **Aplikasi utama dan owner:** mengikuti K-02/K-21. Aplikasi utama memuat core
  logic; aplikasi owner adalah thin client premium tanpa database transaksi dan
  hanya memakai cache ringkasan bertanda tangan.
- **Tier:** mengikuti K-03/K-21. Hanya ada **Gratis** dan **Premium**; tidak ada
  premium v1/v2. Gratis seumur hidup dan lokal dengan Follow Up 20 kredit; baik
  tanpa akun maupun login Google, pengguna gratis berperan sebagai **owner** dan
  memakai kasir, ringkasan, stok, serta laporan. Akun karyawan dan multi-toko
  baru terbuka saat berlangganan. Premium satu tier dengan seluruh fitur
  berbayar; fitur premium boleh dirilis bertahap di balik flag, tetapi tetap
  dijual sebagai satu tier.
- **Mode karyawan:** mengikuti K-07/K-12. Peran dasar + izin tambahan; nota dan
  pembayaran boleh dibuat offline di semua perangkat yang ditugaskan, sedangkan
  void/retur/piutang hanya oleh pengguna dengan akses kasir.
- **Apple:** target tahap ini macOS. iOS bukan target tahap ini.
- **Rencana terpisah:** multi-toko, login, header toko, premium, backup,
  pengujian, dan status ada di `RENCANA_MULTI_TOKO_PREMIUM.md`.
  Web 2.7.0 sudah membuktikan header/registry/ganti toko/gating dan memuat
  prototipe akun/lisensi/perangkat/relay/arsip sebagai acuan migrasi (K-01).
  Sync dan kripto Dart tetap ditulis ulang setelah spesifikasi protokol + test
  vector; prototipe web tidak menggantikan uji Play Billing, secure storage,
  notifikasi, kunci perangkat, atau relay lintas perangkat nyata.

## Arsitektur

- **UI dan logika bisnis** berada di Dart dan dipakai bersama ketiga platform.
- **Satu aplikasi utama** memuat seluruh layar, logika, izin, dan aksi. Tidak ada
  paket layout yang diunduh; pembatasan peran dilakukan di shell dan lapisan
  data (K-07, K-17).
- **Premium** berjalan penuh di perangkat owner tanpa relay; semua
  toko dan shift karyawan memakai perangkat itu. Perangkat owner tambahan,
  perangkat karyawan, dan relay adalah bagian premium yang sama (K-12, K-13,
  K-21).
- **Lapisan data** memakai repository/service di atas SQLite; semua perhitungan
  uang memakai decimal dan pembulatan yang sama dengan versi Python.
- **Platform adapter** menangani printer, pemilih folder, file backup, PIN,
  notifikasi lokal, autostart, update, dan integrasi sistem. Android dapat
  memakai kembali sebagian kode Kotlin lama lewat platform channel; Windows dan
  Mac memakai adapter masing-masing.
- **Sinkronisasi premium** memakai outbox lokal, idempotency, retry, dan HLC
  (K-14). Delta ditandatangani per perangkat dan diverifikasi penerima (K-15).
  Relay hanya menyimpan amplop terenkripsi sementara (K-13).
- **Manajemen kunci premium:** kunci owner, kunci data per toko, wrapped key per
  perangkat, re-key saat pencabutan, dan pemulihan kunci owner mengikuti K-22.
- **Lisensi premium** memakai token bertanda tangan dengan masa tenggang offline
  tanpa batas selama perangkat terdaftar dan belum dicabut; jam perangkat tidak
  dipakai untuk mengunci fitur, dan kegagalan API tidak mengunci transaksi
  (K-11). Perangkat owner dan karyawan didaftarkan terpisah (K-12).
- **Aplikasi owner** adalah thin client premium tanpa database transaksi; hanya
  cache ringkasan/laporan bertanda tangan (K-02, K-21).
- **Backup lokal** tetap menjadi cadangan utama; sinkronisasi bukan pengganti
  backup (K-10).

## Platform

Target akhir; paket platform belum dikerjakan selama fokus web.

| Platform | Paket | Catatan |
| --- | --- | --- |
| Android | AAB (Play) | satu AAB berisi seluruh logika; ukuran diukur; paket aset statis opsional hanya jika perlu (K-17); minSdk 26; printer Bluetooth/USB/Wi-Fi; backup folder/SAF; WorkManager pengganti |
| Windows | Installer EXE | satu installer; paket aset opsional bertanda tangan; printer USB/jaringan/cetak sistem; file backup; autostart opsional |
| iOS (masa depan) | IPA (App Store) | aset/On-Demand Resources tanpa executable code; tidak menambah fitur; App Store 2.5.2 (K-17) |
| Mac | `.app` dan `.dmg` | universal Intel/Apple Silicon; printer jaringan/sistem; signing dan notarization |

## Aturan offline-first

- Tidak ada panggilan API di jalur simpan nota, stok, pembayaran, atau struk.
- Semua data inti tersedia setelah aplikasi dibuka tanpa internet.
- Internet dibutuhkan untuk login pemilik/aktivasi premium, login pertama
  karyawan di perangkat, manajemen akun, dan sinkronisasi; **bukan** untuk kasir
  atau fitur inti (K-16). Login gratis bersifat opsional.
- Gratis tanpa login **tidak memanggil API sama sekali**; kuota WA hanya lokal
  (K-04). Gratis yang memilih login hanya memanggil API autentikasi, tanpa ID
  owner dan tanpa registrasi perangkat (K-07/K-12). Paket aset statis opsional
  tidak boleh mengunci fitur inti atau mewajibkan login online (K-17).
- Premium boleh berjalan lokal di satu perangkat owner tanpa relay; batas
  perangkat owner dan perangkat karyawan mengikuti K-12/K-21.
- Langganan berakhir tidak mengunci kasir atau menghapus data; perilaku fitur
  terkunci mengikuti K-03/K-11.
- Outbox pending, notifikasi, HLC, dan konflik hanya ada di premium (K-14/K-16).
  TTL antrean relay, snapshot, dan replay outbox mengikuti K-13/K-22.
- Banyak akun karyawan (mis. 100) di premium mengikuti K-12/K-14; akun
  dipakai bergiliran, perangkat karyawan tidak dihitung dalam batas owner.
- Backup lokal dan restore mengikuti K-10; backup menyertakan outbox pending dan
  tetap berfungsi tanpa akun/internet.
- Jam transaksi dipakai untuk tampilan; urutan perubahan memakai nomor perangkat
  dan HLC (K-14).

## Ruang lingkup MVP

Fondasi—struktur proyek, SQLite, model data, shell modular, kerangka tes, dan
pengukuran ukuran aplikasi—dikerjakan lebih dulu. Distribusi memakai satu paket
per platform; paket aset statis opsional hanya jika pengukuran membuktikan perlu
(K-17).

1. Kasir: pelanggan, unit dengan empat kategori, jasa, sparepart, pembayaran,
   nota, dan struk.
2. Stok: masuk/keluar, scanner HID, minimum stok, ringkasan, dan peringatan.
3. Riwayat servis, retur, void, garansi, dan laporan harian.
4. Backup lokal, restore, dan format database/Excel/CSV. Backup/restore adalah
   P0, bukan fitur opsional.
5. PIN/keamanan lokal dan pengaturan bengkel.
6. Printer pada Android dan Windows; Mac menyusul di tahap Mac.
7. Uji parity uang, stok, nomor nota, retur, dan laporan dengan versi Python.
8. Fitur lanjutan—follow-up, supplier, karyawan, komisi—setelah inti stabil.
9. **Premium tahap awal:** langganan, satu perangkat owner, multi-toko, karyawan shift
   di komputer toko, gating fitur, Follow up/WA, dan backup sesuai K-03/K-10/K-11/K-21.
10. **Premium sync dan perangkat:** multi-device, perangkat karyawan, relay,
    kunci, dan aplikasi owner; aturan mengikuti K-12–K-16 dan K-21–K-22. Fitur
    ini tetap bagian dari tier premium yang sama, bukan tier kedua. LAN bukan
    bagian rilis awal.

## Tahapan

1. **Web 2.7.0 + pilot:** header, registry, ganti toko, gating lokal, dan
   prototipe akun/lisensi/relay sudah dibangun; lakukan uji UI web manual lalu
   jalankan pilot 1–3 bengkel nyata selama 2–4 minggu. Port Dart, rilis premium,
   dan APK/Android belum dimulai sebelum pilot lulus dan web stabil (K-01).
2. **Fondasi Flutter:** struktur proyek, SQLite, model data, uang decimal, shell
   modular, dan kerangka tes lintas platform.
3. **Spesifikasi protokol:** HLC, tanda tangan, wrapped key, snapshot, replay
   outbox, dan test vector. Prototipe Python di web sudah ada sebagai acuan;
   test vector Dart tetap wajib sebelum port.
4. **Port Flutter dan ukuran:** port layar inti; ukur ukuran aplikasi dan
   putuskan paket aset statis (K-17). Tidak ada paket layout atau unduhan kode.
5. **Inti kasir:** pelanggan, unit empat kategori, jasa, sparepart, pembayaran,
   nota, dan struk.
6. **Stok dan laporan:** scanner HID, pergerakan stok, ringkasan, laporan, retur,
   void, dan garansi.
7. **Backup dan restore (P0):** backup lokal, restore staging, rollback, dan
   checksum.
8. **Android/APK (setelah web dan port inti stabil):** PIN, printer, folder
   backup, WorkManager, AAB lewat Play.
9. **Windows EXE:** printer, file backup, installer, dan paket aset opsional.
10. **Mac:** `.app`/`.dmg`, printer, signing, notarization.
11. **Premium tahap awal:** langganan, satu perangkat owner, multi-toko, karyawan shift
    di komputer toko, gating, Follow up/WA, dan backup sesuai K-03/K-10/K-11/K-21.
12. **Premium sync dan perangkat:** multi-device, perangkat karyawan, relay,
    kunci, dan aplikasi owner sesuai K-12–K-16/K-21–K-22. LAN bukan bagian
    rilis awal.
13. **Uji akhir:** matriks Android/Windows/Mac, offline, backup/restore, dan
    parity.

## Backup dan keamanan data

- Belum ada konsumen; data dummy/pengembangan boleh direset. Backup tetap
  dibuat sebelum menghapus atau mengubah data uji secara besar.
- Backup lokal dan restore harus aman dan dapat diuji tanpa API. Aturan backup
  mengikuti K-10; backup/restore adalah P0.
- PIN disimpan di penyimpanan aman platform; token premium tidak pernah masuk
  database biasa.
- Kunci privat perangkat dan kunci owner hanya di secure storage. Server hanya
  menyimpan kunci publik, wrapped store key, dan amplop terenkripsi sementara
  (K-13, K-22).
- Server tidak menyimpan data bengkel yang dapat dibaca dan tidak menyimpan
  kuota gratis; hanya metadata, kunci publik/wrapped key, dan amplop dengan TTL
  (K-04, K-13).
- Cadangan kunci owner terenkripsi dan kode pemulihan terpisah dari backup data;
  jika keduanya hilang, izin baru tidak dapat diterbitkan dan dukungan tidak
  dapat memulihkan (K-22).
- Data akun (termasuk identitas Google pengguna gratis yang memilih login),
  perangkat, lisensi, kunci, dan amplop adalah data pribadi. Privacy notice, hak
  akses/ekspor/koreksi/hapus, retensi, dan prosedur insiden mengikuti K-18 dan
  UU PDP.

## Risiko utama

- Rewrite besar; parity uang/stok harus diuji terhadap versi Python.
- Printer dan file picker berbeda di tiap platform; adapter tidak bisa
  disamakan mentah-mentah.
- macOS membutuhkan mesin Mac, Xcode, signing, dan notarization.
- Multi-device premium rawan konflik jika beberapa perangkat menulis transaksi
  saat offline; aturan konflik harus selesai sebelum fitur itu dirilis (K-14).
- Batas perangkat dapat diakali dengan menyalin database/token; perangkat harus
  terdaftar, token terikat, dan penegakan offline memakai daftar terakhir
  (K-12).
- Perangkat karyawan tidak dihitung dalam batas owner dapat disalahgunakan;
  mitigasi: perangkat karyawan mengikuti izin akun, void/retur/piutang hanya oleh
  akses kasir, akun aktif, perangkat terdaftar dan dapat dicabut (K-12).
- Halaman harga dapat disalahpahami sebagai multi-device tanpa batas; halaman
  wajib menyebut batas perangkat owner paket dan bahwa perangkat karyawan tidak
  dihitung (K-11, K-21).
- Pemilik yang kehilangan perangkat harus dapat mencabut slot lewat login Google
  di perangkat baru; tanpa alur ini slot premium macet dan pengguna menyalahkan
  lisensi (K-12). Batas satu pelepasan per 72 jam harus dijelaskan.
- Kunci owner yang hilang bersama kode pemulihan membuat izin/pencabutan baru
  tidak dapat diterbitkan; peringatan wajib saat pembuatan kode (K-22).
- Re-key setelah pencabutan bergantung pada perangkat owner online; delta sensitif harus
  ditahan sampai selesai, dan data yang sudah diunduh perangkat dicabut tidak
  dapat dihapus jarak jauh (K-22).
- Snapshot tanpa replay outbox dapat menghilangkan delta lokal; urutan replay,
  deduplikasi, dan konflik wajib diuji (K-22).
- Web loopback-only tidak membuktikan secure storage, Play Billing, notifikasi,
  kunci, atau relay; jangan menganggap web sebagai bukti kesiapan premium (K-01).
- Pilot 1–3 bengkel dapat menunjukkan fitur premium tidak dibutuhkan; hasilnya
  harus memotong lingkup, bukan dipaksakan.
- Estimasi premium di `RENCANA_MULTI_TOKO_PREMIUM.md` masih bisa meleset; buffer
  dan uji perangkat nyata ditambahkan sebelum tanggal rilis dijanjikan.
- Delta dari klien yang dimodifikasi dapat dipalsukan jika tidak ditandatangani;
  tanda tangan per perangkat dan verifikasi penerima wajib (K-15).
- Antrean relay terenkripsi menambah biaya dan memiliki TTL; penerima yang
  offline sangat lama harus memakai snapshot perangkat owner atau backup (K-13).
- Jika semua perangkat owner hilang, pemulihan hanya lewat backup lokal; cache aplikasi owner
  bukan cadangan (K-02).
- Hitung mundur lisensi offline bergantung pada jam perangkat; jam mundur tidak
  boleh memperpanjang masa aktif dan harus dikoreksi saat online (K-11).
- Data fitur terkunci sengaja tetap dibaca/diekspor; akses tulis dan aksi
  premium tetap harus diblokir (K-03).
- Ukuran aplikasi Flutter bisa lebih besar dari perkiraan; ukur dulu dan jangan
  menjanjikan angka (K-17).
- Paket aset opsional dapat disalahartikan sebagai izin atau menambah fitur;
  paket hanya aset statis dan shell tetap memeriksa izin (K-17).
- iOS (App Store) melarang unduhan kode yang dieksekusi; hanya aset/ODR tanpa
  executable code (K-17).
- Metadata akun, perangkat, dan amplop relay adalah data pribadi; retensi,
  penghapusan, dan insiden wajib ditangani sesuai UU PDP (K-18).
- Harga awal dapat tipis setelah komisi Play Billing, relay, dan dukungan; unit
  economics wajib dihitung sebelum rilis (K-20).

## Non-goals tahap ini

- iOS.
- Web sebagai target aplikasi; web 2.7.0 hanya kanal uji fitur sebelum port
  Flutter.
- Paket layout per peran, server-driven UI, unduhan kode yang dieksekusi,
  Play Feature Delivery, atau self-update. Paket aset statis opsional hanya jika
  pengukuran membuktikan perlu (K-17).
- Paket aset yang menambah fitur, logika, atau izin.
- Penyimpanan data bengkel yang dapat dibaca di VPS/cloud; hanya metadata dan
  amplop terenkripsi sementara dengan TTL (K-13).
- Backup ke Google Drive.
- LAN lokal; jika dibutuhkan, menjadi keputusan dan pekerjaan terpisah
  (K-21).
- Sync, perangkat karyawan, dan aplikasi owner tidak dijual terpisah; semuanya
  bagian tier premium yang sama dan dirilis bertahap di balik flag (K-12, K-21).
- Sinkronisasi kuota gratis ke server; kuota hanya lokal (K-04).
- API/VPS sebagai syarat transaksi.
- Mempertahankan Python/Chaquopy di paket baru. Aplikasi Python lama tetap
  disimpan sebagai arsip, bukan bagian paket baru (K-19).
