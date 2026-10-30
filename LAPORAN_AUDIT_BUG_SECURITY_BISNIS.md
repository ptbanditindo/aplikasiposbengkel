# Laporan Audit — Bug, Security, dan Logika Bisnis
**Aplikasi:** BengkelPOS Radiator v2.0
**Tanggal audit:** 30 Oktober 2026
**Sifat audit:** Read-only (tidak ada kode aplikasi yang diubah)
**Cakupan:** seluruh backend (`api/`, `services/`, `repositories/`, `database/`, `config.py`, `run.py`), seluruh frontend (`frontend/index.html`, `frontend/js/app.js`, `frontend/js/api-client.js`, `frontend/css/style.css`), test suite, `.env.example`, `.gitignore`

---

## 1. Jawaban singkat atas tiga pertanyaan

| Pertanyaan | Jawaban | Jumlah temuan |
|---|---|---|
| Apakah ada bug? | **Ya** | 15 temuan (3 Tinggi, 5 Sedang, 7 Rendah) |
| Apakah ada kegagalan security? | **Ya** | 8 temuan (1 Kritis, 1 Tinggi, 4 Sedang, 2 Rendah) |
| Apakah ada kecacatan logika bisnis yang bisa membuat database **tidak tercatat**? | **Ya** | 8 temuan; 3 di antaranya berpotensi langsung membuat transaksi hilang atau ganda |

Tiga temuan yang paling relevan dengan kekhawatiran "database tidak tercatat":

1. **B-05 / L-01** — Restore database saat aplikasi sedang dipakai dapat menghapus transaksi yang baru saja tersimpan (file database diganti di tengah operasi).
2. **B-02 / L-02** — Tidak ada idempotensi: satu transaksi yang dikirim ulang (retry setelah timeout, atau dua klik) tercatat **dua kali** dan memotong stok dua kali.
3. **B-01** — Dua transaksi bersamaan menghasilkan nomor nota yang sama; salah satunya gagal dengan HTTP 500 dan tidak tersimpan.

Selain itu **B-08** adalah kasus "sudah tercatat tetapi tidak terlihat": data lebih lama dari 1 tahun tidak muncul di laporan "Seluruhnya" karena frontend berhenti pada blok 366 hari pertama yang kosong.

---

## 2. Metode dan lingkungan audit

**Statis**
- Membaca seluruh file sumber satu per satu (bukan sampling), termasuk skema Pydantic, model SQLAlchemy, repository, service, router, runner, frontend SPA, dan test.
- Menelusuri pola berisiko: autentikasi per endpoint, transaksi database, pembuatan nomor unik, penanganan file, query dinamis, escaping HTML, penyimpanan rahasia.

**Dinamis (tanpa menyentuh data produksi)**
- Test suite: `./.venv/Scripts/python.exe -m pytest -q` → **64 passed**.
- Probe API/DB pada database sementara (`%TEMP%\bengkel_audit_*`), server uvicorn di `127.0.0.1:8011`, `BACKUP_DIR` sementara. Database produksi `data/bengkel_radiator.db` tidak digunakan.
- Probe mencakup: akses tanpa token, pengiriman ganda, hapus stok yang sudah dipakai, stok kurang, seed ulang, kebocoran token di file backup, restore lintas skema, penumpukan file, balapan nomor nota (dua thread dengan barrier), garansi 12 bulan, dan data lintas tahun.

**Batasan**
- Tidak dilakukan pengujian destruktif terhadap data produksi.
- Restore-saat-transaksi-berjalan (B-05) dan CSRF (S-06) dianalisis dari kode, bukan diuji serangan.
- APK/Android belum ada di repo ini (sesuai keputusan: build APK ditunda), sehingga audit PIN/Android tidak termasuk.

---

## 3. Temuan BUG

### B-01 — Balapan nomor nota: transaksi kedua gagal (HTTP 500) dan tidak tersimpan
**Severity: Tinggi** · `services/pos_service.py:40-48`, `services/pos_service.py:174`, `repositories/service_record_repository.py:59-61`, `database/models.py:110`

