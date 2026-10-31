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
| 11 | DP, pelunasan, dan piutang di Ringkasan | Kasir + laporan | Tinggi | Rencana |
| 12 | Kirim struk langsung ke WhatsApp pelanggan (tanpa Baileys) | Integrasi pesan | Tinggi | Rencana |
| 13 | Follow-up pasca-servis, servis berkala per pekerjaan, garansi, dan piutang | CRM + pesan | Tinggi | Rencana |

Tahap 2 (kerapatan daftar stok) dan Tahap 6 (label barang di bawah nota) sudah
selesai pada rilis **2.2.2** dan tidak lagi dicantumkan sebagai rencana.

## Urutan pelaksanaan dan ketergantungan

Urutan ini bukan nomor tahap, melainkan urutan pengerjaan yang disarankan agar
setiap tahap dapat dirilis dan diuji sendiri tanpa menunggu tahap besar lain.

| Urutan | Tahap | Bergantung pada | Alasan urutan |
| --- | --- | --- | --- |
| 1 | Tahap 1 — Verifikasi nota | Tidak ada | Perubahan terisolasi di layar kasir; menyentuh alur simpan harian sehingga paling cepat memberi manfaat dan paling mudah diuji ulang |
| 2 | Tahap 11 — DP, pelunasan, dan piutang di Ringkasan | Tahap 1 | Memakai dialog simpan dan pratinjau pembayaran yang sama; kartu piutang langsung memberi manfaat operasional |
| 3 | Tahap 3 — Onboarding dan profil bengkel | Tahap 1 | Mengubah layar awal dan pengelompokan master data; alur kasir sebaiknya stabil lebih dulu |
| 4 | Tahap 5 — Peran owner dan admin | Tahap 3 | Profil bengkel dan PIN pertama menjadi dasar penetapan owner serta hak akses |
| 5 | Tahap 12 — Kirim struk langsung ke WhatsApp | Tahap 5 | Pengaturan dan riwayat kirim hanya untuk owner; tidak memerlukan login WhatsApp |
| 6 | Tahap 13 — Follow-up, servis berkala per pekerjaan, dan garansi | Tahap 12 | Satu item per pelanggan/unit; tombol Follow up hanya menandai, perpindahan kolom manual dan tercatat |
| 7 | Tahap 4 — Akun, langganan, dan database daring | Tahap 3, Tahap 5 | Akun dan langganan melekat pada owner; onboarding sudah punya tempat untuk layar akun |
| 8 | Tahap 7 — Pemindai barcode | Tahap 3, Tahap 5 | Kategori barang mengikuti profil; hak ubah stok hanya milik owner |
| Berjalan | Tahap 8 — Uji perangkat dan printer | Build APK terbaru | Pengujian fisik dapat berjalan paralel dengan tahap kode lain |
| Sebelum rilis publik | Tahap 9 — Token Telegram | Tidak ada | Gate keamanan; harus selesai sebelum aplikasi dipakai pihak lain |
| Berkelanjutan | Tahap 10 — Regresi dan dokumentasi | Semua tahap | Dijalankan setiap kali tahap lain selesai |

Catatan ketergantungan:

- Tahap 4 tidak boleh dimulai sebelum peran owner jelas, agar akun tidak
  otomatis dianggap owner.
- Tahap 7 boleh dikerjakan sebelum Tahap 4; pemindai barcode tidak memerlukan
  akun atau langganan.
- Tahap 11 tidak bergantung pada peran, tetapi begitu Tahap 5 aktif, pelunasan
  dan pembatalan piutang mengikuti hak owner/admin.
- Tahap 12 tidak memakai Baileys atau proses Node. Pengiriman struk memakai
  tautan `wa.me` atau Intent WhatsApp, sehingga tidak perlu runtime tambahan
  di APK dan tidak ada sesi WhatsApp yang harus disimpan.
- Tahap 13 memakai kanal Tahap 12. Tombol **Follow up** dan pengingat membuka
  WhatsApp; tanpa persetujuan atau nomor valid, pengingat tetap tampil di
  aplikasi dan tidak dibukakan WhatsApp.
- Tahap 8 dan Tahap 9 adalah gerbang rilis, bukan fitur. Keduanya dapat
  diselesaikan kapan saja sebelum rilis publik, tetapi tidak boleh dilewati.
- Tahap 10 berjalan di setiap tahap: setiap perubahan UI diuji pada Terang/Gelap
  dan lebar ponsel, dokumentasi diperbarui, lalu build APK diverifikasi.

### Usulan pemetaan rilis

Pemetaan ini usulan awal dan dapat berubah saat tahap dimulai.

| Rilis | Isi |
| --- | --- |
| 2.3.0 | Tahap 1 — verifikasi nota sebelum simpan/cetak |
| 2.4.0 | Tahap 11 — DP, pelunasan, dan piutang di Ringkasan |
| 2.5.0 | Tahap 3 — informasi aplikasi dan profil bengkel |
| 2.6.0 | Tahap 5 — peran owner dan admin |
| 2.7.0 | Tahap 12 — kirim struk ke WhatsApp langsung |
| 2.8.0 | Tahap 13 — follow-up, servis berkala per pekerjaan, dan garansi |
| 3.0.0 | Tahap 4 — akun, langganan, database daring, dan backup otomatis |
| 3.1.0 | Tahap 7 — penambahan stok dengan pemindai barcode |

Setiap rilis wajib menaikkan `versionCode`, membangun APK Debug, menjalankan
pytest pada kedua stack, dan menjalankan unit test Kotlin sebelum di-commit.

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

### 1.1 Rancangan layar pemeriksaan

- Pemeriksaan tampil sebagai dialog di atas layar kasir, bukan halaman baru,
  agar isi keranjang tetap terlihat konteksnya dan tidak ada data yang perlu
  dimuat ulang.
- Isi dialog, dari atas ke bawah:
  1. Judul **Periksa nota sebelum disimpan** dan nama pelanggan + nomor HP.
  2. Unit servis: nopol dan model, atau `[BAWA RADIATOR SAJA]` beserta tipe.
  3. Daftar jasa: deskripsi, qty, harga satuan, dan subtotal per baris.
  4. Daftar sparepart: nama part, qty, harga satuan, dan subtotal per baris.
  5. Ringkasan uang: subtotal jasa, subtotal sparepart, diskon, total nota,
     metode bayar, uang diterima, serta kembalian atau kekurangan.
  6. Status garansi: bergaransi/tidak dan tanggal berakhir bila ada.
- Bagian isi dapat digulir; baris tombol tetap terlihat di bawah layar,
  termasuk pada ponsel.
- Tombol: **Periksa lagi** (kiri, gaya sekunder), **Simpan tanpa cetak**, dan
  **Simpan & cetak struk** (kanan, gaya utama). Urutan tombol mengikuti tombol
  simpan yang sudah ada agar kasir tidak mencari posisi baru.
- Dialog mengikuti mode Terang/Gelap dan tidak memotong teks panjang; nama
  pelanggan, part, atau jasa yang panjang turun ke baris berikutnya.

### 1.2 Sumber data dan konsistensi nominal

- Semua angka diambil dari respons `/api/pos/preview` terbaru, termasuk diskon,
  total, uang diterima, kembalian, dan kekurangan. JavaScript hanya memformat
  tampilan, tidak menjumlahkan ulang.
- Pratinjau diminta saat tombol simpan ditekan, memakai payload yang sama
  dengan yang nantinya dikirim ke `/api/pos/transaction`.
- Selama dialog terbuka, isi keranjang tidak dapat diubah sehingga angka pada
  pemeriksaan tidak bergeser tanpa sepengetahuan kasir.
- Bila pratinjau gagal (server belum siap, sesi berakhir, atau validasi
  backend menolak), dialog tidak dibuka. Kasir melihat pesan yang jelas dan
  keranjang tetap utuh.
