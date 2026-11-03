# Rencana Pemantapan

Status: **rencana uji aktif** — 2026-11-03. Status implementasi dan riwayat
pengerjaan ada di
[`STATUS_MULTI_TOKO_PEMANTAPAN.md`](STATUS_MULTI_TOKO_PEMANTAPAN.md).

Dokumen ini menampung pekerjaan pemantapan yang **tidak dikerjakan** selama fase
pengembangan fitur. Pengujian fitur web 2.7.0 dilakukan di fase ini. Skenario
multi-toko dan premium ada di bagian 7; prototipe web Fase 3–7 sudah dibangun
dan sebagian sudah lulus uji otomatis, tetapi **uji UI manual dan pilot belum
dijalankan**. Aturan produk tidak ditulis ulang di sini; rujukannya adalah
`K-xx` pada bagian **Keputusan (sumber kebenaran)** di
`RENCANA_MULTI_TOKO_PREMIUM.md`.

Rencana implementasi hanya memuat pekerjaan yang belum ada kodenya. Jika kode
sudah dibuat, item itu dihapus dari rencana dan statusnya dicatat di
[`STATUS_MULTI_TOKO_PEMANTAPAN.md`](STATUS_MULTI_TOKO_PEMANTAPAN.md). Dokumen ini
tetap memuat skenario uji untuk fitur yang sudah ada.

## Status implementasi

Status fitur dan riwayat pengerjaan ada di
[`STATUS_MULTI_TOKO_PEMANTAPAN.md`](STATUS_MULTI_TOKO_PEMANTAPAN.md). Versi acuan
web adalah **2.7.0**; tidak ada versi 2.8.0 yang terpasang. Kode web Fase 1 dan
prototipe Fase 3–7 sudah ada (multi-toko, akun, lisensi, perangkat, relay,
snapshot, arsip), dengan 400 tes desktop lulus dan 15 tes premium web lulus 3x
berturut pada 2026-11-03.

## Posisi

- Tidak ada uji pemantapan selama fase build fitur.
- Uji pemantapan dilakukan setelah fitur web selesai, dalam satu fase. Uji UI
  manual dan pilot tetap menjadi gerbang sebelum port Dart/APK.
- APK, Android, printer fisik, dan perangkat fisik ditunda sampai kode web
  stabil; fokus saat ini hanya web.
- Tidak ada data pengguna nyata; backup/restore tetap diuji dengan database
  dummy sebagai **P0**.
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

### 1b. Backup, restore, dan rollback (P0)

- Uji backup manual gratis di semua tier, termasuk saat fitur premium terkunci.
- Uji **backup otomatis lokal hanya untuk premium**; gratis tidak dapat
  mengaktifkannya dan tetap mendapat pengingat backup manual.
- Uji restore staging/all-or-nothing, checksum manifest, dan rollback saat satu
  database rusak.
- Backup wajib menyertakan outbox pending dan data fitur terkunci; PIN, token,
  dan rahasia perangkat tidak ikut.
- Backup/restore tetap P0 walau belum ada pengguna nyata; gunakan database dummy
  yang dapat dibuat ulang.

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

Dijalankan setelah fitur di `RENCANA_MULTI_TOKO_PREMIUM.md` dibangun. Aturan
produk tidak diulang di sini; setiap baris merujuk `K-xx` pada bagian
**Keputusan (sumber kebenaran)** di dokumen itu. **Web 2.7.0 sudah memuat
prototipe premium Fase 3–7** (akun, lisensi, ID owner, perangkat/hub, relay,
snapshot, arsip, login perangkat karyawan) sebagai acuan migrasi. Web tetap
hanya membuktikan alur dan penyimpanan metadata; Play Billing, secure storage,
notifikasi sistem, kunci perangkat sungguhan, dan relay lintas perangkat nyata
tetap diuji di Dart/APK.

