# Rencana Perbaikan Hasil Audit
**Aplikasi:** BengkelPOS Radiator v2.0
**Sumber temuan:** `LAPORAN_AUDIT_BUG_SECURITY_BISNIS.md` (30 Oktober 2026)
**Status:** Dokumen rencana — belum ada kode aplikasi yang diubah

Dokumen ini adalah rencana kerja, bukan hasil implementasi. Setiap item memuat: temuan yang diperbaiki, berkas yang disentuh, pendekatan teknis, kriteria selesai, dan uji regresi yang harus ditambahkan.

---

## 0. Prinsip perbaikan

1. **Jangan menambah risiko saat memperbaiki.** Perubahan pada jalur transaksi dan restore harus disertai test yang gagal sebelum perbaikan dan lulus sesudahnya.
2. **Perbaiki akar masalah, bukan gejala.** Contoh: duplikasi nota diperbaiki dengan idempotency key, bukan dengan menyembunyikan tombol.
3. **Pertahankan pertahanan yang sudah terbukti** (bagian 6 laporan): transaksi atomik POS, `Decimal`, escaping `esc()`, token fail-closed, redaksi backup.
4. **Tidak ada operasi destruktif pada data pengguna** dalam perbaikan (tanpa drop tabel, tanpa hapus data tanpa migrasi yang dapat dibatalkan).
5. **Satu item = satu commit** dengan pesan yang menyebut ID temuan (mis. `fix(pos): idempotency key transaksi (B-02)`).

---

## 1. Fase 0 — Wajib sebelum produksi / uji pemakaian nyata

Fase ini menutup jalur **kehilangan data, duplikasi transaksi, dan kebocoran token**. Jangan mengaktifkan mode LAN atau backup otomatis di produksi sebelum fase ini selesai.

### P0-1 · Batasi akses API (S-01, S-06)

**Masalah:** `APP_HOST=0.0.0.0` dan hampir semua endpoint tanpa autentikasi.

**Langkah:**
1. Ubah default `APP_HOST` menjadi `127.0.0.1` (`config.py:91`, `run.py`). Mode LAN hanya aktif bila pengguna menyalakan flag eksplisit, mis. `ALLOW_LAN=true`.
2. Bila mode LAN aktif, wajibkan autentikasi untuk **semua** endpoint `/api/*` kecuali `/api/health`:
   - endpoint baca: token sesi (lihat P0-2 di fase APK) atau `X-Admin-Token`;
   - endpoint tulis (POST/PUT/DELETE): `X-Admin-Token` (perluas pola `require_admin_token` yang sudah ada).
3. Wajibkan header `X-Requested-With: BengkelPOS` pada semua request mutasi. Header non-simple memicu preflight CORS, sehingga halaman asing tidak bisa memicu efek samping (menutup S-06).
4. Tambahkan pembatas percobaan token (S-02): maksimum 5 kegagalan per 5 menit per alamat IP, balas 429, dan catat ke log tanpa menulis token.
5. Nonaktifkan `/docs`, `/redoc`, `/openapi.json` saat `APP_ENV != development` (atau lindungi dengan token) (S-03).
6. Hapus/masking `telegram.chat_id` dari respons `/api/config` publik; tampilkan `***9086` atau pindahkan ke endpoint ber-token (S-04).

**Berkas:** `config.py`, `run.py`, `api/deps.py`, `api/app.py`, `api/stock_routes.py`, `api/pos_routes.py`, `api/customer_routes.py`, `api/report_routes.py`, `frontend/js/api-client.js`, `frontend/js/app.js`.

**Kriteria selesai:**
- Dari perangkat lain di LAN, `GET /api/customers` tanpa token → 401/403.
- `POST /api/stock` tanpa token → 401.
- `POST /api/pos/transaction` tanpa token dan tanpa header khusus → 401/403.
- `GET /docs` di `APP_ENV=production` → 404.
- `GET /api/config` tidak memuat `chat_id` penuh.
- 6 percobaan token salah berturut-turut → 429.

