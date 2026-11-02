# Rencana Multi-Toko dan Fitur Premium — PusatkuPOS

Status: **rencana aktif**. Fase 1 web sudah dibangun; status dan riwayat ada di
`STATUS_MULTI_TOKO_PEMANTAPAN.md`. 2026-11-03.

Produk target: **PusatkuPOS (Flutter)**. Aplikasi 2.7.0 yang berjalan sekarang
tetap **BengkelPOS Radiator** (web) dan **menerima fitur ini lebih dulu** sebagai
kanal uji web; setelah perilakunya teruji, fitur dibawa ke PusatkuPOS Flutter.

Pengujian tidak dicantumkan di sini. Seluruh skenario uji ada di
`RENCANA_PEMANTAPAN.md` dan baru dijalankan setelah fiturnya dibangun.

## Cara membaca dokumen

- **`## Keputusan (sumber kebenaran)` adalah satu-satunya tempat aturan produk
  ditetapkan.** Setiap keputusan punya ID `K-xx`.
- Bagian lain hanya **implementasi dan rujukan**: cara layar bekerja, urutan
  pekerjaan, risiko, dan kriteria penerimaan. Bagian itu tidak boleh menetapkan
  ulang angka, batas, atau kebijakan.
- Jika ada pertentangan, **bagian Keputusan yang menang**. Perbaikan aturan hanya
  dilakukan di sana, lalu bagian lain cukup menyesuaikan rujukannya.
- Tabel tier memakai `K-xx` sebagai rujukan; sel tabel sengaja pendek dan tidak
  mengulang penjelasan.
- **Rencana hanya memuat pekerjaan yang belum ada kodenya.** Jika kode sudah
  dibuat, hapus item itu dari dokumen ini. Status dan riwayat pengerjaan dicatat
  di `STATUS_MULTI_TOKO_PEMANTAPAN.md`.

## Keputusan (sumber kebenaran)

### K-01 — Produk dan kanal uji

- Target produk adalah **PusatkuPOS Flutter** untuk Android, Windows, dan macOS.
- **Web 2.7.0 (BengkelPOS Radiator) adalah kanal implementasi dan uji pertama
  untuk lingkup terbatas:** header, registry, ganti toko, isolasi data, dan
  gating/kuota dengan entitlement stub.
- **Web tidak membuktikan** akun Google, Play Billing, secure storage/Keystore,
  notifikasi sistem, kunci perangkat, relay, E2E, atau LAN. Bagian itu ditulis
  sekali di Dart setelah spesifikasi protokol dan test vector selesai.
- Web berjalan **loopback-only** (`validate_runtime`). Batas itu tidak boleh
  dilonggarkan untuk multi-device; multi-device diuji di Dart.
- **Fokus implementasi saat ini hanya web.** APK/Android dan paket platform lain
  belum dikerjakan sampai kode web stabil dan pilot lulus. Status fitur yang
  sudah ada dicatat di `STATUS_MULTI_TOKO_PEMANTAPAN.md`.
- iOS bukan target tahap ini; aturan App Store hanya disiapkan agar port nanti
  tidak merombak arsitektur.

### K-02 — Model aplikasi

- **Aplikasi utama** memuat seluruh core logic dan dipakai karyawan serta owner
  yang tidak punya karyawan.
- **Premium:** karyawan dapat memakai **hub yang sama secara bergiliran** atau
  perangkat karyawan sendiri. Perangkat karyawan mengikuti K-12.
- **Di gratis, pengguna adalah owner tunggal**; mode karyawan dan akun karyawan
  baru ada setelah premium aktif (K-03, K-07).
- **Aplikasi owner terpisah** adalah thin client premium: tanpa core logic, tanpa
  database transaksi lokal, dan tanpa replika data bengkel. Ia hanya menyimpan
  cache ringkasan/laporan bertanda tangan yang pernah diterima, menampilkan
  badge data basi saat offline, dan tidak dapat menghitung ulang atau
  bertransaksi (K-21).
- Manajemen akun, izin, lisensi, dan perangkat di aplikasi owner membutuhkan
  internet. Jika hub hilang, pemulihan hanya lewat backup lokal di perangkat
  core; cache aplikasi owner bukan cadangan.

### K-03 — Tier gratis dan premium

- **Gratis seumur hidup, tanpa batas waktu.** Aplikasi berjalan lokal seperti
  biasa, **boleh login Google** (opsional; K-07), satu toko tanpa tombol tambah
  toko (K-09), tanpa karyawan, tanpa Supplier, tanpa iklan, tanpa panggilan API
  data, dan **tanpa backup otomatis** (backup manual mengikuti K-10). Gratis
  tidak mendaftarkan perangkat dan tidak memiliki penegakan slot (K-12).
- **Baik tanpa akun maupun login Google, pengguna gratis berperan sebagai
  owner.** Kasir, ringkasan, stok, laporan, dan fitur inti terbuka; yang terkunci
  adalah akun karyawan dan multi-toko (serta fitur premium lain).
- **Follow up gratis dibatasi 20 kredit WhatsApp per `database_id`** (K-04).
  Fitur premium lain tetap terkunci; kredit tidak menambah batas waktu gratis.
- **Premium** adalah satu tier berlangganan yang memuat: multi-toko tanpa batas
  (K-09), akun karyawan untuk shift di hub maupun perangkat karyawan (K-07,
  K-12), Supplier/Follow up/WA (K-04), backup otomatis dan Telegram serta semua
  toko (K-10), lisensi (K-11), perangkat owner sesuai paket, sinkronisasi relay,
  aplikasi owner thin client, dan manajemen kunci (K-21, K-22). Tidak ada
  pembagian premium v1/v2.
- Saat fitur terkunci karena paket berakhir atau turun paket, **data lama tetap
  dapat dibaca dan diekspor**; hanya tambah/ubah data dan aksi premium yang
  diblokir. Data tidak dihapus.

### K-04 — Follow up gratis dan kuota WhatsApp

- Follow up gratis dapat dimulai sebagai **profil/database lokal** tanpa akun
  dan tanpa login. Login Google opsional kapan saja (K-07); tanpa login aplikasi
  tidak menghubungi server.
- **Gratis tidak dibatasi waktu.** Satu-satunya fitur premium yang terbuka adalah
  Follow up, dengan kuota **20 kredit WhatsApp per `database_id`**. Kredit habis
  berarti Follow up terkunci sampai berlangganan.
- Satu kredit dihitung saat tautan `wa.me` dibuka, bukan saat pesan terkirim.
  Kredit tidak dikembalikan jika pengguna membatalkan atau pesan gagal.
- Database yang sama tidak dapat mengulang kuota. Database baru mendapat ID baru
  dan 20 kredit baru. Tidak ada pengikat perangkat atau akun.
- Kuota bersifat monoton per `database_id` dan **hanya disimpan lokal**: restore
  atau salin file membawa counter yang sama.
- **Tidak ada sinkronisasi kuota ke server.** Gratis tanpa login tidak memanggil
  API sama sekali; salinan file yang membawa counter dianggap risiko yang
  diterima.
- Pengguna gratis yang **memilih login** hanya memanggil API autentikasi, bukan
  API data, relay, atau registrasi perangkat (K-07, K-12, K-16). Tanpa login,
  aplikasi tetap tidak menghubungi server.

### K-05 — ID database

- Setiap database memiliki `database_id` unik (UUIDv7/ULID) yang dibuat saat
  database dibuat dan ikut di file serta backup.
- ID ini **hanya untuk pencatatan kuota**. Ia tidak mengikat owner,
  perangkat, lisensi, atau siapa pun yang boleh membuka database.
- File database yang sama dapat dibuka user/perangkat lain dan membawa status
  kuota yang sama.

### K-06 — ID owner

- **ID owner hanya diterbitkan untuk akun premium.** Gratis memakai login Google
  tanpa ID owner dan tanpa registrasi perangkat (K-07, K-12).
- ID owner adalah **8 karakter acak (minimum 7)**, huruf kecil dan angka, tanpa
  karakter ambigu `0`, `1`, `l`, dan `o`. ID tidak berurutan dan tidak berubah
  setelah dibuat.
- ID diterbitkan saat premium aktif dan dipakai untuk **login karyawan dari
  perangkat sendiri** serta aplikasi owner. Di hub, karyawan login dengan
  username + password tanpa mengetik ID owner karena perangkat sudah terikat
  pada akun.
- ID ditampilkan sebagai kartu teks + tombol salin + **QR yang hanya berisi ID**.
- ID owner bukan rahasia. Login karyawan tetap membutuhkan username dan
  password, dengan rate limit dan lockout.

### K-07 — Akun, login, peran, dan izin tambahan

- **Login Google bersifat opsional untuk gratis dan wajib untuk premium.**
  Mode tanpa login tetap ada untuk pengguna gratis yang tidak mau akun; aplikasi
  memakai PIN perangkat dan tidak menghubungi server. Premium wajib login karena
  lisensi, perangkat, dan sinkronisasi harus dapat diverifikasi.