- Backend tetap sumber kebenaran terakhir. Bila data berubah karena transaksi
  lain di perangkat yang sama, backend yang menolak atau menyesuaikan, dan
  pesan kesalahan ditampilkan di dialog tanpa menutup keranjang.

### 1.3 Perilaku batal, gagal, dan stok minus

- **Periksa lagi**, tombol tutup, tombol kembali, atau tombol Esc menutup
  dialog tanpa mengirim request: tidak ada nota baru, tidak ada nomor nota
  terpakai, dan tidak ada pergerakan stok.
- Kedua tombol simpan di dalam dialog memakai alur penyimpanan yang sudah ada;
  hanya satu request yang boleh berjalan. Selama request berjalan, kedua
  tombol dinonaktifkan dan menampilkan status proses agar ketukan ganda tidak
  membuat nota ganda.
- Bila backend menolak karena stok kurang, dialog stok minus yang sudah ada
  muncul di atas dialog pemeriksaan. Bila kasir menolak, kembali ke dialog
  pemeriksaan tanpa menyimpan; bila menerima, transaksi disimpan satu kali.
- Bila penyimpanan gagal karena kesalahan lain, dialog tetap terbuka, alasan
  ditampilkan, dan keranjang tidak dibersihkan.
- Setelah berhasil, dialog ditutup dan alur pascasimpan yang berlaku sekarang
  berjalan seperti biasa: pratinjau struk, cetak, atau pesan tanpa printer.
- Tidak ada penyimpanan otomatis dan tidak ada percobaan ulang diam-diam.

### 1.4 Risiko dan penanganan

| Risiko | Penanganan |
| --- | --- |
| Angka pratinjau berbeda dari nota tersimpan | Angka dari backend, keranjang dibekukan selama dialog, dan struk tersimpan tetap acuan akhir |
| Dialog terlalu panjang di ponsel | Isi digulir, ringkasan uang dan tombol tetap terlihat |
| Kasir merasa alur jadi lebih lambat | Satu dialog ringkas, fokus awal pada **Simpan & cetak struk**, dan tidak ada langkah tambahan setelah konfirmasi |
| Ketukan ganda saat simpan | Tombol dinonaktifkan selama request dan request idempotensi yang sudah ada tetap dipakai |
| Pratinjau gagal karena server lambat | Tampilkan status memuat di dialog tombol, bukan pesan error yang menutup alur |

### 1.5 Rencana pengujian

Pengujian manual pada instance terisolasi (database sementara, bukan data
produksi):

- **Kedua jalur simpan** — Simpan tanpa cetak dan Simpan & cetak struk
  sama-sama menampilkan pemeriksaan sebelum request terkirim.
- **Batal** — menutup dialog tidak menambah nota, tidak memakai nomor nota,
  dan tidak mengubah stok.
- **Kecocokan angka** — total, diskon, kembalian, dan status garansi pada
  dialog sama dengan struk yang tersimpan.
- **Metode bayar** — CASH dengan kembalian, CASH kurang bayar, dan TRANSFER.
- **Stok minus** — tolak dan terima konfirmasi; pastikan hanya satu nota
  tersimpan saat menerima.
- **Gagal simpan** — matikan server sesaat sebelum konfirmasi; dialog tetap
  terbuka, keranjang utuh, dan pesan jelas.
- **Ketukan ganda** — tekan tombol simpan berulang cepat; hanya satu nota.
- **Tampilan** — Terang dan Gelap, lebar ponsel 360–430 px, serta nama
  pelanggan/part yang panjang.
- **Regresi** — cetak ulang, void, retur, dan label barang tetap berjalan
  seperti sebelum perubahan.

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
- Ketukan ganda pada tombol simpan tetap menghasilkan satu nota.
- Bila pratinjau gagal, dialog tidak dibuka dan keranjang tidak hilang.
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

## Tahap 11 — DP, pelunasan, dan piutang pelanggan

**Masalah.** Nota hanya mengenal pembayaran `CASH` dan `TRANSFER`
(`database/models.py:141`). Uang tunai kurang dari total ditolak
(`services/pricing_service.py:61`), sedangkan transfer selalu dianggap pas.
Akibatnya nota servis yang dikerjakan beberapa hari, atau yang part-nya dipesan
dulu, tidak dapat dicatat dengan DP; kasir harus menagih penuh atau menunda
nota. Tidak ada sisa bayar, jatuh tempo, atau buku piutang.

**Tujuan.** Menambahkan DP, pelunasan bertahap, jatuh tempo, daftar piutang, dan
kartu **Piutang** di Ringkasan tanpa mengubah total nota, nomor nota, atau
perhitungan uang yang sudah ada.

### 11.1 Perilaku yang diusulkan

1. Saat menyimpan nota, kasir memilih **Lunas** (perilaku sekarang, default)
   atau **DP / Tempo**.
2. Pada DP, kasir mengisi uang muka dan tanggal jatuh tempo (bawaan 7 hari,
   dapat diubah di Pengaturan). Sisa = total nota − DP.
3. **DP tidak menunda struk.** Saat nota DP disimpan dengan **Simpan & cetak
   struk**, struk tetap keluar saat itu juga, bukan ditahan sampai lunas.
   Struk DP menampilkan total, DP yang dibayar, sisa bayar, status
   **BELUM LUNAS**, dan tanggal jatuh tempo. **Simpan tanpa cetak** tetap
   menyediakan cetak dari dialog struk. Pengiriman WhatsApp Tahap 12 memakai
   struk DP yang sama.
4. Pelunasan dapat dicatat berkali-kali dari detail nota atau daftar piutang:
   nominal, metode (tunai/transfer), tanggal, operator, dan catatan. Setiap
   pencatatan pelunasan dapat dicetak sebagai **struk pelunasan** (nominal,
   sisa baru, metode), tanpa membuat nota atau nomor nota baru.
5. Bila sisa menjadi nol, status berubah menjadi **LUNAS** dan aplikasi
   menawarkan **Cetak struk lunas** terpisah yang menampilkan total, seluruh
   pembayaran, dan sisa `0`. Kelebihan bayar ditolak, bukan disimpan sebagai
   saldo diam-diam.
6. Daftar piutang menampilkan pelanggan, nomor nota, total, sudah dibayar,
   sisa, jatuh tempo, dan umur piutang (0–7, 8–30, 31–60, lebih dari 60 hari).
7. Kartu **Piutang** di Ringkasan menampilkan jumlah pelanggan, jumlah nota
   belum lunas, dan total sisa. Kartu dapat diklik untuk membuka daftar yang
   dikelompokkan per pelanggan dengan rincian nota di dalamnya.
8. Setiap item pelanggan di daftar belum lunas punya tombol **Follow up** dan
   **Catat pelunasan**. Follow up (Tahap 13) hanya menandai **Sudah follow up**
   dan tidak mengubah status bayar; nota tetap **BELUM LUNAS** dan tetap tampil
   di Ringkasan.
9. Saat pelunasan membuat sisa nol, status berubah menjadi **LUNAS** dan
   aplikasi menawarkan **Cetak struk lunas** lewat jalur cetak yang ada. Nota
   baru hilang dari kartu dan daftar piutang setelah LUNAS dicatat; pelunasan
   sebagian tetap tampil dengan sisa yang diperbarui.
10. Void atau retur pada nota ber-DP mengembalikan DP, membatalkan sisa piutang,
    dan mencatat pengembalian. Tidak boleh ada saldo negatif; nota itu keluar
    dari Ringkasan lewat jalur void, bukan dihapus diam-diam.
11. Nota lama yang sudah lunas tidak diubah. Migrasi menandainya **LUNAS**
    dengan satu catatan pembayaran sebesar nilai yang sudah dibayar.

### 11.2 Data dan perhitungan

