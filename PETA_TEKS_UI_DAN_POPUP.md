# Peta Teks UI dan Popup

Dokumen ini mencatat teks yang tampil di antarmuka BengkelPOS Radiator setelah
audit frontend dan penulisan ulang copy. Sumber audit:

- `frontend/index.html`
- `frontend/js/app.js`
- `frontend/js/printer-manager.js`
- adapter printer di `frontend/js/*-adapter.js`
- popup dan dialog konfirmasi yang dibuka dari kode tersebut

Aturan copy yang dipakai:

- Bahasa Indonesia formal untuk pesan pelanggan, bahasa kerja singkat untuk UI internal.
- Tidak memakai em dash atau en dash.
- Tidak menampilkan istilah internal, kode HTTP, nama berkas, alamat server, port,
  token, PIN, hash, atau isi basis data.
- Peringatan keamanan dan kehilangan data tetap lengkap.
- Nama bengkel pada pesan pelanggan mengikuti Pengaturan.
- Angka uang tetap berasal dari server.

---

## 1. Gerbang PIN

| Lokasi | Teks |
| --- | --- |
| Judul setup | Buat PIN pemilik |
| Keterangan setup | PIN 4 sampai 12 angka. Hanya pemilik yang perlu tahu. |
| Label | PIN baru |
| Label | Ulangi PIN |
| Tombol | Simpan PIN |
| Judul login | Masuk |
| Keterangan login | Masukkan PIN pemilik untuk membuka bengkel. |
| Label | PIN |
| Tombol | Buka aplikasi |
| Bantuan | Lupa PIN? Hubungi teknisi bengkel. Data transaksi tidak ikut terhapus. |
| Kesalahan PIN pendek | PIN minimal 4 angka. |
| Kesalahan PIN ulang | PIN yang diulang tidak sama. |
| Kesalahan umum | Aplikasi belum siap. Tutup lalu buka lagi. |
| Kesalahan sesi | Sesi berakhir. Masukkan PIN lagi. |
| Kesalahan percobaan | Terlalu banyak percobaan. Tunggu N detik. |

## 2. Kerangka aplikasi

| Lokasi | Teks |
| --- | --- |
| Merek | BengkelPOS Radiator |
| Tagline | Kasir dan servis radiator |
| Grup navigasi | Operasional |
| Menu | Ringkasan, Kasir, Riwayat servis, Pelanggan, Karyawan, Supplier, Follow up, Stok, Jasa, Laporan, Pengaturan |
| Status printer | Printer belum diatur |
| Catatan sidebar | Data tersimpan di perangkat ini |
| Versi | BengkelPOS Radiator v2.3.3 |
| Status koneksi | Berjalan tanpa internet |

## 3. Ringkasan

| Lokasi | Teks |
| --- | --- |
| Judul | Ringkasan hari ini |
| Keterangan | Servis dan pembayaran yang tercatat hari ini. |
| Kartu | Unit diservis, Tunai masuk, Transfer masuk, Garansi aktif, Total hutang, Stok menipis, Stok habis |
| Tabel | Transaksi terakhir. Nota terbaru yang tercatat di kasir. |
| Kolom | Waktu, No. nota, Pelanggan, Unit, Total, Metode |
| Tombol | Muat ulang, Cetak ulang |
| Kosong | Belum ada transaksi hari ini. Mulai dari tombol Servis baru. |
| Gagal muat | Ringkasan hari ini gagal dimuat. Coba muat ulang. |

### 3.1 Piutang pelanggan