- **Gratis boleh login kapan saja; login tidak wajib.** Layar login menjelaskan
  manfaatnya: **upgrade mulus tanpa pindah data atau membuat akun baru** dan
  **pemulihan lisensi di perangkat baru setelah membeli**. Login tidak menambah
  batas perangkat atau fitur apa pun untuk gratis.
- Login gratis **tidak mendaftarkan perangkat dan tidak menerbitkan ID owner**.
  Server hanya memproses autentikasi; data bengkel tetap lokal dan tidak ada
  penegakan slot untuk gratis (K-12, K-13).
- **Login Google tidak mengubah peran:** gratis tetap owner tunggal. Tidak ada
  akun karyawan di gratis; akun karyawan baru dibuat setelah premium aktif.
- Akun karyawan adalah fitur premium dan dibuat pemilik: username, password,
  **satu peran dasar**, toko yang ditugaskan, dan **izin tambahan opsional**.
  Username hanya wajib unik di dalam satu owner.
- **Login karyawan di hub tidak memakai ID owner dan tidak membutuhkan
  internet:** username + password + PIN diverifikasi lokal di perangkat owner.
  **Login dari perangkat karyawan memakai tiga kolom: ID owner + username +
  password**, tanpa Google; login pertama online, lalu PIN dapat dipakai offline.
- Peran dasar menentukan menu dan aksi minimum. Izin tambahan bersifat aditif
  per akun, tidak mengubah peran dasar, tidak otomatis berlaku ke karyawan lain,
  dan tidak mengubah aturan penulis uang.
- Contoh: Budi berperan Kasir dan diberi izin tambahan opname; Budi dapat
  membuka opname, sedangkan kasir lain tanpa izin ditolak.
- **Akses khusus pemilik tidak dapat diberikan** lewat izin tambahan: kelola
  akun/perangkat, lisensi/langganan, tambah/hapus toko, ubah tarif komisi/gaji,
  dan hapus data.
- Nota, pembayaran, dan retur mengikuti **flag hub perangkat** (K-12), bukan
  status owner atau karyawan. Karyawan kasir boleh menulis uang hanya saat login
  di perangkat owner ber-flag hub; owner di perangkat non-hub tidak boleh. Izin
  tambahan tidak memberi hak menulis uang.
- Izin diperiksa di UI **dan** lapisan data/izin. Permintaan langsung yang tidak
  diizinkan tetap ditolak.
- **Sumber kebenaran akun dan izin karyawan adalah hub.** Hub memverifikasi
  login lokal tanpa server. Saat perangkat karyawan didaftarkan, salinan akun
  bertanda tangan dikirim ke server agar login pertama dari perangkat itu dapat
  diverifikasi; server tidak menerima data bengkel. Perangkat offline memakai
  izin terakhir yang sah sampai sinkronisasi berikutnya; pemilik dapat mencabut
  perangkat untuk menghentikan akses.
- Setiap perubahan izin diaudit: siapa, kapan, dan sebelum/sesudah. Riwayat
  tersedia di hub dan, untuk premium, di aplikasi owner.
- Jika izin tambahan bertabrakan dengan fitur yang terkunci paket, **paket tetap
  menang**.

### K-08 — Password dan PIN karyawan

- Password minimal 8 karakter. Pemilik boleh mengetik atau memakai **tombol acak
  berikon putar/bulat** yang mengisi 10–12 karakter (huruf besar/kecil dan
  angka, tanpa karakter ambigu).
- **Tidak ada aturan password harus berbeda antar karyawan.** Aturan itu
  membocorkan pemakaian password lain dan memaksa pemeriksaan ke semua hash.
  Keamanan berasal dari password acak, hash per pengguna, dan kewajiban ganti.
- Password awal wajib diganti saat login pertama; tidak ada kedaluwarsa
  otomatis; pemilik dapat mereset kapan saja.
- Password disimpan sebagai hash (Argon2id/bcrypt) dengan salt per pengguna,
  tidak pernah sebagai teks biasa di database.
- Password hanya ditampilkan sekali di dialog pembuatan/reset. Jika pemilik
  lupa, gunakan tombol acak untuk reset; password lama langsung tidak berlaku.
- **Tombol salin semua** menyalin teks siap kirim: ID owner (untuk login dari
  perangkat karyawan), username, password, peran, toko, dan catatan ganti
  password. Login di hub cukup memakai username + password. Teks tidak memuat
  PIN, token, atau data bengkel. Tombol hanya aktif selama password baru masih
  tampil.
- PIN 6 digit diatur karyawan sendiri, tidak sama dengan password. Jika lupa,
  pemilik mereset PIN dan karyawan membuat PIN baru.
- Pesan login gagal bersifat umum; percobaan dibatasi per username di hub dan
  per kombinasi ID owner + username pada perangkat karyawan.

### K-09 — Multi-toko

- Multi-toko adalah fitur premium dengan **jumlah toko tanpa batas**.
- Premium menjalankan semua toko di **hub** dan menyinkronkannya ke perangkat
  owner lain serta perangkat karyawan yang ditugaskan (K-12, K-21).
- Setiap toko memiliki database SQLite sendiri dan terdaftar di registry toko;
  data tidak boleh tercampur.
- Pengguna gratis hanya punya satu toko dan tidak melihat tombol tambah toko.
- Ganti toko berada di dalam panel Menu, di atas Ringkasan. Hanya pemilik yang
  dapat menambah toko; karyawan hanya melihat toko yang ditugaskan.
- Toko baru memakai database kosong, bukan salinan toko lain.
- Ganti toko dan toko yang datanya tersedia harus bekerja offline setelah login
  awal.

### K-10 — Backup dan restore

- **Backup manual gratis untuk semua tier; backup otomatis hanya premium.**
  Backup lokal terjadwal, backup Telegram/remote, dan arsip semua toko adalah
  fitur premium.
- Backup/restore adalah **jaring pengaman P0**, bukan fitur opsional; pengujiannya
  tetap dilakukan walau belum ada pengguna nyata.
- Premium menambah **backup otomatis lokal terjadwal**, **backup Telegram/remote**,
  dan **arsip semua toko**. Backup manual satu toko tetap tersedia untuk pengguna
  gratis, termasuk saat fitur premium terkunci.
- Backup semua toko memakai satu arsip dengan manifest (ID database, ID toko,
  nama, alamat, toko aktif, dan ID owner bila akun premium sudah punya),
  seluruh database, versi skema, dan versi aplikasi; setiap database dan manifest
  memiliki checksum.
- Restore bersifat all-or-nothing dengan staging; jika satu bagian gagal, data
  lama dikembalikan. Restore tidak menolak database berdasarkan ID owner atau
  `database_id`.
- Backup menyertakan data fitur yang terkunci dan **outbox pending**, tetapi
  tidak menyertakan PIN, token, atau rahasia perangkat.
- Tidak ada backup ke VPS. Telegram hanya diunggah ke chat pengguna jika fitur
  itu diaktifkan. Google Drive tidak dipakai.
- Backup lokal dan restore harus tetap berfungsi tanpa akun dan tanpa internet.

### K-11 — Lisensi dan pembayaran

- Premium dijual sebagai **langganan bulanan**, bukan sekali bayar. Harga dan
  paket mengikuti K-20; isi premium mengikuti K-21.
- Premium mencakup **perangkat owner sesuai paket** (contoh arah 2 perangkat
  owner) dan perangkat karyawan terdaftar yang tidak dihitung dalam batas owner
  (K-12).
- Server menerbitkan token bertanda tangan berisi masa aktif dan batas perangkat
  owner (K-12). Saat offline, aplikasi memakai hitung mundur lokal.
- Jam perangkat yang dimundurkan tidak boleh memperpanjang masa aktif; koreksi
  dilakukan saat online.
- Saat langganan berakhir: fitur premium terkunci, kasir dan data lokal tetap
  jalan, data lama tetap dibaca/diekspor. Jika ada delta pending, delta dikirim
  lebih dulu saat online, lalu pengiriman berhenti sampai aktif kembali.
- Android memakai Google Play Billing untuk langganan, termasuk restore,
  acknowledge, perpanjangan, dan pembatalan. Tidak ada tautan pembayaran digital
  eksternal yang melanggar kebijakan Play.
- Windows/macOS memakai penyedia yang dipilih pada tahap lisensi. Refund,
  pembatalan, atau chargeback tidak boleh menghapus data lokal.

### K-12 — Perangkat, hub, dan hak menulis uang

- **Perangkat hanya didaftarkan saat berlangganan premium.** Gratis tidak
  mendaftarkan perangkat dan tidak punya penegakan slot. Dua perangkat gratis
  dengan database terpisah tidak dapat dilarang; berbagi data antar perangkat
  itu membutuhkan relay premium.