`_next_nota()` membaca seluruh nota berawalan `INV-YYYYMMDD-` lalu menambah 1, tanpa penguncian. Dua request yang berjalan bersamaan membaca nilai tertinggi yang sama dan menghasilkan nomor identik; kolom `no_nota` unik, sehingga `db.flush()` melempar `IntegrityError` dan request kedua berakhir 500.

Bukti probe I (dua transaksi paralel, barrier pada `nota_prefix_exists`):
```
status=[201, 500], nota tersimpan=1, nomor nota=['INV-20261030-0001']
```
Dampak: kasir melihat error, transaksi tidak tercatat, harus input ulang. Jika error terjadi setelah struk tercetak dari sisi klien (tidak terjadi saat ini karena struk dibangun dari respons server), risiko salah catat lebih besar. Pola yang sama ada pada `_next_radiator_label()` (`services/customer_service.py:48-59`) yang dapat menghasilkan label radiator ganda karena `label_radiator` tidak unik.

### B-02 — Tidak ada idempotensi transaksi: kirim ganda menghasilkan dua nota
**Severity: Tinggi** · `api/pos_routes.py:24-38`, `services/pos_service.py:51`, `frontend/js/app.js:1165-1243`, `frontend/js/api-client.js:110-115`

Tidak ada idempotency key maupun deteksi duplikat. Payload identik yang dikirim dua kali membuat dua nota dan memotong stok dua kali.

Bukti probe B:
```
payload identik dikirim 2x -> 201/201, nota tersimpan=2
(INV-20261030-0001 / INV-20261030-0002), stok SP-003=25 -> 23
```
Pemicu nyata di lapangan: koneksi lokal putus/timeout setelah server commit (`api-client.js:38-47` melempar "Tidak dapat menghubungi server"), kasir mengulang simpan, lalu ada dua nota untuk satu servis. Guard `state.saving` (`app.js:1166`) hanya mencegah klik ganda di tab yang sama; tidak mencegah retry, refresh, atau dua perangkat.

### B-03 — Salinan keamanan sebelum restore menyimpan token bot mentah
**Severity: Tinggi (kebocoran rahasia)** · `services/backup_service.py:122-127`

`restore_backup()` menyalin database aktif ke `backups/sebelum_restore_*.db` memakai `shutil.copy2` **tanpa** `_redact_secrets()`. File backup normal sudah diredaksi (`backup_service.py:35-51, 74`), tetapi salinan keamanan ini tidak.

Bukti probe F:
```
token di file backup (harus kosong) = ''
file di backup dir yang memuat token mentah: ['sebelum_restore_20261030_193343.db']
```
Dampak: token bot Telegram tersimpan plaintext di folder `backups/`. Siapa pun yang membaca folder itu (atau menyalinnya untuk pindah perangkat) dapat mengendalikan bot dan mengunduh seluruh backup database.

### B-04 — Restore dari backup teredaksi menghapus konfigurasi Telegram (backup otomatis berhenti diam-diam)
**Severity: Sedang** · `services/backup_service.py:47`, `services/settings_service.py:112-126`, `services/telegram_backup_service.py:105-112`

Karena backup selalu mengosongkan `telegram.bot_token`, memulihkan database dari backup (alur yang justru dianjurkan saat pindah perangkat) membuat `telegram.configured=false` sementara `telegram.enabled` tetap `1`.

Bukti probe G:
```
restore file hasil backup (token teredaksi) -> 200,
token tersimpan='', telegram.configured=False, enabled=True
```
Dampak: backup otomatis berhenti tanpa error; pemilik hanya melihat teks status "Bot token dan chat ID belum lengkap" (`app.js` `renderTelegramStatus`). Jika tidak segera mengisi ulang token, tidak ada backup terjadwal.

