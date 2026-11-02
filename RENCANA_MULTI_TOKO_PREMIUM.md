# Rencana Multi-Toko dan Fitur Premium — PusatkuPOS

Status: **rencana aktif — belum diimplementasikan**. 2026-11-03.

Produk target: **PusatkuPOS (Flutter)**. Aplikasi 2.7.0 yang berjalan sekarang
tetap **BengkelPOS Radiator** (web) dan **menerima fitur ini lebih dulu** sebagai
kanal uji web; setelah perilakunya teruji, fitur dibawa ke PusatkuPOS Flutter.

Dokumen ini menggabungkan rencana multi-toko dan fitur premium. Pengujian tidak
dicantumkan di sini; seluruh skenario uji ada di `RENCANA_PEMANTAPAN.md` dan baru
dijalankan setelah fiturnya dibangun.

## Ringkasan keputusan

- **Premium:** Karyawan, Supplier, Follow up, semua tombol WhatsApp, backup
  otomatis, dan multi-toko.
- **Trial:** hanya fitur Follow up; 20 klik WhatsApp total per database, tanpa
  batas waktu. Database yang sama tidak bisa mengulang trial; database baru
  mendapat ID baru dan trial baru.
- **Kuota:** 1 klik WhatsApp = 1 kuota. Kuota dipotong saat tombol/link `wa.me`
  dibuka, bukan saat pesan benar-benar terkirim.
- **Setelah trial:** premium membuka pesan unlimited dan seluruh fitur premium.
- **Gratis:** lokal penuh, satu perangkat, satu toko, tanpa panggilan API data,
  dan **tanpa iklan sama sekali** walaupun perangkat terhubung internet.
- **Multi-toko adalah fitur premium.** Pengguna gratis tetap satu toko dan tidak
  melihat tombol tambah toko.
- **Login Google wajib untuk pemilik multi-toko.** Karyawan memakai akun yang
  dibuat pemilik dan tidak wajib punya akun Google.
- **Tidak ada batas jumlah toko** untuk akun premium.
- **ID owner unik:** setiap pemilik memiliki ID unik global yang dibuat sekali
  dan tidak pernah sama dengan pemilik lain. ID ini mengikat lisensi, kuota,
  toko, perangkat, dan routing relay, serta menjadi pembeda username karyawan
  antar pemilik.
- **Login karyawan tanpa Google:** akun karyawan dibuat pemilik; form login
  memakai tiga kolom: ID owner, username, dan password.
- **Peran + izin tambahan:** setiap karyawan punya peran dasar (mis. Kasir), dan
  pemilik dapat menambah izin per karyawan (mis. Budi kasir + stok opname).
  Izin bersifat aditif, tercatat, diperiksa di lapisan data, dan tidak membuka
  akses khusus pemilik.
- **ID database unik:** setiap database punya `database_id` unik yang hanya
  dipakai mencatat pemakaian trial. ID ini tidak mengikat pemilik, perangkat,
  atau lisensi, dan tidak membatasi siapa yang boleh membuka database.
- **VPS tidak menyimpan data bengkel.** API hanya menjadi relay pertukaran data
  antar perangkat/karyawan; tidak ada database tenant, salinan, atau retensi di
  server.
- **Dua aplikasi:** aplikasi utama memuat core logic dan dipakai owner tanpa
  karyawan serta karyawan; aplikasi owner terpisah tanpa core logic hanya untuk
  ringkasan, laporan, dan akun karyawan.
- **Distribusi modular:** paket dasar berisi shell dan seluruh logika fitur
  (login, SQLite, sync, printer, backup, izin, pengelola paket resource). Paket
  resource per peran—layout, aset, label, konfigurasi tampilan—diunduh saat
  login pertama. Android memakai Play Asset Delivery; iOS masa depan memakai
  unduhan aset/On-Demand Resources; Windows memakai paket resource bertanda
  tangan. Tidak ada dex/JAR/so atau self-update, dan paket tidak boleh menambah
  fitur yang tidak ada di shell.
- **Premium awal** berfokus pada fitur lokal dan multi-toko. Sinkronisasi API,
  multi-device, mode karyawan, dan aplikasi owner terpisah adalah tahap premium
  lanjutan.
- **Multi-device adalah hak premium.** Setelah relay aktif, satu pemilik premium
  dapat memakai lebih dari satu perangkat dengan ID owner yang sama, sesuai
  batas perangkat paketnya. Gratis dan trial tetap satu perangkat.
- **Premium dijual sebagai langganan bulanan, bukan sekali bayar.** Harga dan
  daftar paket final ditentukan saat implementasi; arah awal: paket
  Rp10.000/bulan maksimal 2 perangkat. Setiap paket punya batas login perangkat
  sendiri; batas dapat diubah lewat rilis aplikasi, bukan diatur pengguna.
- **Data fitur terkunci tetap dapat dibaca dan diekspor.** Saat fitur Karyawan,
  Supplier, atau Follow up terkunci karena paket berakhir atau turun paket, data
  lama tetap terlihat dan dapat diekspor; yang diblokir hanya tambah/ubah data
  dan aksi premium. Data tidak dihapus.
- **Lisensi diverifikasi dengan token dan hitung mundur di perangkat.** Saat
  offline lama, aplikasi memakai token bertanda tangan dan sisa masa aktif
  lokal; VPS tetap tidak menyimpan data bengkel. Jika paket habis saat ada delta
  pending, aplikasi mengirim delta itu lebih dulu saat online, lalu berhenti
  mengirim sampai langganan aktif kembali.
- **ID owner:** 8 karakter acak (minimum 7), huruf kecil dan angka tanpa karakter
  ambigu (`0`, `1`, `l`, `o`), unik global dan tidak berurutan. ID ditampilkan
  sebagai kartu teks + tombol salin + QR untuk dibagikan ke karyawan; QR hanya
  berisi ID owner, bukan rahasia.
- **Password karyawan:** dibuat pemilik atau otomatis lewat **tombol acak**
  berbentuk ikon putar/bulat, minimal 8 karakter, wajib berbeda dari semua
  karyawan lain di owner yang sama, dan diganti saat login pertama. Tombol yang
  sama dipakai untuk reset. Ada **tombol salin semua** untuk mengirim ID owner +
  username + password sekaligus; password hanya tampil sekali. Tidak ada
  kedaluwarsa otomatis; pemilik dapat mereset kapan saja. PIN 6 digit diatur
  karyawan sendiri; jika lupa, pemilik mereset PIN dan karyawan membuat PIN baru.
- **Aplikasi Python lama disimpan.** Setelah Flutter stabil, aplikasi lama tidak
  dihapus: diarsipkan, tidak diberi fitur baru, dan tetap menjadi acuan/rollback.
- **Relay tidak harus langsung.** Jika internet mati, delta tetap disimpan di
  outbox perangkat dengan status pending; saat online, antrean dikirim
  berurutan. VPS tidak menyimpan delta tersebut.
- **Banyak akun dan penulisan offline.** Satu owner dapat memiliki banyak akun
  karyawan, misalnya 100 akun. Masing-masing dapat mencatat riwayat dan menambah
  stok saat offline; data diurutkan dan digabung saat perangkat kembali online.
- **Pending jangka panjang wajib diberitahukan.** Antrean tidak kedaluwarsa
  walau internet mati berbulan-bulan; aplikasi wajib menampilkan banner dan
  notifikasi sistem selama masih ada data pending.

## Batas gratis, trial, dan premium

| Area | Gratis | Trial | Premium |
| --- | --- | --- | --- |
| Model harga | Gratis | Gratis | Langganan bulanan per paket |
| Kasir, stok, pelanggan, unit, jasa, laporan | Ya | Ya | Ya |
| Backup manual dan restore satu toko | Ya | Ya | Ya |
| PIN dan pengaturan lokal | Ya | Ya | Ya |
| Satu toko | Ya | Ya | Ya |
| ID database unik (internal) | Ya | Ya | Ya |
| Karyawan | Tidak | Tidak | Ya |
| Supplier | Tidak | Tidak | Ya |
| Follow up | Tidak | Demo | Ya |
| Tombol WhatsApp | Tidak | 20 klik per database (Follow up) | Unlimited |
| Akun karyawan (ID owner + username + password) | Tidak | Tidak | Ya |
| Izin tambahan per karyawan di luar peran dasar | Tidak | Tidak | Ya |
| Backup otomatis | Tidak | Tidak | Ya (lokal + Telegram) |
| Backup semua toko | Tidak | Tidak | Ya |
| Multi-toko dan ganti toko | Tidak | Tidak | Ya |
| ID owner unik + login Google pemilik | Tidak perlu | Tidak wajib (toko tunggal) | Ya |
| Jumlah perangkat aktif | 1 | 1 | Sesuai batas paket (contoh: 2 perangkat) |
| Sinkronisasi API (relay) | Tidak | Tidak | Ya, tahap premium lanjutan |
| Multi-device lewat relay | Tidak | Tidak | Ya, sesuai batas perangkat paket |
| Data fitur terkunci (Karyawan/Supplier/Follow up) | Tidak ada | Follow up tetap dibaca/diekspor | Tetap dibaca/diekspor setelah paket berakhir |
| Aplikasi utama (core logic; owner tanpa karyawan dan karyawan) | Ya | Ya | Ya |
| Mode karyawan di aplikasi utama | Tidak | Tidak | Ya |
| Aplikasi owner terpisah (tanpa core logic; ringkasan, laporan, akun, izin tambahan) | Tidak | Tidak | Tahap lanjutan |
| Unduhan paket resource sesuai peran | Ya (paket dasar) | Ya | Ya (paket premium sesuai lisensi) |
| Iklan | Tidak ada | Tidak ada | Tidak ada |