- **Batas perangkat paket hanya menghitung perangkat owner**, termasuk hub.
  Premium: sesuai paket (contoh arah 2 perangkat owner). Perangkat karyawan
  terdaftar tidak dihitung dalam batas owner.
- **Perangkat karyawan hanya ada di premium.** Perangkat itu terdaftar pada akun
  karyawan aktif, dapat dicabut, dan **tidak boleh menjadi hub atau menulis
  nota, pembayaran, dan retur**.
- **Hak menulis uang menempel pada flag hub per toko, bukan status owner atau
  karyawan.** Karyawan dengan peran kasir yang login di perangkat owner ber-flag
  hub boleh menulis uang; owner yang login di perangkat non-hub tidak boleh.
- Setiap toko memiliki **tepat satu hub uang aktif**. Satu perangkat owner boleh
  menjadi hub untuk beberapa toko; dua perangkat tidak boleh menjadi hub untuk
  toko yang sama.
- **Hanya owner yang dapat memindahkan flag hub, dan hanya saat online.**
  Perpindahan normal menunggu hub lama mengonfirmasi; owner dapat memaksa setelah
  autentikasi ulang dengan peringatan. Delta uang dari hub lama yang belum
  terkirim setelah perpindahan dikarantina dan tidak diterapkan otomatis.
- **Perangkat hilang atau rusak:** owner login Google di perangkat baru, lalu
  mencabut perangkat lama dari aplikasi atau halaman akun web. Slot lama bebas
  dan perangkat baru dapat didaftarkan. Token lama langsung tidak berlaku;
  perangkat lama berhenti menerima delta saat kembali online. Data yang sudah
  diunduh ke perangkat lama tidak dapat dihapus dari jarak jauh.
- **Pelepasan slot mandiri dibatasi maksimal satu kali per 72 jam** agar slot
  tidak dipinjamkan bergantian. Percobaan berikutnya ditolak sampai jendela
  waktu lewat; dukungan hanya memverifikasi akun dan tidak melewati batas ini.
- Setiap perangkat terdaftar memiliki ID perangkat, kunci publik, ikatan
  owner/karyawan, toko yang ditugaskan, waktu terakhir online, dan waktu
  pencabutan.
- Menyalin database atau token tidak menambah slot. Token terikat perangkat;
  penegakan offline memakai daftar perangkat dan hitung mundur terakhir.
- Perangkat owner non-hub dan perangkat karyawan dapat menulis stok sebagai
  delta sesuai izin, tetapi tidak menulis uang.

### K-13 — Relay dan penanganan data (premium)

- Relay adalah bagian dari premium; instalasi satu perangkat tetap dapat bekerja
  tanpa relay, tetapi lisensi tetap diverifikasi.
- Server **tidak menyimpan data bengkel yang dapat dibaca**: tidak ada database
  tenant, nota/pelanggan/stok plaintext, atau backup di VPS.
- Server menyimpan metadata akun, lisensi, perangkat, kunci publik, wrapped
  store key, dan **antrean amplop delta terenkripsi end-to-end** untuk penerima
  yang sedang offline. Kunci privat hanya ada di perangkat; server tidak dapat
  membaca isi amplop atau wrapped key. **Tidak ada metadata kuota di server**
  (K-04).
- Amplop dihapus setelah semua penerima terdaftar mengonfirmasi atau setelah
  **TTL default 90 hari**. TTL adalah parameter operasional dan wajib
  didokumentasikan.
- Setelah TTL, penerima harus mengambil **snapshot terenkripsi dari hub yang
  online** atau memulihkan backup lokal. Server bukan sumber pemulihan.
- Perangkat owner kedua mengambil snapshot awal dari hub lewat relay terenkripsi
  saat hub online, atau dari backup lokal. Server tidak menyediakan snapshot
  plaintext.
- Outbox pengirim menyimpan delta sampai server mengonfirmasi; antrean server
  bukan backup dan tidak menggantikan outbox.
- API hanya relay. Free tier tidak memanggil API data.
- Metadata dan amplop tetap data pribadi; retensi dan penghapusan mengikuti
  K-18.

### K-14 — Sinkronisasi dan konflik (premium)

- Sinkronisasi adalah bagian dari premium; perangkat yang tidak terhubung tetap
  bekerja offline dengan outbox lokal.
- Setiap perangkat memiliki outbox lokal dengan status pending, retry, batching,
  dan idempotency. API mati tidak menghentikan kasir.
- Urutan lokal memakai nomor urut perangkat yang selalu naik. Urutan antar
  perangkat memakai jam logis (HLC) dan ID perangkat; jam dinding hanya untuk
  tampilan.
- Uang memakai satu hub per toko (K-12). Stok digabung sebagai delta
  append-only; opname atau koreksi stok absolut yang bertabrakan ditandai
  konflik, bukan ditimpa.
- Banyak akun (mis. 100) dapat mencatat riwayat dan menambah stok saat offline;
  data digabung setelah online. Status data belum lengkap sampai semua perangkat
  terdaftar mengirim pending dan menerima pembaruan.
- Selama pending ada, aplikasi wajib menampilkan banner, badge, dan notifikasi
  sistem berkala. Notifikasi tidak dapat dimatikan permanen; pengguna hanya
  dapat menunda.
- Pengiriman ulang tidak boleh menggandakan nota atau stok.

### K-15 — Keamanan delta dan izin (premium)

- Kunci perangkat, tanda tangan delta, dan verifikasi penerima adalah bagian dari
  premium (K-22).
- Setiap perangkat membuat pasangan kunci saat registrasi. Kunci privat disimpan
  di penyimpanan aman perangkat; kunci publik didaftarkan ke server dan
  penerima.
- Delta ditandatangani dan memuat ID perangkat, nomor urut, HLC, versi izin, dan
  hash payload.
- Penerima memverifikasi tanda tangan, memastikan perangkat terdaftar dan belum
  dicabut, serta memastikan snapshot izin bertanda tangan pemilik mengizinkan
  aksi tersebut.
- Perubahan izin dan daftar pencabutan ditandatangani pemilik. Perangkat offline
  memakai izin terakhir yang sah; delta dari perangkat yang dicabut setelah
  waktu pencabutan ditolak.
- Server dapat memverifikasi amplop, registrasi, dan pencabutan tanpa membaca
  payload. Pemeriksaan makna izin dilakukan penerima dan lapisan data.
- Perangkat yang dimodifikasi tidak dapat memalsukan perangkat lain atau
  mengubah snapshot izin tanpa merusak tanda tangan. Kompromi akun owner tetap
  risiko; aksi sensitif meminta autentikasi ulang.
- Kunci dirotasi saat registrasi ulang; perangkat hilang dicabut dan delta
  lanjutannya ditolak. Distribusi kunci, re-key, dan pemulihan mengikuti K-22.

### K-16 — Offline dan pending

- Fitur inti berjalan offline setelah aplikasi terpasang. Gratis tanpa login
  **tidak memanggil API sama sekali** (K-04). Gratis yang login hanya memanggil
  API autentikasi, bukan API data atau relay.
- Internet dibutuhkan untuk login pemilik (opsional bagi gratis, wajib bagi
  premium), aktivasi premium, login pertama karyawan, manajemen akun, dan
  sinkronisasi; bukan untuk kasir atau fitur inti. Setelah login awal, kasir
  tetap berjalan offline.
- Premium dengan satu perangkat dapat berjalan tanpa relay; relay, outbox, dan
  pending aktif saat perangkat kedua atau perangkat karyawan didaftarkan.
- Outbox pengirim tidak kedaluwarsa karena internet mati berbulan-bulan.
  Antrean relay untuk penerima mengikuti TTL K-13; setelah TTL, snapshot atau
  backup menjadi jalur pemulihan (K-22).
- Backup lokal tetap berfungsi tanpa akun dan tanpa internet.

### K-17 — Distribusi dan ukuran

- Rilis Flutter pertama memakai **satu AAB Android, satu installer Windows, dan
  satu aplikasi macOS**. Semua layout adalah kode Flutter yang dikompilasi di
  shell; tidak ada paket layout yang diunduh.
- **Ukuran aplikasi diukur sebelum rilis.** Paket per peran bukan bagian dari
  rilis pertama.
- Jika pengukuran membuktikan aset statis mendominasi ukuran, Play Asset
  Delivery (Android) atau On-Demand Resources (iOS masa depan) boleh dipakai
  **hanya untuk aset statis** seperti gambar, font, templat, dan label. Paket
  aset tidak boleh berisi layout, logika, kode, izin, atau fitur baru.
- Login fitur dasar tidak boleh bergantung pada unduhan aset. Aplikasi tetap
  offline-first setelah pemasangan.
- Tidak ada server-driven UI, dex/JAR/so dari luar Play, self-update, atau
  WebView yang mengeksekusi kode dari CDN.
