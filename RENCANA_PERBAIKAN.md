# Rencana Perbaikan BengkelPOS Radiator

Dokumen ini adalah **rencana kerja**, bukan hasil audit. Jangan mengerjakan audit
bug lebih dulu. Audit hanya boleh dimulai setelah seluruh perbaikan P-01 sampai
P-10 selesai, lulus test, dan disetujui pemilik.

Dokumen ini ditulis agar bisa dikerjakan oleh AI lain tanpa konteks percakapan
sebelumnya. Ikuti urutan, aturan, dan kriteria penerimaan di setiap bagian.

---

## 0. Aturan wajib sebelum mulai

Baca dan patuhi `ATURAN_PEKERJAAN.md`. Ringkasan yang mengikat:

1. Ada dua varian produk dengan kode backend yang sama, tetapi database
   terpisah dan **tanpa sinkronisasi**:
   - Web lokal di PC kasir: Pydantic 2.x, FastAPI terbaru, Python 3.12.
   - APK Android: Pydantic 1.10.18, FastAPI 0.115.0, SQLAlchemy 2.0.36,
     uvicorn 0.30.6, Python 3.10, hanya paket pure-Python.
2. Setiap perubahan backend harus lulus pytest di **kedua** stack. Pin APK ada
   di `android/app/build.gradle.kts`, bukan di `requirements.txt`.
3. Satu temuan/perbaikan = satu commit kecil. Pesan commit memuat ID, misalnya
   `P-01: hilangkan strip label pada struk mobil`.
4. Test-first: tulis test yang gagal, buktikan gagal karena bug/perilaku lama,
   perbaiki, lalu jalankan seluruh pytest.
5. Uang hanya dihitung di backend memakai `Decimal` dan `ROUND_HALF_UP`.
   Jangan menambah rumus uang baru di JavaScript atau Kotlin.
6. Jangan membaca/menampilkan `.env` asli atau database asli. Test wajib memakai
   database sementara dan `BACKUP_DIR` sementara.
7. Jangan `git push`, jangan ganti/merge branch, jangan install paket global
   tanpa izin.
8. Jika Gradle/JDK/printer/perangkat tidak tersedia, tulis **"belum
   diverifikasi"** beserta langkah uji manual. Jangan mengklaim terverifikasi.
9. Akhiri setiap fase dengan ringkasan: file diubah, test ditambah, hasil pytest
   di dua stack, perubahan yang terlihat pengguna, risiko tersisa. Lalu berhenti
   dan tunggu instruksi.

Baseline saat dokumen ini dibuat (2026-10-31):

- Schema `PRAGMA user_version = 10` (`database/migrations.py:20`).
- 272 test pytest lulus di jalur desktop (Pydantic 2).
- APK debug 2.2.2 / versionCode 5 sudah dibangun, tetapi belum diuji di
  perangkat fisik.
- Halaman Follow-up masih ada di navigasi dan dashboard sudah memakai judul
  "Ringkasan hari ini".

---

## 1. Peta item pekerjaan

| ID | Permintaan pemilik | Dampak utama |
|----|--------------------|--------------|
| P-01 | Struk mobil utuh tidak boleh mencetak strip "POTONG DI SINI" | Backend struk + pembuatan label |
| P-02 | Daftar pelanggan baru tidak menanyakan izin WhatsApp | Form pelanggan |
| P-03 | Tombol hapus kendaraan + warna pada bagian pilih unit | Backend unit, UI POS, CSS |
| P-04 | Bagian keluhan awal berwarna + tombol simpan | UI POS |
| P-05 | DP boleh tanpa tanggal; pelunasan bisa dicatat setelah pekerjaan selesai | UI DP, navigasi pelunasan |
| P-06 | Tampilkan seluruh nota untuk dicek (Benar/Edit) sebelum tombol simpan muncul | UI POS |
| P-07 | Tombol cetak mencetak lalu otomatis membuka WhatsApp berisi struk lengkap; tidak ada tombol WhatsApp terpisah | Struk, WA, UI |
| P-08 | Tautan WA memakai `https://wa.me/62...?text=...` dan tidak diblokir WebView | JS + Android native |
| P-09 | Halaman Follow-up dihapus; cukup ringkasan dengan judul "FOLLOW UP" | Navigasi + dashboard |
| P-10 | Setiap barang/sparepart punya durasi servis seperti jasa | Migrasi + stok + POS + follow-up |
| P-11 | Verifikasi, dokumentasi, build APK | Test + docs + build |
| A-01 | Audit bug setelah perbaikan selesai | Audit, bukan bagian sekarang |

Urutan pengerjaan yang disarankan: P-01, P-02, P-03, P-04, P-05, P-06, P-08,
P-07, P-09, P-10, P-11. P-08 dikerjakan sebelum P-07 agar tautan WA sudah bisa
dibuka saat alur cetak otomatis diuji.

---

## 2. Detail pekerjaan

### P-01 — Jangan cetak strip label untuk mobil utuh

**Masalah**

- `services/pos_service.py:110` memanggil
  `customer_service.ensure_unit_label(...)` untuk semua unit, termasuk
  `MOBIL`. Akibatnya mobil utuh mendapat `label_radiator`.
- `services/receipt_service.py:76-109` membuat strip label setiap kali
  `unit.label_radiator` terisi, lalu menambahkan teks `POTONG DI SINI`,
  pelanggan, nomor HP, unit, kode label, dan `(Radiator ...)`.
- Contoh yang dilaporkan: mobil Avanza dengan `RAD-20261031-002` tetap
  mencetak strip di bawah nota. Itu tidak berguna karena yang diservis adalah
  satu kendaraan utuh, bukan radiator copotan.

**Perilaku yang diinginkan**

- Strip label hanya dibuat untuk unit `RADIATOR_ONLY` (radiator copotan).
- Unit `MOBIL` tidak boleh mendapatkan label baru.
- Data label lama pada unit `MOBIL` (jika sudah ada) tidak boleh ikut tercetak
  sebagai strip.
- Riwayat, pencarian, dan data lama tidak boleh dihapus.

**Perubahan**

1. Backend:
   - Ubah pemanggilan di `services/pos_service.py:110` agar hanya membuat label
     bila `unit.unit_type == "RADIATOR_ONLY"`.
   - Tambahkan penjaga di `services/receipt_service.py` pada `_labels()`:
     kembalikan `[]` bila `unit.unit_type != "RADIATOR_ONLY"`, walaupun
     `label_radiator` terisi.
   - Jangan mengubah format strip untuk `RADIATOR_ONLY`.
