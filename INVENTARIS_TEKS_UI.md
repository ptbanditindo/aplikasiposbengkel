# Inventaris Teks UI dan Popup

Berkas ini mencatat semua teks yang tampil di antarmuka BengkelPOS Radiator setelah
penulisan ulang copy. Sumber:

- `frontend/index.html` untuk teks statis, label, placeholder, dan judul popup.
- `frontend/js/app.js` untuk teks dinamis, toast, dialog konfirmasi, dan label status.
- `frontend/js/printer-manager.js`, `frontend/js/api-client.js`, dan adapter printer
  untuk pesan kesalahan yang tampil ke pengguna.
- `android/app/src/main/res/values/strings.xml` untuk layar native APK.

Aturan yang dipakai:

- Bahasa Indonesia sehari-hari, kalimat pendek, huruf kapital di awal kalimat.
- Tidak memakai em dash atau en dash di dalam kalimat.
- Tidak menampilkan istilah internal, kode HTTP, nama berkas program, alamat server,
  nomor port, token, PIN, hash, atau isi basis data.
- Peringatan yang menyangkut keamanan dan kehilangan data tetap ditampilkan lengkap.
- Angka uang tetap berasal dari server. UI hanya menampilkan nilai yang sudah dihitung.

---

## 1. Gerbang PIN (web)

| Lokasi | Teks |
| --- | --- |
| Judul setup | Buat PIN kasir |
| Keterangan setup | PIN 4 sampai 12 angka. Hanya pemilik yang perlu tahu. |
| Label | PIN baru |
| Label | Ulangi PIN |
| Tombol | Simpan PIN |
| Judul login | Masuk |
| Keterangan login | Masukkan PIN kasir untuk membuka bengkel. |
| Label | PIN |
| Tombol | Buka kasir |
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
| Menu | Ringkasan, Kasir, Riwayat servis, Pelanggan, Stok, Jasa, Laporan, Pengaturan |
| Status printer | Printer belum siap |
| Catatan kaki sidebar | Data tersimpan di perangkat ini |
| Versi | BengkelPOS Radiator v2.2 |
| Status koneksi | Berjalan tanpa internet |

## 3. Ringkasan

| Lokasi | Teks |
| --- | --- |
| Judul | Ringkasan hari ini |
| Keterangan | Servis dan pembayaran yang tercatat hari ini. |
| Tombol | Pelanggan baru, Servis baru |
| Kartu | Unit diservis, Tunai masuk, Transfer masuk, Garansi aktif |
| Tabel | Transaksi terakhir. Nota terbaru yang tercatat di kasir. |
| Kolom | Waktu, No. nota, Pelanggan, Unit, Total, Metode |
| Tombol | Muat ulang |
| Kosong | Belum ada transaksi hari ini. Mulai dari tombol Servis baru. |
| Gagal muat | Ringkasan hari ini gagal dimuat. Coba muat ulang. |

## 4. Kasir

