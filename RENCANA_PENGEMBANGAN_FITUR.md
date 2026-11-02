# Rencana Pengembangan Fitur

Status: **ide/rencana awal — belum diimplementasikan**. 2026-11-03.

Mencakup pemantapan 2.7.0 dan fitur scanner barcode/QR. Bukan fitur premium dan
bukan rewrite Flutter/PusatkuPOS. Belum ada konsumen; data dummy/pengembangan
boleh dimulai ulang dan migrasi data lama bukan syarat.

Sasaran: **BengkelPOS Radiator 2.7.0** yang sekarang berjalan (FastAPI, frontend
web, dan APK Chaquopy). Bukan rewrite Flutter/PusatkuPOS dan bukan fitur
premium.

## Tujuan

- Memantapkan rilis yang ada sebelum pindah ke aplikasi Flutter.
- Memantapkan fitur yang ada sebelum aplikasi menjadi produk final.
- Memastikan kasir, stok, nota, pembayaran, retur, laporan, dan backup tetap
  berjalan tanpa regresi.
- Fokus pada kebenaran data, keamanan, backup, keandalan, perangkat, dan rilis.
- Menyiapkan rilis pemantapan **2.7.1 (versionCode 20)** bila ada perubahan
  kode.
- Menyiapkan pemetaan domain untuk **PusatkuPOS** yang mencakup 10 jenis
  bengkel di bawah.

## Cakupan bengkel

1. **Radiator & Pendingin** — servis, kuras/kored, tambal, ganti core, water
   pump, dan sistem pendingin mesin.
2. **Mesin (Engine/Overhaul)** — turun mesin, piston, skir klep, korter
   silinder, dan komponen pembakaran.
3. **Transmisi & Kaki-kaki** — kemudi, suspensi, roda, rem, transmisi manual,
   matic, dan CVT.
4. **Kelistrikan & AC** — kelistrikan bodi, alternator, aki, ECU/sensor,
   pengapian, serta AC mobil/motor.
5. **Spooring & Balancing** — sudut roda, keseimbangan ban, dan kestabilan
   laju.
6. **Cat, Ketok Magic & Body Repair** — bodi penyok, las sasis, dempul, dan
   cat ulang.
7. **Kaca Film & Aksesoris** — kaca film, kaca retak, dan aksesoris interior
   atau eksterior.
8. **Bubut (Machining)** — bubut piringan rem, facing blok/head, bushing, dan
   komponen logam presisi.
9. **Knalpot (Exhaust)** — header, pipa, resonator, dan muffler.
10. **Injeksi & ECU Tuning (Remap)** — injector ultrasonik, diagnostic
    scanner, dan kalibrasi ECU.

Pemilik bengkel tidak harus memakai semua jenis. Pada PusatkuPOS, jenis
bengkel dan keahlian dipilih saat onboarding dan dapat diubah di Pengaturan.

## Posisi terhadap aplikasi sekarang

- Aplikasi **2.7.0** masih berlabel dan berfokus radiator.
- Pemantapan **2.7.1** tidak membangun dukungan fungsional penuh untuk 10
  jenis bengkel; fokusnya stabilitas rilis yang ada.
- Dukungan penuh 10 jenis bengkel adalah lingkup **PusatkuPOS** (Flutter).
- Pemantapan sekarang menyiapkan pemetaan istilah, unit, jasa, stok, dan struk
  agar generalisasi nanti tidak terikat skema radiator lama.
- Bila 10 jenis harus didukung di aplikasi 2.7.0, itu perubahan fitur besar
  dan harus disetujui sebagai perluasan scope, bukan pemantapan.

## Baseline

- Commit awal: `88236dd`.
- Skema database: 38.
- Tes: 372 pytest lulus di `.venv` dan `.venv-apk`.
- APK terakhir: 2.7.0 (19), debug-signed, belum diuji di perangkat fisik.
- Backup: database, Excel, CSV; otomatis, manual, dan Telegram.
- TODO/FIXME di kode: tidak ditemukan. Ada 17 `except Exception` yang perlu
  ditinjau, bukan otomatis dihapus.
- Dokumen lama sudah dibersihkan; README menjadi acuan teks yang tersisa.

## Aturan kerja

