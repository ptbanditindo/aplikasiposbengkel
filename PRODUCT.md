# BengkelPOS Radiator

Produk kasir dan pembukuan untuk bengkel radiator UMKM. Satu perangkat, data
lokal, tanpa internet.

## Pengguna dan pekerjaan

- **Pemilik bengkel** memeriksa uang masuk, piutang, stok, gaji, dan follow-up.
- **Kasir** mencatat servis atau pembelian sparepart dalam beberapa langkah,
  memilih pelanggan dan unit, lalu menyimpan serta mencetak nota.
- Pekerjaan berulang terjadi di konter, sering sambil berdiri, di ponsel
  Android maupun laptop/PC kasir. Kecepatan scan dan ketepatan angka lebih
  penting daripada ekspresi visual.

## Kebenaran produk

- Mata uang Rupiah, angka tabular, nota bernomor, dan riwayat yang tidak boleh
  hilang.
- Data pelanggan, unit, servis, stok, karyawan, supplier, dan piutang saling
  terhubung; UI tidak boleh menyembunyikan keterkaitan itu.
- Backup, pemulihan, PIN, dan data lokal adalah janji utama produk.
- Semua teks memakai bahasa kerja bengkel berbahasa Indonesia.

## Batasan

- Offline-first: font dan aset dibundel, tanpa CDN.
- Berjalan di WebView Android dan browser desktop.
- Aplikasi dipakai seharian di ruang terang; tema terang adalah bawaan, tema
  gelap tetap tersedia, dengan lima pilihan tema warna: navy-oranye (bawaan),
  charcoal-kuning, biru-teal, putih, dan hitam.
- Backend, API, dan perilaku bisnis tidak boleh berubah karena pekerjaan UI.

## Mode permukaan

Seluruh permukaan aplikasi adalah **Operate**: pengguna menyelesaikan tugas.
Konsistensi, kepadatan yang terbaca, dan kejelasan aksi utama menang atas
ekspresi. Identitas hidup di detail presisi, bukan di dekorasi.
