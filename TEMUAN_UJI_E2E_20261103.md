# Temuan Uji End-to-End — 2026-11-03

Status: **laporan uji final 2026-11-03**. Lingkungan uji:

- Aplikasi lokal E2E: `data/dummy_e2e_final/app.db`, port `8020`, dianggap
  perangkat/HP offline.
- Relay E2E: `data/dummy_e2e_final/relay.db` (SQLite) pada port `8120` untuk
  rangkaian `tools/e2e_full_suite.py`.
- Relay produksi di laptop: PostgreSQL 18.6 port `5433`, service relay port
  `8120`, database `pusatku_relay`; data uji sudah dibersihkan.
- Folder khusus `dummy_*`; data kasir asli tidak disentuh.
- Login awal: PIN pemilik `123456`; akun karyawan `kasir_final`.
- Tidak ada APK; pengujian web nyata lewat Chrome (Playwright) dan HTTP ke dua
  proses.
- Bukti mesin: `data/dummy_e2e_final/report.json`, `app.log`, `relay.log`,
  `pytest_no_hub.log`, `data/dummy_e2e/final_no_hub.log`.
- Baris perintah: `python tools/e2e_full_suite.py` dan `python -m pytest -q`.

## Hasil akhir

**81/81 pemeriksaan lulus** pada 2026-11-03, dijalankan ulang dari database
kosong dan relay kosong dalam satu rangkaian:

1. Instal baru: setup PIN lewat browser, dashboard terbuka, service worker aktif.
2. Gratis: 1 toko, kasir, laporan, kuota 20, gating premium, backup manual.
3. Premium: lisensi, ID owner, multi-toko, isolasi, akun karyawan.
4. Perangkat: batas slot owner, wrapped key, bootstrap; tanpa hub.
5. Sinkronisasi lokal: envelope, feed, ack, hapus ciphertext, counter permanen,
   snapshot `store_seq`, klaim instal ulang, kursor snapshot.
6. Karyawan: login perangkat/komputer toko, wajib ganti password, nota berawalan
   perangkat, void/retur oleh kasir berhasil, peran non-kasir ditolak, rute
   owner ditolak.
7. UI premium: halaman premium, tambah toko, backup semua toko, tanpa error.
8. UI karyawan: identitas karyawan, menu owner tersembunyi, tanpa 403.
9. Backup semua toko: manifest + checksum untuk 3 toko, restore, rollback ZIP
   rusak, kredensial dan token perangkat bertahan.
10. Relay nyata: enroll, wrap, envelope, feed, ack, hapus ciphertext, counter,
    bootstrap, klaim, token lama ditolak, wrap ulang.
11. Offline: shell PWA dimuat tanpa server, transaksi masuk antrean IndexedDB,
    banner pending, lalu terkirim setelah server hidup.

## Ringkasan hasil

