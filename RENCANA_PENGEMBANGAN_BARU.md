# Rencana Pengembangan Baru

Status: **Tahap 1-8 selesai**. Seluruh rencana pada dokumen ini sudah
diimplementasikan dan diverifikasi.

- Tanggal dibuat: 2026-11-01
- Acuan versi: web/desktop **2.3.3**, APK terakhir yang dibangun **2.3.2**
  (versionCode 14)
- Skema database saat ini: **26**
- Tes acuan: 342 pytest jalur desktop (Pydantic v2), 154 unit test Kotlin;
  jalur APK (Pydantic v1) dijalankan saat build APK berikutnya.

## Aturan kerja

- Setiap rencana pengembangan baru dicatat di dokumen ini lebih dulu.
- Tidak ada implementasi kode sampai ada perintah eksplisit seperti
  "kerjakan", "implementasikan", atau "mulai tahap ini".
- Setiap butir rencana memuat tujuan, perilaku yang diinginkan, area yang
  tersentuh, prioritas, dampak, kriteria selesai, dan rencana tes.
- Rencana boleh diubah, dipecah, atau dihapus sebelum implementasi.
- Dokumen ini bukan persetujuan implementasi.

## Ringkasan rencana

| No | Rencana | Area | Prioritas | Status |
| --- | --- | --- | --- | --- |
| 1 | Total hutang seluruhnya dan stok menipis di Ringkasan | Ringkasan + piutang + stok | Tinggi | Selesai 2026-11-01 |
| 2 | Supplier dan Follow up Reseller | Supplier + stok + WhatsApp | Tinggi | Selesai 2026-11-01 |
| 3 | Hasil follow up pelanggan | Follow up + laporan | Tinggi | Selesai 2026-11-01 |
| 4 | Nomor nota angka berurutan | Nota | Tinggi | Selesai 2026-11-01 |
| 5 | Karyawan: mekanik, kasir, performa, dan komisi | Karyawan + nota + laporan | Tinggi | Selesai 2026-11-01 |
| 6 | Pengaturan struk dengan tombol on/off per bagian | Struk + pengaturan | Tinggi | Selesai 2026-11-01 |

## Status implementasi

- Tahap 1-8 selesai dan terverifikasi.
- Acuan: web/desktop 2.3.3, APK terakhir 2.3.2 (versionCode 14), skema 26.
- Setiap tahap harus lulus tes terarah sebelum tahap berikutnya dimulai.
- Setiap sentuhan pada kode yang sudah berjalan wajib dicatat dan dilaporkan
  di akhir pekerjaan.

## Realisasi Tahap 1

- Kartu Ringkasan: Total hutang, Stok menipis, dan Stok habis.
- Total hutang memakai sisa piutang berjalan dan membuka daftar piutang.
- Stok menipis memakai batas efektif per item; batas kosong mengikuti
  pengaturan bawaan, 0 menonaktifkan item, dan nilai positif menjadi batas
  khusus.
- Stok habis menghitung item dengan jumlah 0 atau kurang.
- Halaman stok memiliki filter Semua, Menipis, dan Habis serta kolom Min.
- Pengaturan memiliki **Batas minimum stok bawaan** dengan default 3.
- Migrasi **v22** menambah `stock_items.stok_minimum` nullable.

File lama yang disentuh pada Tahap 1:

- `database/models.py` dan `database/migrations.py`: kolom stok minimum dan
  migrasi v22.
- `api/schemas.py` dan `api/stock_routes.py`: field stok minimum dan field
  ringkasan.
- `services/stock_service.py`: validasi minimum, stok menipis, stok habis.
- `services/report_service.py`: hitungan stok menipis/habis digabung ke query
  ringkasan yang sudah ada agar jumlah query tidak bertambah.
- `services/settings_service.py`: pengaturan batas minimum bawaan.
- `frontend/index.html`, `frontend/js/app.js`, `frontend/css/style.css`: kartu,
  filter, form, dan pengaturan.
- `tools/seed_manual_test.py`: contoh batas minimum dan pengaturan demo.
- `tests/test_s15_stock_minimum.py`: tes baru.

Hasil verifikasi Tahap 1:

- 325 pytest lulus di `.venv` dan `.venv-apk`.
- Migrasi salinan dummy v21 ke v22 berhasil.
- UI browser: kartu Total hutang Rp 1.100.000, Stok menipis 1, Stok habis 1,
  dan isi filter sama dengan kartu.
- APK debug 2.2.8 (versionCode 11) dibangun dengan Tahap 1.

Asumsi Tahap 1:

- Batas minimum kosong mengikuti pengaturan bawaan.
- Stok habis dihitung terpisah dari stok menipis.
- Stok minus dianggap habis.

## Realisasi Tahap 2-8

- **Tahap 2:** tabel supplier dan relasi banyak-ke-banyak ke stok, menu
  Supplier, tab Follow up Reseller, chat WhatsApp supplier, dan log supplier.
  Edit stok dapat memilih supplier barang agar follow up reseller langsung
  mengarah ke supplier yang benar.
- **Tahap 3:** kartu Balik lagi, Masih bagus, Bermasalah, dan Menolak dari
  seluruh pesan pelanggan; hanya angka dan kategori kosong disembunyikan.
- **Tahap 4:** nomor nota baru memakai angka berurutan dari 1; nota lama tetap.
- **Tahap 5:** tabel karyawan, penugasan 0..n mekanik dan satu kasir per nota,
  nama karyawan di struk, dan menu Karyawan. Jenis imbalan dapat dipilih:
  komisi, gaji bulanan, atau gaji dan komisi.
- **Tahap 6:** performa per periode, riwayat pengerjaan, komisi per nota dengan
  basis barang/jasa/keduanya, mode persen/nominal, serta bagi rata atau manual.
