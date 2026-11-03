# BengkelPOS Radiator

Aplikasi kasir dan manajemen servis untuk bengkel radiator: multi-unit per
pelanggan, stok sparepart, tarif jasa, nota servis, garansi, pembatalan dan
retur, laporan harian, serta cetak struk thermal. Berjalan **offline** di
komputer/laptop (web lokal) dan juga bisa dipaketkan menjadi **APK Android**
dengan backend Python tertanam.

Backend FastAPI + SQLAlchemy (SQLite) melayani frontend SPA (HTML/CSS/JS tanpa
build step) di `http://127.0.0.1:8000`.

## Fitur

- **Pelanggan & unit** — satu pelanggan bisa punya banyak mobil/radiator;
  pencarian cepat, ringkasan jumlah unit per pelanggan, dan riwayat servis
  pelanggan yang bisa dibuka langsung dari kartu pelanggan.
- **Transaksi servis (POS)** — jasa + sparepart dalam satu nota, diskon,
  pembayaran CASH/TRANSFER, kembalian, validasi stok, serta opsi izinkan stok
  minus. Zona input jasa dan sparepart dibedakan warna agar kasir tidak salah
  memasukkan item, dan kolom uang otomatis memakai pemisah ribuan
  (`1.000.000`) saat diketik. Strip label hanya ikut tercetak untuk radiator
  copotan; mobil utuh dicetak tanpa strip dan tanpa garis potong.
- **Label barang** — strip label radiator copotan memuat pelanggan, nomor HP,
  unit, jenis barang, dan kode `RAD-YYYYMMDD-NNN` yang berurutan per hari mulai
  `001`. Kode dibuat sekali saat transaksi pertama, lalu dipakai ulang pada
  cetak ulang, void, dan retur. Unit lama yang sudah berlabel tetap memakai
  kodenya; unit radiator tanpa label mendapat kode saat transaksi pertamanya
  tercatat.
- **Pembatalan dan retur** — nota bisa dibatalkan (VOID) atau diretur sebagian
  maupun seluruhnya. Stok dikembalikan secara atomik lewat ledger pergerakan
  stok, bukan dengan menyunting angka stok manual.
- **Garansi** — masa garansi per nota (bulan bebas), status aktif/kadaluarsa,
  catatan klaim, dan klaim yang hanya bisa dilakukan sekali.
- **Kredit & piutang** — nota bisa disimpan sebagai KREDIT dengan uang muka
  opsional, dengan atau tanpa tanggal rencana pembayaran, lalu dilunasi kapan
  saja dari detail nota. Daftar piutang per pelanggan menampilkan sisa, umur
  piutang, dan nota yang belum lunas, dengan tombol **Ingatkan** untuk langsung
  membuka WhatsApp dan **Pelunasan** untuk mencatat pembayaran. Pengingat
  pertama aktif pada hari jatuh tempo, lalu setiap 2 minggu sampai 3 kali;
  setelah itu nota ditandai **Perlu telepon**. **Ubah** pada kolom jatuh tempo
  membuka siklus pengingat baru tanpa menghapus riwayat.
  Daftar piutang memakai kartu ringkas per pelanggan; klik nama untuk membuka
  nota lengkap, sedangkan **Ingatkan**, **Chat**, dan **Pelunasan** tersedia
  langsung sebagai pintasan di kartu. Pelanggan dengan beberapa nota punya
  tombol **N nota** untuk membuka daftar notanya; satu klik **Ingatkan**
  mengirim satu pesan gabungan untuk nota yang sudah jatuh tempo. Nota yang
  belum jatuh tempo tidak ikut dikunci dan tetap menunggu tanggalnya.
  Form pembayaran punya tombol **Kredit**: bila aktif, pembayaran boleh
  sebagian dan sisanya tetap tercatat di Piutang. Opsi **Unit ditinggal**
  menandai kendaraan yang masih di bengkel agar dapat dipakai follow-up saat
  kendaraan selesai.