2. Test:
   - Test baru: buat pelanggan + unit `MOBIL`, simpan transaksi, lalu pastikan
     `receipt["labels"] == []`, teks `struk_58` tidak memuat `POTONG DI SINI`,
     dan `label_radiator` unit baru tetap kosong.
   - Test baru/regresi: unit `RADIATOR_ONLY` tetap menghasilkan satu strip label
     dengan kode `RAD-...` dan teks `POTONG DI SINI`.
   - Test khusus data lama: set `label_radiator` manual pada unit `MOBIL`,
     lalu pastikan struk tetap tanpa strip.
3. UI:
   - Tidak ada perubahan tampilan yang diminta selain hilangnya strip pada
     hasil cetak/pratinjau mobil.

**Kriteria penerimaan**

- Nota mobil utuh dicetak tanpa blok `POTONG DI SINI`.
- Nota radiator copotan tetap mencetak label fisik.
- Tidak ada perubahan angka total, nomor nota, atau data pelanggan.

**Commit**: `P-01: hilangkan strip label radiator pada struk mobil utuh`

---

### P-02 — Pendaftaran pelanggan baru tidak meminta izin WhatsApp

**Masalah**

- `frontend/index.html:1135` menampilkan switch
  `Boleh dihubungi lewat WhatsApp` (`#custWaConsent`) di form tambah pelanggan.
- `frontend/js/app.js` mengirim `wa_consent` dari switch tersebut saat
  membuat pelanggan.
- Pemilik meminta pendaftaran pelanggan baru tidak menanyakan izin WA.

**Perilaku yang diinginkan**

- Form tambah pelanggan hanya meminta nama, nomor HP, dan alamat.
- Pelanggan baru otomatis dianggap boleh dihubungi lewat WhatsApp, mengikuti
  default backend `CustomerCreate.wa_consent = True`.
- Pengaturan izin per pelanggan tetap bisa diubah nanti dari detail pelanggan
  (fitur yang sudah ada), bukan saat pendaftaran.

**Perubahan**

1. `frontend/index.html`: hapus baris switch `#custWaConsent` dari
   `#customerForm`.
2. `frontend/js/app.js`: hapus pembacaan `$('#custWaConsent').checked` dari
   payload pembuatan pelanggan dan hapus reset `#custWaConsent.checked = true`.
   Pastikan tidak ada referensi lain ke `#custWaConsent` di form tambah.
3. Backend tidak perlu diubah: default tetap `True`. Jangan menghapus endpoint
   `PUT /customers/{id}/consent` atau switch izin di detail pelanggan.
4. Test:
   - Frontend tidak punya test framework; lakukan pemeriksaan manual dan
     `node --check frontend/js/app.js`.
   - Test backend yang ada untuk `wa_consent` tetap lulus; tambahkan test bila
     ada yang mengasumsikan form selalu mengirim nilai.

**Kriteria penerimaan**

- Form tambah pelanggan tidak menampilkan pertanyaan izin WhatsApp.
- Pelanggan baru tersimpan dengan `wa_consent = true` dan bisa diubah dari
  detail pelanggan.

**Commit**: `P-02: hapus pertanyaan izin WhatsApp saat daftar pelanggan`

---

### P-03 — Tombol hapus kendaraan dan warna bagian pilih unit

**Masalah**

- Di POS, unit pelanggan hanya ditampilkan sebagai kartu pilihan
  (`renderUnits()` di `frontend/js/app.js`), tanpa tombol hapus.
- Backend hanya punya `GET /customers/{id}/units` dan `POST /units`; tidak ada
  endpoint hapus/arsip (`api/customer_routes.py:116-123`).
- Bagian "Pilih unit servis" belum punya warna pembeda seperti blok
  "Rincian pengerjaan".
- Menghapus unit yang sudah punya riwayat servis secara hard delete akan
  merusak relasi nota. Jangan lakukan hard delete untuk unit yang punya
  riwayat.

**Perilaku yang diinginkan**

- Setiap kartu unit punya tombol hapus.
- Unit yang dihapus hilang dari daftar pilihan POS dan daftar unit pelanggan,
  tetapi riwayat nota lama tetap utuh dan tetap bisa menampilkan unit tersebut.
- Konfirmasi sebelum menghapus.
- Bagian pilih unit memakai latar/border berwarna, konsisten dengan tema terang
  dan gelap.

**Perubahan backend**

1. Migrasi baru (schema menjadi 11):
   - Tambah kolom `archived_at DATETIME NULL` pada `vehicle_or_units`.
   - Jangan hapus baris unit. Ini adalah soft delete/arsip.
   - Pastikan migrasi idempotent dan mengikuti pola migrasi 001-010.
2. `database/models.py`: tambah `archived_at` pada `VehicleOrUnit`.
3. Repository/service pelanggan:
   - `list_units()` dan daftar unit pada overview pelanggan hanya
     mengembalikan unit dengan `archived_at IS NULL`.
   - Tambah `archive_unit(db, unit_id, operator)`:
     - buka transaksi `with db.begin()` + `begin_immediate(db)`;
     - cari unit; jika tidak ada -> `NotFoundError`;
     - jika sudah diarsipkan, perlakukan idempoten;
     - set `archived_at = datetime.now()`;
     - catat audit event (alasan "Unit dihapus dari daftar");
     - flush dan refresh.
   - Jangan mengubah data `service_records`.
4. API:
   - Tambah `DELETE /units/{unit_id}` dengan status 204 (atau 200 dengan body
     unit jika pola proyek menghendaki).
   - Endpoint tetap memerlukan autentikasi.
5. `services/pos_service.py`: saat membuat transaksi, tolak unit yang sudah
   diarsipkan dengan pesan jelas, misalnya
   "Unit ini sudah dihapus dari daftar pelanggan."

**Perubahan frontend**

1. `renderUnits()`:
   - Tambah tombol kecil "Hapus" pada setiap kartu. Tombol harus
     `event.stopPropagation()` agar tidak memilih unit.
   - Tombol hapus memakai konfirmasi
     "Hapus unit <nopol/label>? Riwayat servis yang sudah ada tetap tersimpan."
2. Aksi hapus:
   - Panggil endpoint DELETE.
   - Setelah sukses, muat ulang unit pelanggan.
   - Jika unit yang dihapus sedang dipilih, kosongkan `state.selectedUnit`,
     sembunyikan kartu keluhan dan rincian pengerjaan, lalu tampilkan toast.
3. CSS:
   - Beri kelas khusus pada `#unitCard`, misalnya `step-card--unit`, dengan
     latar tint dan border tipis memakai token warna yang sudah ada.
   - Pastikan kontras teks tetap baik di tema terang dan gelap.
   - Jangan mengubah struktur tiga kolom POS atau ukuran tombol yang sudah ada
     tanpa alasan.

