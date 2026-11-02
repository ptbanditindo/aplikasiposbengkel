# Surface: entire app shell

- Scope: semua view, navigasi, modal, form, tabel, dan state di `frontend/`.
- Visitor mode: Operate.
- Audience: pemilik dan kasir bengkel radiator; dipakai harian di konter.
- Job: mencatat transaksi, memeriksa uang/piutang/stok, dan menindaklanjuti
  pelanggan tanpa kehilangan konteks.
- Constraints: offline, WebView Android, backend tidak berubah, teks Indonesia.

## Chosen direction

Tembaga & Grafit. Rel grafit gelap dengan penanda tembaga, permukaan batu hangat,
tipografi Barlow/Barlow Condensed, tabel bergaris rapat, dan lempeng buku kas.
Dipilih pengguna dari tiga arah; tata letak boleh dirombak, tema terang bawaan.

## Direction contract

THESIS: Buku kerja bengkel yang bisa dioperasikan: padat, bergaris, tenang;
menolak dasbor kartu seragam dan POS pastel.

OWN-WORLD: Rel grafit (#1C1814) dengan penanda tembaga; ground batu hangat dan
permukaan putih; tembaga #A4501F hanya untuk aksi utama, menu aktif, fokus, dan
status hidup; garis 1px, radius 7/10px; Barlow Condensed untuk judul, label
kolom, dan angka besar; Barlow tabular untuk data.

STORY: Kasir melihat uang hari ini, stok menipis, dan follow-up dalam satu
pandangan; mencatat transaksi dalam empat langkah; pemilik memercayai buku kas.

FIRST VIEWPORT: Rel grafit di kiri dengan penanda tembaga pada menu aktif;
kepala halaman "Ringkasan hari ini"; satu lempeng buku kas bergaris untuk unit,
sparepart, tunai, transfer, dan hutang; lempeng stok dan gaji di bawahnya;
aksi utama berada di kepala halaman.

FORM: arah kedua dari tiga arah yang dipilih pengguna; code-led.
seed: none (unavailable)

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.
