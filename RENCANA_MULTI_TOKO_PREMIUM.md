# Rencana Multi-Toko dan Fitur Premium — PusatkuPOS

Status: **rencana aktif — belum diimplementasikan**. 2026-11-03.

Produk: **PusatkuPOS (Flutter)**. Aplikasi 2.7.0 yang berjalan sekarang tetap
**BengkelPOS Radiator** dan tidak menerima fitur ini.

Dokumen ini menggabungkan rencana multi-toko dan fitur premium. Pengujian tidak
dicantumkan di sini; seluruh skenario uji ada di `RENCANA_PEMANTAPAN.md` dan baru
dijalankan setelah fiturnya dibangun.

## Ringkasan keputusan

- **Premium:** Karyawan, Supplier, Follow up, semua tombol WhatsApp, backup
  otomatis, dan multi-toko.
- **Trial:** 20 klik WhatsApp total, tanpa batas waktu, tidak bisa direset atau
  ditambah ulang.
- **Kuota:** 1 klik WhatsApp = 1 kuota. Kuota dipotong saat tombol/link `wa.me`
  dibuka, bukan saat pesan benar-benar terkirim.
- **Setelah trial:** premium membuka pesan unlimited dan seluruh modul premium.
- **Gratis:** lokal penuh, satu perangkat, satu toko, tanpa API, dan **tanpa
  iklan sama sekali** walaupun perangkat terhubung internet.
- **Multi-toko adalah fitur premium.** Pengguna gratis tetap satu toko dan tidak
  melihat tombol tambah toko.
- **Login Google wajib untuk pemilik multi-toko.** Karyawan memakai
  undangan/perangkat yang ditugaskan dan tidak wajib punya akun Google.
- **Tidak ada batas jumlah toko** untuk akun premium.
- **Retensi data cloud per tenant belum diputuskan** dan ditunda.
- **Premium awal** berfokus pada modul lokal dan multi-toko. Sinkronisasi API,
  multi-device, serta aplikasi owner/karyawan adalah tahap premium lanjutan.

## Batas gratis, trial, dan premium

| Area | Gratis | Trial | Premium |
| --- | --- | --- | --- |
| Kasir, stok, pelanggan, unit, jasa, laporan | Ya | Ya | Ya |
| Backup manual dan restore | Ya | Ya | Ya |
| PIN dan pengaturan lokal | Ya | Ya | Ya |
| Satu toko | Ya | Ya | Ya |
| Karyawan, Supplier, Follow up | Tidak | Demo | Ya |
| Tombol WhatsApp | Tidak | 20 klik total | Unlimited |
| Backup otomatis | Tidak | Demo | Ya |
| Multi-toko dan ganti toko | Tidak | Tidak | Ya |
| Sinkronisasi API | Tidak | Untuk kuota/lisensi | Tahap lanjutan |
| Multi-device | Tidak | Tidak | Tahap lanjutan |
| Aplikasi owner/karyawan | Tidak | Tidak | Tahap lanjutan |
| Iklan | Tidak ada | Tidak ada | Tidak ada |

Trial membuka modul premium sebagai demo. Setelah 20 klik WhatsApp habis,
seluruh fitur premium terkunci sampai pembelian. Data lokal tidak dihapus.

## Fitur premium

### 1. Karyawan

- Data karyawan, peran, penugasan mekanik/kasir, komisi, gaji, dan performa.
- Aplikasi/akun karyawan untuk absensi, penugasan, status pengerjaan, dan
  komisi sesuai izin.
- Data karyawan tidak ikut ke perangkat gratis.

### 2. Supplier

- Data supplier, relasi supplier–barang, follow up reseller, dan riwayat
  supplier.
- Tombol WhatsApp supplier memakai kuota yang sama dengan tombol WA lain.

### 3. Follow up