Trial hanya membuka fitur Follow up sebagai demo. Karyawan, Supplier, dan backup
otomatis tetap terkunci. Setelah 20 klik WhatsApp habis, Follow up dan seluruh
fitur premium terkunci sampai berlangganan. Data lokal tidak dihapus; data lama
tetap dapat dibaca dan diekspor.

Catatan:

- Kuota 20 dihitung per `database_id`, bukan per email atau perangkat.
- `database_id` tidak mengikat pemilik atau perangkat. Database baru mendapat ID
  baru dan trial baru; yang dicegah hanya pengulangan trial pada database yang
  sama.
- Sinkronisasi API adalah relay; VPS tidak menyimpan data bengkel.
- Unduhan paket resource dasar lewat Play bukan panggilan API data dan tidak
  mengirim data bengkel. Setelah paket terpasang, pengguna gratis berjalan
  offline.
- Multi-device bukan fitur gratis atau trial. Satu pemilik premium dapat memakai
  perangkat sebanyak batas paketnya dengan ID owner yang sama; perangkat di atas
  batas harus logout atau dicabut. Perangkat tambahan tunduk pada aturan satu
  penulis untuk uang; stok dapat ditulis sebagai delta dari perangkat berizin.
- Langganan dihitung per paket, bukan per toko. Jumlah toko tetap tanpa batas;
  yang dibatasi adalah perangkat aktif. Contoh arah: Rp10.000/bulan = 2
  perangkat.
- Saat langganan berakhir, data Karyawan, Supplier, dan Follow up tetap dapat
  dibaca dan diekspor. Yang terkunci hanya penambahan/perubahan data dan aksi
  premium seperti kirim WhatsApp dan backup otomatis.

## Fitur premium

### 1. Karyawan

- Data karyawan, peran, penugasan mekanik/kasir, komisi, gaji, dan performa.
- Mode karyawan pada aplikasi utama menjadi sumber absensi, status pengerjaan,
  komisi, dan performa; rinciannya di bagian Aplikasi utama dan aplikasi owner.
- Data karyawan tidak ikut ke perangkat gratis.

### 2. Supplier

- Data supplier, relasi supplier–barang, follow up reseller, dan riwayat
  supplier.
- Tombol WhatsApp supplier memakai kuota yang sama dengan tombol WA lain.

### 3. Follow up

- Follow up pelanggan, garansi, servis berkala, prospek, piutang, dan reseller.
- Hasil follow up dan pengingat.
- Semua pengiriman WhatsApp dari fitur ini memakai kuota.

### 4. Semua tombol WhatsApp

- Mencakup struk, follow up, piutang, garansi, reseller, supplier, dan tombol
  WhatsApp lain di aplikasi.
- 1 klik = 1 kuota, termasuk saat pengguna membatalkan atau WhatsApp gagal
  dibuka. Tidak ada pengembalian kuota.

### 5. Backup otomatis

- Backup terjadwal lokal dan Telegram. Tidak ada backup ke VPS.
- Backup manual dan restore tetap tersedia untuk pengguna gratis.
- Sinkronisasi bukan pengganti backup; backup lokal tetap menjadi cadangan
  utama.
- Backup semua toko memakai satu arsip; rinciannya di bagian Multi-toko.
- Backup menyertakan outbox pending agar data yang belum terkirim tidak hilang
  saat perangkat rusak atau hilang.
- Backup manual tetap menyertakan data fitur yang sedang terkunci (Karyawan,
  Supplier, Follow up), sehingga data lama tidak hilang saat paket berakhir.

### 6. Multi-tenant, sinkronisasi, dan multi-device

- Satu tenant per bengkel; data terpisah antar bengkel.
- Perangkat hub dengan peran kasir mengirim delta transaksi lewat API hanya ke
  perangkat owner/karyawan yang berhak; VPS tidak menyimpan delta tersebut.
- Pemilik premium boleh memakai lebih dari satu perangkat sesuai batas paketnya,
  dengan ID owner yang sama. Relay mengirim delta ke semua perangkat pemilik
  yang terdaftar, dan setiap perangkat memakai database lokal serta outbox
  sendiri. Perangkat di atas batas ditolak sampai logout atau dicabut.
- Laporan owner dihitung dari database lokal di perangkat owner yang sudah
  menerima delta lewat relay.
- Multi-device hanya premium; gratis dan trial tetap satu perangkat. Batas
  perangkat mengikuti paket langganan, bukan jumlah toko.
- Satu perangkat ditetapkan sebagai hub kasir. Perangkat lain tidak menulis
  nota, pembayaran, atau retur; menu tulis uang nonaktif dan permintaan langsung
  ditolak. Stok dapat ditulis dari perangkat berizin sebagai delta.
- Perpindahan peran hub harus eksplisit. Dua perangkat tidak boleh menjadi hub
  aktif bersamaan untuk uang.
- Pengiriman relay tidak harus real-time. Setiap perubahan masuk outbox lokal;
  saat internet mati, delta berstatus pending dan transaksi tetap berjalan.
- Saat online, outbox dikirim berurutan sesuai nomor urut perangkat. Item yang
  sudah terkirim ditandai dan tidak dikirim ulang.
- Delta pending tidak kedaluwarsa hanya karena internet mati; antrean disimpan
  lokal sampai berhasil terkirim atau dibatalkan pengguna.
- Kasir tetap offline-first: API mati tidak menghentikan transaksi.
- Sinkronisasi, multi-device, mode karyawan, dan aplikasi owner terpisah
  dikerjakan setelah premium awal dan multi-toko stabil.

#### Banyak akun dan penggabungan data

- Satu owner dapat memiliki banyak akun karyawan, misalnya 100 akun. Setiap
  akun memakai perangkat dan outbox sendiri; data antar owner tetap terpisah
  oleh ID owner.
- Setiap akun dapat mencatat riwayat dan menambah stok saat offline; owner dapat
  mempersempit tindakan lewat izin peran. Delta bersifat append-only
  (penambahan/pengurangan), bukan nilai stok akhir.
- Nota, pembayaran, dan retur tetap hanya ditulis kasir/hub. Opname atau koreksi
  stok absolut tidak digabung otomatis; jika bertabrakan, ditandai sebagai
  konflik untuk diputuskan kasir/owner.
- Saat perangkat kembali online, outbox dikirim berurutan per perangkat.
  Penggabungan antar perangkat memakai jam logis (HLC) dan ID perangkat; jam
  dinding hanya untuk tampilan.
- Data dianggap lengkap setelah semua perangkat terdaftar mengirim pending dan
  menerima pembaruan. Sebelum itu, stok dan riwayat berstatus sementara dan
  ditandai belum lengkap.

#### Pending jangka panjang dan pemberitahuan wajib

- Delta pending disimpan lokal tanpa batas waktu; internet mati berbulan-bulan
  tidak menghapus antrean.
- Selama masih ada pending, aplikasi wajib:
  - menampilkan banner tetap di layar utama berisi jumlah delta dan usia data
    terlama;
  - mengirim notifikasi sistem lokal saat pengiriman gagal, lalu mengulang
    berkala (mis. 1 jam, 24 jam, 7 hari, lalu tiap 7 hari);
  - menampilkan badge pada menu sinkronisasi dan status perangkat.
- Notifikasi tidak dapat dimatikan permanen selama pending masih ada; pengguna
  hanya dapat menunda. Notifikasi memakai mekanisme lokal sehingga tetap muncul
  tanpa internet.
- Setelah pending terkirim dan semua perangkat terdaftar melapor, status berubah
  menjadi tersinkron dan notifikasi berhenti.
- Aplikasi owner menampilkan status sinkron perangkat: terakhir online dan
  jumlah pending terakhir yang dilaporkan. Ini metadata relay, bukan data
  bengkel.

## Aplikasi utama dan aplikasi owner

- **Aplikasi utama** secara keseluruhan—shell ditambah paket resource per
  peran—memuat seluruh core logic. Shell menyimpan seluruh logika, layar, aksi,
  izin, dan perhitungan; paket resource hanya mengatur tampilan, label, dan aset
  peran. Karyawan dan owner yang tidak punya karyawan memakai aplikasi ini.
- Owner tanpa karyawan memakai aplikasi utama dengan semua fitur; fitur premium
  tetap terkunci bila akun gratis.
- Karyawan memakai aplikasi utama; setelah login hanya melihat tampilan dan toko
  yang diizinkan.
- Pembatasan dilakukan di UI dan lapisan data/izin, bukan hanya menyembunyikan
  tombol. Permintaan langsung ke data yang tidak diizinkan tetap ditolak.
- **Aplikasi owner** adalah aplikasi **terpisah** yang dibuat nanti. Aplikasi ini
  tidak memuat core logic dan tidak menjalankan kasir, stok, atau transaksi.
- Aplikasi owner hanya untuk pemilik yang punya karyawan atau multi-toko;
  pemilik tanpa karyawan tidak perlu aplikasi ini.
- Data aplikasi owner diterima lewat relay; VPS tidak menyimpan data bengkel.

### Aplikasi utama: owner tanpa karyawan

- Owner memakai semua fitur: kasir, stok, pelanggan, unit, jasa, laporan, dan
  pengaturan.
- Fitur premium mengikuti paket: gratis terkunci, trial hanya Follow up, premium
  terbuka.