- **Tahap 7:** pengaturan struk 25 bagian, nama bengkel selalu tampil, berlaku
  untuk cetak dan teks WhatsApp.
- **Tahap 8:** seed supplier/karyawan, migrasi v23-v26, 342 pytest jalur desktop,
  verifikasi UI, dan APK debug terakhir 2.3.2 (versionCode 14). APK 2.3.3
  dibangun setelah verifikasi localhost.

Penyempurnaan setelah Tahap 8 (2026-11-01):

- Edit sparepart dapat memilih satu atau beberapa supplier; follow up reseller
  otomatis mengelompokkan barang menipis/habis ke supplier yang tepat.
- Form supplier memakai pemilih barang dan tabel barang terpilih, bukan
  multi-select.
- Karyawan dapat memakai imbalan gaji bulanan, komisi, atau keduanya.
- Tab Follow up Reseller memakai ringkasan angka dan kartu yang sama dengan
  Follow up Pelanggan.
- Laporan menampilkan estimasi laba bersih setelah komisi; gaji tetap bulanan
  tidak diprorata dan dicatat sebagai batasan.
- Sakelar **Fitur karyawan** dan **Fitur supplier** menyembunyikan kolom terkait
  di kasir, struk, form stok, dan tab Reseller saat dimatikan.
- Pembayaran gaji aktual dicatat per karyawan dan periode di halaman Karyawan.
  Migrasi v26 menambah tabel `salary_payments`; laporan memotong gaji berdasarkan
  tanggal bayar pada periode laporan.

File lama yang disentuh pada Tahap 2-8:

- `database/models.py`, `database/migrations.py`: supplier, karyawan,
  penugasan, komisi, kolom kasir, dan migrasi v23-v25.
- `api/app.py`, `api/schemas.py`, `api/supplier_routes.py`,
  `api/employee_routes.py`, `api/followup_routes.py`, `api/pos_routes.py`,
  `api/payment_routes.py`, `api/settings_routes.py`.
- `services/supplier_service.py`, `services/employee_service.py`,
  `services/followup_result_service.py`, `services/pos_service.py`,
  `services/receipt_service.py`, `services/settings_service.py`,
  `services/whatsapp_service.py`, `repositories/service_record_repository.py`.
- `frontend/index.html`, `frontend/js/app.js`, `frontend/js/api-client.js`,
  `frontend/css/style.css`.
- `tools/seed_manual_test.py` dan tes baru `test_s15_*`.
- README, PETA_TEKS_UI_DAN_POPUP.md, INVENTARIS_TEKS_UI.md,
  android/README_APK.md.

Catatan: perubahan pada file lama bersifat aditif dan menjaga alur lama;
laporan akhir menyebutkan seluruh file yang benar-benar disentuh.

## Prinsip kerja

1. **Additive first.** Tambah tabel, kolom, service, route, dan UI baru. Hindari
   mengganti nama atau menghapus field lama.
2. **Perilaku lama tetap default.** Struk tetap sama sampai toggle diubah,
   nota lama tetap memakai nomor lama, dan nota tanpa karyawan tetap sah.
3. **Uang tetap di backend.** Total hutang, komisi, dan nilai servis memakai
   Decimal + ROUND_HALF_UP di backend. JavaScript hanya menampilkan.
4. **Migrasi aman.** Backup dahulu, uji migrasi di salinan database dummy,
   baru terapkan. Tidak menyentuh database produksi.
5. **Modul baru dulu.** Fitur baru dibuat di service/route baru. File lama
   hanya disentuh pada titik integrasi yang benar-benar diperlukan.
6. **Tes dua stack.** Setiap tahap diuji di `.venv` (Pydantic v2) dan
   `.venv-apk` (Pydantic v1).
7. **Laporan akhir.** Cantumkan file yang disentuh, tes yang dijalankan,
   migrasi, asumsi, dan risiko.

## Titik sentuh kode lama (perkiraan)

| File | Perubahan yang diperkirakan | Alasan | Pengaman |
| --- | --- | --- | --- |
| `database/models.py` | Tabel/kolom baru: stok minimum, supplier, employee, penugasan | Fondasi data | Kolom nullable/default, tanpa rename |
| `database/migrations.py` | Migrasi v22-v25 | Perubahan skema | Backup + uji salinan |
| `api/schemas.py` | Schema baru dan field tambahan | Kontrak API | Field lama dipertahankan |
| `api/app.py` | Daftarkan router baru | Endpoint supplier/karyawan | Hanya tambah include |
| `api/report_routes.py` | Field total hutang dan stok menipis | Ringkasan | Tambah field response |
| `services/report_service.py` | Isi field dashboard baru | Ringkasan | Tes laporan lama |
| `services/stock_service.py` | Batas minimum dan daftar stok menipis | Stok | Tes stok lama |
| `api/stock_routes.py` | Field `stok_minimum` | Stok | Tambah field |
| `repositories/service_record_repository.py` | Fungsi nomor nota angka baru | Nomor nota | Fungsi lama tetap ada |
| `services/pos_service.py` | Panggil nomor baru dan simpan karyawan | POS | Tes transaksi lama |
| `services/receipt_service.py` | Nama karyawan dan toggle struk | Struk | Default semua tampil |
| `services/settings_service.py` | Key pengaturan struk | Struk | Default kompatibel |
| `services/whatsapp_service.py` | Jenis log `supplier` | Follow up Reseller | Validasi jenis lama tetap |
| `services/followup_service.py` | Hasil follow up pelanggan | Follow up | Endpoint lama tetap |
| `frontend/index.html` | Menu Supplier/Karyawan, kartu, toggle struk | UI | Elemen lama dipertahankan |
| `frontend/js/app.js` | Render dan form baru | UI | Alur POS lama tetap |
| `frontend/js/api-client.js` | Method endpoint baru | UI | Method lama tetap |
| `tools/seed_manual_test.py` | Data demo supplier/karyawan | Uji manual | Seed lama tetap valid |
| `README.md`, `PETA_TEKS_UI_DAN_POPUP.md`, `INVENTARIS_TEKS_UI.md`, `android/README_APK.md` | Dokumentasi | Rilis | Tidak menyentuh kode |