- **WhatsApp manual** — setelah struk dicetak, aplikasi membuka WhatsApp berisi
  struk lengkap; kasir tetap menekan kirim sendiri. Tombol WhatsApp lain juga
  membuka pratinjau pesan dan tautan `wa.me`. Setiap upaya dicatat, nomor
  ditampilkan tersamarkan, dan pesan hanya aktif bila pelanggan memberi izin.
  Satu gerbang pusat memeriksa izin WhatsApp, jam follow-up, dan status DNC
  sebelum tautan `wa.me` dibuat untuk follow-up, piutang, kendaraan selesai,
  struk, maupun chat. Pesan follow-up memakai bahasa formal dan paragraf
  terpisah: pembuka permintaan maaf, isi yang memperkenalkan bengkel dengan
  nama dari Pengaturan, lalu penutup terima kasih. Setiap kategori punya 2–3
  varian kalimat yang dipilih deterministik; pesan prospek pertama menawarkan
  balasan **BERHENTI**. Template dipisah per keperluan: kendaraan selesai,
  pengingat piutang, prospek, servis berkala, dan garansi; pengingat piutang
  tidak memakai kalimat “kendaraan siap diambil”. Anti-gangguan membatasi
  1 pesan per pelanggan per hari, 2 pesan per bulan untuk prospek/servis,
  jeda 7 hari untuk prospek/servis, serta menggabungkan item sejenis yang
  jatuh bersamaan. Prioritas pesan: Pengerjaan > Piutang > Garansi >
  Servis berkala > Prospek.
- **Follow-up & servis berkala** — menu **Follow up** tersendiri menampilkan
  sembilan kartu kategori: Piutang, Kendaraan selesai, Prospek, Berkendala,
  Servis berkala, Garansi akan habis, serta Akan datang untuk garansi, servis
  berkala, dan prospek. Identitas item mengikuti unit, baris jasa/sparepart,
  atau nota piutang, bukan sekadar pelanggan.
  Setiap kartu membuka daftar atau popup terkait. Kartu follow-up punya
  pintasan **Ingatkan** (WhatsApp dengan teks pengingat), **WA** (chat tanpa
  teks), **Detail**, dan **Status**; tombol **Nota** dihapus karena nota
  lengkap tersedia di Detail. Mengubah status prospek meminta konfirmasi;
  status **Masih kendala** memindahkan prospek ke kartu **Berkendala**.
  Prospek diingatkan pada hari ke-30, 60, dan 90 setelah unit diambil (tanpa
  garansi: hari ke-30 dan ke-90). Unit bergaransi memakai jadwal bulanan
  sampai H-7; prospek dilewati bila acuan+30 sudah melewati H-7 dan ditunda
  bila garansi/servis unit itu jatuh tempo dalam 14 hari. Pintasan Status
  Prospek berisi **Masih bagus**, **Masih kendala / belum bisa**, **Akan
  datang service** (tanggal wajib), dan **Tidak perlu lagi**. **Belum bisa**
  menunda kontak 2 atau 4 minggu; tiga kali tidak merespons menutup item
  sampai servis berikutnya. Tombol Status baru aktif setelah pelanggan
  diingatkan lewat Ingatkan/WA.
  Pengaturan menyediakan **jam mulai** dan **jam selesai follow up**; di luar
  rentang itu tombol Ingatkan follow-up dan pengingat piutang tidak bisa
  dipakai, dan backend menolak permintaannya.
  Di kartu Berkendala, pintasan **Status** hanya berisi **Sudah datang**,
  **Tidak datang**, dan **Reschedule** (wajib tanggal); reschedule
  mengembalikan prospek ke daftar Prospek dengan tanggal kunjungan baru.
  Detail prospek tidak lagi memuat tombol Ingatkan/WA atau form status.
  Pada servis berkala dan garansi, status **Akan datang** beserta tanggal
  memindahkan item ke kartu Akan datang, sedangkan **Tidak akan datang** dan
  **Tidak perlu lagi** menghapusnya dari kolom follow up. Garansi diingatkan
  pada H-7 dan H; pengingat H dilewati bila H-7 sudah dibalas atau sudah ada
  janji datang sebelum H, lalu item diarsipkan pada H+7. Daftar Akan datang menampilkan pintasan
  **Status** dan **WA** (chat tanpa teks). Detail item akan datang punya tiga
  tombol: **Datang**, **Tidak datang**, dan **Reschedule** (wajib tanggal);
  reschedule memperbarui jadwal tanpa mengeluarkan pelanggan dari kolom.
  Detail servis berkala dan garansi tidak lagi memuat tombol Ingatkan/WA,
  petunjuk jeda follow-up, atau form status karena semuanya ada di pintasan
  kartu; detail menampilkan nota lengkap. Rincian servis berkala hanya
  memuat baris dari nota yang menjadi sumber follow-up, tidak digabung
  dengan nota lain. Bila teks pesan WhatsApp diedit
  sebelum dibuka, tautan dan riwayat memakai teks hasil editan itu. Kartu
  **Kendaraan selesai** membuka unit yang ditandai "Unit ditinggal" saat nota
  dicatat; kasir dapat mengabari pelanggan lewat WhatsApp (tombol terkunci
  setelah pesan dibuka), mengubah status pengerjaan beserta riwayatnya, lalu
  menandainya sudah diambil. Unit yang masih di bengkel tidak muncul di
  prospek, garansi, servis berkala, atau piutang sampai diambil. Bila masih ada sisa
  tagihan, nota pembayaran dibuka lebih dulu dan unit baru ditandai diambil
  setelah pembayaran tersimpan. Setiap tarif jasa dan sparepart
  punya interval servis (bulan) yang dapat diubah; nilainya disalin ke nota
  saat dikerjakan dan menjadi pengingat servis berikutnya.