- Owner dapat bertransaksi langsung dari aplikasi ini; ini jalur untuk bengkel
  tanpa karyawan.
- Pemilik premium dapat memasang aplikasi di beberapa perangkat sesuai batas
  paket dengan ID owner yang sama. Satu perangkat menjadi hub untuk uang (nota,
  pembayaran, retur); stok dapat dicatat dari perangkat lain sebagai delta.
- Multi-toko tetap memerlukan akun pemilik dan lisensi premium.

### Aplikasi utama: mode karyawan

- Terbuka setelah login dengan ID owner + username + password; tanpa Google.
- Hanya menampilkan fitur sesuai **peran dasar + izin tambahan** dan toko yang
  ditugaskan. Menu owner dan pengaturan akun tidak muncul.
- Aplikasi operasional untuk kasir/teknisi sesuai peran dan izin tambahan.
  Contoh: kasir dengan izin tambahan opname melihat menu opname tanpa berubah
  menjadi peran stok.
- Izin tambahan tidak mengubah peran dasar, komisi, atau aturan penulis uang;
  izin hanya menambah aksi yang diizinkan.
- Menjadi sumber perhitungan:
  - absensi dan jam kerja;
  - penugasan dan status pengerjaan;
  - penyelesaian servis dan catatan;
  - komisi dari pekerjaan yang diselesaikan;
  - pencatatan stok sesuai izin (permintaan atau penambahan).
- Pada perangkat hub, peran kasir menjadi satu-satunya penulis nota, pembayaran,
  dan retur. Stok dapat ditambah karyawan berizin dari perangkatnya masing-masing
  sebagai delta yang digabung saat sinkronisasi.
- Selama masih ada delta pending, stok dan riwayat di perangkat bersifat
  sementara dan ditandai belum lengkap.
- Karyawan tidak dapat melihat toko lain, mengubah tarif komisi, atau mengubah
  gaji.
- Komisi, gaji, dan performa dihitung dari data mode karyawan; owner hanya
  melihat hasilnya.

### Aplikasi owner (terpisah, tanpa core logic)

- Isi:
  - ringkasan hari ini per toko: penjualan, servis, pembayaran, piutang, stok
    kritis, dan aktivitas karyawan;
  - laporan per toko dan per periode;
  - buat akun karyawan: username, password awal (diketik atau **tombol acak**),
    peran dasar, toko yang ditugaskan, dan izin tambahan; **tombol salin semua**
    untuk mengirim ID owner + username + password sekaligus; ubah/cabut izin,
    reset password, dan cabut perangkat;
  - riwayat perubahan izin per karyawan (siapa, kapan, sebelum/sesudah);
  - status sinkron perangkat: terakhir online dan jumlah pending terakhir yang
    dilaporkan.
- Read-only untuk data operasional: tidak membuat atau mengubah nota,
  pembayaran, retur, stok, atau komisi.
- Ganti toko memfilter ringkasan dan laporan ke satu toko; data tidak tercampur.
- Tanpa core logic, aplikasi owner tidak dapat menghitung ulang transaksi; semua
  angka berasal dari data yang diterima lewat relay.

## Distribusi modular dan unduhan per peran

- **Paket dasar (base)** berisi seluruh logika aplikasi: launcher, login, SQLite,
  sync, printer, backup, izin, pengelola paket resource, layar, dan aksi.
  Paket resource peran tidak ikut di base.
- **Manifest peran** menentukan paket resource minimum. Saat login pertama,
  aplikasi hanya mengunduh paket resource yang dibutuhkan peran itu; peran
  tambahan mengunduh paket tambahan dan menyimpannya di cache.
- Paket resource berisi layout, aset, label, dan konfigurasi tampilan—bukan kode.
  Paket hanya menampilkan fitur yang sudah ada dan diizinkan di shell; paket
  tidak boleh menambah fitur, logika, atau izin baru.
- Paket dasar gratis diunduh saat pertama membuka aplikasi. Paket premium hanya
  diunduh setelah lisensi aktif; paket yang terkunci tidak dipasang.
- Contoh pemetaan:

  | Peran | Paket resource minimum |
  | --- | --- |
  | Kasir | kasir, pembayaran, struk, pelanggan/unit/jasa baca |
  | Teknisi | servis, status, catatan, stok sesuai izin |
  | Stok | stok, opname |
  | Owner tanpa karyawan | paket gratis; paket premium setelah lisensi aktif |
  | Aplikasi owner | ringkasan, laporan, akun karyawan, izin tambahan (aplikasi terpisah) |

- **Android:** AAB + Play Asset Delivery. Tidak ada unduhan dex/JAR/so, tidak
  ada self-update, dan tidak ada kode yang dieksekusi dari CDN.
- **iOS (masa depan):** paket resource yang sama lewat unduhan aset atau
  On-Demand Resources. Tidak ada executable code yang diunduh; paket tidak boleh
  menambah fitur di luar shell (App Store Review Guidelines 2.5.2).
- **Windows:** installer shell + paket resource bertanda tangan dari CDN.
  Logika uang/stok dan izin tetap di shell; Windows tidak memuat Dart/DLL baru
  saat runtime. EXE lebih ringan, tetapi tidak se-extreme base APK; jika EXE
  harus launcher-only, role executable bertanda tangan menjadi tahap terpisah.
- **Offline:** setelah paket resource terpasang, fitur berjalan tanpa internet.
  Jika paket belum terpasang dan perangkat offline, fitur terkunci dengan pesan
  jelas.
- **Izin:** paket yang terpasang tidak membuka akses di luar peran. Pemeriksaan
  tetap di shell dan lapisan data.
- **Versi paket:** shell menolak paket resource di bawah versi minimum; update
  paket mengikuti rilis aplikasi/Play. Windows dan iOS memverifikasi tanda
  tangan/checksum paket sebelum dipakai, dengan rollback ke paket bawaan bila
  gagal.
- **Sideload:** tanpa Play, tidak ada unduhan aset on-demand. APK sideload
  memakai APK penuh/split; jalur ringan hanya berlaku lewat Play.
- **Cache:** paket resource tidak dihapus otomatis saat logout; pengguna dapat
  membersihkannya dari pengaturan. Paket diunduh ulang saat dibutuhkan. Backup
  data tidak menyertakan cache paket.

## Kepatuhan Google Play

- Android dirilis sebagai AAB lewat Play dengan Play App Signing; target API
  mengikuti syarat Play terbaru.
- Distribusi per peran memakai Play Asset Delivery untuk paket resource, bukan
  unduhan kode. Tidak ada dex/JAR/so dari luar Play, tidak ada self-update, dan
  tidak ada WebView yang mengeksekusi kode dari CDN.
- Unduhan paket resource menampilkan ukuran/progres dan tidak berjalan diam-diam.
- Langganan fitur digital di Android memakai Google Play Billing, termasuk
  restore, acknowledge, perpanjangan, dan pembatalan. Jika ada program
  pembayaran alternatif, hanya yang diizinkan Play yang dipakai.
- Sediakan hapus akun di aplikasi dan tautan web; konfirmasi menjelaskan data
  lokal dan metadata server yang dihapus.
- Data safety: akun, lisensi, perangkat, dan kuota; tidak ada data bengkel di
  VPS.
- Privacy policy tersedia dan dapat diakses dari aplikasi serta listing Play.
- Izin Android (printer, file, notifikasi) diminta saat dibutuhkan dengan alasan
  yang jelas.

## Kepatuhan iOS (masa depan)

- iOS belum menjadi target rilis; aturan ini disiapkan agar rencana tidak perlu
  dirombak saat target iOS dimulai.
- Tidak ada unduhan kode yang dieksekusi. Paket peran tetap resource/layout/aset
  dan diunduh lewat mekanisme aset atau On-Demand Resources, mengikuti App Store
  Review Guidelines 2.5.2.
- Paket resource tidak boleh menambah fitur, logika, izin, atau fungsi yang belum
  ada di shell; tanpa paket, fitur tetap ada dan hanya tampilannya yang berbeda.
- Langganan fitur digital di iOS memakai In-App Purchase dengan restore,
  perpanjangan, dan pembatalan; tidak ada tautan pembayaran eksternal yang
  melanggar aturan App Store.
- Sediakan hapus akun di aplikasi dan tautan web, privacy policy, serta App
  Privacy Details (data yang dikumpulkan: akun, lisensi, perangkat, kuota; tanpa
  data bengkel di server).
- Izin iOS (Bluetooth printer, file, notifikasi) diminta saat dibutuhkan dengan
  alasan yang jelas di Info.plist.

## Multi-toko

### Keputusan cakupan

- Multi-toko bukan UI kosong. Fitur baru dirilis setelah registry toko,
  database per toko, dan pemisahan data bekerja.
- Multi-toko lokal berarti **satu database SQLite per toko ditambah registry
  toko**.
- Login tanpa akun tetap jalur default untuk **toko tunggal dan pengguna
  gratis**. Multi-toko, ganti toko, dan backup semua toko hanya tersedia untuk
  premium dengan login Google pemilik.
- Multi-toko dan ganti toko harus tetap bekerja **offline setelah login awal**.
  Internet hanya dibutuhkan untuk login, aktivasi lisensi, dan sinkronisasi.
- Google hanya dipakai untuk identitas, akun premium, dan sinkronisasi. Data
  bengkel tetap disimpan lokal lebih dulu.
- Tidak ada tombol atau menu multi-toko yang dikirim sebelum backend-nya
  tersedia.
- Belum ada user saat ini, jadi tidak ada backup data operasional. Backup semua
  toko adalah fitur produk untuk user mendatang.