| Lokasi | Teks |
| --- | --- |
| Judul | Transaksi kasir |
| Keterangan | Harga jasa dan sparepart bisa disesuaikan di kolom harga deal. |
| Tombol | Kosongkan form |
| Langkah 1 | Pilih pelanggan. Cari berdasarkan nama atau nomor HP. |
| Pencarian pelanggan | Cari nama atau no. HP |
| Tombol | + Pelanggan baru |
| Langkah 2 | Pilih unit servis. Mobil lengkap atau radiator copotan tanpa nopol. |
| Tautan | atau daftarkan unit baru |
| Pilihan unit | Mobil lengkap, Bawa radiator saja |
| Kolom unit | Nomor polisi, Jenis atau tipe mobil, Tahun, Tipe radiator, Kondisi awal, Keterangan tambahan |
| Label otomatis | Label radiator otomatis. Dibuat otomatis saat unit disimpan. |
| Tombol | Simpan unit |
| Langkah 3 | Keluhan awal. Pilih keluhan yang sering muncul atau tulis sendiri. |
| Kolom | Keluhan pelanggan, Catatan pengerjaan (opsional) |
| Langkah 4 | Rincian pengerjaan. Harga master hanya patokan. Harga deal boleh naik atau turun. |
| Tabel jasa | Jasa, Qty, Harga deal, Subtotal |
| Keterangan jasa | Harga deal tidak mengubah tarif master |
| Tombol | + Tambah jasa, + Tambah sparepart |
| Tabel sparepart | Sparepart, Qty, Harga deal, Modal, Subtotal |
| Keterangan stok | Stok gudang otomatis dipotong. Stok tersedia N. Harga patokan Rp X. |
| Zona input | Blok jasa dan blok sparepart memakai latar tipis berbeda beserta penanda warna pada judul dan tombol tambah, sehingga kasir mudah membedakan keduanya. |
| Kosong | Belum ada jasa ditambahkan. Belum ada sparepart ditambahkan. |
| Ringkasan | Ringkasan nota, Subtotal jasa, Subtotal sparepart, Total nota, Diskon (Rp) |
| Catatan | Perkiraan sementara. Nilai final dicatat saat nota disimpan. |
| Pembayaran | Metode pembayaran, Tunai, Hitung kembalian, Transfer, Uang pas, Rekening tujuan transfer, Uang diterima (Rp), Kembalian |
| Garansi | Garansi servis, Durasi garansi, 1 bulan (30 hari), 2 bulan (60 hari), 3 bulan (90 hari), 6 bulan (180 hari), 12 bulan (360 hari), Atur sendiri, Jumlah bulan (1 sampai 120), Catatan garansi |
| Tombol | Simpan dan cetak struk, Simpan tanpa cetak |
| Validasi | Pilih pelanggan terlebih dahulu. Pilih unit servis terlebih dahulu. Keluhan awal wajib diisi. Tambahkan minimal satu jasa atau sparepart. |
| Validasi uang | Angka uang harus rupiah bulat tanpa desimal. Label harus berupa rupiah bulat tanpa desimal. Contoh: 150.000. |
| Format uang | Kolom uang otomatis memakai pemisah ribuan saat diketik, misalnya 1.000.000. Nilai yang dikirim ke backend tetap angka bulat tanpa pemisah, dan total tetap dihitung backend. |
| Konfirmasi stok | <pesan server>\n\nTetap simpan transaksi dengan stok minus? |
| Sukses | Nota <nomor> berhasil disimpan. |
| Gagal | <pesan kesalahan yang sudah disederhanakan> |
| Reset | Reset seluruh isian transaksi? |

## 5. Riwayat servis

| Lokasi | Teks |
| --- | --- |
| Judul | Riwayat servis |
| Pencarian | Cari nota, nopol, label radiator, atau nama pelanggan. |
| Placeholder pencarian | Cari nota, nopol, atau nama |
| Tombol | Muat ulang |
| Jumlah | N nota |
| Kolom | Waktu, No. nota, Pelanggan, Unit, Total, Metode, Garansi, Aksi |
| Tombol baris | Cetak ulang, Retur, Batalkan nota, Klaim garansi |
| Lencana | Tunai, Transfer, Dibatalkan, Tanpa garansi, Sudah diklaim, Aktif s/d <tanggal>, Kedaluwarsa |
| Kosong | Belum ada riwayat servis. |
| Gagal muat | Riwayat servis gagal dimuat. Coba muat ulang. |
| Retur | Isi jumlah retur minimal satu item. Alasan retur minimal 3 karakter. Simpan retur N item? Stok akan diperbarui. |
| Sukses retur | Retur tersimpan. |
| Pembatalan | Batalkan nota <nomor>? Stok dikembalikan dan nota tetap tersimpan di riwayat. |
| Alasan batal | Alasan pembatalan (minimal 3 karakter): |
| Sukses batal | Nota dibatalkan. |
| Klaim | Proses klaim garansi untuk nota ini? |
| Sukses klaim | Klaim garansi tercatat. |
| Detail gagal | Detail nota gagal dimuat. Coba lagi. |

## 6. Detail nota (popup)

| Lokasi | Teks |
| --- | --- |
| Judul | Detail nota |
| Tombol | Tutup, Lihat pelanggan, Retur, Batalkan nota, Cetak struk |
| Pembatalan | Nota dibatalkan |
| Bagian | Pelanggan dan unit, Keluhan awal, Catatan pengerjaan, Rincian jasa, Sparepart, Catatan garansi, Riwayat retur |
| Kolom | Jasa, Qty, Harga, Subtotal, Barang, Harga deal |
| Total | Total jasa, Total part, Diskon, Bayar, Kembalian, Total servis, Retur, Total neto |
| Info | Waktu servis, Metode bayar, Status garansi, Garansi sampai |
| Retur | Retur jasa / sparepart. Isi jumlah yang diretur. Stok sparepart kembali otomatis dan tidak bisa diretur dua kali. |
| Kolom retur | Alasan retur, Contoh: barang tidak cocok / salah pasang |
| Catatan retur | Operator pencatat diambil otomatis dari sesi yang masuk. |
| Tombol retur | Batal, Simpan retur |
| Kosong | Tidak ada rincian jasa. Tidak ada sparepart. Semua item nota ini sudah diretur. |
| Label modal | Laba <nominal>, modal belum diisi, modal estimasi |