| Area | Hasil | Catatan |
| --- | --- | --- |
| Instal baru + setup PIN + login | **Lulus** | Layar setup muncul, PIN tersimpan, dashboard terbuka, tanpa error konsol |
| Akun gratis | **Lulus** | 1 toko, kasir/stok/laporan/backup manual, gating premium 403, kuota 20 |
| Aktivasi premium | **Lulus** | Lisensi, ID owner, kunci publik, batas 2 perangkat |
| Multi-toko | **Lulus** | Tambah/aktifkan toko kedua, isolasi pelanggan |
| Akun karyawan | **Lulus** | Wajib ganti password, login perangkat/komputer toko, izin, tolak rute owner |
| Nota per perangkat | **Lulus** | `HPKFD2C-20261103-0001`; nomor angka tetap dipakai tanpa perangkat |
| Void/retur oleh kasir | **Lulus** | Kasir dapat void lewat sesi server dan token perangkat; peran non-kasir ditolak |
| Perangkat owner + batas slot | **Lulus** | Perangkat owner ke-3 ditolak 403 `device_limit` |
| Kunci toko + bootstrap lokal | **Lulus** | Wrapped key, snapshot, kursor snapshot |
| Feed/kursor/ack lokal | **Lulus** | 1 amplop, ack, ciphertext terhapus, counter tetap 1 |
| Instal ulang lokal (claim) | **Lulus** | Perangkat lama dicabut, perangkat baru minta wrap baru |
| Relay nyata (proses terpisah) | **Lulus setelah perbaikan** | Enroll, wrap, envelope, feed, ack, hapus ciphertext, counter, bootstrap, klaim, token dicabut |
| Backup semua toko | **Lulus** | 3 database + manifest + checksum; restore mengembalikan data |
| Restore rollback | **Lulus** | ZIP rusak ditolak 400 dan data lama tetap |
| Kredensial setelah restore | **Lulus setelah perbaikan** | Password karyawan dan token perangkat bertahan |
| UI premium + tambah toko + backup | **Lulus** | Halaman premium, toko baru, unduhan arsip, tanpa error konsol |
| UI karyawan | **Lulus setelah perbaikan** | Label karyawan, menu owner tersembunyi, tanpa 403 |
| PWA offline | **Lulus** | Shell dimuat, auth tidak dari cache, sesi lokal 7 hari, antrean 1 item, flush 1 terkirim, logout membersihkan sesi |
| Postgres relay | **Lulus** | Enroll, envelope, feed, ack, bootstrap pada PostgreSQL 18.6; data uji dibersihkan |
| HTTPS relay | **Lulus** | TLS nyata dengan CA uji, HTTP polos ditolak, `X-Forwarded-Proto` http/https diuji |
| Kuota Follow up | **Lulus** | 20 kredit habis lintas 20 pelanggan, kredit ke-21 ditolak 403, status bertahan setelah restart |
| Suite pytest | **Lulus** | **403 passed** penuh + tes peran non-kasir terpisah lulus |
| Hub dihapus | **Lulus** | Tidak ada endpoint/UI hub; kasir dapat void lewat sesi dan token perangkat |
| **Total rangkaian final** | **81/81 lulus** | Dijalankan dari database + relay kosong setelah B-07 |

## Bug yang ditemukan

### B-01 — Bootstrap relay tidak mengembalikan `key_wrap_required`

- **Ditemukan pada:** uji relay nyata, perangkat baru setelah klaim.
- **Gejala:** `GET /relay/bootstrap` mengembalikan 200, tetapi respons tidak
  memiliki kunci `key_wrap_required`; pengujian klien gagal `KeyError`.
- **Dampak:** klien relay tidak dapat membedakan “belum ada wrapped key” dari
  “wrapped key kosong”, sehingga alur perangkat baru/instal ulang tidak dapat
  menentukan apakah harus meminta owner membungkus kunci. Bootstrap lokal sudah
  mengembalikan field ini, jadi kontrak lokal dan relay tidak konsisten.
- **Bukti:** respons relay saat itu hanya berisi `wrapped_key`,
  `owner_signature`, `cursor`, `latest_seq`, `snapshot_required`, dan
  `snapshot`.
- **Rencana perbaikan:** tambahkan `key_wrap_required: bool` di
  `relay/service.py::bootstrap` dengan nilai `wrap is None`; pastikan tes relay
  memeriksa field ini. Tidak perlu perubahan skema.
- **Status:** **sudah diperbaiki**; uji relay nyata diulang dan 18/18 lulus.

### B-02 — Restore arsip menghapus kredensial akun karyawan

- **Ditemukan pada:** uji UI login karyawan setelah restore arsip semua toko.
- **Gejala:** login karyawan di UI ditolak 401 “Username atau kata sandi
  salah”. Pemeriksaan database menunjukkan `password_hash`, `password_salt`,
  dan `pin_hash` kosong untuk akun `kasir_e2e`, padahal akun masih aktif.
- **Sebab:** arsip meredaksi hash password/PIN karyawan (K-10). Saat restore,
  baris akun dari arsip menggantikan baris aktif, sehingga hash yang sudah
  diredaksi ikut menimpa kredensial yang masih sah.
- **Dampak:** setelah restore pada instalasi yang sama, seluruh karyawan tidak
  dapat login dan pemilik harus mereset password/PIN satu per satu.
- **Rencana perbaikan:** sebelum restore, baca kredensial karyawan yang ada
  (dicocokkan dengan `username`); setelah restore, kembalikan kolom
  `password_hash/salt/iterations`, `pin_hash/salt/iterations`,
  `must_change_password`, `failed_attempts`, dan `lock_until` untuk akun yang
  masih ada. Akun baru dari arsip yang tidak punya kredensial diberi
  `must_change_password=1` agar pemilik mereset. Tidak mengubah format arsip.