- Tidak perlu migrasi data 2.x satu toko ke multi-toko; database baru dibuat
  dari nol.

### Prasyarat

1. Backup/restore satu toko di PusatkuPOS sudah tersedia dan stabil.
2. Lapisan data web 2.7.0 dan repository siap; SQLite/drift disiapkan saat port
   Flutter.
3. Keputusan bisnis: multi-toko premium (diputuskan 2026-11-03).
4. Keputusan peran: pemilik boleh menambah toko; karyawan hanya melihat toko
   yang ditugaskan (diputuskan).
5. Keputusan akun: Google wajib untuk pemilik multi-toko; karyawan memakai akun
   buatan pemilik tanpa Google (diputuskan 2026-11-03).
6. Penyimpanan aman platform untuk token (Keystore/Keychain/DPAPI) tersedia.

### Arsitektur lokal

- Setiap toko memiliki database sendiri, misalnya
  `stores/<store_id>/database.db`.
- Setiap database memiliki **`database_id` unik** (UUIDv7/ULID) yang dibuat saat
  database pertama kali dibuat dan disimpan di tabel meta. ID ini tidak berubah
  saat backup/restore.
- `database_id` hanya dipakai untuk mencatat pemakaian trial. ID ini tidak
  mengikat `owner_id`, perangkat, lisensi, atau toko.
- Siapa pun yang memiliki file database dapat membukanya; aplikasi tidak
  mencocokkan `database_id` dengan pemilik atau perangkat.
- Salinan file database membawa `database_id` dan status trial yang sama.
- Daftar toko disimpan di registry lokal, misalnya `stores/registry.json`,
  berisi ID owner, ID toko, nama, alamat, toko aktif, versi skema, dan waktu
  dibuat.
- Registry adalah sumber kebenaran daftar toko. Setiap database toko berdiri
  sendiri; tidak ada foreign key lintas toko.
- Ganti toko menutup koneksi database aktif, menyelesaikan penulisan yang
  tertunda, lalu membuka database toko tujuan.
- Toko aktif disimpan di registry. Jika registry rusak, aplikasi menampilkan
  peringatan dan memakai toko valid terakhir; aplikasi tidak membuat toko baru
  secara otomatis.
- Toko baru dibuat dengan database kosong dan skema terbaru. Data toko lain
  tidak disalin.
- Penghapusan toko bukan bagian MVP; jika ditambahkan nanti, wajib memakai
  konfirmasi, backup, dan prosedur rollback.
- Skema database setiap toko memakai versi yang sama. Registry mencatat versi
  skema; database baru dibuat dari nol.

### ID owner dan akun karyawan

- Setiap pemilik memiliki **ID owner unik global** yang dibuat sekali dan tidak
  pernah sama dengan pemilik lain. ID ini tidak berubah walaupun nama bengkel,
  daftar toko, atau perangkat berganti.
- ID owner dipakai untuk:
  - mengikat lisensi premium, kuota trial, daftar toko, dan daftar perangkat ke
    satu pemilik;
  - merutekan delta lewat relay ke perangkat milik pemilik yang benar tanpa
    menyimpan data bengkel di VPS;
  - memisahkan username karyawan antar pemilik, sehingga dua pemilik boleh
    memakai username karyawan yang sama.
- ID owner **bukan rahasia** dan boleh dibagikan ke karyawan karena dipakai saat
  login. ID owner saja tidak memberi akses; akses tetap membutuhkan username dan
  password.
- Format ID owner: **8 karakter acak** (minimum 7), huruf kecil dan angka,
  tanpa karakter ambigu `0`, `1`, `l`, dan `o`. Contoh bentuk: `398urw7x`.
  Panjang ini cukup untuk mencegah tebakan tanpa menyulitkan pengetikan.
- ID owner ditampilkan sebagai **kartu** berisi teks besar + tombol salin dan
  **QR** untuk dibagikan ke karyawan. QR hanya berisi ID owner, bukan password
  atau token.
- Username karyawan hanya wajib unik di dalam satu ID owner, tidak perlu unik
  global.
- Akun karyawan dibuat pemilik lewat aplikasi owner: username, password awal,
  peran dasar, toko yang ditugaskan, dan **izin tambahan** opsional. Karyawan
  tidak memakai Google. Password boleh diketik pemilik atau dibuat otomatis
  dengan **tombol acak**.
- Akun karyawan disimpan di server sebagai metadata akun (username, hash
  password, peran, penugasan, izin tambahan), bukan data bengkel.
- Password disimpan sebagai hash (Argon2id/bcrypt); password awal wajib diganti
  saat login pertama.
- **Kebijakan password karyawan:** minimal 8 karakter, dibuat pemilik, dan wajib
  berbeda dari semua karyawan lain di owner yang sama. Sistem menolak password
  yang sama saat pembuatan atau penggantian. Tidak ada kedaluwarsa otomatis;
  pemilik dapat mereset kapan saja. Tidak ada pemulihan mandiri lewat email.
- **Kebijakan PIN karyawan:** PIN 6 digit diatur karyawan sendiri setelah login
  pertama dan tidak dibagikan. Jika lupa, karyawan meminta reset PIN ke pemilik;
  pemilik mereset PIN, lalu karyawan membuat PIN baru. PIN tidak sama dengan
  password akun.
- Pemilik dapat mereset password, menonaktifkan akun, dan mencabut perangkat
  karyawan dari aplikasi owner kapan saja.

### Membuat dan membagikan akun karyawan

- Di samping kolom password ada **tombol acak berbentuk ikon putar/bulat**.
  Tombol ini langsung mengisi password acak yang lolos kebijakan: 10–12
  karakter, campuran huruf besar/kecil dan angka, tanpa karakter ambigu.
  Pemilik tidak perlu mengetik atau memikirkan password.
- Password hasil tombol acak tetap dicek unik terhadap semua karyawan di owner
  yang sama. Jika bentrok, sistem membuat ulang otomatis.
- Tombol yang sama dipakai untuk **reset password**: menimpa password lama,
  menampilkan password baru sekali, dan mewajibkan karyawan menggantinya saat
  login berikutnya. Reset password tidak otomatis mencabut perangkat; jika akun
  dicurigai bocor, pemilik juga mencabut perangkat karyawan itu.
- Di samping tombol acak ada **tombol salin semua**. Tombol ini menyalin teks
  siap kirim ke clipboard:

  ```text
  PusatkuPOS — akun karyawan
  ID owner: 398urw7x
  Username: budi
  Password: K7mRq2Tn
  Peran: Kasir
  Toko: Bengkel Pusat
  Ganti password saat login pertama.
  ```

- Teks salin semua tidak berisi PIN, token, atau data bengkel. Pemilik tinggal
  menempelkannya ke WhatsApp atau aplikasi pesan lain.
- Password hanya ditampilkan di dialog pembuatan/reset dan tidak bisa dilihat
  lagi setelah dialog ditutup. Jika pemilik lupa, gunakan tombol acak untuk
  reset ulang; password lama langsung tidak berlaku.
- Tombol salin semua hanya aktif selama password baru masih tampil di dialog.
  Ini mencegah password lama tersalin tanpa sengaja.
- QR karyawan tetap hanya berisi ID owner; password tidak pernah masuk QR atau
  tautan.

### Peran dan izin tambahan per karyawan

- Setiap karyawan memiliki **satu peran dasar**—misalnya Kasir, Teknisi, atau
  Stok—yang menentukan menu dan aksi minimum.
- Pemilik dapat menambah **izin tambahan** per karyawan di luar peran dasarnya.
  Contoh: Budi berperan Kasir, lalu diberi izin tambahan untuk stok opname.
- Izin tambahan bersifat **aditif**: peran dasar tidak dihapus dan tidak
  otomatis diperluas ke karyawan lain. Setiap tambahan dicatat per akun.
- Katalog izin mengikuti fitur aplikasi, misalnya opname, stok masuk/keluar,
  lihat laporan, baca Supplier, baca Follow up, atau cetak laporan. Daftar final
  ditetapkan saat implementasi.
- **Akses khusus pemilik tidak dapat diberikan** lewat izin tambahan: kelola
  akun/perangkat, lisensi/langganan, tambah/hapus toko, ubah tarif komisi/gaji,
  dan hapus data.
- Izin tambahan tidak mengubah aturan penulis uang. Nota, pembayaran, dan retur
  tetap hanya dari perangkat hub/kasir. Izin stok hanya menambah hak delta stok
  atau opname; untuk memindahkan hak kasir, peran atau hub harus diubah.
- Izin tambahan disimpan sebagai metadata akun, di-cache di perangkat untuk
  offline, dan diperiksa di UI **serta** lapisan data/izin. Permintaan langsung
  yang tidak diizinkan tetap ditolak.
- Perubahan izin berlaku saat login atau sinkronisasi berikutnya. Perangkat yang
  offline memakai izin terakhir yang tersimpan sampai berhasil sinkron; pemilik
  tetap dapat mencabut perangkat untuk menghentikan akses.
- Setiap perubahan izin dicatat (siapa, kapan, sebelum/sesudah) dan terlihat di
  aplikasi owner.
- Jika izin tambahan bertabrakan dengan fitur yang terkunci paket, paket tetap
  menang; izin tidak membuka fitur premium yang tidak aktif.

### Login karyawan

Form login karyawan memakai tiga kolom:

| Kolom | Isi |
| --- | --- |
| ID unik | ID owner yang diberikan pemilik |
| Username | Username yang dibuat pemilik |
| Password | Password akun karyawan |