## 7. Detail pelanggan (popup)

| Lokasi | Teks |
| --- | --- |
| Judul | Detail pelanggan |
| Tombol | Tutup, Buat servis |
| Ringkasan | Total unit, Unit mobil, Radiator copotan |
| Bagian | Unit terdaftar (N) |
| Bagian riwayat | Riwayat servis (N) |
| Memuat riwayat | Memuat riwayat servis... |
| Kosong riwayat | Belum ada riwayat servis untuk pelanggan ini. |
| Gagal riwayat | Riwayat servis gagal dimuat. Coba lagi. |
| Baris riwayat | No. nota, unit dan jenis mobil, total neto, tanggal servis, metode bayar, status garansi. Ketuk baris untuk membuka detail nota. |
| Kosong | Belum ada unit terdaftar. |
| Gagal muat | Detail pelanggan gagal dimuat. Coba lagi. |
| Tidak ditemukan | Data pelanggan tidak ditemukan. |

## 8. Pelanggan

| Lokasi | Teks |
| --- | --- |
| Judul | Pelanggan |
| Keterangan | Daftar pelanggan bengkel beserta unit mobil dan radiatornya. |
| Pencarian | Cari nama, nomor HP, atau alamat |
| Placeholder pencarian | Cari nama atau nomor HP pelanggan |
| Tombol | Muat ulang, + Pelanggan baru |
| Kartu | Total pelanggan, Total unit terdaftar, Unit mobil, Radiator copotan |
| Jumlah | N pelanggan |
| Kosong | Belum ada pelanggan terdaftar. Tambahkan pelanggan baru untuk mulai mencatat unit servis. |
| Hasil kosong | Tidak ada pelanggan yang cocok dengan pencarian "<kata kunci>". |
| Kartu pelanggan | Terdaftar <tanggal>, N mobil, N radiator, Belum ada unit, Buat servis |
| Gagal muat | Gagal memuat data pelanggan. Coba muat ulang. |
| Pencarian gagal | Pencarian pelanggan gagal. Coba lagi. |
| Unit gagal | Gagal memuat unit pelanggan. Coba pilih pelanggan lagi. |

## 9. Popup pelanggan dan unit

| Lokasi | Teks |
| --- | --- |
| Judul | Tambah pelanggan |
| Keterangan | Format nomor HP dirapikan otomatis. |
| Kolom | Nama pelanggan, Nomor HP, Alamat |
| Tombol | Batal, Simpan pelanggan |
| Sukses | Pelanggan <nama> tersimpan. |
| Label unit | Tanpa nopol |
| Pilihan | Mobil lengkap, Radiator copotan |
| Sukses unit | Unit mobil <nopol> tersimpan. Unit radiator <label> tersimpan. |
| Validasi | Pilih pelanggan terlebih dahulu. Nomor polisi wajib diisi untuk mobil. |

## 10. Stok dan jasa

| Lokasi | Teks |
| --- | --- |
| Judul stok | Stok sparepart. Harga master hanya patokan awal untuk kasir. |
| Tombol | + Sparepart |
| Panel | Sparepart gudang |
| Kolom | Kode, Nama, Modal, Jual, Stok |
| Kosong | Belum ada data sparepart. |
| Ringkasan | N item · N stok menipis (3 atau kurang) |
| Judul jasa | Tarif jasa. Patokan ongkos pengerjaan untuk kasir. |
| Tombol | + Tarif jasa |
| Panel | Daftar tarif jasa |
| Kolom | Nama jasa, Tarif |
| Kosong | Belum ada tarif jasa. |
| Gagal muat stok | Data stok gagal dimuat. Coba muat ulang. |
| Popup stok | Tambah sparepart / Edit sparepart. Harga jual di sini adalah patokan awal kasir. |
| Kolom popup stok | Kode, Jumlah stok, Nama sparepart, Harga modal, Harga jual patokan |
| Tombol popup stok | Batal, Simpan sparepart |
| Sukses stok | Data sparepart tersimpan. |
| Hapus stok | Hapus sparepart "<nama>"? |
| Sukses hapus stok | Sparepart dihapus. |
| Popup jasa | Tambah tarif jasa / Edit tarif jasa. Patokan tarif untuk kasir. |
| Kolom popup jasa | Nama jasa, Tarif standar (Rp) |
| Tombol popup jasa | Batal, Simpan jasa |
| Sukses jasa | Tarif jasa tersimpan. |
| Hapus jasa | Hapus tarif jasa "<nama>"? |
| Sukses hapus jasa | Tarif jasa dihapus. |