- **Status:** **sudah diperbaiki** di `services/archive_service.py`; uji restore
  memperlihatkan password karyawan tetap dapat login setelah restore.

### B-03 — Restore arsip menghapus token perangkat

- **Ditemukan pada:** pemeriksaan database setelah restore arsip.
- **Gejala:** seluruh `devices.token_hash` menjadi `redacted:<id>`; perangkat
  yang sebelumnya login langsung kehilangan akses dan token asli tidak dapat
  dipulihkan dari arsip.
- **Sebab:** arsip meredaksi token perangkat (K-10), lalu restore menimpa tabel
  `devices` pada instalasi aktif.
- **Dampak:** semua perangkat owner/karyawan harus didaftarkan ulang setelah
  restore, termasuk perangkat yang tidak berubah.
- **Rencana perbaikan:** sebelum restore, baca `token_hash` asli per `device.id`
  dari database utama; setelah restore, kembalikan token untuk ID perangkat yang
  masih ada. Perangkat baru dari arsip tetap tanpa token dan harus didaftarkan
  ulang. Tidak mengubah format arsip.
- **Status:** **sudah diperbaiki** di `services/archive_service.py`; uji
  perangkat dengan token yang sama tetap 200 setelah restore.

### B-04 — Menu “Pemilik/Premium” tetap terlihat pada akun karyawan

- **Ditemukan pada:** uji UI login karyawan.
- **Gejala:** setelah login karyawan, tab **Premium** (grup “Pemilik”) masih
  tampil dan membuka halaman premium; halaman itu memicu beberapa respons 403
  di konsol karena endpoint premium hanya untuk owner.
- **Sebab:** markup memakai kelas `role-hidden-owner`, tetapi tidak ada CSS/JS
  yang menyembunyikannya berdasarkan peran operator.
- **Dampak:** UI membingungkan karyawan dan menampilkan permintaan yang pasti
  ditolak; lapisan data tetap aman karena 403.
- **Rencana perbaikan:** di `applyConfig`, sembunyikan semua elemen
  `.role-hidden-owner` bila `operator.kind === 'employee'`; tampilkan lagi untuk
  owner. Tidak mengubah izin backend.
- **Status:** **sudah diperbaiki**; login karyawan di UI tidak lagi menampilkan
  tab Premium dan tidak ada 403 dari halaman premium.

### B-05 — Login karyawan berhenti sebelum `applyConfig` karena satu endpoint 403

- **Ditemukan pada:** uji UI login karyawan setelah B-04.
- **Gejala:** login karyawan berhasil di backend (cookie valid), gerbang login
  tertutup, tetapi judul halaman tetap default, label sesi tetap “Pemilik”,
  menu owner tetap terlihat, dan konsol mencatat 403.
- **Sebab:** `startApp` memakai `Promise.all` untuk config + stok + jasa +
  karyawan + supplier. Akun karyawan tidak memiliki izin `baca_supplier`,
  sehingga `/api/suppliers` 403 dan seluruh `startApp` dibatalkan sebelum
  `applyConfig` dijalankan.
- **Dampak:** UI karyawan tampak terbuka tetapi tidak memakai identitas/izin
  karyawan; ini juga membuat perbaikan B-04 tidak pernah berjalan.
- **Rencana perbaikan:** muat `config` lebih dulu; dataset opsional (stok, jasa,
  karyawan, supplier) dimuat dengan toleransi 403 dan supplier dilewati bila
  izin tidak ada. Setelah config didapat, jalankan `applyConfig` seperti biasa.
- **Status:** **sudah diperbaiki** di `startApp`; uji ulang login karyawan
  menampilkan label karyawan, menyembunyikan menu owner, dan tanpa 403 supplier.

### B-06 — Dashboard karyawan tetap memanggil data owner (`employees`, payroll)

- **Ditemukan pada:** uji ulang UI karyawan setelah B-05; dua respons 403
  tersisa di `/api/employees` dan `/api/payroll/summary`.
- **Sebab:** `startApp` selalu memuat daftar karyawan, dan `loadDashboard`
  memuat ringkasan payroll bila `ops.karyawan_aktif`, tanpa memeriksa peran.