| Lokasi | Teks |
| --- | --- |
| Judul | Piutang pelanggan |
| Keterangan | Nota yang belum lunas. / Nota belum lunas pelanggan ini. |
| Ringkasan | N pelanggan, N nota, total sisa Rp... |
| Kartu | Nama, nomor WA, jatuh tempo terdekat, nomor nota, tanggal servis |
| Pintasan | Ingatkan/Diingatkan, Chat, Pelunasan |
| Beberapa nota | Tombol N nota untuk membuka tabel nota |
| Ingatkan multi-nota | Satu pesan berisi semua nota. Setelah terkirim, semua tombol Ingatkan terkunci sampai tempo diubah per nota. |
| Tabel nota | Nota, Tanggal, Sisa, Jatuh tempo, Umur, Aksi |
| Aksi tabel | Pelunasan, Ingatkan/Diingatkan, Chat |
| Ubah tempo | Judul: Ubah jatuh tempo. Field: Tanggal jatuh tempo. Tombol: Batal, Simpan tanggal. |
| Pesan ubah tempo | Pengingat yang sudah dikirim akan aktif lagi pada tanggal baru. |
| Berhasil ubah tempo | Jatuh tempo diperbarui. Pengingat aktif lagi pada tanggal baru. |
| Kosong | Tidak ada piutang berjalan. |
| Gagal muat | Piutang gagal dimuat. Coba lagi. |
| Berhasil ingatkan | Pengingat dibuka di WhatsApp. Tekan kirim untuk mengirim pesan. |
| Jam pengingat | Pengingat hanya bisa dikirim antara pukul HH.MM-HH.MM. |

### 3.2 Follow up

| Lokasi | Teks |
| --- | --- |
| Judul | Follow up |
| Tab | Follow up Pelanggan, Follow up Reseller |
| Kartu hasil | Balik lagi, Masih bagus, Bermasalah, Menolak (hanya angka yang ada) |
| Kartu reseller | Supplier perlu dihubungi, Barang menipis, Barang habis, Total barang |
| Keterangan | Pengingat aktif pelanggan: piutang, prospek, servis berkala, dan garansi. |
| Tombol | Muat ulang |
| Kartu piutang | Piutang, N nota, total sisa |
| Kartu kendaraan | Kendaraan selesai, Siap dihubungi |
| Kartu prospek | Prospek, Kabar unit pasca servis |
| Kartu berkendala | Berkendala, Masih terkendala |
| Kartu servis | Servis berkala, Mendekati jadwal |
| Kartu garansi | Garansi akan habis, Perlu diingatkan |
| Kartu akan datang | Akan datang: Garansi, Akan datang: Servis berkala, Akan datang: Prospek, Sudah dijadwalkan |
| Daftar | Daftar follow-up / Prospek pelanggan / Servis berkala / Garansi akan habis / Berkendala / Akan datang: Garansi / Akan datang: Servis berkala / Akan datang: Prospek |
| Keterangan daftar | Pengingat aktif. Pilih item untuk melihat detail. / Jadwal kunjungan yang sudah disepakati. Pilih item untuk melihat detail. / Prospek yang masih terkendala. Pilih item untuk melihat detail. |
| Memuat | Memuat follow-up... |
| Kosong | Tidak ada item follow-up. |
| Gagal muat | Daftar follow-up gagal dimuat. Coba lagi. |
| Kartu item | Nama pelanggan, unit, nomor WA, jatuh tempo atau status, judul pengingat, nomor nota, status |
| Pintasan item | Ingatkan, WA, Detail, Status; pada Akan datang hanya Status dan WA |
| Status prospek | Masih bagus, Masih kendala / belum bisa, Akan datang service, Tidak perlu lagi |
| Status berkendala | Sudah datang, Tidak datang, Reschedule |
| Status servis/garansi | Akan datang service, Belum bisa dihubungi lagi, Tidak akan datang service, Tidak perlu lagi |
| Status piutang | Janji bayar, Belum bisa, Sudah bayar (cek sisa), Tidak merespons |
| Status akan datang | Datang, Tidak datang, Reschedule |
| Tombol detail akan datang | Datang, Tidak datang, Reschedule, Tutup |
| Detail akan datang | Data pelanggan, unit, tanggal service, dan nota lengkap |
| Judul status | Status follow-up |
| Field status | Status, Tanggal service/kunjungan, Tanggal janji bayar, Hubungi lagi setelah (2/4 minggu), Catatan |
| Tombol status | Tutup, Simpan status |
| Reschedule | Judul: Reschedule service. Field: Tanggal service baru, Catatan. Tombol: Tutup, Simpan jadwal. |
| Pesan reschedule | Jadwal service diperbarui. |
| Detail follow-up | Pelanggan, Domisili, WhatsApp, Unit, Jatuh tempo, Follow up terakhir, Tanggal service |
| Bagian detail | Nota servis, Rincian, Pesan WhatsApp |
| Konfirmasi datang | Tandai pelanggan datang? / Tandai pelanggan tidak datang? |
| Status terkunci | Lakukan Ingatkan dulu sebelum mengubah status. |
| Jam terkunci | Follow up hanya bisa dilakukan antara pukul HH.MM-HH.MM. |
| DNC | Perlu telepon, Pengingat Nx, Ditunda s.d. tanggal |
| Tombol tutup | Tutup |