## 11. Laporan

| Lokasi | Teks |
| --- | --- |
| Judul | Laporan kas |
| Keterangan | Pemasukan tunai, transfer, dan estimasi laba kotor sparepart. |
| Periode | Periode laporan, Hari ini, 7 hari terakhir, 30 hari terakhir, 1 tahun terakhir, Seluruhnya |
| Tombol | Tampilkan |
| Kartu | Total omset, Tunai, Transfer, Estimasi laba kotor sparepart |
| Tabel transaksi | Transaksi pada periode, Waktu, No. nota, Pelanggan, Unit, Total, Metode |
| Kosong | Tidak ada transaksi pada periode ini. |
| Rekap | Rekap harian periode. Hanya hari yang memiliki transaksi. |
| Kolom rekap | Tanggal, Transaksi, Omset, Tunai, Transfer, Laba kotor sparepart |
| Bagian | Stok pernah terjual. Harga mengikuti harga deal. Barang yang sama diurutkan menurut waktu. |
| Kolom terjual | Barang, Qty, Harga akhir, Subtotal, Waktu, No. nota |
| Meta | <tanggal> sampai <tanggal>, N transaksi, N unit, Diskon, Garansi aktif, Retur, Dibatalkan, Laba belum lengkap, Modal estimasi |
| Label laba | Laba kotor <nominal>, retur -<nominal>, modal sparepart belum diisi |
| Gagal muat | Laporan gagal dimuat. Coba lagi. |
| Catatan tombol backup | Tombol backup di halaman Laporan sudah dihapus. Backup hanya tersedia di Pengaturan. |

## 12. Pengaturan

| Lokasi | Teks |
| --- | --- |
| Judul | Pengaturan bengkel |
| Keterangan | Identitas ini tampil di aplikasi dan tercetak pada struk. |
| Bagian identitas | Identitas dan rekening. Perubahan langsung tampil di aplikasi dan struk. |
| Kolom identitas | Nama bengkel, Tagline, Alamat, Telepon, WhatsApp, Bank, Nomor rekening, Atas nama |
| Tombol | Batalkan perubahan, Simpan pengaturan |
| Sukses | Pengaturan bengkel tersimpan. |
| Validasi | Nama bengkel minimal 2 karakter. |
| Gagal | Pengaturan gagal disimpan. Coba lagi. |

### 12.1 Tampilan

| Lokasi | Teks |
| --- | --- |
| Judul | Tampilan |
| Keterangan | Pilih warna antarmuka. Pilihan tersimpan di perangkat ini. |
| Label | Warna aplikasi |
| Pilihan | Terang, Gelap |

### 12.2 Printer

| Lokasi | Teks |
| --- | --- |
| Judul | Printer |
| Ringkasan | Belum ada printer tersimpan. N printer tersimpan · Utama: <nama> · Belum ada printer utama |
| Tombol | + Tambah printer |
| Kosong | Belum ada printer. Tambahkan printer Bluetooth, Wi-Fi atau LAN, USB OTG, cetak Android, atau cetak browser. |
| Catatan | Menghapus printer hanya menghapus konfigurasinya. Data transaksi, pelanggan, dan stok tidak ikut terhapus. |
| Tombol baris | Hubungkan, Putuskan, Hubungkan ulang, Jadikan utama, Tes cetak, Ubah, Hapus |
| Meta | Alamat Bluetooth, IP:port, USB, 58/80 mm, Printer thermal, Teks, Cetak Android, Cetak browser, Terakhir dipakai, Terakhir terhubung, Belum pernah |
| Status | Siap dipakai, Tidak tersedia, Tidak didukung, Belum diatur, Utama |
| Galat | Jenis printer ini belum didukung di perangkat ini. Pengaturan printer gagal dimuat. Coba muat ulang. |
| Konfirmasi hapus | Hapus printer "<nama>" dari daftar? Data transaksi, pelanggan, dan stok tidak dihapus. |
| Sukses utama | Printer utama diganti ke <nama>. Printer sebelumnya tetap tersimpan. |
| Sukses koneksi | Printer berhasil terhubung. Koneksi printer diputus. Printer tetap tersimpan. Printer berhasil dihubungkan ulang. |
| Gagal | <pesan singkat dari perangkat> |
| Peringatan pengaturan | Pengaturan printer hanya untuk pemilik. |