- Follow up pelanggan, garansi, servis berkala, prospek, piutang, dan reseller.
- Hasil follow up dan pengingat.
- Semua pengiriman WhatsApp dari modul ini memakai kuota.

### 4. Semua tombol WhatsApp

- Mencakup struk, follow up, piutang, garansi, reseller, supplier, dan tombol
  WhatsApp lain di aplikasi.
- 1 klik = 1 kuota, termasuk saat pengguna membatalkan atau WhatsApp gagal
  dibuka. Tidak ada pengembalian kuota.

### 5. Backup otomatis

- Backup terjadwal lokal, Telegram, dan opsi cloud premium.
- Backup manual dan restore tetap tersedia untuk pengguna gratis.
- Sinkronisasi bukan pengganti backup; backup lokal tetap menjadi cadangan
  utama.
- Backup semua toko memakai satu arsip; rinciannya di bagian Multi-toko.

### 6. Multi-tenant, sinkronisasi, dan multi-device

- Satu tenant per bengkel; data terpisah antar bengkel.
- Hub kasir mengirim delta transaksi ke API developer; owner melihat laporan
  dari cloud.
- Multi-device hanya premium; perangkat tambahan mengikuti aturan satu penulis
  untuk uang dan stok.
- Kasir tetap offline-first: API mati tidak menghentikan transaksi.
- Sinkronisasi, multi-device, dan aplikasi owner/karyawan dikerjakan setelah
  premium awal dan multi-toko stabil.

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
2. Lapisan data Flutter (SQLite/drift) dan repository siap.
3. Keputusan bisnis: multi-toko premium (diputuskan 2026-11-03).
4. Keputusan peran: pemilik boleh menambah toko; karyawan hanya melihat toko
   yang ditugaskan (diputuskan).
5. Keputusan akun: Google wajib untuk pemilik multi-toko; karyawan memakai
   undangan/perangkat tanpa Google (diputuskan 2026-11-03).
6. Penyimpanan aman platform untuk token (Keystore/Keychain/DPAPI) tersedia.

### Arsitektur lokal

- Setiap toko memiliki database sendiri, misalnya
  `stores/<store_id>/database.db`.
- Daftar toko disimpan di registry lokal, misalnya `stores/registry.json`,
  berisi ID, nama, alamat, toko aktif, versi skema, dan waktu dibuat.
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

### Login tanpa akun, Google, dan logout

- **Tanpa login** adalah jalur default untuk toko tunggal/pengguna gratis:
  lokal, satu perangkat, tanpa internet, dan memakai PIN perangkat. Data
  disimpan di SQLite lokal pada folder aplikasi perangkat; tidak ada upload ke
  API.
- **Login Google wajib untuk pemilik multi-toko.** Google dipakai untuk
  identitas, lisensi premium, dan akun; data tetap disimpan lokal lebih dulu.
- Karyawan tidak wajib punya akun Google. Mereka memakai undangan/perangkat
  yang ditugaskan oleh pemilik dan hanya melihat toko yang diizinkan.
- Login Google hanya dipakai untuk akun pemilik multi-toko premium. Tanpa
  premium atau saat memakai toko tunggal, data tetap lokal dan tidak diunggah.
  Dengan premium, salinan disinkronkan ke API/cloud tenant; database lokal tetap
  sumber utama.
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
- Jika aplikasi dihapus, data lokal hilang kecuali sudah dibackup; data cloud
  premium mengikuti kebijakan retensi tenant.

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
- Arsip berisi manifest toko (ID, nama, alamat, toko aktif), seluruh database
  toko, versi skema, dan versi aplikasi. Contoh:
  `backup_semua_toko_YYYYMMDD.zip`.
- Arsip menyertakan checksum untuk setiap database dan manifest.
- Backup tidak boleh hanya mengambil toko aktif karena restore bisa
  menghasilkan daftar toko yang tidak lengkap.
- Restore satu arsip langsung memunculkan **Toko A, Toko B, Toko C** dan
  seterusnya tanpa upload/impor database satu per satu.
