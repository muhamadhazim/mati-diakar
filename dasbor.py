#!/usr/bin/env python3
"""Dasbor web MATI DI AKAR — hanya baca, pustaka standar saja.

Menampilkan data dari data/matidiakar.db:
  /                  beranda: KPI + grafik + umpan kelahiran + kartu jaringan
  /kandidat          200 kandidat terbaru
  /jaringan/<id>     berkas satu jaringan (graf relasi, domain, bukti, uang)
  /ekspor/<id>.csv   unduhan CSV berkas jaringan

Desain v4 mengikuti token tertulis di DESIGN.md ("ruang kendali intelijen"):
fon Satoshi + JetBrains Mono yang disajikan lokal, ticker CT live, heatmap
kelahiran 7x24, graf jaringan terbesar di beranda, sparkline KPI, dan label
bukti eksplisit BUKTI KUAT / BUKTI LEMAH / INDIKASI di semua tempat. Semua
visual digambar server-side sebagai SVG; tanpa pustaka luar, tanpa JavaScript
selain animasi CSS ticker.

Database ditulis terus oleh service penangkap CT, jadi koneksi dibuka
read-only dengan timeout besar dan tidak pernah menulis.
"""

import csv
import html
import io
import json
import math
import os
import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

# Host/port bisa diganti lewat environment variable (bawaan = produksi).
HOST = os.environ.get("MATI_DI_AKAR_HOST", "127.0.0.1")
PORT = int(os.environ.get("MATI_DI_AKAR_PORT", "20132"))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "matidiakar.db")
STATS_PATH = os.path.join(BASE_DIR, "data", "stats.json")

GAYA = """
<style>
 @font-face{font-family:'Satoshi';src:url('/aset/font/Satoshi-400.woff2') format('woff2');font-weight:400;font-display:swap}
 @font-face{font-family:'Satoshi';src:url('/aset/font/Satoshi-500.woff2') format('woff2');font-weight:500;font-display:swap}
 @font-face{font-family:'Satoshi';src:url('/aset/font/Satoshi-700.woff2') format('woff2');font-weight:700;font-display:swap}
 @font-face{font-family:'Satoshi';src:url('/aset/font/Satoshi-900.woff2') format('woff2');font-weight:900;font-display:swap}
 @font-face{font-family:'JetBrains Mono';src:url('/aset/font/JetBrainsMono-VF.woff2') format('woff2');font-weight:400 800;font-display:swap}
 :root{--bg:#0d1710;--sisi:#0a140e;--panel:#14231a;--panel2:#1e2b22;--garis:#2c4234;
 --teks:#e8efe9;--redup:#93a698;--aksen:#2ecc71;--terang:#0ddc77;--kuning:#f1c40f;--merah:#e74c3c;--pink:#e56399}
 *{box-sizing:border-box}
 body{font-family:'Satoshi',system-ui,sans-serif;margin:0;background:var(--bg);
 color:var(--teks);line-height:1.45}
 .kerangka{display:flex;min-height:100vh}
 aside{width:248px;flex:0 0 248px;background:var(--sisi);border-right:1px solid var(--garis);
 padding:1.2em 1em;position:sticky;top:0;height:100vh;overflow-y:auto}
 .merek{display:flex;align-items:center;gap:.55em}
 .merek .titik{width:13px;height:13px;border-radius:50%;background:var(--kuning);flex:0 0 13px}
 .merek b{font-size:1.12em;font-weight:900;letter-spacing:.03em}
 .merek b span{color:var(--aksen)}
 .slogan{color:var(--redup);font-size:.8em;margin:.5em 0 1.1em}
 aside h3{font-size:.72em;text-transform:uppercase;letter-spacing:.12em;color:var(--redup);
 margin:1.3em 0 .5em}
 aside nav a{display:block;color:var(--teks);text-decoration:none;padding:.5em .8em;
 border-radius:4px;font-size:.92em;margin-bottom:.25em}
 aside nav a:hover{background:var(--panel)}
 aside nav a.aktif{background:var(--panel);color:var(--terang);font-weight:700}
 .modul{font-size:.85em;color:var(--redup);padding:.35em 0}
 .modul b{color:var(--teks)}
 .modul i{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:.5em}
 .status{border:1px solid var(--garis);border-radius:6px;padding:.6em .8em;font-size:.8em;
 color:var(--redup);background:var(--panel)}
 .status b{color:var(--teks)}
 .hidup{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--aksen);
 margin-right:.35em;animation:denyut 1.6s infinite}
 @keyframes denyut{0%{box-shadow:0 0 0 0 rgba(46,204,113,.5)}70%{box-shadow:0 0 0 8px rgba(46,204,113,0)}100%{box-shadow:0 0 0 0 rgba(46,204,113,0)}}
 .isi{flex:1;min-width:0;padding:1.3em 1.6em 2.5em;max-width:1240px}
 h1.judul-halaman{font-size:1.8em;font-weight:900;margin:.1em 0 .4em;letter-spacing:.01em}
 h2{font-size:1.12em;font-weight:700;margin:1.6em 0 .5em}
 h2::before{content:'';display:inline-block;width:.5em;height:.5em;background:var(--aksen);
 border-radius:2px;margin-right:.55em}
 .perhatian{background:var(--panel);border:1px solid var(--garis);
 border-radius:6px;padding:.55em 1em;color:var(--redup);font-size:.9em}
 .ticker{display:flex;align-items:stretch;border:1px solid var(--garis);border-radius:6px;
 background:var(--panel);overflow:hidden;margin:1em 0}
 .ticker-label{flex:0 0 auto;display:flex;align-items:center;background:var(--panel2);
 color:var(--terang);font-size:11px;font-weight:700;letter-spacing:.14em;
 padding:.55em .9em;border-right:1px solid var(--garis);white-space:nowrap}
 .ticker-viewport{flex:1;overflow:hidden;display:flex;align-items:center}
 .ticker-track{display:inline-flex;white-space:nowrap;animation:geser 80s linear infinite}
 .ticker:hover .ticker-track{animation-play-state:paused}
 @keyframes geser{from{transform:translateX(0)}to{transform:translateX(-50%)}}
 .ticker-item{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:.82em;
 color:var(--teks);margin-right:2.6em}
 .ticker-item .w{color:var(--redup)}
 .ticker-item .s{color:var(--kuning);font-weight:700}
 .angka{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:.9em;margin:1.1em 0}
 .kotak{background:var(--panel);border:1px solid var(--garis);
 border-radius:6px;padding:.9em 1.05em}
 .kotak b{display:block;font-size:2.65em;font-weight:900;line-height:1.05;color:var(--terang)}
 .kotak.utama b{color:var(--kuning)}
 .kotak .label{display:block;color:var(--redup);font-size:11px;text-transform:uppercase;
 letter-spacing:.14em;margin-top:.4em}
 .kotak .sub{color:var(--redup);font-size:.78em;display:block;margin-top:.2em}
 .kotak .spark{display:block;margin-top:.55em}
 .dua-kolom{display:grid;grid-template-columns:1fr 1fr;gap:.9em}
 @media (max-width:900px){.dua-kolom{grid-template-columns:1fr}}
 .panel{background:var(--panel);border:1px solid var(--garis);border-radius:6px;padding:1em 1.1em}
 .panel h3{margin:.1em 0 .6em;font-size:.95em}
 .panel .kecil{margin-top:.5em}
 .kartu-jar{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:.9em}
 .kartu{background:var(--panel);border:1px solid var(--garis);
 border-radius:6px;padding:.9em 1.05em}
 .kartu .kode{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:1.2em;
 font-weight:700;color:var(--kuning)}
 .kartu .besar{font-size:1.9em;font-weight:900}
 .kartu .meta{color:var(--redup);font-size:.82em}
 .kartu a{font-size:.88em}
 .bungkus-tabel{overflow-x:auto;background:var(--panel);border:1px solid var(--garis);border-radius:6px}
 table{border-collapse:collapse;width:100%}
 th,td{padding:.55em .8em;text-align:left;vertical-align:top;font-size:.9em;border-bottom:1px solid var(--garis)}
 thead th{background:var(--bg);color:var(--redup);font-size:.78em;text-transform:uppercase;letter-spacing:.07em;border-bottom:1px solid var(--garis)}
 tbody tr:hover{background:var(--panel2)}
 .lencana{display:inline-block;min-width:2em;text-align:center;padding:.12em .55em;border-radius:4px;
 background:var(--panel2);color:var(--teks);font-weight:700;font-size:.85em}
 .lencana.kuat{background:var(--merah);color:#fff}
 .lencana.kuning{background:var(--kuning);color:#141414}
 .lencana.bukti-kuat{background:var(--aksen);color:#08130c;letter-spacing:.06em;white-space:nowrap}
 .lencana.bukti-lemah{background:transparent;border:1px solid var(--kuning);color:var(--kuning);letter-spacing:.06em;white-space:nowrap}
 .lencana.indikasi{background:transparent;border:1px solid var(--pink);color:var(--pink);letter-spacing:.06em}
 .lencana.mini{font-size:.66em;min-width:0;padding:.08em .45em;vertical-align:middle}
 .cip{display:inline-block;padding:.15em .6em;border-radius:4px;border:1px solid var(--garis);
 font-size:.8em;color:var(--redup);margin-right:.4em}
 .cip b{color:var(--teks)}
 a{color:var(--aksen);text-decoration:none} a:hover{text-decoration:underline}
 .mono{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:.86em;color:#cfe6d4}
 .kecil{color:var(--redup);font-size:.85em}
 .tombol{display:inline-block;background:var(--aksen);color:#08130c;font-weight:700;
 padding:.45em 1.1em;border-radius:4px}
 .tombol:hover{text-decoration:none;filter:brightness(1.1)}
 .legenda{font-size:.82em;color:var(--redup);margin-top:.4em}
 .legenda i{display:inline-block;width:10px;height:10px;border-radius:50%;margin:0 .3em 0 .9em}
 .panas-legenda{display:flex;gap:.4em;align-items:center;font-size:.78em;color:var(--redup);margin-top:.5em;flex-wrap:wrap}
 .panas-legenda i{display:inline-block;width:14px;height:14px;border-radius:3px}
 footer{border-top:1px solid var(--garis);color:var(--redup);font-size:.82em;padding:1em 0 0;margin-top:2em}
</style>
"""


