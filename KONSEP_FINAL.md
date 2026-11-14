# MATI DI AKAR — Konsep Final
Kartika Cyber Hackathon 2026 (PUSSIBERAD × CODEPOLITAN) — Kategori: **Defensive Shield (Penangkalan)**
Disusun: Senin, 9 November 2026. Deadline submisi: 15 November 2026. Final: 24 November 2026, Jakarta.

---

## 1. Identitas karya

- **Nama karya:** MATI DI AKAR
- **Tagline:** "Semua orang memblokir situsnya. Kami mematikan jaringannya."
- **Satu kalimat:** Sistem intelijen yang menangkap situs judi online saat lahir, mengelompokkan situs-situs cermin menjadi jaringan operator, dan memetakan simpul pembayaran bersama, sehingga satu laporan dapat mematikan puluhan situs sekaligus.
- **Nama tim (usulan, boleh diganti):** AKAR — peserta individu (Muhammad Hazim Robbani).
- **Keluaran akhir:** aplikasi web (dasbor + peta jaringan + ekspor berkas bukti) dan repositori publik.

## 2. Masalah (angka terverifikasi dari pernyataan resmi)

- Komdigi menyatakan telah menangani **lebih dari 4,2 juta konten** terkait judi online per Oktober 2026; sepanjang 2025 saja ada **2.087.109 konten**, dan **1.809.358** di antaranya berupa situs dan alamat IP.
- Situs yang diblokir **lahir kembali dengan domain baru dalam hitungan jam**; pemerintah sendiri mengakui pemblokiran saja tidak cukup. Lebih dari **76%** sampel 10.000 situs judol yang ditangani Komdigi bersembunyi di balik Cloudflare.
- PPATK mencatat perputaran dana judi online semester I-2026 sebesar **Rp86,82 triliun** dari 467,32 juta transaksi. OJK bersama Komdigi telah menghimpun **38.796 rekening** terindikasi judi online untuk ditindak perbankan.
- Kesimpulan masalah: perang melawan domain adalah perang melawan barang sekali pakai. Selama simpul operatornya (rekening penampung, kontak operator, pola infrastruktur) tidak dipetakan, pemblokiran tidak akan pernah selesai.

## 3. Insight inti

1. **Domain itu sekali pakai, jaringannya tidak.** Operator yang sama menjalankan puluhan situs cermin dengan rekening, kontak, dan templat yang sama.
2. **Situs judol mengumumkan kelahirannya.** Sertifikat HTTPS setiap situs tercatat publik di log Certificate Transparency (CT), sering kali sebelum situs melayani korban pertama. Siapa pun bisa mendengarkan aliran ini secara real-time dan gratis.
3. **Yang langka dari operator bukan domain, melainkan rekening penampung.** Satu rekening yang diblokir perbankan mematikan seluruh jaringan yang memakainya. Maka target intelijen yang benar adalah simpul uang dan operatornya, bukan daftar situs.

## 4. Cara kerja — tiga modul dan satu keluaran

### Modul 1 — LAHIR (menangkap saat lahir)
- Memantau log Certificate Transparency secara langsung dan real-time melalui API standar RFC 6962 (get-sth/get-entries) pada log besar **Google Argon** dan **Cloudflare Nimbus**, dilengkapi sapuan berkala **crt.sh** untuk menutup celah. (Catatan rekayasa 9 Nov 2026: aliran publik CertStream diuji pada hari pembangunan pertama dan tidak mengalirkan data dari jaringan pembangunan — websocket tersambung tetapi nol pesan — sehingga pemantauan langsung ke log CT dipakai sebagai jalur utama. Dua log independen sekaligus menghilangkan titik gagal tunggal.)
- Setiap domain baru dinilai: kemiripan nama dengan merek judol yang dikenal (jarak edit/fonetik), kata kunci leksikon judol Indonesia (slot, gacor, maxwin, rtp, zeus, mahjong, togel, toto, depo, dan lain-lain), usia domain (RDAP), dan pola sertifikat (penerbit, SAN, wildcard).
- Hasil: daftar kandidat "baru lahir" lengkap dengan stempel waktu kelahiran dan skor keyakinan.