### 3.2b Supplier

| Lokasi | Teks |
| --- | --- |
| Judul | Supplier |
| Keterangan | Daftar supplier dan barang yang disuplai. |
| Tombol | Muat ulang, + Supplier |
| Kolom | Nama, WhatsApp, Barang disuplai, Status |
| Form | Nama supplier, Nomor WhatsApp, Status, Alamat, Catatan, Barang yang disuplai |
| Pilih barang | Pilih sparepart, + Tambah barang, tabel Barang, Stok, Hapus |
| Follow up Reseller | Supplier perlu dihubungi, Barang menipis, Barang habis, Total barang, kartu supplier, Chat |
| Sakelar | Fitur supplier |

### 3.2c Karyawan

| Lokasi | Teks |
| --- | --- |
| Judul | Karyawan |
| Keterangan | Mekanik, kasir, performa, dan komisi. |
| Tombol | Muat ulang, + Karyawan |
| Kolom | Nama, Peran, WhatsApp, Gaji bulanan, Komisi, Status |
| Form | Nama, Peran, Status, Nomor WhatsApp, Catatan, Jenis imbalan, Gaji bulanan, Mode komisi, Basis komisi, Nilai komisi |
| Jenis imbalan | Komisi, Gaji, Komisi dan gaji |
| Performa | Periode, Nota, Jasa, Sparepart, Nilai servis, Pelanggan, Komisi, Riwayat, Komisi manual |
| Pembayaran gaji | Judul Pembayaran gaji, ringkasan N pembayaran dan total, tombol + Catat gaji |
| Kolom gaji | Tanggal, Karyawan, Periode, Metode, Nominal, Catatan, Edit, Hapus |
| Form gaji | Karyawan, Periode gaji, Tanggal bayar, Nominal, Metode, Catatan |
| Kosong gaji | Belum ada pembayaran gaji. |
| Sakelar | Fitur karyawan |

### 3.3 Kendaraan selesai

| Lokasi | Teks |
| --- | --- |
| Judul | Kendaraan selesai |
| Keterangan | Nota dengan unit ditinggal. Kabari pelanggan saat pengerjaan selesai. |
| Kartu | Nama, unit, nomor WA, nota, status, sisa bayar bila ada |
| Aksi | Status, Kabari WA, Sudah diambil |
| Modal status | Status, Janji ambil (opsional), Catatan, Riwayat status, Tutup, Simpan status |
| Pilihan status | Sedang dikerjakan, Menunggu sparepart, Menunggu persetujuan, Selesai siap diambil, Sudah diambil |
| Konfirmasi ambil | Tandai unit sudah diambil pelanggan? |
| Berhasil ambil | Unit ditandai sudah diambil. |
| Pesan WA | Pesan kendaraan selesai, pratinjau, Buka WhatsApp |
| Kosong | Tidak ada kendaraan yang menunggu diambil. |

## 4. Kasir