- Backup database sebelum migrasi atau perubahan berisiko.
- Tidak menghapus data pengguna atau database produksi.
- Perubahan kecil dan terukur; tidak refactor besar.
- Tes terarah dulu, lalu seluruh suite dua stack.
- Verifikasi localhost sebelum build APK.
- Setiap perubahan kode dilaporkan: file, alasan, tes, dan risiko.
- Tidak mengubah alur kasir yang sudah berjalan tanpa alasan yang terbukti.

## Lingkup pemantapan

### 1. Kebenaran data dan uang

- Audit alur nota, pembayaran, piutang, retur, void, garansi, komisi, dan gaji.
- Pastikan semua nominal memakai Decimal dan pembulatan yang konsisten di
  backend; JavaScript hanya menampilkan.
- Uji stok minus, retur sebagian, tukar barang, pembayaran bertahap, dan nota
  void.
- Uji nomor nota berurutan dan idempotency request.
- Rekonsiliasi stok: jumlah awal, masuk, keluar, retur, dan sisa.
- Rekonsiliasi laporan harian/periode dengan data nota.
- Uji migrasi skema pada salinan database dummy, bukan database aktif.
- Uji tanggal, jam, dan batas periode laporan.

### 2. Backup, restore, dan retensi

- Uji backup otomatis/manual database, Excel, dan CSV.
- Uji pemakaian ulang snapshot dan pergantian format.
- Uji retensi, ruang disk kurang, file besar, dan batas Telegram 50 MB.
- Uji restore file valid, file rusak, file kosong, dan skema lama.
- Pastikan salinan pengaman sebelum restore dan rollback saat restore gagal.
- Uji backup Telegram dengan mock; jangan memakai token asli.
- Uji penyalinan backup Android ke folder pilihan dan Unduhan.
- Pastikan PIN/token tidak bocor ke file backup atau ekspor.

### 3. Keamanan

- Uji PIN, sesi, lockout, dan perilaku setelah restore.
- Uji pembatasan loopback, Host, Origin, dan dokumentasi API yang dimatikan.
- Uji token instalasi APK dan penolakan kredensial placeholder.
- Tinjau 17 `except Exception` agar kegagalan tidak tertelan tanpa log.
- Periksa dependency dan file konfigurasi; pastikan tidak ada token/rahasia
  baru di repo.
- Jika token Telegram pernah terekspos, pastikan sudah dirotasi.
- Uji audit event untuk aksi penting: void, retur, restore, perubahan stok.

### 4. Keandalan dan konkurensi

- Uji dua transaksi bersamaan: nomor nota, stok, pembayaran.
- Uji penjadwal backup, maintenance gate, dan restore saat backup berjalan.
- Uji database terkunci, disk penuh, jaringan mati, dan API Telegram gagal.
- Uji startup dengan migrasi gagal dan pemulihan database.
- Uji WorkManager setelah reboot, Doze, dan aplikasi ditutup.
- Uji printer mati, kertas habis, koneksi putus, dan karakter struk.
- Pastikan pesan error memberi langkah berikutnya, bukan hanya “gagal”.

### 5. Performa

- Siapkan dataset besar: pelanggan, unit, nota, stok, dan audit event.
- Ukur laporan harian, periode, stok, dan rekap keuangan.
- Periksa indeks query laporan dan daftar.
- Uji beban transaksi paralel yang sudah ada.
- Ukur waktu backup/restore dan ukuran file.
- Periksa startup web dan APK, memori, serta ukuran database.
- Hindari perubahan performa yang tidak diukur.

### 6. UI, perangkat, dan cetak

- Uji browser desktop Chrome/Edge pada lebar 1440, 1024, 810, dan 360.
- Uji tema terang/gelap dan lima tema warna.
- Uji semua popup, empty state, validasi, dan toast.
- Uji keyboard, scroll, modal panjang, dan tabel di layar sempit.
- Uji APK di perangkat Android nyata: PIN, kasir, struk, backup, restore.
- Uji printer Bluetooth, Wi-Fi/LAN, USB OTG, cetak sistem, dan 58/80 mm.
- Uji backup folder SAF dan Unduhan.
- Catat perangkat/versi Android yang benar-benar diuji.

### 7. Rilis dan dokumentasi