- Restore memvalidasi manifest, checksum, dan seluruh database. Jika satu
  bagian gagal, seluruh restore dibatalkan dan data lama dikembalikan.
- Restore memakai mekanisme tukar-sementara (staging) sebelum mengganti data
  aktif; data lama disimpan sampai restore dinyatakan berhasil.
- Toko yang ditambahkan setelah backup terakhir akan ikut pada backup
  berikutnya.
- Backup otomatis, manual, dan Telegram memakai arsip yang sama; Telegram tetap
  tunduk pada batas ukuran file.
- Ekspor Excel/CSV dapat berisi subfolder atau workbook per toko di dalam satu
  ZIP.
- PIN, token, dan rahasia perangkat tetap diredaksi dari arsip.
- Tidak ada upload per toko ke cloud; restore memakai satu arsip lokal atau satu
  file yang dipilih pengguna.
- Fitur ini dikerjakan **setelah** backup satu toko di PusatkuPOS stabil.

## Kuota trial

- Total kuota: **20 klik WhatsApp**.
- Tidak ada batas waktu; trial berakhir saat kuota habis.
- Tidak ada penambahan ulang, reset, atau kuota harian/bulanan.
- Kuota dihitung saat tombol WA ditekan dan link `wa.me` dibuat.
- Aplikasi tidak dapat memastikan pesan benar-benar terkirim karena WhatsApp
  berada di luar aplikasi.
- Kuota yang sudah terpakai tidak dikembalikan jika pengguna membatalkan,
  WhatsApp tidak terpasang, atau pesan gagal dikirim.
- Aplikasi menampilkan sisa kuota dan peringatan sebelum habis.
- Setelah kuota 0, tombol WA dan modul premium terkunci sampai pembelian.
- Untuk mencegah reset dengan reinstall, kuota harus terikat akun/lisensi atau
  penyimpanan aman, bukan hanya data aplikasi biasa.

## Free tier

- Berjalan lokal, satu perangkat, satu toko, tanpa panggilan API.
- Kasir, stok, pelanggan, unit, jasa, laporan, PIN, pengaturan, backup manual,
  dan restore tetap tersedia.
- Karyawan, Supplier, Follow up, tombol WA, backup otomatis, dan multi-toko
  terkunci.
- **Tanpa iklan sama sekali:** tidak ada banner, popup, video, ad SDK, jaringan
  iklan, atau permintaan latar untuk iklan, termasuk saat online.
- Tidak ada pengiriman data ke API developer.

## Arsitektur premium

```text
Aplikasi Flutter (Android/Windows/Mac)
        │
        ├─ SQLite lokal + outbox + kuota lokal
        ├─ Registry toko + database per toko
        │
        ├─ Hub kasir ── LAN ── owner/karyawan di bengkel
        │
        └─ API developer (HTTPS)
                ├─ akun, tenant, lisensi, perangkat
                ├─ validasi kuota trial
                ├─ penerimaan delta/snapshot
                ├─ laporan owner/karyawan
                └─ object storage backup
```

- **Client:** Flutter + SQLite.
- **API:** FastAPI + PostgreSQL; Python hanya di server, tidak masuk paket
  aplikasi.
- **Auth:** login tanpa akun untuk pemakaian lokal, Google untuk akun premium,
  undangan karyawan, token perangkat, dan sign out per perangkat. Sign out
  menghentikan sync di perangkat itu tanpa menghapus data lokal.
- **Kuota:** dicatat lokal dan disinkronkan ke server saat online; server
  menjadi acuan untuk mencegah reset.
- **Lisensi:** masa tenggang offline; kegagalan API tidak mengunci kasir lokal.
- **Pembayaran:** penyedia pembayaran dipilih saat tahap lisensi.

## Alur trial dan pembelian