| Lokasi | Teks |
| --- | --- |
| Judul | Transaksi kasir |
| Keterangan | Ubah harga deal bila perlu. Tarif master tetap. |
| Tombol | Kosongkan form |
| Bagian pelanggan | Pilih pelanggan. Cari berdasarkan nama atau nomor HP. |
| Placeholder cari | Cari nama atau no. HP |
| Tombol | + Pelanggan baru |
| Bagian unit | Pilih unit servis. Mobil lengkap atau radiator copotan tanpa nopol. |
| Tautan | atau daftarkan unit baru |
| Pilihan unit | Mobil lengkap, Bawa radiator saja |
| Field unit | Nomor polisi, Jenis atau tipe mobil, Tahun, Tipe radiator, Kondisi awal, Keterangan tambahan |
| Placeholder unit | Contoh: B 1234 ABC, Contoh: Avanza 2018, 2018, Contoh: Radiator Canter 2-ply, Contoh: upper tank retak, Catatan unit (opsional) |
| Label otomatis | Label radiator otomatis. RAD-YYYYMMDD-XXX. Dibuat otomatis saat unit disimpan. |
| Tombol unit | Simpan unit |
| Keluhan | Keluhan awal. Pilih keluhan yang sering muncul atau tulis sendiri. |
| Field keluhan | Keluhan pelanggan, Catatan pengerjaan (opsional) |
| Placeholder keluhan | Contoh: air tekor, panas naik saat macet, Contoh: ganti upper tank, tes tekanan |
| Tombol keluhan | Simpan keluhan |
| Rincian | Rincian pengerjaan. Harga master hanya patokan. Harga deal bisa berbeda. |
| Jasa | Jasa, Harga deal tidak mengubah tarif master |
| Placeholder jasa | Nama jasa atau jasa lain, Qty, Harga deal |
| Tombol jasa | + Tambah jasa |
| Kolom jasa | Jasa, Qty, Harga deal, Servis berkala, Subtotal |
| Kosong jasa | Belum ada jasa ditambahkan. |
| Sparepart | Sparepart. Stok gudang berkurang otomatis. |
| Placeholder part | Nama sparepart atau sparepart lain, Qty, Harga deal, Modal (sparepart manual), Servis (bln) |
| Tombol part | + Tambah sparepart |
| Kolom part | Sparepart, Qty, Harga deal, Modal, Servis berkala, Subtotal |
| Kosong part | Belum ada sparepart ditambahkan. |
| Ringkasan | Ringkasan nota. Belum ada pelanggan dipilih. |
| Baris ringkasan | Subtotal jasa, Subtotal sparepart, Total nota |
| Pembayaran | Diskon (Rp), Metode pembayaran, Jenis pembayaran |
| Metode | Tunai, Hitung kembalian, Transfer, Uang pas |
| Jenis | Lunas, Kredit |
| Kredit | Rencana pembayaran (Rp). Nominal yang dijanjikan pelanggan. Boleh dikosongkan. |
| Tanggal rencana | Tanggal rencana pembayaran (opsional). Dipakai sebagai pengingat piutang. |
| Uang muka | Ada penambahan uang (uang muka). Uang muka diterima (Rp). Sisanya menjadi tagihan kredit. |
| Transfer | Rekening tujuan transfer, Uang diterima (Rp), Kembalian, Sisa tagihan |
| Unit ditinggal | Aktifkan bila kendaraan tetap di bengkel. Dipakai untuk follow-up saat kendaraan selesai. |
| Garansi | Garansi servis, Durasi garansi, 1 bulan (30 hari), 2 bulan (60 hari), 3 bulan (90 hari), 6 bulan (180 hari), 12 bulan (360 hari), Atur sendiri, Jumlah bulan (1 sampai 120), Catatan garansi |
| Aksi akhir | Periksa nota, Simpan tanpa cetak, Simpan & cetak struk |

## 5. Riwayat servis