**Uji baru:**
- `test_semua_endpoint_mutasi_wajib_token`
- `test_lan_mode_menolak_baca_tanpa_token`
- `test_docs_nonaktif_di_produksi`
- `test_config_tidak_memuat_chat_id_penuh`
- `test_rate_limit_token_admin`

> Catatan: membatasi ke `127.0.0.1` tidak mengganggu rencana APK, karena WebView APK juga mengakses localhost. Akses dari HP lain di LAN harus menunggu autentikasi sesi/PIN (lingkup APK).

---

### P0-2 · Idempotensi transaksi POS (B-02, L-02)

**Masalah:** retry setelah timeout menghasilkan nota kedua dan potong stok kedua.

**Langkah:**
1. Tambah kolom `client_request_id` (`String(64)`, nullable, **unique**) pada `service_records` + migrasi ringan di `database/session.py`.
2. `CreateServiceTransactionRequest` menerima `client_request_id: Optional[str]` (UUID v4, panjang 36/64).
3. Di `pos_service.create_transaction`, sebelum membuat record: bila `client_request_id` sudah ada, kembalikan record yang ada (tanpa memotong stok) dengan penanda `duplicate=True` pada respons.
4. Frontend membuat satu UUID **per percobaan simpan** dan memakainya ulang di seluruh retry:

```js
// app.js — sekali per klik simpan, bukan per request
const requestId = crypto.randomUUID();
// loop retry stok-minus memakai requestId yang sama
```

5. Jangan membuat UUID baru setelah error jaringan; buat baru hanya setelah sukses atau setelah pengguna mengubah isi transaksi.
6. Respons duplikat tetap menampilkan struk yang sudah ada, dengan toast "Nota ini sudah tersimpan".

**Berkas:** `database/models.py`, `database/session.py`, `api/schemas.py`, `services/pos_service.py`, `api/pos_routes.py`, `frontend/js/app.js`, `frontend/js/api-client.js`.

**Kriteria selesai:**
- Dua POST dengan `client_request_id` sama → hanya 1 baris `service_records`, stok berkurang 1×, kedua respons menunjuk nota yang sama.
- POST tanpa `client_request_id` tetap berfungsi (kompatibilitas).
- Timeout yang disimulasikan (server commit lalu koneksi diputus) + retry → tidak ada duplikat.

**Uji baru:**
- `test_transaksi_idempoten_dengan_request_id_sama`
- `test_request_id_berbeda_tetap_membuat_nota_baru`
- `test_idempoten_tidak_memotong_stok_dua_kali`

---

### P0-3 · Nomor nota aman dari balapan (B-01)

**Masalah:** dua transaksi paralel menghasilkan `no_nota` sama → 500.

**Langkah (pilih satu):**
- **Opsi A (disarankan):** tabel `nota_counter(tanggal DATE PRIMARY KEY, nomor_terakhir INT)`; alokasi memakai `UPDATE ... SET nomor_terakhir = nomor_terakhir + 1 ... RETURNING` di dalam transaksi yang sama. SQLite menserialisasi penulis sehingga aman.
- **Opsi B:** pertahankan `_next_nota` tetapi bungkus `create_transaction` dengan retry 3–5 kali khusus `IntegrityError` pada `service_records.no_nota`; setiap retry memulai transaksi baru dan menghitung ulang nomor.

Terapkan pola yang sama pada `_next_radiator_label()` (`services/customer_service.py:48-59`) dan tambahkan unique index pada `vehicle_or_units.label_radiator` (setelah memastikan tidak ada duplikat lama).

**Berkas:** `services/pos_service.py`, `services/customer_service.py`, `database/models.py`, `database/session.py`.

**Kriteria selesai:**
- Uji paralel 2–10 request → semua 201, semua `no_nota` unik, jumlah baris = jumlah request.
- Tidak ada respons 500 akibat `UNIQUE constraint failed: service_records.no_nota`.