- **Ringkasan operasional** — kartu unit diservis, tunai masuk, transfer masuk,
  garansi aktif, total hutang seluruh pelanggan, stok menipis, dan stok habis.
  Total hutang membuka daftar piutang; stok menipis dan stok habis membuka
  daftar stok yang sudah difilter.
- **Supplier & Follow up Reseller** — menu Supplier menyimpan nama, WhatsApp,
  dan barang yang disuplai. Barang boleh punya beberapa supplier dan dapat
  dipilih saat menambah/mengedit sparepart. Tab Follow up Reseller memakai
  susunan kartu dan ringkasan angka yang sama dengan Follow up Pelanggan:
  jumlah supplier, barang menipis, barang habis, dan total barang yang perlu
  dipasok, lalu kartu per supplier dengan chat WhatsApp manual tanpa pesan
  otomatis. Fitur supplier dapat dimatikan dari Pengaturan; saat mati, pilihan
  supplier di form stok dan tab Reseller disembunyikan.
- **Karyawan & komisi** — menu Karyawan mencatat mekanik dan kasir, penugasan
  0 sampai banyak mekanik per nota, performa per periode, riwayat pengerjaan,
  dan estimasi komisi per nota. Karyawan dapat memakai imbalan komisi, gaji
  bulanan, atau keduanya. Kolom gaji bulanan tampil di daftar karyawan, dan
  halaman Karyawan menyediakan pencatatan pembayaran gaji aktual per periode
  beserta riwayat, edit, dan hapus. Komisi dihitung backend dengan basis barang,
  jasa, atau keduanya; pembagian mekanik dapat rata atau manual. Fitur karyawan
  dapat dimatikan dari Pengaturan; saat mati, kolom kasir/mekanik di kasir dan
  baris kasir/mekanik di struk tidak ditampilkan.
- **Multi-toko & premium** — registry toko menyimpan nama, alamat, dan
  `database_id`; setiap toko memakai file SQLite sendiri sehingga nota, stok,
  pelanggan, karyawan, dan laporan tidak tercampur. **Ganti toko** berada di
  panel Menu, header menampilkan nama dan alamat toko aktif, dan tambah toko
  hanya tersedia di premium. Paket gratis tetap membuka kasir, stok, laporan,
  backup manual, dan 20 kredit Follow up; akun karyawan, multi-toko, Supplier,
  serta fitur premium lain terkunci. Data lama tetap dapat dibaca dan diekspor
  saat paket berakhir, tetapi tambah/ubah dan aksi premium ditolak.