| Lokasi | Teks |
| --- | --- |
| Judul | Riwayat servis |
| Keterangan | Cari nota, nopol, label radiator, atau nama pelanggan. |
| Tombol | Muat ulang |
| Placeholder | Cari nota, nopol, atau nama |
| Penghitung | 0 nota |
| Kolom | Waktu, No. nota, Pelanggan, Unit, Total, Metode, Garansi, Aksi |
| Kosong | Belum ada riwayat servis. |
| Gagal muat | Riwayat servis gagal dimuat. Coba muat ulang. |

## 6. Pelanggan

| Lokasi | Teks |
| --- | --- |
| Judul | Pelanggan |
| Keterangan | Daftar pelanggan bengkel beserta unit mobil dan radiatornya. |
| Tombol | Muat ulang, + Pelanggan baru |
| Kartu | Total pelanggan, Total unit terdaftar, Unit mobil, Radiator copotan |
| Placeholder | Cari nama atau nomor HP pelanggan |
| Penghitung | 0 pelanggan |
| Kosong | Belum ada pelanggan terdaftar. Tambahkan pelanggan baru untuk mulai mencatat unit servis. |
| Gagal muat | Gagal memuat data pelanggan. Coba muat ulang. |

## 7. Stok dan jasa

| Lokasi | Teks |
| --- | --- |
| Judul stok | Stok sparepart |
| Keterangan stok | Harga master menjadi patokan awal. |
| Tombol stok | + Sparepart |
| Kolom stok | Kode, Nama, Modal, Jual, Stok, Min., Servis berkala |
| Filter stok | Semua, Menipis, Habis |
| Kosong stok | Belum ada data sparepart. |
| Gagal stok | Data stok gagal dimuat. Coba muat ulang. |
| Judul jasa | Tarif jasa |
| Keterangan jasa | Tarif awal untuk kasir. |
| Tombol jasa | + Tarif jasa |
| Kolom jasa | Nama jasa, Tarif, Servis berkala |
| Kosong jasa | Belum ada tarif jasa. |

## 8. Laporan

| Lokasi | Teks |
| --- | --- |
| Judul | Laporan kas |
| Keterangan | Pemasukan tunai, transfer, estimasi laba sparepart/jasa, dan estimasi laba bersih setelah komisi dan gaji. |
| Periode | Hari ini, 7 hari terakhir, 30 hari terakhir, 1 tahun terakhir, Seluruhnya |
| Tombol | Tampilkan |
| Kartu | Total omset, Tunai, Transfer, Estimasi laba bersih sparepart, Estimasi laba bersih jasa, Laba bersih setelah dipotong gaji dan komisi |
| Meta | N transaksi, N unit, Diskon, Garansi aktif, Komisi karyawan, Gaji dibayar, Retur, Dibatalkan, Laba belum lengkap, Modal estimasi |
| Tabel | Transaksi pada periode |
| Kolom | Waktu, No. nota, Pelanggan, Unit, Total, Metode |
| Kosong | Tidak ada transaksi pada periode ini. |
| Rekap | Rekap harian periode. Hanya hari yang memiliki transaksi. |
| Kolom rekap | Tanggal, Transaksi, Omset, Tunai, Transfer, Laba bersih sparepart, Laba bersih jasa |
| Stok terjual | Stok pernah terjual. Harga mengikuti harga deal. Barang yang sama diurutkan menurut waktu. |
| Kolom stok | Barang, Qty, Harga akhir, Subtotal, Waktu, No. nota |
| Gagal muat | Laporan gagal dimuat. Coba lagi. |

## 9. Pengaturan

