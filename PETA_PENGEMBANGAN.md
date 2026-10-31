# Rencana Pengembangan BengkelPOS Radiator

Dokumen ini berisi rencana tahap pengembangan berikutnya. **Belum ada kode yang
diubah untuk rencana di bawah ini**; semua butir masih berupa usulan sampai
tahapnya dikerjakan dan diverifikasi.

Status terpasang saat dokumen dibuat:

- UI web/desktop **2.2**
- APK Android **2.2.2** (versionCode 5)
- Backend FastAPI + SQLAlchemy (SQLite), kompatibel Pydantic v2 dan v1
- Test: 239 pytest per stack (v2 dan v1), 150 unit test Kotlin per varian
- Uji perangkat Android fisik: lulus per 31/10/2026 (cetak printer belum)
- Penggunaan saat ini: **sendiri**, belum dipakai publik dan belum ada
  pengguna eksternal

## Ringkasan tahap

| Tahap | Pekerjaan | Area | Prioritas | Status |
| --- | --- | --- | --- | --- |
| 1 | Verifikasi nota sebelum simpan atau cetak | Frontend kasir | Tinggi | Rencana |
| 3 | Informasi aplikasi dan profil bengkel saat instalasi pertama | Onboarding web + Android | Tinggi | Rencana |
| 4 | Akun, langganan daring, database server, backup otomatis Telegram, dan folder backup lokal | Onboarding + penyimpanan | Tinggi | Rencana |
| 5 | Peran owner dan admin (kasir), persetujuan owner untuk nota lama | Keamanan + kasir | Tinggi | Rencana |
| 7 | Penambahan stok dengan pemindai barcode | Stok + perangkat | Sedang | Rencana |
| 8 | Uji perangkat Android fisik dan printer nyata | Rilis | Tinggi | Berjalan — perangkat lulus, cetak printer belum |
| 9 | Ganti token bot Telegram hasil uji backup | Keamanan | Tinggi | Tertunda |
| 10 | Regresi UI dan sinkronisasi dokumentasi | Kualitas | Sedang | Berkelanjutan |

## Tahap 1 — Verifikasi nota sebelum disimpan

**Masalah.** Tombol **Simpan & cetak struk** dan **Simpan tanpa cetak** saat ini
langsung mengirim transaksi ke backend. Kasir tidak punya kesempatan memeriksa
ulang pelanggan, unit, item, atau nominal sebelum stok terpotong dan nota
tersimpan.

**Tujuan.** Menambahkan satu langkah pemeriksaan yang ringkas dan jelas sebelum
transaksi dikirim, tanpa mengubah perhitungan uang di backend.

**Perilaku yang diusulkan.**

1. Kasir menekan salah satu tombol simpan.
2. Aplikasi menjalankan validasi yang sudah ada (pelanggan, unit, keluhan,
   minimal satu item, dan format uang).
3. Aplikasi meminta pratinjau terbaru ke endpoint pratinjau yang sudah ada.
4. Muncul ringkasan pemeriksaan berisi:
   - nama dan nomor HP pelanggan;
   - unit servis;
   - daftar jasa dan sparepart beserta qty dan subtotal;
   - subtotal jasa, subtotal sparepart, diskon, dan total nota;
   - metode bayar, uang diterima, serta kembalian atau kekurangan;
   - status garansi.
5. Kasir memilih **Periksa lagi** untuk kembali tanpa menyimpan, atau
   **Simpan & cetak struk** / **Simpan tanpa cetak** untuk melanjutkan.
6. Setelah dikonfirmasi, alur penyimpanan yang sekarang berjalan seperti biasa,
   termasuk konfirmasi stok minus bila backend menolak stok.

**Batasan.**

- Nominal pada ringkasan berasal dari pratinjau backend, bukan hitungan ulang
  JavaScript.
- Perhitungan final tetap dilakukan backend dengan `Decimal` dan
  `ROUND_HALF_UP`.
- Tidak ada perubahan pada skema, endpoint, atau data transaksi.

**Kriteria selesai.**

- Kedua tombol simpan selalu menampilkan pemeriksaan sebelum mengirim request.
- Membatalkan pemeriksaan tidak menyimpan apa pun dan tidak mengubah stok.
- Ringkasan cocok dengan nota yang akhirnya tersimpan.
- Berfungsi di mode Terang dan Gelap serta pada lebar layar ponsel.

## Tahap 3 — Informasi aplikasi dan profil bengkel saat instalasi pertama

**Masalah.** Pada instalasi baru, aplikasi langsung meminta PIN (native di APK,
layar PIN web di desktop). Pengguna belum tahu aplikasi apa yang dibuka, dan
aplikasi selama ini terkesan hanya untuk servis radiator. Padahal bengkel bisa
melayani mobil atau motor, umum atau spesialis, dengan jenis barang dan jasa
yang berbeda.

**Tujuan.** Memberi informasi singkat tentang aplikasi sebelum PIN, lalu
menanyakan profil bengkel setelah PIN siap dan sebelum pengguna mulai bekerja,
sehingga master jasa dan sparepart mengikuti jenis bengkel — bukan hanya
radiator.

### 3.1 Alur layar

1. **Informasi aplikasi** — nama aplikasi, penjelasan singkat, data tersimpan di
   perangkat, berjalan tanpa internet, dan alasan aplikasi memakai PIN.
   Tombol **Lanjut** membuka langkah berikutnya.
2. **PIN** — bila belum ada PIN, pengguna membuat PIN lewat alur yang sudah
   berlaku; bila PIN sudah ada, pengguna masuk seperti biasa.
3. **Jenis kendaraan** — pertanyaan "Bengkel Anda melayani kendaraan apa?"
   dengan pilihan **Mobil**, **Motor**, atau **Mobil & Motor**.