## Rencana implementasi bertahap

### Tahap 0 - Persiapan dan pengamanan

- Jalankan tes baseline dua stack.
- Backup database dummy dan buat salinan uji migrasi.
- Pastikan working tree bersih dan perubahan pengguna tidak ditimpa.
- Catat versi skema awal dan jumlah data demo.
- Tidak ada perubahan kode pada tahap ini.

Kriteria selesai: baseline lulus, backup dan salinan migrasi tersedia.

### Tahap 1 - Ringkasan: total hutang dan stok menipis

**Data**
- Tambah `stock_items.stok_minimum` nullable.
- Arti: kosong ikut pengaturan, 0 nonaktif, lebih dari 0 batas khusus.
- Tambah pengaturan `stok_minimum_default` dengan default 3.
- Tidak perlu tabel baru untuk total hutang.

**Backend**
- Tambah fungsi stok menipis: item dengan batas efektif lebih dari 0,
  jumlah lebih dari 0, dan jumlah kurang dari atau sama dengan batas.
- Tambah fungsi stok habis: item dengan jumlah 0 atau kurang.
- Tambah total hutang dari ringkasan piutang yang sudah ada.
- Field dashboard baru: total hutang, jumlah nota hutang, jumlah pelanggan
  hutang, jumlah stok menipis, jumlah stok habis, dan daftar item terkait.
- Endpoint stok menyertakan `stok_minimum`; update stok menerima nilai baru.
- Pengaturan operasional menyertakan `stok_minimum_default`.

**Frontend**
- Tiga kartu baru di Ringkasan: **Total hutang**, **Stok menipis**, dan
  **Stok habis**.
- Klik Total hutang membuka daftar piutang.
- Klik Stok menipis atau Stok habis membuka daftar stok yang sudah difilter.
- Halaman stok memiliki filter Semua, Menipis, dan Habis.
- Form stok menambah input batas minimum per item.
- Pengaturan menambah input batas minimum stok bawaan.

**Tes**
- Total hutang mengecualikan VOID dan nota lunas.
- Batas kosong mengikuti pengaturan bawaan.
- Batas 0 menonaktifkan peringatan item.
- Item tepat di batas dan di bawah batas muncul sebagai menipis.
- Item jumlah 0 muncul sebagai stok habis, bukan menipis.
- Kartu dashboard sama dengan isi daftar.

**Kriteria selesai:** angka kartu sesuai daftar, tidak ada perubahan
perhitungan uang, tes lama lulus.

### Tahap 2 - Supplier dan Follow up Reseller

**Data**
- Tabel `suppliers`: nama, nomor HP/WhatsApp, alamat, catatan, aktif.
- Tabel `supplier_items`: relasi banyak-ke-banyak supplier dan stok.
- Satu barang boleh punya beberapa supplier; tidak ada supplier utama wajib.

**Backend**
- Service dan route CRUD supplier.
- Endpoint menghubungkan supplier dengan beberapa item stok.
- Daftar stok menipis menyertakan supplier yang terhubung.
- Jenis log WhatsApp baru: `supplier`.
- Template pesan supplier formal, dapat diedit, memakai `wa.me`.
- Gerbang jam kirim berlaku; pengiriman tetap manual.

**Frontend**
- Menu **Supplier** di sidebar dekat Pelanggan.
- Daftar dan form supplier dengan pilihan barang yang disuplai.
- Tab **Follow up Pelanggan** dan **Follow up Reseller**.
- Kartu reseller per supplier berisi barang menipis, sisa stok, batas minimum,
  dan tombol Chat.
- Bila satu barang punya beberapa supplier, tampilkan semua pilihan chat.

**Tes**
- Relasi banyak-ke-banyak.
- Barang dengan beberapa supplier.
- Supplier tanpa nomor valid.
- Pengelompokan barang menipis per supplier.
- Log `supplier` tidak bercampur dengan log pelanggan.

**Kriteria selesai:** supplier dan reseller dapat dipakai tanpa mengubah data
pelanggan atau alur follow up pelanggan.

### Tahap 3 - Hasil follow up pelanggan

**Sumber data**
- Seluruh pesan pelanggan yang pernah dikirim lewat aplikasi: Follow up,
  piutang, dan kendaraan selesai/pengerjaan.
- Pesan struk dan supplier tidak dihitung.

**Perhitungan**
- Balik lagi: ada nota servis baru setelah pesan dikirim, termasuk garansi.
- Bermasalah: klaim garansi atau status `MASIH_KENDALA` setelah pesan.
- Masih bagus: hasil baik tanpa kunjungan masalah setelahnya.
- Menolak: status `TIDAK_DATANG`/`ARSIP` tidak perlu lagi.
- Pelanggan dihitung sekali memakai hasil terbaru.
- Bila waktu sama, prioritas: Balik lagi > Bermasalah > Masih bagus > Menolak.

**Backend**
- Service baru untuk menghitung hasil; tidak perlu status hasil baru.
- Endpoint hasil per kategori dan daftar pelanggan pendukung.

**Frontend**
- Empat kartu hasil: Balik lagi, Masih bagus, Bermasalah, Menolak.
- Hanya angka, tanpa subteks panjang.
- Kategori tanpa data disembunyikan.
- Klik kartu membuka daftar pelanggan terkait.

