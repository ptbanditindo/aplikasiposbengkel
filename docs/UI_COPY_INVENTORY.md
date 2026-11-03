# Inventaris Teks UI dan Popup - BengkelPOS Radiator

Dokumen ini mencatat seluruh teks yang tampil di antarmuka: judul halaman, keterangan, tombol, kolom isian, placeholder, keadaan kosong, popup, konfirmasi, dan notifikasi.

## Standar penulisan yang dipakai

- Bahasa Indonesia sehari-hari untuk pemilik bengkel UMKM; istilah teknis dijelaskan di tempat.
- Setiap kolom penting diberi contoh isian (placeholder "Contoh: ...") atau keterangan singkat di bawahnya.
- Tombol memakai kata kerja yang sama dengan hasilnya (Simpan, Tambah, Arsipkan, Muat ulang).
- Pesan kosong menyebutkan langkah berikutnya, bukan hanya "Belum ada data".
- Peringatan menyebut akibatnya (mis. isian hilang, riwayat tetap tersimpan).


## Layar akses (PIN, karyawan, perangkat)

- BengkelPOS Radiator
- Data bengkel tersimpan di perangkat ini
- Kasir, stok, dan piutang dalam satu buku kerja.
- Akses pemilik
- Buat PIN pemilik
- PIN 4 sampai 12 angka. Hanya pemilik yang perlu tahu.
- PIN baru
- Ulangi PIN
- Simpan PIN
- Masuk
- Masukkan PIN pemilik untuk membuka bengkel.
- PIN
- Buka aplikasi
- Masuk sebagai karyawan
- Username
- Password
- PIN 6 angka
- Masuk karyawan
- Masuk dari perangkat karyawan
- Kembali ke PIN pemilik
- ID owner
- Token perangkat
- Dari pemilik; cukup diisi sekali
- Perangkat harus didaftarkan pemilik terlebih dahulu. Login pertama memerlukan koneksi ke hub.
- Masuk perangkat
- Lupa PIN? Hubungi teknisi bengkel. Data transaksi tidak ikut terhapus.
- Error: PIN minimal 4 angka.
- Error: PIN yang diulang tidak sama.
- Error: Isi username dan password.
- Error: PIN karyawan harus 6 angka. PIN ini dibuat saat login pertama.
- Error: Isi ID owner, username, dan password.
- Error: Token perangkat belum diisi. Minta token dari pemilik.
- Error: Sesi perangkat berakhir. Masuk kembali dengan akun karyawan.
- Error: Sesi berakhir. Masukkan PIN lagi.
- Prompt: Password awal wajib diganti. Masukkan password baru (minimal 8 karakter):

## Halaman: dashboard

- Ringkasan hari ini
- Servis dan pembayaran yang tercatat hari ini.
- Pengingat gajian
- Bayar
- Laporan keuangan bengkel hari ini
- Unit diservis
- 0
- Sparepart keluar hari ini
- 0
- Servis + pembelian part
- Tunai masuk
- Rp 0
- Transfer masuk
- Rp 0
- Total hutang pelanggan
- Rp 0
- 0 nota · 0 pelanggan
- Laporan stok habis / menipis
- Stok menipis
- 0
- Perlu dibeli
- Stok habis
- 0
- Tidak tersedia
- Laporan keuangan karyawan
- Piutang karyawan
- Rp 0
- 0 hutang berjalan
- Gaji & komisi harus dibayar
- Rp 0
- Belum ada tagihan gaji

## Halaman: pos

- Transaksi kasir
- Catat servis atau penjualan sparepart. Ikuti langkah 1–4, periksa nota, lalu simpan.
- Servis
- Beli sparepart
- Kosongkan form
- 1
- Pilih pelanggan
- Ketik nama atau nomor HP pelanggan. Belum terdaftar? Klik + Pelanggan baru.
- + Pelanggan baru
- 2
- Pilih unit servis
- Pilih unit yang diservis. Untuk radiator tanpa mobil, pilih Bawa radiator saja.
- Daftarkan unit baru
- Mobil lengkap
- Bawa radiator saja
- Nomor polisi
- *
- Jenis atau tipe mobil
- Tahun
- Tipe radiator
- Kondisi awal
- Label radiator otomatis
- RAD-YYYYMMDD-XXX
- Dibuat otomatis saat unit disimpan.
- Keterangan tambahan
- Simpan unit
- 3
- Keluhan awal
- Klik keluhan yang sering muncul, atau tulis dengan bahasa pelanggan.
- Keluhan pelanggan
- *
- Catatan pengerjaan (opsional)
- Simpan keluhan
- 4
- Rincian pengerjaan
- Tambahkan jasa dan sparepart. Harga di sini hanya untuk nota ini; tarif master tidak berubah.
- Jasa
- Harga hanya untuk nota ini
- + Tambah jasa
- Jasa
- Qty
- Harga deal
- Servis berkala
- Subtotal
- Belum ada jasa. Pilih dari daftar tarif atau isi nama jasa, lalu klik + Tambah jasa.
- Sparepart
- Stok gudang berkurang otomatis.
- + Tambah sparepart
- Sparepart
- Qty
- Harga deal
- Modal
- Servis berkala
- Subtotal
- Belum ada sparepart. Pilih barang, isi jumlah, lalu klik + Tambah sparepart.
- Ringkasan nota
- Belum ada pelanggan dipilih.
- Subtotal jasa
- Rp 0
- Subtotal sparepart
- Rp 0
- Sparepart keluar hari ini
- 0
- Total nota
- Rp 0
- Diskon (Rp)
- Potongan dari total nota. Isi 0 bila tidak ada.
- Metode pembayaran
- Tunai
- Hitung kembalian
- Transfer
- Uang pas
- Jenis pembayaran
- Lunas
- Kredit
- Pilih Kredit bila belum lunas. Sisa tagihan masuk piutang pelanggan.
- Rencana pembayaran (Rp)
- Nominal yang dijanjikan pelanggan. Boleh dikosongkan.
- Tanggal rencana pembayaran (opsional)
- Dipakai sebagai pengingat piutang.
- Ada penambahan uang (uang muka)
- Uang muka diterima (Rp)
- Sisanya menjadi tagihan kredit.
- Rekening tujuan transfer
- -
- -
- Uang diterima (Rp)
- Kembalian
- Rp 0
- Sisa tagihan
- Rp 0
- Karyawan
- Kasir
- Tanpa kasir
- Mekanik yang mengerjakan (boleh kosong)
- Unit ditinggal
- Aktifkan bila kendaraan tetap di bengkel. Dipakai untuk follow-up saat kendaraan selesai.
- Garansi servis
- Durasi garansi
- 1 bulan (30 hari)
- 2 bulan (60 hari)
- 3 bulan (90 hari)
- 6 bulan (180 hari)
- 12 bulan (360 hari)
- Atur sendiri
- Jumlah bulan (1 sampai 120)
- Catatan garansi
- Garansi penukaran
- Berlaku berapa hari
- Garansi barang
- Durasi
- Satuan
- Hari
- Bulan
- Periksa nota
- Simpan & cetak struk
- Simpan tanpa cetak