4. **Spesialis atau umum** — pertanyaan "Apakah bengkel Anda spesialis?"
   dengan pilihan **Ya, spesialis** atau **Tidak, bengkel umum**.
5. **Pilihan spesialisasi** — hanya muncul bila memilih spesialis. Pengguna
   memilih satu spesialisasi utama; spesialisasi tambahan boleh dipilih bila
   bengkel memang menangani lebih dari satu bidang.
6. **Cakupan jasa** — pertanyaan "Apakah semua jenis jasa tersedia di bengkel
   Anda?" dengan pilihan **Ya, semua tersedia** atau **Tidak, pilih yang
   tersedia**. Bila memilih tidak, tampilkan daftar kelompok jasa untuk dicentang.
7. **Ringkasan profil** — tampilkan kendaraan, status spesialis, spesialisasi,
   dan kelompok jasa yang dipilih. Tombol **Simpan dan mulai** menyimpan profil
   lalu membuka layar utama.
8. Pengguna lama dan instalasi yang sudah punya PIN tidak melihat layar
   informasi maupun wizard profil.

**Urutan teknis.** Layar informasi tampil sebelum PIN. Pertanyaan profil
ditampilkan setelah PIN dibuat/dibuka dan backend lokal siap, karena pilihan
disimpan di database pengaturan. Dengan begitu logika layar PIN native tidak
perlu diubah.

### 3.2 Daftar spesialisasi

| Kode | Spesialisasi | Fokus utama | Contoh jasa atau barang |
| --- | --- | --- | --- |
| RADIATOR | Radiator & Pendingin | Perbaikan, servis, kored, penambalan, ganti core radiator, water pump, dan sistem pendingin mesin | Core radiator, water pump, coolant, selang radiator, tutup radiator |
| MESIN | Mesin / Engine & Overhaul | Turun mesin, piston, skir klep, korter silinder, dan komponen pembakaran | Piston, ring piston, klep, gasket, bearing, jasa overhaul |
| TRANSMISI | Transmisi & Kaki-kaki | Kemudi, suspensi, rem, serta transmisi manual, matic, dan CVT | Shockbreaker, per, kampas rem, bearing, oli transmisi, jasa servis CVT |
| KELISTRIKAN | Kelistrikan & AC | Kelistrikan bodi, alternator, aki, ECU/sensor, pengapian, dan AC | Aki, alternator, busi, kompresor AC, freon, jasa scanner |
| SPOORING | Kaki-kaki Spesialis (Spooring & Balancing) | Penyetelan sudut roda, keseimbangan ban, dan kestabilan laju | Jasa spooring, balancing, timbal ban, pemeriksaan kaki-kaki |
| BODY | Cat, Ketok Magic & Body Repair | Restorasi bodi, penyok, las sasis, dempul, dan cat ulang | Cat, dempul, panel bodi, jasa ketok magic, jasa oven cat |
| KACAFILM | Kaca Film & Aksesoris | Pemasangan kaca film, perbaikan kaca retak, dan aksesoris | Kaca film, kaca mobil, aksesoris interior dan eksterior |
| BUBUT | Bubut / Machining Shop | Bubut piringan rem, facing blok/head, bushing, dan komponen presisi | Jasa bubut, bushing, facing head silinder, piringan rem |
| KNALPOT | Knalpot / Exhaust System | Perbaikan, penggantian, dan modifikasi header, pipa, resonator, muffler | Header, pipa knalpot, resonator, muffler |
| INJEKSI | Injeksi & ECU Tuning | Pembersihan injector ultrasonik, diagnostic scanner, dan remap ECU | Jasa cuci injector, jasa scanner, jasa remap ECU |

Kelompok jasa pada langkah 5 memakai daftar yang sama. Bila pengguna memilih
spesialis, kelompok jasa milik spesialisasi tersebut tercentang otomatis dan
masih dapat diubah.

### 3.3 Arti "semua ada jasanya"

Pertanyaan ini diartikan sebagai: **apakah seluruh kelompok jasa di atas
tersedia di bengkel tersebut?**

- **Ya, semua tersedia** — semua kelompok jasa aktif; kasir dapat memakai jasa
  dan sparepart dari bidang mana pun.
- **Tidak, pilih yang tersedia** — hanya kelompok yang dicentang yang tampil
  sebagai pilihan utama. Item di luar pilihan tetap dapat ditambahkan secara
  manual bila suatu saat dibutuhkan, kecuali pengguna memilih untuk
  menyembunyikannya.

### 3.4 Dampak ke data dan master barang

- Profil disimpan sebagai konfigurasi bengkel (kendaraan, status spesialis,
  spesialisasi utama, spesialisasi tambahan, kelompok jasa, dan penanda
  onboarding selesai). Tidak ada data transaksi yang dihitung ulang.
- Master **sparepart** dan **tarif jasa** mendapat kategori bidang. Daftar stok
  tidak lagi terbatas pada radiator; bengkel mesin dapat menyimpan piston dan
  gasket, bengkel kelistrikan dapat menyimpan aki dan alternator, dan seterusnya.
- Unit kendaraan mendukung **Mobil** dan **Motor** sesuai pilihan kendaraan.
  Unit lama tetap tampil dan tidak diubah jenisnya.
- Data lama tidak dihapus atau ditimpa. Item yang belum punya kategori diberi
  kategori netral (misalnya **Umum**) dan tetap dapat dipakai.
- Profil dapat diubah kapan saja di **Pengaturan → Profil bengkel**. Perubahan
  profil hanya memengaruhi pilihan yang ditampilkan, bukan nota yang sudah ada.