def db():
    uri = "file:" + DB_PATH + "?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=30)
    con.row_factory = sqlite3.Row
    return con


def e(s):
    return html.escape("" if s is None else str(s))


def kontak_teks(kontak_json):
    """kontak_json -> teks terbaca (daftar JSON atau string apa adanya)."""
    if not kontak_json:
        return ""
    try:
        data = json.loads(kontak_json)
    except (ValueError, TypeError):
        return str(kontak_json)
    if isinstance(data, list):
        bagian = []
        for item in data:
            if isinstance(item, dict):
                bagian.append("; ".join(f"{k}: {v}" for k, v in item.items()))
            else:
                bagian.append(str(item))
        return "; ".join(bagian)
    return str(data)


def kontak_pasangan(kontak_json):
    """kontak_json -> daftar (jenis, nilai); string bebas menjadi ('teks', isi)."""
    if not kontak_json:
        return []
    try:
        data = json.loads(kontak_json)
    except (ValueError, TypeError):
        return [("teks", str(kontak_json))]
    hasil = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "jenis" in item and "nilai" in item:
                hasil.append((str(item["jenis"]), str(item["nilai"])))
            elif isinstance(item, dict):
                for k, v in item.items():
                    hasil.append((str(k), str(v)))
            else:
                hasil.append(("teks", str(item)))
    return hasil