- APK sideload memakai APK penuh/split; tidak ada unduhan aset on-demand.
- iOS masa depan mengikuti App Store 2.5.2: hanya aset, tanpa executable code.
- Windows memakai installer bertanda tangan; paket aset opsional (jika ada)
  harus bertanda tangan dan tidak menambah logika.

### K-18 — Data pribadi dan UU PDP

- Data yang diproses server:
  - **Gratis yang login:** identitas Google/email dan sesi autentikasi saja;
    tanpa ID owner, tanpa ID perangkat, tanpa data bengkel.
  - **Premium:** akun owner, ID owner, metadata akun karyawan, ID perangkat,
    kunci publik, wrapped store key, lisensi, amplop relay terenkripsi, dan log
    dukungan terbatas.
  - **Kuota gratis tidak dikirim ke server** (K-04, K-12).
- Tujuan: autentikasi, lisensi, sinkronisasi, keamanan, dan dukungan. Tidak ada
  penjualan data, iklan, atau pembacaan data bengkel. Identitas pengguna gratis
  tidak dipakai untuk pemasaran.
- Pemberitahuan privasi dan dasar pemrosesan disampaikan **saat pembuatan akun,
  termasuk akun gratis**, serta ditautkan dari aplikasi dan listing toko aplikasi.
  Persetujuan dicatat sebelum akun aktif.
- Retensi: metadata akun selama akun aktif dan sesuai kewajiban hukum; amplop
  relay mengikuti TTL; log dibatasi; penghapusan akun menghapus metadata dan
  amplop milik akun.
- Hak pengguna: akses/ekspor, koreksi, dan penghapusan. Hapus akun tersedia di
  aplikasi dan tautan web **untuk semua akun, termasuk akun gratis**; konfirmasi
  menjelaskan apa yang dihapus dan apa yang tetap ada di perangkat pengguna.
  Menghapus akun gratis menghapus identitas Google dan sesi; tidak ada ID owner
  atau registrasi perangkat yang perlu dihapus. Menghapus akun premium juga
  menghapus ID owner, registrasi perangkat, kunci publik/wrapped key, dan
  amplop. Data bengkel lokal tidak tersentuh.
- Prosedur insiden dan kontak privasi disiapkan. Jika diwajibkan, DPO ditunjuk.
- Transfer lintas negara memakai pengaman yang sah. **Kajian hukum UU PDP
  dilakukan sebelum rilis**, bukan hanya mengandalkan aturan Play/App Store.
- Deklarasi Data Safety Play dan App Privacy iOS harus sesuai perilaku nyata.

### K-19 — Aplikasi Python lama

- Setelah Flutter stabil, aplikasi Python lama **disimpan** sebagai arsip,
  acuan perilaku, dan jalur rollback.
- Tidak diberi fitur baru, tidak dihapus, dan tidak ada migrasi data paksa.

### K-20 — Harga dan unit economics

- Harga final ditetapkan setelah menghitung biaya per pengguna aktif: komisi
  Play Billing, antrean relay terenkripsi, re-key dan dukungan kunci, dukungan,
  pajak, biaya pembayaran, dan refund.
- **Akun gratis yang login tetap menimbulkan biaya**: autentikasi kecil, tetapi
  dukungan dan penghapusan akun ikut dihitung. Login gratis tidak menambah
  pendapatan, jadi biayanya harus ditekan dan dipantau (K-07).
- **Harga premium dihitung untuk satu tier**, bukan versi terpisah. Paket boleh
  berbeda pada batas perangkat owner, tetapi fitur premium dan janji sinkronisasi
  tetap satu. Arah awal Rp10.000/bulan untuk 2 perangkat owner adalah arah paket
  premium, bukan janji final.
- Halaman harga wajib menjelaskan batas perangkat owner, perangkat karyawan, dan
  isi premium (K-12, K-21) agar tidak menimbulkan salah paham.

### K-21 — Premium tunggal

- **Hanya ada dua tier produk: Gratis dan Premium.** Tidak ada premium v1 atau
  premium v2.
- **Premium** mencakup seluruh fitur berbayar: multi-toko tanpa batas (K-09),
  akun karyawan di hub dan perangkat karyawan (K-07), Supplier/Follow up/WA
  (K-04), backup Telegram dan arsip semua toko (K-10), lisensi (K-11), perangkat
  owner sesuai paket, sinkronisasi relay, aplikasi owner thin client, dan
  manajemen kunci (K-12, K-13, K-22).
- Fitur premium boleh dirilis **bertahap di balik flag** untuk pengujian, tetapi
  tier yang dijual tetap satu dan tidak diberi nama versi. Pengguna premium tidak
  membeli "paket sync" terpisah.
- **LAN/hub lokal bukan bagian premium saat ini.** Jika nanti dibutuhkan, LAN
  menjadi keputusan, pengujian, dan pekerjaan terpisah.
- Paket harga boleh membedakan **batas perangkat owner**, bukan fitur inti
  premium. Perangkat karyawan terdaftar tidak dihitung dalam batas owner.
- Premium tidak boleh dibangun sebelum pilot membuktikan kebutuhan dan
  spesifikasi protokol + test vector selesai.

### K-22 — Manajemen kunci, re-key, dan pemulihan snapshot

- **Hierarki kunci:**
  - kunci tanda tangan owner (Ed25519) untuk izin, pencabutan, dan daftar
    perangkat;
  - kunci data per toko (X25519 + AEAD) untuk delta dan snapshot;
  - pasangan kunci per perangkat untuk menandatangani delta dan menerima wrapped
    store key.
- Kunci privat tidak pernah dikirim ke server. Server hanya menyimpan kunci
  publik, wrapped store key, dan amplop terenkripsi; server tidak dapat membuka
  wrapped key atau payload.
- **Distribusi:** perangkat baru membuat pasangan kunci dan mendaftar; owner/hub
  menyetujui lalu membungkus kunci toko yang ditugaskan ke kunci publik
  perangkat. Perangkat karyawan hanya menerima kunci toko yang ditugaskan.
- **Perangkat owner kedua:** menerima snapshot awal dan wrapped key dari hub
  lewat relay saat hub online, atau dari backup lokal. Tanpa hub dan tanpa
  backup, perangkat baru tidak dapat membuka data lama.
- **Pencabutan dan re-key:** server langsung menolak amplop dari perangkat
  dicabut; hub melakukan re-key kunci toko dan membungkusnya ke perangkat
  tersisa. Perangkat dicabut tidak menerima ciphertext baru. Data yang sudah ada
  di perangkat dicabut tidak dapat dihapus dari jarak jauh; re-key dan audit
  wajib.
- Re-key menunggu hub online. Sampai re-key selesai, delta sensitif ditahan di
  outbox hub dan tidak dikirim dengan kunci lama.
- **Kunci owner:** disimpan di secure storage dan dicadangkan terenkripsi dengan
  kode pemulihan yang ditampilkan sekali. Server boleh menyimpan blob
  terenkripsi, tetapi tidak dapat membukanya. Login Google ulang tidak
  menggantikan kode pemulihan.
- Jika kunci owner dan kode pemulihan hilang, tenant tidak dapat menerbitkan izin
  atau pencabutan baru. Data lokal tetap dapat dibaca/diekspor; pemulihan
  lintas-perangkat memerlukan backup lokal dan akun owner baru. Dukungan tidak
  dapat memulihkan kunci.
- **Snapshot + outbox:** snapshot diterapkan secara atomik, lalu outbox lokal
  diputar ulang di atasnya. ID yang sudah ada dideduplikasi, konflik ditandai,
  dan delta yang belum terkirim tidak dibuang. Jika kunci toko berubah, outbox
  dienkripsi ulang dengan kunci baru sebelum dikirim.
- Kunci dirotasi saat registrasi ulang, perangkat hilang, atau pencabutan; kunci
  lama tidak dipakai untuk delta baru.

## Matriks tier

Angka dan aturan rinci ada di keputusan yang dirujuk; sel sengaja ringkas.