- Template contoh jasa/barang per spesialisasi bersifat opsional; aplikasi tidak
  memaksa data contoh masuk ke database pengguna.
- Onboarding hanya muncul sekali per instalasi dan tidak muncul lagi setelah
  reset PIN atau pemulihan backup yang sudah membawa profil.

### Batasan

- PIN, hash PIN, salt, lockout, penyimpanan aman, dan alur reset **tidak boleh
  dihapus, ditimpa, atau dikembangkan ulang**.
- Tidak ada data rahasia (token, hash, atau konfigurasi keamanan) yang
  ditampilkan di layar informasi atau profil.
- Tidak ada perubahan pada perhitungan uang, skema transaksi, atau data
  pelanggan yang sudah ada.

### Kriteria selesai

- Instalasi baru menampilkan informasi aplikasi sebelum PIN.
- Setelah PIN siap, pengguna dapat memilih Mobil/Motor/Mobil & Motor, status
  spesialis, spesialisasi, dan cakupan jasa.
- Pilihan tersimpan, tampil lagi di Pengaturan, dan memengaruhi kategori master
  jasa/sparepart tanpa menghapus data lama.
- Instalasi lama dengan PIN tidak dipaksa mengulang onboarding.
- Menutup aplikasi di tengah onboarding tidak merusak data; pengguna dapat
  melanjutkan atau mengulang tanpa kehilangan transaksi.

## Tahap 4 — Akun, langganan, dan penyimpanan backup (lokal/daring)

**Masalah.** Aplikasi saat ini hanya memakai PIN lokal dan data hanya tersimpan
di perangkat. Untuk model langganan, pemilik toko perlu akun agar status
langganan dapat dikenali. Sebagian pemilik juga tidak ingin mengurus backup
sendiri dan ingin databasenya disimpan di server penyedia aplikasi dengan
unggahan otomatis. Di sisi lain, backup lokal yang ada sekarang sulit ditemukan
lewat file manager. Pengguna lain tetap harus bisa memakai aplikasi tanpa akun.

**Tujuan.** Menawarkan akun Google/email sebagai jalur langganan dan database
daring opsional, sekaligus membuat backup lokal otomatis tersimpan di folder
yang terlihat di file manager. Aplikasi tetap berjalan lokal tanpa akun; akun
tidak menggantikan PIN.

### 4.1 Alur saat instalasi pertama

1. Layar informasi aplikasi (Tahap 3) → tombol **Lanjut**.
2. Layar akun menampilkan tiga pilihan:
   - **Masuk dengan Google**
   - **Masuk dengan Email**
   - **Lewati**
3. **Lewati** → mode lokal **gratis selamanya**: lanjut ke pembuatan PIN dan
   aplikasi berjalan seperti sekarang. Langganan dan database daring tidak
   aktif.
4. **Masuk berhasil** → akun terhubung → tetap membuat PIN lokal → pengguna
   dapat memilih paket langganan untuk fitur daring. Pemilihan paket boleh
   ditunda ke Pengaturan.
5. **Masuk gagal atau tidak ada internet** → pesan jelas, data tidak berubah,
   dan **Lewati** tetap dapat dipakai.

### 4.2 Akun, langganan, dan database daring di Pengaturan

- Bagian **Akun** menampilkan status **Belum dikaitkan** atau email terhubung,
  status langganan layanan daring (percobaan, aktif, lewat jatuh tempo,
  nonaktif), dan tanggal perpanjangan.
- Tombol **Kaitkan dengan Google**, **Kaitkan dengan Email**, **Lepas kaitan**,
  dan **Kelola langganan**.
- Bagian **Database daring** berisi saklar **Simpan database di server**,
  jadwal unggah otomatis, tombol **Unggah sekarang**, **Pulihkan dari server**,
  **Ekspor**, dan **Hapus data di server**.
- Bagian **Backup** menandai jadwal **Backup otomatis ke Telegram** sebagai
  fitur **Paket Daring**, dengan keterangan bahwa pengiriman manual tetap
  gratis. Bila langganan tidak aktif, saklar otomatis dinonaktifkan tanpa
  menghapus pengaturan bot atau token yang sudah ada.
- Melepas akun atau menghentikan langganan tidak menghapus data lokal. Data di
  server mengikuti kebijakan retensi yang disetujui pengguna.
- Satu instalasi hanya memiliki satu akun owner. Mengganti akun dilakukan
  dengan melepas lalu mengaitkan ulang.

### 4.3 Model langganan

- **Mode lokal gratis selamanya**, tanpa batas waktu, jumlah transaksi, atau
  kewajiban akun. Langganan hanya membayar layanan daring: database di server,
  unggah otomatis, **backup otomatis terjadwal ke Telegram**, dan fitur daring
  lain yang disetujui.
- **Backup manual dan backup lokal otomatis tetap gratis:** ekspor berkas,
  simpan ke folder pilihan, berbagi berkas, dan tombol kirim manual ke Telegram
  tidak memerlukan langganan. Yang berbayar adalah otomatisasi ke Telegram dan
  unggahan ke server.
- Satu langganan melekat pada akun owner dan satu toko/instalasi. Akun kasir
  (admin) tidak memerlukan langganan sendiri.
- Status langganan diperiksa ke server. Aplikasi menyimpan status terakhir yang
  ditandatangani beserta masa tenggang (misalnya 7–14 hari) agar kasir tetap
  dapat bekerja saat internet mati.
- Saat langganan tidak aktif, fitur lokal tetap berjalan penuh. Jadwal backup
  otomatis berhenti, tetapi konfigurasi Telegram, token, dan data lokal tidak
  dihapus; pengguna tetap dapat melakukan backup manual.