**Tes**
- Satu pelanggan dengan beberapa pesan memakai hasil terbaru.
- Kunjungan garansi dihitung Balik lagi.
- Klaim garansi dihitung Bermasalah.
- Pesan struk dan supplier tidak masuk.
- Kategori kosong tidak tampil.

**Kriteria selesai:** angka berasal dari riwayat pesan nyata, bukan input manual,
dan tidak menghitung pelanggan dua kali.

### Tahap 4 - Nomor nota angka berurutan

**Perilaku**
- Nota baru bernomor `1`, `2`, `3`, dan seterusnya.
- Nota lama tetap memakai nomor lama, tanpa renumbering.
- Nomor tidak dipakai ulang setelah retur, void, atau pembatalan.
- Counter dimulai dari 1 walaupun sudah ada nota lama.

**Backend**
- Fungsi alokasi nomor baru memakai counter atomik di dalam transaksi tulis.
- Counter baru dapat memakai tabel `nota_counters` yang sudah ada dengan kunci
  khusus `NUMERIC`, sehingga tidak perlu tabel baru.
- Fungsi lama `allocate_nota` tetap dipertahankan untuk membaca/mencetak nota
  lama; hanya nota baru yang memakai fungsi angka.
- `pos_service` memanggil fungsi baru hanya untuk nota baru.
- Format nomor lama dan baru sama-sama dapat dicari, dicetak, dan diretur.
- Indeks unik tetap dipertahankan.

**Frontend**
- Tidak ada perubahan alur kasir; label nomor nota mengikuti data backend.
- Daftar, detail, struk, dan pencarian menerima nomor angka.

**Tes**
- Urutan 1, 2, 3 tanpa duplikat.
- Nota 14 diretur, nota berikutnya 15.
- Dua transaksi bersamaan tidak mendapat nomor sama.
- Nota lama tetap terbaca dan dapat dicetak ulang.
- Void/retur tidak mengembalikan nomor ke counter.

**Kriteria selesai:** nota baru unik dan berurutan, nota lama tidak berubah,
dan alur POS/struk/retur tetap lulus.

### Tahap 5 - Karyawan, mekanik, kasir, dan struk

**Data**
- Tabel `employees`: nama, peran, aktif, nomor HP, catatan.
- Tabel `service_record_mechanics`: nota dan mekanik, boleh 0 sampai banyak.
- Kolom `service_records.cashier_employee_id` nullable.

**Backend**
- CRUD karyawan.
- Payload POS menerima daftar mekanik dan kasir.
- Validasi: mekanik boleh kosong, kasir satu, karyawan harus aktif.
- Nota lama tanpa data menampilkan "Tidak dicatat".
- Struk mencetak nama kasir dan mekanik; data tetap tersimpan bila toggle
  struk dimatikan.

**Frontend**
- Menu **Karyawan** di sidebar dekat Pelanggan.
- Form karyawan dengan peran Mekanik, Kasir, atau Keduanya.
- Kasir POS memilih mekanik (multi) dan kasir (satu).
- Detail nota dan struk menampilkan karyawan terkait.

**Tes**
- Nota tanpa mekanik.
- Nota dengan 1, 2, dan 3 mekanik.
- Kasir wajib satu; mekanik tidak wajib.
- Nota lama menampilkan "Tidak dicatat".
- Nama karyawan muncul di struk dan teks WhatsApp.

**Kriteria selesai:** penugasan karyawan tersimpan per nota tanpa mengubah
perhitungan uang atau status nota.

### Tahap 6 - Performa karyawan dan komisi

**Backend**
- Service performa per karyawan dan periode.
- Metrik: jumlah nota, jasa, sparepart, total nilai servis, pelanggan unik.
- Riwayat pengerjaan per karyawan.
- Komisi per nota dengan basis pilihan owner: barang, jasa, atau keduanya.
- Mode komisi: persentase atau nominal tetap per nota, dipilih per karyawan.
- Pembagian beberapa mekanik: rata atau manual per nota.
- Semua nominal memakai Decimal + ROUND_HALF_UP di backend.

**Frontend**
- Tab Performa di menu Karyawan.
- Filter periode: hari ini, bulan ini, rentang tanggal.
- Ringkasan metrik, riwayat nota, dan estimasi komisi.
- Owner dapat menimpa nominal komisi pada nota tertentu.

**Tes**
- Basis barang, jasa, dan keduanya.
- Mode persentase dan nominal tetap.
- Pembagian rata dan manual.
- Pembulatan uang.
- Karyawan tanpa nota.
- Periode kosong.

**Kriteria selesai:** angka performa dan komisi sesuai nota, dapat ditelusuri,
dan tidak dihitung ulang di JavaScript.

### Tahap 7 - Pengaturan struk

**Data**
- Key pengaturan struk di `app_settings`, semua boolean default aktif.
- Nama bengkel selalu aktif dan tidak memiliki toggle.

**Backend**
- `receipt_service` membaca toggle sebelum mencetak setiap bagian.
- Berlaku untuk cetak thermal, cetak browser/Android, dan teks WhatsApp.
- Bagian kosong otomatis tidak dicetak.
- Nominal dan isi transaksi tidak berubah.

**Frontend**
- Bagian **Pengaturan Struk** di menu Pengaturan.
- Toggle per bagian: header, nomor nota, tanggal, kasir, mekanik, pelanggan,
  nomor HP, unit, keluhan, catatan, tabel JASA, tabel PART, total, pembayaran,
  garansi, rekening, footer.
- Pratinjau struk dengan data terakhir atau data contoh.
- Default semua aktif agar struk lama tetap sama.