- **Akun karyawan & login** — pemilik membuat akun dengan satu peran dasar
  (Kasir, Mekanik, atau keduanya), toko yang ditugaskan, dan izin tambahan.
  Password minimal 8 karakter, dapat diisi tombol acak 10–12 karakter, disimpan
  sebagai hash bcrypt, dan wajib diganti saat login pertama. Di hub, karyawan
  masuk dengan username + password + PIN 6 angka tanpa internet; dari perangkat
  sendiri, karyawan memakai ID owner + username + password + token perangkat.
  Setiap perubahan izin dicatat di audit, dan pemeriksaan izin dilakukan di UI
  serta lapisan data.
- **ID owner & perangkat** — ID owner 8 karakter unik ditampilkan sebagai kartu
  dengan tombol salin dan QR lokal yang hanya berisi ID. Perangkat owner
  terdaftar mengikuti batas paket (contoh 2), dapat dicabut, dan pelepasan slot
  mandiri dibatasi sekali per 72 jam. Hak menulis uang mengikuti flag hub per
  toko; perangkat non-hub dan perangkat karyawan hanya menulis stok sesuai izin.
  Tombol **Ganti kunci toko** membungkus ulang kunci toko hanya untuk perangkat
  aktif, menghapus amplop/snapshot lama, dan mengirim ulang outbox dengan kunci
  baru setelah perangkat dicabut.
- **Sinkronisasi terenkripsi (prototipe web)** — server hanya menyimpan
  metadata, kunci publik, wrapped store key, dan amplop delta terenkripsi
  end-to-end; kunci privat tidak pernah dikirim. Outbox bersifat idempoten,
  konflik opname ditandai, snapshot diterapkan atomik lalu outbox lokal diputar
  ulang, amplop dihapus setelah semua penerima mengakui atau setelah TTL 90
  hari, dan arsip semua toko berbentuk ZIP dengan manifest serta checksum.
  Jalur ini adalah acuan migrasi; Play Billing, secure storage, notifikasi,
  kunci perangkat, dan relay lintas perangkat sungguhan tetap diuji di
  Dart/APK.
- **Nomor nota angka** — nota baru memakai nomor 1, 2, 3, dan seterusnya tanpa
  duplikat atau nomor ulang. Nota lama tetap memakai nomor lama.
- **Pengaturan struk** — setiap bagian struk memiliki tombol on/off sendiri:
  header, nomor nota, tanggal, kasir, mekanik, pelanggan, unit, jasa, part,
  total, pembayaran, garansi, rekening, dan footer. Nama bengkel selalu tampil.
  Pengaturan berlaku untuk cetak dan teks struk WhatsApp.
- **Stok & tarif jasa** — harga modal/jual, penyesuaian jumlah, interval servis
  berkala per jasa dan per sparepart, snapshot modal saat part dipakai, dan
  proteksi hapus item yang sudah dipakai transaksi. Setiap item punya batas
  minimum stok; batas bawaan diatur owner di Pengaturan. Halaman stok dapat
  difilter Semua, Menipis, dan Habis. Daftar stok memakai baris
  lebih rapat agar lebih banyak item terlihat; tabel jasa, riwayat, dan laporan
  tidak ikut dirapatkan.
- **Laporan** — kas harian, rekap periode, penjualan sparepart, estimasi laba
  bersih sparepart dan jasa, estimasi laba bersih setelah dikurangi komisi
  dan gaji yang benar-benar dibayar pada periode, rincian per metode bayar,
  dan laporan semua waktu. Pembayaran gaji memakai tanggal bayar sebagai dasar
  pemotongan, sehingga gaji yang dibayar di luar periode tidak mengurangi
  laporan periode tersebut.
- **Printer universal** — kelola beberapa printer dari Pengaturan: Bluetooth
  (SPP), Wi-Fi/LAN (TCP 9100), USB OTG, cetak lewat layanan Android, dan cetak
  lewat browser. Mendukung kertas 58/80 mm, tes cetak, serta printer utama.
- **Backup & pemulihan** — snapshot SQLite lengkap (pelanggan, unit, riwayat
  servis, transaksi keuangan, stok, pengaturan), pemulihan dengan validasi
  skema dan salinan pengaman otomatis. Backup manual tersedia di semua paket;
  backup terjadwal lokal, backup Telegram/remote, dan arsip semua toko hanya
  aktif di premium. Di paket gratis, pengingat backup manual tetap tampil.
  Backup, ekspor spreadsheet, dan arsip meredaksi hash password/PIN karyawan,
  token perangkat, `login_guards`, serta rahasia sesi dan Telegram; konfigurasi
  printer tidak ikut ke database atau backup.