- **Kanal pembayaran:** APK yang dijual lewat Play Store harus memakai Google
  Play Billing untuk langganan digital. Versi web/direct dapat memakai payment
  gateway (misalnya Midtrans atau Xendit). Kanal final perlu diputuskan sebelum
  rilis.
- Perubahan status langganan tidak boleh mengubah nota, stok, atau perhitungan
  uang.

### 4.4 Database daring dan unggahan otomatis

- Bersifat pilihan (opt-in) per toko.
- Tahap pertama berupa **snapshot backup terenkripsi** yang diunggah otomatis
  (misalnya harian atau setelah tutup buku), bukan sinkronisasi real-time.
- Data lokal SQLite tetap sumber utama. Server menyimpan salinan untuk
  pemulihan.
- Pemulihan dari server harus eksplisit: pengguna memilih snapshot, aplikasi
  memperingatkan bahwa data lokal akan diganti, dan alur PIN/keamanan yang ada
  tetap dipakai.
- Setiap toko terisolasi (tenant terpisah); akses hanya lewat akun owner yang
  terautentikasi.
- Enkripsi saat transit (TLS) dan saat disimpan; kunci dikelola server dengan
  rotasi.
- Owner dapat mengekspor dan menghapus data di server. Kebijakan retensi dan
  penghapusan harus tertulis.
- PIN, hash PIN, salt, token, dan kunci tidak boleh masuk berkas backup yang
  diunggah. Bila suatu data sensitif memang harus ada, data tersebut wajib
  terenkripsi dan tidak dapat dibaca operator.

### 4.5 Backup lokal otomatis ke folder file manager

- Backup lokal otomatis tetap **gratis** dan tidak memerlukan akun atau
  langganan.
- Saat pertama diaktifkan, owner memilih folder lewat pemilih folder sistem
  (Storage Access Framework di Android). Aplikasi membuat subfolder
  `BengkelPOS/Backup` di dalam folder yang dipilih bila diizinkan.
- Izin folder disimpan, sehingga backup berikutnya tidak meminta izin ulang.
- Nama berkas memuat tanggal dan waktu, misalnya
  `bengkelpos-20261031-0635.bak`, agar backup tidak saling menimpa.
- Pengaturan menampilkan lokasi folder, waktu backup terakhir, ukuran berkas,
  dan status berhasil atau gagal.
- Tombol **Backup sekarang**, **Ganti folder**, **Buka folder** (bila didukung
  perangkat), dan **Hapus berkas lama**.
- Retensi dapat diatur, misalnya menyimpan 7 backup harian dan 4 mingguan.
  Aplikasi hanya menghapus berkas backup yang dibuatnya sendiri, dan penghapusan
  massal meminta konfirmasi.
- Bila izin folder dicabut atau folder hilang, backup otomatis berhenti dengan
  pemberitahuan jelas dan sementara memakai folder aplikasi. Data tidak hilang;
  backup otomatis aktif lagi setelah folder dipilih.
- **Android:** mengikuti scoped storage Android 11 ke atas, jadi lokasi dipilih
  pengguna lewat pemilih folder, bukan path absolut paksa.
- **Desktop/web:** memakai File System Access API bila tersedia. Bila tidak,
  backup diunduh ke folder Unduhan dengan nama berkas yang sama.
- Format backup dibuat sama antara APK dan web agar dapat dipulihkan lintas
  platform selama versi databasenya kompatibel.
- Berkas backup tidak boleh memuat PIN, hash, salt, token Telegram, atau kunci.
  Bila konfigurasi sensitif harus ikut, isinya wajib terenkripsi.
- Aplikasi hanya mengakses folder yang dipilih pengguna dan tidak memindai
  folder lain.

### 4.6 Keamanan dan kepemilikan data

- Data transaksi milik toko. Penyedia aplikasi hanya memproses untuk backup dan
  pemulihan.
- Akses dukungan ke data toko harus melalui persetujuan owner dan tercatat.
- Data toko tidak dipakai untuk analitik pihak ketiga tanpa persetujuan.
- Kebijakan privasi dan Play Data Safety harus mencakup email akun, foto kamera
  (bila pemindai kamera dipakai), dan backup daring.
- Sesuai UU PDP, jelaskan lokasi penyimpanan, masa simpan, serta hak ekspor dan
  penghapusan data.

### 4.7 Batasan

- PIN, hash PIN, salt, lockout, penyimpanan aman, dan alur reset **tidak dihapus,
  ditimpa, atau dikembangkan ulang**.
- Akun, langganan, dan database daring bersifat opsional; tanpa internet
  aplikasi lokal tetap dapat dipakai.
- Tahap ini **bukan** sinkronisasi real-time atau multi-perangkat; hanya backup
  dan pemulihan snapshot.
- Layanan server adalah komponen baru di luar APK. Ini menambah biaya
  operasional, pemantauan, pencadangan server, dan pemeliharaan.
- Fitur Telegram yang sudah ada tidak dihapus. Yang digerbangi hanya
  otomatisasinya; pengaturan bot, token, dan berkas backup manual tetap
  tersedia saat langganan tidak aktif.
- Aplikasi masih dipakai sendiri, jadi belum ada pengguna eksternal yang perlu
  dimigrasikan. Kebijakan masa tenggang untuk backup otomatis baru disusun
  sebelum aplikasi mulai dipakai pihak lain.
- Token akun disimpan di penyimpanan aman perangkat (APK) atau penyimpanan sesi
  aman (web), tidak pernah dicetak pada nota, tidak masuk log, dan tidak
  ditampilkan di layar.