| Area | Rujukan | Uji |
| --- | --- | --- |
| Isolasi | K-09 | 3 toko; nota, stok, pelanggan, karyawan, dan laporan tidak tercampur |
| Registry | K-09 | tambah toko, toko aktif, registry rusak, toko hilang |
| Ganti toko | K-09 | posisi di dalam Menu, satu/banyak toko, konfirmasi perubahan, offline |
| Izin toko | K-09, K-07 | pemilik dapat menambah toko; karyawan hanya melihat toko yang ditugaskan |
| Premium | K-03, K-11, K-21 | satu tier: multi-toko, karyawan di hub/perangkat, Supplier/Follow up/WA, backup otomatis/Telegram/semua toko, lisensi, relay, aplikasi owner, ID owner |
| Gating | K-03, K-04 | gratis hanya membuka fitur inti dan Follow up 20 kredit; akun karyawan, multi-toko, dan fitur premium lain terkunci; tambah/ubah dan aksi premium ditolak saat terkunci |
| Data terkunci | K-03, K-10 | setelah paket berakhir: daftar/detail data lama terbuka, ekspor berhasil, tombol tambah/ubah/WA nonaktif, permintaan langsung ditolak |
| Follow up gratis | K-04, K-07 | gratis seumur hidup; profil lokal tanpa akun/Google; login opsional kapan saja; tanpa login tidak memanggil API; database yang sama tidak bisa mengulang 20 kredit |
| Kuota | K-04 | kredit terakhir diterima, berikutnya ditolak; dihitung saat link `wa.me` dibuat; tidak kembali saat pesan gagal; counter lokal ikut file/backup |
| ID database | K-05 | `database_id` unik di file; restore file yang sama membawa kuota yang sama; database dapat dibuka user/perangkat lain |
| Kuota per database | K-04, K-05 | database baru mendapat ID dan 20 kredit baru; tidak ada pengikat perangkat/akun |
| Free tier | K-03, K-04, K-07, K-10 | gratis seumur hidup; peran owner baik tanpa akun maupun login Google; kasir/ringkasan/stok/laporan terbuka; 1 toko tanpa tambah; tanpa karyawan/Supplier; Follow up 20 kredit; tanpa API data; login gratis hanya auth, tanpa registrasi perangkat; backup manual saja |
| Backup lokal (P0) | K-10 | backup manual gratis di semua tier; backup otomatis lokal hanya premium; tetap manual setelah downgrade; restore staging, checksum, rollback; outbox dan data terkunci ikut; PIN/token tidak ikut |
| Gating backup web | K-10 | tombol backup manual tetap berhasil di gratis; penjadwal dan Telegram melewati pengiriman saat gratis lalu melapor premium-only; pengingat backup manual tetap tampil |
| Redaksi rahasia | K-10, K-18 | backup, ekspor Excel/CSV, dan arsip semua toko menghapus hash password/PIN karyawan, hash token perangkat, `login_guards`, serta rahasia sesi/Telegram; database aktif tetap menyimpan yang dibutuhkan |
| Backup Telegram | K-10 | hanya premium; setelah downgrade backup baru berhenti, file lama tidak dihapus |
| Backup semua toko | K-10 | 3 toko menjadi satu ZIP dengan manifest, checksum, seluruh database, data terkunci, dan outbox |
| Restore | K-10 | satu arsip memunculkan semua toko; checksum/manifest valid; satu database rusak membatalkan semua |
| Rollback | K-10 | restore gagal tidak menghilangkan data lama; staging tidak menimpa data aktif |
| Header | K-09 | nama + printer, alamat, alamat kosong, layar sempit, ganti toko |
| ID owner | K-06 | hanya premium; diterbitkan saat premium aktif; format, keunikan, tidak berurutan, kartu + salin + QR berisi ID saja; dipakai login perangkat karyawan/aplikasi owner; tidak untuk gratis atau login hub; dua owner dengan username karyawan sama tetap terpisah |
| Login pemilik | K-07, K-11 | tanpa login tetap default gratis; Google opsional untuk gratis kapan saja dan wajib untuk premium; alasan manfaat tampil; token aman; offline setelah login awal |
| Login gratis | K-07, K-12, K-18 | diuji di Dart, bukan web; boleh login kapan saja; tanpa ID owner; tanpa registrasi perangkat; hanya API autentikasi; data bengkel tidak dikirim; persetujuan privasi dicatat; hapus akun menghapus identitas |
| Login karyawan | K-07, K-08 | di hub: username + password + PIN, lokal tanpa internet; di perangkat: tiga kolom + ID owner, login pertama online; lockout; tanpa Google |
| Password | K-08 | tanpa aturan unik; tombol acak memenuhi kebijakan; password tampil sekali; wajib ganti saat login pertama; reset oleh pemilik |
| Salin semua | K-08 | teks berisi username + password + peran + toko + catatan ganti; ID owner disertakan hanya untuk login perangkat karyawan, hub tidak perlu; tanpa PIN/token/data bengkel; hanya aktif selama password baru tampil |
| ID owner web | K-06 | kartu besar + salin; QR lokal hanya memuat ID owner; ID tidak berubah setelah aktivasi; QR tidak memuat password/token/data bengkel |
| Password web | K-08 | bcrypt + salt per pengguna; tombol acak menghasilkan 10–12 karakter tanpa `0`,`1`,`l`,`o`; password awal wajib diganti saat login pertama; hash PBKDF2 lama tetap dapat login |
| Login perangkat web | K-07 | form ID owner + username + password + token perangkat; token disimpan di `sessionStorage`, dikirim sebagai `X-Device-Token`, dan dihapus saat logout; login pertama meminta ganti password |
| PIN | K-08 | PIN diatur karyawan; lupa PIN meminta reset pemilik lalu membuat PIN baru |
| Peran dan izin | K-07 | Budi kasir + opname membuka opname; kasir lain tanpa izin ditolak; peran/komisi Budi tidak berubah; login hub lokal |
| Batas izin | K-07 | akses khusus pemilik tidak bisa diberikan; permintaan langsung ditolak |
| Penerapan izin | K-07, K-15 | UI menyembunyikan menu dan lapisan data menolak permintaan langsung; paket terkunci tetap menang; delta karyawan diverifikasi terhadap snapshot izin bertanda tangan owner (versi, toko, izin stok) |
| Cabut izin | K-07, K-15 | di hub berlaku lokal; perangkat offline memakai izin terakhir, lalu izin baru saat sinkron; cabut perangkat mengakhiri akses |
| Audit izin | K-07 | setiap perubahan mencatat siapa, kapan, sebelum/sesudah; riwayat terlihat di hub dan aplikasi owner premium |
| Logout | K-07, K-08 | sesi/token terhapus, sync berhenti, data lokal dan PIN tetap ada; perangkat tidak lagi menerima delta |
| Reinstall | K-04, K-10, K-17 | hapus aplikasi, pasang ulang, restore arsip memunculkan semua toko; status kuota mengikuti database; tidak ada unduhan per peran |
| Perangkat owner | K-12, K-21 | gratis: tidak didaftarkan, tanpa penegakan slot; premium: paket contoh 2, ke-3 ditolak; cabut membebaskan slot |
| Perangkat hilang | K-12, K-22 | owner login Google di perangkat baru, cabut perangkat lama dari aplikasi/web; token lama ditolak; percobaan kedua dalam 72 jam ditolak; data lama tidak dapat dihapus jarak jauh |
| Perangkat karyawan | K-12, K-21 | premium; 100 akun terdaftar; tidak dihitung dalam batas owner; tidak menjadi hub; tidak menulis nota/pembayaran/retur; dapat dicabut |
| Flag hub | K-12 | hanya perangkat owner bisa menjadi hub; karyawan kasir di hub boleh menulis uang; owner di non-hub tidak; satu hub per toko; pindah hub online + ack/force; delta uang hub lama dikarantina |
| Multi-device | K-12, K-14, K-21 | premium: delta sampai ke semua perangkat owner terdaftar; non-hub hanya stok sesuai izin; dua hub untuk toko yang sama ditolak |
| Relay data | K-13, K-21 | premium: server tidak dapat membaca nota/pelanggan/stok; hanya metadata, kunci publik/wrapped key, dan amplop terenkripsi |
| Antrean terenkripsi | K-13 | penerima offline; amplop ciphertext; hapus setelah semua penerima aktif mengakui; pengakuan ulang setelah amplop dihapus dianggap duplikat, bukan galat; TTL sesuai K-13; server tidak memegang kunci privat |
| TTL antrean | K-13, K-22 | setelah TTL, penerima meminta snapshot dari hub online atau restore backup; outbox pengirim tidak hilang |
| Snapshot | K-13, K-22 | perangkat kedua mengambil snapshot + wrapped key dari hub/backup; snapshot atomik; outbox lokal diputar ulang, dideduplikasi, konflik ditandai |
| Distribusi kunci | K-22 | perangkat baru membuat keypair; owner/hub menyetujui; wrapped store key hanya untuk toko yang ditugaskan |
| Pencabutan dan re-key | K-22 | perangkat dicabut tidak menerima amplop baru; **Ganti kunci toko** membungkus ulang hanya ke perangkat aktif, menghapus amplop/snapshot lama, dan mengirim ulang outbox; data lama di perangkat dicabut tidak dapat dihapus jarak jauh |
| Pemulihan kunci owner | K-22 | secure storage + cadangan terenkripsi + kode pemulihan; Google re-auth tidak cukup; kunci+kode hilang berarti izin baru tidak bisa diterbitkan dan dukungan tidak dapat memulihkan |
| Tanda tangan delta | K-15, K-22 | delta valid diterima; tanda tangan salah, perangkat dicabut, replay, atau izin diubah ditolak |
| Sinkronisasi | K-13, K-14 | premium: delta hanya diteruskan; kasir tetap transaksi saat API mati; kirim ulang idempotent; konflik uang/stok ditolak |
| Pending relay | K-14 | premium: internet mati saat transaksi; delta pending; transaksi tetap jalan; saat online terkirim berurutan; status pending terlihat |
| Banyak akun | K-12, K-14 | premium: 100 akun mencatat riwayat dan menambah stok saat offline; data tergabung setelah online; tidak tercampur dengan owner lain |
| Pending lama | K-16 | simulasi offline berbulan-bulan; outbox tidak hilang; banner dan notifikasi lokal tetap muncul; notifikasi tidak bisa dimatikan permanen |
| Urutan dan konflik | K-14 | delta diurutkan dengan nomor perangkat dan HLC; stok tidak ganda; opname bertabrakan ditandai konflik |
| Aplikasi utama | K-02, K-03 | owner (tanpa akun atau login Google) membuka fitur sesuai tier; mode karyawan hanya premium dan menampilkan fitur/toko/izin yang diberikan |
| Aplikasi owner | K-02, K-21 | premium; tanpa core logic dan database transaksi; offline hanya cache bertanda tangan; tidak bisa menghitung ulang; manajemen akun butuh online |
| Aplikasi Python lama | K-19 | setelah Flutter stabil, aplikasi lama tetap tersimpan sebagai arsip/acuan; tidak dihapus atau dimigrasikan paksa |
| Distribusi | K-17 | satu AAB/EXE/aplikasi Mac; ukuran diukur; tidak ada paket layout atau login online untuk fitur dasar |
| Paket aset opsional | K-17 | hanya jika pengukuran membuktikan perlu; hanya aset statis; tanpa kode/fitur; tidak mengunci fitur inti saat offline |
| Kepatuhan iOS | K-17 | tanpa executable code; aset/ODR; App Store 2.5.2 terpenuhi |
| Play Billing | K-11 | hanya diuji di Dart, bukan web; langganan, restore, acknowledge, perpanjangan, pembatalan; tanpa tautan pembayaran eksternal |
| Lisensi offline | K-11 | token + hitung mundur; jam mundur tidak memperpanjang; koreksi saat online |
| Langganan berakhir | K-03, K-11 | fitur premium terkunci, kasir/data lokal tetap; delta pending dikirim lebih dulu lalu sync berhenti |
| Hapus akun | K-18 | berlaku untuk akun gratis dan berbayar; hapus akun di aplikasi dan tautan web; metadata, kunci publik/wrapped key, dan amplop dihapus; data lokal dijelaskan |
| Data safety | K-13, K-18 | deklarasi akun (termasuk identitas Google pengguna gratis), lisensi, perangkat, kunci/wrapped key, dan amplop terenkripsi; tidak ada data bengkel atau kuota gratis di server |
| Retensi dan PDP | K-18 | privacy notice dan persetujuan saat pembuatan akun gratis/berbayar; dasar pemrosesan, retensi, hak akses/ekspor/koreksi/hapus, prosedur insiden |
| Harga | K-20, K-21 | harga satu tier premium; halaman harga menjelaskan perangkat owner dan perangkat karyawan |
| Batas web | K-01 | web sudah memuat header/registry/ganti toko/gating serta prototipe akun, lisensi, perangkat, relay, snapshot, dan arsip; Play Billing, secure storage, notifikasi sistem, kunci perangkat sungguhan, dan relay lintas perangkat nyata tidak diuji di web; loopback tidak dilonggarkan |
| Protokol | K-01, K-22 | kode protokol web (HLC, tanda tangan, wrapped key, snapshot, replay outbox) sudah ada sebagai acuan; dokumen test vector dan implementasi Dart tetap wajib diselesaikan sebelum sync Dart |