| Lokasi | Teks |
| --- | --- |
| Judul | Pengaturan bengkel |
| Keterangan | Identitas ini tampil di aplikasi dan tercetak pada struk. |
| Bagian | Tampilan, Identitas dan rekening, Pengingat dan follow-up, Printer, Backup, pemulihan dan berbagi database, Backup otomatis Telegram & lokal, Keamanan aplikasi |
| Tampilan | Warna aplikasi, Terang, Gelap |
| Identitas | Nama bengkel, Tagline, Alamat, Telepon, WhatsApp, Bank, Nomor rekening, Atas nama |
| Aksi identitas | Batalkan perubahan, Simpan pengaturan |
| Pengingat | Tempo piutang, Batas minimum stok bawaan, Prospek tahap 1/2/3, Jeda follow-up, Pengingat garansi H-, Arsip garansi, Tampilkan servis berkala H-, Jeda pengingat piutang, Maksimal pengingat piutang, Belum bisa dihubungi lagi, Belum bisa pilihan panjang, Batas tidak merespons, Batas pesan per hari, Batas pesan per bulan, Jeda prospek dan servis, Jam mulai follow up, Jam selesai follow up |
| Sakelar fitur | Fitur karyawan, Fitur supplier |
| Catatan jam | Di luar jam ini tombol Ingatkan dan pengingat piutang tidak bisa dipakai. |
| Aksi pengingat | Simpan pengaturan follow-up |
| Printer | Printer. Belum ada printer tersimpan. + Tambah printer |
| Kosong printer | Belum ada printer. Tambahkan printer Bluetooth, Wi-Fi atau LAN, USB OTG, cetak Android, atau cetak browser. |
| Catatan printer | Menghapus printer hanya menghapus konfigurasinya. Data transaksi, pelanggan, dan stok tidak ikut terhapus. |
| Backup | Folder backup, Belum dipilih, Pilih folder, Pulihkan data, Backup manual, Bagikan database |
| Catatan backup | Gunakan file backup dari perangkat lain saat memasang aplikasi baru. Data saat ini akan diganti, tetapi salinan pengaman dibuat otomatis sebelum pemulihan. |
| Telegram | Backup otomatis Telegram & lokal, Belum diatur, Kirim backup otomatis setiap hari, Jam kirim (waktu lokal), Chat ID penerima, Bot token Telegram |
| Catatan Telegram | Setiap kiriman berisi satu file backup lengkap. Nama file memakai rentang tanggal. Butuh koneksi internet. Jika jadwal terlewat, backup dikirim begitu internet tersedia. |
| Aksi Telegram | Simpan pengaturan, Kirim backup sekarang |
| Keamanan | Keamanan aplikasi. PIN diminta setiap aplikasi dibuka dan setelah aplikasi lama di latar belakang. Kunci otomatis setelah di latar belakang. Kunci sekarang |

## 10. Popup