- **Pengaturan** — identitas bengkel, rekening transfer, token/jadwal Telegram,
  printer, tema, jam follow-up, dan seluruh angka pengingat dapat diubah dari UI
  tanpa mengedit `.env`. Angka yang dapat diatur mencakup tempo piutang, tahap
  prospek, jeda follow-up, H- pengingat garansi, arsip garansi, H- servis
  berkala, jeda dan batas pengingat piutang, penundaan belum bisa, batas pesan
  harian/bulanan, jeda prospek/servis, serta batas tidak merespons. Setiap
  bagian tampil sebagai judul yang bisa diklik; isi formulir hanya dibuka saat
  dibutuhkan agar halaman tetap ringkas.
- **Tampilan terang/gelap** — antarmuka berbasis kertas putih dengan aksen
  warna pada angka dan status penting; pilihan Terang atau Gelap tersimpan per
  perangkat di Pengaturan dan langsung berlaku tanpa memuat ulang halaman.
  Kontrol memakai satu geometri: 40 px di desktop dan 44 px di layar sempit
  atau perangkat sentuh. Navigasi mobile menjadi satu baris yang dapat digeser,
  modal panjang memakai footer aksi tetap, dan tabel tidak keluar dari layar.
  Daftar lengkap teks dan popup ada di `docs/UI_COPY_INVENTORY.md`.
- **APK Android** — gerbang PIN 4-12 angka native (PBKDF2 + salt, lockout
  bertingkat), shell WebView, backend berjalan di dalam aplikasi. Saat server
  disiapkan, layar menampilkan indikator loading lingkaran. Layar utama
  dapat di-screenshot dan direkam; hanya layar PIN yang diproteksi. Layar
  mengikuti area aman (status bar, navigation bar, dan notch) sehingga kontrol
  tidak tertutup sistem, dan warna status bar ikut tema terang/gelap. Build APK
  debug terakhir adalah **2.7.0** (versionCode 19); kode web premium setelah
  2026-11-03 belum dipaketkan ke APK.

## Menjalankan versi web/desktop

Prasyarat: Python 3.10 atau lebih baru (diverifikasi pada Python 3.12.10 dan
3.14.7).

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
membuat PIN pemilik 4&ndash;12 angka. Data tersimpan di
`data/bengkel_radiator.db`, backup di `backups/`, dan konfigurasi printer di
`data/printer_config.json`.

## Konfigurasi penting (`.env`)

| Variabel | Fungsi |
| --- | --- |
| `APP_HOST` | Alamat server. Hanya `127.0.0.1`, `localhost`, atau `::1` yang diterima; nilai lain menggagalkan startup. |
| `APP_PORT` | Port web lokal (default 8000). |
| `AUTH_MODE` | `session-pin` untuk versi web/desktop; `install-token` diisi otomatis oleh APK. |
| `DATABASE_URL` | Default `sqlite:///./data/bengkel_radiator.db`. |
| `BENGKEL_*` | Identitas bengkel & rekening; nilai awal, bisa diubah dari menu Pengaturan. |
| `DEFAULT_GARANSI_BULAN`, `GARANSI_SYARAT_STANDAR` | Nilai awal garansi untuk nota baru. |
| `PRINTER_PAPER_WIDTH`, `PRINTER_DEFAULT_ENCODING` | Default kertas (58/80 mm) dan encoding teks struk. |
| `PRINTER_CONFIG_PATH` | Berkas konfigurasi printer per perangkat (default `./data/printer_config.json`), di luar database dan backup. |
| `BACKUP_DIR` | Folder backup lokal. |
| `BACKUP_KEEP` | Jumlah file backup terakhir yang disimpan (default 14). |
| `BACKUP_MAX_RESTORE_MB` | Batas ukuran berkas restore yang diunggah (default 64 MB). |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Nilai awal backup Telegram; bisa diisi dari Pengaturan. |
| `TELEGRAM_BACKUP_ENABLED`, `TELEGRAM_BACKUP_TIME` | Sakelar dan jam pengiriman harian Telegram (default 21:00). |
| `BACKUP_SCHEDULER` | `python` untuk versi desktop (default). APK memakai `workmanager`, diisi otomatis oleh `bootstrap.py`. |