- Login pertama membutuhkan internet untuk memverifikasi akun ke server.
- Setelah login berhasil, perangkat menyimpan token perangkat di penyimpanan
  aman; pemakaian berikutnya bisa memakai PIN perangkat saat offline.
- PIN 6 digit diatur karyawan sendiri, bukan oleh pemilik. Jika lupa, karyawan
  meminta reset PIN ke pemilik, lalu membuat PIN baru.
- Kombinasi ID owner + username menentukan akun. ID owner yang salah atau tidak
  cocok ditolak dengan pesan umum, tanpa membocorkan apakah username ada.
- Percobaan login dibatasi dan dikunci sementara per kombinasi ID owner +
  username.
- Karyawan hanya melihat toko yang ditugaskan pada akunnya.

### Login tanpa akun, Google, dan logout

- **Tanpa login** adalah jalur default untuk toko tunggal/pengguna gratis:
  lokal, satu perangkat, tanpa internet, dan memakai PIN perangkat. Data
  disimpan di SQLite lokal pada folder aplikasi perangkat; tidak ada upload ke
  API.
- **Login Google wajib untuk pemilik multi-toko.** Google dipakai untuk
  identitas, lisensi premium, dan akun; data tetap disimpan lokal lebih dulu.
- Karyawan tidak wajib punya akun Google. Mereka memakai akun yang dibuat
  pemilik dan login dengan ID owner + username + password; lihat bagian
  "Login karyawan".
- Login Google hanya dipakai untuk akun pemilik multi-toko premium. Tanpa
  premium atau saat memakai toko tunggal, data tetap lokal dan tidak diunggah.
  Dengan premium, delta dipertukarkan lewat API ke perangkat yang berhak; VPS
  tidak menyimpan salinan, dan database lokal tetap menjadi sumber utama.
- Login pertama membutuhkan internet. Setelah itu data lokal tetap dapat dipakai
  saat offline; permintaan login ulang hanya muncul saat fitur akun/sync
  dipakai.
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
- Token Google disimpan di penyimpanan aman platform, bukan di database biasa.
  Aplikasi tidak memakai Google Drive untuk data bengkel kecuali fitur itu
  ditambahkan eksplisit.
- Jika aplikasi dihapus, data hanya dapat dipulihkan dari backup lokal/Telegram;
  VPS tidak menyimpan salinan data bengkel.

### Ganti toko di dalam Menu

- Tombol/dropdown **Ganti toko** ditempatkan **di dalam panel Menu**, di bagian
  paling atas dan tepat di atas item Ringkasan. Bukan tombol terpisah di luar
  panel menu.
- Saat tombol Menu ditekan, Ganti toko tampil sebelum Ringkasan.
- Menampilkan nama toko yang sedang aktif.
- **Gratis:** panel hanya menampilkan toko aktif tanpa tombol tambah; bila perlu,
  tampilkan ajakan upgrade premium.
- **Premium:** jika belum ada toko kedua, panel menampilkan toko aktif dan
  tombol **Tambahkan toko baru**.
- Jika sudah ada beberapa toko, panel menampilkan daftar **Toko A**, **Toko B**,
  dan seterusnya, dengan penanda toko aktif, lalu tombol **Tambah toko** di
  bagian bawah. Tidak ada batas jumlah toko untuk premium.
- Menekan **Tambahkan toko baru/Tambah toko** membuka form nama toko dan alamat
  (serta profil bengkel bila diperlukan). Setelah dibuat, toko masuk ke daftar
  dan dapat langsung dipilih.
- Toko baru memakai database/tenant terpisah; tidak menyalin data toko lain.
- Nota, stok, pelanggan, karyawan, dan laporan tidak boleh tercampur antar
  toko.
- Hanya pemilik yang boleh menambah toko. Pemilik harus login Google dan
  memiliki lisensi premium. Karyawan hanya melihat daftar toko yang ditugaskan
  dan tidak melihat tombol tambah.
- Jika ada perubahan yang belum disimpan, minta konfirmasi sebelum berganti.
- Ganti toko harus bekerja offline untuk toko yang datanya tersedia di
  perangkat.
- Di layar sempit, tombol tetap berada di dalam panel Menu, di atas Ringkasan,
  dan tidak menutupi navigasi.

### Judul bengkel dan alamat di header

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

### Backup semua toko

- Backup semua toko adalah **fitur premium**. Pengguna gratis tetap memakai
  backup satu toko.
- Setiap toko punya database SQLite sendiri, tetapi backup manual dan otomatis
  dibuat sebagai **satu arsip semua toko**, bukan satu file per toko.
- Arsip berisi manifest toko (ID owner, ID database, ID toko, nama, alamat, toko
  aktif), seluruh database toko, versi skema, dan versi aplikasi. Contoh:
  `backup_semua_toko_YYYYMMDD.zip`.
- Arsip menyertakan checksum untuk setiap database dan manifest.
- Backup tidak boleh hanya mengambil toko aktif karena restore bisa
  menghasilkan daftar toko yang tidak lengkap.
- Restore satu arsip langsung memunculkan **Toko A, Toko B, Toko C** dan
  seterusnya tanpa upload/impor database satu per satu.
- Restore memvalidasi manifest, checksum, dan seluruh database. Jika satu
  bagian gagal, seluruh restore dibatalkan dan data lama dikembalikan.
- Restore tidak menolak database berdasarkan ID owner atau `database_id`;
  `database_id` hanya dicatat agar status trial database itu ikut terbawa.
- Restore memakai mekanisme tukar-sementara (staging) sebelum mengganti data
  aktif; data lama disimpan sampai restore dinyatakan berhasil.
- Toko yang ditambahkan setelah backup terakhir akan ikut pada backup
  berikutnya.
- Backup otomatis, manual, dan Telegram memakai arsip yang sama; Telegram tetap
  tunduk pada batas ukuran file.
- Ekspor Excel/CSV dapat berisi subfolder atau workbook per toko di dalam satu
  ZIP.
- PIN, token, dan rahasia perangkat tetap diredaksi dari arsip.
- Tidak ada upload ke VPS/cloud; restore memakai satu arsip lokal atau satu file
  yang dipilih pengguna.
- Fitur ini dikerjakan **setelah** backup satu toko di PusatkuPOS stabil.

## Kuota trial

- Total kuota: **20 klik WhatsApp per database**, hanya untuk tombol WA di fitur
  Follow up.
- Tombol WA di fitur lain tetap terkunci selama trial.
- Tidak ada batas waktu; trial berakhir saat kuota habis.
- Tidak ada penambahan ulang, reset, atau kuota harian/bulanan.
- Kuota dihitung saat tombol WA ditekan dan link `wa.me` dibuat.
- Aplikasi tidak dapat memastikan pesan benar-benar terkirim karena WhatsApp
  berada di luar aplikasi.
- Kuota yang sudah terpakai tidak dikembalikan jika pengguna membatalkan,
  WhatsApp tidak terpasang, atau pesan gagal dikirim.
- Aplikasi menampilkan sisa kuota dan peringatan sebelum habis.
- Setelah kuota 0, tombol WA dan fitur premium terkunci sampai berlangganan.

### Trial per database

- Trial dihitung dari `database_id`, bukan email, akun, perangkat, atau lisensi.
- `database_id` dibuat sekali saat database dibuat dan ikut tersimpan di file
  database serta backup.
- Kuota terpakai disimpan di database. Server hanya mencatat kuota terpakai per
  `database_id` (metadata kuota, bukan data bengkel) agar file database yang
  sama tidak mengulang trial.
- Kuota bersifat monoton untuk `database_id` yang sama: restore atau salin file
  tidak menurunkan kuota terpakai.
- Database yang sama dapat dibuka oleh pemilik atau perangkat lain; status trial
  mengikuti `database_id` tersebut, bukan siapa yang membuka.
- Database baru selalu mendapat `database_id` baru dan memulai trial dari 20.
- Karena tidak ada pengikat perangkat atau akun, ID ini tidak bisa membedakan
  database baru yang dibuat oleh orang yang sama. Yang dicegah hanya pemakaian
  ulang database yang sama; penghapusan aplikasi lalu pembuatan database baru
  tetap menghasilkan trial baru.
- Pencegahan tambahan hanya mungkin lewat pengikat perangkat/akun, dan itu tidak
  dipakai dalam keputusan ini.
- Tanpa internet, kuota lokal tetap dicatat dan memakai token bertanda tangan;
  saat online, nilai tertinggi antara lokal dan server untuk `database_id` yang
  sama yang dipakai.

## Free tier

- Berjalan lokal, satu perangkat, satu toko, tanpa panggilan API data. Paket
  resource dasar diunduh sekali lewat Play; setelah itu berjalan offline.
- Kasir, stok, pelanggan, unit, jasa, laporan, PIN, pengaturan, backup manual,
  dan restore tetap tersedia.
- Karyawan, Supplier, Follow up, tombol WA, backup otomatis, dan multi-toko
  terkunci.
- **Tanpa iklan sama sekali:** tidak ada banner, popup, video, ad SDK, jaringan
  iklan, atau permintaan latar untuk iklan, termasuk saat online.
- Tidak ada pengiriman data ke API developer.

## Arsitektur premium