### B-05 — Restore saat aplikasi aktif berisiko menghilangkan transaksi yang sedang/baru disimpan
**Severity: Tinggi** · `services/backup_service.py:120-131`, `api/report_routes.py:82-89`

Urutan restore: `engine.dispose()` → `shutil.move(temp, target)` → `init_db()` → `seed_defaults()`. Tidak ada kunci global, mode maintenance, atau penolakan request selama restore.

- Request POS yang sudah memegang koneksi SQLite ke file lama dapat commit ke file yang sudah diganti (di POSIX file lama tetap hidup sampai handle ditutup) sehingga barisnya hilang dari database yang dipakai setelah restore.
- Di Windows, `shutil.move` atas file yang masih dibuka proses lain dapat gagal `PermissionError`; respons menjadi 500 dan aplikasi berjalan dengan engine yang sudah di-dispose.
- Dua request restore bersamaan memakai path sementara yang sama (`<db>.restore.tmp`).

Dampak langsung: **transaksi tercatat lalu hilang**, atau restore gagal di tengah dan aplikasi perlu restart. Ini temuan paling dekat dengan skenario "database tidak tercatat" yang ditanyakan.

### B-06 — Master yang sengaja dihapus hidup kembali (seed setiap start dan setiap restore)
**Severity: Sedang** · `database/seed.py:43-68`, `api/app.py:53-57`, `services/backup_service.py:133-136`

`seed_defaults()` menambahkan 12 sparepart dan 10 tarif jasa setiap kali tabel kosong, dan dipanggil pada setiap startup serta setelah restore.

Bukti probe E:
```
setelah master dikosongkan lalu seed_defaults: stok=12, jasa=10
```
Dampak: pemilik tidak bisa benar-benar mengosongkan katalog (mis. memulai inventaris dari nol atau menghapus master lama); data yang dihapus muncul lagi setelah restart dan ikut terhitung di laporan/stok.

### B-07 — File backup menumpuk tanpa pembersihan; backup gagal pun meninggalkan file
**Severity: Sedang** · `services/backup_service.py:54-75`, `services/telegram_backup_service.py:117-132`

Setiap backup membuat file baru `bengkel_radiator_<timestamp>.db`; tidak ada retensi/rotasi. Pada pengiriman Telegram, file dibuat **sebelum** cek ukuran 50 MB dan tidak dihapus bila pengecekan atau pengiriman gagal.

Bukti probe H:
```
file backup bertambah=2, total file=5, total ukuran=460 KB (tanpa pembersihan otomatis)
```
Pada pemakaian harian, ukuran folder `backups/` tumbuh linear terhadap jumlah hari (dan jumlah percobaan gagal). Untuk perangkat dengan penyimpanan terbatas ini berisiko memenuhi disk, yang pada akhirnya bisa menggagalkan penulisan SQLite.

### B-08 — Laporan "Seluruhnya" berhenti di celah > 1 tahun; data lama tidak tampil
**Severity: Sedang** · `frontend/js/app.js:2347-2361`, `api/report_routes.py:28-39`

`loadAllTimePeriod()` memotong riwayat menjadi blok 366 hari dan **berhenti pada blok pertama yang kosong**. Jika ada transaksi 2019 lalu tidak ada aktivitas sampai 2026, blok 2024–2025 kosong → perulangan berhenti → data 2019 tidak pernah diambil.

Bukti probe K (data 2019 + 2026):
```
chunk terbaru transaksi=1, chunk setahun sebelumnya transaksi=0
(frontend berhenti pada chunk kosong pertama)
```
Dampak: total omset/laba pada periode "Seluruhnya" lebih kecil dari kenyataan; data ada di database tetapi tidak terlihat. Ini bukan kehilangan data, tetapi **laporan salah** dan mudah disalahartikan sebagai data hilang.

### B-09 — Riwayat dibatasi 200 nota tanpa penjelasan
**Severity: Rendah** · `repositories/service_record_repository.py:17-40`, `api/pos_routes.py:41-50`, `frontend/js/app.js:1575`

