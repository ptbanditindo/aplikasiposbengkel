# Rencana Pengembangan Baru

Status: **tidak ada rencana aktif**. Seluruh butir Tahap 1-8 dan filter periode
hasil follow-up sudah tersedia di aplikasi; catatan rencana yang sudah terwujud
dihapus dari dokumen ini pada 2026-11-02.

- Acuan versi: web/desktop dan APK **2.6.0** (versionCode 18)
- Skema database: **38**
- Audit dilakukan terhadap kode backend, UI, dan tes yang ada.

## Aturan kerja

- Hanya rencana yang **belum ada** di aplikasi yang dicatat di sini.
- Tidak ada implementasi kode tanpa perintah eksplisit seperti "kerjakan"
  atau "implementasikan".
- Butir yang sudah selesai **dihapus** dari dokumen ini, bukan ditandai selesai.
- Dokumen ini bukan persetujuan implementasi.

## Rencana aktif

Belum ada. Tambahkan rencana baru di sini hanya jika fiturnya belum ada di
aplikasi.

## Audit butir yang dihapus

| Butir lama | Bukti sudah ada di aplikasi |
| --- | --- |
| Total hutang dan stok menipis/habis di Ringkasan | `stock_items.stok_minimum`, perhitungan di `services/report_service.py`, kartu Ringkasan, filter stok, pengaturan batas minimum |
| Supplier dan Follow up Reseller | `suppliers`, `supplier_items`, `supplier_followups`, `api/supplier_routes.py`, menu Supplier, tab Reseller, chat WhatsApp supplier |
| Hasil follow up pelanggan (garansi, servis, prospek) | `followup_result_service` menghitung jumlah pesan follow-up, kembali ke bengkel beserta persentase, serta Masih bagus/Bermasalah/Menolak di halaman Follow up |
| Filter periode hasil follow-up | `followup_result_service.summary(start, end)`, query `start`/`end` di `/api/followup/results`, dan pilihan periode di kartu hasil Follow up |
| Nomor nota angka berurutan | `nota_counters` dan generator nomor di repository/nota baru |
| Karyawan, penugasan nota, performa, komisi, dan gaji | `employees`, `service_record_mechanics`, `service_record_commissions`, `salary_payments`, menu Karyawan, laporan performa |
| Pengaturan struk per bagian | `RECEIPT_FIELDS` di `services/settings_service.py`, toggle di Pengaturan, pembacaan toggle di layanan struk |

## Catatan

- Rencana rinci Tahap 1-8 beserta titik sentuh kode, daftar tes, migrasi, dan
  risiko dihapus karena fiturnya sudah terverifikasi.
- `PETA_PENGEMBANGAN.md` lama tetap disimpan sebagai dokumen historis.
- `RENCANA_PERBAIKAN.md` sudah dihapus dan tidak dipakai lagi.