### 12.3 Popup printer

| Lokasi | Teks |
| --- | --- |
| Judul | Tambah printer / Ubah printer |
| Keterangan | Simpan perangkat sekali, lalu sambungkan saat dibutuhkan. |
| Kolom | Nama printer, Cara menghubungkan, Lebar kertas, Mode cetak, Encoding teks |
| Pilihan cara | Bluetooth, Wi-Fi / LAN, USB OTG, Cetak Android, Cetak browser |
| Pilihan kertas | 58 mm, 80 mm |
| Kolom alamat | Alamat Bluetooth, IP printer, Port, Identitas perangkat USB |
| Bantuan Bluetooth | Cetak lewat dialog Android. Pilih printer dan jumlah salinan di sana; aplikasi tidak menganggap printer selalu terhubung. |
| Bantuan browser | Cetak lewat dialog browser. Pilih printer biasa atau printer thermal yang sudah terpasang di komputer. |
| Pencarian | Cari printer, Cari printer Bluetooth, Cari printer jaringan, Cari printer USB |
| Petunjuk cari | Pastikan Bluetooth aktif dan printer siap dipasangkan. Pastikan printer dan perangkat berada di jaringan yang sama. Hubungkan kabel OTG lalu izinkan akses USB saat diminta. |
| Proses | Mencari printer... Mencari printer yang terdeteksi di perangkat ini. |
| Kosong | Tidak ada printer ditemukan. Masukkan data printer secara manual. |
| Peringatan ubah | Perubahan alamat atau jenis koneksi akan memutus sesi printer ini. |
| Tombol | Cari printer, Jadikan printer utama, Batal, Simpan printer, Simpan perubahan |
| Validasi | Nama printer wajib diisi. Alamat Bluetooth harus berbentuk AA:BB:CC:DD:EE:FF. Alamat IP printer wajib diisi. Port harus antara 1 dan 65535. Identitas perangkat USB wajib diisi. |
| Sukses | Perubahan printer disimpan. Printer <nama> disimpan. |
| Gagal muat | Gagal memuat daftar printer. Coba lagi. |
| Pencarian tidak tersedia | Pencarian printer ini tidak tersedia di perangkat. |
| Info masukan | Data printer dimasukkan. Periksa lalu simpan. |

### 12.4 Backup dan pemulihan

| Lokasi | Teks |
| --- | --- |
| Judul | Backup dan pemulihan |
| Keterangan | Satu file berisi data pelanggan, unit, riwayat servis, transaksi keuangan, stok, dan pengaturan bengkel. |
| Petunjuk | Gunakan file backup dari perangkat lain saat memasang aplikasi baru. Data saat ini akan diganti, tetapi salinan pengaman dibuat otomatis sebelum pemulihan. |
| Tombol | Unduh backup, Bagikan backup, Pulihkan data |
| Konfirmasi pulihkan | Pulihkan data dari "<nama file>"? Seluruh data saat ini akan diganti. Salinan pengaman tetap dibuat otomatis. |
| Proses | Memulihkan... |
| Sukses | Data berhasil dipulihkan. Menyiapkan ulang aplikasi... Data berhasil dipulihkan. Memuat ulang aplikasi... |
| Gagal muat ulang | Data sudah dipulihkan, tetapi aplikasi gagal dimuat ulang. Tutup lalu buka aplikasi. |
| Gagal pulihkan | Data gagal dipulihkan. Periksa file backup lalu coba lagi. |
| Proses backup | Membuat backup... |
| Sukses backup | Backup tersimpan ke <lokasi>: <nama file>. |
| Gagal backup | Backup gagal dibuat. Periksa ruang penyimpanan lalu coba lagi. |
| Gagal bagikan | Backup gagal dibagikan. Coba lagi. |