- Perbarui versi ke 2.7.1 (20) bila ada perubahan kode.
- Perbarui README untuk perilaku yang berubah.
- Catat chagelog singkat dan daftar perbaikan.
- Build APK debug, catat ukuran dan SHA-256.
- Uji update dari APK 2.7.0 ke 2.7.1 tanpa kehilangan data.
- Siapkan prosedur rollback dan restore.
- Bersihkan artefak uji/dummy hanya setelah dikonfirmasi; jangan hapus data
  pengguna.
- Push ke GitHub hanya setelah tes dan verifikasi selesai.

### 8. Kesiapan domain 10 bengkel

- Inventaris label, istilah, dan field yang masih hardcoded radiator.
- Petakan kategori unit: **mobil lengkap, motor lengkap, part motor, part
  mobil**. Tidak ada master kategori per item; part memakai kolom barang bebas
  (misalnya radiator, ban, shockbreaker, aki, mesin copotan, potongan unit).
- Bedakan unit pelanggan yang diservis dari stok barang/copotan yang dijual.
- Petakan data kendaraan lengkap, kolom barang part, kategori jasa, kategori
  stok, dan label struk untuk tiap jenis bengkel.
- Pastikan data lama tidak perlu dipertahankan karena belum ada konsumen; data
  dummy boleh direset.
- Catat fitur yang khusus radiator agar tidak diasumsikan berlaku untuk semua
  bengkel.
- Siapkan daftar istilah UI yang perlu dinetralkan di PusatkuPOS.
- Jangan membangun onboarding/profil 10 bengkel di rilis 2.7.1 kecuali
  disetujui sebagai perluasan scope.

### 9. Scanner barcode/QR

- Dukungan scanner USB/Bluetooth yang bekerja sebagai keyboard (HID) di web
  dan APK. Input ditangkap sebagai kode barang tanpa mengganggu kolom lain.
- Android dapat memakai kamera untuk scan QR/barcode; butuh izin kamera dan
  jembatan native.
- Penggunaan: cari sparepart, tambah barang ke kasir, **tambah stok**, stok
  opname, cari nota, dan verifikasi label.
- **Tambah stok via scanner:** scan barcode/QR untuk mencari barang, lalu isi
  jumlah masuk. Jika kode belum dikenal, buka form barang baru dengan kode
  terisi otomatis.
- Stok opname memakai scanner untuk mencari barang dan menyesuaikan jumlah;
  scan berulang harus mencegah duplikasi atau meminta konfirmasi.
- Satu barang dapat memiliki beberapa barcode/alias, misalnya barcode supplier
  dan barcode toko. Barcode harus unik dan tidak boleh menunjuk dua barang
  berbeda.
- Pencarian memakai SQLite lokal; scanner tetap berfungsi tanpa internet.
- Kode tidak dikenal menampilkan pilihan cari manual atau buat barang baru.
- Input divalidasi panjang/karakternya dan tidak dijalankan sebagai perintah.
- Sediakan mode scan, bunyi/notifikasi singkat, dan fallback pencarian manual.
- Barcode/QR pada label dan nota mengikuti kemampuan printer yang tersedia.
- Prioritas: scanner HID lebih dulu; kamera Android menyusul bila perangkat
  uji tersedia.

### 10. Empat kategori unit

- Kategori unit hanya empat: **mobil lengkap, motor lengkap, part motor, part
  mobil**.
- Tidak perlu master kategori per item. Untuk part, kasir mengisi kolom bebas
  “barang yang dibawa”, misalnya radiator, ban, shockbreaker, aki, mesin
  copotan, atau potongan unit.
- Unit lengkap memakai data kendaraan: nopol/label, merek/model, tahun, dan
  catatan.
- Part memakai nama barang, merek/ukuran, nomor seri opsional, kondisi,
  kendaraan asal opsional, catatan, dan foto bila diperlukan.
- Laporan dapat mengelompokkan part dari isi kolom barang tanpa master
  kategori per item.
- Barang pelanggan yang diservis bukan stok. Part yang dipakai diambil dari
  stok; unit copotan yang dijual dapat menjadi stok dengan kondisi dan asal.
- Form unit, kasir, struk, pencarian, dan laporan menyesuaikan empat kategori
  ini.
- Belum ada konsumen dan data konsumen yang perlu dimigrasikan; data dummy
  boleh direset.