`list_records` default `limit=200`; UI menampilkan `"<n> nota"` dari panjang array yang dikembalikan, bukan total sebenarnya. Setelah 200 nota, nota lama "hilang" dari daftar tanpa penanda. Pencarian masih bisa menemukan, tetapi pengguna tidak tahu harus mencari.

### B-10 — `garansi_aktif` bersifat global, bukan per periode/hari
**Severity: Rendah** · `services/report_service.py:52-60`, `services/report_service.py:87-108`

`_summarize_records()` menghitung `garansi_aktif` dari seluruh tabel dengan syarat `garansi_sampai >= hari ini`, tanpa memfilter rentang laporan. Akibatnya chip "Garansi aktif" pada laporan bulan lalu menampilkan angka hari ini, dan setiap baris rekap harian menampilkan angka global yang sama.

### B-11 — Bulan garansi dihitung 30 hari; label struk membulatkan bulan
**Severity: Rendah** · `services/warranty_service.py:18-33`, `services/receipt_service.py:15-20`

`base + timedelta(days=30 * months)` membuat 12 bulan = 360 hari (bukan 365) dan 1 bulan dari 31 Januari = 2 Maret, bukan 28 Februari. Label struk menghitung `round(days/30)`, sehingga garansi kustom (mis. 45 hari) tercetak "(2 Bulan)".

Bukti probe J:
```
garansi 1 bulan=2026-11-29 (30 hari),
12 bulan=2027-10-25 (360 hari; kalender 365 hari)
```
Catatan: test `test_tc13_garansi_satu_bulan_tepat_30_hari` mengunci perilaku ini, jadi perubahan harus disertai pembaruan test dan keputusan bisnis.

### B-12 — Kinerja laporan periode: query per hari + filter O(n × hari)
**Severity: Rendah** · `services/report_service.py:87-108`

Untuk rentang 366 hari: satu query `records_between` + 366 kali `_summarize_records` (masing-masing menjalankan query `active_warranty` ke database) + pemfilteran daftar penuh per hari. Pada perangkat rendah (target aplikasi kasir lokal) laporan setahun bisa terasa lambat dan membebani SQLite.

### B-13 — Pelanggan duplikat diizinkan
**Severity: Rendah** · `services/customer_service.py:17-29`, `database/models.py:34-36`

Tidak ada pengecekan/unique constraint pada `nomor_hp`. Pelanggan sama dapat tercatat berkali-kali, sehingga riwayat servis terpecah dan laporan per pelanggan tidak lengkap.

### B-14 — Part yang tidak terhubung stok tidak menyumbang laba kotor
**Severity: Rendah** · `services/pricing_service.py:76-85`, `services/report_service.py:39-50`

Part yang diinput manual (tanpa `stock_item_id`) memiliki `harga_modal=None`; baris itu dilewati saat menghitung laba kotor, sehingga margin penjualan part manual tidak masuk laporan laba (laba kotor tampak lebih kecil).

### B-15 — Nama file backup Telegram bisa sama untuk beberapa kiriman di hari yang sama
**Severity: Rendah** · `services/telegram_backup_service.py:38-40`

Nama file ditentukan rentang tanggal data (`bengkel_radiator_<mulai>-<akhir>.db`, akhir = hari ini). Kirim manual dua kali pada hari yang sama menghasilkan dua dokumen dengan nama identik tetapi isi berbeda. Ini bertentangan dengan niat "satu file per rentang, tidak tumpang tindih" dan menyulitkan pemilik memilih file terbaru.

---

## 4. Temuan SECURITY

### S-01 — API terbuka untuk seluruh perangkat di jaringan lokal
**Severity: Kritis** · `config.py:91`, `run.py:12-27`, `api/stock_routes.py:24-47, 60-77`, `api/customer_routes.py:30-115`, `api/pos_routes.py:24-74`, `api/app.py:81-88`