- Tidak ada perubahan pada perhitungan uang, nomor nota, atau skema transaksi.
- Peran owner/admin (kasir) diatur terpisah di Tahap 5; akun yang dikaitkan
  tidak otomatis menjadi owner.

### 4.8 Keputusan yang perlu disetujui

- **Penyedia autentikasi** — Google Sign-In dan email memerlukan layanan
  autentikasi (misalnya Firebase Authentication) beserta konfigurasi OAuth.
  Alternatifnya backend sendiri dengan email dan kata sandi.
- **Metode email** — tautan masuk (magic link) direkomendasikan agar aplikasi
  tidak menyimpan kata sandi; alternatifnya kata sandi + verifikasi email.
- **Kanal pembayaran** — Google Play Billing untuk APK di Play Store, atau
  payment gateway untuk penjualan langsung.
- **Masa tenggang offline** — berapa hari aplikasi tetap dapat dipakai saat
  status langganan tidak dapat diperiksa.
- **Cakupan paket** — apakah database daring, unggah otomatis, dan backup
  otomatis Telegram masuk satu paket atau add-on terpisah, beserta kuota dan
  masa retensi.
- **Batas gratis dan berbayar** — usulan saat ini: backup manual dan kirim
  manual ke Telegram gratis; jadwal otomatis ke Telegram berbayar; backup lokal
  otomatis tetap gratis.
- **Retensi backup lokal** — berapa banyak berkas backup yang disimpan secara
  bawaan (misalnya 7 harian + 4 mingguan) dan apakah pengguna dapat mengubahnya.
- **Lokasi server** — apakah data disimpan di Indonesia dan bagaimana kebijakan
  retensinya.

### Kriteria selesai

- Instalasi baru menampilkan pilihan Google, email, dan **Lewati** sebelum
  pembuatan PIN.
- **Lewati** membuka pembuatan PIN tanpa error, tanpa akun, dan tanpa
  ketergantungan server.
- Mode lokal tetap gratis selamanya dan tidak pernah terkunci karena tidak ada
  akun atau langganan.
- Login berhasil mengaitkan akun, menampilkan status langganan, dan PIN lokal
  tetap berlaku.
- Saat offline atau langganan lewat jatuh tempo, aplikasi lokal tetap dapat
  dipakai dan fitur daring ditandai tidak tersedia dengan jelas.
- Owner dapat mengaktifkan unggah otomatis, melihat snapshot di server, dan
  memulihkannya dengan peringatan yang jelas.
- Backup otomatis terjadwal ke Telegram hanya aktif dengan langganan; backup
  manual dan kirim manual tetap berfungsi tanpa langganan.
- Saat langganan berakhir, pengaturan bot, token, dan data lokal tetap ada;
  hanya jadwal otomatis yang berhenti.
- Ekspor dan hapus data di server berfungsi tanpa menghapus data lokal.
- Backup lokal otomatis pertama meminta folder, membuat subfolder backup, dan
  menulis berkas yang terlihat di file manager.
- Backup lokal berikutnya memakai folder yang sama tanpa meminta izin ulang;
  ganti folder, backup manual, dan hapus berkas lama berfungsi.
- Mencabut izin folder menampilkan peringatan dan tidak menghilangkan data.
- Isolasi tenant teruji: toko lain tidak dapat mengakses data toko ini.
- Tidak ada PIN, hash, salt, atau token di berkas backup, baik lokal maupun
  yang diunggah.
- Tidak ada perubahan pada total, nomor nota, atau data transaksi.
- Tampilan berfungsi di mode Terang/Gelap dan lebar layar ponsel.

## Tahap 5 — Peran owner dan admin (kasir), persetujuan owner untuk nota lama

**Masalah.** Saat ini satu PIN membuka seluruh aplikasi. Siapa pun yang memegang
PIN dapat mengubah nota lama, harga, stok, dan pengaturan, sehingga tidak ada
pemisahan tugas antara admin (kasir) dan owner (pemilik bengkel).

**Tujuan.** Memisahkan peran **owner (master/pemilik)** dan **admin (kasir)**.
Admin hanya dapat membuat nota baru; perubahan pada nota yang sudah tersimpan
harus disetujui owner. Semua perubahan tercatat.

### 5.1 Hak akses per peran

| Tindakan | Owner | Admin (kasir) |
| --- | --- | --- |
| Membuat nota baru dan mencetak | Ya | Ya |
| Melihat nota yang sudah tersimpan | Ya | Ya, hanya baca |
| Melihat harga modal dan laba | Ya | Tidak |
| Void, retur, atau koreksi nota tersimpan | Ya, langsung dan tercatat | Tidak, harus diajukan |
| Mengubah tarif jasa, harga sparepart, stok | Ya | Tidak |
| Menghapus master data | Ya | Tidak |
| Pengaturan (identitas, printer, backup, Telegram, akun) | Ya | Tidak |
| Mengelola admin dan mereset PIN admin | Ya | Tidak |
| Laporan penjualan dan laba | Ya | Tidak |

Admin (kasir) tetap dapat melihat katalog jasa dan sparepart secara baca-saja
agar bisa menulis nota, tanpa melihat harga modal.

### 5.2 Alur admin membuat nota

1. Admin masuk dengan PIN admin masing-masing dan membuat nota seperti biasa.
2. Nota tersimpan dan struk tercetak; admin tidak mendapat tombol untuk
   mengubah nota tersebut.
3. Peran yang sedang aktif ditampilkan jelas (misalnya lencana **Admin**) agar
   kasir tidak mengira sedang memakai akses owner.

### 5.3 Konfirmasi owner untuk nota lama

1. Admin membuka nota lama dan memilih tindakan yang memerlukan persetujuan,
   misalnya **Ajukan void**, **Ajukan retur**, atau **Ajukan koreksi**.