- **Dampak:** UI karyawan memicu permintaan yang pasti ditolak dan
  menampilkan kegagalan di konsol; data tidak bocor karena backend menolak.
- **Rencana perbaikan:** lewati `API.employees` untuk operator karyawan dan
  panggil `payrollSummary` hanya untuk owner. Tampilkan kartu payroll hanya
  untuk owner.
- **Status:** **sudah diperbaiki**; uji ulang tidak menemukan 403 di dashboard
  karyawan.

### B-07 — Service worker menyajikan status autentikasi dari cache

- **Ditemukan pada:** uji PWA dengan server lokal dimatikan.
- **Gejala:** halaman tetap terbuka dari cache dan UI menganggap sesi masih
  aktif karena `/api/auth/status` dilayani dari respons cache; pengguna tidak
  melihat gerbang login saat server mati.
- **Sebab:** service worker memakai network-first untuk semua `/api/` GET dan
  menyimpan respons sukses, termasuk status autentikasi dan metadata premium.
- **Dampak:** pada web, sesi yang sudah dicabut/di-logout dapat tampak aktif
  saat offline; data baca juga tersimpan di cache peramban. Ini bukan
  kebocoran lintas pengguna pada perangkat yang sama, tetapi perlu kebijakan
  retensi/keluar yang jelas.
- **Rencana perbaikan:** untuk web, kecualikan `/api/auth/`, `/api/premium/`,
  `/api/license/`, `/api/accounts`, `/api/devices`, dan `/api/sync/` dari cache;
  simpan penanda sesi lokal yang eksplisit untuk mode offline, atau terima
  sebagai keterbatasan prototipe web karena APK/Dart memakai sesi lokal dan
  SQLite. Menghapus cache saat logout juga wajib.
- **Status:** **sudah diperbaiki** (2026-11-03). Service worker tidak lagi
  menyimpan `/api/auth/`, `/api/premium/`, `/api/license/`, `/api/accounts`,
  `/api/devices`, `/api/sync/`, atau `/api/owner-app/`. Sesi offline memakai
  penanda lokal berumur 7 hari yang disimpan setelah login sukses dan dihapus
  saat logout/401. Uji ulang memastikan `auth/status` gagal saat server mati
  (tidak dilayani cache), penanda sesi ada, antrean offline tetap jalan, dan
  logout menghapus penanda.

### B-08 — Arsip ZIP dengan CRC rusak menghasilkan 500, bukan 400

- **Ditemukan pada:** uji restore dengan satu database di dalam ZIP dirusak.
- **Gejala:** `POST /api/admin/restore-all` mengembalikan 500; data lama tetap
  utuh karena rollback berjalan, tetapi klien menerima “kesalahan server”.
- **Sebab:** `zipfile.BadZipFile` saat ekstraksi tidak ditangkap; hanya checksum
  manifest yang diperiksa setelah ekstraksi. `is_zipfile` tetap benar walau CRC
  isi berkas rusak.
- **Dampak:** pengguna tidak mendapat pesan yang dapat ditindaklanjuti; log
  server berisi traceback.
- **Rencana perbaikan:** tangkap `zipfile.BadZipFile`/`LargeZipFile` di
  `restore_archive` dan ubah menjadi `BusinessValidationError` (400) dengan
  pesan “Arsip rusak atau tidak lengkap”. Rollback yang ada tetap dipertahankan.
- **Status:** **sudah diperbaiki**; uji ulang ZIP rusak menghasilkan 400 dan
  data lama tetap ada.

## Perilaku yang dikonfirmasi (bukan bug)

- Nota baru wajib memiliki `keluhan_awal`; permintaan tanpa keluhan ditolak 400.
  Ini aturan transaksi yang sudah ada.
- Karyawan dengan password awal wajib mengganti password sebelum transaksi;
  setelah ganti password, nota dan izin berjalan.
- Login karyawan pertama di komputer toko membuat PIN dari isian PIN dan
  mengembalikan `pin_set: true`; login berikutnya `pin_set: false`.

## Uji PostgreSQL lokal (2026-11-03)

- Instance PostgreSQL 18.6 khusus relay berjalan di `127.0.0.1:5433` dengan data
  directory `data/pg_relay` (diabaikan Git). Database `pusatku_relay` dan role
  `pusatku_relay` terpisah dari instance service port 5432.
