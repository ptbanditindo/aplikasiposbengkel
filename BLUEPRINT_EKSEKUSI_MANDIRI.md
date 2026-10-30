# BLUEPRINT EKSEKUSI MANDIRI (AUTONOMOUS BUILD BLUEPRINT) — v2.0
## BengkelPOS Radiator: Sistem Kasir, Manajemen Servis Multi-Unit & Cetak Struk Bluetooth Thermal

Dokumen ini dirancang khusus sebagai **panduan instruksi eksekusi mandiri tanpa jeda konfirmasi (*Zero-Confirmation Autonomous Directive*)** untuk AI Coding Agent di VS Code (seperti **Roo Code**, **Cline**, **Cursor**, atau **GitHub Copilot**).

Saat pengguna memberikan salah satu dari dua perintah ini:
1. **Perintah Memulai dari Awal:**
   > **"Mulai bangun project ini lihat file BLUEPRINT_EKSEKUSI_MANDIRI.md dan PRD_BengkelPOS_Radiator.md"**
2. **Perintah Melanjutkan Jika Terhenti di Tengah Jalan:**
   > **"Lanjutkan pembuatan project"**

AI **WAJIB langsung bekerja secara mandiri dari titik terakhir hingga tuntas (end-to-end)** mencakup backend FastAPI, database SQLite (normalisasi pelanggan multi-unit & radiator copotan), integrasi driver printer Bluetooth ESC/POS (58mm/80mm), antarmuka kasir responsif, serta modul manajemen stok dan garansi, **tanpa berhenti di tengah jalan untuk meminta konfirmasi**. Seluruh penyesuaian/revisi oleh Pemilik Bengkel akan dilakukan di akhir setelah sistem utuh selesai dibangun dan siap dijalankan.

---

## 1. Protokol Eksekusi Otonom (Autonomous Execution Rules)