def status_ct():
    """Ringkasan status penangkap dari stats.json; None bila tak terbaca."""
    try:
        with open(STATS_PATH, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    log = d.get("log", {})
    bagian = []
    for nama in ("argon2026h2", "nimbus2026"):
        info = log.get(nama) or {}
        label = "Argon" if nama.startswith("argon") else "Nimbus"
        if info.get("status") == "ok":
            lag = info.get("tertinggal", "?")
            if isinstance(lag, (int, float)) and lag < 0:
                lag = 0
            bagian.append(f"{label}: terhubung (lag {lag})")
        else:
            bagian.append(f"{label}: {info.get('status', 'tidak diketahui')}")
    wib = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M")
    return (f"<b>{d.get('entri_diproses', 0):,}</b> entri diproses run ini<br>"
            + "<br>".join(e(b) for b in bagian)
            + f"<br>Diperbarui per {wib} WIB").replace(",", ".")


def halaman(judul, isi, aktif="beranda"):
    st = status_ct()
    blok_status = (f"<div class='status'><span class='hidup'></span>"
                   f"<b>Penangkap CT aktif</b><br>{st}</div>") if st else \
                  "<div class='status'>Status penangkap tidak terbaca.</div>"
    nav = "".join(
        f"<a href='{href}'{' class=\"aktif\"' if kunci == aktif else ''}>{label}</a>"
        for href, label, kunci in [("/", "Beranda", "beranda"),
                                   ("/kandidat", "Umpan kelahiran", "kandidat")])
    return ("<!DOCTYPE html><html lang=\"id\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<title>{e(judul)}</title>{GAYA}</head><body><div class='kerangka'>"
            "<aside><div class='merek'><span class='titik'></span>"
            "<b>MATI DI <span>AKAR</span></b></div>"
            "<p class='slogan'>Sistem Intelijen Jaringan Judi Online. Semua orang "
            "memblokir situsnya, kami mematikan jaringannya.</p>"
            f"<h3>Navigasi</h3><nav>{nav}</nav>"
            "<h3>Modul</h3>"
            "<div class='modul'><i style='background:var(--aksen)'></i><b>LAHIR</b> — pantau log CT, tangkap domain saat lahir</div>"
            "<div class='modul'><i style='background:var(--kuning)'></i><b>SIDIK</b> — sidik jari & klaster cermin</div>"
            "<div class='modul'><i style='background:var(--pink)'></i><b>UANG</b> — simpul pembayaran bersama</div>"
            f"<h3>Status</h3>{blok_status}"
            "</aside>"
            f"<div class='isi'>{isi}"
            "<footer>MATI DI AKAR — Kartika Cyber Hackathon 2026, kategori "
            "Penangkalan. Semua temuan berstatus indikasi intelijen untuk "
            "diverifikasi pihak berwenang, bukan vonis.</footer></div>"
            "</div></body></html>")


def tabel_kandidat(rows):
    trs = []
    for r in rows:
        if r["skor"] >= 6:
            lencana = f"<span class='lencana kuat'>{r['skor']}</span>"
        elif r["skor"] >= 4:
            lencana = f"<span class='lencana kuning'>{r['skor']}</span>"
        else:
            lencana = f"<span class='lencana'>{r['skor']}</span>"
        label_jar = ""
        if "jar_id" in r.keys() and r["jar_id"]:
            label_jar = (f"<br><span class='kecil'>{e(r['jar_id'])}</span> "
                         + lencana_bukti(r["jar_bukti"], kecil=True))
        trs.append(
            f"<tr><td class='mono'>{e(r['domain'])}{label_jar}</td>"
            f"<td class='kecil'>{e(r['pertama_utc'])}</td>"
            f"<td>{lencana}</td>"
            f"<td>{e(r['alasan'])}</td>"
            f"<td class='kecil'>{e(r['penerbit'])}</td></tr>")
    return ("<div class='bungkus-tabel'><table><thead><tr><th>Domain</th>"
            "<th>Waktu (UTC)</th><th>Skor</th><th>Alasan</th><th>Sumber log CT</th>"
            "</tr></thead><tbody>" + "".join(trs) + "</tbody></table></div>")


def svg_batang_jam(ember):
    """ember: list (label_jam, jumlah) -> grafik batang SVG."""
    w, h, dasar = 520, 170, 140
    maks = max([n for _, n in ember] + [1])
    lebar = w / max(len(ember), 1)
    bagian = []
    for i, (label, n) in enumerate(ember):
        tinggi = (n / maks) * 105
        x = i * lebar + lebar * 0.18
        bagian.append(
            f"<rect x='{x:.0f}' y='{dasar - tinggi:.0f}' width='{lebar * 0.64:.0f}' "
            f"height='{tinggi:.0f}' rx='3' fill='#2ecc71'/>"
            f"<text x='{x + lebar * 0.32:.0f}' y='{dasar - tinggi - 5:.0f}' "
            f"fill='#e8efe9' font-size='11' text-anchor='middle'>{n}</text>"
            f"<text x='{x + lebar * 0.32:.0f}' y='{dasar + 16:.0f}' "
            f"fill='#93a698' font-size='10' text-anchor='middle'>{e(label)}</text>")
    return (f"<svg viewBox='0 0 {w} {h}' width='100%' role='img'>"
            f"<line x1='0' y1='{dasar}' x2='{w}' y2='{dasar}' stroke='#1e2b22'/>"
            + "".join(bagian) + "</svg>")


def svg_donat_skor(kuat, sedang, lemah):
    """Donat distribusi skor kandidat: kuat >=6, sedang 4-5, lemah <=3."""
    total = max(kuat + sedang + lemah, 1)
    r, keliling = 62, 2 * math.pi * 62
    segmen = [(kuat, "#e74c3c", "Kuat (skor ≥ 6)"),
              (sedang, "#f1c40f", "Sedang (4–5)"),
              (lemah, "#3a4a3f", "Lemah (≤ 3)")]
    lingkaran, legenda, awal = [], [], 0.0
    for nilai, warna, label in segmen:
        frac = nilai / total
        lingkaran.append(
            f"<circle cx='85' cy='85' r='{r}' fill='none' stroke='{warna}' "
            f"stroke-width='22' stroke-dasharray='{frac * keliling:.1f} {keliling:.1f}' "
            f"stroke-dashoffset='{-awal * keliling:.1f}' "
            f"transform='rotate(-90 85 85)'/>")
        legenda.append(
            f"<div class='modul'><i style='background:{warna}'></i>{label}: "
            f"<b>{nilai:,}</b> ({frac * 100:.0f}%)</div>".replace(",", "."))
        awal += frac
    return ("<div style='display:flex;gap:1em;align-items:center;flex-wrap:wrap'>"
            f"<svg viewBox='0 0 170 170' width='150' role='img'>"
            + "".join(lingkaran)
            + f"<text x='85' y='82' fill='#e8efe9' font-size='19' font-weight='700' "
              f"text-anchor='middle'>{total:,}</text>".replace(",", ".")
            + "<text x='85' y='102' fill='#93a698' font-size='11' "
              "text-anchor='middle'>kandidat</text></svg>"
            f"<div>{''.join(legenda)}</div></div>")


def label_uang(jenis):
    """'bank:BCA' -> 'Bank BCA'; 'ewallet:DANA' -> 'E-wallet DANA'; 'qris' -> 'QRIS'.
    Hanya label jenis; nilai nomor tidak pernah dirender ke halaman."""
    j = (jenis or "").strip()
    if ":" in j:
        aw, nama = j.split(":", 1)
        aw = {"bank": "Bank", "ewallet": "E-wallet"}.get(aw.lower(), aw)
        return f"{aw} {nama}"
    return "QRIS" if j.lower() == "qris" else j


# Nilai kontak generik dari mekanisme berbagi Telegram (t.me/share/url,
# t.me/addlist/...) — token mekanisme, BUKAN identitas kontak operator,
# jadi tidak dihitung sebagai bukti kuat (definisi diperketat atas
# keputusan pengguna, 2026-11-10). Daftar eksplisit dari enumerasi data.
KONTAK_GENERIK = {"share", "addlist"}


def kontak_generik(nilai):
    return (nilai or "").strip().lower() in KONTAK_GENERIK


def bukti_kuat(bukti):
    """BUKTI KUAT (aturan ketat): ada segmen favicon:/uang:, atau segmen
    kontak: yang nilainya kontak operator nyata (bukan generik 'share' /
    'addlist'). Selain itu — simhash saja atau kontak generik saja —
    adalah BUKTI LEMAH."""
    if not bukti:
        return False
    for seg in bukti.split(";"):
        seg = seg.strip()
        if seg.startswith(("favicon:", "uang:")):
            return True
        if seg.startswith("kontak:"):
            nilai = seg.split(":", 2)[-1].strip()
            if not kontak_generik(nilai):
                return True
    return False


def lencana_bukti(bukti, kecil=False):
    """Label bukti TEKS eksplisit (pola kejujuran berlabel, lihat
    REFERENSI_HACKATHON.md Pola 5): BUKTI KUAT bila bukti memuat
    kontak operator/favicon/uang bersama, selain itu BUKTI LEMAH
    (simhash saja atau kontak generik 'share')."""
    kuat = bukti_kuat(bukti)
    kelas = "lencana bukti-kuat" if kuat else "lencana bukti-lemah"
    if kecil:
        kelas += " mini"
    return f"<span class='{kelas}'>{'BUKTI KUAT' if kuat else 'BUKTI LEMAH'}</span>"


def samarkan_angka(teks):
    """Samarkan deret >= 9 digit (nomor telepon/WA pihak ketiga) untuk
    tampilan web. Nama pengguna Telegram dan hash tidak terpengaruh."""
    return re.sub(r"\d{9,}", "••••", teks or "")


def bukti_tampil(bukti):
    """Versi tampil string bukti: nomor pada segmen 'uang:...:NOMOR'
    disamarkan ('uang:bank:BCA:••••'). Klasifikasi lencana tetap memakai
    string asli; berkas bukti CSV tetap memuat nilai asli untuk aparat."""
    if not bukti:
        return ""
    tampil = re.sub(r"(uang:[^;]*):(\d{6,})(?=;|$)", r"\1:••••", bukti)
    # segmen kontak whatsapp memuat nomor telepon: samarkan nilainya saja
    # (hash favicon dan nama pengguna telegram TIDAK ikut tersamar)
    return re.sub(r"(kontak:whatsapp:)[^;\s]+", r"\1••••", tampil)


def svg_sparkline(deret, warna="#0ddc77", w=132, h=30):
    """Sparkline SVG dari deret angka asli (per jam, lama -> baru)."""
    if not deret:
        return ""
    maks = max(list(deret) + [1])
    langkah = w / max(len(deret) - 1, 1)
    titik = []
    for i, n in enumerate(deret):
        y = h - 3 - (n / maks) * (h - 8)
        titik.append(f"{i * langkah:.1f},{y:.1f}")
    lx, ly = titik[-1].split(",")
    return (f"<svg viewBox='0 0 {w} {h}' width='{w}' height='{h}' role='img'>"
            f"<polyline points='{' '.join(titik)}' fill='none' stroke='{warna}' "
            f"stroke-width='1.8'/><circle cx='{lx}' cy='{ly}' r='2.6' "
            f"fill='{warna}'/></svg>")


HARI_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN_ID = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
            "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def svg_heatmap(sel, daftar_hari):
    """Heatmap kelahiran 7 hari x 24 jam (UTC) dari timestamp kandidat asli.
    sel: {(tgl_iso, jam): jumlah}; daftar_hari: list[date] lama -> baru."""
    sel_w, sel_h, celah = 33, 20, 3
    kiri, atas = 86, 22
    w = kiri + 24 * (sel_w + celah) + 6
    h = atas + 7 * (sel_h + celah) + 8
    maks = max(list(sel.values()) + [1])

    def warna(n):
        if n <= 0:
            return "#101c13"
        t = math.sqrt(n / maks)
        r = round(20 + (13 - 20) * t)
        g = round(35 + (220 - 35) * t)
        b = round(26 + (119 - 26) * t)
        return f"rgb({r},{g},{b})"

    bagian = []
    for jam in range(0, 24, 6):
        x = kiri + jam * (sel_w + celah) + sel_w / 2
        bagian.append(
            f"<text x='{x:.0f}' y='14' fill='#93a698' font-size='10' "
            f"text-anchor='middle' font-family='JetBrains Mono',monospace>"
            f"{jam:02d}</text>")
    for i, hari in enumerate(daftar_hari):
        y = atas + i * (sel_h + celah)
        label = (f"{HARI_ID[hari.weekday()][:3]} {hari.day:02d} "
                 f"{BULAN_ID[hari.month - 1]}")
        bagian.append(
            f"<text x='{kiri - 8}' y='{y + sel_h / 2 + 4:.0f}' fill='#93a698' "
            f"font-size='10.5' text-anchor='end'>{label}</text>")
        iso = hari.isoformat()
        for jam in range(24):
            n = sel.get((iso, jam), 0)
            x = kiri + jam * (sel_w + celah)
            bagian.append(
                f"<rect x='{x}' y='{y}' width='{sel_w}' height='{sel_h}' rx='3' "
                f"fill='{warna(n)}'><title>{label} {jam:02d}:00 UTC — "
                f"{n} kandidat</title></rect>")
    return (f"<svg viewBox='0 0 {w} {h}' width='100%' role='img'>"
            + "".join(bagian) + "</svg>")


def ticker_html(rows):
    """Ticker CT live: kandidat terbaru + stempel waktu UTC, data asli DB.
    Isi digandakan agar animasi CSS translateX(-50%) berputar mulus."""
    item = []
    for r in rows:
        waktu = (r["pertama_utc"] or "")[11:19]
        item.append(
            f"<span class='ticker-item'><span class='w'>{e(waktu)} UTC</span> "
            f"{e(r['domain'])} <span class='s'>skor {r['skor']}</span></span>")
    isi = "".join(item)
    return ("<div class='ticker'><span class='ticker-label'>LOG CT — "
            "KELAHIRAN TERBARU</span><div class='ticker-viewport'>"
            f"<div class='ticker-track'>{isi}{isi}</div></div></div>")


WARNA_BUKTI = {"kontak": "#2ecc71", "favicon": "#f1c40f", "uang": "#e56399"}


def graf_jaringan(jid, anggota, uang):
    """Graf relasi SVG: pusat jaringan, hub bukti bersama, domain di cincin luar."""
    # Hub: kontak bersama (selain kontak generik), favicon bersama, pembayaran per jenis.
    hitung_kontak, hitung_favicon = {}, {}
    for r in anggota:
        for jenis, nilai in kontak_pasangan(r["kontak_json"]):
            if not kontak_generik(nilai):
                hitung_kontak[(jenis, nilai)] = hitung_kontak.get((jenis, nilai), 0) + 1
        if r["favicon_hash"]:
            hitung_favicon[r["favicon_hash"]] = hitung_favicon.get(r["favicon_hash"], 0) + 1
    hub = {}  # kunci -> (label, warna)
    for (jenis, nilai), n in hitung_kontak.items():
        if n >= 2:
            label = f"{jenis}: {nilai}"
            if len(re.sub(r"\D", "", nilai)) >= 9:  # nomor WA/telepon: samarkan
                label = f"{jenis}: ••••"
            hub[("kontak", jenis, nilai)] = (label, WARNA_BUKTI["kontak"])
    for fav, n in hitung_favicon.items():
        if n >= 2:
            hub[("favicon", str(fav))] = (f"favicon {fav}", WARNA_BUKTI["favicon"])
    jenis_uang = {}
    for u in uang:
        jenis_uang.setdefault(u["domain"], set()).add(u["jenis"])
        kunci = ("uang", u["jenis"])
        if kunci not in hub:
            label = u["jenis"].split(":")[-1] if ":" in u["jenis"] else u["jenis"]
            hub[kunci] = (f"pembayaran: {label}", WARNA_BUKTI["uang"])

    def hub_domain(r):
        kunci = []
        for jenis, nilai in kontak_pasangan(r["kontak_json"]):
            if ("kontak", jenis, nilai) in hub:
                kunci.append(("kontak", jenis, nilai))
        if r["favicon_hash"] and ("favicon", str(r["favicon_hash"])) in hub:
            kunci.append(("favicon", str(r["favicon_hash"])))
        for jenis in jenis_uang.get(r["domain"], set()):
            kunci.append(("uang", jenis))
        return kunci

    def kuat(r):
        return bukti_kuat(r["bukti"])

    daftar = sorted(anggota, key=lambda r: (not kuat(r), r["domain"]))
    kunci_hub = list(hub.keys())
    W, H = 980, 600
    cx, cy = W / 2, H / 2
    pos_hub = {}
    for i, k in enumerate(kunci_hub):
        sudut = 2 * math.pi * i / max(len(kunci_hub), 1) - math.pi / 2
        pos_hub[k] = (cx + 150 * math.cos(sudut), cy + 118 * math.sin(sudut))
    bagian = []
    n = len(daftar)
    pos_dom = []
    for i, r in enumerate(daftar):
        sudut = 2 * math.pi * i / max(n, 1) - math.pi / 2
        x, y = cx + 400 * math.cos(sudut), cy + 248 * math.sin(sudut)
        pos_dom.append((x, y))
        for k in hub_domain(r)[:2]:
            hx, hy = pos_hub[k]
            bagian.append(f"<line x1='{x:.0f}' y1='{y:.0f}' x2='{hx:.0f}' y2='{hy:.0f}' "
                          f"stroke='{hub[k][1]}' stroke-opacity='.45' stroke-width='1.2'/>")
        if not hub_domain(r):
            bagian.append(f"<line x1='{x:.0f}' y1='{y:.0f}' x2='{cx:.0f}' y2='{cy:.0f}' "
                          "stroke='#3a4a3f' stroke-opacity='.5' stroke-dasharray='3 4'/>")
    bagian.append(f"<circle cx='{cx:.0f}' cy='{cy:.0f}' r='34' fill='#f1c40f'/>"
                  f"<text x='{cx:.0f}' y='{cy + 5:.0f}' font-size='15' font-weight='700' "
                  f"fill='#141414' text-anchor='middle'>{e(jid)}</text>")
    for k, (x, y) in pos_hub.items():
        label, warna = hub[k]
        lebar = max(len(label) * 6.6 + 18, 74)
        bagian.append(
            f"<rect x='{x - lebar / 2:.0f}' y='{y - 13:.0f}' width='{lebar:.0f}' height='26' "
            f"rx='13' fill='#0d1710' stroke='{warna}'/>"
            f"<text x='{x:.0f}' y='{y + 4:.0f}' font-size='11' fill='#e8efe9' "
            f"text-anchor='middle'>{e(label)}</text>")
    berlabel = 0
    for (x, y), r in zip(pos_dom, daftar):
        warna = "#2ecc71" if kuat(r) else "#5a6a5e"
        bagian.append(f"<circle cx='{x:.0f}' cy='{y:.0f}' r='5' fill='#0a0f0d' "
                      f"stroke='{warna}' stroke-width='2'/>")
        if berlabel < 28:
            jangkar = "start" if x >= cx else "end"
            dx = 9 if x >= cx else -9
            nama = r["domain"] if len(r["domain"]) <= 30 else r["domain"][:29] + "…"
            bagian.append(f"<text x='{x + dx:.0f}' y='{y + 3:.0f}' font-size='10.5' "
                          f"fill='#cfe6d4' text-anchor='{jangkar}'>{e(nama)}</text>")
            berlabel += 1
    sisa = f" ({n - 28} domain lain tanpa label)" if n > 28 else ""
    return ("<div class='panel'><h3>Graf relasi jaringan</h3>"
            f"<svg viewBox='0 0 {W} {H}' width='100%' role='img'>"
            + "".join(bagian) + "</svg>"
            "<p class='legenda'>Simpul penghubung = bukti bersama. Garis "
            "<i style='background:#2ecc71'></i>kontak bersama "
            "<i style='background:#f1c40f'></i>favicon sama "
            "<i style='background:#e56399'></i>pembayaran sejenis. "
            "Domain berlingkar hijau = berbukti kuat, abu-abu = bukti lemah "
            f"(simhash saja).{sisa}</p></div>")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # diamkan log bawaan
        pass

    def kirim(self, kode, isi, tipe="text/html; charset=utf-8", header_tambahan=None):
        data = isi.encode("utf-8") if isinstance(isi, str) else isi
        self.send_response(kode)
        self.send_header("Content-Type", tipe)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (header_tambahan or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def tidak_ada(self, apa):
        self.kirim(404, halaman("Tidak ditemukan",
                                f"<h1 class='judul-halaman'>404</h1><p>{e(apa)} tidak "
                                "ditemukan.</p><p><a href='/'>Kembali ke beranda</a></p>"))

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path.startswith("/aset/font/"):
                self.aset_fon(unquote(path[len("/aset/font/"):]))
            elif path == "/":
                self.beranda()
            elif path == "/kandidat":
                self.kandidat()
            elif path.startswith("/jaringan/"):
                self.jaringan(unquote(path[len("/jaringan/"):]).strip("/"))
            elif path.startswith("/ekspor/") and path.endswith(".csv"):
                self.ekspor(unquote(path[len("/ekspor/"):-len(".csv")]).strip("/"))
            else:
                self.tidak_ada("Halaman")
        except sqlite3.Error as exc:
            self.kirim(503, halaman("Database sibuk",
                                    "<h1 class='judul-halaman'>Database sedang sibuk</h1>"
                                    f"<p class='kecil'>{e(exc)}</p>"
                                    "<p>Coba lagi sebentar lagi; penangkap CT "
                                    "sedang menulis data baru.</p>"))

    def aset_fon(self, nama):
        nama = os.path.basename(nama)
        berkas = os.path.join(BASE_DIR, "aset", "font", nama)
        if not nama.endswith(".woff2") or not os.path.isfile(berkas):
            self.tidak_ada("Berkas fon")
            return
        with open(berkas, "rb") as f:
            data = f.read()
        self.kirim(200, data, "font/woff2",
                   {"Cache-Control": "public, max-age=86400"})

    def beranda(self):
        con = db()
        try:
            total = con.execute("SELECT COUNT(*) FROM kandidat").fetchone()[0]
            kuat = con.execute(
                "SELECT COUNT(*) FROM kandidat WHERE skor >= 6").fetchone()[0]
            sedang = con.execute(
                "SELECT COUNT(*) FROM kandidat WHERE skor BETWEEN 4 AND 5").fetchone()[0]
            bersidik = con.execute("SELECT COUNT(*) FROM sidik").fetchone()[0]
            n_jaringan = con.execute(
                "SELECT COUNT(DISTINCT jaringan_id) FROM jaringan").fetchone()[0]
            n_uang = con.execute("SELECT COUNT(*) FROM uang").fetchone()[0]
            terbaru = con.execute(
                "SELECT k.*, j.jaringan_id AS jar_id, j.bukti AS jar_bukti "
                "FROM kandidat k LEFT JOIN jaringan j ON j.domain = k.domain "
                "ORDER BY k.pertama_utc DESC LIMIT 25").fetchall()
            # n_kuat dihitung di Python dengan bukti_kuat() (aturan ketat:
            # kontak generik 'share'/'addlist' tidak dihitung) — SQL LIKE
            # tidak bisa membedakan nilai segmen kontak.
            hitung_jar = {}
            for r in con.execute("SELECT jaringan_id, bukti FROM jaringan"):
                h = hitung_jar.setdefault(
                    r["jaringan_id"],
                    {"jaringan_id": r["jaringan_id"], "n": 0,
                     "n_kuat": 0, "n_uang": 0})
                h["n"] += 1
                if bukti_kuat(r["bukti"]):
                    h["n_kuat"] += 1
            for r in con.execute(
                    "SELECT j.jaringan_id AS jid, COUNT(*) AS n FROM uang u "
                    "JOIN jaringan j ON j.domain = u.domain "
                    "GROUP BY j.jaringan_id"):
                if r["jid"] in hitung_jar:
                    hitung_jar[r["jid"]]["n_uang"] = r["n"]
            terbesar = sorted(hitung_jar.values(),
                              key=lambda h: (-h["n"], h["jaringan_id"]))[:6]
            per_jam = con.execute(
                "SELECT substr(pertama_utc, 1, 13) AS jam, COUNT(*) AS n "
                "FROM kandidat GROUP BY jam ORDER BY jam DESC LIMIT 24").fetchall()
            kuat_jam = con.execute(
                "SELECT substr(pertama_utc, 1, 13) AS jam, COUNT(*) AS n "
                "FROM kandidat WHERE skor >= 6 GROUP BY jam "
                "ORDER BY jam DESC LIMIT 24").fetchall()
            sidik_jam = con.execute(
                "SELECT substr(diambil_utc, 1, 13) AS jam, COUNT(*) AS n "
                "FROM sidik GROUP BY jam ORDER BY jam DESC LIMIT 24").fetchall()
            maks_tgl = con.execute(
                "SELECT MAX(substr(pertama_utc, 1, 10)) FROM kandidat").fetchone()[0]
            panas = con.execute(
                "SELECT substr(pertama_utc, 1, 10) AS tgl, "
                "CAST(substr(pertama_utc, 12, 2) AS INTEGER) AS jam, "
                "COUNT(*) AS n FROM kandidat "
                "WHERE substr(pertama_utc, 1, 10) >= date(?, '-6 days') "
                "GROUP BY tgl, jam", (maks_tgl,)).fetchall()
            jid_terbesar = terbesar[0]["jaringan_id"] if terbesar else None
            graf_data = (self.ambil_jaringan(con, jid_terbesar)
                         if jid_terbesar else None)
        finally:
            con.close()

        def fmt(nilai):
            return f"{nilai:,}".replace(",", ".")

        hari_akhir = date.fromisoformat(maks_tgl) if maks_tgl else date.today()
        daftar_hari = [hari_akhir - timedelta(days=d) for d in range(6, -1, -1)]
        jam_urut = [r["jam"] for r in reversed(per_jam)]
        deret_total = [r["n"] for r in reversed(per_jam)]
        peta_kuat = {r["jam"]: r["n"] for r in kuat_jam}
        deret_kuat = [peta_kuat.get(j, 0) for j in jam_urut]
        peta_sidik = {r["jam"]: r["n"] for r in sidik_jam}
        deret_sidik = [peta_sidik.get(j, 0) for j in jam_urut]

        kotak_data = [
            (fmt(total), "Total kandidat", "domain terindikasi sejak 9 Nov 2026",
             True, svg_sparkline(deret_total, "#f1c40f")),
            (fmt(kuat), "Kandidat kuat (skor \u2265 6)",
             f"{kuat / max(total, 1) * 100:.0f}% dari total", False,
             svg_sparkline(deret_kuat)),
            (fmt(bersidik), "Domain bersidik",
             f"{bersidik / max(total, 1) * 100:.0f}% kandidat sudah diprofil",
             False, svg_sparkline(deret_sidik)),
            (fmt(n_jaringan), "Jaringan operator", "klaster cermin terpetakan",
             False, ""),
            (fmt(n_uang), "Temuan uang", "rekening, e-wallet, dan QRIS (indikasi)",
             False, ""),
        ]
        kotak = "".join(
            f"<div class='kotak{' utama' if utama else ''}'><b>{v}</b>"
            f"<span class='label'>{label}</span><span class='sub'>{sub}</span>"
            + (f"<span class='spark'>{spark}</span>" if spark else "")
            + "</div>"
            for v, label, sub, utama, spark in kotak_data)
        ember = [(r["jam"][11:13] + ":00", r["n"])
                 for r in list(reversed(per_jam))[-12:]]
        grafik = (f"<div class='panel'><h3>Kelahiran kandidat per jam (12 jam terakhir, UTC)</h3>"
                  f"{svg_batang_jam(ember)}</div>") if ember else ""
        donat = (f"<div class='panel'><h3>Distribusi skor kandidat</h3>"
                 f"{svg_donat_skor(kuat, sedang, total - kuat - sedang)}</div>")
        sel_panas = {(r["tgl"], r["jam"]): r["n"] for r in panas}
        blok_panas = (
            "<div class='panel'><h3>Heatmap kelahiran kandidat — 7 hari \u00d7 "
            "24 jam (UTC)</h3>"
            + svg_heatmap(sel_panas, daftar_hari)
            + "<div class='panas-legenda'>Sepi "
              "<i style='background:#101c13'></i>"
              "<i style='background:#123c26'></i>"
              "<i style='background:#0d9e57'></i>"
              "<i style='background:#0ddc77'></i> Ramai"
              "<span style='margin-left:1em'>Pemantauan dimulai 9 Nov 2026; "
              "hari sebelumnya kosong.</span></div></div>")
        blok_graf = ""
        if graf_data:
            anggota0, uang0 = graf_data
            blok_graf = (
                f"<h2>Graf jaringan terbesar — {e(jid_terbesar)} "
                f"({len(anggota0)} domain)</h2>"
                + graf_jaringan(jid_terbesar, anggota0, uang0)
                + f"<p><a href='/jaringan/{e(jid_terbesar)}'>Buka berkas "
                  f"lengkap jaringan {e(jid_terbesar)} \u2192</a></p>")
        kartu_jar = "".join(
            f"<div class='kartu'><span class='kode'>{e(r['jaringan_id'])}</span> "
            + ("<span class='lencana bukti-kuat mini'>BUKTI KUAT</span>"
               if (r['n_kuat'] or 0) > 0 else
               "<span class='lencana bukti-lemah mini'>BUKTI LEMAH</span>")
            + f"<br><span class='besar'>{r['n']}</span> "
              f"<span class='meta'>domain</span><br>"
              f"<span class='meta'>{r['n_kuat'] or 0} berbukti kuat \u00b7 "
              f"{r['n_uang'] or 0} temuan uang</span><br>"
              f"<a href='/jaringan/{e(r['jaringan_id'])}'>Buka berkas jaringan "
              f"\u2192</a></div>"
            for r in terbesar)
        isi = ("<h1 class='judul-halaman'>Dasbor Intelijen Jaringan Judol</h1>"
               + ticker_html(terbaru[:15])
               + "<div class='perhatian'><span class='lencana indikasi'>"
                 "INDIKASI</span> Semua temuan berstatus indikasi untuk "
                 "diverifikasi aparat, bukan vonis. Label bukti: "
                 "<b>BUKTI KUAT</b> = kontak operator, favicon, atau pembayaran "
                 "bersama; <b>BUKTI LEMAH</b> = kemiripan simhash saja.</div>"
               f"<div class='angka'>{kotak}</div>"
               f"<div class='dua-kolom'>{grafik}{donat}</div>"
               + blok_panas
               + blok_graf
               + "<h2>Umpan kelahiran terbaru (25 kandidat terakhir)</h2>"
               + tabel_kandidat(terbaru)
               + "<p><a class='tombol' href='/kandidat'>Lihat 200 kandidat "
                 "terbaru</a></p>"
               "<h2>Jaringan terbesar</h2>"
               f"<div class='kartu-jar'>{kartu_jar}</div>")
        self.kirim(200, halaman("MATI DI AKAR — Beranda", isi))

    def kandidat(self):
        con = db()
        try:
            rows = con.execute(
                "SELECT k.*, j.jaringan_id AS jar_id, j.bukti AS jar_bukti "
                "FROM kandidat k LEFT JOIN jaringan j ON j.domain = k.domain "
                "ORDER BY k.pertama_utc DESC LIMIT 200").fetchall()
        finally:
            con.close()
        isi = ("<h1 class='judul-halaman'>Umpan Kelahiran — 200 Kandidat Terbaru</h1>"
               "<p class='kecil'>Domain-domain judi online yang tertangkap log "
               "Certificate Transparency, dari yang paling baru lahir. Skor ≥ 6 "
               "berarti kandidat kuat.</p>"
               + tabel_kandidat(rows))
        self.kirim(200, halaman("MATI DI AKAR — Kandidat", isi, aktif="kandidat"))

    def ambil_jaringan(self, con, jid):
        anggota = con.execute(
            "SELECT j.domain, j.bukti, s.judul, s.favicon_hash, s.kontak_json "
            "FROM jaringan j LEFT JOIN sidik s ON s.domain = j.domain "
            "WHERE j.jaringan_id = ? ORDER BY j.domain", (jid,)).fetchall()
        if not anggota:
            return None
        uang = con.execute(
            "SELECT u.domain, u.jenis, u.nilai, u.konteks FROM uang u "
            "JOIN jaringan j ON j.domain = u.domain "
            "WHERE j.jaringan_id = ? ORDER BY u.domain, u.jenis", (jid,)).fetchall()
        return anggota, uang

    def jaringan(self, jid):
        con = db()
        try:
            hasil = self.ambil_jaringan(con, jid)
        finally:
            con.close()
        if hasil is None:
            self.tidak_ada(f"Jaringan {jid}")
            return
        anggota, uang = hasil
        n_kuat = sum(1 for r in anggota if bukti_kuat(r["bukti"]))
        trs = []
        for r in anggota:
            trs.append(
                f"<tr><td class='mono'>{e(r['domain'])}</td>"
                f"<td>{e(bukti_tampil(r['bukti']))}</td>"
                f"<td>{lencana_bukti(r['bukti'])}</td>"
                f"<td>{e(r['judul'])}</td>"
                f"<td class='mono'>{e(r['favicon_hash'])}</td>"
                f"<td>{e(samarkan_angka(kontak_teks(r['kontak_json'])))}</td></tr>")
        if uang:
            trs_uang = "".join(
                f"<tr><td class='mono'>{e(u['domain'])}</td>"
                f"<td>{e(label_uang(u['jenis']))}</td></tr>"
                for u in uang)
            blok_uang = ("<h2>Temuan uang anggota "
                         "<span class='lencana indikasi'>INDIKASI</span></h2>"
                         "<p class='kecil'>Nomor rekening dan e-wallet "
                         "disamarkan di tampilan web; nilai asli hanya ada "
                         "pada berkas bukti (CSV/PDF) untuk aparat. Semua "
                         "temuan berstatus indikasi dan wajib diverifikasi "
                         "sebelum ditindak.</p>"
                         "<div class='bungkus-tabel'><table><thead><tr>"
                         "<th>Domain</th><th>Jenis pembayaran</th></tr></thead>"
                         "<tbody>" + trs_uang + "</tbody></table></div>")
        else:
            blok_uang = ("<h2>Temuan uang anggota "
                         "<span class='lencana indikasi'>INDIKASI</span></h2>"
                         "<p class='kecil'>Belum ada temuan uang pada jaringan "
                         "ini.</p>")
        cips = (f"<span class='cip'><b>{len(anggota)}</b> domain anggota</span>"
                f"<span class='cip'><b>{n_kuat}</b> berbukti kuat</span>"
                f"<span class='cip'><b>{len(uang)}</b> temuan uang</span>")
        cips += (f" <span class='lencana bukti-kuat'>BUKTI KUAT: {n_kuat}</span> "
                 f"<span class='lencana bukti-lemah'>BUKTI LEMAH: "
                 f"{len(anggota) - n_kuat}</span>")
        isi = (f"<h1 class='judul-halaman'>Berkas Jaringan "
               f"<span class='lencana kuning'>{e(jid)}</span></h1>"
               f"<p>{cips}</p>"
               f"<p><a class='tombol' href='/ekspor/{e(jid)}.csv'>Unduh berkas CSV</a></p>"
               + graf_jaringan(jid, anggota, uang)
               + "<h2>Domain anggota dan bukti penggabungan</h2>"
               "<div class='bungkus-tabel'><table><thead><tr><th>Domain</th>"
               "<th>Bukti</th><th>Label bukti</th><th>Judul halaman</th><th>Favicon hash</th>"
               "<th>Kontak publik</th></tr></thead><tbody>"
               + "".join(trs) + "</tbody></table></div>" + blok_uang)
        self.kirim(200, halaman(f"MATI DI AKAR — Jaringan {jid}", isi))

    def ekspor(self, jid):
        con = db()
        try:
            hasil = self.ambil_jaringan(con, jid)
            if hasil is None:
                self.tidak_ada(f"Jaringan {jid}")
                return
            anggota, uang = hasil
        finally:
            con.close()
        uang_per_domain = {}
        for u in uang:
            teks = u["jenis"] + (f": {u['nilai']}" if u["nilai"] else "")
            if u["konteks"]:
                teks += f" ({u['konteks']})"
            uang_per_domain.setdefault(u["domain"], []).append(teks)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["domain", "jaringan_id", "bukti", "judul", "kontak",
                    "temuan_uang"])
        for r in anggota:
            w.writerow([r["domain"], jid, r["bukti"] or "", r["judul"] or "",
                        kontak_teks(r["kontak_json"]),
                        "; ".join(uang_per_domain.get(r["domain"], []))])
        self.kirim(200, buf.getvalue(), "text/csv; charset=utf-8",
                   {"Content-Disposition":
                    f'attachment; filename="jaringan_{jid}.csv"'})


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Dasbor MATI DI AKAR jalan di http://{HOST}:{PORT}/ (DB: {DB_PATH})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