**Tes**
- Semua toggle aktif menghasilkan struk lama.
- Setiap toggle mematikan bagian yang tepat.
- Nama bengkel tidak dapat dimatikan.
- Tabel JASA/PART kosong tidak mencetak judul.
- Teks WhatsApp mengikuti toggle yang sama.
- Uang dan status tidak berubah.

**Kriteria selesai:** tampilan struk dapat diatur tanpa mengubah data atau
perhitungan.

### Tahap 8 - Integrasi, migrasi, APK, dan dokumentasi

- Perbarui seed dummy: supplier, karyawan, stok minimum, pengaturan struk,
  dan contoh nomor nota baru.
- Uji migrasi pada salinan database dummy dari skema saat ini ke skema baru.
- Jalankan seluruh tes dua stack.
- Uji UI di browser: Ringkasan, Follow up Pelanggan/Reseller, Kasir, Karyawan,
  Supplier, dan Pengaturan Struk.
- Build APK debug dengan nomor versi baru; jangan membuat release APK.
- Perbarui README, PETA_TEKS_UI_DAN_POPUP.md, INVENTARIS_TEKS_UI.md, dan
  android/README_APK.md.
- Laporkan seluruh file lama yang benar-benar disentuh dan alasannya.

## Urutan dan ketergantungan

| Urutan | Tahap | Bergantung pada | Alasan |
| --- | --- | --- | --- |
| 1 | Tahap 1 | Tidak ada | Perubahan baca dan stok minimum paling kecil risikonya |
| 2 | Tahap 2 | Tahap 1 | Reseller memakai daftar stok menipis |
| 3 | Tahap 3 | Tidak ada | Hanya membaca log, servis, dan status |
| 4 | Tahap 4 | Tidak ada | Menyentuh POS dan struk, sebaiknya setelah fitur baca stabil |
| 5 | Tahap 5 | Tahap 4 | Penugasan karyawan ikut payload POS dan struk |
| 6 | Tahap 6 | Tahap 5 | Performa dan komisi membutuhkan data penugasan |
| 7 | Tahap 7 | Tahap 5 | Toggle struk mencakup baris karyawan |
| 8 | Tahap 8 | Semua | Migrasi, tes penuh, APK, dan dokumentasi |

## Rencana tes

### Tes baru

- `tests/test_s15_stock_minimum.py`
- `tests/test_s15_suppliers.py`
- `tests/test_s15_followup_results.py`
- `tests/test_s15_numeric_notes.py`
- `tests/test_s15_employees.py`
- `tests/test_s15_receipt_settings.py`
- Tambahan di `tests/test_migrations.py`

### Regresi wajib

- POS, kredit, pembayaran, piutang, void, retur.
- Struk dan cetak ulang.
- Follow up, pengerjaan, dan WhatsApp.
- Stok, jasa, laporan harian/periode.
- Backup, restore, dan migrasi.
- Dua stack Pydantic v2 dan v1.
- UI browser untuk kartu Ringkasan dan tab Follow up.

## Migrasi dan rollback

- Skema baru ditambahkan bertahap:
  - **v22**: `stock_items.stok_minimum`.
  - **v23**: tabel `suppliers` dan `supplier_items`.
  - **v24**: tabel `employees`, tabel `service_record_mechanics`, dan kolom
    `service_records.cashier_employee_id`.
- Pengaturan struk disimpan di `app_settings`, bukan perubahan skema.
- Counter nomor nota baru memakai `nota_counters` dengan kunci `NUMERIC`,
  bukan perubahan skema.
- Semua kolom baru nullable atau memiliki default.
- Tidak ada rename atau drop kolom lama.
- Sebelum migrasi: backup database dan buat salinan uji.
- Bila migrasi gagal, database asli tidak dipakai dan salinan uji dibuang.
- Nota lama tidak diubah nomornya.
- Data lama tetap dapat dibaca setelah migrasi.

## Risiko

| Risiko | Dampak | Mitigasi |
| --- | --- | --- |
| Nomor nota baru menyentuh POS/struk/retur | Tinggi | Tes alur penuh, nota lama tidak diubah, counter atomik |
| Toggle struk menghilangkan informasi garansi | Sedang | Default semua aktif, pratinjau, peringatan di pengaturan |
| Komisi salah hitung | Tinggi | Decimal di backend, tes pembulatan, tidak ada hitung di JS |
| Supplier ganda pada satu barang | Sedang | Tampilkan semua supplier, tanpa supplier utama wajib |
| Karyawan lama tidak punya data | Rendah | Tampilkan "Tidak dicatat", tidak backfill |
| Hasil follow up dobel | Sedang | Satu pelanggan satu hasil, hasil terbaru, prioritas tie-break |
| Cache UI/APK lama | Sedang | Naikkan versi aset dan versionCode APK |
| Data demo berubah | Rendah | Seed diuji di database dummy terpisah |

## Kriteria selesai keseluruhan

- Semua fitur pada dokumen ini tersedia dan dapat dipakai dari UI.
- Nota lama tetap utuh; nota baru memakai nomor angka.
- Total hutang, stok menipis, supplier, hasil follow up, karyawan, komisi, dan
  pengaturan struk bekerja sesuai keputusan.
- Tes dua stack lulus.
- Migrasi lulus pada salinan dummy.
- APK debug baru memuat seluruh perubahan.
- Laporan akhir mencantumkan file lama yang disentuh dan hasil verifikasi.

## 1. Ringkasan: total hutang dan stok menipis

### 1.1 Total hutang seluruhnya