**Uji baru:**
- `test_nota_unik_saat_transaksi_paralel` (thread + barrier, seperti probe I)
- `test_label_radiator_unik_saat_paralel`

---

### P0-4 · Hentikan kebocoran token di salinan keamanan restore (B-03, S-05)

**Masalah:** `backups/sebelum_restore_*.db` memuat token bot mentah.

**Langkah:**
1. Setelah `shutil.copy2(target, safety)`, panggil `_redact_secrets(safety)` (`services/backup_service.py:122-127`).
2. Batasi izin folder `backups/` (POSIX `chmod 700`; di Windows, dokumentasikan agar folder tidak dibagikan).
3. Pertimbangkan menyimpan token di luar database (mis. file kredensial terpisah yang di-ignore) agar database dapat dibagikan tanpa risiko. Minimal: pastikan **semua** file `*.db` di `backups/` teredaksi.

**Kriteria selesai:**
- Setelah restore, `grep` token pada seluruh file di `BACKUP_DIR` → tidak ditemukan.
- Backup manual dan backup Telegram tetap tanpa token.

**Uji baru:**
- `test_salinan_sebelum_restore_tidak_memuat_token`
- `test_semua_file_backup_teredaksi`

---

### P0-5 · Restore aman: kunci global + pertahankan konfigurasi (B-05, B-04, L-01)

**Masalah:** restore dapat menghapus transaksi yang sedang/baru disimpan; restore backup teredaksi mematikan backup otomatis.

**Langkah:**
1. Tambah `threading.Lock` modul-level di `services/backup_service.py` dan flag `MAINTENANCE` yang dibaca middleware. Selama restore: semua request `/api/*` (kecuali health) dibalas **503** dengan pesan "Database sedang dipulihkan".
2. Urutan restore yang benar:
   - ambil kunci;
   - set maintenance;
   - tunggu request aktif selesai (atau tolak request baru);
   - salinan keamanan + redaksi (P0-4);
   - validasi file (sudah ada);
   - `engine.dispose()` → ganti file → `init_db()` → verifikasi cepat (`SELECT COUNT(*)` pada tabel inti);
   - pulihkan konfigurasi Telegram dari memori (token/jam/enabled) bila hasil restore tidak memilikinya;
   - lepas maintenance & kunci di `finally`.
3. Tolak restore kedua saat restore pertama berjalan (409).
4. UI: konfirmasi eksplisit bahwa semua tab lain harus ditutup; tampilkan status "memulihkan" dan nonaktifkan tombol.
5. Untuk koreksi transaksi (L-01), jangan gunakan restore. Tambahkan mekanisme void terpisah (P1-5). Sampai itu ada, dokumentasikan di UI bahwa restore **bukan** alat koreksi.

**Kriteria selesai:**
- Request POS yang dikirim saat restore berlangsung → 503, tidak ada baris "setengah jadi".
- Setelah restore backup teredaksi: `telegram.configured=true` bila token sebelumnya ada, `enabled` tidak berubah.
- Restore kedua saat proses berjalan → 409.
- Tidak ada file `*.restore.tmp` tertinggal.

**Uji baru:**
- `test_restore_menolak_request_selama_maintenance`
- `test_restore_mempertahankan_konfigurasi_telegram`
- `test_restore_bersamaan_ditolak`

---

### P0-6 · Perbaiki laporan "Seluruhnya" (B-08)

**Masalah:** frontend berhenti pada blok 366 hari pertama yang kosong.

