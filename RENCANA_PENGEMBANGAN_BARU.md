# Rencana Pengembangan Baru

Status: **ada rencana aktif yang belum diimplementasikan**. Seluruh butir
Tahap 1-8 sudah tersedia di aplikasi; rencana onboarding dan perluasan cakupan
bengkel dicatat di bawah dan belum dikerjakan.

- Acuan versi: web/desktop dan APK **2.6.0** (versionCode 18)
- Skema database: **38**
- Audit dilakukan terhadap kode backend, UI, dan tes yang ada.

## Aturan kerja

- Hanya rencana yang **belum ada** di aplikasi yang dicatat di sini.
- Tidak ada implementasi kode tanpa perintah eksplisit seperti "kerjakan"
  atau "implementasikan".
- Butir yang sudah selesai **dihapus** dari dokumen ini, bukan ditandai selesai.
- Dokumen ini bukan persetujuan implementasi.

## Rencana aktif — Onboarding dan bengkel umum

Status: **rencana, belum diimplementasikan**. Tidak ada kode yang diubah untuk
bagian ini.

### Tujuan

Aplikasi tidak lagi hanya untuk bengkel radiator. Aplikasi harus bisa dipakai
bengkel mobil, bengkel motor, atau keduanya, dengan 10 kelompok keahlian.
Pemilik memilih profil bengkel saat pertama kali memakai aplikasi; profil itu
bisa diubah lagi di Pengaturan. Login karyawan dikembangkan paling akhir.

### Alur pertama kali

1. **Pengenalan aplikasi — 3 layar.**
   - Layar 1: pengenalan aplikasi dan manfaatnya.
   - Layar 2: gambaran alur kerja bengkel.
   - Layar 3: penjelasan data lokal, backup, dan pilihan akses.
   - Setiap layar memiliki tombol **Lanjut**; layar terakhir masuk ke pilihan
     akses.
2. **Pilihan akses.**
   - **Login tanpa akun** — memakai aplikasi secara lokal. PIN pemilik yang
     sudah ada tetap dipertahankan sebagai pengunci data.
   - **Daftar menggunakan akun Gmail** — tombol Google. Identitas akun dipakai
     untuk pendaftaran; keputusan apakah data ikut cloud masih terbuka.
   - **Login karyawan** — hanya front-end pada tahap ini; autentikasi dan hak
     akses sebenarnya menyusul di tahap akhir.
3. **Profil bengkel** — wajib dijawab saat pertama kali, kecuali login
   karyawan.
   - Jenis bengkel: **Mobil saja**, **Motor saja**, atau **Mobil dan motor**.
   - Keahlian: pilih satu atau beberapa dari 10 keahlian, atau **Semua
     keahlian**.
4. **Login karyawan** langsung masuk tanpa memilih jenis bengkel dan keahlian.

Jenis bengkel dan keahlian wajib dijawab pada first run, lalu dapat diedit di
Pengaturan.

### 10 keahlian bengkel

1. **Radiator dan pendingin** — servis, kuras/kored, tambal, ganti core,
   water pump, dan sistem pendingin mesin.
2. **Mesin (engine/overhaul)** — turun mesin, piston, skir klep, korter
   silinder, dan komponen pembakaran.
3. **Transmisi dan kaki-kaki** — kemudi, suspensi, roda, rem, transmisi manual,
   matic, dan CVT.
4. **Kelistrikan dan AC** — kelistrikan bodi, alternator, aki, ECU/sensor,
   pengapian, serta AC mobil/motor.
5. **Spooring dan balancing** — sudut roda, keseimbangan ban, dan kestabilan
   laju.
6. **Cat, ketok magic, dan body repair** — bodi penyok, las sasis, dempul, dan
   cat ulang.
7. **Kaca film dan aksesoris** — kaca film, kaca retak, dan aksesoris interior
   atau eksterior.
8. **Bubut (machining)** — bubut piringan rem, facing blok/head, bushing, dan
   komponen logam presisi.
9. **Knalpot (exhaust)** — header, pipa, resonator, dan muffler.
10. **Injeksi dan ECU tuning (remap)** — injector ultrasonik, diagnostic
    scanner, dan kalibrasi ECU.

### Perluasan data dan UI