- Tambah kartu **Total hutang** di Ringkasan.
- Isi kartu: total sisa pembayaran seluruh nota pelanggan yang masih berjalan.
- Subteks: jumlah nota dan jumlah pelanggan yang masih berhutang.
- Kartu dapat diklik untuk membuka daftar piutang.
- Sumber angka tetap backend. JavaScript tidak menghitung ulang nominal.
- Definisi: jumlah `sisa_bayar` dari nota berstatus NORMAL dan BELUM_LUNAS.
  Nota VOID dan nota lunas tidak dihitung.
- Data yang sudah ada sudah mencukupi; tidak perlu tabel baru.

### 1.2 Stok menipis dan stok habis

- Tambah kartu **Stok menipis** dan **Stok habis** di Ringkasan.
- Isi kartu stok menipis: item dengan jumlah di atas 0 dan sama dengan atau di
  bawah batas minimum.
- Isi kartu stok habis: item dengan jumlah 0 atau kurang.
- Klik masing-masing kartu membuka daftar stok yang sudah difilter.
- Daftar menampilkan nama barang, kode, jumlah tersisa, batas minimum, dan
  supplier terkait.
- Owner memiliki **Pengaturan stok menipis** untuk menetapkan batas minimum
  bawaan.
- Batas minimum dapat ditimpa per item.
- Perlu kolom `stok_minimum` per item stok dengan arti:
  - kosong: ikut batas bawaan Pengaturan
  - 0: peringatan item ini nonaktif
  - lebih dari 0: batas khusus item
- Item lama yang belum punya batas minimum mengikuti batas bawaan.
- Stok menipis dan stok habis langsung muncul setelah data stok atau
  pengaturan disimpan, tanpa proses sinkronisasi manual.

## 2. Supplier dan Follow up Reseller

### 2.1 Menu Supplier

- Tambah menu **Supplier** di sidebar, bersebelahan dengan Pelanggan.
- Data supplier minimal:
  - nama supplier
  - nomor HP/WhatsApp
  - alamat, opsional
  - catatan, opsional
  - status aktif/nonaktif
  - daftar barang yang disuplai
- Satu barang stok dapat dihubungkan ke **beberapa supplier**.
- Tidak ada supplier utama wajib; semua supplier yang terhubung ditampilkan.
- Tujuan: saat stok menipis, bengkel tahu harus menghubungi supplier mana.
- Supplier bukan pelanggan dan tidak memakai data piutang pelanggan.

### 2.2 Follow up Reseller

- Halaman Follow up dipisah menjadi dua bagian atau tab:
  - **Follow up Pelanggan**
  - **Follow up Reseller**
- Follow up Reseller menampilkan barang yang akan habis atau sudah menipis.
- Item dikelompokkan per supplier.
- Setiap item menampilkan nama barang, sisa stok, batas minimum, dan supplier.
- Aksi utama: **Chat** atau **WA** langsung ke supplier lewat `wa.me`.
- Tidak ada pengiriman otomatis; operator tetap menekan kirim di WhatsApp.
- Template pesan formal berisi nama bengkel, nama supplier, daftar barang yang
  menipis, sisa stok, dan permintaan ketersediaan/lead time.
- Teks pesan dapat diedit sebelum dibuka.
- Perlu jenis log WhatsApp baru untuk supplier, misalnya `supplier`.
- Perlu aturan jam kirim dan jeda agar tidak spam ke supplier.
- Bila supplier punya nomor tidak valid, tombol chat dinonaktifkan.
- Bila satu barang punya beberapa supplier, tampilkan semua pilihan chat.

## 3. Hasil follow up pelanggan

Tambahkan kartu hasil di Follow up Pelanggan. Sesuai permintaan, kartu hasil
**hanya menampilkan angka yang ada**, tanpa subteks panjang. Kategori yang
tidak memiliki data tidak perlu ditampilkan.

Kartu hasil:

- **Balik lagi**
- **Masih bagus**
- **Bermasalah**
- **Menolak**

### 3.1 Arti hasil

- **Balik lagi**: pelanggan yang benar-benar datang kembali ke bengkel setelah
  servis sebelumnya, baik untuk servis biasa, garansi, atau pekerjaan lain.
  Bukan sekadar berjanji akan datang.
- **Masih bagus**: hasil perbaikan bertahan, pelanggan tidak melaporkan masalah
  dan tidak kembali karena keluhan.
- **Bermasalah**: pelanggan kembali karena keluhan, klaim garansi, atau
  pekerjaan sebelumnya belum beres.
- **Menolak**: pelanggan menolak dihubungi, menolak servis lanjutan, atau
  meminta tidak perlu lagi.

"Masih bagus" dan "Bermasalah" adalah dua hasil yang berbeda dan tidak
digabung.

### 3.2 Sumber data hasil

- Dasar hitungan adalah **seluruh pesan pelanggan yang pernah dikirim lewat
  aplikasi**:
  - pesan Follow up: prospek, servis berkala, dan garansi
  - pengingat piutang
  - pesan kendaraan selesai/pengerjaan
- Pesan struk tidak dihitung karena bersifat dokumen transaksi.
- Pesan supplier tidak dihitung sebagai hasil follow up pelanggan.
- Setiap pesan atau pelanggan yang pernah dihubungi dipetakan ke satu hasil
  berdasarkan data yang sudah ada setelah pesan dikirim.
- **Balik lagi**: ada nota servis baru setelah pesan dikirim, termasuk garansi,
  servis biasa, dan pekerjaan lain.
- **Bermasalah**: ada klaim garansi atau status follow-up `MASIH_KENDALA`
  setelah pesan dikirim.
- **Masih bagus**: pelanggan menyatakan perbaikan baik atau tidak ada keluhan
  setelah pesan dikirim, dan tidak ada kunjungan masalah setelahnya.
- **Menolak**: pelanggan menolak dihubungi, menolak servis lanjutan, atau
  statusnya `TIDAK_DATANG`/`ARSIP` dengan alasan tidak perlu lagi.