## Gerbang pilot (sebelum akun, lisensi, relay)

- Dijalankan setelah web 2.7.0 menyelesaikan header, registry, ganti toko, dan
  gating lokal. Prototipe web akun/lisensi/relay sudah dibuat lebih awal atas
  permintaan pemilik; pilot tetap menjadi **gerbang sebelum port Dart, rilis
  premium, dan APK**, bukan gerbang pembuatan prototipe web.
- Ajak **1–3 bengkel nyata** memakai alur gratis selama **2–4 minggu**.
- Kriteria lulus: dipakai harian, tidak ada kehilangan data P0, backup/restore
  berhasil, dan pemilik dapat menjelaskan kebutuhan karyawan, multi-toko, serta
  sync.
- Jika gagal: perbaiki inti dan jangan mulai akun/lisensi/relay. Jika kebutuhan
  tidak terbukti, potong fitur premium yang tidak dipakai.
- Hasil pilot dan keputusan lanjut/tidak lanjut dicatat.

## Uji akhir pemantapan

Dilakukan sekali setelah fitur web selesai dan build web berhasil.

1. Jalankan `pytest` pada `.venv` (termasuk `tests/test_premium_web.py`).
2. Buat database baru dari nol dan jalankan integrity check.
3. Uji manual web: kasir, pembayaran, retur, void, stok, laporan, pengaturan,
   serta backup/restore lokal dan rollback.