`APP_HOST` default `0.0.0.0` sehingga server mendengarkan semua antarmuka. Hanya empat kelompok endpoint memakai `require_admin_token`: DELETE stok/jasa, seluruh `/api/settings/*`, `/api/admin/*`. Endpoint lain terbuka tanpa autentikasi.

Bukti probe A (tanpa token):
```
GET stock/records/customers/reports/config: 200/200/200/200/200
POST stock=201, POST jasa=201, PUT stock=200, DELETE stock=401, openapi=200
```
Dampak di jaringan bengkel/Wi-Fi rumah:
- siapa pun dapat membaca seluruh data pelanggan (nama, nomor HP, alamat, nopol) dan seluruh riwayat transaksi;
- siapa pun dapat mengubah harga jual/modal stok dan tarif jasa (POST/PUT tanpa token) — laporan laba dan struk berikutnya ikut berubah;
- siapa pun dapat membuat transaksi, memotong stok, dan **menandai klaim garansi** (`PUT /service-records/{id}/claim` tanpa token), sehingga klaim pelanggan yang sah bisa "dihanguskan";
- `is_low_stock` dan laporan kas dapat dipalsukan lewat transaksi fiktif.

CORS `localhost` (`app.py:81-88`) **bukan** kontrol keamanan di sini: klien non-browser (curl, script) tidak tunduk CORS, dan frontend yang diakses lewat IP LAN adalah same-origin.

### S-02 — Token admin dikirim lewat HTTP polos; tanpa pembatasan percobaan
**Severity: Tinggi** · `api/deps.py:11-37`, `frontend/js/app.js:2579-2591`, `frontend/js/api-client.js:93-108`

Token dikirim sebagai header `X-Admin-Token` pada HTTP tanpa TLS, sehingga dapat disadap di Wi-Fi yang sama. Tidak ada rate limit/lockout; token juga dimasukkan lewat `window.prompt` dan disimpan di `sessionStorage`, sehingga dapat dibaca ekstensi browser atau skrip same-origin.

### S-03 — Dokumentasi API terbuka
**Severity: Sedang** · `api/app.py:70-79`

`/openapi.json`, `/docs`, `/redoc` aktif di semua environment. Ini memetakan seluruh endpoint dan skema untuk penyerang di LAN (probe A: `openapi=200`). Tidak ada data rahasia di skema, tetapi mempermudah eksploitasi S-01.

### S-04 — `chat_id` pemilik bot terekspos tanpa autentikasi
**Severity: Sedang** · `api/app.py:125-145`, `api/schemas.py:329-335`, `services/settings_service.py:129-138`

`GET /api/config` (tanpa token) mengembalikan `telegram.chat_id`. Token bot tidak bocor (baik), tetapi ID akun pemilik adalah data pribadi dan cukup untuk mengirim pesan langsung ke pemilik bila bot diketahui.

### S-05 — Token bot tersimpan plaintext di database dan di salinan keamanan restore
**Severity: Sedang** · `services/settings_service.py:147-163`, `services/backup_service.py:122-127`

Token disimpan apa adanya di tabel `app_settings`. Backup normal diredaksi (baik), tetapi database aktif dan file `sebelum_restore_*.db` menyimpan token mentah (lihat B-03). Siapa pun yang dapat membaca folder aplikasi atau menyalin `data/*.db` dapat mengambil alih bot.

### S-06 — Potensi CSRF terhadap API lokal
**Severity: Sedang (analisis kode, belum diuji serangan)** · `api/pos_routes.py:24`, `api/customer_routes.py:54`, `api/app.py:81-88`

Endpoint yang mengubah data tidak mewajibkan header khusus/CSRF token. Halaman web berbahaya yang dibuka di browser mesin kasir dapat mengirim `POST` ke `http://127.0.0.1:8000/api/...` (request "simple" tanpa preflight); CORS memblokir pembacaan respons, tetapi **efek samping tetap terjadi**. Karena aplikasi kasir biasanya dibuka berdampingan dengan browser, ini perlu ditutup dengan kewajiban header kustom atau token sesi.

