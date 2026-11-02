# Rencana Pemantapan

Status: **siap dimulai — fitur web 2.8.0 sudah dibangun; multi-toko/premium
dibangun dan diuji di web 2.7.0 lebih dulu**. 2026-11-03.

Dokumen ini menampung pekerjaan pemantapan yang **tidak dikerjakan** selama fase
pengembangan fitur. Fitur web sudah dibangun; pengujian dilakukan di fase ini.
Seluruh skenario uji multi-toko dan premium juga dipindahkan ke sini dan baru
dijalankan setelah fiturnya dibangun.

## Posisi

- Tidak ada uji pemantapan selama fase build fitur.
- Uji pemantapan dilakukan setelah fitur web selesai, dalam satu fase.
- APK, Android, printer fisik, dan perangkat fisik ditunda.
- Tidak ada backup data karena belum ada user.
- Database baru boleh dibuat dari nol; tidak ada kewajiban kompatibilitas.
- Nomor versi rilis pemantapan ditentukan setelah fitur web dan uji
  multi-toko/premium di web selesai.

## Lingkup pemantapan

### 1. Kebenaran data dan uang

- Audit alur nota, pembayaran, piutang, retur, void, garansi, komisi, dan gaji.
- Pastikan nominal memakai Decimal dan pembulatan konsisten di backend.
- Uji stok minus, retur sebagian, tukar barang, pembayaran bertahap, dan nota
  void.
- Uji nomor nota berurutan dan idempotency request.
- Rekonsiliasi stok dan laporan harian/periode dengan data nota.
- Uji tanggal, jam, dan batas periode laporan.

### 2. Keamanan

- Uji PIN, sesi, dan lockout.
- Uji pembatasan loopback, Host, Origin, dan dokumentasi API yang dimatikan.
- Uji token instalasi dan penolakan kredensial placeholder.
- Tinjau `except Exception` agar kegagalan tidak tertelan tanpa log.
- Pastikan tidak ada token/rahasia baru di repo.
- Uji audit event untuk void, retur, dan perubahan stok.

### 3. Keandalan

- Uji dua transaksi bersamaan: nomor nota, stok, pembayaran.
- Uji database terkunci, disk penuh, dan jaringan mati.
- Uji startup dengan database rusak atau kosong dan pemulihan database.
- Pastikan pesan error memberi langkah berikutnya, bukan hanya “gagal”.

### 4. Performa web

- Siapkan dataset besar: pelanggan, unit, nota, stok, dan audit event.
- Ukur laporan harian, periode, stok, rekap keuangan, dan startup web.
- Periksa indeks query laporan dan daftar.
- Hindari perubahan performa yang tidak diukur.

### 5. UI web

- Uji Chrome/Edge pada lebar 1440, 1024, 810, dan 360.
- Uji tema terang/gelap dan lima tema warna.
- Uji popup, empty state, validasi, toast, keyboard, scroll, dan tabel di layar
  sempit.

### 6. Rilis

- Perbarui versi dan README sesuai perilaku yang berubah.
- Catat changelog singkat.
- Build web final; tidak membuat APK.
- Siapkan prosedur rollback sederhana (pasang ulang versi lama, database baru).
- Push ke GitHub hanya setelah uji selesai.

### 7. Uji premium dan multi-toko (setelah implementasi)

Dijalankan setelah fitur di `RENCANA_MULTI_TOKO_PREMIUM.md` dibangun. Fitur
multi-toko dan premium dibangun lebih dulu di **web 2.7.0 (BengkelPOS
Radiator)**; web menjadi kanal uji pertama sebelum fitur dibawa ke PusatkuPOS
Flutter. Tidak ada uji fitur ini selama fase build. Baris yang menyebut paket
resource, Play Asset Delivery, dan iOS diuji pada fase port Flutter, bukan di
web 2.7.0.