### Modul 2 — SIDIK (sidik jari dan pengelompokan jaringan)
- Untuk setiap kandidat dan domain benih, sistem mengambil sidik jari teknis dari halaman publiknya:
  - hash favicon (MurmurHash3, gaya Shodan),
  - hash struktural halaman (simhash atas struktur DOM dan teks tampak),
  - hash berkas JS/CSS utama dan ID pelacak (analytics) bila ada,
  - pola DNS (rekord A/NS, ASN), pola sertifikat TLS,
  - tautan kontak yang tampil publik (t.me, wa.me) dan tautan keluar khas.
- Domain-domain digabung menjadi **klaster jaringan** (union-find) bila berbagi pengenal kuat yang sama; kemiripan lemah menaikkan skor pasangan, bukan langsung menggabung.
- Benih awal: daftar blokir publik **BrigsLabs/judol (39.461 domain)** dan cermin daftar judi TrustPositif di GitHub (`alsyundawy/TrustPositif`), untuk memberi konteks "merek yang sudah diblokir" sejak hari pertama.

### Modul 3 — UANG (ekstraksi simpul pembayaran)
- Dari halaman publik situs dalam klaster (beranda dan halaman yang tertaut terbuka), sistem mengekstrak dengan pola regex + konteks kata kunci:
  - nomor rekening di dekat nama bank (BCA, BRI, Mandiri, BNI, dan lain-lain),
  - nomor e-wallet di dekat kata DANA/OVO/GoPay/ShopeePay,
  - kontak operator (Telegram/WhatsApp) sebagai simpul operator.
- Simpul pembayaran/kontak menjadi simpul graf: dua klaster yang berbagi satu nomor rekening atau kontak yang sama **digabungkan sebagai satu jaringan operator**.

### Keluaran — DOSIR JARINGAN
- Dasbor web berisi: (a) umpan kelahiran langsung, (b) peta graf jaringan (domain ↔ rekening ↔ kontak), (c) halaman dosir per jaringan: daftar domain + waktu pertama terlihat + sidik jari penghubung + simpul pembayaran + tangkapan bukti.
- **Ekspor satu berkas bukti per jaringan** (PDF + CSV) berformat laporan intelijen: ringkasan jaringan, daftar domain, simpul pembayaran yang perlu ditindak perbankan, dan bukti pendukung. Format ini meniru alur kerja nyata aduan ke Komdigi dan permintaan pemblokiran rekening ke perbankan/OJK.

## 5. Arsitektur dan teknologi

- Bahasa: Python 3.12 (satu bahasa, cepat dibangun solo).
- Penangkap: `certstream`, kueri `crt.sh`, RDAP via `httpx`.
- Pengambilan sidik: `httpx` (timeout ketat, laju terbatas), `mmh3` (favicon), simhash DOM (parser `selectolax`/`lxml`), DNS via `dnspython`.
- Graf dan klaster: `networkx` + union-find; penyimpanan SQLite.
- Dasbor: Streamlit (cepat) dengan komponen graf `vis-network` (atau pyvis) untuk peta jaringan; ekspor PDF via `reportlab`/cetak HTML.
- Berjalan di satu laptop/VM Linux biasa; tanpa GPU, tanpa API berbayar, semua sumber data publik dan gratis.
- Snapshot demo beku: seluruh basis data dibekukan pada H5 sehingga presentasi tidak bergantung pada koneksi langsung.

## 6. Batas ruang lingkup (MVP — yang TIDAK dijanjikan)

- Fokus hanya judi online Indonesia; phishing disebut sebagai pengembangan, bukan janji MVP.
- Tidak ada transaksi, tidak ada pendaftaran akun di situs judol, tidak ada login; hanya pengamatan pasif atas data dan halaman publik.
- Ekstraksi QRIS dari gambar ditunda (bukan MVP); nomor rekening/e-wallet berbasis teks dulu.
- Situs dengan cloaking berat mungkin lolos dari sidik halaman; sistem mengakuinya lewat skor keyakinan, bukan menyembunyikannya.
- Semua temuan berstatus **indikasi untuk diverifikasi aparat**, bukan vonis.

## 7. Pemetaan ke kriteria penilaian juri

