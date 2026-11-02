# Rencana Pemantapan

Status: **siap dimulai — fitur web 2.8.0 sudah dibangun**. 2026-11-03.

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
- Nomor versi rilis pemantapan ditentukan setelah fitur web 2.8.0 selesai.

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

Dijalankan setelah fitur di `RENCANA_MULTI_TOKO_PREMIUM.md` dibangun. Tidak ada
uji fitur ini selama fase build web 2.8.0.

| Area | Uji |
| --- | --- |
| Isolasi | 3 toko; nota, stok, pelanggan, karyawan, dan laporan tidak tercampur |
| Registry | tambah toko, toko aktif, registry rusak, toko hilang |
| Ganti toko | posisi di dalam Menu, satu/banyak toko, konfirmasi perubahan, offline |
| Izin | pemilik dapat menambah toko; karyawan hanya melihat toko yang ditugaskan |
| Premium | gratis tidak bisa menambah toko; premium tanpa batas toko; login Google wajib untuk pemilik |
| Gating | gratis tidak bisa membuka modul premium; trial membuka mode demo |
| Kuota | 20 klik WA; klik ke-21 ditolak; reinstall tidak mereset kuota |
| Free tier | tanpa iklan dan tanpa panggilan API |
| Header | nama + printer, alamat, alamat kosong, layar sempit, ganti toko |
| Backup | 3 toko menjadi satu ZIP, checksum, manifest, batas Telegram |
| Restore | satu arsip memunculkan semua toko; satu database rusak membatalkan semua |
| Rollback | restore gagal tidak menghilangkan data lama |
| Backup otomatis | jadwal lokal, Telegram, dan cloud sesuai paket |
| Login | tanpa login untuk toko tunggal; Google untuk pemilik multi-toko; token aman; offline |
| Logout | sesi/token terhapus, sync berhenti, data lokal dan PIN tetap ada |
| Reinstall | hapus aplikasi, pasang ulang, restore arsip memunculkan semua toko |
| Sinkronisasi | kasir tetap transaksi saat API mati; kirim ulang idempotent; konflik uang/stok ditolak |
| Owner/employee app | owner read-only; karyawan hanya menulis absensi, status, dan catatan sesuai izin |

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
- Backup/restore, Telegram, dan retensi.
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