## Halaman: history

- Riwayat servis
- Cari nota, nopol, label radiator, atau nama pelanggan. Klik nomor nota untuk detail.
- Muat ulang
- 0 nota
- Waktu
- No. nota
- Pelanggan
- Unit
- Total
- Metode
- Garansi
- Retur/Ganti
- Aksi
- Belum ada transaksi. Buat nota pertama dari menu Kasir.

## Halaman: stock

- Stok sparepart
- Barang di gudang. Harga jual boleh diubah saat transaksi; stok berkurang otomatis.
- Semua
- Menipis
- Habis
- Sparepart gudang
- -
- + Sparepart
- Kode
- Nama
- Supplier
- Modal
- Jual
- Stok
- Min.
- Servis berkala
- Belum ada sparepart. Klik + Sparepart untuk menambah barang.

## Halaman: jasa

- Tarif jasa
- Daftar tarif jasa. Nilai ini menjadi harga awal saat kasir menambah jasa.
- Daftar tarif jasa
- -
- + Tarif jasa
- Nama jasa
- Tarif
- Servis berkala
- Belum ada tarif jasa. Klik + Tarif jasa untuk menambah.

## Halaman: report

- Laporan kas
- Uang masuk, piutang, dan estimasi laba. Pilih periode lalu klik Tampilkan.
- Laporan kas
- Transaksi pada periode
- Stok pernah terjual
- Periode laporan
- Hari ini
- 7 hari terakhir
- 30 hari terakhir
- 1 tahun terakhir
- Seluruhnya
- Tampilkan
- Total omset
- Rp 0
- Tunai
- Rp 0
- Transfer
- Rp 0
- Estimasi laba bersih sparepart
- Rp 0
- Estimasi laba bersih jasa
- Rp 0
- Laba bersih setelah dipotong gaji dan komisi
- Rp 0
- Rekap harian periode
- Hanya hari yang memiliki transaksi.
- Tanggal
- Transaksi
- Omset
- Tunai
- Transfer
- Modal sparepart
- Laba bersih sparepart
- Laba bersih jasa
- Transaksi pada periode
- -
- Waktu
- No. nota
- Pelanggan
- Unit
- Total
- Metode
- Tidak ada transaksi pada periode ini.
- Stok pernah terjual
- Harga mengikuti harga deal. Barang yang sama diurutkan menurut waktu.
- Barang
- Qty
- Harga akhir
- Subtotal
- Waktu
- No. nota
- Tidak ada penjualan sparepart pada periode ini.

## Halaman: settings

- Pengaturan bengkel
- Isi identitas bengkel, pengingat, struk, dan printer. Perubahan langsung dipakai.
- Tampilan
- Pilih warna antarmuka. Pilihan tersimpan di perangkat ini.
- Warna aplikasi
- Terang
- Gelap
- Menu navigasi
- Pilih menu yang ditampilkan. Ringkasan, Kasir, dan Pengaturan selalu tampil.
- Atur urutan menu
- Menu yang dimatikan tidak hilang — bisa ditampilkan lagi kapan saja. Pilihan tersimpan di perangkat ini.
- Identitas dan rekening
- Perubahan langsung tampil di aplikasi dan struk.
- Nama bengkel
- *
- Tagline
- Alamat
- Telepon
- WhatsApp
- Bank
- Nomor rekening
- Atas nama
- Batalkan perubahan
- Simpan pengaturan
- Pengingat dan follow-up
- Batas hari untuk piutang, garansi, prospek, dan pesan WhatsApp.
- Batas minimum stok bawaan
- Dipakai untuk barang yang batas minimumnya dikosongkan. 0 berarti peringatan stok menipis nonaktif.
- Jumlah ditanyakan ke supplier
- Pesan WhatsApp ke supplier menanyakan ketersediaan sebanyak ini untuk setiap barang.
- Prospek tahap 1 (hari)
- Pengingat kabar unit setelah servis, tahap 1.
- Prospek tahap 2 (hari)
- Pengingat tahap 2 bila tahap 1 belum dijawab.
- Prospek tahap 3 (hari)
- Pengingat tahap 3, terakhir.
- Jeda follow-up WhatsApp (hari)
- Setelah satu pesan terkirim, item yang sama tidak bisa diingatkan lagi selama ini.
- Ingatkan garansi H- (hari)
- Pengingat garansi muncul sekian hari sebelum masa garansi habis.
- Tampilkan servis berkala H- (hari)
- Pengingat servis berkala muncul sekian hari sebelum jadwal servis berikutnya.
- Jeda pengingat piutang (hari)
- Jarak minimal antar pengingat piutang ke pelanggan yang sama.
- Maksimal pengingat piutang
- Setelah batas ini, pengingat WA berhenti dan pelanggan perlu ditelepon.
- Arsip garansi setelah (hari)
- Garansi diarsipkan sekian hari setelah masa garansinya berakhir.
- Belum bisa dihubungi lagi (hari)
- Nilai tombol Tunda saat pelanggan belum bisa dihubungi.
- Belum bisa, pilihan panjang (hari)
- Pilihan tunda yang lebih panjang pada tombol Tunda.
- Batas tidak merespons (kali)
- Setelah sekian pesan tanpa balasan, item prospek/servis/garansi diarsipkan otomatis.
- Batas pesan per hari
- Maksimal pesan WhatsApp ke satu pelanggan dalam sehari.
- Batas pesan per bulan
- Maksimal pesan prospek/servis ke satu pelanggan dalam 30 hari.
- Jeda prospek dan servis (hari)
- Jarak minimal antar pesan prospek/servis ke pelanggan yang sama.
- Jam mulai follow up
- Jam selesai follow up
- Di luar jam ini tombol Ingatkan dan pengingat piutang tidak bisa dipakai.
- Simpan pengaturan follow-up
- Struk
- Pilih bagian yang tampil di struk cetak dan WhatsApp.
- Nama bengkel selalu ditampilkan dan tidak dapat dimatikan.
- Simpan pengaturan struk
- Printer
- Belum ada printer tersimpan.
- + Tambah printer
- Belum ada printer. Tambahkan printer Bluetooth, Wi-Fi atau LAN, USB OTG,
- cetak Android, atau cetak browser.
- Menghapus printer hanya menghapus konfigurasinya. Data transaksi, pelanggan,
- dan stok tidak ikut terhapus.
- Backup, pemulihan dan berbagi database
- Satu file berisi data pelanggan, unit, riwayat servis, transaksi keuangan, stok, dan pengaturan bengkel.
- Folder backup
- Belum dipilih
- Pilih folder
- Gunakan file backup dari perangkat lain saat memasang aplikasi baru. Data saat ini
- akan diganti, tetapi salinan pengaman dibuat otomatis sebelum pemulihan.
- Pulihkan data
- Mengganti data sekarang dengan file backup.
- Backup manual
- Menyimpan ke folder terpilih.
- Bagikan database
- Data terbaru saat ini.
- Backup otomatis Telegram & lokal
- Belum diatur.
- Token Telegram perlu diisi ulang agar backup otomatis berjalan.
- Belum ada backup terjadwal.
- Backup terakhir lebih dari 2 hari. Periksa jadwal dan ruang penyimpanan.
- Kirim backup otomatis setiap hari
- Jam kirim (waktu lokal)
- Chat ID penerima
- Contoh: 123456789 atau @namachannel
- Format backup otomatis
- Database (.db) - bisa dipulihkan
- Excel (.xlsx) - data per tabel
- CSV (.zip) - teks spreadsheet per tabel
- Database (.db) dapat dipulihkan lewat Pulihkan data. Excel dan CSV hanya untuk dibaca atau diolah; file pemulihan tetap harus .db.
- Bot token Telegram
- Kosongkan jika token sudah ada
- Setiap kiriman berisi satu berkas sesuai format yang dipilih: pelanggan, unit,
- riwayat servis, transaksi keuangan, stok, dan pengaturan bengkel. Database (.db)
- dapat dipulihkan; Excel dan CSV hanya untuk dibaca. Butuh koneksi internet. Jika
- jadwal terlewat, backup dikirim begitu internet tersedia.
- Pilih folder tempat penyimpanan
- Belum dipilih
- Pilih folder
- Simpan pengaturan
- Kirim backup sekarang
- Langsung kirim ke Telegram dan folder pilihan.
- Keamanan aplikasi
- PIN diminta setiap aplikasi dibuka dan setelah aplikasi lama di latar belakang.
- Kunci otomatis setelah di latar belakang
- 1 menit
- 2 menit
- 5 menit
- 10 menit
- 30 menit
- Kunci sekarang