**Langkah:**
1. **Opsi A (disarankan):** tambah endpoint `GET /api/reports/all-time` yang mengagregasi seluruh data di server (satu query) dan mengembalikan ringkasan + rekap harian + daftar transaksi (dengan paginasi).
2. **Opsi B (perbaikan minimal):** ubah `loadAllTimePeriod()` agar **melanjutkan** melewati blok kosong sampai tanggal transaksi paling awal. Tanggal paling awal bisa diperoleh dari endpoint kecil `GET /api/reports/first-date` (atau dari `service-records?limit=1&order=asc`).
3. Hentikan perulangan berdasarkan tanggal, bukan berdasarkan blok kosong; batasi maksimum iterasi (mis. 200 tahun) sebagai pengaman.

**Kriteria selesai:**
- Data 2019 + 2026: laporan "Seluruhnya" menampilkan total kedua periode.
- Data hanya 2026: tidak ada request berlebihan (maksimum 1–2 panggilan).

**Uji baru:**
- `test_laporan_all_time_melewati_tahun_kosong` (data 2019 + 2026)
- `test_laporan_all_time_tanpa_data`

---

### P0-7 · Bersihkan file backup (B-07, B-15, L-08)

**Masalah:** file backup menumpuk; file gagal kirim tertinggal; dua pengiriman bersamaan; nama file Telegram bisa sama.

**Langkah:**
1. Tambah kebijakan retensi: simpan 14 backup terbaru + 1 backup per bulan selama 12 bulan (konfigurasi `BACKUP_KEEP`), hapus sisanya setelah backup baru berhasil dibuat.
2. Hapus file sementara bila pengiriman Telegram gagal (dengan tetap mencatat error).
3. Tambah `threading.Lock` pada `send_backup()` agar penjadwal dan tombol manual tidak berjalan bersamaan.
4. Sertakan jam/menit pada nama file Telegram (mis. `bengkel_radiator_20260901-20261030_2100.db`) atau tambahkan penomoran bila nama sudah ada.
5. Pastikan file yang dihapus tidak sedang dikirim (hapus setelah respons sukses).

**Kriteria selesai:**
- Setelah 20 kali backup, jumlah file ≤ batas retensi.
- Gagal kirim → tidak ada file baru tertinggal.
- Kirim manual 2× berturut-turut → dua nama file berbeda, tidak ada proses paralel.

**Uji baru:**
- `test_retensi_backup_membatasi_jumlah_file`
- `test_backup_gagal_tidak_meninggalkan_file`
- `test_kirim_bersamaan_diserialkan`
- `test_nama_file_telegram_unik_per_kiriman`

---

## 2. Fase 1 — Sebelum pemakaian harian skala penuh

### P1-1 · Seed hanya sekali (B-06)
**Langkah:** tambah `app_settings['seed.version']`; `seed_defaults()` hanya berjalan bila kunci belum ada. Setelah restore, jangan seed ulang bila database hasil restore sudah pernah di-seed. Alternatif: seed hanya saat file database baru dibuat.
**Kriteria:** hapus seluruh stok/jasa → restart → tetap kosong; database baru → terisi 12/10.
**Uji:** `test_seed_tidak_menghidupkan_master_yang_dihapus`, `test_seed_hanya_sekali_setelah_restore`.

### P1-2 · Versi skema pada backup & restore (L-05)
**Langkah:** tabel `app_meta(key, value)` berisi `schema_version` dan `app_version`; backup menyertakannya; restore menolak `schema_version` lebih baru dan memberi peringatan bila `app_settings` hilang (bukan menerima diam-diam). Tambah daftar tabel wajib `app_settings` (opsional, dengan peringatan).
**Kriteria:** backup versi lebih baru → 400 dengan pesan jelas; restore tanpa `app_settings` → 200 + peringatan di respons/UI.
**Uji:** `test_restore_menolak_skema_lebih_baru`, `test_restore_memberi_peringatan_tanpa_app_settings`.