- Tidak perlu membuat status hasil baru; gunakan data pesan, status follow-up,
  kunjungan servis, dan klaim garansi yang sudah ada.
- Satu pelanggan dihitung sekali. Bila punya beberapa pesan dengan hasil
  berbeda, yang dipakai adalah **hasil terbaru** berdasarkan waktu kejadian.
- Bila waktu hasil sama atau tidak bisa dibedakan, urutan prioritasnya:
  Balik lagi > Bermasalah > Masih bagus > Menolak.

### 3.3 Struktur halaman Follow up Pelanggan

- Judul halaman: **Follow up Pelanggan**.
- Tombol **Muat ulang**.
- Kartu kategori yang sudah ada tetap dipertahankan:
  - Piutang
  - Kendaraan selesai
  - Prospek
  - Berkendala
  - Servis berkala
  - Garansi akan habis
  - Akan datang: Garansi
  - Akan datang: Servis berkala
  - Akan datang: Prospek
- Kartu hasil ditambahkan setelah kartu kategori.
- Kartu hasil dapat diklik untuk membuka daftar pelanggan terkait.

### 3.4 Catatan

- "Masih bagus" saat ini adalah label untuk prospek berstatus `BARU`.
- Hasil dihitung dari seluruh pesan yang pernah dikirim, bukan hanya item yang
  masih aktif.
- Data lama tetap dipakai; tidak ada backfill hasil.
- Angka hasil memakai seluruh riwayat pesan. Filter periode dapat ditambahkan
  menyusul.
- Kategori tanpa data tidak ditampilkan; angka 0 tidak perlu ditampilkan.

## 4. Nomor nota angka berurutan

### 4.1 Perilaku yang disepakati

- Nomor nota baru berupa angka saja: `1`, `2`, `3`, dan seterusnya.
- Hanya **nota baru** yang memakai format angka.
- Nota lama tetap memakai nomor lama. Tidak ada penomoran ulang dan tidak ada
  backfill nomor lama.
- Nomor yang sudah dipakai tidak dipakai ulang.
- Contoh: nota 14 diretur, pelanggan berikutnya tetap mendapat nota 15.
- Nomor dibuat saat nota baru disimpan, bukan saat pelanggan dibuat.

### 4.2 Dampak teknis

- Generator nomor memakai satu penghitung berurutan yang aman dari dua
  transaksi bersamaan.
- Nomor tetap disimpan sebagai teks agar kompatibel dengan struk, retur, void,
  pencarian, dan laporan.
- Perlu indeks unik pada nomor nota.
- Nota lama dengan format lama tetap dapat dicari dan dicetak.
- Tampilan daftar nota dapat menampilkan campuran nomor lama dan nomor baru.

### 4.3 Catatan

- Karena nota lama tidak dinomori ulang, nomor `1` baru dapat muncul setelah
  nota lama yang masih memakai format `INV-...`.
- Penghitung nomor baru **dimulai dari 1** walaupun sudah ada nota lama.
  Format lama dan format angka tidak bentrok.
- Nomor baru dan nomor lama sama-sama dapat dicari dan dicetak.

## 5. Karyawan: mekanik, kasir, performa, dan komisi

### 5.1 Menu Karyawan

- Tambah menu **Karyawan** di sidebar, bersebelahan dengan Pelanggan.
- Data karyawan minimal:
  - nama
  - peran: Mekanik, Kasir, atau Keduanya
  - status aktif/nonaktif
  - nomor HP, opsional
  - catatan, opsional
- Karyawan adalah data operasional, bukan akun login. Hak akses aplikasi tetap
  milik pemilik.

### 5.2 Penugasan di nota

- Satu nota dapat memiliki 0, 1, 2, 3, atau lebih mekanik.
- Nota tanpa mekanik diperbolehkan, misalnya saat pemilik mengerjakan sendiri.
- Satu nota memiliki satu kasir dan namanya tercatat.
- Penugasan disimpan per nota, bukan per pelanggan.
- Nota lama yang belum punya data karyawan ditampilkan sebagai "Tidak dicatat".
- Perlu tabel penghubung nota-mekanik dan kolom kasir pada nota.
- Nama mekanik dan kasir **tercetak di struk**, dengan tombol on/off tersendiri
  di Pengaturan Struk.

### 5.3 Performa dan riwayat pengerjaan

- Menu Karyawan memiliki bagian performa per karyawan.
- Periode dapat dipilih: hari ini, bulan ini, atau rentang tanggal.
- Metrik yang ditampilkan:
  - jumlah nota yang ditangani
  - jumlah jasa yang dikerjakan
  - jumlah sparepart yang dipasang
  - total nilai servis
  - jumlah pelanggan unik
  - riwayat pengerjaan: tanggal, nomor nota, pelanggan, unit, jasa/part, nilai
- Untuk mekanik: dihitung dari nota tempat ia ditugaskan.
- Untuk kasir: dihitung dari nota yang ia proses.
- Riwayat pengerjaan dapat dibuka per karyawan.

### 5.4 Sharing komisi

- Performa karyawan dipakai untuk membantu pembagian komisi.
- Komisi dihitung **per nota**.
- Basis komisi dapat diatur oleh pemilik:
  - barang/sparepart saja
  - jasa saja
  - keduanya
- Bila satu nota punya beberapa mekanik, komisi dapat:
  - dibagi rata, atau
  - diatur manual per mekanik.
- Tampilkan estimasi komisi per karyawan dan riwayat per nota.
- Aplikasi hanya menghitung dan menampilkan estimasi; pembayaran komisi tetap
  dilakukan manual oleh pemilik.
