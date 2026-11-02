# DESIGN.md — BengkelPOS Radiator

Sistem warna dan tipografi memakai variabel. Layout, ukuran, jarak, komponen,
dan perilaku tidak berubah dari desain sebelumnya.

## Mekanisme tema

- Mode terang/gelap tetap memakai atribut `data-theme` di `<html>` dan kunci
  penyimpanan lama `bengkel.theme` (`light` / `dark`).
- Tema warna ditambahkan sebagai token di atribut yang sama, misalnya
  `data-theme="navy-oranye"` atau `data-theme="navy-oranye dark"`.
- Pilihan tema disimpan di `bengkel.colorTheme`. Tanpa nilai tersimpan,
  aplikasi memakai `navy-oranye`.
- Mengganti tema tidak mengubah mode; mengganti mode tidak mengubah tema.
- `prefers-color-scheme` tidak dipakai karena aplikasi sudah memiliki pilihan
  mode manual. Tidak ada opsi "ikuti sistem" di versi ini.

## Variabel tema

Setiap tema mengisi delapan variabel resmi:

`--color-sidebar`, `--color-text`, `--color-text-muted`, `--color-bg`,
`--color-card`, `--color-border`, `--color-accent`, `--color-on-accent`.

Token lama (`--ground`, `--surface`, `--text`, `--muted`, `--border`,
`--accent`, `--on-primary`, `--rail-*`, `--chrome-*`, `--toast-*`) dipetakan ke
variabel tersebut sehingga seluruh halaman, modal, tabel, input, dropdown, dan
badge ikut berubah tanpa menyentuh struktur.

### navy-oranye (bawaan)

| Variabel | Terang | Gelap |
| --- | --- | --- |
| sidebar | `#1E293B` | `#0F172A` |
| text | `#1E293B` | `#F1F5F9` |
| text-muted | `#556377` | `#94A3B8` |
| bg | `#F1F5F9` | `#0B1220` |
| card | `#F8FAFC` | `#1E293B` |
| border | `#E2E8F0` | `#334155` |
| accent | `#C2410C` | `#F97316` |
| on-accent | `#FFFFFF` | `#1C1917` |

### charcoal-kuning

| Variabel | Terang | Gelap |
| --- | --- | --- |
| sidebar | `#27272A` | `#18181B` |
| text | `#18181B` | `#FAFAFA` |
| text-muted | `#556377` | `#A1A1AA` |
| bg | `#F4F4F5` | `#09090B` |
| card | `#FAFAFA` | `#27272A` |
| border | `#E4E4E7` | `#3F3F46` |
| accent | `#FACC15` | `#FACC15` |
| on-accent | `#1C1917` | `#1C1917` |

### biru-teal

| Variabel | Terang | Gelap |
| --- | --- | --- |
| sidebar | `#0F4C81` | `#0B2F52` |
| text | `#1E293B` | `#F1F5F9` |
| text-muted | `#556377` | `#94A3B8` |
| bg | `#F1F5F9` | `#0B1220` |
| card | `#F8FAFC` | `#1E293B` |
| border | `#E2E8F0` | `#334155` |
| accent | `#0F766E` | `#2DD4BF` |
| on-accent | `#FFFFFF` | `#0F172A` |

### putih (monokrom)

| Variabel | Terang | Gelap |
| --- | --- | --- |
| sidebar | `#FFFFFF` | `#000000` |
| text | `#000000` | `#FFFFFF` |
| text-muted | `#525252` | `#A3A3A3` |
| bg | `#FFFFFF` | `#000000` |
| card | `#FFFFFF` | `#000000` |
| border | `#E5E5E5` | `#262626` |
| accent | `#000000` | `#FFFFFF` |
| on-accent | `#FFFFFF` | `#000000` |

Tema Putih memakai putih penuh pada mode terang dan berbalik menjadi hitam
penuh pada mode gelap.

### hitam (monokrom)

| Variabel | Terang | Gelap |
| --- | --- | --- |
| sidebar | `#000000` | `#FFFFFF` |
| text | `#FFFFFF` | `#000000` |
| text-muted | `#A3A3A3` | `#525252` |
| bg | `#000000` | `#FFFFFF` |
| card | `#000000` | `#FFFFFF` |
| border | `#262626` | `#E5E5E5` |
| accent | `#FFFFFF` | `#000000` |
| on-accent | `#000000` | `#FFFFFF` |

Tema Hitam memakai hitam penuh pada mode terang dan berbalik menjadi putih
penuh pada mode gelap.

## Turunan

Warna turunan dihitung dari delapan variabel di atas dengan `color-mix`:
raised/active surfaces, rule, control border, accent hover/tint/ink, rail
hover/line/muted, overlay, dan shadow. Warna status tidak berubah antar tema:

- hijau lunas/selesai `#15803D` (gelap `#4ADE80`)
- merah batal/hapus `#DC2626` (gelap `#F87171`)
- kuning menunggu/stok menipis `#CA8A04` (gelap `#FACC15`)
- biru dikerjakan `#2563EB` (gelap `#60A5FA`)

Badge memakai latar soft dan teks ink yang disesuaikan per mode.

## Tipografi

- `font-family: "Plus Jakarta Sans", Roboto, "Segoe UI", Arial, sans-serif`
- `font-variant-numeric: tabular-nums`
- Berkas latin `frontend/fonts/plus-jakarta-sans-latin.woff2`, dimuat lokal
  dengan `@font-face` untuk bobot 400, 500, 600, 700, dan 800,
  `font-display: swap`.
- Ukuran dan ketebalan teks yang ada dipertahankan. Satu-satunya penyesuaian
  adalah angka besar Ringkasan pada 1280–1439 px (27 px) agar tetap satu baris
  setelah keluarga font berubah.

## Struk

Cetak struk memakai jendela cetak terpisah dengan teks hitam di atas putih dan
font `Courier New`. Tema dan mode tidak memengaruhi hasil cetak.

## Berkas

- `frontend/css/world.css` — variabel tema, pemetaan token, komponen.
- `frontend/css/style.css` — lapisan struktur lama; warna komponen sudah
  memakai variabel.
- `frontend/index.html` — pilihan tema di Pengaturan, meta theme-color.
- `frontend/js/app.js` — penyimpanan tema/mode dan pemilihan tema.
- `frontend/fonts/plus-jakarta-sans-latin.woff2`.