**Test backend**

- Unit tanpa riwayat: setelah DELETE, tidak muncul di `GET /units` dan
  `GET /customers/overview`.
- Unit dengan riwayat: setelah DELETE, nota lama tetap ada dan
  `GET /service-records/{id}` masih menampilkan unit; unit tidak muncul di
  daftar POS.
- Transaksi baru memakai unit yang sudah diarsipkan ditolak.
- Audit event tercatat.
- Migrasi dari database versi 10 ke 11 berhasil dan data lama tetap ada.

**Kriteria penerimaan**

- Tombol hapus terlihat dan berfungsi di POS.
- Unit hilang dari pilihan setelah dihapus.
- Riwayat servis lama tidak hilang.
- Bagian pilih unit punya warna yang jelas.

**Commit**: `P-03: arsipkan unit dari POS dan beri warna bagian pilih unit`

---

### P-04 — Bagian keluhan awal berwarna dan punya tombol simpan

**Masalah**

- `frontend/index.html:329-347` menampilkan kartu "Keluhan awal" tanpa warna
  khusus dan tanpa tombol simpan.
- Saat unit dipilih, `selectUnit()` langsung menampilkan kartu keluhan dan
  kartu rincian pengerjaan sekaligus. Pemilik ingin alur yang lebih tegas:
  isi keluhan, simpan, baru lanjut ke rincian.

**Perilaku yang diinginkan**

- Kartu keluhan punya latar/border berwarna, konsisten dengan kartu unit.
- Ada tombol "Simpan keluhan".
- Bagian "Rincian pengerjaan" baru muncul setelah keluhan disimpan.
- Keluhan tetap bisa diedit setelah disimpan; tombol simpan tidak perlu muncul
  ulang setiap kali mengetik.

**Perubahan frontend**

1. `frontend/index.html`:
   - Tambah kelas `step-card--complaint` pada `#complaintCard`.
   - Tambah tombol `#btnSaveComplaint` dengan teks "Simpan keluhan" di bagian
     bawah kartu, sebelum kartu rincian.