| Area | Gratis | Premium | Rujukan |
| --- | --- | --- | --- |
| Model | Seumur hidup, tanpa batas waktu | Langganan bulanan | K-03, K-11, K-21 |
| Login Google | Opsional, kapan saja | Wajib | K-07 |
| Peran | Owner (tanpa akun atau login) | Owner + akun karyawan | K-02, K-03, K-07 |
| ID owner | Tidak | Ya | K-06 |
| Toko | 1, tanpa tombol tambah | Tanpa batas | K-09 |
| Kasir, stok, pelanggan, unit, jasa, laporan | Ya, dijalankan owner | Ya, owner atau karyawan | K-03, K-07 |
| Backup manual | Ya | Ya | K-10 |
| Backup otomatis lokal terjadwal | Tidak | Ya | K-10 |
| Backup Telegram/remote | Tidak | Ya | K-10 |
| Backup semua toko | Tidak | Ya | K-10 |
| Karyawan | Tidak | Ya, hub atau perangkat sendiri | K-03, K-07, K-21 |
| Supplier | Tidak | Ya | K-03 |
| Follow up | Ya, 20 kredit WA | Ya | K-03, K-04 |
| Tombol WhatsApp | 20 kredit | Tanpa batas | K-04 |
| Akun karyawan + izin tambahan | Tidak | Ya | K-07, K-08 |
| Login karyawan | Tidak | Lokal di hub; tiga kolom di perangkat | K-07 |
| Perangkat owner | Tidak didaftarkan | Sesuai paket (contoh 2) | K-12 |
| Perangkat karyawan | Tidak | Terdaftar; tidak dihitung | K-12, K-21 |
| Multi-device owner | Tidak | Ya | K-11, K-12, K-21 |
| Mode karyawan | Tidak | Ya | K-02, K-07 |
| Aplikasi owner terpisah | Tidak | Ya | K-02, K-21 |
| Sinkronisasi relay | Tidak | Ya | K-13, K-14, K-21 |
| LAN/hub lokal | Tidak | Tidak; keputusan terpisah | K-21 |
| Iklan | Tidak ada | Tidak ada | K-03 |
| Panggilan API | Tanpa login: tidak ada; login: auth saja | Lisensi; relay sesuai perangkat | K-04, K-07, K-13, K-16 |
| Data karyawan di server | Tidak | Ya, untuk login perangkat | K-07, K-18 |

## Implementasi fitur premium

### Karyawan dan izin

- Akun karyawan hanya ada di premium; di gratis pengguna tetap owner tunggal.
  Layar karyawan, peran, dan izin tidak muncul sampai langganan aktif.
- Data karyawan mencakup identitas, peran, penugasan toko, komisi, gaji, absensi,
  status pengerjaan, catatan, penyelesaian servis, dan performa.
- Katalog peran dan izin ditetapkan saat implementasi; contoh izin tambahan:
  opname, stok masuk/keluar, lihat laporan, baca Supplier, baca Follow up, dan
  cetak laporan.
- Layar pemilik menampilkan peran dasar, izin tambahan, toko yang ditugaskan, dan
  riwayat perubahan per karyawan.
- Aplikasi utama menampilkan menu sesuai peran + izin. Menu owner tidak muncul di
  mode karyawan; permintaan langsung tetap ditolak di lapisan data.
- **Di hub:** karyawan login bergiliran dengan username + password + PIN;
  absensi, status pengerjaan, dan komisi tercatat per akun. Izin berlaku lokal.
- **Di perangkat karyawan:** perubahan izin dikirim bertanda tangan ke perangkat
  (K-15); perangkat offline memakai izin terakhir yang sah sampai sinkron.
  Akun dan izin bersumber dari hub; salinan bertanda tangan dipakai untuk login
  pertama di perangkat.
- Jika paket tidak aktif, fitur premium terkunci walau izin tambahan diberikan
  (K-07).

### Supplier, Follow up, dan WhatsApp

- Supplier dan Follow up adalah fitur premium; data lama tetap dapat dibaca saat
  fitur terkunci (K-03).
- Tombol WA di Follow up memotong kuota hanya untuk pengguna gratis (K-04);
  setelah 20 kredit habis, tombol dan fitur premium terkunci sampai berlangganan.
  Premium tidak memotong kuota.
- Aplikasi menampilkan sisa kuota dan peringatan sebelum habis.
- Kuota dihitung saat tautan `wa.me` dibuat; aplikasi tidak dapat memastikan
  pesan benar-benar terkirim.

### Backup dan restore

Mengikuti K-10. Detail implementasi:

- Backup manual tetap tersedia saat langganan berakhir atau fitur premium
  terkunci.
- Arsip semua toko berisi manifest, seluruh database, checksum, versi skema, dan
  versi aplikasi. Restore memakai staging dan all-or-nothing.
- Backup menyertakan outbox pending dan data fitur terkunci; PIN, token, dan
  rahasia perangkat diredaksi.
- Restore tidak menolak database berdasarkan ID owner atau `database_id`.
- Backup otomatis lokal dan Telegram hanya aktif di premium; keduanya memakai
  arsip yang sama, dengan batas ukuran file untuk Telegram.
- Ekspor Excel/CSV dapat berisi subfolder atau workbook per toko dalam satu ZIP.
- Tidak ada upload ke VPS; Telegram hanya jika pengguna mengaktifkannya.

## Implementasi multi-toko

### Registry dan database per toko

- Registry menyimpan daftar toko, nama, alamat, ID database, dan toko aktif.
- Setiap toko memakai database SQLite terpisah; toko baru dimulai kosong.
- Registry rusak atau toko hilang harus dapat dipulihkan tanpa mencampur data
  toko lain.
- Backup semua toko memakai manifest registry (K-10).

### Ganti toko di Menu

- Tombol/dropdown **Ganti toko** berada di dalam panel Menu, di bagian paling
  atas dan tepat di atas Ringkasan; bukan tombol terpisah.
- Gratis: panel hanya menampilkan toko aktif tanpa tombol tambah; ajakan upgrade
  boleh ditampilkan.
- Premium: panel menampilkan daftar toko dengan penanda aktif dan tombol
  **Tambah toko** di bagian bawah.
- Menambah toko membuka form nama dan alamat; setelah dibuat, toko langsung dapat
  dipilih. Hanya pemilik yang boleh menambah toko (K-09).
- Jika ada perubahan belum disimpan, minta konfirmasi sebelum berganti.
- Ganti toko bekerja offline untuk toko yang datanya tersedia di perangkat.
- Di layar sempit, tombol tetap di dalam panel Menu, di atas Ringkasan, dan tidak
  menutupi navigasi.

### Header bengkel

- Header memakai dua baris:

  ```text
  Nama bengkel                         [printer]
  Alamat bengkel
  ```

- Baris pertama berisi nama bengkel; tombol/ikon printer berada di kanan pada
  baris yang sama.
- Baris kedua selalu alamat bengkel, bukan judul halaman. Jika alamat kosong,
  tampilkan “Alamat belum diisi”.
- Nama dan alamat mengikuti toko aktif; judul halaman seperti “Ringkasan” tetap
  di area konten.
- Nama panjang dipotong atau dibungkus tanpa menutupi tombol printer; alamat
  aman di area status bar/notch.
- Header tetap tampil offline dan tidak memanggil API.

### Isolasi data

- Nota, stok, pelanggan, karyawan, dan laporan tidak boleh tercampur antar toko.
- Karyawan hanya melihat toko yang ditugaskan.
- Data toko tidak ikut ke perangkat pengguna gratis atau akun lain.

## Implementasi akun, login, dan peran

### ID owner

- ID owner dibuat sekali saat **premium aktif**, unik global, dan tidak berubah
  (K-06). Gratis tidak menerima ID owner.
- Ditampilkan sebagai kartu teks besar + tombol salin + QR berisi ID saja.
- ID owner bukan rahasia; login karyawan tetap membutuhkan username dan
  password.
- Di hub, ID owner tidak perlu diketik karena perangkat sudah terikat akun.

### Login pemilik dan karyawan

- **Tanpa login** adalah jalur default untuk pengguna gratis: lokal, satu
  perangkat, tanpa internet, memakai PIN perangkat (K-07).
- **Login Google opsional untuk gratis (boleh kapan saja) dan wajib untuk
  premium.** Layar login menampilkan manfaatnya: upgrade mulus tanpa pindah data
  dan pemulihan lisensi di perangkat baru (K-07).
- Login gratis **tidak mendaftarkan perangkat**; server hanya menerima
  autentikasi dan data bengkel tetap lokal (K-07, K-12).
- **Di hub:** karyawan login dengan username + password + PIN, diverifikasi lokal
  tanpa internet dan tanpa ID owner.
- **Di perangkat karyawan:** login memakai ID owner + username + password, tanpa
  Google; login pertama membutuhkan internet, lalu PIN dapat dipakai offline.
- Perangkat karyawan terdaftar per akun dan hanya menerima kunci toko yang
  ditugaskan (K-22); perangkat itu tidak menulis uang (K-12).
- Setelah login premium, perangkat menyimpan token perangkat di penyimpanan
  aman; pemakaian berikutnya dapat memakai PIN perangkat saat offline.
- Pesan login gagal bersifat umum dan percobaan dibatasi (K-08).

### Membuat dan membagikan akun

- Form akun berisi username, password (diketik atau tombol acak), peran dasar,
  toko yang ditugaskan, dan izin tambahan.
- Di samping kolom password ada tombol acak berikon putar/bulat. Password hasil
  tombol acak langsung memenuhi K-08; pemilik tidak perlu mengetik.