| Area | Uji |
| --- | --- |
| Isolasi | 3 toko; nota, stok, pelanggan, karyawan, dan laporan tidak tercampur |
| Registry | tambah toko, toko aktif, registry rusak, toko hilang |
| Ganti toko | posisi di dalam Menu, satu/banyak toko, konfirmasi perubahan, offline |
| Izin | pemilik dapat menambah toko; karyawan hanya melihat toko yang ditugaskan |
| Premium | gratis tidak bisa menambah toko; premium tanpa batas toko; login Google wajib untuk pemilik; premium hanya langganan bulanan, tidak ada sekali bayar |
| Batas perangkat | paket contoh 2 perangkat: perangkat ke-2 diterima, ke-3 ditolak; logout/cabut membebaskan slot; gratis dan trial tetap 1 perangkat |
| Gating | gratis tidak bisa membuka fitur premium; trial hanya membuka Follow up; saat terkunci, data lama Karyawan/Supplier/Follow up tetap dibaca/diekspor, tetapi tambah/ubah dan aksi premium ditolak |
| Data terkunci | setelah langganan berakhir atau turun paket: daftar dan detail data lama terbuka, ekspor berhasil, tombol tambah/ubah/WA nonaktif dan permintaan langsung ditolak |
| Kuota | 20 klik WA dari Follow up per database; database yang sama tidak bisa mengulang trial |
| ID database | `database_id` unik dan tersimpan di file; restore file yang sama membawa kuota yang sama; database dapat dibuka user/perangkat lain |
| Trial per database | database baru mendapat ID baru dan trial baru; tidak ada pengikat perangkat/akun |
| Free tier | tanpa iklan dan tanpa panggilan API data; paket resource dasar diunduh sekali lewat Play |
| Paket resource per peran | login kasir pertama hanya mengunduh paket tampilan kasir; paket stok/owner tidak terpasang; login peran lain menambah paket; cache dipakai ulang |
| Offline paket | setelah paket terpasang fitur jalan offline; sebelum terpasang dan offline, fitur terkunci dengan pesan jelas |
| Play Asset Delivery | unduhan aset lewat Play; gagal dan retry tidak merusak data; tidak ada dex/JAR/so dari luar Play; tidak ada self-update |
| Sideload | APK sideload memakai APK penuh/split; tidak ada unduhan aset on-demand |
| Base size | base berisi seluruh logika shell dan fitur; paket peran terpisah; ukuran base diukur sebelum rilis |
| Tanpa kode di paket | paket resource berisi layout/aset/label/konfigurasi; tidak ada kode dan tidak menambah fitur di luar shell |
| Izin paket | paket terpasang tidak membuka akses di luar peran; permintaan langsung ditolak |
| Versi paket | shell menolak paket di bawah versi minimum; rollback ke paket bawaan saat unduhan atau pembaruan gagal |
| Kepatuhan iOS | paket peran diunduh sebagai aset/On-Demand Resources tanpa executable code; paket tidak menambah fitur; App Store 2.5.2 terpenuhi |
| Play Billing | langganan Android lewat Play Billing; restore dan acknowledge; perpanjangan dan pembatalan tercermin; tidak ada tautan pembayaran digital eksternal yang melanggar kebijakan |
| Lisensi offline | token bertanda tangan + hitung mundur di perangkat; offline lama tidak memanggil API data; jam dimundurkan tidak memperpanjang masa aktif; saat online lisensi dikoreksi dari server |
| Langganan berakhir | fitur premium terkunci, kasir dan data lokal tetap jalan; data lama tetap dibaca/diekspor; 10 delta pending dikirim lebih dulu saat online lalu pengiriman berhenti; VPS tidak menyimpan data bengkel |
| Hapus akun | hapus akun tersedia di aplikasi dan tautan web; data lokal serta metadata server dihapus sesuai konfirmasi |
| Data safety | deklarasi akun, lisensi, perangkat, dan kuota; tidak ada data bengkel di VPS; unduhan paket resource menampilkan progres |
| Header | nama + printer, alamat, alamat kosong, layar sempit, ganti toko |
| Backup | 3 toko menjadi satu ZIP, checksum, manifest, batas Telegram |
| Restore | satu arsip memunculkan semua toko; checksum dan manifest valid; satu database rusak membatalkan semua |
| Rollback | restore gagal tidak menghilangkan data lama |
| Backup otomatis | jadwal lokal dan Telegram; tidak ada backup ke VPS |
| Login | tanpa login untuk toko tunggal; Google untuk pemilik multi-toko; token aman; offline; paket resource peran diunduh setelah login |
| ID owner | 8 karakter acak (minimum 7), huruf kecil/angka tanpa `0`, `1`, `l`, `o`; unik antar pemilik; tidak berurutan; kartu teks + tombol salin + QR berisi ID saja; dua pemilik dengan username karyawan sama tetap terpisah |
| Login karyawan | tiga kolom: ID owner + username + password; tanpa Google; ID owner salah ditolak; lockout berlaku; hanya paket resource peran yang diunduh |
| Password karyawan | minimal 8 karakter; password sama dengan karyawan lain di owner yang sama ditolak; wajib ganti saat login pertama; tidak kedaluwarsa otomatis; reset hanya oleh pemilik |
| PIN karyawan | 6 digit diatur karyawan sendiri; tidak sama dengan password; lupa PIN meminta reset ke pemilik lalu membuat PIN baru |
| Tombol acak password | tombol ikon putar/bulat mengisi password 10–12 karakter sesuai kebijakan tanpa diketik pemilik; hasil tetap unik terhadap karyawan lain; jika bentrok dibuat ulang otomatis |
| Salin semua akun | tombol menyalin satu teks berisi ID owner + username + password + peran + toko + catatan ganti password; tidak memuat PIN/token/data bengkel; tombol hanya aktif selama password baru tampil |
| Reset password lewat tombol acak | password lama langsung tidak berlaku; password baru tampil sekali; karyawan wajib menggantinya saat login berikutnya; perangkat tetap terdaftar kecuali dicabut pemilik |
| Logout | sesi/token terhapus, sync berhenti, data lokal dan PIN tetap ada; perangkat karyawan tercabut; cache paket tidak terhapus otomatis |
| Reinstall | hapus aplikasi, pasang ulang, restore arsip memunculkan semua toko; status trial mengikuti database di arsip; paket resource diunduh ulang sesuai peran |
| Sinkronisasi | VPS tidak menyimpan data bengkel; delta hanya diteruskan; kasir tetap transaksi saat API mati; kirim ulang idempotent; konflik uang/stok ditolak |
| Pending relay | internet mati saat transaksi; delta pending di perangkat; transaksi tetap jalan; saat online terkirim berurutan; status pending terlihat; pengiriman ulang tidak menggandakan nota/stok |
| Multi-device premium | owner premium memakai perangkat sesuai batas paket (contoh 2) dengan ID owner sama; delta sampai ke semua perangkat terdaftar; perangkat di atas batas ditolak; perangkat non-hub tidak bisa menulis nota, pembayaran, atau retur; stok boleh ditambah sebagai delta; gratis dan trial tetap satu perangkat |
| Banyak akun | 100 akun karyawan satu owner; masing-masing mencatat riwayat dan menambah stok saat offline; data tergabung setelah online; tidak tercampur dengan owner lain |
| Pending lama | simulasi offline berbulan-bulan; outbox tidak hilang; banner dan notifikasi lokal tetap muncul; notifikasi tidak bisa dimatikan permanen; saat online terkirim berurutan |
| Urutan dan konflik | delta dari banyak perangkat diurutkan dengan nomor urut perangkat dan jam logis; stok tidak ganda; opname bertabrakan ditandai konflik |
| Aplikasi utama (owner tanpa karyawan) | semua fitur terbuka; fitur premium terkunci sesuai paket |
| Aplikasi utama (mode karyawan) | hanya fitur/toko ditugaskan sesuai peran dasar + izin tambahan per akun; absensi, status, catatan, penyelesaian servis, komisi; tidak bisa ubah tarif/gaji |
| Aplikasi owner terpisah | tanpa core logic; ringkasan per toko, laporan, buat/reset akun, beri/cabut izin tambahan, reset password/PIN, cabut perangkat, riwayat perubahan izin; tidak bisa transaksi |
| Izin mode | menu/data owner tidak muncul dan permintaan langsung dari mode karyawan ditolak |
| Izin tambahan | Budi berperan Kasir lalu diberi izin opname: Budi membuka opname; kasir lain tanpa izin ditolak; peran dasar dan tarif komisi Budi tidak berubah |
| Batas izin tambahan | pemilik tidak bisa memberi akses khusus pemilik (kelola akun/perangkat, lisensi, tambah/hapus toko, ubah tarif komisi/gaji, hapus data) lewat izin tambahan; permintaan langsung ditolak |
| Penerapan izin tambahan | UI menyembunyikan menu yang tidak diizinkan dan lapisan data menolak permintaan langsung; izin tidak membuka fitur premium yang terkunci paket |
| Cabut izin tambahan | pemilik mencabut izin opname Budi; perangkat Budi memakai izin terakhir saat offline, lalu izin baru berlaku saat login/sinkronisasi berikutnya; cabut perangkat langsung mengakhiri akses |
| Audit izin | setiap pemberian/pencabutan izin mencatat siapa, kapan, dan sebelum/sesudah; riwayat terlihat di aplikasi owner |
| Aplikasi Python lama | setelah Flutter stabil, aplikasi lama tetap tersimpan sebagai arsip/acuan; tidak dihapus, tidak diberi fitur baru, dan database/backup lama tidak dimigrasikan paksa |

