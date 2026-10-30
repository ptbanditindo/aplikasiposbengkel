# BengkelPOS Radiator - aturan tetap

KONTEKS
- Dua varian produk, kode backend SAMA, database MASING-MASING, tanpa sinkronisasi:
  1. Web lokal: PC kasir, FastAPI + SQLite, diakses browser HANYA dari PC itu sendiri.
  2. APK Android: FastAPI + SQLite berjalan di dalam HP (Chaquopy), offline penuh.
- Pengguna adalah pemilik UMKM non-teknis. Kehilangan data transaksi adalah risiko terbesar.

KOMPATIBILITAS GANDA (wajib)
- Desktop: Pydantic 2.x, FastAPI terbaru, Python 3.12.
- APK: Pydantic 1.10.18, FastAPI 0.115.0, SQLAlchemy 2.0.36, uvicorn 0.30.6, Python 3.10,
  hanya paket pure-Python. Jangan menambah dependensi native/Rust.
- Setiap perubahan backend harus lulus pytest di KEDUA environment. requirements.txt BUKAN
  daftar dependensi APK; pin APK ada di android/app/build.gradle.kts.

PRINSIP KERJA
- Satu temuan = satu commit kecil; pesan commit memuat ID temuan (mis. "K-01: ...").
- Test-first: tulis test yang GAGAL (membuktikan bug), perbaiki, pastikan test lulus,
  lalu jalankan seluruh pytest.
- Jangan ubah perilaku di luar temuan yang diminta. Jangan refactor besar.
- Uang: Decimal/ROUND_HALF_UP di backend, tidak pernah float. Satu sumber logika bisnis
  (services/); jangan menduplikasi rumus di Kotlin atau JS.
- Jangan membaca atau menampilkan .env asli maupun database asli. Test memakai database
  dan BACKUP_DIR sementara.
- Jangan git push, jangan ganti/merge branch tanpa izin, jangan install paket global.
- Jika tidak bisa menjalankan sesuatu (mis. Gradle/JDK tidak ada), JANGAN menyatakan
  "terverifikasi"; tulis sebagai "belum diverifikasi" beserta langkah uji manualnya.
- Akhiri tiap fase dengan ringkasan (file diubah, test ditambah, hasil pytest di dua stack,
  perubahan yang terlihat pengguna, risiko tersisa), lalu berhenti dan tunggu instruksi.