## Halaman: premium

- Premium dan pemilik
- Lisensi, akun karyawan, perangkat, sinkronisasi terenkripsi, dan arsip semua toko. Metadata disimpan di database utama; data toko tetap di database toko masing-masing.
- Muat ulang
- Paket gratis
- Akun karyawan, perangkat, sinkronisasi terenkripsi, dan arsip semua toko hanya tersedia di paket premium. Aktifkan lisensi di bawah untuk membuka fitur ini.
- Terkunci
- Lisensi dan ID owner
- Satu paket premium untuk semua fitur. Aktivasi di web hanya untuk pengujian; pembelian resmi memakai Play Billing di APK.
- Gratis
- Premium
- ID owner
- Salin ID
- Tampilkan QR
- Sembunyikan QR
- QR hanya berisi ID owner untuk login perangkat karyawan. Tidak memuat password atau data bengkel.
- QR tidak tersedia.
- QR gagal dibuat.
- Status lisensi
- Berlaku sampai
- Sisa hari
- Batas perangkat owner
- Kunci publik owner
- Jam perangkat mundur dari verifikasi terakhir. Lisensi tetap aktif sampai batas waktu, tetapi periksa jam perangkat.
- Masa aktif (hari)
- Sumber aktivasi
- Manual (uji)
- Play Billing
- Voucher
- Aktifkan premium
- Perpanjang
- Lihat token lisensi
- Ringkasan aplikasi owner
- Pemulihan dan penghapusan metadata akun
- Kode pemulihan
- Tempel kode pemulihan
- Buka kunci privat owner
- Penghapusan hanya menghapus metadata premium di database utama. Data bengkel, stok, nota, dan backup tetap utuh.
- Ketik ID owner untuk konfirmasi
- Hapus metadata premium
- Akun karyawan
- Peran dasar ditambah izin tambahan. Tindakan pemilik tetap ditolak di lapisan data.
- + Tambah akun
- Tutup form
- Username
- Nama tampilan
- Peran dasar
- Kasir
- Mekanik
- Kasir & Mekanik
- Password awal
- Kosongkan untuk dibuat otomatis
- Kosongkan bila tidak diubah
- Buat password acak
- Toko yang ditugaskan
- Izin tambahan
- Katalog izin belum dimuat.
- Simpan akun
- Batal
- Username
- Nama
- Peran
- Toko
- Status
- Aktif
- Nonaktif
- Wajib ganti password
- Ubah
- Password
- Reset PIN
- Audit
- Snapshot
- Nonaktifkan
- Belum ada akun karyawan. Tambahkan akun untuk membuka akses terbatas.
- Teks akun
- Salin semua
- Perangkat dan hub
- Server hanya menyimpan kunci publik dan hash token perangkat. Kunci privat tidak pernah disimpan di server.
- Siapkan web hub
- + Daftarkan perangkat
- Nama perangkat
- HP kasir
- Jenis
- Owner
- Karyawan
- Akun karyawan
- Tidak terikat
- Buat kunci di server
- Ya, tampilkan sekali
- Tidak, kirim kunci publik
- Toko yang ditugaskan
- Daftarkan
- Batal
- Nama
- Jenis
- Toko
- Status
- Online
- Offline
- Dicabut
- Hub:
- Cabut
- Lepas slot
- Belum ada perangkat terdaftar.
- Hub toko
- Hub wajib daring untuk menulis uang di toko. Perangkat lain hanya dapat mengantrekan perubahan.
- Toko
- Perangkat hub
- Paksa ganti hub
- Tidak
- Ya
- Simpan hub
- Buat kunci toko
- Ganti kunci toko
- Sinkronisasi terenkripsi
- Antrean keluar, konflik, dan snapshot dienkripsi di perangkat. Server hanya melihat ciphertext dan tanda tangan.
- Muat status
- Bersihkan kedaluwarsa
- Tertunda
- Konflik
- Sinkron terakhir
- Status
- Lengkap
- Menunggu
- Antrean keluar
- Entitas
- Aksi
- Status
- Dibuat
- Antrean kosong.
- Konflik
- Entitas
- Alasan
- Dibuat
- Pertahankan lokal
- Pakai server
- Tidak ada konflik terbuka.
- Snapshot terenkripsi
- Perangkat
- Kunci toko (base64)
- Dibuat lewat tombol Buat kunci toko
- Kunci privat perangkat
- Hanya tersedia di sesi ini
- Buat snapshot
- Ambil snapshot
- Terapkan snapshot
- Arsip semua toko
- Satu ZIP berisi database seluruh toko, manifest, dan checksum. Pemulihan memvalidasi semua berkas sebelum menimpa data.
- Buat arsip semua toko
- Berkas
- Ukuran
- Dibuat
- Unduh
- Belum ada arsip semua toko.
- Pulihkan arsip ZIP
- Pulihkan semua toko
- Restore arsip menimpa database toko yang ada. Buat backup manual dulu bila ragu.
- Teks siap kirim: PusatkuPOS — akun karyawan / ID owner / Username / Password / Peran / Toko / Ganti password saat login pertama.
- Teks rahasia perangkat: Perangkat / ID / Token perangkat (sekali) / Kunci tanda tangan (sekali) / Kunci enkripsi (sekali).
- Teks kunci toko: Kunci toko (hanya ditampilkan sekali) / Perangkat terbungkus.
- Teks ganti kunci: Kunci baru toko (hanya ditampilkan sekali) / Perangkat dibungkus ulang / Amplop dihapus / Snapshot dihapus / Outbox dikirim ulang.
- Teks lisensi: Lisensi / ID owner / Berlaku sampai / Batas perangkat / Kode pemulihan (hanya sekali) / Token lisensi.
- Teks pemulihan: Kunci privat owner (jangan bagikan):
- Pesan gating paket gratis: Satu toko, kasir, stok, laporan, dan backup manual. / 20 kredit WhatsApp untuk Follow up. / Karyawan, Supplier, dan multi-toko terkunci.
- Pesan gating paket premium: Toko tanpa batas dengan data terpisah. / Karyawan, Supplier, dan Follow up tanpa kuota. / Backup otomatis lokal dan Telegram.
- Banner kuota: Kuota Follow up / 20 dari 20 kredit WhatsApp tersisa. Satu kredit terpakai saat tautan WhatsApp dibuka.
- Banner kuota habis: Kuota Follow up habis / 20 kredit WhatsApp sudah terpakai. Fitur Follow up terkunci sampai berlangganan premium.
- Catatan gating: Paket gratis: daftar karyawan tetap bisa dibaca, tetapi tambah dan ubah data terkunci.