2. `frontend/js/app.js`:
   - Tambah state `complaintConfirmed` (default `false`).
   - Saat pelanggan/unit dipilih atau form direset, set `false`, sembunyikan
     `#itemsCard`.
   - `#btnSaveComplaint`:
     - validasi `#keluhanInput` tidak kosong (pesan "Keluhan awal wajib
       diisi.");
     - set `complaintConfirmed = true`;
     - tampilkan `#itemsCard`;
     - scroll ke kartu rincian;
     - toast "Keluhan disimpan.";
   - `selectUnit()` tidak lagi langsung menampilkan `#itemsCard`; hanya
     menampilkan `#complaintCard`.
   - Pastikan `saveTransaction()` tetap memvalidasi keluhan dan minimal satu
     item.
3. CSS:
   - `step-card--complaint` memakai tint warna berbeda dari unit (misalnya
     tone warning) tetapi tetap tenang dan sesuai tema.
   - Jangan memakai warna hardcoded baru; gunakan token warna yang ada atau
     tambahkan token di bagian root.

**Test**

- Manual di browser: pilih unit, rincian belum terlihat; klik simpan keluhan
  tanpa isi -> peringatan; isi -> rincian muncul; edit keluhan -> tetap bisa
  simpan transaksi.
- Manual reset POS: state kembali tersembunyi.
- `node --check frontend/js/app.js`.

**Kriteria penerimaan**

- Alur unit -> keluhan -> simpan -> rincian berjalan.
- Warna kartu keluhan terlihat dan tidak mengganggu keterbacaan.

**Commit**: `P-04: tambah warna dan tombol simpan pada keluhan awal`

---

### P-05 — DP tanpa tanggal jatuh tempo dan pelunasan setelah pekerjaan selesai

**Masalah**

- Saat memilih DP, frontend mewajibkan `#jatuhTempoInput`
  (`frontend/js/app.js:1623-1629`).
- Pemilik ingin pelanggan bisa meninggalkan mobil untuk pekerjaan lama tanpa
  harus menentukan tanggal pelunasan di muka, dan pelunasan bisa dicatat
  kapan saja setelah pekerjaan selesai.
- Backend sebenarnya sudah mengizinkan `jatuh_tempo = null`
  (`api/schemas.py:218`) dan `payment_service.record_payment()` tidak
  mensyaratkan tanggal jatuh tempo. Jadi masalah utama ada di UI dan
  keterjangkauan aksi pelunasan.

**Perilaku yang diinginkan**

- Saat DP, tanggal jatuh tempo bersifat opsional.
- Nota DP tetap tercatat sebagai piutang dan muncul di ringkasan.
- Pelunasan bisa dicatat kapan saja, tidak menunggu tanggal.
- Aksi pelunasan mudah ditemukan dari ringkasan piutang dan detail nota.
- Setelah perbaikan selesai, kasir dapat memberi tahu pelanggan bahwa
  **kendaraannya sudah selesai dikerjakan dan siap diambil**, bukan menagih
  dengan kata "hutang".

**Aturan kata-kata untuk pelanggan (wajib)**

- Pesan yang dibaca pelanggan tidak boleh memakai kata **"hutang"**,
  **"piutang"**, **"tagihan"**, **"kekurangan pembayaran"**, atau
  **"penunggak"**.
- Gunakan kalimat netral dan berorientasi pada kendaraan, misalnya:
  - "Kendaraan <unit> sudah selesai dikerjakan dan siap diambil."
  - "DP sudah kami terima."
  - "Sisa pembayaran dapat diselesaikan saat pengambilan."
  - "Silakan datang ke <bengkel> untuk pengambilan kendaraan."
- Jangan menampilkan nominal sisa sebagai ancaman. Nominal boleh disebut
  sebagai informasi pelunasan, bukan sebagai utang.
- Label **"Piutang" di dashboard internal pemilik tetap dipertahankan** karena
  itu istilah laporan, bukan pesan pelanggan. Larangan kata di atas hanya
  berlaku untuk pesan/notifikasi yang dikirim atau disalin ke pelanggan.
- Pesan tetap dibuka sebagai draf WhatsApp; tidak ada pengiriman otomatis.

**Perubahan backend (teks pesan)**

1. Ubah `services/followup_service.py` pada bagian `_message()` untuk
   `JENIS_PIUTANG`:
   - Awali pesan dengan informasi kendaraan selesai.
   - Ganti frasa "Kekurangan pembayaran" menjadi "Sisa pembayaran".
   - Jangan memakai kata "hutang", "piutang", "tagihan", atau
     "kekurangan pembayaran" di teks yang dikirim ke pelanggan.
   - Contoh hasil yang diinginkan:
     "Halo Bapak/Ibu <nama>, kendaraan <unit> dengan nota <no_nota> sudah
     selesai dikerjakan dan siap diambil di <bengkel>. DP sudah kami terima.
     Sisa pembayaran <nominal> dapat diselesaikan saat pengambilan. Terima
     kasih."
2. Buat **satu** fungsi penyusun teks "kendaraan selesai" di backend,
   misalnya `whatsapp_service.completion_wa_text(record, bengkel)`, lalu pakai
   fungsi itu untuk follow-up piutang dan aksi "Kendaraan selesai" di UI.
   Jangan menduplikasi kalimat di JavaScript.
3. Untuk nota yang sudah LUNAS, teks cukup berisi "Kendaraan ... sudah selesai
   dikerjakan dan siap diambil" tanpa menyebut pembayaran.

**Perubahan frontend**

1. Form DP:
   - Ubah label menjadi "Jatuh tempo (opsional)".
   - Hapus validasi wajib di `saveTransaction()`.
   - Tambah teks bantuan kecil: "Boleh dikosongkan. Pelunasan dicatat saat
     pekerjaan selesai."
   - Boleh tetap mengisi tanggal default sebagai saran, tetapi pengguna harus
     bisa mengosongkannya.
   - Payload tetap mengirim `jatuh_tempo: null` bila kosong.
2. Ringkasan piutang:
   - Di daftar piutang, setiap nota/baris pelanggan punya tombol "Pelunasan"
     yang membuka detail nota dan langsung mengarah ke form pembayaran.
   - Jika antarmuka saat ini sudah membuka detail nota saat baris diketuk,
     tambahkan tombol eksplisit agar aksi pelunasan terlihat.
3. Detail nota:
   - Pastikan form pelunasan yang sudah ada tetap dapat dipakai untuk nota DP
     tanpa jatuh tempo.
   - Setelah pelunasan penuh, nota berubah LUNAS dan hilang dari piutang
     (perilaku backend yang sudah ada).
4. Struk:
   - Jika `jatuh_tempo` kosong, jangan mencetak baris "Jatuh Tempo".
   - Jangan menampilkan teks "None"/"null".
5. Opsional tetapi disarankan: setelah nota DP disimpan, tampilkan tombol
   "Catat pelunasan" pada modal struk/detail agar kasir tidak perlu mencari
   menu lain.
6. Aksi "Kendaraan selesai":
   - Tampilkan tombol "Kendaraan selesai" pada detail nota dan daftar piutang
     untuk nota yang belum lunas.
   - Tombol membuka draf WhatsApp berisi teks dari
     `whatsapp_service.completion_wa_text(...)`.
   - Jangan mengirim otomatis; kasir tetap menekan kirim di WhatsApp.
   - Hormati izin WhatsApp dan nomor valid seperti alur WA lain.
   - Jangan memakai kata "hutang" atau "piutang" pada draf tersebut.

**Test backend**

- Buat nota DP dengan `jatuh_tempo = null`; simpan berhasil; status
  `BELUM_LUNAS`; piutang muncul.
- Catat pelunasan sebagian dan penuh tanpa tanggal jatuh tempo; status berubah
  dan sisa benar.
- Struk dengan jatuh tempo kosong tidak memuat baris "Jatuh Tempo".
- Teks `completion_wa_text()` untuk nota DP memuat "sudah selesai dikerjakan"
  dan "siap diambil", serta **tidak** memuat kata "hutang", "piutang",
  "tagihan", atau "kekurangan".
- Teks follow-up piutang memakai kata "Sisa pembayaran", bukan "Kekurangan
  pembayaran", dan tetap menyebut kendaraan sudah selesai.
- Test uang memakai `Decimal`; tidak ada float.

**Kriteria penerimaan**

- DP bisa disimpan tanpa tanggal.
- Pelunasan bisa dicatat kapan saja setelah pekerjaan selesai.
- Piutang dan struk menampilkan informasi yang benar.
- Pelanggan menerima informasi "kendaraan sudah selesai", bukan pesan
  berisi kata "hutang".
- Dashboard internal tetap memakai label "Piutang" sesuai permintaan pemilik.

**Commit**: `P-05: izinkan DP tanpa jatuh tempo dan mudahkan pelunasan`

---

### P-06 — Periksa seluruh nota sebelum tombol simpan muncul

**Masalah**

- Saat ini tombol `#btnSavePrint` dan `#btnSaveOnly`
  (`frontend/index.html:513-514`) langsung terlihat dan langsung menyimpan.
- Pemilik ingin melihat seluruh nota lebih dulu, memastikan benar, lalu baru
  memunculkan tombol simpan.

**Perilaku yang diinginkan**

- Alur POS: isi form -> klik "Periksa nota" -> modal menampilkan seluruh isi
  nota -> tombol "Benar" dan "Edit".
- "Benar": tutup modal, tampilkan tombol "Simpan & cetak struk" dan "Simpan
  tanpa cetak".
- "Edit": tutup modal, kembali ke form untuk diperbaiki.
- Setelah "Benar", jika data penting diubah lagi, tombol simpan disembunyikan
  dan pengguna harus memeriksa ulang.
- Tombol simpan tidak boleh bisa dipakai sebelum pemeriksaan.

**Isi modal pemeriksaan**

Tampilkan minimal:

- Nama pelanggan dan nomor HP.
- Unit (nopol/jenis atau label radiator).
- Keluhan awal dan catatan pengerjaan.
- Daftar jasa: nama, qty, harga deal, interval servis (bila ada), subtotal.
- Daftar sparepart: nama, qty, harga deal, interval servis (bila ada),
  subtotal.
- Diskon, total jasa, total part, grand total.
- Metode bayar dan jenis bayar (LUNAS/DP).
- Untuk DP: nominal DP, sisa, dan jatuh tempo bila diisi.
- Garansi: aktif/tidak, durasi, catatan.
- Semua angka uang diformat memakai helper yang ada; **jangan** menghitung
  ulang total di JS. Gunakan hasil preview backend yang sudah dipakai
  (`preview_transaction`) untuk total dan sisa.

**Perubahan frontend**

1. `frontend/index.html`:
   - Tambah modal `#notaReviewModal` (backdrop, judul "Periksa nota", isi
     ringkasan, tombol `#btnNotaEdit` "Edit" dan `#btnNotaCorrect` "Benar").
   - Sembunyikan `#btnSavePrint` dan `#btnSaveOnly` dengan kelas `hidden`
     pada keadaan awal.
   - Tambah tombol utama `#btnReviewNota` "Periksa nota" di area ringkasan.
2. `frontend/js/app.js`:
   - Tambah state `notaReviewed` (default `false`).
   - `#btnReviewNota` menjalankan validasi yang sama dengan `saveTransaction`
     (pelanggan, unit, keluhan, minimal item, format uang, DP, preview error),
     lalu membangun HTML ringkasan dari state dan hasil preview, dan membuka
     modal. Jangan memanggil API simpan.
   - `#btnNotaCorrect`: tutup modal, set `notaReviewed = true`, tampilkan kedua
     tombol simpan, fokuskan tombol simpan.
   - `#btnNotaEdit`: tutup modal, fokus ke field pertama yang perlu diperbaiki
     atau ke keluhan.
   - `invalidateNotaReview()`: set `false`, sembunyikan tombol simpan. Panggil
     pada perubahan pelanggan, unit, keluhan, catatan, tambah/hapus/ubah
     jasa/part, diskon, metode, jenis bayar, DP, jatuh tempo, dan garansi.
   - `saveTransaction()` sebagai pengaman: jika `!notaReviewed`, tampilkan
     modal pemeriksaan dan jangan simpan.
   - Setelah simpan sukses atau reset POS, set `notaReviewed = false` dan
     sembunyikan tombol simpan.
3. CSS:
   - Modal ringkasan harus nyaman dibaca di layar kecil, dengan baris label
     nilai yang rapi dan total yang tebal.
   - Jangan memakai tabel lebar yang membuat horizontal scroll berlebihan.

**Test**

- Manual browser: tombol simpan tidak terlihat sebelum "Benar"; "Edit"
  mengembalikan ke form; "Benar" memunculkan tombol; mengubah qty setelah
  "Benar" menyembunyikan tombol lagi.
- Pastikan tombol simpan tidak bisa diaktifkan lewat keyboard saat hidden.
- `node --check frontend/js/app.js`.

**Kriteria penerimaan**

- Seluruh nota dapat diperiksa sebelum disimpan.
- Tombol simpan hanya muncul setelah konfirmasi "Benar".
- Tidak ada jalan pintas yang menyimpan tanpa pemeriksaan.

**Commit**: `P-06: tampilkan pemeriksaan nota sebelum tombol simpan`

---

### P-07 — Cetak saja, lalu otomatis buka WhatsApp berisi struk lengkap

**Masalah**

- Modal struk punya tombol `#btnReceiptWhatsapp`
  (`frontend/index.html:1312`) sehingga ada dua aksi terpisah: cetak dan WA.
- `maybeOfferWhatsapp()` (`frontend/js/app.js:1892-1901`) membuka pratinjau WA
  setelah cetak, tetapi masih berupa modal dan bergantung pada
  `ops.wa_after_print`.
- `receipt.wa_text` saat ini memakai template pendek
  (`services/whatsapp_service.py:38-47`), bukan isi struk lengkap seperti nota.

**Perilaku yang diinginkan**

- Di modal struk tidak ada tombol WhatsApp terpisah. Cukup aksi cetak.
- Setelah cetak berhasil, aplikasi otomatis membuka WhatsApp ke nomor pelanggan
  dengan teks **struk lengkap**, sama isinya dengan nota yang dicetak.
- Tidak ada pengiriman otomatis di latar belakang. WhatsApp hanya dibuka pada
  layar tulis pesan; kasir tetap menekan kirim.
- Jika pelanggan tidak punya nomor valid atau tidak setuju WA, cetak tetap
  berjalan dan tidak ada upaya membuka WA.

**Perubahan backend**

1. Buat teks WA struk dari isi struk 58 mm, bukan template pendek.
   - Refactor kecil di `services/receipt_service.py`: `_build()` diberi opsi
     untuk tidak menambahkan strip label fisik.
   - Tambah fungsi/field yang menghasilkan teks nota lengkap (header bengkel,
     nomor, tanggal, pelanggan, unit, keluhan, catatan, jasa, part, total,
     pembayaran, garansi, rekening, penutup) **tanpa** blok
     `POTONG DI SINI`.
   - Gunakan fungsi ini untuk `wa_text` pada payload struk agar isi WA sama
     dengan nota.
   - Jangan mengubah `struk_58`/`struk_80` yang dipakai printer.
2. Template `wa_template` yang lama:
   - Untuk struk, hentikan penggunaan template pendek.
   - Follow-up tetap memakai pesan follow-up yang sudah ada (lihat P-09/P-10);
     jangan memaksa template struk ke follow-up.
   - Hapus opsi `wa_after_print` dari UI pengaturan karena WA sekarang otomatis
     setelah cetak. Jika field backend masih ada, jangan dipakai lagi; hapus
     referensinya di frontend.
3. Test:
   - `wa_text` memuat nomor nota, nama barang/jasa, total, status bayar, dan
     rekening.
   - `wa_text` tidak memuat `POTONG DI SINI`.
   - Untuk `RADIATOR_ONLY`, label tetap ada di struk fisik tetapi tidak wajib
     ada di teks WA (karena itu instruksi potong, bukan isi nota).
   - Link WA memakai nomor `62...` dan teks ter-encode satu kali.

**Perubahan frontend**

1. Hapus tombol `#btnReceiptWhatsapp` dari modal struk dan hapus listener-nya.
2. Ganti `maybeOfferWhatsapp()` dengan `sendReceiptToWhatsapp(receipt)`:
   - cek `receipt.wa_consent`;
   - cek nomor valid (`waDigits`);
   - cek `receipt.wa_text` tidak kosong;
   - catat upaya `DIBUKA` lewat API yang sudah ada;
   - buka tautan WA memakai helper P-08.
3. Panggil `sendReceiptToWhatsapp(receipt)` setelah cetak berhasil pada semua
   jalur: A4/browser, printer Web, Bluetooth, network, USB, dan system print.
   Jangan panggil saat pengguna memilih "Simpan tanpa cetak".
4. Jika popup/tautan diblokir:
   - jangan menampilkan modal WA baru;
   - tampilkan toast yang jelas dan sediakan teks untuk disalin (tombol
     "Salin teks" tetap ada di modal struk);
   - jangan mengklaim pesan terkirim.
5. Atur urutan log: catat upaya setelah tautan berhasil dibuka, atau catat
   status `TIDAK_TERSEDIA` bila WhatsApp tidak tersedia. Konsisten dengan
   aturan Tahap 12.

**Catatan penting tentang browser**

- `window.open()` setelah proses cetak yang async bisa diblokir popup blocker.
- Sediakan fallback satu klik yang tidak melanggar permintaan "tidak ada tombol
  WhatsApp di modal struk", misalnya tautan pada toast atau tombol "Buka
  WhatsApp" yang hanya muncul jika otomatis gagal. Tulis di ringkasan bahwa
  fallback ini dipakai.
- Di APK, intent Android tidak terkena popup blocker; gunakan jalur native
  P-08.

**Kriteria penerimaan**

- Tidak ada tombol WhatsApp terpisah di modal struk.
- Cetak berhasil memicu WhatsApp berisi struk lengkap.
- Isi WA sama dengan nota yang dicetak (tanpa strip potong).
- Tidak ada pesan yang terkirim otomatis tanpa tindakan kasir.

**Commit**: `P-07: cetak lalu buka WhatsApp dengan struk lengkap`

---

### P-08 — Tautan WhatsApp `wa.me` tidak boleh diblokir

**Masalah**

- Di APK, `MainActivity.kt:298-306` memblokir semua URL yang bukan
  `http://127.0.0.1:<port>` dan menampilkan "Tautan eksternal diblokir".
- `NativeBridge.kt` belum punya metode untuk membuka tautan eksternal.
- Tautan `wa.me` yang benar sudah dibuat oleh `waLink()` di
  `frontend/js/app.js:1769-1778`, tetapi tidak pernah bisa dibuka dari WebView.

**Perilaku yang diinginkan**

- Tautan WhatsApp memakai format:
  `https://wa.me/62<nomor tanpa 0 di depan>?text=<teks ter-encode>`.
- Di browser desktop, tautan membuka tab WhatsApp.
- Di APK, tautan membuka aplikasi WhatsApp (atau browser) lewat intent.
- Tautan eksternal lain tetap diblokir. Jangan membuka allowlist umum.

**Perubahan Android**

1. `MainActivity.kt`:
   - Pada `shouldOverrideUrlLoading`, deteksi host `wa.me` dan
     `api.whatsapp.com`, serta skema `whatsapp` bila diperlukan.
   - Untuk tautan yang diizinkan, buat `Intent(Intent.ACTION_VIEW, uri)` dan
     `startActivity`. Tangani `ActivityNotFoundException` dengan toast
     "WhatsApp tidak terpasang di perangkat ini."
   - Kembalikan `true` setelah menangani, agar WebView tidak mencoba memuat.
   - Semua URL eksternal lain tetap diblokir dengan pesan lama.
2. `NativeBridge.kt`:
   - Tambah method `openExternal` pada switch `call`.
   - Validasi URL: hanya `https` dan host `wa.me` atau `api.whatsapp.com`.
   - Jalankan intent di UI thread, balas sukses/gagal melalui mekanisme
     `reply`/`fail` yang sudah ada.
   - Jangan menambahkan izin Android baru.
3. String resource:
   - Tambah `whatsapp_unavailable` (misalnya "WhatsApp tidak terpasang di
     perangkat ini.") di `res/values/strings.xml`.
4. Test Kotlin:
   - Unit test untuk fungsi klasifikasi URL: `wa.me` diterima, host lain
     ditolak, skema `http`/`javascript`/`file` ditolak.
   - Jika ada test WebView existing, tambahkan kasus allowlist.

**Perubahan frontend**

1. Buat helper `openExternalLink(url)`:
   - Jika `window.BengkelBridge` tersedia dan mendukung `openExternal`,
     panggil lewat wrapper async yang sudah ada.
   - Jika tidak, gunakan `window.open(url, '_blank', 'noopener')` untuk
     desktop.
   - Kembalikan status berhasil/gagal agar pemanggil bisa menampilkan toast.
2. Pastikan semua aksi WA (struk, follow-up, piutang, garansi) memakai
   `waLink()` + `openExternalLink()`, bukan `location.href` atau anchor
   `target="_blank"` yang diblokir WebView.
3. Periksa `handleWaOpen()`: jika modal WA masih dipakai untuk follow-up,
   tautan harus memakai helper yang sama.
4. Jangan mengubah `quote`/`encodeURIComponent` ganda. Teks nota dikirim apa
   adanya; `encodeURIComponent` hanya sekali.

**Kriteria penerimaan**

- Di APK, menekan aksi WA membuka WhatsApp dengan nomor dan teks yang benar.
- Tidak ada lagi pesan "Tautan eksternal diblokir" untuk `wa.me`.
- URL eksternal lain tetap diblokir.
- Di desktop, tautan membuka WhatsApp Web/aplikasi.

**Commit**: `P-08: izinkan tautan wa.me dibuka dari APK`

---

### P-09 — Hapus halaman Follow-up, cukup ringkasan "FOLLOW UP"

**Masalah**

- Navigasi punya tab Follow-up (`frontend/index.html:103-106`) dan ada
  `#view-followup` dengan papan kolom status.
- Pemilik hanya ingin follow-up terlihat di Ringkasan, bukan halaman/kolom
  terpisah.
- Dashboard sudah berjudul "Ringkasan hari ini" dan sudah punya empat kartu
  follow-up, tetapi belum ada judul kelompok "FOLLOW UP".

**Perilaku yang diinginkan**

- Tidak ada tab/halaman Follow-up di navigasi.
- Di Ringkasan tetap ada:
  - Piutang
  - Servis berkala
  - Garansi akan habis
  - Tugas follow-up
- Beri judul kelompok "FOLLOW UP" di atas empat kartu tersebut.
- Detail follow-up tetap bisa dibuka (modal), tetapi bukan halaman penuh dengan
  kolom status.

**Perubahan frontend**

1. `frontend/index.html`:
   - Hapus tombol nav `data-view="followup"`.
   - Hapus section `#view-followup` beserta markup papan kolom.
   - Di dashboard, tambah heading kelompok "FOLLOW UP" di atas
     `.stats-grid--secondary` (judul "Ringkasan hari ini" tetap).
   - Ganti tombol "Buka papan follow-up" menjadi aksi yang membuka daftar
     ringkas (modal), bukan halaman.
2. `frontend/js/app.js`:
   - Hapus `FOLLOWUP_COLUMNS`, `renderFollowupBoard`, dan fungsi yang hanya
     dipakai papan.
   - Pertahankan `followupCardHtml`, `followupRincianHtml`,
     `followupEventsHtml`, `renderFollowupDetail`, modal detail, dan aksi
     status/follow-up yang masih dipakai.
   - Buat `openFollowupList(jenis)` yang menampilkan daftar item (judul, unit,
     jatuh tempo, sisa hari) dalam modal dengan tombol "Lihat detail".
   - Kartu "Piutang" tetap membuka daftar piutang yang ada.
   - Kartu "Servis berkala", "Garansi akan habis", dan "Tugas follow-up"
     membuka `openFollowupList()` dengan filter yang sesuai.
   - Hapus `navigate('followup')` dan referensi `view-followup` yang tersisa.
3. CSS:
   - Hapus style papan kolom yang menjadi mati, atau biarkan bila masih dipakai
     modal; jangan hapus style modal/detail.
   - Tambah style heading kelompok "FOLLOW UP" yang tenang (label kecil,
     huruf kapital, jarak konsisten).
4. Test:
   - Manual: navigasi tidak menampilkan Follow-up; kartu ringkasan membuka
     daftar/modal; detail dan aksi status tetap berfungsi.
   - `node --check frontend/js/app.js`.
   - Pastikan tidak ada error console karena elemen yang dihapus.

**Kriteria penerimaan**

- Tidak ada halaman/kolom Follow-up terpisah.
- Ringkasan menampilkan kelompok "FOLLOW UP" dengan empat kartu.
- Detail follow-up tetap dapat diakses tanpa halaman penuh.

**Commit**: `P-09: hapus halaman follow-up dan rapikan ringkasan FOLLOW UP`

---

### P-10 — Interval servis untuk sparepart/barang

**Masalah**

- `HargaJasa` dan `ServiceJob` sudah punya `interval_servis_bulan`
  (`database/models.py:107`, `:377`), dan `followup_service` hanya membaca
  baris jasa (`services/followup_service.py:207-256`).
- `StockItem` (`database/models.py:79-95`) dan `ServicePart`
  (`database/models.py:384-411`) belum punya interval.
- Pemilik ingin setiap barang juga punya durasi, sama seperti jasa.

**Perilaku yang diinginkan**

- Master stok punya kolom "Servis berkala" (bulan; 0 = nonaktif).
- Saat sparepart ditambahkan ke nota, interval master otomatis terisi dan bisa
  diubah untuk nota tersebut, sama seperti jasa.
- Interval disimpan sebagai snapshot di baris part nota agar riwayat tidak
  berubah saat master diubah.
- Follow-up servis berkala mempertimbangkan jasa **dan** sparepart.
- Jika beberapa item punya interval, pengingat memakai jatuh tempo terdekat
  untuk pelanggan tersebut, tanpa membuat duplikat item aktif.

**Perubahan database**

1. Migrasi baru (schema menjadi 12 setelah migrasi P-03):
   - `ALTER TABLE stock_items ADD COLUMN interval_servis_bulan INTEGER NOT NULL DEFAULT 0`.
   - `ALTER TABLE service_parts ADD COLUMN interval_servis_bulan INTEGER NOT NULL DEFAULT 0`.
   - Pastikan aman untuk database lama dan idempotent sesuai pola migrasi.
2. Model:
   - `StockItem.interval_servis_bulan`.
   - `ServicePart.interval_servis_bulan`.

**Perubahan backend**

1. Schema (`api/schemas.py`):
   - `StockItemCreate`, `StockItemUpdate`, `StockItemOut`: tambah
     `interval_servis_bulan` dengan batas 0-120.
   - `ServicePartInput`: tambah `interval_servis_bulan` opsional 0-120.
   - Payload struk `parts`: sertakan `interval_servis_bulan`.
2. `services/stock_service.py` + `api/stock_routes.py`:
   - Validasi dan simpan interval pada create/update stok.
   - Tolak nilai negatif atau >120 dengan pesan jelas.
3. `services/pos_service.py`:
   - Untuk setiap part: jika payload memberi interval, pakai itu; jika tidak,
     ambil dari master `StockItem.interval_servis_bulan`; validasi 0-120.
   - Simpan snapshot ke `ServicePart.interval_servis_bulan`.
4. `services/followup_service.py`:
   - Kumpulkan sumber servis berkala dari dua jenis baris: `record.jobs` dan
     `record.parts`.
   - Kunci deduplikasi harus membedakan jenis dan id/nama, misalnya
     `("jasa", harga_jasa_id atau nama)` dan
     `("part", stock_item_id atau nama)`.
   - Label pekerjaan untuk part: `"Sparepart <nama>"` atau format yang jelas.
   - Tetap satu item aktif per `(jenis, customer)`; pilih jatuh tempo terdekat.
   - Rincian item harus menyebut jenis (jasa/sparepart), nama, tanggal servis,
     interval, dan jatuh tempo.
5. `services/receipt_service.py`:
   - Sertakan interval part di payload (boleh tidak dicetak di struk jika tidak
     diminta; jangan mengubah tampilan struk tanpa kebutuhan).
6. Test:
   - CRUD stok dengan interval 0, 6, 120; nilai invalid ditolak.
   - Transaksi dengan part dari master berinterval menyimpan snapshot yang
     benar.
   - Mengubah master setelah transaksi tidak mengubah snapshot part lama.
   - Follow-up servis berkala muncul dari part; tidak duplikat dengan jasa.
   - Part tanpa interval tidak memunculkan pengingat.
   - Migrasi database versi 11 -> 12 mempertahankan data.

**Perubahan frontend**

1. Halaman Stok:
   - Tambah kolom "Servis berkala" pada tabel stok (badge "X bulan" atau
     "Nonaktif").
   - Tambah field interval pada modal tambah/edit sparepart, dengan bantuan
     "0 berarti nonaktif".
2. POS, blok Sparepart:
   - Tambah kolom input "Servis berkala" pada tabel part dan input interval
     pada form tambah part.
   - Saat memilih master stok, isi otomatis interval dari master.
   - Tampilkan hint kecil di dekat form, mirip `#jasaIntervalHint`.
   - Masukkan `interval_servis_bulan` ke payload part di
     `buildTransactionPayload()`.
   - Reset input interval saat form dikosongkan.
3. Modal pemeriksaan nota (P-06):
   - Tampilkan interval part bila > 0, sama seperti jasa.
4. CSS:
   - Pastikan kolom interval tidak membuat tabel rusak di layar kecil; gunakan
     kelas `col-interval` yang sudah ada atau pola serupa.

**Kriteria penerimaan**

- Sparepart punya durasi di master dan di nota.
- Follow-up servis berkala muncul dari sparepart.
- Snapshot interval tidak berubah saat master diubah.
- Tidak ada regresi pada stok, total nota, atau follow-up jasa.

**Commit**: `P-10: tambah interval servis berkala untuk sparepart`

---

## 3. P-11 — Verifikasi akhir, dokumentasi, dan APK

Kerjakan setelah P-01 sampai P-10 selesai.

1. Jalankan seluruh pytest di dua stack:
   - Desktop: Pydantic 2 + FastAPI terbaru.
   - APK: Pydantic 1.10.18 + FastAPI 0.115.0 + SQLAlchemy 2.0.36.
   - Jika environment kedua tidak tersedia, buat venv sementara; jangan
     install global. Laporkan hasil apa adanya.
2. Jalankan `./gradlew test` di `android/` untuk unit test Kotlin.
3. Jalankan `node --check frontend/js/app.js` (dan file JS lain yang diubah).
4. Uji manual di browser dengan database sementara:
   - Buat pelanggan baru tanpa pertanyaan WA.
   - Tambah unit, hapus unit, pastikan hilang dari pilihan dan riwayat aman.
   - Simpan keluhan, periksa nota, Benar/Edit, simpan.
   - Cetak struk mobil tanpa `POTONG DI SINI`.
   - Cetak struk radiator copotan tetap dengan label.
   - Cetak memicu WhatsApp berisi struk lengkap.
   - DP tanpa jatuh tempo, catat pelunasan, piutang hilang setelah lunas.
   - Aksi "Kendaraan selesai": draf WhatsApp menyebut kendaraan sudah selesai
     dan siap diambil, tanpa kata "hutang"/"piutang"/"tagihan".
   - Follow-up servis berkala dari jasa dan sparepart.
   - Ringkasan tanpa halaman Follow-up.
5. Uji manual di APK (jika perangkat tersedia):
   - Tautan `wa.me` membuka WhatsApp, bukan "Tautan eksternal diblokir".
   - Cetak lalu WhatsApp berjalan.
   - Layar utama tetap bisa screenshot; layar PIN tetap aman.
   - Data lama tetap terbaca setelah migrasi 11 dan 12.
   Jika tidak ada perangkat, tulis **"belum diverifikasi"**.
6. Perbarui dokumentasi:
   - `README.md`: perilaku baru (label mobil, WA otomatis, hapus unit, DP
     opsional, interval sparepart, dashboard).
   - `android/README_APK.md`: hasil build, ukuran, SHA-256, jumlah test,
     versi/versionCode, dan catatan uji perangkat.
   - `INVENTARIS_TEKS_UI.md` bila ada teks UI yang berubah.
7. Naikkan versi APK (misalnya `versionName 2.2.3`, `versionCode 6`) dan
   bangun ulang APK debug memakai toolchain yang sudah ada. Periksa isi ZIP
   backend dan hash aset terhadap working tree.
8. Jangan `git push` tanpa izin. Akhiri dengan ringkasan lengkap dan tunggu
   instruksi.

---

## 4. A-01 — Audit bug (JANGAN DIKERJAKAN SEKARANG)

Audit baru dimulai setelah P-01 sampai P-11 selesai dan disetujui. Gunakan satu
temuan = satu commit dengan ID `K-01`, `K-02`, dan seterusnya. Setiap temuan
harus punya test yang gagal sebelum diperbaiki.

Area yang wajib diperiksa saat audit:

1. **Struk dan label**
   - Mobil utuh: tidak ada strip label; data label lama tidak bocor.
   - Radiator copotan: label, nomor, dan strip tetap benar.
   - Void, retur, diskon, total neto, DP, dan pelunasan konsisten di struk.
   - `None`/tanggal kosong tidak tercetak sebagai teks aneh.

2. **Uang dan DP**
   - Tidak ada float; pembulatan `ROUND_HALF_UP`.
   - DP 0, DP lebih besar dari total, pelunasan melebihi sisa, dan pembayaran
     ganda dengan `request_id` ditolak dengan benar.
   - `bayar`, `kembalian`, `total_dibayar`, `sisa_bayar` konsisten untuk
     CASH/TRANSFER/LUNAS/DP.
   - Retur dan void tidak meninggalkan piutang palsu.

3. **WhatsApp**
   - Nomor `0...`, `8...`, `62...`, dan nomor tidak valid.
   - Teks ter-encode tepat satu kali; tidak ada `+`/spasi yang merusak.
   - Panjang URL untuk struk lengkap; fallback bila terlalu panjang/gagal.
   - Izin pelanggan, log `DIBUKA`/`TIDAK_TERSEDIA`, dan tidak ada pengiriman
     otomatis.
   - Follow-up memakai format yang terbaca di WhatsApp.

4. **Unit dan pelanggan**
   - Arsip unit tidak memutus riwayat, follow-up, atau laporan.
   - Pelanggan tanpa unit, unit ganda, dan nopol ganda.
   - Hapus pelanggan/unit tidak menghapus nota secara tidak sengaja.

5. **Follow-up dan interval**
   - Satu item aktif per `(jenis, pelanggan)`.
   - Jasa + sparepart dengan interval sama tidak menghasilkan duplikat.
   - Perubahan master setelah nota tidak mengubah snapshot.
   - Arsip/penolakan piutang dan garansi bekerja sesuai aturan.

6. **Migrasi dan data**
   - Database versi 10 -> 11 -> 12, data lama utuh.
   - Migrasi aman dijalankan ulang; `PRAGMA user_version` benar.
   - Backup sebelum migrasi (bila ada mekanismenya) tetap berfungsi.

7. **Frontend/security**
   - Semua teks dinamis di-`esc` saat masuk HTML (nama pelanggan, nama part,
     keluhan).
   - Tidak ada `innerHTML` dengan data pengguna tanpa escape.
   - Tombol tersembunyi tidak bisa diaktifkan lewat keyboard/atribut.
   - Modal pemeriksaan nota menampilkan angka dari backend, bukan hitungan JS.

8. **Android/WebView**
   - Allowlist `wa.me` tidak membuka URL eksternal lain.
   - Tidak ada bypass navigasi ke `http://127.0.0.1` port lain.
   - Intent WhatsApp gagal ditangani bila aplikasi tidak terpasang.
   - Aset backend di APK sama dengan working tree.

9. **Test dan dokumentasi**
   - Jalankan pytest penuh di dua stack setelah setiap perbaikan audit.
   - Perbarui dokumentasi dan hash APK bila build berubah.

---

## 5. Format laporan akhir setiap fase

Gunakan format ini agar pemilik mudah memeriksa:

```text
Fase: P-xx — <judul>
File diubah: ...
Test ditambah: ...
Hasil pytest desktop: ... lulus / ... gagal
Hasil pytest APK (Pydantic 1.10): ... lulus / ... gagal / belum diverifikasi
Perubahan yang terlihat pengguna: ...
Risiko tersisa: ...
Status: selesai / belum diverifikasi
```

Setelah menulis laporan, **berhenti dan tunggu instruksi**. Jangan melanjutkan
ke item berikutnya atau audit tanpa persetujuan.