- Bentuk komisi dapat dipilih owner per karyawan:
  - persentase dari basis komisi per nota, atau
  - nominal tetap per nota.
- Default awal: persentase. Nominal tetap disediakan untuk bengkel yang ingin
  angka komisi sama untuk setiap nota.
- Owner dapat menimpa nominal komisi pada nota tertentu secara manual.
- Tidak ada penggajian, absensi, atau slip gaji pada tahap ini.

## 6. Pengaturan struk

### 6.1 Tujuan

- Pemilik dapat memilih bagian mana yang tampil di struk.
- Setiap bagian atau tabel memiliki tombol on/off sendiri.
- Perhitungan uang tidak berubah; pengaturan hanya mengatur tampilan.

### 6.2 Bagian yang selalu tampil

- **Nama bengkel** selalu tampil dan tidak dapat dimatikan.
- Format tabel JASA dan PART tetap memakai susunan hardcoded yang sudah ada,
  tetapi masing-masing tabel tetap punya tombol on/off.

### 6.3 Bagian yang dapat diatur

- Header: tagline, alamat, telepon/WA.
- Nomor nota.
- Tanggal.
- Kasir.
- Mekanik.
- Nama karyawan pada baris tersendiri dapat dimatikan tanpa mematikan seluruh
  bagian karyawan.
- Pelanggan.
- Nomor HP pelanggan.
- Unit.
- Keluhan.
- Catatan.
- Tabel JASA.
- Tabel PART.
- Total Jasa.
- Total Part.
- Grand Total.
- Metode bayar.
- Nominal bayar.
- Kembalian.
- Status bayar.
- Garansi servis: status, tanggal berakhir, catatan garansi.
- Rekening bengkel untuk transfer.
- Footer "Simpan struk ini sebagai kartu bukti garansi".
- Ucapan terima kasih.

### 6.4 Perilaku

- Default semua bagian aktif agar struk tetap sama seperti sekarang.
- Bila tabel JASA atau PART tidak punya item, bagian tersebut otomatis tidak
  dicetak walaupun tombolnya aktif.
- Bila semua baris dalam satu bagian dimatikan, judul bagian ikut tidak
  dicetak.
- Pengaturan disimpan per instalasi dan berlaku untuk cetak berikutnya.
- Pratinjau struk di Pengaturan Struk menampilkan contoh dengan data nota
  terakhir atau data contoh.
- Pengaturan struk tidak mengubah nilai transaksi, stok, atau laporan.
- Pengaturan berlaku untuk **semua keluaran struk**: cetak thermal, cetak
  browser/Android, dan teks struk yang dikirim lewat WhatsApp.
- Nama mekanik dan kasir tetap dicatat di data nota. Bila baris karyawan
  dimatikan, nama tidak dicetak tetapi data tetap tersimpan.
- Nota lama yang belum punya data karyawan menampilkan "Tidak dicatat" bila
  baris karyawan aktif, atau tidak menampilkan baris itu bila dimatikan.

### 6.5 Contoh susunan struk

Contoh urutan yang dipakai sebagai acuan:

1. Nama bengkel, tagline, alamat, telepon/WA.
2. Nomor nota, tanggal, kasir, mekanik.
3. Pelanggan, nomor HP, unit, keluhan, catatan.
4. Tabel JASA.
5. Tabel PART.
6. Total Jasa, Total Part, Grand Total.
7. Metode bayar, bayar, kembali, status bayar.
8. Garansi servis.
9. Rekening bengkel.
10. Footer bukti garansi dan terima kasih.

## Keputusan yang sudah diambil

- Batas stok menipis ditetapkan per item.
- Satu barang dapat memiliki beberapa supplier.
- "Balik lagi" berarti pelanggan benar-benar datang kembali ke bengkel, untuk
  servis biasa, garansi, atau pekerjaan lain. Cukup tampilkan angka.
- "Masih bagus" dan "Bermasalah" adalah hasil berbeda. Cukup tampilkan angka.
- Hanya nota baru yang memakai nomor angka; nota lama tidak diubah.
- Nama mekanik dan kasir tercetak di struk.
- Performa karyawan dipakai untuk sharing komisi dan riwayat pengerjaan.
- Komisi dihitung per nota; basis dapat dipilih owner: barang, jasa, atau
  keduanya; pembagian mekanik dapat dibagi rata atau diatur manual.
- Setiap bagian struk memiliki tombol on/off; nama bengkel selalu tampil.
- Pengaturan struk berlaku untuk semua keluaran, termasuk teks WhatsApp.
- Hasil follow up dihitung dari seluruh pesan pelanggan yang pernah dikirim
  lewat aplikasi: Follow up, piutang, dan kendaraan selesai. Pesan struk dan
  supplier tidak dihitung.
- Satu pelanggan dihitung sekali memakai hasil terbaru. Bila waktunya sama,
  prioritas Balik lagi > Bermasalah > Masih bagus > Menolak.
- Kartu hasil hanya menampilkan kategori yang memiliki angka. Kategori kosong
  disembunyikan.
- Komisi per nota memakai mode persentase atau nominal tetap yang dipilih owner
  per karyawan; default persentase. Nominal per nota dapat ditimpa manual.
- Penomoran nota baru dimulai dari 1; nota lama tidak diubah.

## Pertanyaan terbuka

Tidak ada pertanyaan terbuka. Empat pertanyaan sebelumnya sudah dijawab dan
dicatat sebagai keputusan di bagian ini.

## Catatan

- `PETA_PENGEMBANGAN.md` lama tetap disimpan sebagai dokumen historis.
- `RENCANA_PERBAIKAN.md` sudah dihapus dan tidak dipakai lagi.
- Belum ada kode yang diubah untuk seluruh butir di dokumen ini.
