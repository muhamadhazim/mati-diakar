# DESIGN.md — Token Desain MATI DI AKAR v4

Satu bahasa visual untuk dasbor, video Remotion, dan slide. Dikunci dari
RISET_V4.md (2026-11-10). Arah: "ruang kendali intelijen" — bukan SaaS generik.

## Warna (semantik, tanpa gradien dekoratif)
- Dasar halaman: `#0d1710` (nyaris-hitam kehijauan)
- Panel: `#14231a`; panel terang: `#1e2b22`; garis hairline: `#2c4234`
- Teks utama: `#e8efe9`; teks redup: `#93a698`
- Hijau aktif/kuat (brand): `#2ecc71`; hijau keamanan terang: `#0ddc77`
- Kuning akar/peringatan: `#f1c40f`
- Merah kritis: `#e74c3c`
- Pink uang/pembayaran: `#e56399` (label JENIS saja, angka tidak pernah tampil)
Aturan: warna selalu berarti status/kategori. Dilarang gradien ungu-biru,
glassmorphism, glow dekoratif, border-kiri berwarna, ikon emoji.

## Tipografi
- Display (judul, angka besar): **Satoshi** Bold/Black (Fontshare, gratis);
  cadangan: Space Grotesk (Google Fonts).
- Data (domain, hash, ID jaringan, waktu, angka tabel): **fon mono** —
  JetBrains Mono atau IBM Plex Mono.
- Isi/teks penjelas: Satoshi Regular/Medium.
- Skala: angka KPI 40–48px; judul halaman 26–30px; label kecil 11px huruf
  kapital berjarak (letter-spacing) warna redup.

## Bentuk & kepadatan
- Radius kecil (6px panel, 4px lencana), bayangan nyaris nol.
- Pemisah = garis hairline, bukan kotak melayang. Kepadatan ala analis:
  informasi rapat tapi hierarki jelas dari ukuran dan bobot fon.
- Angka besar selalu disertai konteks (sparkline data asli / persen / tren).

## Komponen khas (pembeda dari dasbor generik)
1. **Ticker CT live**: pita berjalan berisi domain kandidat terbaru +
   stempel waktu, dari data asli DB.
2. **Heatmap kelahiran** 7 hari x 24 jam dari timestamp kandidat asli.
3. **Graf jaringan di beranda**: jaringan terbesar dirender SVG seperti
   halaman detail.
4. **Sparkline** pada kartu KPI dari data deret waktu asli.
5. Stempel waktu "per HH:MM WIB" pada panel status.

## Gerak (khusus video Remotion)
- Easing ease-out untuk masuk; durasi gerak 0,3–0,9 detik; tidak ada bounce.
- Angka count-up; grafik tumbuh dari data; graf menggambar simpul bertahap.
- Kinetic typography: hanya kata bermakna yang bergerak; kata kunci aksen.