2. Admin wajib mengisi alasan pengajuan.
3. Pengajuan masuk ke daftar **Permintaan persetujuan** milik owner. Nota belum
   berubah selama menunggu.
4. Owner memeriksa nota dan alasan, lalu memilih **Setujui** atau **Tolak**
   dengan PIN owner.
5. Bila disetujui, backend menjalankan void/retur/koreksi memakai aturan yang
   sudah ada. Nota asli tidak ditimpa; perubahan dan alasannya tercatat.
6. Bila ditolak, tidak ada data yang berubah dan admin melihat alasan
   penolakan bila diisi owner.
7. Tanpa persetujuan owner, admin tidak dapat memaksa perubahan melalui UI
   maupun permintaan langsung ke API.

Persetujuan dilakukan owner di perangkat yang sama dengan PIN owner, sehingga
tetap berjalan tanpa internet. Persetujuan jarak jauh lewat akun di luar
cakupan tahap ini.

### 5.4 Jejak audit perubahan

- Setiap pengajuan mencatat: nomor nota, jenis perubahan, alasan, admin
  pengaju, waktu pengajuan, status, owner yang memutuskan, dan waktu keputusan.
- Setiap perubahan yang disetujui mencatat nilai sebelum dan sesudah dari
  backend, bukan hitungan ulang JavaScript atau Kotlin.
- Riwayat audit bersifat tambah-saja (append-only); admin tidak dapat
  menghapusnya.
- Owner dapat melihat riwayat ini di Pengaturan; tampilan tidak memuat token,
  hash PIN, atau data rahasia lain.

### 5.5 Sesi, PIN, dan pengelolaan admin

- PIN yang sudah ada menjadi **PIN owner** dan alurnya tidak diubah. Admin
  (kasir) mendapat PIN sendiri dengan hash, salt, dan lockout terpisah.
- Owner dapat menambah admin (kasir), menonaktifkan admin, dan mereset PIN
  admin. Reset PIN admin tidak menghapus transaksi atau data lain.
- Langganan dan akun Google/email melekat pada owner. Akun kasir tidak
  memerlukan langganan sendiri dan tidak harus memakai akun Google/email.
- Minimal harus ada satu owner aktif; owner terakhir tidak dapat dihapus atau
  diturunkan menjadi admin.
- Admin tidak dapat melihat atau mengubah PIN owner.
- Peran ditentukan saat masuk dan disimpan pada sesi. Kembali ke layar masuk
  memakai perilaku yang sudah ada.
- Backend menolak operasi berdasarkan peran. Menyembunyikan tombol di UI hanya
  lapisan tampilan, bukan satu-satunya pengaman.

### 5.6 Batasan

- Tidak mengubah perhitungan uang atau penomoran nota. Nominal tetap dihitung
  backend dengan `Decimal` dan `ROUND_HALF_UP`.
- Nota lama tidak diedit langsung; koreksi hanya melalui void/retur/koreksi
  resmi dengan persetujuan owner.
- Menonaktifkan admin tidak menghapus transaksinya.
- Aplikasi tetap dapat dipakai tanpa internet karena persetujuan owner terjadi
  di perangkat yang sama.
- Akun Google/email (Tahap 4) tidak otomatis memberikan peran owner; peran
  diatur terpisah oleh owner.

### Kriteria selesai

- Instalasi baru menetapkan PIN pertama sebagai owner, dan owner dapat
  menambahkan admin.
- Admin hanya dapat membuat/mencetak nota serta melihat data yang diizinkan.
- Admin tidak dapat void, retur, atau mengubah nota tersimpan tanpa persetujuan
  owner.
- Pengajuan admin muncul ke owner beserta alasan; penolakan tidak mengubah data.
- Setelah disetujui, perubahan berjalan dan tercatat di jejak audit.
- Admin tidak dapat menyetujui pengajuannya sendiri.
- Owner terakhir tidak dapat dihapus atau diturunkan.
- Permintaan langsung ke API ditolak bila peran tidak berhak, bukan hanya
  tombolnya disembunyikan.
- Tampilan berfungsi di mode Terang/Gelap dan lebar layar ponsel.

## Tahap 7 — Penambahan stok dengan pemindai barcode

**Masalah.** Penambahan stok saat ini diketik manual. Salah ketik kode atau nama
barang membuat stok tidak cocok, dan menambah banyak item satu per satu lambat.

**Tujuan.** Memungkinkan penambahan stok lewat pemindai barcode/QR yang
terhubung ke perangkat, tanpa mengubah perhitungan stok atau data yang sudah
ada.

### 7.1 Jenis pemindai yang didukung

- **USB/OTG HID** — pemindai bertindak sebagai keyboard, tanpa driver tambahan;
  cocok untuk desktop dan APK dengan kabel OTG.
- **Bluetooth HID** — dipasangkan lewat pengaturan Bluetooth perangkat, lalu
  masuk sebagai input keyboard.
- **Kamera perangkat** — cadangan bila tidak ada pemindai; hanya aktif setelah
  pengguna memberikan izin kamera.
- Input manual tetap tersedia di semua kondisi.

### 7.2 Alur penambahan stok

1. Owner membuka **Stok → Tambah stok** (hak ubah stok hanya milik owner sesuai
   Tahap 5).
2. Kolom kode barang otomatis fokus. Pindai barcode; kode terisi dan Enter
   dijalankan otomatis.
3. Bila kode dikenal, tampilkan nama barang, stok saat ini, dan satuan; kursor
   pindah ke kolom jumlah.
4. Masukkan jumlah lalu simpan. Alternatifnya, setiap pindai menambah 1 ke
   jumlah pada mode tambah cepat.
