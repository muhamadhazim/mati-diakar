# MATI DI AKAR — Sistem Intelijen Jaringan Judi Online

Hackathon Kartika Cyber 2026, kategori Penangkalan (Defensive Shield).
Tim GRASSROOT.

Komdigi telah menangani lebih dari 4,2 juta konten judi online, tetapi
situs yang diblokir selalu lahir kembali dengan domain baru dalam hitungan
jam, karena yang diganti operator hanyalah domain. MATI DI AKAR mengubah
sasaran: bukan domainnya, melainkan jaringannya. Sistem bekerja dalam tiga
lapis:

1. **LAHIR** (`tangkap.py`, `ctparse.py`, `penilaian.py`): mendengarkan log
   Certificate Transparency secara langsung (API RFC 6962) untuk menangkap
   domain judi online baru saat kelahirannya, dinilai dengan kemiripan nama
   merek, leksikon judi online Indonesia, dan usia domain.
2. **SIDIK** (`sidik.py`): mengambil sidik jari teknis tiap situs (hash
   favicon, struktur halaman, pola sertifikat dan DNS, kontak operator).
3. **KLASTER** (`klaster.py`, `ekspor_pdf.py`): mengelompokkan situs cermin
   menjadi satu jaringan operator dan mengekstrak simpul pembayaran bersama
   (rekening dan e-wallet penampung) yang menghubungkan seluruh jaringan.
   Keluaran: dasbor peta jaringan dan berkas bukti per jaringan (PDF, CSV).

Seluruh data bersumber publik dan gratis. Dasbor hanya membaca basis data.
Versi repo ini membawa data contoh tersamar (`data/matidiakar.db`, 79
kandidat) supaya bisa langsung dicoba juri tanpa menunggu penangkap CT.

## Demo langsung

Dasbor dengan data terbaru berjalan di https://matidiakar.onedash.web.id
— penangkap CT masih aktif menangkap domain baru, dan halaman Temuan Uang
di sana merangkum seluruh temuan QRIS, rekening, dan e-wallet.

## Cara jalan (dasbor)

Syarat: Python 3.10+. Dasbor memakai pustaka standar saja, tanpa pip install.

```bash
python3 dasbor.py
```

Lalu buka http://127.0.0.1:20132 di peramban. Host dan port bisa diganti
lewat variabel lingkungan `MATI_DI_AKAR_HOST` dan `MATI_DI_AKAR_PORT`.

Halaman:

- `/` beranda: KPI, grafik, umpan kelahiran, kartu jaringan
- `/kandidat` 200 kandidat terbaru
- `/jaringan/<id>` berkas satu jaringan (graf relasi, domain, bukti, uang)
- `/ekspor/<id>.csv` unduhan CSV berkas jaringan

## Cara jalan (pipelinanya)

Untuk menjalankan penangkap CT, sidik, klaster, dan ekspor PDF diperlukan
dependensi di `requirements.txt`:

```bash
pip install -r requirements.txt
python3 tangkap.py     # pemantau CT langsung, berjalan terus
python3 sidik.py       # sidik jari situs kandidat
python3 klaster.py     # pengelompokan jaringan
python3 ekspor_pdf.py  # berkas bukti PDF per jaringan
```

Penangkap CT (`tangkap.py`) berjalan terus-menerus dan menyimpan kursor di
tabel `ct_state`, jadi aman dihentikan dan dijalankan lagi. Statistik
terkini ditulis ke `data/stats.json`.

## Catatan data

- `data/matidiakar.db` di repo ini adalah data contoh tersamar untuk demo.
  Nomor rekening dan e-wallet asli tidak pernah ikut terunggah; di dasbor
  dan PDF rekening selalu tampil tersamar (mis. `Bank BCA ....`).
- Label bukti eksplisit di semua tempat: BUKTI KUAT / BUKTI LEMAH /
  INDIKASI. Jaringan yang belum lolos verifikasi tangan tidak didemokan.
- `contoh-berkas/` berisi dua contoh berkas bukti PDF (J010 dan J015).

## Struktur

| Berkas | Fungsi |
|---|---|
| `dasbor.py` | Dasbor web baca-saja (pustaka standar) |
| `tangkap.py` | Pemantau log CT langsung |
| `ctparse.py` | Pengurai entri CT |
| `penilaian.py` | Penilaian domain (merek, leksikon, usia) |
| `sidik.py` | Sidik jari teknis situs |
| `klaster.py` | Pengelompokan jaringan |
| `ekspor_pdf.py` | Ekspor berkas bukti PDF |
| `benih.py` | Muat daftar benih domain publik, ekstrak batang merek |
| `data/` | Basis data contoh, daftar merek, statistik |
| `aset/font/` | Fon lokal Satoshi + JetBrains Mono |
| `DESIGN.md` | Token desain dasbor v4 |
| `KONSEP_FINAL.md` | Konsep lengkap karya |