- Jenis unit minimal: **mobil** dan **motor**.
- Barang/unit copotan minimal: **mesin copotan**, **AC copotan**, **aki
  copotan**, dan kategori copotan lain yang ditentukan kemudian.
- Stok tidak lagi hanya sparepart radiator; kategori barang mengikuti keahlian
  dan jenis bengkel.
- Form unit, form servis, stok, follow-up, dan label struk menyesuaikan jenis
  bengkel serta keahlian yang dipilih.
- Data radiator yang sudah ada tetap dipertahankan; bengkel radiator lama
  mendapat profil awal Radiator dan pendingin tanpa kehilangan data.
- "Semua keahlian" menandai seluruh 10 keahlian aktif; pemilik dapat
  mempersempitnya lagi di Pengaturan.

### Login dan offline

- Login tanpa akun tetap menjadi jalur utama dan harus bekerja penuh offline.
- Google memerlukan internet. Perlu diputuskan apakah akun hanya untuk
  identitas/pendaftaran atau juga untuk backup cloud.
- Login karyawan hanya berupa tampilan pada tahap ini; belum ada akun, PIN
  karyawan, atau pembatasan hak akses.

### Tahapan yang direncanakan

1. **Onboarding dan pilihan akses** — 3 layar, tombol Lanjut, dan tiga pilihan
   akses (karyawan masih placeholder).
2. **Profil bengkel** — first-run wajib memilih jenis bengkel dan keahlian;
   dapat diedit di Pengaturan.
3. **Generalisasi unit dan barang** — kategori mobil/motor, copotan mesin/AC/
   aki, kategori stok, dan penyesuaian form/struk.
4. **Google sign-in** — backend/OAuth, penanganan offline, dan keputusan data
   cloud.
5. **Login karyawan dan hak akses** — tahap akhir.
6. **Uji matriks** — mobil, motor, keduanya, 10 keahlian, semua keahlian,
   offline, dan migrasi data radiator lama.

### Keputusan yang perlu dikunci sebelum implementasi

- Apakah PIN pemilik tetap dipakai setelah "Login tanpa akun".
- Fungsi akun Google: hanya identitas/pendaftaran atau termasuk backup cloud.
- Pemetaan data lama: unit `MOBIL`/`RADIATOR_ONLY` dan label radiator menjadi
  jenis bengkel/keahlian baru.
- Daftar kategori unit dan barang copotan yang final.
- Apakah "Semua keahlian" boleh dipersempit kapan saja tanpa mengubah data
  lama.
- Hak akses karyawan yang akan datang: kasir, mekanik, atau keduanya.

## Audit butir yang dihapus

| Butir lama | Bukti sudah ada di aplikasi |
| --- | --- |
| Total hutang dan stok menipis/habis di Ringkasan | `stock_items.stok_minimum`, perhitungan di `services/report_service.py`, kartu Ringkasan, filter stok, pengaturan batas minimum |
| Supplier dan Follow up Reseller | `suppliers`, `supplier_items`, `supplier_followups`, `api/supplier_routes.py`, menu Supplier, tab Reseller, chat WhatsApp supplier |
| Hasil follow up pelanggan (garansi, servis, prospek) | `followup_result_service` menghitung jumlah pesan follow-up, kembali ke bengkel beserta persentase, serta Masih bagus/Bermasalah/Menolak di halaman Follow up |
| Filter periode hasil follow-up | `followup_result_service.summary(start, end)`, query `start`/`end` di `/api/followup/results`, dan pilihan periode di kartu hasil Follow up |
| Nomor nota angka berurutan | `nota_counters` dan generator nomor di repository/nota baru |
| Karyawan, penugasan nota, performa, komisi, dan gaji | `employees`, `service_record_mechanics`, `service_record_commissions`, `salary_payments`, menu Karyawan, laporan performa |
| Pengaturan struk per bagian | `RECEIPT_FIELDS` di `services/settings_service.py`, toggle di Pengaturan, pembacaan toggle di layanan struk |

## Catatan

- Rencana rinci Tahap 1-8 beserta titik sentuh kode, daftar tes, migrasi, dan
  risiko dihapus karena fiturnya sudah terverifikasi.
- `PETA_PENGEMBANGAN.md` lama tetap disimpan sebagai dokumen historis.
- `RENCANA_PERBAIKAN.md` sudah dihapus dan tidak dipakai lagi.