- Tabel baru `service_payments` menyimpan setiap pembayaran (nota, metode,
  nominal, waktu, operator, catatan, dan `request_id` unik untuk idempotensi).
- Status bayar dan tanggal jatuh tempo disimpan pada nota atau diturunkan dari
  catatan pembayaran; keputusan bentuk akhirnya diambil saat implementasi.
- Total nota tetap dihitung backend dari jasa + sparepart − diskon. DP tidak
  mengubah total, hanya cara pembayaran.
- Laporan harus memisahkan **nilai nota** (dasar laporan penjualan yang ada)
  dari **uang diterima** (dasar laporan kas). Ini mencegah pendapatan dihitung
  dua kali: sekali saat nota dibuat dan sekali saat pelunasan.
- Angka kartu **Piutang** di Ringkasan (jumlah pelanggan, jumlah nota, dan
  total sisa) dihitung backend memakai query yang sama dengan daftar belum
  lunas. JavaScript hanya menampilkan; tidak ada penjumlahan ulang.
- Status follow-up disimpan terpisah dari status bayar. Nota berstatus
  **Sudah follow up** tetap **BELUM LUNAS** dan tetap dihitung di Ringkasan
  sampai sisa nol atau void/retur.
- **Struk DP** dan **struk lunas** disusun dari `build_receipt_payload` yang
  sama dengan struk biasa. Struk DP keluar saat nota disimpan dan memuat
  total, DP, sisa, status **BELUM LUNAS**, serta jatuh tempo. Struk lunas
  memuat total, seluruh pembayaran, sisa `0`, metode pelunasan terakhir, dan
  waktu pelunasan. Tidak ada perhitungan uang baru di JavaScript atau Kotlin.
- Semua nominal memakai `Decimal` + `ROUND_HALF_UP` di backend. JS hanya
  menampilkan; tidak ada penjumlahan ulang di frontend.

### 11.3 API dan tampilan

- Permintaan transaksi mendapat field opsional untuk DP, jatuh tempo, dan
  penanda boleh tempo. Nota tanpa field tersebut berperilaku seperti sekarang.
- Respons transaksi DP tetap menyertakan `receipt` seperti sekarang, sehingga
  **Simpan & cetak struk** mencetak struk DP saat itu juga. Tidak ada struk
  yang ditahan sampai pelunasan.
- Endpoint baru: daftar piutang, rincian pembayaran nota, pencatatan
  pelunasan, dan penandaan follow-up. Semua memakai aturan peran Tahap 5
  setelah tahap itu aktif.
- Ringkasan harian menambah `piutang_count`, `piutang_customers`, dan
  `piutang_total` dari query yang sama dengan daftar piutang. Klik kartu
  membuka daftar per pelanggan dengan filter umur dan jatuh tempo.
- Respons pencatatan pelunasan menyertakan struk lunas. Tombol **Cetak struk
  lunas** memakai `PrinterManager` yang sudah ada; tidak ada jalur cetak baru.
- Dialog pemeriksaan Tahap 1 menampilkan DP, sisa, dan jatuh tempo sebelum
  nota disimpan.
- Detail pelanggan menampilkan piutang berjalan; laporan menampilkan umur
  piutang dan uang diterima per metode.
- Nota yang sudah punya pembayaran tidak dapat dihapus; koreksi hanya lewat
  void/retur resmi dan tercatat.

### 11.4 Batasan

- Tidak mengubah total, diskon, nomor nota, atau data nota lama.
- Tidak mengubah PIN, hash, salt, lockout, atau alur reset.
- Tidak ada perhitungan uang di JavaScript atau Kotlin.
- Tidak membuat `PrinterManager` kedua; struk tetap dicetak lewat jalur yang
  sudah ada.
- Pembayaran tidak boleh dihapus diam-diam; pembatalan memakai void/refund
  dengan alasan dan audit.
- Follow-up bukan pembayaran. Menandai **Sudah follow up** tidak boleh
  mengurangi sisa, mengubah status LUNAS, atau menghilangkan nota dari
  Ringkasan.
- Nota hanya keluar dari kartu/daftar piutang bila LUNAS tercatat (sisa nol)
  atau lewat void/retur resmi. Pelunasan sebagian tetap tampil.

### 11.5 Rencana pengujian

- Nota lunas biasa tetap berperilaku sama.
- DP dengan **Simpan & cetak struk**: struk tetap keluar saat nota disimpan
  dan memuat total, DP, sisa, status **BELUM LUNAS**, serta jatuh tempo.
  Cetak gagal tidak menghalangi nota tersimpan.
- DP dengan **Simpan tanpa cetak**: struk tidak tercetak otomatis, tetapi
  dialog struk menyediakan cetak dan teks WhatsApp versi DP.
- DP lalu satu pelunasan; DP lalu beberapa pelunasan; pelunasan tepat di sisa.
- Setiap pelunasan dapat dicetak sebagai struk pelunasan; pelunasan penuh
  menghasilkan struk lunas dengan sisa `0`.
- Kelebihan bayar ditolak dan tidak mengubah sisa.
- Void/retur pada nota ber-DP: pengembalian, pembatalan sisa, dan audit benar.
- Dua pelunasan bersamaan tidak membuat saldo ganda (uji konkurensi dan
  idempotensi).
- Laporan nilai nota dan uang diterima tidak menghitung dobel.
- Kartu **Piutang** di Ringkasan: jumlah pelanggan, jumlah nota, dan total
  sisa sama dengan daftar belum lunas; klik kartu membuka daftar yang sama.
  Satu pelanggan dengan beberapa nota tampil sebagai satu item dengan rincian
  nota.
- Follow up tidak mengubah sisa atau status bayar; nota tetap tampil di
  Ringkasan dengan tanda **Sudah follow up**.
- Pelunasan sebagian memperbarui sisa dan tetap tampil; pelunasan penuh
  mengubah status LUNAS, menawarkan struk lunas, lalu nota hilang dari
  Ringkasan setelah LUNAS dicatat.
- Void/retur ber-DP mengeluarkan nota lewat jalur void tanpa saldo negatif.
- Umur piutang, jatuh tempo, dan struk cocok dengan data backend.
- Tampilan berfungsi di Terang/Gelap dan lebar ponsel.

### Kriteria selesai

- Nota dapat disimpan dengan DP dan **tetap mencetak struk DP saat disimpan**
  yang menampilkan total, DP, sisa, status BELUM LUNAS, dan jatuh tempo.
- Pelunasan bertahap mengubah status menjadi LUNAS saat sisa nol.
- Ringkasan menampilkan kartu **Piutang** yang akurat; klik membuka daftar
  nota belum lunas.
- Follow up hanya menandai **Sudah follow up**; nota tetap belum lunas dan
  tetap tampil sampai dibayar.
- Pelunasan penuh mencetak struk lunas lewat jalur cetak yang ada dan baru
  menghilangkan nota dari Ringkasan.
- Daftar piutang dan umur piutang akurat serta dapat difilter.
- Void/retur ber-DP tidak meninggalkan saldo negatif.
- Nota lama dan laporan yang sudah ada tidak berubah artinya.
- Tidak ada perbedaan angka antara dialog, struk, laporan, dan Ringkasan.

## Tahap 12 — Kirim struk langsung ke WhatsApp pelanggan (tanpa Baileys)

**Masalah.** Struk hanya dicetak atau disimpan sebagai pratinjau. Tidak ada
pengiriman digital ke pelanggan, dan “WhatsApp” di Pengaturan hanya nomor
kontak bengkel (`frontend/index.html:704`), bukan integrasi pesan.

**Tujuan.** Setelah tombol **Simpan & cetak struk** berhasil, aplikasi mencetak
struk seperti sekarang lalu membuka WhatsApp pelanggan dengan teks struk yang
sudah terisi. Kasir hanya menekan kirim di WhatsApp. Tidak ada login WhatsApp,
QR, sesi, atau bridge Node di dalam aplikasi.