- Tombol yang sama dipakai untuk reset; password lama langsung tidak berlaku.
- Tombol **salin semua** menyalin teks siap kirim:

  ```text
  PusatkuPOS — akun karyawan
  ID owner: 398urw7x
  Username: budi
  Password: K7mRq2Tn
  Peran: Kasir
  Toko: Bengkel Pusat
  Ganti password saat login pertama.
  ```

- Teks salin semua tidak memuat PIN, token, atau data bengkel. Password hanya
  tampil sekali; tombol salin hanya aktif selama password baru tampil.
- QR karyawan tetap hanya berisi ID owner; password tidak masuk QR atau tautan.
- Pemilik dapat mereset password, menonaktifkan akun, dan mencabut perangkat
  karyawan dari aplikasi owner.

### Logout

- Logout meminta konfirmasi, menghapus sesi dan token perangkat, lalu kembali ke
  pilihan akses.
- Logout tidak menghapus database, nota, stok, backup, atau PIN lokal.
- Setelah logout, sinkronisasi perangkat itu berhenti sampai login kembali.
- Jika aplikasi dihapus, data hanya dapat dipulihkan dari backup lokal/Telegram;
  server tidak menyimpan salinan data bengkel yang dapat dibaca.

## Implementasi lisensi, perangkat, dan pembayaran

- Server menerbitkan token lisensi bertanda tangan berisi masa aktif dan batas
  perangkat owner (K-11). Batas perangkat mengikuti paket premium.
- Aplikasi memakai hitung mundur lokal saat offline; jam mundur tidak
  memperpanjang masa aktif dan dikoreksi saat online.
- Perangkat owner dan karyawan didaftarkan terpisah (K-12). Perangkat karyawan
  tidak memakai slot owner, tidak menjadi hub, dan tetap dapat dicabut.
- Perangkat hilang atau rusak dilepas dengan login Google di perangkat baru lalu
  mencabut perangkat lama dari aplikasi atau halaman akun web; pelepasan mandiri
  dibatasi satu kali per 72 jam (K-12).
- Hak menulis uang mengikuti flag hub per toko, bukan status owner/karyawan
  (K-12). Hanya perangkat owner yang dapat menjadi hub; perangkat non-hub dan
  perangkat karyawan hanya dapat menulis stok sesuai izin.
- Batas perangkat dapat berubah lewat rilis aplikasi, bukan pengaturan pengguna.
- Android memakai Play Billing untuk langganan; Windows/macOS memakai penyedia
  yang dipilih pada tahap lisensi.
- Harga final menunggu unit economics (K-20); halaman harga menjelaskan batas
  perangkat owner dan kebijakan perangkat karyawan.

## Implementasi relay dan sinkronisasi (premium)

Relay dan sinkronisasi adalah bagian dari premium (K-21). Instalasi satu
perangkat dapat berjalan tanpa relay, tetapi lisensi tetap diverifikasi.

### Relay dan antrean

- API adalah relay: metadata akun/lisensi/perangkat, kunci publik, wrapped store
  key, dan amplop delta terenkripsi untuk penerima offline (K-13, K-22).
- Server tidak memegang kunci privat dan tidak dapat membaca isi amplop atau
  wrapped key.
- Amplop dihapus setelah semua penerima mengonfirmasi atau setelah TTL
  mengikuti K-13. Setelah TTL, penerima mengambil snapshot terenkripsi dari hub
  yang online atau memulihkan backup, lalu memutar ulang outbox lokal (K-22).
- Perangkat owner kedua mengambil snapshot awal dan wrapped key dari hub lewat
  relay terenkripsi saat hub online, atau dari backup lokal.
- Outbox pengirim tetap menyimpan delta sampai server mengonfirmasi; antrean
  server bukan backup.
- Jika hub rusak atau hilang, pemulihan hanya lewat backup lokal; cache aplikasi
  owner bukan cadangan.

### Outbox dan penggabungan

- Setiap perubahan masuk outbox lokal dengan status pending; saat online, antrean
  dikirim berurutan sesuai nomor urut perangkat.
- Item yang sudah terkirim ditandai dan tidak dikirim ulang; pengiriman ulang
  harus idempotent (K-14).
- Saat internet mati, transaksi tetap berjalan dan delta menunggu.
- Urutan antar perangkat memakai HLC + ID perangkat; jam dinding hanya untuk
  tampilan.
- Stok digabung sebagai delta append-only; opname atau koreksi absolut yang
  bertabrakan ditandai konflik.
- Status data berubah menjadi lengkap setelah semua perangkat terdaftar mengirim
  pending dan menerima pembaruan.

### Banyak akun dan pending jangka panjang

- Satu owner dapat memiliki banyak akun karyawan (mis. 100). Setiap akun dapat
  memakai perangkat dan outbox sendiri; data antar owner tetap terpisah oleh ID
  owner. Akun yang hanya memakai hub login bergiliran tanpa perangkat sendiri.
- Perangkat karyawan terdaftar per akun, tidak memakai slot owner, dan tidak
  menjadi hub, mengikuti K-12.
- Outbox pengirim tidak kedaluwarsa karena internet mati berbulan-bulan.
- Selama pending ada, aplikasi menampilkan banner tetap berisi jumlah delta dan
  usia data terlama, badge menu sinkronisasi, dan notifikasi sistem berkala.
- Notifikasi tidak dapat dimatikan permanen selama pending ada; pengguna hanya
  dapat menunda. Notifikasi memakai mekanisme lokal dan tetap muncul tanpa
  internet.
- Setelah pending terkirim dan semua perangkat terdaftar melapor, status berubah
  menjadi tersinkron dan notifikasi berhenti.

### Keamanan delta dan kunci

- Setiap perangkat memiliki pasangan kunci (K-15, K-22); kunci privat di
  penyimpanan aman, kunci publik didaftarkan.
- Delta, perubahan izin, dan daftar pencabutan ditandatangani.
- Penerima menolak tanda tangan salah, perangkat tidak terdaftar, perangkat
  dicabut, atau izin yang tidak sah.
- Server memverifikasi amplop dan status perangkat tanpa membaca payload;
  penerima memeriksa makna izin.
- Perangkat yang dimodifikasi tidak dapat memalsukan perangkat lain atau
  mengubah snapshot izin tanpa merusak tanda tangan.
- Perangkat hilang dicabut; delta setelah waktu pencabutan ditolak. Re-key
  dijalankan ke perangkat tersisa dan delta sensitif ditahan sampai selesai
  (K-22).

## Implementasi distribusi dan ukuran

Mengikuti K-17. Detail implementasi:

- Android memakai AAB lewat Play App Signing; APK sideload memakai APK
  penuh/split tanpa unduhan aset on-demand.
- Windows memakai installer bertanda tangan; paket aset opsional, jika ada,
  harus bertanda tangan.
- iOS masa depan memakai aset/ODR tanpa executable code.
- Ukuran diukur pada build rilis; hasil pengukuran menentukan perlu/tidaknya
  paket aset statis.
- Tidak ada server-driven UI, WebView yang mengeksekusi kode dari CDN, atau
  self-update.

## Kepatuhan Play, App Store, dan data pribadi

- Android dirilis sebagai AAB lewat Play dengan Play App Signing; target API
  mengikuti syarat Play terbaru.
- Langganan digital di Android memakai Play Billing, termasuk restore,
  acknowledge, perpanjangan, dan pembatalan (K-11).
- Sediakan hapus akun di aplikasi dan tautan web; konfirmasi menjelaskan data
  lokal dan metadata server yang dihapus (K-18).
- Data safety Play dan App Privacy iOS mendeklarasikan akun, lisensi, perangkat,
  kunci publik/wrapped key, dan amplop relay terenkripsi; tidak ada data bengkel
  atau kuota gratis yang dapat dibaca server.
- Privacy policy tersedia di aplikasi dan listing toko aplikasi.
- Izin Android/iOS (printer, file, notifikasi, Bluetooth) diminta saat
  dibutuhkan dengan alasan jelas.
- iOS masa depan mengikuti App Store 2.5.2: tidak ada unduhan executable code;
  paket aset tidak menambah fitur.
- Kepatuhan UU PDP mengikuti K-18; kajian hukum dilakukan sebelum rilis.

## Arsitektur

```text
Gratis
        ├─ SQLite lokal (database_id) + kuota lokal
        ├─ Registry toko (1 toko)
        ├─ Peran owner: kasir, ringkasan, stok, laporan
        ├─ PIN perangkat atau login Google (autentikasi saja)
        └─ Tanpa registrasi perangkat, tanpa relay

Premium (satu tier)
        ├─ Hub: SQLite per toko + registry
        ├─ Perangkat owner sesuai paket + perangkat karyawan
        ├─ Satu hub uang per toko; perangkat non-hub menulis stok saja
        ├─ Karyawan: login lokal di hub; tiga kolom di perangkat sendiri
        ├─ Backup otomatis/Telegram/semua toko + aplikasi owner thin client
        └─ API relay (HTTPS)
                ├─ akun owner + ID owner, lisensi, daftar perangkat
                ├─ akun karyawan (username, hash password, peran, izin)
                ├─ kunci publik + wrapped store key (tanpa kunci privat)
                ├─ amplop delta terenkripsi E2E (TTL, hapus setelah ack)
                └─ forward delta dan ringkasan berdasarkan ID owner
```