4. Uji manual halaman Premium: ID owner + salin + QR, aktivasi/perpanjangan,
   pembuatan akun (password acak + salin semua), login hub dan login perangkat
   karyawan, pendaftaran/pencabutan perangkat, hub toko, buat/ganti kunci toko,
   snapshot, konflik, arsip semua toko, dan gating fitur saat gratis.
5. Perbaiki bug, lalu ulangi hanya tes yang gagal.
6. Build web ulang bila ada perbaikan.

Tidak diuji pada tahap ini: APK, Android, printer, scanner fisik, Telegram
jaringan sungguhan, perangkat fisik, Play Billing, secure storage, notifikasi
sistem, kunci perangkat sungguhan, dan relay lintas perangkat nyata.
Backup/restore lokal **tetap diuji** sebagai P0, termasuk backup manual gratis
dan penolakan backup terjadwal di paket gratis.

## Kriteria selesai

- Tidak ada bug P0/P1 yang terbuka pada alur uang, stok, nota, dan laporan.
- `pytest` `.venv` lulus.
- Database baru dapat dibuat dan lulus integrity check.
- Kasir dan stok tetap benar pada uji konkurensi.
- Build web berhasil dan halaman utama berjalan.
- Backup/restore lokal dan rollback lulus sebagai P0.
- Tidak ada rahasia baru di repo.
- README dan changelog sesuai.
- Gap perangkat/APK/sync premium dan hasil uji UI web manual dicatat.
- Pilot 1–3 bengkel dijalankan dan keputusan lanjut/tidak lanjut dicatat sebelum
  port Dart, rilis premium, dan APK. Prototipe web akun/lisensi/relay sudah ada;
  pilot menilai apakah fitur itu dibawa ke Dart.