### 12.1 Keputusan: Baileys dihapus

Rencana sebelumnya memakai Baileys seperti repo
`ptbanditindo/website-bengkel-dashboard`. Rencana itu dibatalkan karena:

- Baileys adalah pustaka tidak resmi dan berjalan sebagai proses Node.js.
  APK memakai Chaquopy (Python 3.10) tanpa runtime Node, sehingga bridge tidak
  dapat berjalan di dalam APK apa adanya.
- Otomasi pesan latar belakang dan sesi tidak resmi berisiko melanggar
  kebijakan Play Store dan ketentuan WhatsApp, termasuk nomor dibatasi.
- Nomor bengkel harus tetap aman; tidak ada kredensial WhatsApp yang perlu
  disimpan, dienkripsi, atau dipulihkan.

Karena itu pengiriman memakai jalur resmi dan sederhana:

| Cara | Perilaku | Kapan dipakai |
| --- | --- | --- |
| Tautan `wa.me` | Membuka WhatsApp dengan nomor dan teks terisi | Versi browser/desktop dan cadangan WebView |
| Intent Android `whatsapp://send` | Membuka aplikasi WhatsApp langsung dari APK | APK, lewat `NativeBridge` |
| WhatsApp Cloud API resmi | Backend mengirim tanpa membuka WhatsApp | Opsional, ditunda; butuh akun bisnis, token, internet, verifikasi, dan biaya Meta |

Tahap ini hanya mengerjakan dua baris pertama. Pengiriman selalu dikonfirmasi
manusia di WhatsApp, sehingga status yang dicatat adalah **dibuka** atau
**dibatalkan**, bukan **terkirim**.

### 12.2 Alur simpan, cetak, lalu WhatsApp

1. **Simpan & cetak struk** menyimpan nota lewat alur yang ada — termasuk
   nota **DP** — lalu mencetak struk saat itu juga memakai `PrinterManager`
   yang sudah ada. Struk DP tidak ditunda sampai pelunasan; jalur cetak tidak
   diubah.
2. Setelah percobaan cetak selesai — berhasil, gagal, atau belum ada printer —
   aplikasi membuka WhatsApp bila sakelar **Buka WhatsApp setelah cetak**
   aktif, pelanggan punya nomor valid, dan pelanggan menyetujui pesan.
3. Kegagalan cetak tidak membatalkan nota dan tidak menghalangi WhatsApp;
   kegagalan membuka WhatsApp tidak memengaruhi nota atau cetak. Setiap
   kegagalan diberi pesan yang jelas, bukan diam.
4. **Simpan tanpa cetak** tidak membuka WhatsApp otomatis. Dialog struk punya
   tombol **Kirim ke WhatsApp** untuk mengirim setelah kasir memeriksa nota.
5. Cetak ulang, void, dan retur memakai struk tersimpan; tombol WhatsApp di
   dialog struk tetap tersedia dan memakai teks dari backend.
6. Saat pelunasan penuh dicatat, **Cetak struk lunas** memakai jalur yang sama
   dan dialognya juga punya tombol **Kirim ke WhatsApp** dengan teks struk
   lunas. Struk DP yang sudah tercetak tidak diubah.
7. Pelanggan tanpa nomor atau tanpa persetujuan: tombol dinonaktifkan dengan
   alasan singkat, dan kasir diarahkan mengisi nomor di data pelanggan.
8. Bila WhatsApp tidak terpasang atau pengguna menutup aplikasi WhatsApp,
   catatan disimpan sebagai **dibatalkan**; kasir dapat mencoba lagi atau
   mencetak seperti biasa.

### 12.3 Isi pesan dan normalisasi nomor

- Backend mengirim `wa_text` di dalam payload struk yang sama
  (`ReceiptOut.struk_58`/`struk_80` sudah ada). Teks disusun dari baris struk
  yang sama dengan hasil cetak, sehingga nomor nota, item, dan total identik.
- Nota DP mengirim teks versi DP: total, DP, sisa, status **BELUM LUNAS**, dan
  jatuh tempo. Setelah lunas, teks yang dikirim adalah versi **struk lunas**
  dengan sisa `0`, bukan struk DP lama.
- Tidak ada perhitungan ulang nominal di JavaScript atau Kotlin. Format ribuan
  mengikuti struk; teks memakai lebar sekitar 32 karakter agar terbaca di
  WhatsApp dan tidak memakai markdown.
- Isi bawaan: nama bengkel, nomor nota, pelanggan/unit, ringkas jasa dan
  sparepart, total, masa garansi, dan ucapan terima kasih. Template dapat
  diubah owner, tetapi field angka tetap berasal dari backend.
- Nomor dinormalisasi: spasi, tanda hubung, dan tanda kurung dibuang; `08…`,
  `8…`, dan `+62…` menjadi `628…`; panjang divalidasi sebelum tombol aktif.
- Teks di-URL-encode saat membuka tautan. Tidak ada tautan pihak ketiga atau
  data internal di pesan.

### 12.4 Kejujuran status, persetujuan, dan kepatuhan

- Aplikasi tidak mengirim pesan sendiri dan tidak berjalan di latar belakang.
  Tidak ada pesan massal, percobaan ulang otomatis, atau pengiriman ke nomor
  tanpa persetujuan.
- Persetujuan dicatat per pelanggan (sakelar di detail pelanggan). Pelanggan
  yang menolak tetap dapat mencetak struk; tombol WhatsApp dinonaktifkan.
- Setiap percobaan dicatat di `wa_message_log`: nota, nomor tersamar, jenis
  pesan, status (`dibuka`, `dibatalkan`, `tidak tersedia`), operator, waktu,
  dan `request_id` unik. Status **terkirim** hanya boleh muncul bila kelak
  memakai Cloud API yang memberi laporan pengiriman.
- Tidak meminta izin SMS, akses notifikasi, atau aksesibilitas. Aplikasi hanya
  membuka aplikasi lain lewat Intent/tautan.
- Data pelanggan tetap di perangkat. Kepatuhan Play Store: kebijakan privasi
  dan Data Safety menyatakan nomor telepon dipakai untuk mencetak dan membuka
  WhatsApp, bukan diunggah ke server pihak ketiga.

### 12.5 Data, API, dan tampilan

- `ReceiptOut` mendapat field opsional `wa_text`; pembuatannya ada di
  `services/receipt_service.py` dan tidak menyentuh perhitungan uang.
- Endpoint kecil untuk mencatat percobaan buka WhatsApp dan membaca riwayat
  kirim per nota. Setelah Tahap 5 aktif, pengaturan hanya untuk owner;
  pencatatan boleh dilakukan kasir.
- `NativeBridge` mendapat satu metode `openWhatsApp(nomor, teks)` yang memakai
  pola Intent yang sudah ada di `shareBackupNow`
  (`android/app/src/main/java/com/bengkelpos/radiator/nativebridge/NativeBridge.kt:264`).
  Versi browser memakai `window.open` ke `wa.me`. Tidak ada `PrinterManager`
  kedua.
- Pengaturan → WhatsApp: sakelar buka setelah cetak (bawaan mati), template,
  pratinjau, dan tombol uji ke nomor sendiri.
- Dialog struk: **Kirim ke WhatsApp** dan **Salin teks struk**. Detail nota
  menampilkan status percobaan kirim. Tampilan diuji pada Terang/Gelap dan
  lebar ponsel.

### 12.6 Batasan

- Tidak memakai Baileys, bridge Node, QR, pairing, sesi, atau bot balasan.
- Tidak mengubah perhitungan uang, nomor nota, skema transaksi lama, atau label.
- Tidak membuat `PrinterManager` kedua dan tidak mengubah urutan cetak yang ada.
- Aplikasi tetap dapat dipakai tanpa WhatsApp dan tanpa internet; cetak tetap
  menjadi cadangan utama.