## Uji akhir pemantapan

Dilakukan sekali setelah fitur web selesai dan build web berhasil.

1. Jalankan `pytest` pada `.venv`.
2. Buat database baru dari nol dan jalankan integrity check.
3. Uji manual web: kasir, pembayaran, retur, void, stok, laporan, dan
   pengaturan.
4. Perbaiki bug, lalu ulangi hanya tes yang gagal.
5. Build web ulang bila ada perbaikan.

Tidak diuji pada tahap ini: APK, Android, printer, scanner fisik, backup,
Telegram, dan perangkat fisik.

## Kriteria selesai

- Tidak ada bug P0/P1 yang terbuka pada alur uang, stok, nota, dan laporan.
- `pytest` `.venv` lulus.
- Database baru dapat dibuat dan lulus integrity check.
- Kasir dan stok tetap benar pada uji konkurensi.
- Build web berhasil dan halaman utama berjalan.
- Tidak ada rahasia baru di repo.
- README dan changelog sesuai.
- Gap perangkat/APK/backup dicatat.

## Di luar lingkup

- APK, Android, kamera, dan perangkat fisik.
- Printer fisik dan pengujian cetak.
- Backup/restore dan Telegram; VPS tidak menyimpan data bengkel.
- Implementasi multi-toko, login, premium, dan sinkronisasi; pengujiannya ada
  di bagian 7 dan baru dijalankan setelah fiturnya dibangun.
- Fitur baru; pemantapan tidak menambah fitur.

## Risiko

- Pemantapan yang ditunda dapat menemukan masalah setelah fitur dibangun.
- Tanpa APK, perilaku mobile belum diketahui.
- Tanpa backup, data dummy tidak dapat dipulihkan; ini diterima karena belum ada
  user.
- Uji perangkat fisik dan printer belum tercakup.

## Dokumen terkait

- `RENCANA_MULTI_TOKO_PREMIUM.md` — rencana multi-toko, akun, dan fitur premium.
- `RENCANA_PENGEMBANGAN_TAHAP_FINAL.md` — arah Flutter PusatkuPOS.