- **Client:** web 2.7.0 hanya untuk lingkup K-01; target PusatkuPOS Flutter +
  SQLite. Aplikasi owner adalah thin client premium tanpa database transaksi
  (K-02, K-21).
- **API:** FastAPI sebagai relay premium. Server hanya menyimpan akun, ID owner,
  lisensi, perangkat, kunci publik/wrapped key, dan amplop terenkripsi; bukan
  data bengkel yang dapat dibaca (K-13, K-22).
- **Auth:** mengikuti K-07. Tanpa login untuk pemakaian lokal; Google opsional
  untuk gratis kapan saja dan wajib untuk premium. Login karyawan di hub memakai
  username + password + PIN; login dari perangkat karyawan memakai ID owner +
  username + password. Token perangkat premium disimpan aman.
- **Kuota:** mengikuti K-04; hanya lokal per `database_id`, tanpa sinkronisasi
  server. Gratis tanpa login tidak memanggil API; login gratis hanya memanggil
  autentikasi.
- **Lisensi:** langganan bulanan per paket premium; batas perangkat owner sesuai
  paket; token bertanda tangan; kegagalan API tidak mengunci kasir lokal (K-11,
  K-12, K-21).
- **Pembayaran:** Play Billing (Android), penyedia Windows/macOS ditentukan pada
  tahap lisensi. Tidak ada pembelian sekali bayar (K-11).
- **Keamanan delta:** tanda tangan per perangkat, verifikasi penerima, daftar
  pencabutan, wrapped store key, dan re-key (K-15, K-22).

## Alur gratis dan langganan

1. Pengguna memakai gratis seumur hidup sebagai **owner tunggal** dengan membuat
   database lokal; tidak perlu akun, login, atau Google. Login boleh dilakukan
   kapan saja tetapi tidak wajib dan tidak mengubah peran. Kuota mengikuti K-04.
2. Fitur inti terbuka untuk owner; Follow up terbuka dengan 20 kredit WA; akun
   karyawan, multi-toko, dan fitur premium lain terkunci (K-03/K-04).
3. Setiap klik WA dari Follow up mengurangi kredit (K-04).
4. Saat kredit habis, Follow up terkunci; pilihan langganan muncul. Fitur inti
   gratis tetap berjalan tanpa batas waktu.
5. Sebelum membeli, pengguna login Google (wajib untuk premium) dan menerima ID
   owner (K-06/K-07); jika sudah login sebagai pengguna gratis, akun yang sama
   dipakai tanpa membuat akun baru.
6. Langganan premium membuka fitur premium dan perangkat owner sesuai paket
   (K-11/K-12/K-21).
7. Data lokal tetap tersimpan; tidak ada data yang dihapus saat gratis atau saat
   langganan berakhir.
8. Jika langganan berakhir, perilaku mengikuti K-03/K-11.
9. Perpanjangan mengaktifkan kembali fitur premium tanpa menghapus data lokal
   (K-11).

## Urutan pekerjaan

Fase disusun dari mudah ke sulit. Dependensi yang tidak bisa ditawar tetap menjadi
gerbang: pilot sebelum akun/lisensi, dan spesifikasi protokol sebelum kode sync.
Estimasi adalah perkiraan kasar untuk satu pengembang setelah prasyarat selesai.
**Fokus saat ini adalah pemantapan web dan pilot; APK/Android dan paket platform
lain belum dikerjakan sampai kode web stabil dan pilot lulus.**

| Fase | Pekerjaan | Kanal | Kesulitan | Estimasi | Prasyarat |
| --- | --- | --- | --- | --- | --- |
| G | **Pilot 1–3 bengkel nyata** | Web | **Gerbang** | 2–4 minggu | Pemantapan web |
| 2 | Port Flutter inti + ukur ukuran (fondasi wajib; APK/Android belum) | Dart | Sedang–Sulit | 30–45 hari | Pilot |
| 3 | Akun owner + Google + secure storage; akun karyawan + peran/izin/password/PIN + login lokal hub; lisensi + Play Billing + hitung mundur + ID owner + registrasi/pencabutan perangkat | Dart | Sedang–Sulit | 21–32 hari | Fase 2 |
| 4 | Backup manual/otomatis lokal/Telegram/semua toko + restore; rilis premium tahap hub + QA | Dart | Sulit | 15–25 hari | Fase 3 |
| 5 | Spesifikasi protokol sync/kripto + test vector | Dokumen | Sulit | 8–12 hari | Fase 4 |
| 6 | Sync multi-device + E2E + kunci + antrean + snapshot + batching + notifikasi | Dart | Sangat sulit | 40–60 hari | Fase 5 |
| 7 | Perangkat karyawan + aplikasi owner thin client | Dart | Sangat sulit | 20–30 hari | Fase 6 |
| 8 | LAN/hub lokal (opsional) | Dart | Sangat sulit | TBD | Keputusan baru |

Perkiraan kasar satu pengembang: **premium tahap hub dan spesifikasi protokol
(Fase 2–5) sekitar 80–130 hari** dan **sinkronisasi/perangkat (Fase 6–7) sekitar
60–90 hari**; total **140–220 hari kerja** di luar pilot 2–4 minggu, desain, QA
lanjutan, dan buffer.

Catatan urutan:

- **Pilot adalah gerbang wajib** sebelum Fase 2 dan seterusnya. Jika pilot gagal,
  perbaiki inti dan jangan mulai akun, lisensi, atau relay.
- Fase 2 adalah fondasi lintas platform, bukan fitur premium. Port inti dan ukur
  dulu; paket APK/Android belum dikejar sampai hasilnya stabil (K-17).
- Fase 3–4 adalah premium tahap hub: satu perangkat owner, multi-toko, karyawan
  shift di hub, lisensi, dan backup. Relay dan perangkat karyawan menyusul, tetapi
  tier yang dijual tetap satu.
- Fase 5 menulis protokol, format pesan, urutan HLC, tanda tangan, wrapped key,
  snapshot, dan test vector. Tidak ada implementasi Python untuk sync/kripto.
- Fase 6–7 melengkapi premium dengan sync dan perangkat karyawan; tidak ada tier
  baru.
- Fase 8 tidak dikerjakan kecuali ada keputusan baru dan uji terpisah.

Urutan wajib: pilot sebelum akun/lisensi;
spesifikasi protokol sebelum kode sync/kripto Dart; port Flutter dan ukuran
sebelum rilis premium tahap hub; backup satu toko stabil sebelum backup semua
toko; sync lulus uji sebelum perangkat karyawan; tidak ada rilis UI kosong.

## Kriteria selesai

Kriteria ini adalah gerbang penerimaan, bukan penetapan aturan. Nilai dan
kebijakan mengikuti `K-xx`; skenario rinci ada di `RENCANA_PEMANTAPAN.md`
bagian 7.

- **K-01:** web hanya membuktikan lingkup header/registry/ganti toko/gating;
  Play Billing, secure storage, kunci, notifikasi, dan relay diuji di Dart.
- **K-02/K-21:** hanya ada Gratis dan Premium; premium mencakup hub, sync, dan
  aplikasi owner tanpa tier versi terpisah.
- **K-03/K-11:** tier, gating, langganan, data terkunci, dan perilaku saat
  langganan berakhir lulus uji.
- **K-04/K-05:** gratis tanpa API data (login hanya autentikasi), kuota Follow up
  lokal, dan `database_id` lulus uji.
- **K-06/K-07/K-08:** ID owner, login, peran + izin tambahan, password/PIN,
  audit, dan pencabutan lulus uji.
- **K-09/K-10:** multi-toko, isolasi, backup, restore, dan rollback lulus uji;
  backup/restore adalah P0.
- **K-12:** batas perangkat owner/karyawan, flag hub, hak menulis uang, dan
  pencabutan lulus uji.
- **K-13/K-14/K-15/K-16:** relay terenkripsi, TTL/snapshot, sinkronisasi,
  konflik, tanda tangan delta, dan pending lulus uji.
- **K-17:** satu paket per platform, ukuran terukur, tanpa paket layout/kode;
  opsi paket aset statis diuji jika dipakai.
- **K-18/K-19/K-20:** privacy/UU PDP, hapus akun, arsip Python, dan unit
  economics lulus.
- **K-22:** distribusi kunci, re-key, pemulihan kunci owner, dan replay
  snapshot+outbox lulus uji.
- **Pilot:** 1–3 bengkel nyata memakai alur gratis sebelum akun/lisensi/relay;
  hasilnya dicatat dan keputusan lanjut/tidak lanjut eksplisit.