```text
Aplikasi utama (core logic; web 2.7.0 untuk uji, lalu Flutter)
        │
        ├─ SQLite lokal (database_id) + outbox pending + kuota lokal
        ├─ Registry toko + database per toko
        │
        ├─ Owner tanpa karyawan / mode karyawan (peran dasar + izin tambahan)
        ├─ Pemilik premium: perangkat sesuai batas paket (satu hub kasir)
        ├─ Hub kasir (mode karyawan) ── LAN ── perangkat bengkel
        │
        └─ API relay (HTTPS, tanpa penyimpanan data bengkel)
                ├─ akun owner + ID owner unik, lisensi, daftar perangkat
                ├─ akun karyawan (username, hash password, peran, izin tambahan)
                ├─ validasi kuota trial per database_id
                └─ forward delta dan ringkasan berdasarkan ID owner

Aplikasi owner (tanpa core logic)
        └─ ringkasan, laporan, dan akun karyawan lewat API relay
```

- **Client:** implementasi pertama di web 2.7.0 (BengkelPOS Radiator) agar dapat
  diuji; target produk PusatkuPOS memakai Flutter + SQLite. Aplikasi owner adalah
  klien ringan tanpa core logic.
- **API:** FastAPI sebagai relay; Python hanya di server, tidak masuk paket
  aplikasi. Server hanya menyimpan akun (termasuk akun karyawan), ID owner,
  lisensi, daftar perangkat, dan kuota per `database_id`, bukan data bengkel.
- **Auth:** login tanpa akun untuk pemakaian lokal, Google untuk akun pemilik
  premium, dan login karyawan dengan ID owner + username + password. Token
  perangkat disimpan aman; sign out menghentikan sync di perangkat itu tanpa
  menghapus data lokal.
- **Kuota:** dicatat lokal per `database_id` dan disamakan dengan catatan server
  untuk ID database yang sama saat online.
- **Lisensi:** langganan bulanan per paket. Server menerbitkan token bertanda
  tangan berisi masa aktif dan batas perangkat. Saat offline, aplikasi memakai
  hitung mundur lokal dari token; VPS tidak menyimpan data bengkel. Kegagalan
  API tidak mengunci kasir lokal.
- **Saat langganan berakhir:** fitur premium terkunci, tetapi data lama tetap
  dapat dibaca dan diekspor; kasir dan data lokal tetap jalan. Jika ada delta
  pending, aplikasi mengirimkannya lebih dulu saat online, lalu berhenti
  mengirim sampai langganan aktif kembali. Ini mencegah data hilang tanpa
  memberi akses premium berkelanjutan.
- **Pembayaran:** langganan Android memakai Google Play Billing; Windows/macOS
  memakai penyedia yang dipilih saat tahap lisensi. Aktivasi dan perpanjangan
  lisensi tetap di server; tidak ada pembelian sekali bayar untuk premium.

## Alur trial dan langganan

1. Pengguna membuat akun trial dan mendapat 20 kuota.
2. Hanya fitur Follow up yang terbuka dalam mode demo; fitur premium lain
   terkunci.
3. Setiap klik WA dari Follow up mengurangi kuota satu.
4. Saat kuota habis, Follow up dan fitur premium lain terkunci dan muncul
   pilihan langganan.
5. Langganan bulanan membuka pesan unlimited, seluruh fitur premium, dan batas
   perangkat sesuai paket.
6. Data lokal tetap tersimpan selama trial berakhir.
7. Jika langganan berakhir, kasir lokal tetap jalan; fitur premium terkunci,
   data lama tetap dibaca/diekspor, dan delta pending dikirim lebih dulu saat
   online sebelum pengiriman berhenti.
8. Perpanjangan mengaktifkan kembali fitur premium dan pengiriman delta tanpa
   menghapus data lokal.

## Aturan konflik dan sinkronisasi

- Perangkat hub dengan peran kasir adalah satu-satunya penulis nota, pembayaran,
  dan retur.
- Pemilik premium yang memakai beberapa perangkat tetap tunduk pada aturan satu
  penulis untuk uang: satu perangkat menjadi hub. Stok dapat dicatat dari
  perangkat lain sebagai delta.
- Owner yang memakai aplikasi utama dapat bertransaksi sesuai fitur dan izinnya;
  aplikasi owner terpisah hanya read-only untuk ringkasan, laporan, dan
  manajemen akun karyawan.
- Karyawan berizin menulis absensi, status tugas, catatan, penyelesaian servis,
  pencatatan stok, dan data dasar komisi. Tarif komisi dan gaji tidak dapat
  diubah dari mode karyawan.
- Uang tidak memakai “tulisan terakhir menang”. Stok digabung sebagai delta
  append-only; opname atau koreksi stok absolut yang bertabrakan ditandai
  konflik, bukan ditimpa.
- Urutan dalam satu perangkat mengikuti nomor urut lokal yang selalu naik.
  Delta yang sempat pending tetap dikirim sesuai urutan itu, bukan urutan waktu
  terkirim.
- Urutan antar perangkat memakai jam logis (HLC) dan ID perangkat sebagai
  pemecah seri. Jam dinding dan waktu terima relay hanya untuk tampilan/audit.
- Pengiriman ulang harus idempotent agar nota/stok tidak ganda.
- Relay tidak menyimpan delta; jika perangkat penerima offline, delta ditahan di
  outbox pengirim sampai terkirim.

## Urutan pekerjaan (mudah → sulit)

Keputusan produk sudah selesai 2026-11-03 dan tidak dihitung dalam urutan:
multi-toko premium, Google wajib untuk pemilik, karyawan tanpa Google, ID owner
unik global, login karyawan tiga kolom, tanpa batas toko untuk premium, VPS
hanya menjadi relay tanpa menyimpan data bengkel, premium berupa langganan
bulanan dengan batas perangkat per paket, data fitur terkunci tetap
dibaca/diekspor, ID owner 8 karakter + kartu/QR, serta kebijakan password/PIN
karyawan.

Urutan di bawah ini disusun dari pekerjaan termudah ke tersulit, lalu
disesuaikan dengan dependensi. Jika pekerjaan ringan bergantung pada pekerjaan
yang lebih sulit (misalnya logout membutuhkan login), dependensi menang dan
pekerjaan ringan itu dikerjakan tepat setelah prasyaratnya. Estimasi adalah
perkiraan kasar untuk satu pengembang setelah prasyarat selesai.

Implementasi pertama dilakukan di **web 2.7.0 (BengkelPOS Radiator)** agar fitur
dapat diuji tanpa menunggu port Flutter. Estimasi di bawah adalah perkiraan untuk
implementasi web; port Flutter dikerjakan setelah perilaku web stabil. Pekerjaan
11 adalah persiapan distribusi Flutter dan tidak menghalangi uji web.

| Urutan | Pekerjaan | Kesulitan | Prioritas | Estimasi | Prasyarat |
| --- | --- | --- | --- | --- | --- |
| 1 | Header nama bengkel + alamat | Mudah | P0 | 1–2 hari | Tidak ada; memakai toko aktif dan menyatu saat ganti toko siap |
| 2 | Registry toko + ID owner + `database_id` + folder + database kosong per toko | Mudah–Sedang | P0 | 3–4 hari | Web 2.7.0; lapisan data web |
| 3 | Ganti toko di Menu + izin peran + konfirmasi | Sedang | P0 | 2–3 hari | Registry; login pemilik untuk rilis premium |
| 4 | Akun premium + ID owner unik + login Google pemilik + lisensi + token aman | Sedang–Sulit | P0 | 5–8 hari | Penyimpanan aman web; sesi login |
| 5 | Gating premium + kuota WhatsApp per `database_id` | Sedang | P0 | 3–5 hari | Akun dan lisensi |
| 6 | Langganan, aktivasi, hitung mundur offline, penurunan paket | Sedang | P0 | 3–5 hari | Lisensi |
| 7 | Logout + akun karyawan (ID owner + username + password), tombol acak password, dan salin semua | Sedang | P1 | 3–4 hari | Login pemilik |
| 8 | Backup otomatis + backup semua toko | Sulit | P0/P1 | 8–12 hari | Registry; backup satu toko stabil |
| 9 | Multi-device premium + sinkronisasi banyak akun + notifikasi pending | Sangat sulit | P1 | 12–17 hari | API, outbox, idempotency, HLC |
| 10 | Mode karyawan di aplikasi utama + aplikasi owner terpisah (tanpa core logic), termasuk izin tambahan per karyawan | Sulit–Sangat sulit | P1 | 11–18 hari | Sinkronisasi dasar dan izin |
| 11 | Port Flutter: shell modular + pengelola paket resource + manifest peran + Play Asset Delivery (Android) + paket resource Windows | Sulit | P0 | 10–15 hari | Uji web stabil |

Perkiraan total: **61–93 hari** setelah prasyarat. Pekerjaan 1–6 adalah
rangkaian premium awal dan multi-toko di web; pekerjaan 7 menyusul tanpa menunda
rilis. Pekerjaan 8 boleh berjalan paralel setelah registry siap. Pekerjaan 9–10
adalah tahap lanjutan dan dikerjakan terakhir di web. Pekerjaan 11 adalah
persiapan distribusi Flutter setelah uji web dinyatakan stabil.

Catatan urutan:

- Pekerjaan 1–3 tidak membutuhkan API relay. Pekerjaan 11 membutuhkan akun Play
  Console dan jalur distribusi Play untuk Android.
- Pekerjaan 11 menetapkan batas paket resource: tampilan peran masuk ke paket
  masing-masing, sedangkan logika, layar, aksi, dan izin tetap di shell. Ukuran
  base wajib diukur sebelum fitur peran ditambahkan.
- Pekerjaan 2 mencakup ID owner di registry dan `database_id` di database.
  `database_id` tetap berdiri sendiri dan tidak terikat ke owner atau perangkat.