- Tidak ada kredensial WhatsApp di repository, dokumentasi, log, atau backup.

### 12.7 Rencana pengujian

- Nota lunas biasa: simpan, cetak, lalu WhatsApp terbuka dengan teks yang sama
  dengan struk; angka dan nomor nota identik.
- Cetak gagal atau belum ada printer: nota tetap tersimpan, WhatsApp tetap
  dapat dibuka, pesan kegagalan jelas.
- Nota DP dengan **Simpan & cetak struk**: struk DP keluar saat disimpan dan
  WhatsApp memakai teks versi DP (total, DP, sisa, BELUM LUNAS, jatuh tempo).
  Setelah pelunasan penuh, struk lunas dan teksnya memakai versi sisa `0`.
- Simpan tanpa cetak: WhatsApp tidak terbuka otomatis; tombol di dialog bekerja.
- Nomor `08…`, `+62…`, dan nomor tidak valid; tombol nonaktif saat tidak valid.
- Pelanggan menolak atau tanpa nomor: tidak ada pembukaan WhatsApp.
- WhatsApp tidak terpasang atau dibatalkan: status tercatat jujur, bukan
  "terkirim".
- Cetak ulang, void, dan struk lunas memakai teks struk yang benar.
- Tampilan Terang/Gelap dan lebar ponsel.

### Kriteria selesai

- Struk tercetak seperti sekarang — termasuk struk DP saat nota DP disimpan —
  dan WhatsApp pelanggan terbuka dengan teks struk yang sama.
- Struk lunas terpisah tercetak saat pelunasan penuh, dengan sisa `0`.
- Angka, nomor nota, dan label di WhatsApp sama dengan struk cetak.
- Kegagalan cetak atau WhatsApp tidak menghalangi transaksi tersimpan.
- Status kirim jujur (dibuka/dibatalkan), tanpa klaim terkirim.
- Tidak ada login WhatsApp, sesi, Node, atau kredensial di aplikasi dan backup.
- Pelanggan tanpa persetujuan atau nomor valid tidak dibukakan WhatsApp.

## Tahap 13 — Follow-up pasca-servis, servis berkala, garansi, dan piutang

**Masalah.** Setelah servis selesai, bengkel tidak punya daftar pelanggan yang
perlu ditanya kabarnya, servis berkala radiator terlewat, dan pengingat
garansi/piutang mengandalkan ingatan. Daftar per nota juga membuat pelanggan
dengan beberapa unit muncul berkali-kali.

**Tujuan.** Menampilkan satu daftar follow-up per pelanggan/unit yang
menggabungkan prospek pasca-servis, servis berkala per jenis pekerjaan
(misalnya cuci/cek radiator 3/6 bulan atau ganti oli 6 bulan), garansi hampir
habis, dan piutang. Setiap item punya penanggung jawab,
tombol **Follow up** yang membuka WhatsApp, badge **Sudah follow up**, dan
tombol pindah kolom manual. Semua perpindahan dan penghilangan pengingat
tercatat sebagai riwayat (database), bukan dihapus. Tidak ada pengiriman
otomatis.

### 13.1 Prospek follow-up di Ringkasan

- Bagian **Prospek follow-up** di daftar **Tugas follow-up hari ini** pada
  halaman Ringkasan, di bawah kartu statistik dan di atas transaksi terakhir.
- Dasar perhitungan: nota berstatus NORMAL (bukan VOID/retur penuh), servis
  terakhir per unit/pelanggan, umur servis ≥ X hari, nomor valid, dan
  persetujuan pelanggan.
- X dapat diatur (bawaan 7 hari; pilihan 3/7/14/30) di Pengaturan. Cooldown
  bawaan 7 hari sejak follow-up terakhir agar pelanggan tidak dipesan berulang.
- **Satu item per pelanggan/unit, bukan per nota.** Jika pelanggan punya tiga
  unit, baris digabung menjadi satu item pelanggan (unit disebutkan di
  rincian) dan memakai nota NORMAL terbaru sebagai dasar. Tujuan: tidak ada
  tiga pesan follow-up untuk orang yang sama.
- Baris menampilkan pelanggan, nomor, semua unit/radiator, tanggal servis
  terakhir dan umur hari, ringkas pekerjaan dari nota terakhir, status
  garansi, penanggung jawab, dan tombol **Follow up**.
- Urutan: servis paling lama lebih dulu, lalu item yang belum punya
  penanggung jawab. Batas tampilan misalnya 10 baris dengan tautan "Lihat
  semua".
- Tombol **Follow up** membuka WhatsApp dengan pesan yang disesuaikan riwayat:
  menyebut unit, tanggal, pekerjaan yang dilakukan, dan menanyakan apakah
  masih ada kendala. Bila garansi masih aktif, pesan menyebut garansi; bila
  garansi akan habis dalam ambang 13.2, pesan juga memberi tahu tanggal
  berakhir, sisa hari, dan ajakan cek ulang. Bila servis berupa cuci radiator,
  pesan menanyakan kebocoran atau suhu mesin.
- Teks pesan disusun backend dari data nota yang sama dengan struk; JavaScript
  dan Kotlin hanya membuka WhatsApp, tanpa menyusun ulang angka atau tanggal.
- Setelah tombol ditekan, item **tidak dihapus dan tidak dipindah otomatis**.
  Item diberi badge **Sudah follow up** dan tetap di daftar sampai kasir
  memindahkannya ke kolom lain secara manual (13.6).

### 13.2 Kartu Garansi akan habis di Ringkasan

- Kartu statistik baru **Garansi akan habis** di samping **Garansi aktif** pada
  halaman Ringkasan. Angka dihitung backend dari nota yang memenuhi semua
  syarat: status NORMAL (bukan VOID), `bergaransi` benar, `garansi_sampai`
  jatuh dalam 7 hari ke depan (hari ini sampai H+7), belum lewat, dan belum
  diklaim (`status_klaim` bukan "Sudah claim").
- Ambang bawaan 7 hari, dapat diubah di Pengaturan (7/14/30). Perhitungan
  memakai `garansi_sampai` dan aturan `warranty_service.is_active` yang sudah
  ada; tidak ada perhitungan tanggal di JavaScript.
- Kartu dapat diklik seperti kartu **Garansi aktif** dan membuka daftar nota
  yang sama (filter `warranty_expiring`) sehingga angka kartu dan isi daftar
  selalu cocok.
- Setiap baris menampilkan pelanggan, nomor HP, unit/radiator, tanggal servis,
  ringkas pekerjaan dari nota, tanggal garansi berakhir, sisa hari, dan tombol
  **Follow up**.
- Tombol **Follow up** langsung membuka WhatsApp dengan pesan yang
  menggabungkan tiga hal:
  1. pertanyaan kondisi barang/mesin sesuai data servis — misalnya radiator
     (kebocoran, suhu mesin, air berkurang), servis mesin (suara, tenaga,
     getaran), atau penggantian sparepart (kondisi part yang dipasang);
  2. pemberitahuan bahwa garansi akan berakhir pada tanggal tersebut dan sisa
     harinya;
  3. ajakan memeriksa ulang ke bengkel sebelum garansi habis bila masih ada
     kendala.
- Contoh isi pesan: "Halo Bapak/Ibu {nama}, kami dari {bengkel}. Garansi
  servis {unit} tanggal {tanggal_servis} akan berakhir pada
  {tanggal_garansi} ({sisa} hari lagi). Bagaimana kondisi {barang} setelah
  {pekerjaan}? Bila masih ada {gejala}, silakan cek ulang ke bengkel sebelum
  masa garansi berakhir."