5. Bila kode tidak dikenal, tampilkan pilihan **Tambah barang baru** atau
   **Cari manual**; tidak ada barang yang dibuat otomatis tanpa konfirmasi.
6. Beberapa barang dapat dipindai berurutan ke dalam satu daftar, lalu disimpan
   sekaligus dalam satu transaksi.

### 7.3 Aturan

- Pemindai hanya alat input. Backend tetap satu-satunya sumber data stok dan
  perhitungan.
- Kode barang harus unik. Bila satu barcode memetakan beberapa item, tampilkan
  pilihan dan minta pengguna memilih.
- Penambahan stok memakai mekanisme dan ledger stok yang sudah ada; stok lama
  tidak ditimpa.
- Harga dan nominal tidak dihitung ulang di perangkat; hanya backend yang
  menghitung dengan `Decimal` dan `ROUND_HALF_UP`.
- Berjalan tanpa internet karena pemindai terhubung langsung ke perangkat.
- Admin tidak dapat menambah atau mengubah stok; aturan peran Tahap 5 berlaku.

### 7.4 Batasan

- Tidak membuat `PrinterManager` baru atau adapter printer baru.
- Tidak mengubah skema transaksi, nomor nota, atau data pelanggan.
- Tidak menyimpan data pemindai dan tidak meminta izin kamera bila mode kamera
  tidak dipakai.
- Pemindaian banyak barang dari satu foto atau daftar belanja di luar cakupan
  tahap ini.

### Kriteria selesai

- Pemindai HID USB maupun Bluetooth mengisi kode barang dan menambah stok tanpa
  mengetik manual.
- Kode tidak dikenal menampilkan pilihan yang jelas dan tidak membuat data
  otomatis.
- Penambahan stok tercatat dan cocok dengan ledger stok.
- Mode kamera berfungsi setelah izin diberikan; menolak izin tidak mengganggu
  input manual.
- Beberapa barang dapat dipindai lalu disimpan sekaligus tanpa stok ganda.
- Tampilan berfungsi di mode Terang/Gelap dan lebar layar ponsel.

## Tahap 8 — Uji perangkat Android dan printer nyata

**Status per 31/10/2026.** Pengujian di perangkat Android fisik sudah berjalan
baik. Yang belum diuji hanya sambungan ke printer nyata.

**Sudah lulus di perangkat fisik.**

- APK hasil build terbaru terpasang dan dijalankan.
- PIN, transaksi, screenshot, mode Terang/Gelap, restore, dan backup berjalan
  tanpa masalah yang dilaporkan.

**Belum dikerjakan.**

- Menyambungkan dan mencetak ke printer Bluetooth, Wi-Fi/LAN, dan USB yang
  dipakai bengkel.
- Mencatat model perangkat, versi Android, dan model printer yang lolos.

**Kriteria selesai.** Ada catatan hasil uji cetak nyata pada tiap jenis
sambungan printer; bug yang ditemukan masuk daftar perbaikan sebelum rilis
dianggap stabil.

## Tahap 9 — Keamanan token Telegram

**Pekerjaan.**

- Ganti token bot Telegram yang pernah dipakai saat uji backup.
- Pastikan token baru hanya disimpan di Pengaturan atau `.env` lokal dan tidak
  masuk ke repository, log, atau dokumentasi.
- Uji ulang pengiriman backup setelah token diganti.

**Kriteria selesai.** Token lama tidak berlaku lagi dan backup Telegram berhasil
dengan token baru.

## Tahap 10 — Regresi UI dan dokumentasi

**Pekerjaan.**

- Setiap perubahan UI diuji pada mode Terang dan Gelap serta lebar ponsel.
- Perbarui README, inventaris teks UI, dan README APK bila teks atau alur
  berubah.
- Jalankan pytest pada kedua stack dan unit test Kotlin sebelum build APK.
- Naikkan versi APK agar backend tertanam diekstrak ulang saat pemasangan.

## Kesiapan produksi

Bagian ini bukan fitur baru, melainkan syarat tambahan sebelum aplikasi dipakai
pihak lain. Status saat ini: dipakai sendiri, belum ada pengguna eksternal.

### Gate wajib sebelum rilis publik

| Gate | Syarat lulus |
| --- | --- |
| Printer nyata | Struk dan label tercetak benar pada 58/80 mm dan A4, Bluetooth, Wi-Fi/LAN, serta USB |
| Build rilis | AAB/APK release bertanda tangan, naik versi, dan teruji upgrade dari versi sebelumnya |
| Peran dan audit | Admin (kasir) tidak dapat mengubah nota tersimpan lewat UI maupun API; persetujuan owner dan audit teruji |
| Backup dan restore | Backup lokal/daring dapat dipulihkan lintas versi dan perangkat; izin folder dicabut dan ruang penuh tertangani |
| Langganan dan cloud | Status langganan, masa tenggang offline, pembayaran, pembatalan, dan isolasi tenant teruji |
| Keamanan dan privasi | Rotasi token, pemindaian rahasia, tinjauan otorisasi, kebijakan privasi, dan Data Safety siap |
| Operasi dan dukungan | Crash reporting, monitoring server, kanal dukungan, dan prosedur pemulihan tersedia |

### Rilis dan distribusi

- Build **release** dengan keystore yang disimpan aman dan dicadangkan;
  `versionCode` naik setiap rilis.
- Uji build release Chaquopy, termasuk minify/ProGuard dan ekstraksi backend
  tertanam, bukan hanya build Debug.
- Uji upgrade dari versi yang sudah terpasang tanpa kehilangan data, dengan
  jalur rollback lewat backup.