## Di luar lingkup

- APK, Android, kamera, dan perangkat fisik.
- Printer fisik dan pengujian cetak.
- Telegram jaringan sungguhan dan pengiriman jarak jauh; gating premium dan
  antrean lokal sudah diuji. Skenario backup ada di bagian 7. Backup/restore
  lokal **termasuk lingkup P0**.
- Play Billing, secure storage, notifikasi sistem, kunci perangkat sungguhan,
  relay lintas perangkat nyata, dan LAN; semuanya diuji di Dart, bukan web.
- Port Dart/Flutter dan build APK; prototipe web multi-toko, akun, premium, dan
  sinkronisasi sudah ada dan pengujiannya ada di bagian 7.
- Fitur baru; pemantapan tidak menambah fitur.

## Risiko

- Pemantapan yang ditunda dapat menemukan masalah setelah fitur dibangun.
- Tanpa APK, perilaku mobile belum diketahui.
- Data dummy tetap harus dibackup sebelum perubahan besar; backup/restore P0
  diuji agar kegagalan restore tidak menimpa data aktif.
- Uji perangkat fisik dan printer belum tercakup.
- Web loopback-only tidak membuktikan perilaku mobile, secure storage, atau
  relay; jangan menganggap web sebagai bukti kesiapan sync premium.
- Pilot dapat menunjukkan bahwa sebagian fitur premium tidak dibutuhkan; itu
  adalah hasil yang sah dan harus memotong lingkup, bukan dipaksakan.

## Dokumen terkait

- `RENCANA_MULTI_TOKO_PREMIUM.md` — rencana multi-toko, akun, dan fitur premium.
- `RENCANA_PENGEMBANGAN_TAHAP_FINAL.md` — arah Flutter PusatkuPOS.