1. Pengguna membuat akun trial dan mendapat 20 kuota.
2. Modul premium terbuka dalam mode demo.
3. Setiap klik WA mengurangi kuota satu.
4. Saat kuota habis, fitur premium terkunci dan muncul pilihan pembelian.
5. Pembelian membuka pesan unlimited dan seluruh modul premium.
6. Data lokal tetap tersimpan selama trial berakhir.
7. Jika langganan berakhir, kasir lokal tetap jalan; fitur premium mengikuti
   kebijakan paket.

## Aturan konflik dan sinkronisasi

- Hub kasir adalah satu-satunya penulis nota, pembayaran, retur, dan stok.
- Owner app read-only pada tahap awal.
- Karyawan hanya menulis absensi, status tugas, catatan, dan permintaan stok.
- Uang dan stok tidak memakai “tulisan terakhir menang”.
- Waktu server menjadi acuan urutan; waktu lokal untuk tampilan.
- Pengiriman ulang harus idempotent agar nota/stok tidak ganda.

## Urutan pekerjaan (mudah → sulit)

Keputusan produk sudah selesai 2026-11-03 dan tidak dihitung dalam urutan:
multi-toko premium, Google wajib untuk pemilik, karyawan tanpa Google, tanpa
batas toko untuk premium, dan retensi cloud ditunda.

Urutan di bawah ini disusun dari pekerjaan termudah ke tersulit, lalu
disesuaikan dengan dependensi. Jika pekerjaan ringan bergantung pada pekerjaan
yang lebih sulit (misalnya logout membutuhkan login), dependensi menang dan
pekerjaan ringan itu dikerjakan tepat setelah prasyaratnya. Estimasi adalah
perkiraan kasar untuk satu pengembang setelah prasyarat selesai.

| Urutan | Pekerjaan | Kesulitan | Prioritas | Estimasi | Prasyarat |
| --- | --- | --- | --- | --- | --- |
| 1 | Header nama bengkel + alamat | Mudah | P0 | 1–2 hari | Tidak ada; memakai toko aktif dan menyatu saat ganti toko siap |
| 2 | Registry toko + folder + database kosong per toko | Mudah–Sedang | P0 | 3–4 hari | Lapisan data Flutter |
| 3 | Ganti toko di Menu + izin peran + konfirmasi | Sedang | P0 | 2–3 hari | Registry; login pemilik untuk rilis premium |
| 4 | Akun premium + login Google pemilik + lisensi + token aman | Sedang–Sulit | P0 | 5–8 hari | Penyimpanan aman platform; lapisan data Flutter |
| 5 | Gating premium + kuota WhatsApp | Sedang | P0 | 3–5 hari | Akun dan lisensi |
| 6 | Pembelian, aktivasi, masa tenggang, penurunan paket | Sedang | P0 | 3–5 hari | Lisensi |
| 7 | Logout + akses karyawan tanpa Google | Sedang | P1 | 2–3 hari | Login pemilik |
| 8 | Backup otomatis + backup semua toko | Sulit | P0/P1 | 8–12 hari | Registry; backup satu toko stabil |
| 9 | Multi-device + sinkronisasi | Sangat sulit | P1 | 10–15 hari | API, outbox, idempotency |
| 10 | Owner app read-only + employee app | Sulit–Sangat sulit | P1 | 11–18 hari | Sinkronisasi dasar dan izin |

Perkiraan total: **48–75 hari** setelah prasyarat. Pekerjaan 1–6 adalah
rangkaian premium awal dan multi-toko; pekerjaan 7 menyusul tanpa menunda rilis.
Pekerjaan 8 boleh berjalan paralel setelah registry siap. Pekerjaan 9–10 adalah
tahap lanjutan dan dikerjakan terakhir.

Catatan urutan:

- Pekerjaan 1–3 bisa dimulai tanpa akun cloud. Header lebih dulu, lalu registry,
  lalu ganti toko.