1. **Dilarang Berhenti untuk Bertanya/Konfirmasi Sepele:**
   - Seluruh keputusan teknis, arsitektur, skema tabel, dan antarmuka telah dikunci dalam blueprint ini dan [PRD_BengkelPOS_Radiator.md](file:///c:/Users/Administrator/Downloads/Aplikasi%20bengkel/PRD_BengkelPOS_Radiator.md).
   - Jangan meminta persetujuan untuk hal-hal implementatif (seperti nama variabel internal, format styling CSS, atau konfigurasi port). Ambil keputusan terbaik sesuai standar industri dan lanjutkan pengkodean.
2. **Kepatuhan Mutlak pada Aturan Bisnis Bengkel Radiator (Ref: PRD BAB 1 & 3):**
   - **Multi-Unit per Pelanggan (`FR-CUST-05`)**: 1 Pelanggan dapat memiliki lebih dari 1 kendaraan/unit radiator.
   - **Dukungan Bawa Radiator Saja (`FR-UNIT-04`)**: Objek servis tidak selalu mobil (nopol); sistem wajib mendukung unit radiator copotan dengan label/ID unik otomatis (contoh: `RAD-20261028-001`).
   - **Fleksibilitas Harga Deal (`FR-POS-03`, `FR-POS-04`)**: Harga jasa dan harga part pada saat transaksi kasir bersifat fleksibel (bisa dinaikkan/diturunkan sesuai kesepakatan langsung dengan pelanggan). Harga di master katalog hanya patokan awal (*default baseline*), bukan harga mati, dan perubahan harga deal tidak boleh mengubah harga master di gudang.
   - **Metode Pembayaran (`FR-POS-06`, `FR-POS-07`)**:
     * **CASH / TUNAI**: Menginput uang diterima dan menghitung kembalian.
     * **TRANSFER BANK**: Jumlah bayar otomatis pas (kembalian Rp 0), menampilkan nomor rekening tujuan bengkel.
   - **Informasi Rekening Bengkel**: Nama Bank, No. Rekening, dan Atas Nama dimuat via `.env` dan dicetak di struk sebagai petunjuk transfer pelanggan.
   - **Potong Stok Atomik (`FR-POS-04`, `FR-POS-08`)**: Pemilihan sparepart dalam servis otomatis mengurangi kuantitas stok di tabel `stock_items` secara atomik di dalam satu transaksi database (`db.begin()`).
   - **Presisi Perhitungan Uang (`FR-POS-05`)**: Semua kalkulasi biaya (Jasa, Part, Grand Total, Kembalian) menggunakan presisi desimal pasti (`decimal.Decimal` di Python / `Numeric(14, 2)` di SQLite).
   - **Printer Bluetooth Thermal 58mm/80mm (`FR-PRN-01` s/d `FR-PRN-08`)**: Menggunakan Web Bluetooth API dengan transmisi paket aman (*chunking safe-write* 50 bytes) agar printer thermal murah tidak macet/overflow.
3. **Pembaruan Dokumen Pelacak Berkala:**
   - Setiap kali menyelesaikan satu tahap pengerjaan, AI wajib memperbarui persentase pada [STATUS_PROYEK_DAN_SKEMA_IMPLEMENTASI.md](file:///c:/Users/Administrator/Downloads/Aplikasi%20bengkel/STATUS_PROYEK_DAN_SKEMA_IMPLEMENTASI.md).

---

## 2. Pilihan Stack Teknologi Baku (Pre-Determined Tech Stack)

| Komponen | Pilihan Teknologi | Alasan & Standar |
| :--- | :--- | :--- |
| **Runtime & Bahasa** | **Python 3.11+** | Kompatibel dengan fondasi kode referensi yang Anda buat sebelumnya |
| **Backend Framework**| **FastAPI + Uvicorn** | Eksekusi sangat cepat, validasi otomatis skema Pydantic, dokumentasi OpenAPI bawaan |
| **Basis Data & ORM** | **SQLite + SQLAlchemy 2.0** | Single-file (`data/bengkel_radiator.db`), nol instalasi server, sangat mudah di-backup harian |
| **Frontend Kasir**   | **HTML5 SPA + Modern Tailwind CSS + Vanilla JS** | Ringan, dimuat langsung oleh FastAPI (`StaticFiles`), tidak memerlukan `node_modules` berat di komputer bengkel, responsif di HP/tablet/laptop |
| **Bluetooth Printing**| **Web Bluetooth API + ESC/POS Generator (JS)** | Cetak nirkabel langsung dari browser Chrome/Edge tanpa driver Windows yang membingungkan |
| **Testing**          | **Pytest + FastAPI TestClient** | Eksekusi otomatis 20 skenario uji baku (`TC-01` s/d `TC-20`) |

---

## 3. Struktur Berkas Proyek Terstandar (Granular Directory Structure)

AI wajib membangun struktur folder proyek yang sangat terorganisir persis seperti skema berikut:

```text
Aplikasi bengkel/
├── .env.example                                      # Template konfigurasi bengkel & printer
├── .env                                              # Konfigurasi aktif (diabaikan git)
├── .gitignore                                        # Proteksi file sensitif & cache
├── PRD_BengkelPOS_Radiator.md                        # Dokumen spesifikasi kebutuhan baku (v2.0)
├── STATUS_PROYEK_DAN_SKEMA_IMPLEMENTASI.md           # Master pelacak progres proyek
├── BLUEPRINT_EKSEKUSI_MANDIRI.md                     # Panduan eksekusi mandiri ini
├── PROMPT_PENGEMBANGAN_KODE.md                       # Prompt instruksi developer
├── PROMPT_AUDIT_SECURITY_DAN_TEST_BUG.md             # Panduan audit dan bug testing
├── requirements.txt                                  # Dependensi Python (FastAPI, SQLAlchemy, Uvicorn, dll)
├── run.py                                            # Script runner satu klik untuk menjalankan aplikasi
│
├── database/                                         # === BASIS DATA & MODEL ===
│   ├── __init__.py
│   ├── base.py                                       # Declarative Base SQLAlchemy
│   ├── session.py                                    # Engine SQLite, sessionmaker & init_db()
│   └── models.py                                     # 7 Entitas Relasional (Ref: PRD BAB 4.2)
│
├── repositories/                                     # === AKSES DATA REPOSITORY ===
│   ├── __init__.py
│   ├── customer_repository.py                        # CRUD Customer & VehicleOrUnit
│   ├── service_record_repository.py                  # CRUD ServiceRecord, ServiceJob, ServicePart
│   └── stock_repository.py                           # CRUD StockItem & HargaJasa
│
├── services/                                         # === LOGIKA BISNIS INTI ===
│   ├── __init__.py
│   ├── customer_service.py                           # Registrasi pelanggan, multi-unit, label RAD-xxxx
│   ├── pos_service.py                                # Transaksi kasir, kalkulasi deal, potong stok atomik
│   ├── warranty_service.py                           # Validasi masa aktif garansi & klaim
│   ├── stock_service.py                              # Pengelolaan stok gudang & mutasi
│   ├── pricing_service.py                            # Perhitungan presisi finansial Decimal
│   └── backup_service.py                             # Ekspor cadangan database SQLite
│
├── api/                                              # === CONTROLLER & ENDPOINTS ===
│   ├── __init__.py
│   ├── app.py                                        # Inisialisasi FastAPI, lifespan & mounting static
│   ├── schemas.py                                    # Validasi Pydantic DTO (Ref: PRD BAB 5.1)
│   ├── customer_routes.py                            # Endpoint /api/customers & /api/units
│   ├── pos_routes.py                                 # Endpoint /api/pos/transaction & /api/service-records
│   ├── stock_routes.py                               # Endpoint /api/stock & /api/harga-jasa
│   └── report_routes.py                              # Endpoint rekap kas harian & backup
│
├── frontend/                                         # === ANTARMUKA KASIR WEB APP / PWA ===
│   ├── index.html                                    # Single Page Application kasir modern
│   ├── css/
│   │   └── style.css                                 # Custom styling & utility classes
│   └── js/
│       ├── app.js                                    # Logika UI, navigasi modal & form kasir
│       ├── bluetooth-printer.js                      # Driver Web Bluetooth, safe chunking & ESC/POS
│       └── api-client.js                             # Komunikasi HTTP fetch ke backend
│
└── tests/                                            # === PENGUJIAN OTOMATIS (TC-01 s/d TC-20) ===
    ├── __init__.py
    ├── test_customer_unit.py                         # Uji multi-unit & radiator copotan (TC-01 s/d TC-05)
    ├── test_pos_transaction.py                       # Uji kalkulasi deal & potong stok (TC-06 s/d TC-12)
    ├── test_warranty.py                              # Uji garansi & klaim (TC-13 s/d TC-16)
    └── test_print_backup.py                          # Uji ESC/POS byte & backup SQLite (TC-17 s/d TC-20)
```

---

## 4. Spesifikasi Logika Kritis (Critical Business Logics)

### 4.1 Format Penamaan Unit Radiator Copotan (`FR-UNIT-04`)
Jika pelanggan membawa radiator lepas tanpa mobil:
- Flag: `unit_type = "RADIATOR_ONLY"`
- Kolom `nopol` diisi `NULL`.
- Sistem membuat label unik otomatis:
  $$\text{Label} = \text{"RAD-"} + \text{YYYYMMDD} + \text{"-"} + \text{NomorUrutHarian (3 digit)}$$
  *(Contoh: `RAD-20261028-001`)*.
- Label ini tercetak jelas di struk untuk ditempel pada radiator fisik pelanggan.

### 4.2 Alur Transaksi Kasir, Fleksibilitas Harga & Potong Stok Atomik (`FR-POS-01` s/d `FR-POS-08`)
Saat tombol **Simpan Transaksi** ditekan:
1. Buka transaksi database atomik: `with session.begin():`.
2. Generate Nomor Nota unik format: `INV-YYYYMMDD-XXXX` (cek keunikan di database).
3. Buat `ServiceRecord` baru (catat keluhan awal, waktu, diskon, metode bayar, garansi).
4. Masukkan baris-baris `ServiceJob` (Jasa):
   - Gunakan nominal harga deal yang dimasukkan kasir (`harga` deal, bisa berbeda dari master `harga_jasa`).
   - Hitung `subtotal = jumlah * harga`.
5. Masukkan baris-baris `ServicePart` (Suku Cadang):
   - Gunakan nominal harga deal yang dimasukkan kasir (`harga_satuan` deal, bisa berbeda dari master `stock_items`).
   - Jika terhubung ke `stock_item_id`, periksa ketersediaan stok (`jumlah_stok >= qty`).
   - Kurangi stok secara langsung: `stock_items.jumlah = stock_items.jumlah - qty`.
6. Hitung total uang & proses metode bayar:
   $$\text{Total Servis} = \sum(\text{Subtotal Jasa Deal}) + \sum(\text{Subtotal Part Deal}) - \text{Diskon}$$
   - Jika `metode_bayar == 'CASH'`: Validasi $\text{bayar} \ge \text{Total Servis}$, lalu $\text{Kembalian} = \text{Bayar} - \text{Total Servis}$.
   - Jika `metode_bayar == 'TRANSFER'`: Kunci $\text{Bayar} = \text{Total Servis}$ dan $\text{Kembalian} = 0$.
7. Komit transaksi database secara atomik. Jika terjadi galat, SQLAlchemy otomatis melakukan rollback.

### 4.3 Driver Printer Bluetooth (ESC/POS Safe-Chunking Write) (`FR-PRN-01` s/d `FR-PRN-06`)
Modul `bluetooth-printer.js` bertugas:
1. Menghubungkan browser ke printer via `navigator.bluetooth.requestDevice`:
   - Service UUID standar printer thermal: `000018f0-0000-1000-8000-00805f9b34fb` atau Serial Port Profile `0000ffe0-0000-1000-8000-00805f9b34fb`.
2. Menyusun byte command ESC/POS:
   - Inisialisasi: `ESC @` (`0x1B, 0x40`)
   - Perataan Tengah: `ESC a 1` (`0x1B, 0x61, 0x01`)
   - Teks Tebal: `ESC E 1` (`0x1B, 0x45, 0x01`)
   - Baris Baru / Feed: `LF` (`0x0A`)
   - Potong Kertas (jika didukung): `GS V 66 0`
3. Mengirimkan array byte tersebut ke characteristic Bluetooth printer secara terpecah (chunks 50 byte dengan jeda 25ms) agar buffer printer murah tidak meluap.
4. Menambahkan bagian Rekening Bengkel pada struk (Bank, No Rek, a/n) dari konfigurasi environment.

---

## 5. Tahapan Eksekusi Otomatis (Step-by-Step Autonomous Steps)

AI di VS Code wajib mengeksekusi tahapan berikut secara berurutan:

* **Tahap 1: Setup Lingkungan & Basis Data (Ref: PRD BAB 4)**
  - Buat berkas `requirements.txt` (FastAPI, Uvicorn, SQLAlchemy, Pydantic, python-dotenv, pytest, httpx).
  - Implementasikan `database/base.py`, `database/session.py`, dan `database/models.py` (7 tabel relasional persis seperti di PRD Bab 4.2).
  - Pastikan database SQLite lokal terbuat di folder `data/bengkel_radiator.db`.
* **Tahap 2: Repository & Service Logika Bisnis (Ref: PRD BAB 3 & 4)**
  - Bangun `repositories/` untuk komunikasi database murni.
  - Bangun `services/customer_service.py` (dukungan 1-to-many pelanggan & unit, serta generator `RAD-xxxx`).
  - Bangun `services/pos_service.py` (transaksi kasir, kalkulasi deal, potong stok atomik).
  - Bangun `services/warranty_service.py` (validasi garansi aktif/expired & klaim).
  - Bangun `services/stock_service.py` dan `services/backup_service.py`.
* **Tahap 3: Controller API FastAPI & Skema Pydantic (Ref: PRD BAB 5)**
  - Buat `api/schemas.py` sesuai kontrak PRD Bab 5.1.
  - Implementasikan rute di `api/customer_routes.py`, `api/pos_routes.py`, `api/stock_routes.py`, dan `api/report_routes.py`.
  - Sambungkan seluruh router ke `api/app.py` dan pasang middleware CORS serta `StaticFiles`.
* **Tahap 4: Antarmuka Web Kasir (Frontend SPA) (Ref: PRD BAB 7)**
  - Bangun `frontend/index.html` dengan Tailwind CSS modern dan responsif.
  - Pasang tombol hero: **[ + Tambah Service ]** dan **[ + Tambah Pelanggan ]**.
  - Sediakan form modal transaksi kasir dengan kolom input harga deal yang dapat diketik bebas.
  - Sediakan radio button metode bayar: `CASH` vs `TRANSFER BANK`.
  - Pasang tabel riwayat servis dengan tombol **[ Cetak Ulang Struk ]** dan **[ Klaim Garansi ]**.
* **Tahap 5: Modul Web Bluetooth Printer ESC/POS (Ref: PRD BAB 6)**
  - Buat `frontend/js/bluetooth-printer.js` lengkap dengan koneksi Web Bluetooth dan formatter struk 58mm & 80mm.
  - Terapkan transmisi data safe-chunking 50 byte.
  - Pasang tombol pairing Bluetooth di header UI kasir.
* **Tahap 6: Runner Satu Klik & Pengujian Terpadu (Ref: PRD BAB 9)**
  - Buat berkas runner `run.py` untuk menjalankan aplikasi lokal dengan sekali klik (`python run.py`).
  - Tulis seluruh pengujian unit di folder `tests/` yang mencakup 20 skenario uji (`TC-01` s/d `TC-20`).
  - Jalankan `pytest tests/` dan pastikan seluruh 20 pengujian berstatus **100% PASSED**.
  - Perbarui status pada `STATUS_PROYEK_DAN_SKEMA_IMPLEMENTASI.md`.