### P1-3 · Tanggal transaksi bisa mundur (L-03)
**Langkah:** tambah field opsional `waktu_service` (datetime) pada payload; default `now`. Validasi: tidak boleh masa depan, tidak lebih dari 30 hari ke belakang (konfigurasi), wajib token admin bila bukan hari ini. Laporan memakai `waktu_service`. Nomor nota memakai tanggal transaksi (bukan tanggal sistem).
**Kriteria:** transaksi bertanggal kemarin masuk laporan kemarin; nomor nota mengikuti tanggal itu; UI menampilkan tanggal yang dipakai.
**Uji:** `test_transaksi_tanggal_mundur_masuk_laporan_harian_benar`, `test_tanggal_masa_depan_ditolak`.

### P1-4 · Audit trail & pengamanan master (L-04, L-06)
**Langkah:**
1. Tabel `stock_movements(id, stock_item_id, delta, alasan, ref_record_id, created_at)`; catat setiap penjualan, edit stok, dan opname.
2. Tabel `audit_log(id, entitas, entitas_id, aksi, data_sebelum, data_sesudah, created_at)` untuk perubahan harga/stok/pengaturan.
3. Tolak hapus stok/jasa yang sudah dipakai nota (409) atau ubah menjadi soft delete (`is_active=false`) sehingga master hilang dari pilihan tetapi riwayat tetap utuh.
4. Tampilkan riwayat pergerakan stok di halaman Stok.

**Kriteria:** hapus master yang dipakai → 409 (atau nonaktif); setiap penjualan menghasilkan 1 baris movement; perubahan harga tercatat di audit_log.
**Uji:** `test_hapus_stok_dipakai_nota_ditolak`, `test_penjualan_mencatat_stock_movement`, `test_edit_harga_tercatat_di_audit_log`.

### P1-5 · Void/koreksi transaksi (L-01)
**Langkah:** kolom `voided_at`, `void_reason`, `voided_by` pada `service_records`; endpoint `POST /api/service-records/{id}/void` (wajib token admin, hanya untuk nota yang belum di-void); stok dikembalikan lewat `stock_movements`; laporan dan struk menandai "DIBATALKAN"; nota tetap ada di database (tidak dihapus). Batasi waktu void (mis. 7 hari) atau wajib alasan.
**Kriteria:** nota void tidak dihitung di omset/laba; stok kembali; jejak siapa/kapan/alasan tersimpan; nota asli masih bisa dicetak dengan tanda void.
**Uji:** `test_void_mengembalikan_stok_dan_mengecualikan_laporan`, `test_void_wajib_alasan`, `test_void_ganda_ditolak`.

### P1-6 · Perbaikan laporan kecil (B-09, B-10, B-12)
**Langkah:**
1. Paginasi riwayat (`limit` + `offset`/cursor) dan tampilkan "menampilkan X dari Y".
2. `garansi_aktif` dihitung terhadap akhir periode (atau hapus dari rekap harian; tampilkan sekali di ringkasan periode).
3. Agregasi laporan periode dengan `GROUP BY date(waktu_service)` dan `func.sum`, bukan perulangan per hari; hitung garansi aktif satu kali.
**Kriteria:** 366 hari < 200 ms pada data seed; UI menyatakan batas riwayat; angka garansi konsisten dengan periode.
**Uji:** `test_riwayat_menyertakan_total_sebenarnya`, `test_garansi_aktif_mengikuti_periode`, `test_kinerja_laporan_setahun` (batas waktu longgar).

### P1-7 · Konfigurasi Telegram saat restore & pengaturan (B-04 lanjutan)
**Langkah:** setelah restore, bila `enabled=true` tetapi token kosong, tampilkan banner peringatan di halaman Pengaturan (bukan hanya teks status) dan tombol "Isi token". Jangan biarkan `enabled=true` tanpa token tersimpan sebagai keadaan normal.
**Kriteria:** restore backup tanpa token → banner jelas; menyimpan token → banner hilang.
**Uji:** `test_status_telegram_menandai_enabled_tanpa_token`.

---

## 3. Fase 2 — Peningkatan mutu