| Popup | Judul dan isi |
| --- | --- |
| Pelanggan | Tambah pelanggan. Format nomor HP dirapikan otomatis. Nama pelanggan, Nomor HP, Alamat. Batal, Simpan pelanggan. |
| Printer | Tambah printer. Simpan perangkat sekali, lalu sambungkan saat dibutuhkan. Nama printer, Cara menghubungkan, Lebar kertas, Mode cetak, Encoding teks, Dukungan perangkat, Cari printer, Jadikan printer utama, Batal, Simpan printer. |
| Pilih printer | Pilih printer. Printer utama tetap tersimpan. Pilihan ini hanya untuk struk saat ini. Tutup. |
| Struk servis | Struk servis. Pratinjau struk sebelum dicetak. 58 mm, 80 mm. Printer tujuan. Coba lagi, Pilih printer lain, Buka pengaturan printer, Buka WhatsApp, Salin teks, Cetak browser, Cetak. |
| Periksa nota | Periksa nota. Pastikan seluruh isi nota sudah benar sebelum disimpan. Edit, Benar. |
| Daftar nota | Daftar nota. Waktu, No. nota, Pelanggan, Total, Metode. Tidak ada nota pada kategori ini. Tutup. |
| Detail nota | Detail nota. Tutup. |
| Preferensi pesan | Pelanggan memberi izin WhatsApp, Berhenti dihubungi (DNC), Simpan preferensi |
| Detail pelanggan | Detail pelanggan. Tutup, Buat servis. |
| Pembayaran gaji | Catat pembayaran gaji. Karyawan, Periode gaji, Tanggal bayar, Nominal, Metode, Catatan. Batal, Simpan gaji. |
| Pengaturan struk | Toggle per bagian; nama bengkel selalu tampil. |
| Tambah sparepart | Tambah sparepart. Kode, Jumlah stok, Nama sparepart, Harga modal, Harga jual patokan, Servis berkala, Batas minimum stok, Supplier. Batal, Simpan sparepart. |
| Tambah tarif jasa | Tambah tarif jasa. Patokan tarif untuk kasir. Nama jasa, Tarif standar (Rp), Servis berkala, Batal, Simpan jasa. |
| Pesan WhatsApp | Pesan WhatsApp. Periksa pesan sebelum dibuka di WhatsApp. Nomor tujuan, Isi pesan. Pesan dibuka di WhatsApp. Pengiriman tetap dilakukan oleh kasir. Tutup, Buka WhatsApp. |
| Daftar follow-up | Daftar follow-up. Pilih item untuk melihat detail. Tidak ada item follow-up. Tutup. |
| Detail follow-up | Detail follow-up. Data pelanggan, unit, nota, rincian, pesan WhatsApp. Datang, Tidak datang, Reschedule, Tutup. |
| Status follow-up | Status follow-up. Status, Tanggal service, Tanggal kunjungan, Catatan. Tutup, Simpan status. |
| Reschedule service | Reschedule service. Tanggal service baru, Catatan. Tutup, Simpan jadwal. |
| Piutang pelanggan | Piutang pelanggan. Nota yang belum lunas. Daftar kartu pelanggan. Tutup. |
| Ubah jatuh tempo | Ubah jatuh tempo. Tentukan tanggal pembayaran berikutnya. Tanggal jatuh tempo. Batal, Simpan tanggal. |
| Kendaraan selesai | Kendaraan selesai. Nota dengan unit ditinggal. Kabari pelanggan saat pengerjaan selesai. Tutup. |
| Konfirmasi browser | Tandai pelanggan datang? / Tandai pelanggan tidak datang? / Tandai unit sudah diambil pelanggan? / Proses klaim garansi untuk nota ini? / Hapus sparepart "..."? / Hapus tarif jasa "..."? / Reset seluruh isian transaksi? |

## 11. Pesan dinamis utama

| Jenis | Teks |
| --- | --- |
| Gagal muat | Pencarian pelanggan gagal. Coba lagi. / Gagal memuat unit pelanggan. Coba pilih pelanggan lagi. / Ringkasan hari ini gagal dimuat. Coba muat ulang. / Riwayat servis gagal dimuat. Coba muat ulang. / Detail nota gagal dimuat. Coba lagi. / Detail pelanggan gagal dimuat. Coba lagi. / Daftar follow-up gagal dimuat. Coba lagi. / Follow up gagal dimuat. Coba muat ulang. / Data stok gagal dimuat. Coba muat ulang. / Laporan gagal dimuat. Coba lagi. |
| Validasi transaksi | Pilih pelanggan terlebih dahulu. / Pilih unit servis terlebih dahulu. / Keluhan awal wajib diisi. / Simpan keluhan awal terlebih dahulu. / Tambahkan minimal satu jasa atau sparepart. / Angka uang harus rupiah bulat tanpa desimal. / Isi uang muka lebih dari Rp 0 atau matikan opsi penambahan uang. / Nominal pembayaran harus lebih dari nol. / Nominal melebihi sisa bayar nota. |
| Validasi follow-up | Pilih status terlebih dahulu. / Isi tanggal service. / Isi tanggal service baru. / Status prospek sudah "...". / Status follow-up diperbarui. / Jadwal service diperbarui. |
| Validasi printer | Nama printer wajib diisi. / Alamat Bluetooth harus berbentuk AA:BB:CC:DD:EE:FF. / Alamat IP printer wajib diisi. / Port harus antara 1 dan 65535. / Identitas perangkat USB wajib diisi. |
| Validasi pengaturan | Isi jam mulai dan jam selesai follow up. / Jam mulai dan jam selesai tidak boleh sama. / Nama bengkel minimal 2 karakter. |
| Berhasil simpan | Keluhan disimpan. / Data sparepart tersimpan. / Tarif jasa tersimpan. / Perubahan printer disimpan. / Pengaturan follow-up disimpan. / Pengaturan bengkel tersimpan. / Pengaturan Telegram tersimpan. / Data berhasil dipulihkan. |
| Gagal simpan | Pengaturan gagal disimpan. Coba lagi. / Pengaturan Telegram gagal disimpan. Coba lagi. / Data gagal dipulihkan. Periksa file backup lalu coba lagi. / Backup gagal dibuat. Periksa ruang penyimpanan lalu coba lagi. |
| WhatsApp | Nomor WhatsApp pelanggan belum valid. / Pengingat dibuka di WhatsApp. Tekan kirim untuk mengirim pesan. / Pemberitahuan kendaraan selesai tercatat. / Follow-up tercatat. / Pesan kendaraan selesai belum tersedia. |
| Cetak | Belum ada printer utama. Pilih printer di Pengaturan. / Cetak gagal. / Popup diblokir browser. Izinkan popup untuk mencetak. / Fitur printer tidak tersedia di perangkat ini. |