## Halaman: customers

- Pelanggan
- Data pelanggan dan unitnya. Cari dengan nama atau HP, atau tambahkan pelanggan baru.
- Muat ulang
- 0 pelanggan
- Total pelanggan
- 0
- Pelanggan terdaftar
- Total unit terdaftar
- 0
- Mobil dan radiator
- Unit mobil
- 0
- Unit dengan nomor polisi
- Radiator copotan
- 0
- Radiator berlabel
- Garansi aktif
- 0
- Nota masih bergaransi
- Daftar pelanggan
- Klik nama pelanggan untuk melihat unit dan riwayat servis.
- + Pelanggan baru
- Belum ada pelanggan terdaftar. Tambahkan pelanggan baru untuk mulai mencatat unit servis.

## Halaman: employees

- Karyawan
- Atur mekanik dan kasir: peran, komisi atau gaji, hutang, dan riwayat pembayaran.
- Fitur karyawan
- Muat ulang
- Daftar karyawan
- Hutang karyawan
- Riwayat pembayaran gaji
- Daftar karyawan
- -
- Lihat arsip
- + Karyawan
- Nama
- Peran
- Status
- Belum ada karyawan. Klik + Karyawan untuk menambah mekanik atau kasir.
- Hutang karyawan
- Catat uang muka atau kebutuhan karyawan. Sisa hutang otomatis dipotong dari gaji atau komisi saat gajian.
- Lihat semua
- + Catat hutang
- Nama
- Nominal hutang
- Status
- Belum ada hutang. Catat pinjaman karyawan dengan tombol + Catat hutang.
- Riwayat pembayaran gaji
- Menampilkan 2 pembayaran terbaru per karyawan.
- Lihat semua
- Tanggal
- Karyawan
- Periode
- Metode
- Nominal
- Potongan hutang
- Catatan
- Belum ada pembayaran gaji. Bayar dari Ringkasan atau tombol Bayar saat gajian.

## Halaman: suppliers

- Supplier
- Toko penyedia sparepart. Atur barang yang disuplai; arsipkan supplier yang tidak dipakai.
- Fitur supplier
- Muat ulang
- Daftar supplier
- -
- Lihat arsip
- + Supplier
- Nama
- WhatsApp
- Barang disuplai
- Belum ada supplier. Klik + Supplier untuk menambah toko pemasok.

## Halaman: followup

- Follow up
- Pelanggan yang perlu dihubungi hari ini: piutang, servis berkala, garansi, dan prospek.
- Fitur follow up
- Muat ulang
- Follow up Pelanggan
- Follow up Reseller
- Piutang
- Rp 0
- 0 nota
- Kendaraan selesai
- 0
- Siap dihubungi
- Prospek
- 0
- Kabar unit pasca servis
- Berkendala
- 0
- Masih terkendala
- Servis berkala
- 0
- Mendekati jadwal
- Garansi akan habis
- 0
- Perlu diingatkan
- Akan datang: Garansi
- 0
- Sudah dijadwalkan
- Akan datang: Servis berkala
- 0
- Sudah dijadwalkan
- Akan datang: Prospek
- 0
- Sudah dijadwalkan
- Stok menipis
- 0
- Perlu dibeli
- Stok habis
- 0
- Tidak tersedia
- Perlu dipasok
- 0
- Menipis dan habis

## Popup: customerModal

- Tambah pelanggan
- Format nomor HP dirapikan otomatis.
- ×
- Nama pelanggan
- *
- Nomor HP
- *
- Alamat
- Batal
- Simpan pelanggan

## Popup: printerModal

- Tambah printer
- Simpan perangkat sekali, lalu sambungkan saat dibutuhkan.
- ×
- Nama printer
- *
- Cara menghubungkan
- *
- Bluetooth
- Wi-Fi / LAN
- USB OTG
- Cetak Android
- Cetak browser
- Lebar kertas
- 58 mm
- 80 mm
- Mode cetak
- Encoding teks
- Dukungan perangkat
- -
- Alamat Bluetooth
- *
- IP printer
- *
- Port
- *
- Identitas perangkat USB
- *
- Cetak lewat dialog Android. Pilih printer dan jumlah salinan di sana;
- aplikasi tidak menganggap printer selalu terhubung.
- Cetak lewat dialog browser. Pilih printer biasa atau printer thermal
- yang sudah terpasang di komputer.
- Cari printer
- Mencari printer yang terdeteksi di perangkat ini.
- Jadikan printer utama
- Batal
- Simpan printer

## Popup: printerPickerModal

- Pilih printer
- Printer utama tetap tersimpan. Pilihan ini hanya untuk struk saat ini.
- ×
- Tutup

## Popup: receiptModal

- Struk servis
- Pratinjau struk sebelum dicetak.
- ×
- 58 mm
- 80 mm
- A4
- Menyiapkan printer...
- Printer tujuan
- Belum ada printer utama
- Belum diatur
- Pilih printer
- Coba lagi
- Pilih printer lain
- Buka pengaturan printer
- Buka WhatsApp
- Salin teks
- Cetak browser
- Cetak

## Popup: notaReviewModal

- Periksa nota
- Pastikan seluruh isi nota sudah benar sebelum disimpan.
- ×
- Edit
- Benar

## Popup: notaListModal

- Daftar nota
- -
- ×
- Waktu
- No. nota
- Pelanggan
- Total
- Metode
- Tidak ada nota pada kategori ini.
- Tutup

## Popup: recordModal

- Detail nota
- -
- ×
- Tutup
- Tukar barang

## Popup: exchangeModal

- Tukar sparepart
- Barang lama kembali ke stok, barang pengganti keluar.
- ×
- Barang yang ditukar
- Jumlah
- Barang pengganti
- Harga barang pengganti
- Alasan
- Nilai barang ditukar
- Rp 0
- Nilai barang pengganti
- Rp 0
- Selisih
- Rp 0
- Metode tambahan
- Tunai
- Transfer
- Batal
- Simpan tukar