### 11. Login tanpa akun, Google, dan logout/sign out

- **Tanpa login** adalah jalur default: lokal, satu perangkat, tanpa internet,
  dan memakai PIN perangkat. Data disimpan di SQLite lokal pada folder aplikasi
  perangkat; tidak ada upload ke API.
- **Login Google** bersifat opsional. Google dipakai untuk identitas dan akun;
  data tetap disimpan lokal lebih dulu.
- Tanpa premium, login Google tidak mengunggah data bengkel. Dengan premium,
  salinan disinkronkan ke API/cloud tenant; database lokal tetap sumber utama.
- Login pertama membutuhkan internet. Setelah itu data lokal tetap dapat dipakai
  saat offline; permintaan login ulang hanya muncul saat fitur akun/sync dipakai.
- **Logout/sign out** tersedia di menu akun atau Pengaturan. Logout meminta
  konfirmasi, menghapus sesi akun dan token perangkat, lalu kembali ke pilihan
  akses.
- Logout **tidak menghapus** database, nota, stok, backup, atau pengaturan.
  Penghapusan data harus menjadi aksi terpisah dengan konfirmasi.
- Setelah logout, pengguna dapat memakai mode tanpa login atau masuk dengan
  akun Google lain; penautan data ke akun berbeda harus dikonfirmasi.
- PIN perangkat tetap menjadi pengunci lokal dan tidak otomatis terhapus oleh
  logout Google.
- Logout menghentikan sinkronisasi di perangkat itu sampai login kembali.
- Token Google disimpan di penyimpanan aman platform (Keystore/Keychain/DPAPI),
  bukan di database biasa. Aplikasi tidak memakai Google Drive untuk data
  bengkel kecuali fitur itu ditambahkan eksplisit.
- Jika aplikasi dihapus, data lokal hilang kecuali sudah dibackup; data cloud
  premium mengikuti kebijakan retensi tenant.

### 12. Tombol ganti toko di dalam Menu

- Tombol/dropdown **Ganti toko** ditempatkan **di dalam panel Menu**, di bagian
  paling atas dan tepat di atas item Ringkasan. Bukan tombol terpisah di luar
  panel menu.
- Saat tombol Menu ditekan, Ganti toko tampil sebelum Ringkasan.
- Menampilkan nama toko yang sedang aktif.
- Jika **belum ada toko kedua**, panel hanya menampilkan toko aktif dan tombol
  **Tambahkan toko baru**.
- Jika sudah ada beberapa toko, panel menampilkan daftar:
  **Toko A**, **Toko B**, dan seterusnya, dengan penanda toko aktif, lalu
  tombol **Tambah toko** di bagian bawah.
- Menekan **Tambahkan toko baru/Tambah toko** membuka form nama toko dan alamat
  (serta profil bengkel bila diperlukan). Setelah dibuat, toko masuk ke daftar
  dan dapat langsung dipilih.
- Toko baru memakai database/tenant terpisah; tidak menyalin data toko lain.
- Setiap toko memiliki file SQLite sendiri, misalnya
  `stores/<store_id>/database.db`, dan daftar toko disimpan di registry lokal.
- Nota, stok, pelanggan, karyawan, dan laporan tidak boleh tercampur antar
  toko.
- Hanya pemilik yang boleh menambah toko. Karyawan hanya melihat daftar toko
  yang ditugaskan dan tidak melihat tombol tambah.
- Jika ada beberapa toko, pemilik dapat memilih Toko A, Toko B, atau tambah
  toko. Setelah memilih, aplikasi memuat data toko tersebut dan kembali ke
  Ringkasan.
- Jika ada perubahan yang belum disimpan, minta konfirmasi sebelum berganti.
- Ganti toko harus bekerja offline untuk toko yang datanya tersedia di
  perangkat.
- Di layar sempit, tombol tetap berada di dalam panel Menu, di atas Ringkasan,
  dan tidak menutupi navigasi.
- Fitur ini bergantung pada multi-toko/multi-tenant yang masih ditunda; tombol
  dapat disiapkan sebagai UI, tetapi pemisahan data baru aktif setelah backend
  multi-toko tersedia.

### 13. Judul bengkel dan alamat di header

