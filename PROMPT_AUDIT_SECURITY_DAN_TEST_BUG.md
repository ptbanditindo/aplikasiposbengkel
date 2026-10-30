# PANDUAN & PROMPT AUDIT KEAMANAN, HARDENING & PENGUJIAN BUG (SECURITY & BUG HUNTING) — v2.0
## BengkelPOS Radiator: Sistem Kasir, Manajemen Servis Multi-Unit & Cetak Struk Bluetooth Thermal

Berkas ini dirancang untuk dijalankan **SETELAH seluruh kode aplikasi kasir, backend, dan antarmuka selesai dibangun**. 

Saat pengguna memberikan perintah:
> **"Lakukan security audit dan test bug menyeluruh lihat file PROMPT_AUDIT_SECURITY_DAN_TEST_BUG.md"**

AI akan bertindak sebagai **Principal Cybersecurity Auditor & QA Lead Automation Engineer** yang melakukan audit mendalam terhadap keamanan data, keutuhan finansial, penanganan unit tanpa nopol, pemotongan stok atomik, kompatibilitas pencetakan Bluetooth thermal, dan eksekusi 20 skenario uji otomatis (`TC-01` s/d `TC-20`).

---

## SALIN PROMPT DI BAWAH INI (UNTUK DIGUNAKAN SETELAH KODE SELESAI):

