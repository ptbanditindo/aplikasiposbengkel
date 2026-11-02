# Rencana Pengembangan Fitur Premium PusatkuPOS

Status: **rencana aktif — belum diimplementasikan**. 2026-11-03.

Produk: **PusatkuPOS**. Aplikasi 2.7.0 saat ini tetap **BengkelPOS Radiator**.

## Ringkasan keputusan

- **Premium:** Karyawan, Supplier, Follow up, semua tombol WhatsApp, dan backup
  otomatis.
- **Trial:** 20 klik WhatsApp total, tanpa batas waktu, tidak bisa direset atau
  ditambah ulang.
- **Kuota:** 1 klik WhatsApp = 1 kuota. Kuota dipotong saat tombol/link `wa.me`
  dibuka, bukan saat pesan benar-benar terkirim.
- **Setelah trial:** premium membuka pesan unlimited dan seluruh modul premium.
- **Gratis:** lokal penuh, satu perangkat, tanpa API, dan **tanpa iklan sama
  sekali** walaupun perangkat terhubung internet.
- **Premium juga mencakup** multi-tenant, sinkronisasi API, multi-device, serta
  aplikasi owner/karyawan sesuai rencana induk.

## Batas gratis, trial, dan premium

| Area | Gratis | Trial | Premium |
| --- | --- | --- | --- |
| Kasir, stok, pelanggan, unit, jasa, laporan | Ya | Ya | Ya |
| Backup manual dan restore | Ya | Ya | Ya |
| PIN dan pengaturan lokal | Ya | Ya | Ya |
| Karyawan, Supplier, Follow up | Tidak | Demo | Ya |
| Tombol WhatsApp | Tidak | 20 klik total | Unlimited |
| Backup otomatis | Tidak | Demo | Ya |
| Multi-device | Tidak | Tidak | Ya |
| Sinkronisasi API | Tidak | Untuk kuota/lisensi | Ya |
| Aplikasi owner/karyawan | Tidak | Tidak | Ya |
| Iklan | Tidak ada | Tidak ada | Tidak ada |

Trial membuka modul premium sebagai demo. Setelah 20 klik WhatsApp habis,
seluruh fitur premium terkunci sampai pembelian. Data lokal tidak dihapus.

## Fitur premium

### 1. Karyawan

- Data karyawan, peran, penugasan mekanik/kasir, komisi, gaji, dan performa.
- Aplikasi/akun karyawan untuk absensi, penugasan, status pengerjaan, dan
  komisi sesuai izin.
- Data karyawan tidak ikut ke perangkat gratis.

### 2. Supplier

- Data supplier, relasi supplier–barang, follow up reseller, dan riwayat
  supplier.
- Tombol WhatsApp supplier memakai kuota yang sama dengan tombol WA lain.

### 3. Follow up

- Follow up pelanggan, garansi, servis berkala, prospek, piutang, dan reseller.
- Hasil follow up dan pengingat.
- Semua pengiriman WhatsApp dari modul ini memakai kuota.

### 4. Semua tombol WhatsApp

- Mencakup struk, follow up, piutang, garansi, reseller, supplier, dan tombol
  WhatsApp lain di aplikasi.
- 1 klik = 1 kuota, termasuk saat pengguna membatalkan atau WhatsApp gagal
  dibuka. Tidak ada pengembalian kuota.

### 5. Backup otomatis

- Backup terjadwal lokal, Telegram, dan opsi cloud premium.
- Backup manual dan restore tetap tersedia untuk pengguna gratis.
- Sinkronisasi bukan pengganti backup; backup lokal tetap menjadi cadangan
  utama.

### 6. Multi-tenant, sinkronisasi, dan multi-device

- Satu tenant per bengkel; data terpisah antar bengkel.
- Hub kasir mengirim delta transaksi ke API developer; owner melihat laporan
  dari cloud.
- Multi-device hanya premium; perangkat tambahan mengikuti aturan satu penulis
  untuk uang dan stok.
- Kasir tetap offline-first: API mati tidak menghentikan transaksi.

## Kuota trial

- Total kuota: **20 klik WhatsApp**.
- Tidak ada batas waktu; trial berakhir saat kuota habis.
- Tidak ada penambahan ulang, reset, atau kuota harian/bulanan.
- Kuota dihitung saat tombol WA ditekan dan link `wa.me` dibuat.
- Aplikasi tidak dapat memastikan pesan benar-benar terkirim karena WhatsApp
  berada di luar aplikasi.
- Kuota yang sudah terpakai tidak dikembalikan jika pengguna membatalkan,
  WhatsApp tidak terpasang, atau pesan gagal dikirim.
- Aplikasi menampilkan sisa kuota dan peringatan sebelum habis.
- Setelah kuota 0, tombol WA dan modul premium terkunci sampai pembelian.
- Untuk mencegah reset dengan reinstall, kuota harus terikat akun/lisensi atau
  penyimpanan aman, bukan hanya data aplikasi biasa.

## Free tier

- Berjalan lokal, satu perangkat, tanpa panggilan API.
- Kasir, stok, pelanggan, unit, jasa, laporan, PIN, pengaturan, backup manual,
  dan restore tetap tersedia.