### 12.5 Backup otomatis Telegram

| Lokasi | Teks |
| --- | --- |
| Judul | Backup otomatis Telegram |
| Status awal | Belum diatur. |
| Peringatan token | Token Telegram perlu diisi ulang agar backup otomatis berjalan. |
| Status backup | Belum ada backup terjadwal. Backup terakhir: <waktu>. Backup otomatis terakhir gagal. Periksa ruang penyimpanan dan izin aplikasi. |
| Peringatan basi | Backup terakhir lebih dari 2 hari. Periksa jadwal dan ruang penyimpanan. |
| Sakelar | Kirim backup otomatis setiap hari |
| Kolom | Jam kirim (waktu lokal), Chat ID penerima, Bot token Telegram |
| Status jadwal | Aktif, mengirim otomatis setiap hari pukul <jam>. Pengiriman otomatis nonaktif (jadwal <jam>). |
| Riwayat | Terakhir dikirim <waktu>. Belum pernah dikirim. Pengiriman terakhir gagal. Periksa token, Chat ID, dan koneksi internet. |
| Penjelasan | Setiap kiriman berisi satu file backup lengkap: pelanggan, unit, riwayat servis, transaksi keuangan, stok, dan pengaturan bengkel. Nama file memakai rentang tanggal, jadi tidak ada file terpisah yang tumpang tindih. Butuh koneksi internet. Jika jadwal terlewat, backup dikirim begitu internet tersedia. |
| Tombol | Kirim backup sekarang, Simpan pengaturan Telegram |
| Validasi kirim | Simpan bot token dan chat ID terlebih dahulu. |
| Sukses kirim | Backup terkirim: <nama file> (N nota). |
| Gagal kirim | Backup gagal dikirim. Periksa token, Chat ID, dan koneksi internet. |
| Sukses simpan | Pengaturan Telegram tersimpan. |
| Gagal simpan | Pengaturan Telegram gagal disimpan. Coba lagi. |

### 12.6 PIN kasir dan keamanan

| Lokasi | Teks |
| --- | --- |
| Judul | PIN kasir |
| Status | PIN kasir aktif. Kasir dapat masuk memakai PIN-nya sendiri. Belum diatur. Hanya pemilik yang dapat membuat PIN kasir. |
| Keterangan | Kasir dapat membuat transaksi, membatalkan nota, dan mencatat retur. Pengaturan, backup, dan pemulihan data tetap khusus pemilik. |
| Kolom | PIN kasir (4 sampai 12 angka) |
| Tombol | Hapus PIN kasir, Simpan PIN kasir |
| Validasi | PIN kasir minimal 4 angka. |
| Sukses | PIN kasir tersimpan. |
| Gagal | PIN kasir gagal disimpan. Coba lagi. |
| Hapus | Hapus PIN kasir? Kasir tidak dapat masuk lagi sampai PIN baru dibuat. |
| Sukses hapus | PIN kasir dihapus. |
| Gagal hapus | PIN kasir gagal dihapus. Coba lagi. |
| Judul keamanan | Keamanan aplikasi |
| Keterangan | PIN diminta setiap aplikasi dibuka dan setelah aplikasi lama di latar belakang. |
| Pilihan kunci | Kunci otomatis setelah di latar belakang, 1 menit, 2 menit, 5 menit, 10 menit, 30 menit |
| Tombol | Kunci sekarang |

## 13. Popup struk dan printer