- Sesuaikan target SDK dengan kebijakan Play Store; deklarasikan izin Bluetooth,
  kamera, USB, dan notifikasi beserta alasannya.
- Siapkan halaman toko: kebijakan privasi, Data Safety, kontak dukungan, dan
  tangkapan layar. Bila distribusi langsung, siapkan mekanisme pembaruan.

### Keamanan dan kepatuhan

- Rotasi token Telegram dan pemindaian rahasia di repository/CI; tidak ada token
  di log, backup, atau dokumentasi.
- Tinjau ulang pengamanan lokal: parameter PBKDF2, lockout, batas sesi, Host dan
  Origin guard, token per instalasi, serta dokumentasi API yang dimatikan.
- Cloud: isolasi tenant, otorisasi per peran, enkripsi dan rotasi kunci, rate
  limit, validasi unggahan, audit akses, serta penghapusan data.
- Pembayaran: verifikasi webhook, idempotensi, status langganan, pembatalan,
  refund, dan perlindungan replay.
- UU PDP: dasar pemrosesan, kebijakan privasi, masa retensi, ekspor/hapus,
  lokasi data, dan prosedur insiden kebocoran.
- Periksa lisensi dependensi, termasuk Chaquopy, untuk distribusi komersial.

### Keandalan data

- Matriks migrasi dari setiap versi skema; backup otomatis sebelum migrasi.
- Restore lintas versi dan lintas perangkat, dengan checksum snapshot dan uji
  saat penyimpanan hampir penuh.
- Uji listrik mati atau crash di tengah transaksi, WAL, integrity check, dan
  pemulihan database rusak.
- Idempotensi request, konkurensi nota/stok, pergantian hari, dan zona waktu.
- Prosedur pemulihan bila kunci enkripsi backup hilang; backup tidak boleh
  menjadi tidak terbaca tanpa jalan keluar.
- Penanganan izin folder backup dicabut, kartu SD dilepas, dan ruang habis.

### Pengujian minimum

- E2E: onboarding, PIN, peran owner/kasir, persetujuan nota, verifikasi simpan,
  label, pemindai, backup/restore, dan status langganan.
- Uji negatif otorisasi: admin memanggil API langsung, akses lintas tenant, dan
  path traversal pada unggahan.
- Printer: 58/80/A4, Bluetooth/Wi-Fi/USB, teks panjang, karakter Indonesia,
  kertas habis, sambungan terputus, dan cetak ulang.
- Perangkat: beberapa versi Android, layar kecil, mode gelap, RAM rendah, dan
  kondisi tanpa internet.
- Beban: ribuan transaksi, laporan panjang, waktu mulai, dan ukuran backup.
- Aksesibilitas: kontras, ukuran area sentuh, dan font besar.

### Operasi dan dukungan

- Crash reporting dan log terpusat dengan penyamaran data sensitif.
- Monitoring server, peringatan biaya, uptime, backup server, disaster recovery,
  serta lingkungan staging terpisah dari produksi.
- Kanal dukungan dan panduan pemulihan: PIN hilang, ganti perangkat, langganan
  berakhir, dan akun owner tidak dapat diakses.
- Prosedur pemulihan akun owner agar langganan dan data daring tetap dapat
  diakses bila akses Google/email hilang.
- Kebijakan insiden: kontak, waktu respons, dan komunikasi ke pengguna.

### Komersial dan hukum

- Harga, masa percobaan, masa tenggang, penagihan ulang, refund, pajak/PPN, dan
  faktur.
- Syarat layanan dan kebijakan privasi berbahasa Indonesia.
- Perjanjian pengolahan data untuk toko yang memakai database server.
- Batas perangkat dan printer yang dijanjikan dalam dukungan.

### Strategi rilis yang disarankan

Dua jalur terpisah:

1. **Rilis lokal gratis** setelah gate printer, build rilis, peran/audit,
   backup/restore, dan pengujian inti lulus. Cocok untuk uji terbatas di beberapa
   bengkel sebelum publik.
2. **Rilis layanan berbayar** setelah cloud, billing, isolasi tenant, privasi,
   dan operasi server lulus.

Tradeoff: menunda pendapatan langganan, tetapi risiko ke pengguna dan reputasi
jauh lebih kecil. Jangan mengaktifkan langganan untuk fitur yang belum terbukti
stabil.

## Aturan yang dijaga di semua tahap

- PIN dan reset PIN tidak dihapus, ditimpa, atau dikembangkan ulang.
- Akun Google/email, langganan, dan database daring bersifat opsional, tidak
  menggantikan PIN, dan melepas kaitan tidak menghapus data lokal. Mode lokal
  gratis selamanya dan tidak boleh dikunci oleh status langganan.
- Backup lokal (manual maupun otomatis ke folder pilihan) tetap gratis; yang
  berbayar adalah otomatisasi ke Telegram dan penyimpanan di server.
- Data toko tetap milik toko: dapat diekspor dan dihapus dari server; PIN, hash,
  salt, dan token tidak boleh masuk berkas backup daring.
- Admin (kasir) tidak dapat mengubah nota yang sudah tersimpan secara langsung;
  perubahan memerlukan persetujuan owner dan tercatat di jejak audit.
- Pemindai barcode hanya alat input; stok dan nominal tetap dihitung backend.
- Database, transaksi, konfigurasi, dan data pengguna tidak dihapus.
- Perhitungan uang tetap di backend dengan `Decimal` dan `ROUND_HALF_UP`;
  Kotlin dan JavaScript tidak menghitung ulang nominal transaksi.
- Tidak membuat `PrinterManager` kedua atau adapter palsu pengganti adapter
  produksi.
- Perubahan tidak dianggap selesai sebelum diuji dan dilaporkan batasannya.