- Karyawan, Supplier, Follow up, tombol WA, dan backup otomatis terkunci.
- **Tanpa iklan sama sekali:** tidak ada banner, popup, video, ad SDK, jaringan
  iklan, atau permintaan latar untuk iklan, termasuk saat online.
- Tidak ada pengiriman data ke API developer.

## Arsitektur premium

```text
Aplikasi Flutter (Android/Windows/Mac)
        │
        ├─ SQLite lokal + outbox + kuota lokal
        │
        ├─ Hub kasir ── LAN ── owner/karyawan di bengkel
        │
        └─ API developer (HTTPS)
                ├─ akun, tenant, lisensi, perangkat
                ├─ validasi kuota trial
                ├─ penerimaan delta/snapshot
                ├─ laporan owner/karyawan
                └─ object storage backup
```

- **Client:** Flutter + SQLite.
- **API:** FastAPI + PostgreSQL; Python hanya di server, tidak masuk paket
  aplikasi.
- **Auth:** login tanpa akun untuk pemakaian lokal, Google untuk akun premium,
  undangan karyawan, token perangkat, dan sign out per perangkat. Sign out
  menghentikan sync di perangkat itu tanpa menghapus data lokal.
- **Kuota:** dicatat lokal dan disinkronkan ke server saat online; server
  menjadi acuan untuk mencegah reset.
- **Lisensi:** masa tenggang offline; kegagalan API tidak mengunci kasir lokal.
- **Pembayaran:** penyedia pembayaran dipilih saat tahap lisensi.

## Alur trial dan pembelian

1. Pengguna membuat akun trial dan mendapat 20 kuota.
2. Modul premium terbuka dalam mode demo.
3. Setiap klik WA mengurangi kuota satu.
4. Saat kuota habis, fitur premium terkunci dan muncul pilihan pembelian.
5. Pembelian membuka pesan unlimited dan seluruh modul premium.
6. Data lokal tetap tersimpan selama trial berakhir.
7. Jika langganan berakhir, kasir lokal tetap jalan; fitur premium mengikuti
   kebijakan paket.

## Aturan konflik dan sinkronisasi

- Hub kasir adalah satu-satunya penulis nota, pembayaran, retur, dan stok.
- Owner app read-only pada tahap awal.
- Karyawan hanya menulis absensi, status tugas, catatan, dan permintaan stok.
- Uang dan stok tidak memakai “tulisan terakhir menang”.
- Waktu server menjadi acuan urutan; waktu lokal untuk tampilan.
- Pengiriman ulang harus idempotent agar nota/stok tidak ganda.

## Tahapan

1. **Fondasi premium:** akun, tenant, lisensi, perangkat, dan kuota trial.
2. **Gating fitur:** kunci Karyawan/Supplier/Follow up/WA/backup otomatis untuk
   gratis; buka untuk trial/premium.
3. **Kuota WA:** hitung klik, tampilkan sisa, kunci saat habis, sinkron kuota.
4. **Pembelian:** paket unlimited, aktivasi, masa tenggang, dan penurunan paket.
5. **Owner app:** laporan, stok, piutang, gaji read-only.
6. **Employee app:** absensi, penugasan, status, komisi, izin bertahap.
7. **Multi-device dan sync:** hub, outbox, idempotency, konflik, retensi.
8. **Backup otomatis premium:** lokal terjadwal, Telegram, cloud.
9. **Hardening:** keamanan tenant, audit, uji offline, uji kuota, uji migrasi.

## Kriteria selesai premium MVP

- Free tier tidak menampilkan iklan dan tidak memanggil API.
- Free tier tidak bisa membuka modul premium.
- Trial memberi 20 klik WA; kuota tidak bisa ditambah dengan reinstall.
- Klik WA ke-21 ditolak dan modul premium terkunci.
- Premium membuka pesan unlimited dan semua modul.
- Kasir tetap transaksi saat API mati total.
- Backup manual tetap bisa dipulihkan tanpa cloud.
- Data lama tidak hilang saat trial berakhir.

## Risiko

- Kuota lokal bisa diakali jika tidak terikat akun/lisensi.
- `wa.me` tidak bisa memastikan pesan terkirim; kuota dihitung saat klik.
- Gating fitur lama berisiko mengunci data pengguna yang sudah ada.
- Konflik multi-device jika uang/stok ditulis dari beberapa perangkat.
- Biaya API, database, storage, dan dukungan.
- Kebocoran data tenant jika isolasi akses lemah.

## Keputusan yang masih terbuka

- Harga paket premium dan apakah sekali bayar atau langganan.
- Batas perangkat untuk akun premium.
- Apakah data Karyawan/Supplier/Follow up lama tetap bisa dibaca/diekspor saat
  fitur terkunci.
- Kapan kuota disinkronkan ke server dan bagaimana perilaku saat offline lama.
- Apakah backup otomatis premium mencakup Telegram, cloud, atau keduanya.
- Nasib aplikasi Python lama setelah versi Flutter stabil.