## Popup: customerDetailModal

- Detail pelanggan
- -
- ×
- Tutup
- Buat servis

## Popup: customerStatModal

- Daftar pelanggan
- -
- ×
- Belum ada data.
- Tutup

## Popup: employeeModal

- Tambah karyawan
- Data karyawan operasional, bukan akun login. Komisi dan gaji dipakai untuk menghitung performa.
- ×
- Nama
- *
- Peran
- Mekanik
- Kasir
- Mekanik dan kasir
- Status
- Aktif
- Nonaktif
- Tanggal masuk
- Jenis imbalan
- Komisi
- Gaji bulanan
- Gaji dan komisi
- Gaji bulanan (Rp)
- Nomor WhatsApp
- Catatan
- Mode komisi
- Persentase
- Nominal per nota
- Jadwal gajian
- Per tanggal
- Per minggu
- Per 2 minggu
- Per 3 minggu
- Bulanan
- Komisi barang (%)
- Komisi jasa (%)
- Tanggal gajian (1-31)
- Hari pembayaran
- Senin
- Selasa
- Rabu
- Kamis
- Jumat
- Sabtu
- Minggu
- Bank
- Nomor rekening
- Atas nama rekening
- Batal
- Simpan karyawan

## Popup: payrollModal

- Gaji & komisi
- Perkiraan yang perlu dibayar pada siklus berjalan.
- ×
- Karyawan
- Total
- Belum ada karyawan dengan gaji atau komisi.
- Tutup

## Popup: payrollPayModal

- Pilih pembayaran
- Tentukan cara pembayaran gaji dan komisi.
- ×
- Gaji & komisi
- Rp 0
- Sisa hutang (termasuk bulan lalu)
- Rp 0
- Potong hutang
- Rp 0
- Bonus
- Rp 0
- Total yang harus dibayarkan
- Rp 0
- Cicil hutang (dipotong dari gaji)
- Full bayar hutang (dipotong dari gaji)
- Tambah bonus
- Bayar
- Batal

## Popup: salaryModal

- Catat pembayaran gaji
- Gaji yang dicatat di sini mengurangi laba bersih pada tanggal pembayaran.
- ×
- Karyawan
- -
- Periode
- -
- Total yang harus dibayarkan
- Rp 0
- Metode pembayaran
- Tunai
- Transfer
- Rekening karyawan
- -
- Bonus
- -
- Batal
- Bayar

## Popup: debtModal

- Catat hutang karyawan
- Hutang akan dipotong otomatis dari gaji atau komisi saat gajian.
- ×
- Karyawan
- *
- Tanggal
- *
- Nominal (Rp)
- *
- Keperluan
- Batal
- Simpan hutang

## Popup: debtDetailModal

- Detail hutang karyawan
- -
- ×
- Tutup

## Popup: debtHistoryModal

- Seluruh hutang karyawan
- Semua catatan hutang yang tercatat.
- ×
- Tanggal
- Karyawan
- Keperluan
- Nominal
- Sudah dipotong
- Sisa
- Status
- Belum ada hutang karyawan.
- Tutup

## Popup: salaryHistoryModal

- Seluruh riwayat pembayaran gaji
- Semua pembayaran gaji yang tercatat.
- ×
- Tanggal
- Karyawan
- Periode
- Metode
- Nominal
- Potongan hutang
- Catatan
- Belum ada pembayaran gaji.
- Tutup

## Popup: employeePerfModal

- Performa karyawan
- -
- ×
- Tutup

## Popup: employeeDetailModal

- Detail karyawan
- -
- ×
- Tutup

## Popup: employeeArchiveModal

- Arsip karyawan
- Karyawan yang sudah keluar. Data tetap tersimpan.
- ×
- Nama
- Peran
- Masuk
- WhatsApp
- Gaji
- Belum ada karyawan di arsip.
- Tutup

## Popup: employeePerfDetailModal

- Rincian performa
- Riwayat pengerjaan dan komisi per nota.
- ×
- Tanggal
- Nota
- Pelanggan
- Unit
- Nilai
- Komisi
- Komisi manual
- Belum ada pengerjaan.
- Tutup

## Popup: supplierPickModal

- Pilih supplier
- Barang ini memiliki beberapa supplier.
- ×
- Tutup

## Popup: supplierModal

- Tambah supplier
- Simpan nama dan barang yang disuplai.
- ×
- Nama supplier
- *
- Nomor WhatsApp
- Status
- Aktif
- Nonaktif
- Alamat
- Catatan
- Barang yang disuplai
- + Tambah barang
- Barang
- Stok
- Belum ada barang dipilih.
- Batal
- Simpan supplier

## Popup: supplierArchiveModal

- Arsip supplier
- Supplier yang sudah diarsipkan. Data tetap tersimpan.
- ×
- Nama
- WhatsApp
- Barang disuplai
- Belum ada supplier di arsip.
- Tutup

## Popup: supplierStatusModal

- Status penanyaan stok
- -
- ×
- Status
- Tanpa status
- Sudah dipesan
- Akan dikirim
- Tidak tersedia
- Tidak perlu ditanyakan (sembunyikan)
- Catatan
- Tutup
- Simpan status

## Popup: stockModal

- Tambah sparepart
- Isi nama, harga, dan stok. Harga jual hanya patokan awal; kasir boleh mengubahnya per nota.
- ×
- Kode
- Jumlah stok
- Nama sparepart
- *
- Harga modal
- Harga jual patokan
- Servis berkala
- Interval bulan untuk pengingat servis. 0 berarti nonaktif.
- Batas minimum stok
- Kosongkan untuk ikut pengaturan. Isi 0 untuk menonaktifkan peringatan item ini.
- Supplier barang ini
- Pilih supplier yang menyuplai barang ini. Dipakai saat stok menipis.
- Batal
- Simpan sparepart

## Popup: jasaModal

- Tambah tarif jasa
- Tarif ini menjadi harga awal saat kasir menambah jasa.
- ×
- Nama jasa
- *
- Tarif standar (Rp)
- Servis berkala
- Isi interval bulan (mis. 6 untuk ganti oli). 0 berarti nonaktif.
- Batal
- Simpan jasa

## Popup: waModal

- Pesan WhatsApp
- Periksa pesan sebelum dibuka di WhatsApp.
- ×
- Jumlah yang ditanyakan
- Nomor tujuan
- Isi pesan
- Pesan dibuka di WhatsApp. Pengiriman tetap dilakukan oleh kasir.
- Tutup
- Buka WhatsApp

## Popup: followupListModal

- Daftar follow-up
- Pilih item untuk melihat detail.
- ×
- Tidak ada item follow-up.
- Tutup

## Popup: followupModal

- Detail follow-up
- -
- ×
- Datang
- Tidak datang
- Reschedule
- Tutup

## Popup: followupStatusModal

- Status follow-up
- -
- ×
- Tutup
- Simpan status

## Popup: followupRescheduleModal

- Reschedule service
- -
- ×
- Tanggal service baru
- *
- Catatan
- Tutup
- Simpan jadwal