| Lokasi | Teks |
| --- | --- |
| Judul | Struk servis |
| Keterangan | Pratinjau struk sebelum dicetak. |
| Lebar | 58 mm, 80 mm, A4 |
| Status | Menyiapkan printer... |
| Target | Printer tujuan, Belum ada printer utama, Belum diatur |
| Tombol | Pilih printer, Coba lagi, Pilih printer lain, Buka pengaturan printer, Cetak browser, Cetak |
| Pemilih printer | Pilih printer. Printer utama tetap tersimpan. Pilihan ini hanya untuk struk saat ini. |
| Target siap | Printer tujuan: <nama>. Tekan Cetak untuk mengirim struk. |
| Gagal sebelumnya | Cetak sebelumnya gagal dan sebagian struk mungkin sudah tercetak. Cetak ulang struk yang sama? Tidak ada transaksi baru yang dibuat. |
| Tidak ada struk | Tidak ada struk untuk dicetak. |
| Lebar salah | Pilih lebar 58 mm atau 80 mm untuk printer utama. Cetak A4 hanya bisa lewat browser di komputer. |
| Info lebar | Struk memakai lebar kertas printer utama, 58 atau 80 mm. |
| Belum ada printer | Belum ada printer utama. Transaksi tetap tersimpan; pilih printer untuk mencetak struk ini. Belum ada printer utama. Pilih printer di Pengaturan. |
| Tidak didukung | Printer <nama> tidak didukung di perangkat ini. Pilih printer lain. |
| Proses | Mengirim struk ke <nama>. |
| Dialog Android | Dialog Android dibuka. Pekerjaan #<id> <status>. |
| Dialog browser | Dialog browser dibuka. Pilih printer lalu konfirmasi. |
| Sukses | Perintah cetak dikirim ke <nama>. Cetak untuk <nama> selesai. |
| Peringatan cetak ulang | Transaksi sudah tersimpan; mencetak ulang tidak membuat transaksi baru. Periksa kertas sebelum mencoba lagi karena sebagian struk mungkin sudah terkirim. |
| Gagal | Cetak gagal: <pesan singkat>. |
| Popup diblokir | Popup diblokir browser. Izinkan popup untuk mencetak. |
| Gagal browser | Cetak browser gagal. |
| Status pekerjaan | Selesai dilaporkan layanan cetak, Sedang dikirim ke layanan cetak, Menunggu antrean layanan cetak, Tertahan periksa dialog Android, Dibatalkan dari dialog Android, Gagal menurut layanan cetak, Belum ada pekerjaan, Layanan cetak tidak tersedia, Status belum tersedia |
| Tes cetak | Dialog Android dibuka untuk tes cetak. Status: <status>. Dialog cetak browser dibuka. Tes cetak dikirim ke <nama>. |
| Gagal tes | Pekerjaan cetak Android gagal. Periksa printer. Pekerjaan cetak dibatalkan dari dialog Android. |
| Selesai tes | Layanan cetak melaporkan pekerjaan selesai. |

## 14. Daftar nota (popup)

| Lokasi | Teks |
| --- | --- |
| Judul | Daftar nota |
| Kolom | Waktu, No. nota, Pelanggan, Total, Metode |
| Kosong | Tidak ada nota pada kategori ini. |
| Tombol | Tutup |

## 15. Teks native Android

| Kunci | Teks |
| --- | --- |
| app_name | BengkelPOS Radiator |
| pin_create_title | Buat PIN |
| pin_create_subtitle | Masukkan 6 angka |
| pin_confirm_title | Konfirmasi PIN |
| pin_confirm_subtitle | Masukkan 6 angka yang sama |
| pin_unlock_title | Masukkan PIN |
| pin_unlock_subtitle | 6 angka untuk membuka aplikasi |
| pin_mismatch | PIN tidak sama |
| pin_wrong | PIN salah |
| pin_wrong_remaining | PIN salah, sisa percobaan sebelum dikunci: N |
| pin_locked_countdown | Terkunci. Coba lagi dalam <waktu> |
| pin_storage_error | Penyimpanan aman PIN bermasalah. Coba lagi. |
| forgot_pin | Lupa PIN? |
| forgot_warning | PIN akan dihapus dan Anda dapat membuat PIN baru. Data pelanggan, transaksi, stok, dan backup TIDAK dihapus. Siapa pun yang memegang perangkat ini dapat membuka aplikasi setelah reset PIN. |
| reset_confirm_title | Konfirmasi reset |
| reset_confirm_message | Ketik RESET untuk melanjutkan. |
| reset_action | Reset PIN |
| reset_done | PIN baru tersimpan. Data pelanggan, transaksi, dan backup tetap aman. |
| reset_done_title | PIN baru dibuat |
| cancel / continue / ok | Batal / Lanjut / OK |
| pin_storage_title | Penyimpanan PIN tidak dapat dibuka |
| pin_storage_message | Kunci keamanan perangkat tidak dapat dipakai untuk membaca PIN. Tutup lalu buka kembali aplikasi. Jika masih gagal, hubungi teknisi; jangan menghapus data aplikasi. |
| delete_digit | Hapus angka |
| offline_hint | Aplikasi belum merespons. Coba lagi. |
| preparing_hint | Menyiapkan aplikasi. Mohon tunggu... |
| backend_error_hint | Aplikasi gagal dijalankan. Tutup aplikasi lain yang sedang berjalan, lalu tekan Coba lagi. |
| retry | Coba lagi |
| external_link_blocked | Tautan eksternal diblokir di dalam aplikasi. |
| download_blocked | Unduhan dari alamat luar diblokir. |
| download_failed | Unduhan gagal dimulai. Coba lagi. |