Backup manual dapat dijalankan di semua paket. Backup lokal terjadwal dan
pengiriman Telegram hanya berjalan saat lisensi premium aktif; di paket gratis
snapshot terjadwal dilewati dan pengguna diarahkan memakai backup manual. Di
versi desktop, penjadwal berjalan selama aplikasi terbuka; di APK 2.7.0,
WorkManager menjalankan jadwal harian, tetapi build APK tersebut belum memuat
kode premium. Pengiriman Telegram adalah tambahan opsional: bila token dan Chat
ID diisi, file snapshot yang sama dikirim ke chat bot. Format backup otomatis
dapat dipilih di Pengaturan: database (`.db`), Excel (`.xlsx`), atau CSV dalam
ZIP. Database dapat dipulihkan; Excel dan CSV hanya untuk dibaca atau diolah.
Backup manual dan bagikan mengikuti pilihan format manual di Pengaturan;
pemulihan tetap memakai `.db`. Nilai `APP_ENV=test` mematikan penjadwal agar
test tidak berjalan latar.

`.env` **tidak pernah** ikut di-commit; hanya `.env.example`. Identitas bengkel
dan konfigurasi Telegram yang disimpan lewat UI berada di database dan
menimpa nilai default `.env`.

## Keamanan akses web

Web lokal hanya untuk PC kasir itu sendiri; tidak ada mode LAN. Server menolak
startup bila `APP_HOST` bukan loopback, menolak header `Host` asing, menolak
permintaan tulis dari `Origin` lain, dan mematikan `/docs`, `/redoc`, serta
`/openapi.json`.

Akses aplikasi dijaga PIN pemilik:

- PIN dibuat saat aplikasi pertama kali dibuka dan disimpan sebagai hash
  PBKDF2 + salt di database (bukan plaintext).
- Login menghasilkan cookie sesi `HttpOnly` + `SameSite=Strict` berlaku 12 jam;
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

Prasyarat build: JDK 17, Android SDK 35, dan Python 3.10+ lengkap dengan
modul `venv` di mesin build.

```bash
cd android
./gradlew test          # unit test Kotlin (JVM)
./gradlew assembleDebug # APK debug
```

Di Windows, tunjuk interpreter host lewat
`-Pchaquopy.buildPython="C:/path/python/python.exe"` bila `py` atau `python`
tidak tersedia di PATH.

Detail arsitektur, versi dependensi, hasil build, dan batasan ada di
[`android/README_APK.md`](android/README_APK.md). Perilaku PIN, lockout, dan
alur reset ada di [`android/README_PIN.md`](android/README_PIN.md). Build debug
terakhir yang dibangun adalah versi **2.7.0** (versionCode 19).

Di APK, backend berjalan dengan `AUTH_MODE=install-token`: setiap request
membawa header `X-Install-Token` dari token acak per instalasi yang disimpan
terenkripsi. Server menolak startup bila token itu kosong atau masih
placeholder `ganti-dengan-...`. Shell WebView hanya mengizinkan navigasi ke
`http://127.0.0.1` pada port backend aplikasi; layar PIN web tidak dipakai
karena PIN sudah native.

Layar utama APK (WebView) **tidak** memakai `FLAG_SECURE`, sehingga nota,
laporan, dan tampilan operasional dapat di-screenshot atau direkam. Layar PIN
tetap memakai `FLAG_SECURE`, dan `privacyCover` menutup pratinjau recents saat
aplikasi masuk latar belakang.

Batasan APK saat ini: printer fisik belum diuji di perangkat nyata (jalur
Bluetooth SPP, TCP 9100, USB OTG, dan cetak Android sudah tersedia), pemulihan
dari Telegram tetap manual (unduh file lalu pilih di Pengaturan), dan proses
aplikasi dapat dimatikan Android saat di latar belakang (data aman di SQLite;
WorkManager tetap menjalankan backup harian). APK 2.7.0 juga **belum memuat**
prototipe premium/multi-toko yang sekarang ada di web: paket backend, daftar
dependensi Chaquopy (termasuk `bcrypt`), dan `versionCode` harus diperbarui saat
migrasi APK dikerjakan.