- Header paling atas memakai dua baris:

  ```text
  Nama bengkel                         [printer]
  Alamat bengkel
  ```

- Baris pertama berisi **nama bengkel**; tombol/ikon printer berada di kanan
  pada baris yang sama.
- Baris kedua selalu **alamat bengkel**, bukan judul halaman. Fungsinya agar
  pengguna langsung tahu toko/bengkel mana yang sedang aktif.
- Nama dan alamat mengikuti toko yang dipilih lewat tombol Ganti toko.
- Jika alamat kosong, tampilkan “Alamat belum diisi” agar ruang tidak kosong.
- Judul halaman seperti “Ringkasan” tetap berada di area konten, bukan di
  header toko.
- Nama panjang dipotong atau dibungkus tanpa menutupi tombol printer; alamat
  mengikuti lebar layar dan aman di area status bar/notch.
- Header tetap tampil offline dan tidak memanggil API.

### 14. Backup semua toko

- Setiap toko punya database SQLite sendiri, tetapi backup manual dan otomatis
  dibuat sebagai **satu arsip semua toko**, bukan satu file per toko.
- Arsip berisi manifest toko (ID, nama, alamat, toko aktif), seluruh database
  toko, dan versi skema. Contoh: `backup_semua_toko_YYYYMMDD.zip`.
- Backup tidak boleh hanya mengambil toko aktif karena restore bisa
  menghasilkan daftar toko yang tidak lengkap.
- Restore satu arsip langsung memunculkan **Toko A, Toko B, Toko C** dan
  seterusnya tanpa upload/impor database satu per satu.
- Restore memvalidasi manifest dan seluruh database. Jika satu bagian gagal,
  seluruh restore dibatalkan dan data lama dikembalikan.
- Toko yang ditambahkan setelah backup terakhir akan ikut pada backup
  berikutnya.
- Backup otomatis, manual, dan Telegram memakai arsip yang sama; Telegram tetap
  tunduk pada batas ukuran file.
- Ekspor Excel/CSV dapat berisi subfolder atau workbook per toko di dalam satu
  ZIP.
- PIN, token, dan rahasia perangkat tetap diredaksi dari arsip.
- Tidak ada upload per toko ke cloud; restore memakai satu arsip lokal atau
  satu file yang dipilih pengguna.

## Tahapan

1. **Pembekuan dan baseline:** backup database, catat versi, jalankan suite
   penuh, siapkan salinan migrasi.
2. **Audit data dan uang:** rekonsiliasi, tes transaksi, retur, stok, laporan.
3. **Backup, restore, keamanan:** uji seluruh format, restore, rahasia, akses.
4. **Keandalan dan perangkat:** konkurensi, printer, APK, jaringan, backup
   native.
5. **Performa dan UI:** dataset besar, query, browser, layar sempit.
6. **Kesiapan domain:** audit istilah radiator, pemetaan unit/jasa/stok/struk,
   catatan gap untuk PusatkuPOS.
7. **Scanner barcode/QR:** input HID, kamera Android, alias barcode, tambah
   stok, stok opname, pencarian stok/nota, dan fallback manual.
8. **Empat kategori unit:** mobil lengkap, motor lengkap, part motor, part
   mobil, dan kolom barang bebas untuk part.
9. **Login dan akun:** tanpa login, Google, logout/sign out, penyimpanan lokal,
   dan perilaku offline.
10. **Ganti toko:** tombol di dalam Menu, pemilihan toko, izin, dan pemisahan
    data; aktif penuh setelah multi-toko tersedia.
11. **Header toko:** nama bengkel + printer, alamat bengkel, dan pembaruan saat
    ganti toko.
12. **Backup semua toko:** satu arsip berisi seluruh database toko dan restore
    langsung memunculkan semua toko.
13. **Rilis 2.7.1:** perbaikan, tes ulang, build APK, dokumentasi, commit.
14. **Serah terima:** laporan file yang disentuh, tes, hash APK, risiko tersisa.

## Matriks uji minimum