- Skema relay dibuat di PostgreSQL: 11 tabel `relay_*` setelah tabel hub
  dihapus; tidak ada tabel bisnis.
- Simulasi 6 perangkat pada PostgreSQL: **35 amplop diterapkan, 0 tersisa,
  counter feed 7**, dialek `postgresql+psycopg`.
- Uji HTTP nyata ke proses relay: enroll 2 perangkat, wrapped key, envelope,
  feed, ack/hapus, dan bootstrap **9/9 lulus**.
- Setelah uji, seluruh data uji di-TRUNCATE; database relay bersih dengan
  `relay_schema_version = 1`.
- Relay produksi berjalan di port `8120` dengan PostgreSQL, health
  `"dialect":"postgresql"`, tanpa tabel `relay_store_hubs`.
- Relay berjalan dengan `RELAY_HOST=127.0.0.1`, jadi belum terbuka ke LAN.
  Untuk akses perangkat lain, wajib HTTPS reverse proxy lalu ubah host secara
  sadar; PostgreSQL sendiri hanya mendengarkan localhost.

## Uji HTTPS relay

- Sertifikat uji (CA + server untuk `localhost`/`127.0.0.1`) dibuat di
  `data/dummy_https`; relay dijalankan dengan TLS di port 8443 dan
  `RELAY_REQUIRE_HTTPS=1`.
- Health dan route perangkat lewat HTTPS dengan verifikasi CA: **lulus**.
- HTTP polos ke port TLS ditolak oleh lapisan TLS.
- Relay polos di port 8445 dengan `RELAY_REQUIRE_HTTPS=1`:
  tanpa `X-Forwarded-Proto` → 400; header `http` → 400; header `https` → 201.
  Ini menguji kontrak reverse proxy.
- Data uji di PostgreSQL dibersihkan setelah pengujian.

## Uji kuota Follow up sampai habis

- Profil gratis baru di `data/dummy_quota`; 20 pelanggan masing-masing mendapat
  satu prospek (transaksi digeser 30 hari sebagai fixture uji).
- Kredit terpakai berurutan 1..20; status akhir `terpakai=20, sisa=0,
  terkunci=true`; permintaan berikutnya **403 `followup_quota_habis`**.
- Status kuota tetap 20/20 setelah server dihentikan dan dijalankan ulang
  (counter lokal persisten).
- Catatan perilaku: satu item tidak bisa dipakai 20 kali karena aturan jeda
  10 hari dan batas pesan harian per pelanggan; pengujian memakai 20 pelanggan
  berbeda, sesuai aturan yang ada.

## Suite pytest penuh

- Putaran awal menemukan satu tes lama yang masih mengharapkan karyawan ditolak
  membuat nota; tes itu diperbarui mengikuti K-12 (nota karyawan 201).
- Setelah keputusan **hub dihapus**, tes diperbarui: karyawan dengan akses kasir
  dapat membuat nota dan void lewat sesi server maupun token perangkat; tidak
  ada endpoint hub.
- Suite penuh setelah perubahan hub: **403 passed, 0 failed** (1.451 detik).
  Bukti: `data/dummy_e2e_final/pytest_no_hub.log`.
- Setelah itu ditambahkan satu tes peran non-kasir
  (`tests/test_premium_web.py::test_karyawan_non_kasir_tidak_bisa_void`); tes
  tersebut lulus sendiri. Total tes di repo sekarang 404, tetapi belum
  dijalankan ulang sebagai satu batch penuh setelah penambahan itu.

## Revisi: hub dihapus, void oleh akses kasir

- **Aturan baru:** tidak ada hub/flag hub. Owner dan karyawan `KASIR`/`KEDUANYA`
  pada toko yang ditugaskan dapat void, retur, tukar, dan piutang. Peran lain
  ditolak `role_money_locked`.
- **Kode:** `assert_cashier_money_access` menggantikan pemeriksaan hub; endpoint
  `/api/devices/hub` dan `/relay/devices/hub` dihapus; snapshot dibuat dari
  perangkat owner mana pun; form/JS hub di UI dihapus; migrasi 46 menghapus
  tabel hub dan mengganti kolom kunci menjadi `primary_device_id`.
- **E2E:** **81/81 lulus**; kasir membuat nota dan void lewat sesi server dan
  token perangkat; peran non-kasir mendapat 403.