## 12. Perubahan copy yang diterapkan

| Sebelum | Sesudah |
| --- | --- |
| Akan datang — Garansi | Akan datang: Garansi |
| Akan datang — Servis berkala | Akan datang: Servis berkala |
| Siap dikabari | Siap dihubungi |
| Tanya service | Peluang servis |
| Jatuh tempo dekat | Mendekati jadwal |
| Ingatkan pelanggan | Perlu diingatkan |
| Sudah ada tanggal | Sudah dijadwalkan |
| Harga jasa dan sparepart bisa disesuaikan di kolom harga deal. | Ubah harga deal bila perlu. Tarif master tetap. |
| Harga master hanya patokan. Harga deal boleh naik atau turun. | Harga master hanya patokan. Harga deal bisa berbeda. |
| Stok gudang otomatis dipotong. | Stok gudang berkurang otomatis. |
| Harga master hanya patokan awal untuk kasir. | Harga master menjadi patokan awal. |
| Patokan ongkos pengerjaan untuk kasir. | Tarif awal untuk kasir. |
| Database real sampai detik ini. | Data terbaru saat ini. |
| Harga jual di sini adalah patokan awal kasir. | Harga jual ini menjadi patokan awal kasir. |
| Sudah follow up | Sudah dihubungi |
| Upaya follow-up tercatat. | Follow-up tercatat. |
| Pengingat dibuka di WhatsApp. Tekan kirim di WhatsApp. | Pengingat dibuka di WhatsApp. Tekan kirim untuk mengirim pesan. |
| Jam 08.00–20.00 | Jam 08.00-20.00 |

## 13. Konsistensi desain yang diterapkan

- Palet warna tidak diubah.
- Kontrol desktop disamakan: tombol utama 40 px, tombol kecil 34/30 px, input 40 px.
- Di layar sempit dan perangkat sentuh, tombol, input, tab, ikon, dan segmented control menjadi 44 px.
- Navigasi mobile menjadi satu baris yang dapat digeser, bukan grid tiga baris.
- Tab aktif otomatis digeser ke area terlihat.
- Tabel laporan mengisi sel terakhir dengan kartu penuh saat jumlah kartu ganjil.
- Modal piutang dan kendaraan selesai memakai isi yang dapat digeser dengan footer aksi tetap terlihat.
- Input pencarian pelanggan tidak lagi lebih pendek dari kontrol lain.
- Jarak antaraksi pada kartu dan footer modal disamakan 8 px.