| Area | Uji |
| --- | --- |
| Backend | pytest `.venv` dan `.venv-apk` |
| Database | migrasi salinan, integrity check, restore |
| Uang | nota, pembayaran, piutang, retur, void, komisi, gaji |
| Stok | masuk, keluar, retur, minus, minimum, rekonsiliasi |
| Backup | db/xlsx/csv, otomatis/manual/Telegram mock, retensi |
| Keamanan | PIN, sesi, loopback, Host/Origin, token instalasi |
| Web | Chrome/Edge, 360/810/1024/1440, tema, popup |
| APK | install, update, PIN, kasir, struk, backup, restore |
| Printer | Bluetooth, Wi-Fi/LAN, USB, sistem, 58/80 mm |
| Scanner | HID USB/Bluetooth, kamera Android, tambah stok, kode dikenal/tidak dikenal, offline |
| Unit | empat kategori, kolom barang part, unit lengkap vs part, laporan |
| Login | tanpa login, Google, logout/sign out, token aman, offline |
| Ganti toko | posisi di dalam Menu, satu/banyak toko, izin, pemisahan data, offline |
| Header | nama bengkel + printer, alamat toko, ganti toko, layar sempit |
| Backup toko | 3 toko, satu arsip, restore semua sekaligus, rollback, Telegram |
| Offline | kasir tanpa internet, backup lokal, retry Telegram |

## Kriteria selesai

- Tidak ada bug P0/P1 yang terbuka.
- Seluruh pytest lulus di dua stack.
- Migrasi dan restore diverifikasi pada salinan database.
- Tidak ada rahasia baru di repo atau file backup.
- Kasir dan stok tetap benar pada uji konkurensi.
- Backup semua format dan restore berhasil.
- APK 2.7.1 terpasang dan diuji di minimal satu perangkat Android nyata.
- Scanner HID berfungsi di browser dan APK; kamera Android diuji bila tersedia.
- Tambah stok via scanner menambah jumlah barang yang benar; kode baru membuka
  form barang dengan kode terisi.
- Kode scanner yang tidak dikenal atau duplikat tidak merusak input kasir.
- Empat kategori unit tersimpan dan tampil benar di kasir, struk, dan laporan.
- Part dengan kolom barang bebas tidak memerlukan master kategori per item.
- Login tanpa akun bekerja penuh offline; Google hanya untuk akun/sync premium.
- Logout menghapus sesi/token, menghentikan sync, dan tidak menghapus data lokal.
- PIN tetap berlaku setelah logout.
- Tombol ganti toko tampil di dalam panel Menu, di atas Ringkasan, dan tidak
  menutupi navigasi.
- Ganti toko tidak mencampur data antar toko; karyawan hanya melihat toko yang
  diizinkan.
- Header menampilkan nama bengkel + printer di baris pertama dan alamat di
  baris kedua; keduanya berubah saat ganti toko.
- Backup dengan 3 toko menghasilkan satu arsip; setelah aplikasi dihapus dan
  dipasang ulang, restore arsip langsung menampilkan kembali ketiga toko.
- Restore arsip gagal tidak menghilangkan data toko yang lama.
- Printer yang tersedia di lokasi uji berfungsi; yang tidak tersedia dicatat.
- README dan versi sesuai.
- Laporan akhir menyebut file yang disentuh, tes, hash APK, dan risiko.

## Di luar lingkup

- Fitur premium, trial, kuota WhatsApp, dan gating modul.
- Multi-tenant, sync API, owner/employee app.
- Rewrite Flutter, Android/Windows/Mac baru.
- Rename PusatkuPOS.
- Implementasi fungsional 10 jenis bengkel di rilis 2.7.1.
- Onboarding/profil bengkel di rilis 2.7.1.
- Fitur baru lain seperti shift, SPK, pengadaan, QRIS, atau pajak.
- Perubahan desain besar.

## Risiko

- Perangkat Android, scanner, dan printer fisik mungkin tidak tersedia.
- Token Telegram asli tidak dipakai; pengujian hanya mock.
- Dataset besar bisa lambat di mesin uji.
- Perbaikan kecil dapat menyentuh alur kasir; wajib tes regresi.
- Scope creep ke fitur baru di luar scanner harus ditolak selama pemantapan.

## Laporan akhir yang diminta

- Daftar file yang disentuh dan alasannya.
- Tes yang dijalankan dan hasilnya.
- Migrasi/backup yang dibuat.
- APK: versi, ukuran, SHA-256.
- Asumsi, risiko, dan hal yang belum diuji.