Catatan: teks PIN native memakai 6 angka dan tidak diubah karena termasuk alur
autentikasi yang harus dipertahankan. Gerbang PIN web memakai 4 sampai 12 angka.

## 16. Pesan kesalahan HTTP yang sudah disederhanakan

`frontend/js/api-client.js` sekarang mengubah kesalahan menjadi kalimat berikut:

| Kondisi | Teks |
| --- | --- |
| Tidak dapat terhubung | Tidak dapat menghubungi aplikasi. Pastikan aplikasi masih berjalan. |
| 401 | Sesi berakhir. Masukkan PIN lagi. |
| 403 | Akses ditolak. |
| 429 | Terlalu banyak percobaan. Tunggu sebentar. |
| 503 | Aplikasi belum siap. Tutup lalu buka lagi. |
| 5xx lain | Aplikasi sedang bermasalah. Coba lagi. |
| Validasi bentuk isian | Isian belum sesuai. Periksa kembali data yang dimasukkan. |
| Kesalahan lain | Permintaan gagal. Coba lagi. |

Detail kesalahan bisnis dari server (misalnya stok tidak cukup atau tanggal laporan
tidak valid) tetap ditampilkan karena membantu pengguna memperbaiki isian. Detail
yang memuat istilah internal, jalur berkas, nama basis data, alamat server, atau kode
HTTP diganti dengan kalimat umum di atas.

## 17. Informasi yang sengaja tidak lagi ditampilkan

| Informasi lama | Pengganti |
| --- | --- |
| Perintah `python reset_pin.py` di layar lupa PIN | Hubungi teknisi bengkel. Data transaksi tidak ikut terhapus. |
| Nomor port server 8000-8010 | Aplikasi gagal dijalankan. Tutup aplikasi lain, lalu tekan Coba lagi. |
| Istilah "server lokal" dan "backend" | Aplikasi |
| Kode HTTP dan detail kesalahan mentah | Kalimat umum yang dapat ditindaklanjuti |
| Istilah "database", "SQLite", dan "file database" | Data, file backup, atau salinan pengaman |
| Nama jenis koneksi internal (BLUETOOTH, NETWORK, USB, SYSTEM, WEB) | Bluetooth, Wi-Fi atau LAN, USB, Cetak Android, Cetak browser |
| Istilah "adapter", "ESC/POS", "payload", "endpoint", "pairing" | Istilah sehari-hari atau dihilangkan |
| Status internal "VOID" | Dibatalkan |
| Label "MAC" dan "ID" perangkat pada kartu printer | Alamat Bluetooth atau USB |
| Detail token, chat ID, PIN, hash, salt, dan session secret | Tidak pernah ditampilkan. Kolom token selalu kosong setelah disimpan. |
| Daftar tabel dan isi basis data | Ringkasan isi backup: pelanggan, unit, riwayat servis, transaksi keuangan, stok, pengaturan |

## 18. Perubahan fungsional terkait teks

1. Tombol "Backup database" di halaman Laporan dihapus. Backup hanya ada di
   Pengaturan, tepatnya bagian Backup dan pemulihan serta Backup otomatis Telegram.
2. Penjelasan backup Telegram menyebut cakupan lengkap: pelanggan, unit, riwayat
   servis, transaksi keuangan, stok, dan pengaturan bengkel. PIN dan token tidak ikut
   dijelaskan karena memang tidak disertakan dalam file backup.
3. Semua tombol, id, dan alur data lama tetap dipertahankan. Perubahan hanya pada
   teks, penamaan yang tampil, dan gaya visual.
4. Layar utama aplikasi Android kini dapat di-screenshot dan direkam. Proteksi
   `FLAG_SECURE` hanya tersisa di layar PIN agar PIN tidak ikut terambil; pratinjau
   recents tetap ditutup `privacyCover` saat aplikasi masuk latar belakang.
5. Seluruh tampilan memakai satu sistem desain: latar kertas hangat, sidebar
   ink gelap, aksen copper, angka nominal monospace, dan navigasi 4x2 di layar
   kecil. Id elemen, tombol, dan alur data tidak berubah.