| ID | Perbaikan | Berkas utama | Kriteria |
|---|---|---|---|
| P2-1 (B-11) | Bulan garansi memakai kalender (tambah bulan dengan clamp akhir bulan); label struk menampilkan tanggal akhir atau jumlah bulan yang benar | `services/warranty_service.py`, `services/receipt_service.py` | 31 Jan + 1 bulan = 28/29 Feb; 12 bulan = 1 tahun kalender; test TC-13 diperbarui |
| P2-2 (B-13) | Cegah pelanggan duplikat: cek nomor HP ternormalisasi saat create, tawarkan "gunakan pelanggan yang ada"; unique index setelah data lama dirapikan | `services/customer_service.py`, `database/models.py` | Input nomor HP yang sama → 409 atau pilihan merge |
| P2-3 (B-14) | Part manual: wajib isi harga modal atau tandai laba "tidak diketahui"; jangan diam-diam menghitung 0 | `services/pos_service.py`, `api/schemas.py`, `services/report_service.py` | Laporan menampilkan kelompok "part tanpa modal" |
| P2-4 (L-07) | Backfill `harga_modal` hanya sekali (migration version), tidak setiap startup | `database/session.py` | Restart tidak mengubah laba historis; test snapshot |
| P2-5 (S-02) | Opsional HTTPS lokal atau panduan reverse proxy; token admin minimal 24 karakter acak; rotasi token terdokumentasi | `.env.example`, dokumentasi | Token lama tidak berlaku setelah rotasi |
| P2-6 (S-07) | PIN/lock screen (lingkup APK, sudah dispesifikasikan terpisah) | APK | Sesuai spesifikasi PIN 6 digit |
| P2-7 (B-15) | Nama file backup memuat waktu kirim | `services/telegram_backup_service.py` | Dua kiriman sehari → nama berbeda |

---

## 4. Uji yang harus ditambahkan (ringkasan)

| Test | Menutup |
|---|---|
| `test_semua_endpoint_mutasi_wajib_token` | S-01 |
| `test_rate_limit_token_admin` | S-02 |
| `test_docs_nonaktif_di_produksi` | S-03 |
| `test_config_tidak_memuat_chat_id_penuh` | S-04 |
| `test_transaksi_idempoten_dengan_request_id_sama` | B-02 / L-02 |
| `test_idempoten_tidak_memotong_stok_dua_kali` | B-02 |
| `test_nota_unik_saat_transaksi_paralel` | B-01 |
| `test_salinan_sebelum_restore_tidak_memuat_token` | B-03 |
| `test_restore_mempertahankan_konfigurasi_telegram` | B-04 |
| `test_restore_menolak_request_selama_maintenance` | B-05 |
| `test_seed_tidak_menghidupkan_master_yang_dihapus` | B-06 |
| `test_retensi_backup_membatasi_jumlah_file` | B-07 |
| `test_laporan_all_time_melewati_tahun_kosong` | B-08 |
| `test_riwayat_menyertakan_total_sebenarnya` | B-09 |
| `test_garansi_aktif_mengikuti_periode` | B-10 |
| `test_garansi_kalender_bulan_penuh` | B-11 |
| `test_hapus_stok_dipakai_nota_ditolak` | L-04 |
| `test_void_mengembalikan_stok_dan_mengecualikan_laporan` | L-01 |
| `test_restore_menolak_skema_lebih_baru` | L-05 |
| `test_penjualan_mencatat_stock_movement` | L-06 |
| `test_backfill_modal_tidak_berubah_setelah_restart` | L-07 |
| `test_kirim_bersamaan_diserialkan` | L-08 |

Target: seluruh test lama (64) tetap lulus + test baru di atas lulus. Jalankan:

```bash
./.venv/Scripts/python.exe -m pytest -q
```

---

## 5. Urutan kerja dan ketergantungan