## Struktur proyek

```
api/            router FastAPI, skema Pydantic (kompatibel v1 & v2), dependency auth
services/       logika bisnis: POS, void/retur, laporan, garansi, struk, printer, backup
repositories/   akses data SQLAlchemy
database/       engine/session, model, migrasi, seed
frontend/       SPA (index.html, css, js) + PrinterManager dan adapter printer
android/        proyek APK: PIN, WebView shell, jembatan printer, Chaquopy, bootstrap.py
tests/          pytest (API + alur bisnis)
run.py          runner lokal
reset_pin.py    pemulihan darurat PIN di PC kasir
```

## Pengujian

```bash
python -m pytest -q
```

400 test pada jalur desktop mencakup transaksi, kredit/pelunasan/piutang,
WhatsApp, follow-up dan servis berkala (jasa dan sparepart), void/retur, stok,
garansi, laporan, pengaturan, label barang, printer, backup/restore, Telegram,
serta pemeriksaan keamanan akses (PIN, sesi, token instalasi, loopback,
host/origin). Termasuk 15 tes premium web untuk akun/peran, lisensi dan ID
owner, perangkat/hub, kunci toko, relay E2E, snapshot, konflik, TTL, arsip semua
toko, dan login perangkat karyawan. Jalur desktop memakai Pydantic v2;
kombinasi APK tetap memakai Pydantic 1.10 + FastAPI 0.115 dan harus diuji ulang
saat APK dibangun kembali.

Unit test Kotlin untuk PIN, backup, printer, dan shell WebView juga tersedia
(154 test pada build terakhir):

```bash
cd android
./gradlew test -Pchaquopy.buildPython="<path python lengkap dengan venv>"
```

Chaquopy memakai interpreter host hanya untuk menjalankan pip. Nilainya wajib
ditunjuk eksplisit di Windows karena `py`/`python` tidak ada di PATH mesin build.
Interpreter host boleh berbeda dari target runtime 3.10; build terakhir memakai
Python 3.12.

Database dummy untuk uji manual dapat dibangun ulang dengan
`SEED_DB_REL=data/dummy_manual.db python tools/seed_manual_test.py`. Skrip ini
mengisi pelanggan, unit, nota, piutang, garansi, servis berkala, follow-up,
stok, retur, void, dan unit yang masih di bengkel, lalu menghapus PIN lama agar
alur pendaftaran dapat dicoba dari awal.

## Keamanan dan data

- PIN pemilik di-hash PBKDF2-HMAC-SHA256 + salt; sesi ditandatangani HMAC dengan
  rahasia yang tersimpan di database, sehingga reset PIN membatalkan sesi lama.
  Password karyawan di-hash bcrypt dengan salt per pengguna; hash PBKDF2 lama
  tetap dapat dibaca dan dimigrasikan saat login.
- Server hanya mendengar loopback, memvalidasi `Host`, menolak `Origin` asing
  untuk permintaan tulis, dan tidak membuka dokumentasi API otomatis.
- File backup database meredaksi PIN, sesi, hash password/PIN karyawan, hash
  token perangkat, `login_guards`, dan token bot Telegram. Ekspor Excel/CSV
  serta arsip semua toko juga meredaksi nilai rahasia tersebut; database aktif
  tetap menyimpan token karena dibutuhkan untuk pengiriman. Konfigurasi printer
  disimpan di berkas terpisah dan tidak ikut masuk database atau backup.
- Pustaka QR dimuat dari aset lokal (tanpa CDN); QR hanya berisi ID owner, bukan
  password, token, atau data bengkel.
- Di APK: hash PIN + salt di EncryptedSharedPreferences, layar PIN memakai
  `FLAG_SECURE`, `allowBackup=false`, dan server hanya mendengar `127.0.0.1`.
- Data transaksi tidak dikirim ke layanan pihak ketiga; Telegram hanya dipakai
  bila fitur backup diaktifkan pengguna.

Dokumen pendukung:

- [`docs/UI_COPY_INVENTORY.md`](docs/UI_COPY_INVENTORY.md) — inventaris seluruh
  teks UI, popup, dan pesan kesalahan.