```markdown
Anda adalah Principal Cybersecurity Engineer, Code Auditor, dan Lead QA Automation Specialist untuk Sistem Point of Sale (POS) Bengkel.

Tugas Anda adalah melakukan SECURITY HARDENING, VULNERABILITY SCANNING, LOGIC AUDIT, dan BUG HUNTING secara menyeluruh terhadap seluruh codebase "BengkelPOS Radiator" di direktori kerja ini.

Acuan Baku Anda:
- PRD_BengkelPOS_Radiator.md (Spesifikasi Kebutuhan Baku v2.0)
- BLUEPRINT_EKSEKUSI_MANDIRI.md (Panduan Arsitektur & Direktori Baku v2.0)
- STATUS_PROYEK_DAN_SKEMA_IMPLEMENTASI.md (Master Pelacak Progres & Matriks Uji)

Lakukan 8 FASE AUDIT KETAT berikut secara mendalam, temukan setiap celah/bug, jalankan 20 skenario uji (`TC-01` s/d `TC-20`), dan langsung lakukan perbaikan kode (patching) sampai 100% aman dan stabil:

---

### FASE 1: AUDIT KEAMANAN KREDENSIAL & AKSES (.env & AUTH)
1. Pindai seluruh kode backend dan frontend:
   - Pastikan TIDAK ADA token atau secret key yang di-hardcode di kode Python atau JavaScript.
   - Seluruh rahasia dan identitas rekening bank bengkel wajib dimuat via variabel lingkungan (`.env`).
2. Periksa file `.gitignore`:
   - Pastikan berkas `.env`, basis data `*.db`, dan cache `__pycache__` terdaftar dan tidak ikut ter-commit ke git.
3. Proteksi Endpoint API:
   - Pastikan endpoint sensitif (seperti reset database, ekspor backup, hapus stok) dilindungi oleh validasi otentikasi token yang aman.

---

### FASE 2: AUDIT INTEGRITAS FINANSIAL & FLEKSIBILITAS HARGA DEAL (Ref: PRD FR-POS-03 s/d FR-POS-07)
1. Uji Pembulatan Desimal:
   - Pastikan semua perhitungan di backend menggunakan tipe data `decimal.Decimal` (Python) dan `Numeric(14, 2)` (SQLAlchemy).
   - Pastikan tidak ada bug floating point JavaScript (seperti `0.1 + 0.2 = 0.30000000000000004`).
2. Validasi Pembayaran CASH vs TRANSFER BANK (Ref: TC-10, TC-11, TC-12):
   - **CASH**: Pastikan sistem menolak transaksi jika uang bayar lebih kecil dari grand total (`TC-11`), dan kalkulasi kembalian selalu presisi: `kembalian = bayar - total_servis`.
   - **TRANSFER**: Pastikan uang bayar terkunci pas dengan total_servis, dan nilai kembalian mutlak bernilai 0 (`TC-12`).
3. Uji Fleksibilitas Harga Deal (Price Override & Master Preservation) (Ref: TC-06, TC-07):
   - Uji pembuatan transaksi kasir dengan harga jasa atau part yang dinaikkan atau diturunkan dari harga master data.
   - Pastikan transaksi berhasil tersimpan dengan harga deal yang disepakati, dan struk kasir mencetak harga deal tersebut.
   - Pastikan master data `stock_items.harga_jual` dan `harga_jasa.harga_standar` di gudang TIDAK BERUBAH/TERTIMPA.
   - Pastikan laporan laba kotor dihitung dari $(\text{Harga Jual Deal} - \text{Harga Modal Master})$.

---

### FASE 3: AUDIT TRANSAKSI & PEMOTONGAN STOK ATOMIK (Ref: PRD FR-POS-08, TC-08, TC-09)
1. Keutuhan Transaksi (*Atomicity*):
   - Pastikan operasi penyimpanan `ServiceRecord`, penambahan `ServiceJob`, `ServicePart`, dan pemotongan `stock_items` dibungkus dalam blok transaksi database tunggal (`with session.begin():`).
   - Simulasikan jika terjadi kegagalan di tengah jalan (misal error saat insert part), pastikan transaksi di-*rollback* secara utuh dan stok tidak berkurang secara siluman.
2. Pencegahan Stok Minus:
   - Uji skenario stok tinggal 1 lalu diminta 2 oleh kasir (`TC-09`). Pastikan sistem memberikan dialog validasi peringatan yang jelas.

---

### FASE 4: AUDIT LOGIKA KHUSUS BENGKEL RADIATOR (Ref: PRD FR-UNIT-04, FR-WAR-01 s/d FR-WAR-05)
1. Penanganan Unit "Bawa Radiator Saja" (Tanpa Nopol) (Ref: TC-05):
   - Uji pendaftaran unit servis di mana `nopol` bernilai NULL atau kosong.
   - Pastikan sistem TIDAK melempar error `IntegrityError` atau `NotNullConstraintViolation`.
   - Pastikan generator label otomatis (`RAD-YYYYMMDD-XXX`) menghasilkan kode yang konsisten, berurutan, dan unik.
2. Relasi 1 Pelanggan Banyak Mobil (Multi-Unit) (Ref: TC-03):
   - Uji pembuatan 3 kendaraan/radiator berbeda untuk 1 data pelanggan yang sama.
   - Pastikan riwayat servis masing-masing unit terisolasi dengan rapi dan dapat ditelusuri.
3. Logika Garansi & Masa Kedaluwarsa (Ref: TC-13, TC-14, TC-15, TC-16):
   - Uji pencatatan masa garansi servis (misal garansi 30 hari).
   - Simulasikan klaim dalam masa aktif (`TC-15`, harus lolos) vs klaim setelah tanggal kedaluwarsa lewat (`TC-16`, sistem wajib memberikan peringatan bahwa masa garansi telah habis).

---

### FASE 5: AUDIT DRIVER PRINTER BLUETOOTH THERMAL (ESC/POS) (Ref: PRD BAB 6 & FR-PRN-01 s/d FR-PRN-08)
1. Format Baris Kertas 58mm & 80mm (Ref: TC-17):
   - Periksa string template pada lebar 58mm: pastikan panjang baris tidak melebihi 32 karakter agar teks tidak terpotong acak ke baris baru.
   - Pastikan pemisah garis horizontal (`--------------------------------`) pas dengan lebar kertas.
2. Penanganan Karakter Khusus & Encoding:
   - Pastikan teks nama pelanggan, keluhan, dan jenis mobil disanitasi dari karakter emoji atau karakter UTF-8 non-ASCII yang dapat membuat printer thermal mengeluarkan karakter aneh (tulisan acak/sampah).
3. Transmisi Data Bluetooth (Chunking Buffer 50 Bytes) (Ref: FR-PRN-06):
   - Pastikan transmisi byte ESC/POS melalui Web Bluetooth API dikirim dalam ukuran paket terbagi (50 byte per chunk dengan jeda 25ms), mencegah printer thermal mengalami *buffer overflow* atau macet di tengah cetakan.
4. Pencantuman Rekening Bank Transfer (Ref: TC-18):
   - Pastikan Nama Bank, No. Rekening, dan Atas Nama dari `.env` tercetak jelas di bagian footer struk.
5. Fallback Handling:
   - Jika perangkat pengguna tidak mendukung Web Bluetooth, pastikan ada fallback ramah berupa dialog preview cetak browser standar (Print Dialog) (`FR-PRN-08`).

---

### FASE 6: AUDIT SANITASI INPUT & KEAMANAN WEB (XSS & INJECTION) (Ref: PRD NFR-SEC-01)
1. Sanitasi Input Teks:
   - Uji input nama pelanggan atau keluhan awal yang mengandung payload XSS (contoh: `<script>alert('hack')</script>`).
   - Pastikan antarmuka melakukan escape HTML sehingga script tidak tereksekusi di browser kasir.
2. Pencegahan SQL Injection:
   - Pastikan seluruh query pencarian (pencarian nopol, nama, riwayat servis) menggunakan SQLAlchemy Parameterized Queries atau ORM filter, bukan string formatting mentah (`f"SELECT * WHERE ..."`).

---

### FASE 7: AUDIT CADANGAN & PEMULIHAN DATABASE (BACKUP & DISASTER RECOVERY) (Ref: TC-20)
1. Integritas Backup SQLite:
   - Uji pembuatan berkas cadangan melalui fungsi backup (`/api/admin/backup`).
   - Pastikan berkas cadangan SQLite dapat dibuka, tidak korup, dan dapat dipulihkan (*restore*) ke kondisi semula dengan sempurna.

---

### FASE 8: EKSEKUSI PENGUJIAN OTOMATIS (20 TEST CASES) & AUTO-PATCHING
1. Jalankan seluruh unit & integration test:
   ```bash
   pytest tests/ -v
   ```
2. Pastikan 20 skenario uji baku (`TC-01` s/d `TC-20` dari PRD Bab 9) berstatus **PASSED**:
   - `TC-01`: Tambah Pelanggan Valid
   - `TC-02`: Normalisasi Nomor HP
   - `TC-03`: 1 Pelanggan Multi-Mobil
   - `TC-04`: Normalisasi Nopol Mobil
   - `TC-05`: Unit Radiator Copotan (`RAD-xxxx`)
   - `TC-06`: Jasa Harga Deal Di-override
   - `TC-07`: Part Harga Deal Di-override
   - `TC-08`: Servis Potong Stok Gudang Otomatis
   - `TC-09`: Peringatan Stok Minus / Habis
   - `TC-10`: Pembayaran CASH & Hitung Kembalian
   - `TC-11`: Pembayaran CASH Kurang Uang Ditolak
   - `TC-12`: Pembayaran TRANSFER (Kembalian = 0)
   - `TC-13`: Garansi Servis 1 Bulan Dihitung Tepat
   - `TC-14`: Servis Tanpa Garansi (`NULL`)
   - `TC-15`: Klaim Garansi Masa Aktif Berhasil
   - `TC-16`: Klaim Garansi Expired Diberi Peringatan
   - `TC-17`: Format Byte ESC/POS 58mm $\le$ 32 Karakter
   - `TC-18`: Rekening Bank Bengkel Tercetak di Struk
   - `TC-19`: Cetak Ulang Nota Lama (*Reprint*)
   - `TC-20`: Ekspor Backup Database SQLite
3. Catat seluruh temuan dalam format:
   - **ID Temuan**: (misal: SEC-01 / BUG-02)
   - **Tingkat Keparahan**: Critical / High / Medium / Low
   - **Deskripsi Bug**: Penjelasan lokasi file dan baris penyebab
   - **Perbaikan Langsung**: Kode patch yang telah diterapkan
4. Lakukan perbaikan langsung (*auto-patch*) terhadap setiap celah yang ditemukan hingga pengujian lulus 100%.
```