```
P0-4 (redaksi salinan)  ─┐
P0-5 (restore aman)     ─┼─> P0-1 (auth)  ─> uji LAN tertutup
P0-2 (idempotensi)      ─┤
P0-3 (nota)             ─┘
P0-6 (laporan all-time)  ─> P1-6 (paginasi/agregasi)
P0-7 (retensi backup)    ─> P1-2 (versi skema)
P1-1 (seed)              ─> P1-5 (void) ─> P1-4 (audit trail)
```

Urutan yang disarankan: **P0-4 → P0-5 → P0-2 → P0-3 → P0-1 → P0-6 → P0-7**, lalu Fase 1, lalu Fase 2.

Alasan urutan:
- P0-4/P0-5 lebih dulu karena menyangkut kehilangan data dan rahasia, dan tidak bergantung pada perubahan API.
- P0-2/P0-3 menyentuh jalur transaksi; lakukan sebelum menambah field tanggal (P1-3) agar konflik migrasi minimal.
- P0-1 mengubah semua klien; lakukan setelah jalur transaksi stabil agar uji E2E tidak bercampur dua variabel.
- P1-5 (void) bergantung pada `stock_movements` (P1-4) dan pada idempotensi (P0-2).

---

## 6. Risiko perubahan dan mitigasi

| Perubahan | Risiko | Mitigasi |
|---|---|---|
| Wajib token di semua endpoint | Frontend lama gagal (401) | Rilis backend + frontend bersamaan; sediakan `ADMIN_TOKEN` sekali isi di sesi; uji E2E di 360/768/1024 px |
| Idempotency key | Nota lama tanpa key tidak terpengaruh | Kolom nullable + unique; hanya aktif bila key dikirim |
| Ganti generator nota | Nomor melompat/berubah format | Format `INV-YYYYMMDD-XXXX` dipertahankan; uji nomor berurutan |
| Restore maintenance | Restore gagal di tengah | Salinan keamanan + verifikasi + `finally` melepas kunci; jangan hapus salinan keamanan |
| Retensi backup | Menghapus file yang masih dibutuhkan | Simpan 14 terbaru + 12 bulanan; hapus hanya setelah backup baru sukses |
| Void transaksi | Laporan historis berubah | Tandai void, jangan hapus; tampilkan di detail; uji laporan sebelum/sesudah |
| Bulan garansi kalender | Nota lama tetap 30 hari | Hanya berlaku untuk transaksi baru; dokumentasikan |

**Rollback:** setiap perubahan skema harus aditif (kolom/tabel baru, bukan rename/drop). Bila terjadi masalah, cukup kembalikan kode; database tetap kompatibel karena kolom baru nullable.

---

## 7. Definition of done

- [ ] Semua item Fase 0 selesai dan test barunya lulus.
- [ ] `pytest -q` ≥ 64 test lama + test baru, semuanya lulus.
- [ ] Uji manual: transaksi ganda (dua tab), restore saat transaksi berjalan, restore backup tanpa token, laporan lintas tahun, hapus master yang dipakai.
- [ ] Tidak ada token bot/admin di file backup mana pun (`grep` pada `backups/`).
- [ ] `GET /api/customers` dari IP LAN tanpa token → 401.
- [ ] Dokumen ini dan laporan audit diperbarui bila ada temuan baru saat implementasi.
- [ ] Token bot Telegram yang dipakai saat uji **dirotasi** di @BotFather dan pesan backup lama dihapus (tindakan pengguna, di luar kode).

---

## 8. Estimasi indikatif

| Fase | Isi | Estimasi |
|---|---|---|
| Fase 0 | 7 item (auth, idempotensi, nota, restore, redaksi, laporan, retensi) | 2–3 hari kerja |
| Fase 1 | 7 item (seed, skema, tanggal, audit/void, laporan kecil) | 3–4 hari kerja |
| Fase 2 | 7 item (kalender garansi, dedupe, laba part manual, migrasi, HTTPS, PIN APK, nama file) | 3–5 hari kerja |

Estimasi bersifat indikatif dan belum termasuk pengujian perangkat/printer fisik.
