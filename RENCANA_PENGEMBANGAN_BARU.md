# Rencana Pengembangan Baru

Status: **perencanaan saja**. Belum ada kode, build APK, atau migrasi database
yang diubah untuk dokumen ini.

- Tanggal dibuat: 2026-11-01
- Acuan versi: web/desktop **2.2.6**, APK **2.2.6** (versionCode 9)
- Skema database saat ini: **21**
- Tes acuan: 322 pytest per stack (Pydantic v2 dan v1), 154 unit test Kotlin

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
| 1 | Total hutang seluruhnya dan stok menipis di Ringkasan | Ringkasan + piutang + stok | Tinggi | Rencana |
| 2 | Supplier dan Follow up Reseller | Supplier + stok + WhatsApp | Tinggi | Rencana |
| 3 | Hasil follow up pelanggan | Follow up + laporan | Tinggi | Rencana |
| 4 | Nomor nota angka berurutan | Nota | Tinggi | Rencana |
| 5 | Karyawan: mekanik, kasir, performa, dan komisi | Karyawan + nota + laporan | Tinggi | Rencana |
| 6 | Pengaturan struk dengan tombol on/off per bagian | Struk + pengaturan | Tinggi | Rencana |

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

### 1.2 Stok menipis

- Tambah kartu **Stok menipis** di Ringkasan.
- Isi kartu: jumlah item yang jumlah stoknya sama dengan atau di bawah batas.
- Klik kartu membuka daftar stok yang sudah difilter.
- Daftar menampilkan nama barang, kode, jumlah tersisa, batas minimum, dan
  supplier terkait.
- Batas minimum ditetapkan **per item**, bukan satu angka global.
- Perlu kolom baru `stok_minimum` per item stok.
- Nilai 0 berarti item tidak masuk peringatan otomatis.
- Item lama yang belum punya batas minimum dianggap 0 sampai diatur.

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

- Dasar hitungan adalah **seluruh pesan yang pernah dikirim lewat aplikasi**
  melalui tombol Ingatkan, WA, pengingat piutang, dan pesan kendaraan selesai.
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
- Bila satu pelanggan masuk beberapa hasil, angka mengikuti hasil terbaru atau
  prioritas yang disepakati agar tidak dobel.

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
- Bentuk komisi per nota dapat berupa persentase atau nominal tetap; keputusan
  akhirnya masih perlu ditetapkan sebelum implementasi.
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
- Hasil follow up dihitung dari seluruh pesan yang pernah dikirim lewat
  aplikasi. Kartu hanya menampilkan angka yang ada.
- Penomoran nota baru dimulai dari 1; nota lama tidak diubah.

## Pertanyaan terbuka

1. Bentuk komisi per nota: persentase dari basis komisi, atau nominal tetap per
   nota?
2. Bila satu pelanggan punya beberapa pesan dengan hasil berbeda, apakah angka
   memakai hasil terbaru atau prioritas Balik lagi > Bermasalah > Masih bagus >
   Menolak?
3. Apakah pesan kendaraan selesai dan pengingat piutang ikut dihitung sebagai
   hasil follow up, atau hanya pesan dari menu Follow up?
4. Kategori hasil yang tidak punya data: disembunyikan sepenuhnya atau tetap
   tampil dengan angka 0?

## Catatan

- `PETA_PENGEMBANGAN.md` lama tetap disimpan sebagai dokumen historis.
- `RENCANA_PERBAIKAN.md` sudah dihapus dan tidak dipakai lagi.
- Belum ada kode yang diubah untuk seluruh butir di dokumen ini.