| Kriteria | Bobot | Cara MATI DI AKAR memenuhinya |
|---|---|---|
| Relevansi dan Manfaat | 25% | Menjawab masalah nasional terukur (4,2 juta konten, Rp86,82 triliun) dan celah yang diakui pemerintah sendiri; keluaran berupa berkas yang bisa langsung dipakai patroli siber dan diteruskan ke perbankan. |
| Inovasi Teknis | 25% | Pergeseran paradigma dari memblokir domain ke mematikan jaringan: deteksi saat lahir via CT log + sidik jari infrastruktur + graf simpul pembayaran. Teknik CT terbukti untuk phishing di literatur keamanan, tetapi belum dikemas untuk jaringan cermin judol Indonesia. |
| Fungsionalitas Purwarupa | 25% | Sistem hidup yang memproses aliran data sungguhan sejak hari pertama pembangunan; angka hasil (kelahiran tertangkap, klaster, rekening terpetakan) berasal dari data riil yang terkumpul, bukan data contoh. |
| Kelayakan Implementasi | 15% | Semua sumber data publik dan gratis, berjalan di satu mesin, tanpa ketergantungan API berbayar; format ekspor mengikuti alur aduan dan pemblokiran rekening yang sudah ada. |
| Kualitas Dokumentasi | 10% | Video presentasi dengan demo langsung, slide, README arsitektur, dan dokumen konsep ini. |

## 8. Skenario demo (video submisi dan final 10 menit)

1. **Menit 0–1,5 — Masalah:** angka 4,2 juta dan pengakuan bahwa situs lahir lagi. "Kami berhenti mengejar ekornya. Kami memburu akarnya."
2. **Menit 1,5–3,5 — Lahir:** buka umpan langsung; domain judol baru tertangkap beberapa menit setelah sertifikatnya terbit, lengkap dengan skor dan alasan penilaiannya.
3. **Menit 3,5–6,5 — Jaringan menyala:** pilih satu merek judol yang sudah diblokir; peta menunjukkan puluhan situs cerminnya yang belum diblokir sebagai satu klaster, dengan sidik jari penghubungnya (favicon sama, templat sama, kontak sama).
4. **Menit 6,5–8,5 — Simpul uang:** zoom ke satu nomor rekening/e-wallet yang dipakai bersama seluruh klaster. "Domain bisa diganti dalam semenit. Rekening ini tidak." 
5. **Menit 8,5–10 — Dosir dan penutup:** klik ekspor, berkas bukti satu jaringan keluar; tutup dengan peta jalan (API untuk ISP/perbankan, perluasan ke phishing penipuan).

## 9. Risiko dan mitigasi

| Risiko | Mitigasi |
|---|---|
| Endpoint publik CertStream kadang tidak stabil | Cadangan berlapis: server CertStream self-hosted, plus sapuan berkala crt.sh; data yang sudah tertangkap tersimpan lokal sejak hari pertama. |
| False positive pada penilaian domain | Skor berlapis + ambang tampil; klaster demo diverifikasi manual pada H5; dasbor membedakan "indikasi" dan "terverifikasi". |
| Situs judol memakai cloaking/Cloudflare | Sidik multi-sinyal (favicon, DOM, sertifikat, DNS, kontak) tidak bergantung pada satu sinyal atau IP asal. |
| Kehabisan waktu | Urutan bangun menempatkan penangkap data di hari pertama (data terakumulasi sambil modul lain dibangun); submisi ditargetkan H6 malam, sehari sebelum deadline. |
| Demo langsung gagal | Snapshot basis data beku H5 untuk presentasi; video submisi direkam dari sistem yang berjalan. |

## 10. Etika dan batasan kerja

- Hanya data publik dan halaman publik; tanpa transaksi, tanpa akun, tanpa interaksi dengan operator.
- Laju pengambilan halaman dibatasi dan diberi jeda; tidak membebani situs target.
- Temuan dinyatakan sebagai indikasi intelijen untuk diverifikasi pihak berwenang.
- Tidak ada data pribadi warga yang dikumpulkan; yang dipetakan adalah infrastruktur dan simpul pembayaran pelaku.

## 11. Teks ide untuk formulir pendaftaran CODEPOLITAN (siap salin)

**Nama tim:** AKAR
**Kategori:** Defensive Shield (Penangkalan)
**Judul solusi:** MATI DI AKAR — Sistem Intelijen Jaringan Judi Online: Deteksi Saat Lahir, Pemetaan Klaster Cermin, dan Penindakan Simpul Pembayaran