### S-07 — Tidak ada kunci layar/PIN pada aplikasi web
**Severity: Rendah (keputusan produk; PIN direncanakan untuk APK)** · `frontend/index.html`, `frontend/js/app.js`

Siapa pun yang memegang perangkat kasir dapat membuka aplikasi dan melihat/mengubah data. Catatan: spesifikasi PIN 6 digit yang diminta sebelumnya adalah lingkup APK dan belum diimplementasikan.

### S-08 — `.env` berisi token admin; pastikan tidak pernah dibagikan
**Severity: Rendah** · `.gitignore:2-6`, `.env.example`

`.env` sudah di-ignore dan hanya `.env.example` yang terlacak (baik). Namun token admin di `.env` adalah kredensial tunggal; jika folder aplikasi disalin ke perangkat lain (alur "upload database saat instal di perangkat berbeda"), file `.env` ikut membawa token yang sama.

---

## 5. Temuan LOGIKA BISNIS (fokus: data tidak tercatat / ganda / tidak terlihat)

### L-01 — Tidak ada void/koreksi transaksi; koreksi memaksa restore yang menghapus data setelahnya
**Severity: Tinggi** · `api/pos_routes.py` (tidak ada endpoint hapus/void), `services/backup_service.py:78-136`

Tidak ada endpoint untuk membatalkan, menghapus, atau mengoreksi `service_records`. Satu-satunya "koreksi" adalah restore database lama. Karena backup terbaru memuat seluruh data sampai hari ini, memilih backup sebelum kesalahan akan **menghapus semua transaksi sesudahnya** — persis kebalikan dari tujuan pencatatan. Ini juga alasan mengapa B-05 berbahaya: mekanisme koreksi satu-satunya adalah operasi berisiko tinggi.

### L-02 — Transaksi ganda akibat retry (lihat B-02)
**Severity: Tinggi** · `frontend/js/app.js:1203-1224`

Alur retry stok-minus aman (409 tidak menyimpan), tetapi tidak ada pembeda antara "gagal sebelum commit" dan "commit berhasil tetapi respons hilang". Tanpa idempotency key, retry manual menciptakan nota kedua yang sah secara database sehingga tidak bisa dibedakan dari transaksi asli.

### L-03 — Transaksi tidak bisa diberi tanggal mundur
**Severity: Sedang** · `services/pos_service.py:171-175`

`waktu_service` selalu `datetime.now()`. Servis yang baru dicatat besoknya akan masuk ke laporan kas hari pencatatan, bukan hari servis. Tidak ada input tanggal/jam transaksi, sehingga laporan harian bisa salah tanpa ada cara memperbaikinya (lihat L-01).

### L-04 — Tidak ada jejak audit perubahan stok/master; hapus stok yang dipakai nota tetap lolos
**Severity: Sedang** · `services/stock_service.py:72-106`, `database/models.py:180`, `services/pos_service.py:206-217`

- Tidak ada log siapa/kapan stok diubah atau dihapus; `PUT /api/stock/{id}` menimpa `jumlah` secara absolut sehingga selisih stok tidak dapat ditelusuri.
- Menghapus sparepart yang sudah dipakai nota berhasil (204). Foreign key `ON DELETE SET NULL` membuat `service_parts.stock_item_id` menjadi `NULL` secara diam-diam.

Bukti probe C:
```
hapus stok dipakai nota=204, struk=200,
service_parts stock_item_id=None, nama tetap='Tutup Radiator 0.9',
sold-parts=200/2
```
Struk dan laporan tetap benar (nama/harga/modal sudah snapshot — ini baik), tetapi tautan ke master hilang, sehingga master tidak bisa dihidupkan kembali dengan riwayat dan analisis per item kehilangan identitas.

### L-05 — Restore menerima database dari versi/skema lain tanpa penanda versi
**Severity: Sedang** · `services/backup_service.py:15-23, 89-118`