- Pekerjaan 4–6 satu rangkaian: akun dan lisensi sebelum gating dan pembelian.
  Login Google pemilik wajib sebelum multi-toko dirilis.
- Pekerjaan 7 (logout dan akses karyawan) menyusul setelah login tanpa menunda
  rilis multi-toko.
- Pekerjaan 8 menunggu backup satu toko stabil; backup semua toko tidak boleh
  mendahului backup satu toko.
- Pekerjaan 9–10 dikerjakan setelah alur lokal stabil. Owner/employee app
  menunggu sinkronisasi dasar.

Urutan wajib: akun dan lisensi sebelum multi-toko dirilis; registry dan isolasi
sebelum ganti toko; backup satu toko stabil sebelum backup semua toko; tidak ada
rilis UI kosong.

## Kriteria selesai

- **Hanya akun premium** yang dapat menambah toko; pengguna gratis tetap satu
  toko dan tidak melihat tombol tambah.
- **Login Google pemilik wajib** untuk multi-toko; karyawan memakai undangan
  tanpa Google.
- **Tidak ada batas jumlah toko** untuk akun premium.
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
- Login tanpa akun bekerja penuh offline untuk toko tunggal; multi-toko
  memerlukan login Google pemilik dan lisensi premium.
- Free tier tidak menampilkan iklan dan tidak memanggil API.
- Trial memberi 20 klik WA; kuota tidak bisa ditambah dengan reinstall.
- Klik WA ke-21 ditolak dan modul premium terkunci.
- Premium membuka pesan unlimited dan semua modul premium awal.
- Kasir tetap bertransaksi saat API mati total.
- Backup manual tetap bisa dipulihkan tanpa cloud.
- Data lokal tidak hilang saat trial berakhir.
- Kebijakan retensi data cloud per tenant tetap ditunda dan dicatat pada rilis.
- Tidak ada rahasia di arsip backup.

## Di luar lingkup

- Implementasi fitur ini di lini 2.x.
- Penghapusan atau pemindahan kepemilikan toko.
- Backup ke Google Drive.
- Migrasi otomatis data 2.x satu toko ke multi-toko; belum ada user, database
  baru dibuat dari nol.
- iOS; target Flutter tahap ini Android, Windows, dan macOS.

## Risiko

- Isolasi data lemah dapat mencampur nota/stok antar toko.
- Registry rusak dapat menyembunyikan toko; butuh pemulihan yang aman.
- Restore semua toko memperbesar dampak kegagalan; wajib all-or-nothing.
- Arsip multi-toko cepat membesar dan dapat melewati batas Telegram.
- Login Google menambah ketergantungan jaringan; kasir tetap harus offline
  setelah login awal.
- Gating premium yang salah dapat mengunci pengguna gratis dari toko tunggal
  atau membuka multi-toko tanpa lisensi.
- Karyawan tanpa Google harus tetap dapat membuka toko yang ditugaskan tanpa
  membocorkan toko lain.
- Kuota lokal bisa diakali jika tidak terikat akun/lisensi.
- `wa.me` tidak bisa memastikan pesan terkirim; kuota dihitung saat klik.
- Konflik multi-device jika uang/stok ditulis dari beberapa perangkat.
- Biaya API, database, storage, dan dukungan.
- Kebocoran data tenant jika isolasi akses lemah.
- Data lama 2.x tidak dibawa; database baru dibuat dari nol.

## Keputusan yang masih terbuka

- Kebijakan retensi data cloud per tenant.
- Harga paket premium dan apakah sekali bayar atau langganan.
- Batas perangkat untuk akun premium.
- Apakah data Karyawan/Supplier/Follow up lama tetap bisa dibaca/diekspor saat
  fitur terkunci.
- Kapan kuota disinkronkan ke server dan bagaimana perilaku saat offline lama.
- Apakah backup otomatis premium mencakup Telegram, cloud, atau keduanya.
- Nasib aplikasi Python lama setelah versi Flutter stabil.