- Setelah tombol ditekan, percobaan dicatat di `wa_message_log` dan item
  diberi badge **Sudah follow up**, tetapi tetap di daftar. Perpindahan ke
  kolom lain dilakukan manual (13.6).
- **Hilangkan pengingat langsung.** Owner/kasir dapat menekan **Hilangkan
  pengingat** pada baris garansi H-xx tanpa harus follow up. Item masuk kolom
  **Arsip** dengan alasan dan waktu, hilang dari Ringkasan/daftar tugas, tetapi
  riwayatnya tetap tersimpan dan dapat dibuka kembali.
- Satu item per pelanggan/unit; pelanggan dengan beberapa unit memakai nota
  terbaru dan unit terdekat jatuh tempo sebagai dasar, tanpa baris ganda.
- Nota yang sudah kedaluwarsa tidak dihitung di kartu **Garansi akan habis**,
  tetapi tetap ada di riwayat dan daftar garansi. Nota VOID dan yang sudah
  diklaim tidak dihitung.

### 13.3 Kartu Piutang di Ringkasan dan follow-up tagihan

- Kartu statistik **Piutang** di halaman Ringkasan menampilkan jumlah nota
  belum lunas dan total sisa. Angka dihitung backend dari query yang sama
  dengan daftar piutang Tahap 11; JavaScript hanya menampilkan.
- Kartu dapat diklik dan membuka daftar riwayat yang belum lunas, **digabung
  per pelanggan** agar satu pelanggan dengan beberapa nota tidak muncul
  berkali-kali. Header menampilkan jumlah pelanggan dan jumlah nota; rincian
  per nota (total, sudah dibayar, sisa, jatuh tempo, umur) bisa dibuka.
- Tombol **Follow up** per pelanggan membuka WhatsApp dengan pesan yang
  menyatakan:
  1. pekerjaan sudah selesai,
  2. pelanggan diminta datang ke bengkel untuk mengambil barang/unit,
  3. total kekurangan dari semua nota yang belum lunas, dihitung backend,
  4. tanggal jatuh tempo terdekat bila ada.
- Contoh isi pesan: "Halo Bapak/Ibu {nama}, servis {unit} dengan nota
  {no_nota} sudah selesai. Silakan datang ke {bengkel} untuk mengambil
  barangnya. Kekurangan pembayaran Rp {sisa} dari total Rp {total}, jatuh
  tempo {tanggal}. Terima kasih."
- **Follow up bukan pembayaran.** Setelah tombol ditekan, percobaan dicatat di
  `wa_message_log`, item diberi badge **Sudah follow up** beserta waktu, dan
  sisa pembayaran tidak berubah. Nota tetap **BELUM LUNAS**, tetap dihitung di
  kartu **Piutang**, dan tetap tampil di Ringkasan.
- Item tidak disembunyikan setelah follow-up dan **tidak boleh dihilangkan
  manual**; satu-satunya jalan keluar adalah pelunasan penuh (LUNAS) atau
  void/retur resmi. Tombol follow-up hanya dinonaktifkan selama cooldown 7
  hari.
- Pelunasan sebagian memperbarui sisa dan umur piutang; item dan kartu tetap
  tampil dengan angka baru.
- Pelunasan penuh mengubah status menjadi **LUNAS** dan menawarkan **Cetak
  struk lunas** lewat `PrinterManager` yang sudah ada. Item baru hilang dari
  kartu dan daftar piutang setelah LUNAS tercatat; void/retur mengeluarkannya
  lewat jalur resmi. Tidak ada penghapusan diam-diam.
- Pelanggan tanpa nomor valid atau tanpa persetujuan tidak dapat di-follow up;
  item tetap tampil di Ringkasan dan kasir tetap dapat mencatat pelunasan.

### 13.4 Servis berkala per jenis pekerjaan (mis. ganti oli 6 bulan)

**Fakta acuan.** `HargaJasa` (`database/models.py:92-103`) belum punya interval
servis, dan `ServiceJob` (`database/models.py:194-210`) hanya menyimpan
deskripsi, jumlah, dan harga. Tabel **Jasa** di UI baru punya kolom Nama,
Harga, dan Aksi (`frontend/js/app.js:4019-4048`), sedangkan tabel **Stok**
sudah punya kolom jumlah. Jadi interval ditambahkan sebagai kolom baru di
master jasa, lalu disalin ke baris nota saat transaksi.

- **Kolom Servis berkala di master Jasa.** Tabel **Jasa** mendapat kolom
  **Servis berkala** sejajar dengan kolom harga, seperti kolom jumlah pada
  tabel Stok. Isinya interval bulan: **Nonaktif** (0), 1, 2, 3, 6, 12, atau
  nilai bebas. Nilai disimpan di `harga_jasa.interval_servis_bulan` dan dapat
  diubah kapan saja lewat modal Tambah/Edit jasa.
- **Contoh.** "Ganti oli" diisi 6 bulan, "Cuci radiator" 3 atau 6 bulan,
  "Servis besar" 12 bulan. Jasa yang tidak perlu diingatkan dibiarkan
  **Nonaktif** dan tidak pernah muncul di daftar servis berkala.
- **Baris jasa di POS.** Saat kasir memilih tarif jasa berinterval, baris jasa
  menampilkan **Servis berkala: 6 bulan** dan nilainya boleh diubah untuk nota
  itu saja. Yang tersimpan di nota adalah nilai saat nota disimpan, bukan nilai
  master terbaru.
- **Snapshot di nota.** `service_jobs` menyimpan `interval_servis_bulan`
  sebagai salinan saat nota disimpan. Mengubah master jasa sesudahnya hanya
  memengaruhi nota baru; jadwal nota lama tidak berubah.
- **Dasar daftar adalah nota.** Daftar servis berkala membaca nota NORMAL
  (bukan VOID/retur penuh) dan menampilkan **pekerjaan yang benar-benar
  dikerjakan** — nama jasa dari baris nota — beserta tanggal servis, interval,
  dan tanggal servis berikutnya. Jadi daftar menjawab "jasa apa yang terakhir
  dikerjakan", bukan sekadar "unit pernah servis".
- **Jatuh tempo.** Tanggal servis + interval bulan, dihitung backend dengan
  kalender bulan (tanggal 31 mengikuti hari terakhir bulan tujuan); JavaScript
  hanya menampilkan.
- **Beberapa jasa berinterval dalam satu nota.** Item per pelanggan/unit
  memakai jatuh tempo paling dekat; rincian menampilkan semua jasa beserta
  interval dan jatuh tempo masing-masing.
- **Siklus baru.** Servis berikutnya yang lebih awal menutup siklus lama dan
  membuat siklus baru dari nota terbaru untuk jasa yang sama; tidak ada item
  ganda.
- **Kartu Ringkasan.** Kartu **Servis berkala** menampilkan jumlah item yang
  masuk ambang H-14 atau sudah jatuh tempo; klik kartu membuka daftar yang
  sama. Ambang H-14 dapat diatur.
- **Urutan dan tampilan.** Item muncul mulai H-14 (dapat diatur) sampai jatuh
  tempo dan tetap terlihat setelah lewat; urutannya jatuh tempo terdekat.
  Satu item per pelanggan/unit.
- **Follow up.** Tombol **Follow up** membuka WhatsApp yang menyebut jasa
  terakhir (mis. "ganti oli"), tanggal servis, dan anjuran servis berikutnya;
  tanpa angka uang.
- **Hilangkan pengingat langsung.** Tombol **Hilangkan pengingat** mengarsipkan
  siklus ini dengan alasan (sudah servis di tempat lain, tidak ingin
  diingatkan, lainnya). Item hilang dari Ringkasan/tugas dan tidak muncul lagi
  sampai ada servis baru; riwayatnya tetap tersimpan.
- **Tanpa perubahan uang.** Interval tidak memengaruhi total, stok, nomor
  nota, atau perhitungan apa pun.