Validasi hanya: header SQLite, `PRAGMA integrity_check`, dan keberadaan 7 tabel wajib. Tidak ada pemeriksaan versi aplikasi/skema, jumlah kolom, atau asal file. Backup dari versi lama dapat dipulihkan dan perilakunya bergantung pada migrasi ringan `init_db()`; backup dengan `app_settings` hilang diterima tanpa peringatan (probe G).

### L-06 — Stok minus hanya lewat konfirmasi; tidak ada ledger pergerakan stok
**Severity: Rendah** · `services/pos_service.py:126-146, 219-221`

Pengurangan stok terjadi langsung pada kolom `jumlah` tanpa tabel pergerakan (masuk/keluar/opname). Stok minus diizinkan bila kasir mengonfirmasi (`izinkan_stok_minus`), dan nilai itu datang dari klien tanpa batasan tambahan. Tidak ada rekonsiliasi fisik vs sistem.

### L-07 — Backfill `harga_modal` saat startup dapat mengubah laba historis
**Severity: Rendah** · `database/session.py:63-93`

Setiap `init_db()` menjalankan `UPDATE service_parts SET harga_modal = (SELECT harga_modal FROM stock_items ...) WHERE harga_modal IS NULL`. Untuk nota lama (sebelum kolom ada atau setelah restore database lama), modal historis diisi dengan **harga modal master saat ini**, sehingga laba kotor masa lalu berubah mengikuti perubahan harga master. Snapshot untuk nota baru sudah benar (`pos_service.py:122`).

### L-08 — Backup terjadwal dan manual dapat berjalan bersamaan
**Severity: Rendah** · `services/telegram_backup_service.py:183-205`, `api/settings_routes.py:40-52`

Tidak ada lock antara `scheduler_loop()` dan tombol "Kirim sekarang". Dua pengiriman dapat terjadi pada menit yang sama (dua file, dua pesan, nama file sama — lihat B-15), serta menambah penumpukan file (B-07).

---

## 6. Yang sudah baik (terverifikasi, jangan dirusak saat perbaikan)

| Aspek | Bukti |
|---|---|
| Query parameterized (anti SQL injection) | seluruh repository memakai SQLAlchemy `select`/model; test `test_pencarian_tahan_sql_injection` lulus |
| Escaping XSS di frontend | `esc()` meng-escape `& < > " '` (`app.js:20-25`); `browserPrint` memakai `esc(text)` (`app.js:1401`); test `test_xss_payload_tersimpan_sebagai_teks_biasa` lulus |
| Token admin fail-closed | `api/deps.py:20-28` → 503 bila `UI_ACCESS_TOKEN` kosong; test `test_endpoint_admin_fail_closed_saat_token_belum_dikonfigurasi` lulus |
| Perbandingan token constant-time | `hmac.compare_digest` (`deps.py:31-33`) |
| Atomisitas transaksi POS | `with db.begin()` (`pos_service.py:55`); stok kurang → 409 dan tidak ada nota (probe D: `nota tersimpan=0, stok tidak berubah=True`) |
| Presisi uang | `Decimal` + `ROUND_HALF_UP` (`services/utils.py:48-50`); test presisi desimal lulus |
| Snapshot harga & modal di nota | `service_parts.harga_satuan/harga_modal` disalin saat transaksi (`pos_service.py:206-217`); test laba kotor historis lulus |
| Redaksi token di file backup normal | `_redact_secrets()` (`backup_service.py:35-51`); probe F: nilai token di file backup `''` |
| Validasi integritas saat restore | header SQLite + `PRAGMA integrity_check` + tabel wajib (`backup_service.py:80-118`) |
| Catch-up backup Telegram | `should_send()` mengirim segera setelah online bila jadwal terlewat (`telegram_backup_service.py:150-180`); test terkait lulus |
| Isolasi test | DB sementara + seed per test (`tests/conftest.py`); 64 test lulus |

---

## 7. Matriks prioritas