- Tidak ada kontradiksi terbuka antara implementasi dan `K-xx`.

## Risiko

- Isolasi data lemah dapat mencampur nota/stok antar toko.
- Registry rusak dapat menyembunyikan toko; butuh pemulihan aman.
- Web loopback-only tidak dapat membuktikan multi-device, secure storage,
  Play Billing, notifikasi, atau relay; jangan menganggap web sebagai bukti
  kesiapan sync premium.
- Premium dirilis bertahap di balik flag; pengguna dapat salah mengira tahap
  hub sebagai tier berbeda. Halaman harga wajib menegaskan hanya ada Gratis dan
  Premium.
- Protokol sync/kripto yang ditulis dua kali (Python lalu Dart) berisiko
  berbeda; spesifikasi + test vector wajib selesai sebelum kode Dart.
- Restore semua toko memperbesar dampak kegagalan; wajib all-or-nothing.
- Arsip multi-toko cepat membesar dan dapat melewati batas Telegram.
- Aplikasi owner thin client bergantung pada ringkasan bertanda tangan; saat
  offline hanya menampilkan cache basi dan tidak dapat menghitung ulang.
- Jika hub hilang, pemulihan hanya lewat backup lokal; cache aplikasi owner
  bukan cadangan.
- Login Google menambah ketergantungan jaringan; kasir tetap offline setelah
  login awal.
- Login gratis membuat pengguna menyerahkan identitas; manfaatnya harus jelas
  (upgrade mulus dan pemulihan lisensi) dan login tetap opsional (K-07).
- Pengguna gratis tidak dapat dibatasi slot perangkatnya karena salin file
  database tidak bisa dicegah; ini risiko yang diterima, bukan alasan memaksa
  login atau mendaftarkan perangkat gratis (K-12).
- Backup otomatis hanya untuk premium; pengguna gratis yang tidak pernah
  menjalankan backup manual kehilangan jaring pengaman. Aplikasi wajib mengingatkan
  backup manual secara berkala.
- Gating premium yang salah dapat mengunci pengguna gratis dari toko tunggal
  atau membuka multi-toko tanpa lisensi.
- Izin tambahan dapat menumpuk dan terlupakan; aplikasi owner wajib menampilkan
  ringkasan izin dan riwayat.
- Pencabutan izin saat karyawan offline baru berlaku setelah sinkron; pencabutan
  perangkat menghentikan akses lebih cepat.
- Izin yang hanya disembunyikan di UI bisa ditembus lewat permintaan langsung;
  pemeriksaan wajib di lapisan data.
- Batas perangkat dapat diakali dengan menyalin database/token; perangkat harus
  terdaftar, token terikat, dan penegakan offline memakai daftar terakhir. Untuk
  pengguna gratis, penegakan ini tidak berlaku.
- Perangkat hilang tanpa akses ke perangkat lama tetap dapat dicabut lewat akun
  web selama owner bisa login Google. Batas pelepasan satu kali per 72 jam dapat
  menahan owner yang benar-benar kehilangan dua perangkat berdekatan; dukungan
  tidak boleh melewati batas, jadi alur darurat harus dijelaskan di UI.
- Pencabutan perangkat lama tidak menghapus data yang sudah diunduh; jika
  perangkat hilang, anggap data itu bocor dan re-key toko terkait (K-22).
- Flag hub yang berpindah saat hub lama masih offline dapat menghasilkan dua
  penulis uang; perpindahan wajib menunggu ack atau memaksa dengan karantina
  delta lama.
- Kunci owner yang hilang bersama kode pemulihan membuat izin baru tidak dapat
  diterbitkan; pengguna harus diberi peringatan saat membuat kode.
- Re-key setelah pencabutan bergantung pada hub online; sampai selesai, delta
  sensitif harus ditahan.
- Perangkat yang dicabut tetap memegang kunci lama dan data yang sudah
  diunduhnya; re-key tidak menghapus data itu.
- Snapshot yang diterapkan tanpa memutar ulang outbox dapat menghilangkan delta
  lokal yang belum terkirim.
- TTL antrean dan snapshot yang lebih tua dari outbox dapat menimbulkan konflik;
  urutan replay dan deduplikasi wajib diuji.
- Pilot yang dilewati dapat menghasilkan fitur premium yang tidak dibutuhkan;
  gerbang pilot wajib dijalankan sebelum akun/lisensi.
- Estimasi 140–220 hari masih bisa meleset; buffer dan uji perangkat nyata
  ditambahkan sebelum tanggal rilis dijanjikan.
- Perangkat karyawan tidak dihitung dalam batas owner dapat disalahgunakan untuk
  menambah perangkat; mitigasi: uang tetap hub-only, akun harus aktif, perangkat
  terdaftar, dapat dicabut, dan pemakaian diaudit.
- Antrean relay terenkripsi menambah biaya penyimpanan dan bandwidth; TTL, kuota,
  dan batching wajib dipantau.
- TTL antrean dapat membuat penerima yang offline sangat lama kehilangan delta;
  snapshot dari hub atau backup lokal menjadi jalur pemulihan.
- Delta dari klien yang dimodifikasi dapat dipalsukan jika tidak ditandatangani;
  tanda tangan per perangkat dan verifikasi penerima wajib.
- Perangkat yang dicabut tetapi offline dapat memakai izin terakhir sampai
  mencoba sinkron; pencabutan dan notifikasi harus jelas.
- Hitung mundur lisensi offline bergantung pada jam perangkat; jam mundur tidak
  boleh memperpanjang masa aktif.
- Data fitur terkunci sengaja tetap dibaca/diekspor; ini bukan kebocoran, tetapi
  akses tulis dan aksi premium tetap harus diblokir.
- Play Billing/IAP harus direkonsiliasi saat online; refund/chargeback tidak
  boleh menghapus data lokal.
- Ukuran aplikasi Flutter bisa lebih besar dari perkiraan; ukur dulu, jangan
  menjanjikan angka.
- Paket aset opsional dapat disalahartikan sebagai izin atau menambah fitur;
  paket hanya aset statis dan shell tetap memeriksa izin.
- Windows/iOS tidak punya padanan Play Asset Delivery; paket aset harus bertanda
  tangan dan tidak menghapus logika dari shell.
- 100 akun offline lama dapat menghasilkan antrean besar; unggahan harus
  dibatching dan tidak memblokir kasir.
- Jam perangkat berbeda dapat mengacaukan urutan; wajib HLC.
- Notifikasi pending berulang dapat diabaikan; banner dan badge harus selalu
  terlihat.
- Pending berbulan-bulan dapat hilang jika perangkat rusak; backup wajib
  menyertakan outbox.
- Password yang diketik manual bisa lemah; tombol acak menjadi default dan
  karyawan wajib mengganti saat login pertama.
- Tombol salin semua menyalin password teks biasa; kirim lewat kanal pribadi dan
  karyawan wajib mengganti saat login pertama.
- ID owner yang mudah ditebak dapat dipakai mencoba username; rate limit dan
  lockout wajib aktif.
- Kuota per database dapat diakali dengan membuat database baru; keterbatasan
  diterima.
- Kesalahan input di mode karyawan memengaruhi komisi/gaji; koreksi harus
  tercatat dan disetujui pemilik.
- Metadata akun, perangkat, dan amplop relay adalah data pribadi; retensi,
  penghapusan, dan insiden wajib ditangani sesuai UU PDP.
- Harga Rp10.000/bulan dapat tipis setelah komisi Play Billing, relay, dan
  dukungan; unit economics wajib dihitung sebelum rilis.
- Biaya API relay, penyimpanan antrean, akun, dan dukungan.
- Delta bocor saat transit jika isolasi akses lemah; enkripsi E2E dan tanda
  tangan wajib.
- API/VPS mati membuat sinkronisasi berhenti; data lokal tetap aman.
- Data lama 2.x tidak dibawa; database baru dibuat dari nol.

## Di luar lingkup

- Penyimpanan data bengkel yang dapat dibaca di VPS atau cloud; API hanya relay
  dan antrean terenkripsi sementara.
- Backup ke Google Drive.
- Paket layout per peran, server-driven UI, atau unduhan kode yang dieksekusi.
- iOS sebagai target rilis tahap ini.
- Penghapusan atau pemindahan kepemilikan toko.
- Migrasi otomatis data 2.x satu toko ke multi-toko; belum ada user, database baru
  dibuat dari nol.
- Modul WebView yang mengeksekusi kode dari CDN, Play Feature Delivery, atau
  self-update.
- LAN/hub lokal; jika dibutuhkan, menjadi keputusan dan pekerjaan terpisah
  (K-21).
- Penjualan terpisah untuk sync, perangkat karyawan, atau aplikasi owner;
  semuanya bagian dari satu tier premium (K-21).
- Sinkronisasi kuota gratis ke server; kuota hanya lokal (K-04).