### 13.5 Daftar tugas follow-up hari ini dan penanggung jawab

- Halaman/daftar **Tugas follow-up** di Ringkasan atau tab sendiri, berisi
  item yang jatuh tempo hari ini dan terlambat dari semua jenis (prospek,
  servis berkala, garansi, piutang).
- Setiap item punya **penanggung jawab** dari operator aktif (identitas audit
  yang sudah ada); setelah Tahap 5 memakai akun owner/admin.
- Tombol **Ambil tugas** menetapkan penanggung jawab dan waktu, lalu item
  menampilkan "sedang ditangani oleh X" agar operator lain tidak menekan
  follow-up yang sama.
- Filter: hari ini, terlambat, belum ditugaskan, milik saya, dan semua. Urutan
  jatuh tempo lalu pelanggan.
- Penanggung jawab dapat dilepas atau diganti dengan alasan dan tercatat.
- Item yang selesai/diarsipkan hilang dari tugas hari ini, tetapi tetap di
  riwayat pelanggan.

### 13.6 Badge, kolom, dan riwayat status follow-up

- Setelah Follow up ditekan, item hanya mendapat badge **Sudah follow up** dan
  **tidak otomatis pindah kolom**.
- Kolom status: **Baru** (belum di-follow up), **Sudah follow up**,
  **Janji bayar** (khusus piutang, wajib tanggal), **Masih kendala**,
  **Selesai**, dan **Arsip**.
- Tombol **Pindahkan ke …** tersedia pada setiap item; perpindahan hanya
  manual, dengan alasan opsional dan operator.
- Aturan:
  - Piutang tidak boleh dipindah ke **Selesai** lewat tombol; LUNAS hanya dari
    pelunasan penuh. **Janji bayar** memunculkan pengingat pada tanggal janji.
  - Garansi dan servis berkala boleh langsung **Selesai** atau **Arsip**
    (hilangkan pengingat) tanpa follow up.
  - **Masih kendala** membuat tugas tindak lanjut (misalnya klaim garansi atau
    servis ulang) dan tetap tampil.
  - **Arsip** menyembunyikan item dari Ringkasan/tugas, bukan menghapus data.
- Setiap perpindahan dicatat di `followup_events`: item, dari kolom, ke kolom,
  alasan, operator, dan waktu. Ini membentuk database riwayat yang dapat
  dilihat per pelanggan.
- Kolom ditampilkan sebagai tab/papan pada halaman **Follow-up**; Ringkasan
  tetap ringkas dan hanya menampilkan jumlah serta daftar tugas hari ini.
- Badge dan kolom konsisten di Ringkasan, daftar tugas, detail pelanggan, dan
  riwayat servis.

### 13.7 Pengingat garansi dan piutang jatuh tempo

- **Garansi berakhir** — pengingat H-7, H-3, dan H-1 memakai query yang sama
  dengan kartu 13.2. Kartu Ringkasan menampilkan hitungannya, daftar
  **Pengingat** menampilkan rinciannya.
- **Piutang jatuh tempo** — H-3, hari jatuh tempo, dan H+7 memakai data
  Tahap 11 dan query kartu 13.3.
- Keduanya tampil di daftar **Pengingat** dengan tombol WhatsApp yang sama.
  Tanpa persetujuan atau nomor valid, pengingat tetap tampil di aplikasi.
- Promosi, ulang tahun, dan kampanye massal tidak termasuk tahap ini.

### 13.8 Data dan tampilan

- Tabel baru `followup_items`: jenis (`prospek`, `servis_berkala`, `garansi`,
  `piutang`), pelanggan, unit, nota sumber, jatuh tempo, kolom status,
  penanggung jawab, waktu follow-up terakhir, dan alasan arsip. Satu item
  aktif per pelanggan/unit per jenis.
- Tabel baru `followup_events`: item, dari kolom, ke kolom, alasan, operator,
  dan waktu. Ini riwayat/database perpindahan yang tidak boleh dihapus.
- `harga_jasa` mendapat `interval_servis_bulan`; `service_jobs` menyimpan
  salinannya sebagai snapshot saat nota disimpan. Kolom **Servis berkala**
  tampil di tabel Jasa (`frontend/js/app.js:4019`) dan modal Tambah/Edit jasa
  (`frontend/js/app.js:4105`); field ikut di `HargaJasaCreate/Update/Out`
  (`api/schemas.py:166-179`).
- `wa_message_log` Tahap 12 dipakai ulang dengan jenis `struk`, `followup`,
  `garansi`, dan `piutang`; tidak ada tabel pesan kedua.
- Endpoint ringkasan harian yang sekarang mengirim `garansi_aktif`
  (`services/report_service.py:95`) ditambah `garansi_akan_habis`,
  `piutang_count`, `piutang_total`, `servis_berkala_due`, dan
  `followup_hari_ini` dari query backend yang sama dengan daftar. Kartu
  Ringkasan memakai angka itu, bukan hitungan JavaScript.
- Status follow-up dan penanggung jawab disimpan terpisah dari status bayar
  dan tidak mengubah sisa. Daftar untuk filter `warranty_expiring`, `piutang`,
  `servis_berkala`, dan `tugas_hari_ini` memakai query backend yang sama
  dengan angka kartu.
- Pengaturan menyimpan X hari, ambang garansi akan habis, H-14 servis berkala,
  cooldown, template, dan persetujuan bawaan. Tidak ada token atau sesi.
- Detail pelanggan menampilkan servis terakhir, servis berikutnya per jasa
  beserta intervalnya, garansi, piutang berjalan, status follow-up terakhir,
  penanggung jawab, dan sakelar persetujuan.
- Ringkasan menampilkan kartu **Tugas follow-up hari ini**, **Servis
  berkala**, **Garansi akan habis**, dan **Piutang**; daftar tugas dapat
  difilter hari ini, terlambat, belum ditugaskan, dan milik saya.
- Pelanggan dengan piutang, garansi aktif, servis berkala, atau garansi akan
  habis tetap muncul di daftar Ringkasan sampai lunas/void, garansi habis atau
  diklaim, pengingat diarsipkan, atau nota dibatalkan. Follow up tidak
  menghapus mereka dari daftar.
- Tampilan diuji pada Terang/Gelap dan lebar ponsel.

### 13.9 Batasan

- Tidak mengubah transaksi, stok, atau perhitungan uang.
- Tidak mengirim pesan otomatis, tanpa persetujuan, atau di luar jam wajar.
- Tidak ada kampanye massal, bot AI, atau balasan otomatis.
- Follow-up tidak mengubah status nota, garansi, atau piutang; kasir tetap
  mencatat tindak lanjut secara manual.
- Follow up tidak boleh dianggap pembayaran dan tidak boleh menghilangkan nota
  dari Ringkasan; hanya LUNAS atau void/retur yang mengeluarkannya.
- Follow up tidak boleh memindahkan item ke kolom lain secara otomatis; semua
  perpindahan manual dan tercatat di `followup_events`.
- Item yang diarsipkan tidak dihapus; riwayat dan alasannya tetap tersimpan.
  Piutang tidak boleh diarsipkan manual.
- Interval servis berkala disalin ke nota saat transaksi; mengubah master jasa
  tidak boleh mengubah jadwal nota lama.
- Nilai 0 berarti **Nonaktif**; jasa tanpa interval tidak pernah masuk daftar
  servis berkala.
- Interval hanya berlaku untuk jasa; sparepart dan stok tidak mendapat
  interval pada tahap ini.
- Satu pelanggan/unit hanya boleh punya satu item aktif per jenis; tidak ada
  baris ganda untuk nota berbeda.
- Penanggung jawab memakai identitas operator yang sudah ada; tidak ada
  perubahan PIN, akun, atau autentikasi baru pada tahap ini.