- **UI:** halaman Premium tidak lagi memuat form/nav hub; `keyStore` berisi 3
  toko; tombol **Buat kunci pengaman** berhasil; tanpa error konsol/permintaan
  gagal. Bukti: `data/dummy_e2e_final/premium_no_hub.png`.
- **Pytest:** suite penuh **403 passed**; tes peran non-kasir terpisah lulus.
- Bukti E2E: `data/dummy_e2e/final_no_hub.log`.

## Fase 2 Flutter (kode inti)

- Flutter 3.47.9 stable dipasang di `C:\Users\Administrator\flutter`; proyek
  `pusatkupos/` dibuat untuk Android, web, dan Windows.
- Kode inti dibangun: SQLite lokal, PIN pemilik, pelanggan/unit, stok +
  stok masuk, tarif jasa, kasir, nomor nota, void, riwayat, laporan, pengaturan,
  dan backup ZIP.
- **Bukti:** `flutter analyze` bersih (2 info), `flutter test` **2 lulus**
  (parser Rupiah + transaksi, laporan, void), `flutter build web --release`
  berhasil, smoke Chrome berhasil setup PIN, membuka dashboard, dan menambah
  sparepart tanpa error konsol.
- **Belum diuji:** transaksi kasir end-to-end lewat UI Flutter, restore backup
  di perangkat, build Android/Windows, ukuran aplikasi, dan Fase 3–7.

## Yang belum dilakukan

### Produk dan rilis
- **Pilot 1–3 bengkel nyata** selama 2–4 minggu. Ini gerbang sebelum port
  Dart/APK dan rilis premium.
- **Uji UI manual lengkap** pada lebar 1440/1024/810/360, tema terang/gelap,
  lima tema warna, header dua baris + layout printer, ganti toko, semua form
  premium, dan login perangkat karyawan.
- **Perangkat fisik:** printer thermal, scanner HID, render barcode/QR pada
  label dan nota.
- **Telegram jaringan sungguhan** dan backup terjadwal jarak jauh.
- **Uji beban** lebih dari 6 perangkat, offline berbulan-bulan, jaringan lambat/
  putus-putus, dan penyimpanan hampir penuh.

### Flutter, Android, dan distribusi
- Port Dart/Flutter **Fase 3–7**; Fase 2 kode inti sudah dibangun di
  `pusatkupos/` dan baru diuji lewat web build + smoke. Uji kasir end-to-end di
  Flutter belum.
- Build APK/AAB Android, Play Billing, secure storage, notifikasi sistem, dan
  kunci perangkat sungguhan; Android SDK/Visual Studio belum terpasang.
- Relay lintas perangkat nyata (bukan dua proses di laptop yang sama).
- Paket Windows/macOS, penandatanganan, dan pengukuran ukuran aplikasi.
- Dokumen spesifikasi protokol + test vector sebelum implementasi sync Dart.

### Infrastruktur relay
- **Reverse proxy produksi dengan sertifikat publik.** HTTPS sudah diuji dengan
  CA lokal; relay saat ini hanya mendengarkan `127.0.0.1`.
- Firewall/LAN exposure, monitoring, backup PostgreSQL, dan retensi data relay
  pada skala produksi.
- Uji keamanan tambahan: rate limit jangka panjang, pembatasan IP, rotasi token,
  dan audit login nyata.
- **Suite pytest 404 tes sebagai satu batch penuh.** Suite 403 lulus sudah
  dijalankan setelah hub dihapus; satu tes peran non-kasir ditambahkan setelah
  itu dan baru dijalankan sendiri.

### Akun, privasi, dan kepatuhan
- Login Google sungguhan, persetujuan privasi, dan hapus akun end-to-end di web.
- Play Data Safety, kebijakan retensi, dan prosedur insiden UU PDP.
- Uji pemulihan kunci owner dengan kode pemulihan di perangkat nyata.

## Urutan perbaikan

1. Jalankan pilot 1–3 bengkel dan uji UI manual; perbaiki temuan sebelum port
   Dart.
2. Siapkan reverse proxy produksi dengan sertifikat publik dan uji beban relay.
3. Tulis spesifikasi protokol + test vector, lalu port Dart/Flutter dan APK.
4. Jalankan suite pytest 404 sebagai satu batch dan uji akhir lintas platform.