**Deskripsi ide:**
Komdigi telah menangani lebih dari 4,2 juta konten judi online, tetapi situs yang diblokir selalu lahir kembali dengan domain baru dalam hitungan jam, karena yang diganti operator hanyalah domain, yaitu barang sekali pakai. MATI DI AKAR mengubah sasaran: bukan domainnya, melainkan jaringannya. Sistem ini bekerja dalam tiga lapis. Pertama, mendengarkan aliran log Certificate Transparency secara real-time untuk menangkap domain judi online baru pada saat kelahirannya, bahkan sebelum situsnya ramai dikunjungi, lalu menilainya dengan kemiripan nama merek, leksikon judi online Indonesia, dan usia domain. Kedua, mengambil sidik jari teknis setiap situs (hash favicon, struktur halaman, pola sertifikat dan DNS, kontak operator) untuk mengelompokkan puluhan situs cermin menjadi satu jaringan operator. Ketiga, mengekstrak simpul pembayaran bersama (nomor rekening dan e-wallet penampung) yang menghubungkan seluruh jaringan, karena satu rekening yang diblokir perbankan mematikan semua situs yang memakainya. Keluaran akhirnya adalah dasbor peta jaringan dan berkas bukti per jaringan yang siap diteruskan untuk penindakan. Seluruh data bersumber publik dan gratis, dan sistem berjalan di satu mesin biasa.

**Teknologi:** Python, CertStream/Certificate Transparency, crt.sh, analisis sidik jari web (favicon hash, simhash DOM), graf jaringan (networkx), SQLite, dasbor web.

## 12. Rencana bangun 6 hari (9–14 November 2026; deadline resmi 15 November)

Prinsip: penangkap data dinyalakan pada hari pertama, karena setiap jam aliran CT yang terlewat adalah data kelahiran yang hilang. Submisi ditargetkan selesai Sabtu 14 November malam, sehari sebelum deadline.

| Hari | Fokus | Keluaran yang harus jadi |
|---|---|---|
| **H1 — Senin 9 Nov (hari ini)** | Pendaftaran + penangkap dinyalakan | Akun/tim terdaftar di CODEPOLITAN dengan teks ide di §11; repo publik dibuat; skrip CertStream + penilaian leksikon jalan dan mulai menyimpan domain kandidat ke SQLite; daftar benih BrigsLabs/judol + leksikon kata kunci v1 masuk repo. |
| **H2 — Selasa 10 Nov** | Modul SIDIK | Pengambil sidik jari (favicon mmh3, simhash DOM, DNS, sertifikat) + klaster union-find; sapuan crt.sh untuk merek benih; klaster pertama terbentuk dari data riil. |
| **H3 — Rabu 11 Nov** | Modul UANG | Ekstraktor rekening/e-wallet/kontak + penggabungan klaster lewat simpul bersama; skema dosir jaringan (JSON) selesai. |
| **H4 — Kamis 12 Nov** | Dasbor + ekspor | Dasbor web: umpan kelahiran, peta graf jaringan, halaman dosir; ekspor berkas bukti PDF/CSV per jaringan. |
| **H5 — Jumat 13 Nov** | Bukti dan pembekuan demo | Uji ujung-ke-ujung dengan data terkumpul 4 hari; kurasi klaster demo (verifikasi manual); angka hasil akhir dicatat apa adanya; snapshot basis data dibekukan untuk presentasi; naskah video ditulis. |
| **H6 — Sabtu 14 Nov** | Dokumentasi + submisi | Video presentasi direkam dari sistem berjalan; slide selesai; README lengkap; **submisi di CODEPOLITAN malam ini** (link karya, video, slide). |
| Cadangan — Minggu 15 Nov | Perbaikan terakhir | Hanya bila ada yang kurang; deadline resmi 15 Nov 2026. |

Sesudah pengumuman finalis (20 Nov): siapkan versi presentasi 10 menit mengikuti skenario §8 dan latihan demo dari snapshot beku.

## 13. Checklist submisi

- [ ] Tim terdaftar di CODEPOLITAN, ide terajukan (H1)
- [ ] Link karya: repo GitHub publik + dasbor yang bisa diakses/snapshot
- [ ] Video presentasi (demo dari sistem berjalan)
- [ ] Slide penjelasan proyek
- [ ] Angka hasil di video/slide = angka riil dari basis data (tidak dibulatkan ke atas)