- Perhitungan umur, sisa garansi, dan jadwal servis memakai zona waktu
  perangkat dan tahan terhadap jam diubah; angka kartu tetap dari backend.

### 13.10 Rencana pengujian

- Batas X hari: servis X−1 hari belum muncul, X hari muncul; setelah diubah di
  Pengaturan daftar ikut berubah.
- Cooldown: setelah Follow up ditekan, item ditandai **Sudah follow up** dan
  tidak bisa dikirim ulang sebelum cooldown; tidak ada duplikat pada hari yang
  sama.
- Master Jasa: isi interval 6 bulan, simpan, dan kolom **Servis berkala**
  tampil di tabel; ubah menjadi 3 bulan dan pastikan modal Edit memuat nilai
  terbaru.
- POS: memilih jasa berinterval menampilkan **Servis berkala** pada baris jasa;
  mengubahnya untuk satu nota tersimpan sebagai snapshot, bukan mengubah
  master.
- Daftar servis berkala menampilkan nama jasa yang dikerjakan dari nota (mis.
  ganti oli dan cuci radiator), tanggal servis, interval, dan jatuh tempo
  terdekat; jasa **Nonaktif** tidak muncul.
- Mengubah nama atau interval master jasa tidak mengubah riwayat, jadwal, atau
  nama pekerjaan pada nota lama.
- Jatuh tempo kalender: servis 31 Januari + 1 bulan menjadi 28/29 Februari
  sesuai tahun; interval 6 bulan menghasilkan tanggal yang benar.
- Servis berkala: interval 3/6 bulan menghasilkan jatuh tempo benar; nota
  dengan beberapa jasa memakai jatuh tempo terdekat; servis lebih awal menutup
  siklus lama.
- Batas H-14 servis berkala: H-15 belum muncul, H-14 muncul; item tetap
  terlihat setelah lewat.
- Penggabungan: pelanggan dengan tiga unit menghasilkan satu item per jenis,
  memakai nota terbaru, dan tidak ada baris ganda setelah follow-up.
- Tugas hari ini: item jatuh tempo/terlambat muncul, penanggung jawab dapat
  diambil, operator lain melihat "sedang ditangani", penggantian penanggung
  jawab tercatat.
- Badge: setelah Follow up item tetap di kolomnya dengan badge **Sudah follow
  up**; tidak ada perpindahan otomatis. Tombol pindah kolom mencatat
  `followup_events` (dari, ke, alasan, operator, waktu).
- Hilangkan pengingat: garansi H-xx dan servis berkala dapat langsung
  diarsipkan tanpa follow up, hilang dari Ringkasan/tugas, dan tidak muncul
  lagi pada siklus yang sama; riwayatnya tetap ada. Piutang tidak bisa
  diarsipkan manual.
- Janji bayar piutang: tanggal janji memunculkan pengingat baru; memindah kolom
  tidak mengubah sisa, dan LUNAS hanya dari pelunasan penuh.
- Follow up piutang: pesan menyebut pekerjaan selesai, ajakan datang mengambil
  barang, dan sisa dari backend; status berubah **Sudah follow up** tetapi
  sisa, status BELUM LUNAS, dan hitungan kartu **Piutang** tidak berubah.
- Kartu **Piutang**: jumlah dan total sisa sama dengan daftar belum lunas,
  klik membuka daftar yang sama; nota yang sudah follow up tetap dihitung.
- Pelunasan sebagian: sisa dan total kartu turun, jumlah nota tetap, baris
  tetap tampil. Pelunasan penuh: status LUNAS, struk lunas ditawarkan, lalu
  nota hilang dari Ringkasan; void/retur juga mengeluarkannya.
- Follow up tidak menghapus baris; cooldown hanya menonaktifkan tombol.
- Nota VOID/retur penuh tidak masuk prospek; servis NORMAL terbaru dipakai.
- Pelanggan tanpa nomor atau menolak tidak punya tombol aktif.
- Pesan mengikuti riwayat servis (cuci, perbaikan, ganti sparepart) dan
  menyebut garansi bila masih aktif.
- Kartu **Garansi akan habis**: `garansi_sampai` hari ini dan H+7 dihitung,
  H+8 tidak; nota VOID, tanpa garansi, sudah kedaluwarsa, dan sudah diklaim
  tidak dihitung.
- Angka kartu **Garansi akan habis** sama dengan jumlah baris daftar filter
  `warranty_expiring`; klik kartu membuka daftar yang sama.
- Pesan follow-up garansi menyebut kondisi barang sesuai pekerjaan, tanggal
  garansi berakhir, sisa hari, dan ajakan cek ulang.
- Status dibuka/dibatalkan tercatat jujur; WhatsApp tidak terpasang tidak
  merusak daftar.
- Garansi H-7/H-3/H-1 dan piutang dari Tahap 11 tampil tepat waktu.
- Tampilan Terang/Gelap dan lebar ponsel.

### Kriteria selesai

- Ringkasan menampilkan prospek follow-up yang benar untuk servis lewat X hari.
- Master Jasa punya kolom **Servis berkala** yang dapat diubah (Nonaktif,
  1/3/6/12, atau bebas); jasa Nonaktif tidak pernah diingatkan.
- Follow-up servis berkala muncul sesuai interval per jenis jasa (mis. ganti
  oli 6 bulan, cuci radiator 3 bulan), menampilkan jasa yang benar-benar
  dikerjakan dari nota, dan memakai nota terbaru.
- Mengubah interval master jasa tidak mengubah jadwal atau nama pekerjaan pada
  nota lama.
- Satu item per pelanggan/unit per jenis; pelanggan dengan tiga unit tidak
  menghasilkan tiga baris.
- Daftar tugas hari ini menampilkan item jatuh tempo, penanggung jawab, dan
  mencegah dua operator menangani item yang sama.
- Tombol Follow up hanya memberi badge **Sudah follow up** dan tidak memindah
  kolom; pindah kolom manual dan riwayatnya tercatat.
- Garansi H-xx dan servis berkala dapat langsung dihilangkan/diarsipkan tanpa
  follow up, dan tidak muncul lagi pada siklus yang sama.
- Ringkasan menampilkan **Garansi akan habis** yang akurat dan dapat diklik;
  angkanya sama dengan daftar yang terbuka.
- Ringkasan menampilkan **Piutang** yang akurat; klik membuka daftar belum
  lunas dan tombol **Follow up** mengirim tagihan selesai + sisa bayar.
- Follow up hanya menandai **Sudah follow up**; nota tetap BELUM LUNAS dan
  tetap tampil sampai pelunasan penuh.
- Pelunasan penuh menawarkan **Cetak struk lunas**, lalu nota hilang dari
  Ringkasan; pelunasan sebagian memperbarui sisa dan tetap tampil.
- Tombol **Follow up** membuka WhatsApp dengan pesan sesuai riwayat servis.
- Follow-up garansi menanyakan kondisi barang/mesin dan memberi tahu garansi
  akan berakhir serta mengajak cek ulang.
- Cooldown mencegah follow-up berulang; status tercatat jujur.
- Pelanggan tanpa persetujuan atau nomor valid tidak dibukakan WhatsApp.
- Pengingat garansi dan piutang memakai kanal dan daftar yang sama.
- Tidak ada pengiriman otomatis, Baileys, sesi, atau perubahan perhitungan uang.

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
| Pembayaran dan piutang | DP, pelunasan bertahap, void/retur ber-DP, kartu piutang di Ringkasan, struk lunas, umur piutang, dan rekonsiliasi kas versus nilai nota teruji |
| WhatsApp dan CRM | Tanpa Baileys/sesi; pengiriman lewat tautan/Intent dengan persetujuan; worklist dan penanggung jawab; perpindahan kolom manual tercatat; Data Safety teruji |
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