## Popup: receivablesModal

- Piutang pelanggan
- Nota yang belum lunas.
- ×
- Tutup

## Popup: rescheduleModal

- Ubah jatuh tempo
- Tentukan tanggal pembayaran berikutnya.
- ×
- Tanggal jatuh tempo
- *
- Pengingat yang sudah dikirim akan aktif lagi pada tanggal baru.
- Batal
- Simpan tanggal

## Popup: pengerjaanModal

- Kendaraan selesai
- Nota dengan unit ditinggal. Kabari pelanggan saat pengerjaan selesai.
- ×
- Tutup

## Popup: pengerjaanStatusModal

- Status pengerjaan
- -
- ×
- Status
- Sedang dikerjakan
- Menunggu sparepart
- Menunggu persetujuan
- Selesai, siap diambil
- Sudah diambil
- Janji ambil (opsional)
- Catatan
- Tutup
- Simpan status

## Pesan notifikasi (toast)

- harus berupa rupiah bulat tanpa desimal. Contoh: 150.000.warning
- #toastContainer
- Pencarian pelanggan gagal. Coba lagi.error
- Gagal memuat unit pelanggan. Coba pilih pelanggan lagi.error
- Unit dihapus dari daftar. Riwayat servis tetap tersimpan.success
- error
- Keluhan awal wajib diisi.warning
- Keluhan disimpan.success
- Pilih pelanggan terlebih dahulu.warning
- Nomor polisi wajib diisi untuk mobil.warning
- RADIATOR_ONLYUnit radiator tersimpan. Label dibuat saat transaksi pertama.Unit mobil tersimpan.success
- Pelanggan tersimpan.success
- Gagal memuat data pelanggan. Coba muat ulang.error
- Nama jasa wajib diisi.warning
- Nama sparepart wajib diisi.warning
- Mode beli sparepart hanya menerima sparepart.warning
- Tambahkan minimal satu sparepart.warning
- Isi durasi garansi penukaran minimal 1 hari.warning
- Isi durasi garansi barang minimal 1.warning
- Pilih unit servis terlebih dahulu.warning
- Simpan keluhan awal terlebih dahulu.warning
- Tambahkan minimal satu jasa atau sparepart.warning
- Angka uang harus rupiah bulat tanpa desimal.warning
- Isi uang muka lebih dari Rp 0 atau matikan opsi penambahan uang.warning
- warning
- Ringkasan nota belum siap. Coba lagi.warning
- Periksa nota dan tekan Benar sebelum menyimpan.warning
- Nota berhasil disimpan.success
- Tautan tidak dapat dibuka.error
- Tautan tidak dapat dibuka. Izinkan pop-up lalu coba lagi.warning
- Tidak ada teks untuk disalin.warning
- Teks disalin.success
- Gagal menyalin. Salin manual dari kotak teks.warning
- Isi jumlah yang ditanyakan dulu.warning
- Nomor WhatsApp pelanggan belum valid.warning
- Pesan kendaraan selesai belum tersedia.warning
- Pemberitahuan kendaraan selesai tercatat.success
- Pesan kendaraan selesai gagal dimuat.error
- WhatsApp tidak tersedia di perangkat ini. Gunakan Salin teks.error
- WhatsApp tidak dapat dibuka otomatis karena pop-up diblokir. Tekan "Buka WhatsApp" atau salin teks struk.warning
- WhatsApp nota dibuka. Tekan kirim di WhatsApp.success
- Layanan cetak melaporkan pekerjaan selesai.success
- Pekerjaan cetak Android gagal. Periksa printer.error
- Pekerjaan cetak dibatalkan dari dialog Android.info
- Tidak ada struk untuk dicetak.warning
- Struk memakai lebar kertas printer utama, 58 atau 80 mm.warning
- Belum ada printer utama. Pilih printer di Pengaturan.warning
- Perintah cetak dikirim ke .success
- Cetak gagal: error
- Popup diblokir browser. Izinkan popup untuk mencetak.error
- Cetak browser gagal.error
- Printer utama diganti ke . Printer sebelumnya tetap tersimpan.success
- Printer berhasil terhubung.success
- Koneksi printer diputus. Printer tetap tersimpan. warning
- Koneksi printer diputus. Printer tetap tersimpan.info
- Printer berhasil dihubungkan ulang.success
- Dialog Android dibuka untuk tes cetak. Status: QUEUED.info
- Dialog cetak browser dibuka.info
- Tes cetak dikirim ke printer.success
- Printer dihapus. Data transaksi tidak berubah.success
- Cetak untuk selesai.success
- Fitur printer tidak tersedia di perangkat ini.error
- Pencarian printer ini tidak tersedia di perangkat.warning
- Data printer dimasukkan. Periksa lalu simpan.info
- Nama printer wajib diisi.warning
- Alamat Bluetooth harus berbentuk AA:BB:CC:DD:EE:FF.warning
- Alamat IP printer wajib diisi.warning
- Port harus antara 1 dan 65535.warning
- Identitas perangkat USB wajib diisi.warning
- Perubahan printer disimpan.success
- Printer disimpan.success
- Gagal memuat daftar printer. Coba lagi.error
- Ringkasan hari ini gagal dimuat. Coba muat ulang.error
- Data gaji belum dimuat.warning
- Isi nominal bonus lebih dari 0.warning
- Isi keterangan bonus.warning
- Isi nominal cicilan hutang lebih dari 0.warning
- Cicilan melebihi sisa hutang karyawan.warning
- Cicilan melebihi gaji dan komisi.warning
- Tidak ada nominal yang perlu dibayar.warning
- Riwayat servis gagal dimuat. Coba muat ulang.error
- Detail nota gagal dimuat. Coba lagi.error
- Tidak ada sparepart yang bisa ditukar.warning
- Stok pengganti tidak tersedia.warning
- Lengkapi barang dan jumlah tukar.warning
- Isi alasan tukar minimal 3 karakter.warning
- Tukar barang tersimpan. Stok dan selisih sudah dicatat.success
- Nominal pembayaran harus lebih dari nol.warning
- Nominal melebihi sisa bayar nota.warning
- Kredit nonaktif. Isi pelunasan penuh atau aktifkan Kredit untuk membayar sebagian.warning
- Nota lunas.success
- Pembayaran kredit tercatat. Sisa masuk ke Piutang.success
- Pembayaran tercatat. Sisa .success
- Unit ditandai sudah diambil.success
- Pembayaran tercatat, tetapi unit gagal ditandai diambil: error
- Detail pelanggan gagal dimuat. Coba lagi.error
- Data pelanggan tidak ditemukan.warning
- Daftar follow-up gagal dimuat. Coba lagi.error
- Follow up gagal dimuat. Coba muat ulang.error
- Follow up belum bisa dilakukan sekarang. Periksa jeda atau status.warning
- Follow-up tercatat.success
- Ditandai datang.Ditandai tidak datang.success
- Isi tanggal service baru.warning
- Jadwal service diperbarui.success
- Pilih status terlebih dahulu.warning
- Isi tanggal service.warning
- Isi tanggal janji bayar.warning
- Status prospek sudah "".warning
- Status follow-up diperbarui.success
- Preferensi pesan disimpan.success
- Pengingat dibuka di WhatsApp. Tekan kirim untuk mengirim pesan.success
- Tanggal jatuh tempo wajib diisi.warning
- Jatuh tempo diperbarui. Pengingat aktif lagi pada tanggal baru.success
- Status pengerjaan diperbarui.success
- Data stok gagal dimuat. Coba lagi.error
- Sparepart keluar hari ini gagal dimuat. Coba lagi.error
- Piutang karyawan gagal dimuat. Coba lagi.error
- Unit ditandai masih di bengkel.success
- Klaim garansi tercatat.success
- Data stok gagal dimuat. Coba muat ulang.error
- Data sparepart tersimpan.success
- Sparepart dihapus.success
- Tarif jasa tersimpan.success
- Tarif jasa dihapus.success
- Laporan gagal dimuat. Coba lagi.error
- Data karyawan gagal dimuat. Coba lagi.error
- Data karyawan tersimpan.success
- Karyawan dipindahkan ke arsip.success
- Arsip karyawan gagal dimuat. Coba lagi.error
- Karyawan diaktifkan kembali.success
- Karyawan dihapus. Riwayat gaji dan hutang tetap tersimpan.success
- Data pembayaran gaji gagal dimuat. Coba lagi.error
- Data hutang karyawan gagal dimuat. Coba lagi.error
- Tambahkan karyawan lebih dulu.warning
- Hutang karyawan tersimpan.success
- Hutang karyawan dihapus.success
- Karyawan pembayaran tidak ditemukan.warning
- Pembayaran gaji tersimpan.success
- Nota gaji gagal dimuat. Pembayaran tetap tersimpan.warning
- Nota gaji dibuka di WhatsApp karyawan.success
- Nota gaji tidak tersedia untuk dibuka.warning
- Nomor WhatsApp karyawan belum diisi.warning
- Pembayaran gaji dihapus.success
- Komisi manual disimpan.success
- Data supplier gagal dimuat. Coba lagi.error
- Data supplier tersimpan.success
- Supplier dihapus.success
- Supplier dipindahkan ke arsip.success
- Arsip supplier gagal dimuat. Coba lagi.error
- Supplier diaktifkan kembali.success
- Penanyaan stok tercatat.success
- Nomor WhatsApp supplier belum valid.warning
- Supplier untuk barang ini belum memiliki nomor WhatsApp valid.warning
- Belum ada supplier untuk barang ini.warning
- Status penanyaan stok disimpan.success
- Fitur diaktifkan. dinonaktifkan.success
- Pengaturan struk disimpan.success
- harus antara dan hari.warning
- Isi jam mulai dan jam selesai follow up.warning
- Jam mulai dan jam selesai tidak boleh sama.warning
- Pengaturan follow-up disimpan.success
- Nama bengkel minimal 2 karakter.warning
- Pengaturan bengkel tersimpan.success
- Pengaturan gagal disimpan. Coba lagi.error
- Pemilihan folder hanya tersedia di aplikasi Android.warning
- Folder backup: .success
- Folder backup gagal dipilih. Coba lagi.error
- Pengaturan Telegram tersimpan.success
- Pengaturan Telegram gagal disimpan. Coba lagi.error
- Backup terkirim ke Telegram dan ().success
- Backup tersimpan di . Telegram belum dikirim: token dan chat ID belum lengkap.warning
- Backup gagal disimpan. Coba lagi.error
- Backup gagal dibuat. Periksa ruang penyimpanan lalu coba lagi.error
- Data berhasil dipulihkan. Menyiapkan ulang aplikasi...success
- Data sudah dipulihkan, tetapi aplikasi gagal dimuat ulang. Tutup lalu buka aplikasi.error
- Data berhasil dipulihkan. Memuat ulang aplikasi...success
- Data gagal dipulihkan. Periksa file backup lalu coba lagi.error
- Backup tersimpan: file backupsuccess
- Backup gagal dibagikan. Coba lagi.error
- Aplikasi gagal memuat data awal. Tutup lalu buka lagi.error
- Status premium gagal dimuat. Coba lagi.error
- ID owner disalin.success
- Teks akun disalin.success
- Akun diperbarui.success
- Akun dibuat.success
- Pilih minimal satu toko untuk akun ini.error
- Perangkat karyawan wajib terikat akun.error
- Perangkat terdaftar.success
- Kunci toko dibuat. Salin sekarang; tidak dapat ditampilkan lagi.success
- Kunci toko diganti. Salin sekarang; tidak dapat ditampilkan lagi.success
- Hub toko : aktif/dipaksa/menunggu/belum ada.success
- Pilih toko dan perangkat owner untuk hub.error
- Premium aktif.success
- Lisensi diperpanjang.success
- Masukkan kode pemulihan.error
- Ketik ID owner untuk konfirmasi.error
- Metadata premium dihapus. Data toko tidak disentuh.success
- Password direset.success
- PIN dihapus.success
- Akun dinonaktifkan.success
- Perangkat dicabut.success
- Slot perangkat dilepas.success
- Konflik ditandai selesai.success
- Pilih perangkat hub, isi kunci toko dan kunci privat perangkat.error
- Snapshot terenkripsi dibuat.success
- Pilih perangkat.error
- Pilih perangkat dan isi kunci toko.error
- Snapshot diterapkan.success
- Amplop kedaluwarsa dibersihkan: .success
- Arsip semua toko dibuat: .success
- Masuk sebagai .success
- Password karyawan diperbarui.success
- Password belum diganti. Ganti lewat pemilik bila perlu.warning
- PIN karyawan dibuat dari isian login pertama.success