- Pekerjaan 4–6 satu rangkaian: akun, ID owner, dan lisensi sebelum gating dan
  langganan. Login Google pemilik wajib sebelum multi-toko dirilis.
- Pekerjaan 5 mencatat kuota per `database_id`; ID ini tidak mengikat pemilik
  atau perangkat.
- Pekerjaan 7 (logout dan akun karyawan) menyusul setelah login tanpa menunda
  rilis multi-toko. Akun karyawan memakai ID owner + username + password.
- Pekerjaan 8 menunggu backup satu toko stabil; backup semua toko tidak boleh
  mendahului backup satu toko.
- Pekerjaan 9–10 dikerjakan setelah alur lokal stabil. Mode karyawan dan
  aplikasi owner terpisah menunggu sinkronisasi dasar.
- Pekerjaan 9 mencakup penggabungan banyak akun, notifikasi pending, dan status
  sinkron perangkat. Multi-device tidak boleh dirilis tanpa notifikasi pending.

Urutan wajib: registry dan isolasi sebelum ganti toko; akun dan lisensi sebelum
multi-toko dirilis; backup satu toko stabil sebelum backup semua toko; uji web
stabil sebelum port Flutter; Play Asset Delivery sebelum rilis Android Flutter;
tidak ada rilis UI kosong.

## Kriteria selesai

- **Hanya akun premium** yang dapat menambah toko; pengguna gratis tetap satu
  toko dan tidak melihat tombol tambah.
- **Login Google pemilik wajib** untuk multi-toko; karyawan login dengan ID
  owner + username + password tanpa Google.
- **Setiap pemilik memiliki ID owner unik global** yang tidak pernah sama
  dengan pemilik lain dan tidak berubah setelah dibuat.
- **Dua pemilik boleh memakai username karyawan yang sama** tanpa tabrakan
  karena akun dipisahkan oleh ID owner.
- **ID owner saja tidak membuka akses**; login tetap membutuhkan username dan
  password, dan percobaan dibatasi.
- **Tidak ada batas jumlah toko** untuk akun premium.
- **Paket dasar memuat seluruh logika shell dan fitur**; paket resource peran
  tidak ikut di base dan ukuran base diukur sebelum rilis.
- **Login pertama hanya mengunduh paket resource peran itu.** Kasir tidak
  memasang paket stok/owner; peran tambahan mengunduh paket tambahan dan memakai
  cache.
- **Paket resource tidak menambah fitur atau izin.** Semua layar, aksi, logika,
  dan perhitungan tetap di shell; paket hanya mengatur tampilan.
- **Setelah paket terpasang, fitur berjalan offline.** Jika paket belum terpasang
  dan perangkat offline, fitur terkunci dengan pesan jelas.
- **Android memakai Play Asset Delivery.** Tidak ada unduhan dex/JAR/so dari
  luar Play dan tidak ada self-update. Sideload memakai APK penuh/split.
- **iOS masa depan memakai unduhan aset/ODR tanpa executable code** dan mengikuti
  App Store 2.5.2; paket tidak boleh menambah fitur di luar shell.
- **Paket terpasang tidak membuka izin.** Pemeriksaan peran tetap di shell dan
  lapisan data; permintaan langsung ditolak.
- Shell menolak paket resource di bawah versi minimum dan menyediakan rollback
  ke paket bawaan jika unduhan atau pembaruan gagal.
- Multi-toko bekerja penuh, bukan UI kosong: registry, database per toko, dan
  pemisahan data tersedia.
- Ganti toko tampil di dalam panel Menu, di atas Ringkasan, dan tidak menutupi
  navigasi.
- Nota, stok, pelanggan, karyawan, dan laporan tidak tercampur antar toko;
  karyawan hanya melihat toko yang diizinkan.
- Header menampilkan nama bengkel + printer di baris pertama dan alamat di
  baris kedua; keduanya berubah saat ganti toko.
- Backup dengan 3 toko menghasilkan satu arsip; setelah aplikasi dihapus dan
  dipasang ulang, restore arsip langsung menampilkan kembali ketiga toko.
- Restore arsip yang gagal tidak menghilangkan data toko yang lama.
- Logout menghapus sesi/token, menghentikan sync, dan tidak menghapus data
  lokal; PIN tetap berlaku.
- Hapus akun owner tersedia di aplikasi dan tautan web; konfirmasi menjelaskan
  data lokal serta metadata server yang dihapus.
- Langganan premium Android memakai Google Play Billing; restore, acknowledge,
  perpanjangan, dan pembatalan berjalan; tidak ada tautan pembayaran digital
  eksternal yang melanggar kebijakan Play.
- Login tanpa akun bekerja penuh offline untuk toko tunggal; multi-toko
  memerlukan login Google pemilik dan lisensi premium.
- Free tier tidak menampilkan iklan dan tidak memanggil API.
- Trial hanya membuka Follow up dan memberi 20 klik WA per database.
- Trial dihitung per database; database yang sama tidak bisa mengulang trial.
- Salinan atau restore file database membawa `database_id` dan kuota yang sama.
- Setiap database memiliki `database_id` unik; database baru mendapat ID baru
  dan memulai trial baru.
- Klik WA ke-21 ditolak dan Follow up terkunci.
- Premium membuka pesan unlimited dan semua fitur premium awal.
- Premium dijual sebagai langganan bulanan; tidak ada opsi sekali bayar.
- Batas perangkat mengikuti paket langganan (contoh: paket Rp10.000/bulan = 2
  perangkat); perangkat di atas batas ditolak sampai logout atau dicabut.
- Saat fitur Karyawan, Supplier, atau Follow up terkunci, data lama tetap dapat
  dibaca dan diekspor; hanya tambah/ubah data dan aksi premium yang diblokir.
- Lisensi offline memakai token bertanda tangan dan hitung mundur di perangkat;
  VPS tidak menyimpan data bengkel. Saat langganan berakhir dan ada delta
  pending, delta dikirim lebih dulu saat online, lalu pengiriman berhenti sampai
  langganan aktif kembali.
- ID owner 8 karakter acak (minimum 7), huruf kecil/angka tanpa `0`, `1`, `l`,
  `o`, unik global, ditampilkan sebagai kartu teks + tombol salin + QR.
- Password karyawan minimal 8 karakter, unik di antara karyawan satu owner,
  diganti saat login pertama, tanpa kedaluwarsa otomatis, dan dapat direset
  pemilik. PIN 6 digit diatur karyawan sendiri dan direset pemilik jika lupa.
- Tombol acak mengisi password yang lolos kebijakan tanpa diketik pemilik;
  tombol salin semua menyalin ID owner + username + password + peran + toko
  dalam satu teks siap kirim. Password hanya tampil sekali setelah dibuat atau
  direset, dan reset membuat password lama langsung tidak berlaku.
- Pemilik premium dapat memakai perangkat sesuai batas paket dengan ID owner
  yang sama; delta tersinkron lewat relay dan perangkat baru memakai database
  lokal sendiri.
- Perangkat pemilik yang bukan hub tidak dapat menulis nota, pembayaran, atau
  retur; stok boleh ditambah dari perangkat berizin sebagai delta. Percobaan
  langsung ditolak di lapisan izin.
- Gratis dan trial tetap satu perangkat; multi-device terkunci.
- Satu owner dapat memiliki 100 akun karyawan atau lebih; masing-masing dapat
  mencatat riwayat dan menambah stok saat offline tanpa tercampur dengan owner
  lain.
- Delta dari banyak perangkat digabung setelah online memakai urutan perangkat
  dan jam logis; stok tidak ganda dan opname yang bertabrakan ditandai konflik.
- Pending bertahan walau internet mati berbulan-bulan. Aplikasi wajib
  menampilkan banner, badge, dan notifikasi sistem berkala selama pending ada;
  notifikasi tidak dapat dimatikan permanen.
- Status data berubah menjadi lengkap setelah semua perangkat terdaftar mengirim
  pending dan menerima pembaruan.
- Kasir tetap bertransaksi saat API mati total.
- Backup manual tetap bisa dipulihkan tanpa API atau VPS.
- Data lokal tidak hilang saat trial berakhir.
- VPS tidak menyimpan data bengkel; API hanya meneruskan pertukaran data antar
  perangkat.
- Relay tidak harus langsung; delta saat internet mati tersimpan pending di
  perangkat dan terkirim berurutan saat online.
- Pengiriman ulang delta pending tidak menggandakan nota atau stok.
- Jika API/VPS mati, delta ditahan di outbox dan data lokal tetap utuh.
- Aplikasi utama dipakai owner tanpa karyawan dan karyawan; owner tanpa
  karyawan dapat membuka semua fitur, dengan fitur premium terkunci bila akun
  gratis.
- Aplikasi owner terpisah tidak memuat core logic dan tidak dapat bertransaksi;
  hanya ringkasan hari ini per toko, laporan, dan pembuatan akun karyawan.
- Mode karyawan di aplikasi utama menjadi sumber absensi, status pengerjaan, dan
  komisi; perhitungan komisi dan gaji memakai data tersebut.
- Aplikasi utama menampilkan menu sesuai peran dasar + izin tambahan; percobaan
  membuka menu atau data owner dari mode karyawan ditolak di lapisan izin, bukan
  hanya disembunyikan.
- Pemilik dapat menambah izin per karyawan tanpa mengubah peran dasarnya;
  contoh Budi kasir + opname berhasil membuka opname, sedangkan karyawan kasir
  lain tanpa izin tetap ditolak.