| ID | Temuan | Severity | Dampak utama | Perbaikan di |
|---|---|---|---|---|
| S-01 | API terbuka di LAN | Kritis | Baca/ubah seluruh data, transaksi & klaim garansi palsu | Fase 0 |
| B-02 / L-02 | Tanpa idempotensi | Tinggi | Nota & potong stok ganda | Fase 0 |
| B-05 / L-01 | Restore saat aktif / tanpa void | Tinggi | Transaksi hilang; koreksi menghapus data | Fase 0 |
| B-01 | Balapan nomor nota | Tinggi | Transaksi gagal 500 | Fase 0 |
| B-03 / S-05 | Token di salinan restore | Tinggi | Bot Telegram diambil alih | Fase 0 |
| S-02 | Token via HTTP + tanpa lockout | Tinggi | Token disadap/ditebak | Fase 0/1 |
| B-04 | Restore hapus konfigurasi Telegram | Sedang | Backup otomatis berhenti | Fase 0 |
| B-06 | Seed menghidupkan master | Sedang | Data terhapus kembali | Fase 1 |
| B-07 | Backup menumpuk | Sedang | Disk penuh | Fase 1 |
| B-08 | Laporan "Seluruhnya" terpotong | Sedang | Laporan salah | Fase 0 |
| L-03 | Tidak bisa tanggal mundur | Sedang | Laporan harian salah | Fase 1 |
| L-04 | Tanpa audit stok; hapus master | Sedang | Stok tak tertelusur | Fase 1 |
| L-05 | Restore tanpa versi skema | Sedang | DB tidak kompatibel | Fase 1 |
| S-03 / S-04 | Docs & chat_id terbuka | Sedang | Info untuk penyerang | Fase 1 |
| S-06 | Potensi CSRF | Sedang | Transaksi dari halaman asing | Fase 1 |
| B-09..B-15, L-06..L-08, S-07, S-08 | Rendah | UX/akurasi/performa | Fase 2 |

---

## 8. Lampiran — keluaran probe (ringkas)

```
[A] tanpa token -> GET stock/records/customers/reports/config: 200/200/200/200/200;
    POST stock=201, POST jasa=201, PUT stock=200, DELETE stock=401, openapi=200
[A] config memuat chat_id: True
[B] payload identik dikirim 2x -> 201/201, nota tersimpan=2,
    stok SP-003=25 (berkurang 2)
[C] hapus stok dipakai nota=204, struk=200, service_parts stock_item_id=None,
    nama tetap='Tutup Radiator 0.9', sold-parts=200/2
[D] stok kurang -> 409, nota tersimpan=0, stok tidak berubah=True
[E] setelah master dikosongkan lalu seed_defaults: stok=12, jasa=10
[F] token di file backup (harus kosong) = ''
[F] file di backup dir yang memuat token mentah: ['sebelum_restore_20261030_193343.db']
[G] restore backup lama tanpa app_settings -> 200, tabel app_settings dibuat ulang=1,
    telegram.configured=False
[G] restore file hasil backup (token teredaksi) -> 200, token tersimpan='',
    telegram.configured=False, enabled=True
[H] file backup bertambah=2, total file=5, total ukuran=460 KB
[I] dua transaksi bersamaan -> status=[201, 500], nota tersimpan=1,
    nomor nota=['INV-20261030-0001']
[J] garansi 1 bulan=2026-11-29 (30 hari), 12 bulan=2027-10-25 (360 hari)
[K] data 2019 + 2026: chunk terbaru transaksi=1, chunk setahun sebelumnya transaksi=0
```

**Catatan operasional:** database produksi `data/bengkel_radiator.db` saat audit belum memiliki tabel `app_settings` (tabel dibuat otomatis saat aplikasi dijalankan ulang). Artinya server produksi belum di-restart setelah fitur Pengaturan ditambahkan. Ini bukan bug kode, tetapi perlu diperhitungkan sebelum uji coba fitur backup/restore di produksi.