## Dialog konfirmasi

- Hapus unit ? Riwayat servis yang sudah ada tetap tersimpan.
- \n\nTetap simpan transaksi dengan stok minus?
- Hapus printer "" dari daftar? Data transaksi, pelanggan, dan stok tidak dihapus.
- Cetak sebelumnya gagal dan sebagian struk mungkin sudah tercetak. Cetak ulang struk yang sama? Tidak ada transaksi baru yang dibuat.
- Pelanggan datang sesuai jadwal.Pelanggan tidak datang.
- Ubah status prospek menjadi ""?#followupStatusSave
- Nota masih memiliki sisa . Unit baru ditandai diambil setelah pembayaran dicatat. Buka nota sekarang?
- Tandai unit sudah diambil pelanggan?[data-action="pengerjaan-taken"][data-id=""]
- Proses klaim garansi untuk nota ini?
- Hapus sparepart ""?
- Hapus tarif jasa ""?
- Arsipkan ? Data karyawan tetap tersimpan dan bisa diaktifkan kembali.
- Aktifkan kembali ? Karyawan akan muncul lagi di daftar aktif.
- Hapus karyawan ""? Riwayat gaji dan hutang tetap tersimpan tanpa nama karyawan.
- Hapus hutang sebesar ?
- Bayar sebesar via ?#salaryTanggal#salaryPotonganHutang#salaryBonus#salaryBonusKeterangan#salaryCicilanHutang#salaryCatatan
- Hapus gaji periode ? Laporan akan dihitung ulang.
- Hapus supplier ""? Data barang tidak ikut terhapus.
- Arsipkan ? Data supplier tetap tersimpan dan bisa diaktifkan kembali.
- Aktifkan kembali ? Supplier akan muncul lagi di daftar aktif.
- Pulihkan data dari ""? Seluruh data saat ini akan diganti. Salinan pengaman tetap dibuat otomatis.
- Kosongkan semua isian transaksi? Isian yang belum disimpan akan hilang.
- Ganti kunci toko ? Amplop dan snapshot lama dihapus; outbox dikirim ulang. Lakukan setelah perangkat dicabut.
- Hapus PIN ? Karyawan harus membuat PIN baru.
- Nonaktifkan akun ?
- Cabut perangkat ini? Sesi perangkat langsung ditolak.
- Lepas slot perangkat? Tindakan ini hanya dapat dilakukan sekali per 72 jam.
- Terapkan snapshot ke toko aktif? Data toko saat ini akan diganti dan antrean lokal diputar ulang.
- Hapus metadata premium di database utama? Data bengkel dan backup tetap utuh.
- Prompt: Password baru untuk (kosongkan untuk dibuat otomatis):
- Prompt: ID snapshot yang diterapkan:

## Judul/subjudul yang diisi dinamis

- `bankAccount`: :
- `bankOwner`: a/n
- `customerModalTitle`: Tambah pelanggan
- `customerDirectoryCount`: pelanggan
- `customerDirectoryEmpty`: Tidak ada pelanggan yang cocok dengan pencarian "".Belum ada pelanggan terdaftar. Tambahkan pelanggan baru untuk mulai mencatat unit servis.
- `partStockHint`: Stok gudang berkurang otomatis.
- `jobSubtotal`: \u2014
- `partSubtotal`: \u2014
- `grandTotalValue`: \u2014
- `kembalianValue`: \u2014
- `dpSisaValue`: \u2014
- `jobSubtotal`: Rp 0
- `partSubtotal`: Rp 0
- `grandTotalValue`: Rp 0
- `dpSisaValue`: Rp 0
- `receiptTitle`: Struk
- `receiptSubtitle`: -
- `waModalTitle`: Pesan WhatsApp
- `waModalSubtitle`: Periksa pesan sebelum dibuka di WhatsApp.
- `waModalNote`: Pesan hanya dibuka di WhatsApp, tidak dikirim otomatis. Upaya dicatat saat tombol dibuka.
- `printerModalTitle`: Ubah printerTambah printer
- `printerModalSubtitle`: Perubahan alamat atau jenis koneksi akan memutus sesi printer ini.Simpan perangkat sekali, lalu sambungkan saat dibutuhkan.
- `statTotalDebtSub`: nota · pelanggan
- `statEmployeeDebtSub`: hutang berjalan
- `statPayrollSub`: karyawan jatuh tempo · karyawan · berikutnya -Tidak ada tagihan gaji
- `payrollAlertText`: , · total .
- `payrollModalSubtitle`: Total perlu dibayar · berikutnya
- `payrollPayTitle`: Bayar
- `payrollPaySubtitle`: Pilih cara pembayaran gaji dan komisi.
- `payrollPayDebtLabel`: Full bayar hutangCicil hutang
- `historyCount`: nota
- `notaListSubtitle`: ·
- `recordTitle`: Nota
- `recordSubtitle`: ·
- `exchangeDiffLabel`: Tambahan dibayarKembalianSelisih
- `customerDetailSubtitle`: ·
- `followupModalSubtitle`: AKAN_DATANGgaransi · ·
- `followupRescheduleSubtitle`: · · Jadwal saat ini
- `followupStatusSubtitle`: · ·
- `rescheduleSubtitle`: · sisa · tempo · belum ada tempo · sudah diingatkan
- `pengerjaanStatusSubtitle`: · -
- `stockSummary`: item · menipis · habis
- `jasaSummary`: tarif jasa
- `stockModalTitle`: Edit sparepartTambah sparepart
- `jasaModalTitle`: Edit tarif jasaTambah tarif jasa
- `periodNote`: · hanya hari yang memiliki transaksi.
- `soldPartsNote`: · penjualan · unit terjual · harga mengikuti harga deal, diurutkan menurut waktu.
- `reportDateLabel`: · sampai
- `employeeKomisiBarangLabel`: Komisi barang
- `employeeKomisiJasaLabel`: Komisi jasa
- `employeeModalTitle`: Edit karyawanTambah karyawan
- `employeeDetailSubtitle`: · Aktif · Nonaktif
- `employeeArchiveSubtitle`: karyawan di arsip. Data tetap tersimpan.
- `salaryHistorySubtitle`: pembayaran gaji tercatat, termasuk potongan hutang.
- `debtDetailSubtitle`: · LunasBelum lunas
- `debtHistoryTitle`: Seluruh hutang karyawan
- `debtHistorySubtitle`: catatan hutang karyawan.
- `debtModalTitle`: Edit hutang karyawanCatat hutang karyawan
- `salaryModalTitle`: Bayar karyawan
- `salaryEmployeeName`: -
- `salaryBankInfo`: · Nomor rekening karyawan belum diisi di menu Karyawan.
- `salaryBonusText`: · -
- `employeePerfTitle`: Performa Performa karyawan
- `employeePerfSubtitle`: Periode dapat diubah. Komisi dihitung per nota di backend.
- `employeePerfSubtitle`: Karyawan ·
- `employeePerfDetailTitle`: Rincian karyawan
- `supplierModalTitle`: Edit supplierTambah supplier
- `supplierArchiveSubtitle`: supplier di arsip. Data tetap tersimpan.
- `followupListTitle`: Follow up reseller
- `followupListSubtitle`: Pilih tindakan yang perlu dilakukan.
- `supplierPickSubtitle`: · pilih supplier untuk chat.
- `supplierStatusSubtitle`: ·
- `supplierPickSubtitle`: · pilih supplier untuk mengatur status.
- `supplierPickSubtitle`: · pilih supplier yang akan dihubungi.
- `premiumPlanBadge`: GratisPremium
- `premiumLicenseStatus`: Tidak aktifAktifKedaluwarsa
- `premiumDaysLeft`: hari
- `premiumOwnerId`: ID owner atau -
- `premiumSecretOut`: teks lisensi, token, kunci toko, snapshot, ringkasan owner, atau audit akun
- `accountSecretOut`: teks akun karyawan siap kirim atau hasil audit/snapshot akun
- `deviceSecretOut`: token/kunci perangkat atau hasil buat/ganti kunci toko
- `syncSecretOut`: hasil snapshot, penerapan, atau status sinkronisasi
- `syncComplete`: LengkapMenunggu
- `hubStore`/`hubDeviceId`: toko dan perangkat owner aktif
- `premiumStoreLabel`: aktif/dipaksa/menunggu/belum ada