- Izin tambahan tidak dapat membuka akses khusus pemilik (kelola akun/perangkat,
  lisensi, tambah/hapus toko, ubah tarif komisi/gaji, hapus data).
- Pencabutan izin berlaku saat login/sinkron berikutnya; perangkat offline
  memakai izin terakhir sampai sinkron, dan pemilik dapat mencabut perangkat.
- Setiap perubahan izin tercatat dan terlihat di aplikasi owner.
- Karyawan hanya melihat toko yang ditugaskan dan tidak dapat mengubah tarif
  komisi atau gaji.
- Fitur multi-toko dan premium lolos uji di web 2.7.0 sebelum port Flutter
  dimulai.
- Aplikasi Python lama disimpan sebagai arsip/acuan dan tidak dihapus saat
  Flutter stabil.
- Tidak ada rahasia di arsip backup.

## Aplikasi Python lama

- Setelah PusatkuPOS Flutter stabil, aplikasi Python lama **disimpan**, bukan
  dihapus.
- Aplikasi lama tidak diberi fitur baru dan tidak lagi menjadi target rilis;
  fungsinya sebagai arsip, acuan perilaku, dan jalur rollback bila diperlukan.
- Database dan backup lama tidak dihapus atau dimigrasikan paksa. Data baru
  berjalan di database baru.
- Proyek lama hanya diarsipkan agar tidak membingungkan pengembangan; tidak ada
  pekerjaan pemeliharaan rutin.

## Di luar lingkup

- Penyimpanan data bengkel di VPS atau cloud; API hanya relay.
- Penghapusan atau pemindahan kepemilikan toko.
- Backup ke Google Drive.
- Migrasi otomatis data 2.x satu toko ke multi-toko; belum ada user, database
  baru dibuat dari nol.
- Modul WebView yang mengeksekusi kode dari CDN; paket peran memakai Play Asset
  Delivery (Android), unduhan aset/ODR (iOS nanti), dan paket resource bertanda
  tangan (Windows).
- Unduhan kode yang dieksekusi di luar toko aplikasi, Play Feature Delivery, atau
  self-update.
- iOS sebagai target rilis tahap ini; target Flutter tahap ini Android, Windows,
  dan macOS.

## Risiko

- Isolasi data lemah dapat mencampur nota/stok antar toko.
- Registry rusak dapat menyembunyikan toko; butuh pemulihan yang aman.
- Restore semua toko memperbesar dampak kegagalan; wajib all-or-nothing.
- Arsip multi-toko cepat membesar dan dapat melewati batas Telegram.
- Aplikasi owner tanpa core logic bergantung pada relay; jika data belum
  diterima, ringkasan bisa kosong atau tertinggal dan aplikasi tidak dapat
  menghitung ulang.
- Login Google menambah ketergantungan jaringan; kasir tetap harus offline
  setelah login awal.
- Gating premium yang salah dapat mengunci pengguna gratis dari toko tunggal
  atau membuka multi-toko tanpa lisensi.
- Izin tambahan dapat menumpuk dan terlupakan; aplikasi owner wajib menampilkan
  ringkasan izin per karyawan dan riwayat perubahannya.
- Pencabutan izin saat karyawan offline baru berlaku setelah sinkron; pemilik
  harus dapat mencabut perangkat untuk menghentikan akses segera.
- Izin yang hanya disembunyikan di UI bisa ditembus lewat permintaan langsung;
  pemeriksaan wajib ada di lapisan data dan tetap memakai izin terakhir yang
  sah.
- Batas perangkat dapat diakali dengan menyalin database atau token; perangkat
  harus terdaftar dan token perangkat terikat, sedangkan penegakan offline
  memakai hitung mundur dan daftar perangkat terakhir.
- Hitung mundur lisensi offline bergantung pada jam perangkat; jam mundur tidak
  boleh memperpanjang masa aktif, dan koreksi dilakukan saat online.
- Data fitur terkunci sengaja tetap dapat dibaca/diekspor; ini bukan kebocoran,
  tetapi akses tulis dan aksi premium tetap harus diblokir.
- Langganan lewat Play Billing/IAP harus direkonsiliasi saat online; pembatalan,
  refund, atau chargeback tidak boleh menghapus data lokal.
- Play Asset Delivery hanya berjalan lewat Play; APK sideload memakai APK
  penuh/split dan tidak ringan. Login pertama peran juga membutuhkan internet.
- Base shell tetap memuat Flutter engine, layar, logika, dan aksi; ukuran base
  harus diukur dan tidak boleh membengkak oleh paket resource peran.
- Windows tidak punya Play Asset Delivery; paket resource bertanda tangan tidak
  menghapus logika dari shell, jadi EXE tidak sekecil base APK.
- iOS (App Store) melarang unduhan kode yang dieksekusi; paket peran harus tetap
  resource/aset lewat unduhan aset/ODR dan tidak boleh menambah fitur di luar
  shell (App Store 2.5.2).
- Versi shell dan paket resource dapat berbeda; paket lama harus ditolak dan
  unduhan gagal/korup harus dapat diulang tanpa merusak data.
- Banyak peran di satu perangkat dapat menumpuk cache paket; sediakan pembersihan
  cache tanpa menghapus data.
- Paket terpasang dapat disalahartikan sebagai izin; shell tetap wajib menolak
  akses di luar peran.
- Multi-device pada satu owner dapat menimbulkan dua penulis uang jika
  penetapan hub gagal; perangkat non-hub harus ditolak di lapisan izin untuk
  uang, bukan hanya dinonaktifkan di UI.
- 100 akun yang offline lama dapat menghasilkan antrean besar; unggahan harus
  dibatching, dapat dilanjutkan, dan tidak memblokir kasir.
- Jam perangkat yang berbeda dapat mengacaukan urutan; urutan wajib memakai jam
  logis, bukan jam dinding.
- Notifikasi pending yang berulang dapat diabaikan; banner tetap dan status
  perangkat harus selalu terlihat.
- Pending berbulan-bulan dapat hilang jika perangkat rusak atau hilang; backup
  lokal wajib menyertakan outbox pending.
- Karyawan tanpa Google harus tetap dapat membuka toko yang ditugaskan tanpa
  membocorkan toko lain.
- ID owner yang salah ketik atau tertukar membuat login karyawan gagal; UI harus
  mudah menyalin/membagikan ID dan menampilkan pesan yang jelas.
- Karyawan tidak punya email pemulihan; reset password sepenuhnya lewat pemilik,
  sehingga akun pemilik wajib aman.
- Tombol salin semua menyalin password dalam bentuk teks biasa; pemilik harus
  mengirim lewat kanal pribadi dan karyawan wajib menggantinya saat login
  pertama. Clipboard tidak dibersihkan otomatis oleh sistem.
- ID database tidak mengikat siapa pun; membuat database baru selalu memberi
  trial baru, jadi hanya pemakaian ulang database yang sama yang bisa dicegah.
- Kuota per database dapat diakali dengan menghapus aplikasi lalu membuat
  database baru; ini keterbatasan yang diterima.
- Kesalahan input di mode karyawan langsung memengaruhi komisi dan gaji;
  koreksi harus tercatat dan disetujui pemilik.
- Menyembunyikan menu saja tidak cukup; izin harus diperiksa di lapisan data
  agar mode karyawan tidak bisa membuka data owner lewat permintaan langsung.
- ID owner yang mudah ditebak dapat dipakai mencoba username; rate limit dan
  lockout wajib aktif.
- Kuota lokal bisa diakali jika tidak terikat ID owner/lisensi.
- `wa.me` tidak bisa memastikan pesan terkirim; kuota dihitung saat klik.
- Konflik multi-device jika uang/stok ditulis dari beberapa perangkat.
- Biaya API relay, akun, dan dukungan.
- Delta salah kirim atau bocor saat transit jika isolasi akses lemah.
- API/VPS mati membuat sinkronisasi berhenti; data lokal tetap aman.
- Data lama 2.x tidak dibawa; database baru dibuat dari nol.

## Keputusan tambahan (2026-11-03)

- **Harga dan model:** premium adalah langganan bulanan, bukan sekali bayar.
  Harga/daftar paket final ditentukan saat implementasi; arah awal
  Rp10.000/bulan untuk 2 perangkat.
- **Batas perangkat:** mengikuti paket langganan; gratis/trial 1 perangkat, dan
  perangkat di atas batas ditolak sampai logout atau dicabut.
- **Data terkunci:** data Karyawan, Supplier, dan Follow up lama tetap dapat
  dibaca dan diekspor saat fitur terkunci; hanya tambah/ubah data dan aksi
  premium yang diblokir.
- **Verifikasi offline:** token bertanda tangan + hitung mundur di perangkat;
  VPS tidak menyimpan data bengkel. Delta pending dikirim lebih dulu saat online
  setelah langganan berakhir, lalu pengiriman berhenti sampai aktif kembali.
- **ID owner:** 8 karakter acak (minimum 7), huruf kecil/angka tanpa `0`, `1`,
  `l`, `o`; ditampilkan sebagai kartu teks + tombol salin + QR.
- **Password/PIN karyawan:** password minimal 8 karakter, unik per owner,
  diganti saat login pertama, tanpa kedaluwarsa otomatis, reset oleh pemilik;
  tombol acak mengisi password otomatis dan tombol salin semua menyalin ID
  owner + username + password siap kirim; password hanya tampil sekali. PIN 6
  digit diatur karyawan sendiri dan direset pemilik jika lupa.
- **Aplikasi Python lama:** disimpan sebagai arsip/acuan; tidak dihapus dan tidak
  diberi fitur baru setelah Flutter stabil.
