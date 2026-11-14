#!/usr/bin/env python3
"""MATI DI AKAR - Modul SIDIK (+ ekstraksi UANG dalam satu lintasan ambil).

Mengambil halaman publik domain kandidat dari tabel `kandidat`, lalu menyimpan:
  - sidik jari infrastruktur: hash favicon (MurmurHash3 gaya Shodan), simhash
    teks halaman, judul, URL akhir setelah pengalihan;
  - kontak publik operator: t.me, wa.me, api.whatsapp.com;
  - temuan uang: nomor rekening di dekat nama bank dan nomor e-wallet di dekat
    nama dompet digital (disimpan apa adanya sebagai indikasi).

Aturan main: observasi pasif data publik saja. Tanpa akun, tanpa transaksi,
tanpa pengiriman formulir. Jeda antar-domain dan batas ukuran unduhan dijaga.

Pakai:
  python sidik.py [--batas N] [--segarkan]
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import mmh3
import requests

AKAR = Path(__file__).resolve().parent
DB = AKAR / "data" / "matidiakar.db"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
BATAS_HALAMAN = 400_000
BATAS_FAVICON = 120_000
JEDA = 0.2

BANK = ["BCA", "BRI", "BNI", "MANDIRI", "BSI", "DANAMON", "PERMATA",
        "CIMB", "BJB", "BTN", "MEGA", "OCBC", "PANIN", "JAGO", "SEABANK",
        "ALLO", "NEO", "BLU"]
EWALLET = ["DANA", "OVO", "GOPAY", "SHOPEEPAY", "LINKAJA", "QRIS"]

RE_JUDUL = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
RE_FAVICON = re.compile(
    r"<link[^>]+rel=[\"'][^\"']*icon[^\"']*[\"'][^>]+href=[\"']([^\"']+)",
    re.I)
RE_FAVICON2 = re.compile(
    r"<link[^>]+href=[\"']([^\"']+)[\"'][^>]+rel=[\"'][^\"']*icon", re.I)
RE_SCRIPT = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.I | re.S)
RE_TAG = re.compile(r"<[^>]+>")
RE_TME = re.compile(r"(?:t\.me|telegram\.me)/([A-Za-z0-9_]{3,})", re.I)
RE_WAME = re.compile(r"wa\.me/(\d{8,15})", re.I)
RE_WAAPI = re.compile(r"api\.whatsapp\.com/send\?phone=(\d{8,15})", re.I)
RE_ANGKA = re.compile(r"\d[\d\s.\-]{7,}\d")
RE_TOKEN = re.compile(r"[a-z0-9]+")


def simhash64(teks: str) -> int:
    """Simhash 64-bit atas token kata teks yang terlihat."""
    v = [0] * 64
    for tok in RE_TOKEN.findall(teks.lower()):
        h = int.from_bytes(hashlib.md5(tok.encode()).digest()[:8], "little")
        for i in range(64):
            v[i] += 1 if (h >> i) & 1 else -1
    out = 0
    for i in range(64):
        if v[i] > 0:
            out |= 1 << i
    return out


def ke_signed64(n: int | None) -> int | None:
    """SQLite INTEGER bertanda 64-bit; simhash disimpan sebagai signed."""
    if n is None:
        return None
    return n - (1 << 64) if n >= (1 << 63) else n


def hash_favicon(data: bytes) -> int:
    """Hash favicon gaya Shodan: mmh3 atas base64 dibungkus 76 kolom."""
    b64 = base64.encodebytes(data)
    return mmh3.hash(b64)


def normal_angka(s: str) -> str:
    return re.sub(r"[\s.\-]", "", s)


def mirip_tanggal(nilai: str) -> bool:
    """True bila 8 digit pertama membentuk tanggal DDMMYYYY atau YYYYMMDD
    yang masuk akal (penyaring positif palsu: tanggal promo di dekat nama
    bank, mis. 20261005 = 5 Oktober 2026)."""
    if len(nilai) < 8:
        return False
    try:
        hh, bb, tttt = int(nilai[0:2]), int(nilai[2:4]), int(nilai[4:8])
        tttt2, bb2, hh2 = int(nilai[0:4]), int(nilai[4:6]), int(nilai[6:8])
    except ValueError:
        return False
    ddmmyyyy = 1 <= hh <= 31 and 1 <= bb <= 12 and 2018 <= tttt <= 2027
    yyyymmdd = 2018 <= tttt2 <= 2027 and 1 <= bb2 <= 12 and 1 <= hh2 <= 31
    return ddmmyyyy or yyyymmdd


def ekstrak_uang(teks: str, html: str) -> list[dict]:
    """Cari nomor di dekat nama bank / e-wallet pada teks halaman."""
    temuan: list[dict] = []
    polos = re.sub(r"\s+", " ", teks)
    for nama in BANK + EWALLET:
        for m in re.finditer(re.escape(nama), polos, re.I):
            jendela = polos[max(0, m.start() - 60): m.end() + 60]
            for a in RE_ANGKA.finditer(jendela):
                nilai = normal_angka(a.group(0))
                if mirip_tanggal(nilai) or nilai.startswith("08"):
                    continue  # tanggal promo / nomor HP, bukan rekening
                if nama in BANK and 8 <= len(nilai) <= 16:
                    temuan.append({"jenis": f"bank:{nama}", "nilai": nilai,
                                   "konteks": jendela.strip()[:120]})
                elif nama in EWALLET and nama != "QRIS" and \
                        9 <= len(nilai) <= 15 and nilai.startswith("0"):
                    temuan.append({"jenis": f"ewallet:{nama}", "nilai": nilai,
                                   "konteks": jendela.strip()[:120]})
    # QRIS yang disebut tanpa nomor: catat keberadaannya saja.
    if re.search(r"\bQRIS\b", polos, re.I):
        temuan.append({"jenis": "qris", "nilai": "", "konteks": "disebut di halaman"})
    unik = {(t["jenis"], t["nilai"]): t for t in temuan if t["nilai"] or t["jenis"] == "qris"}
    return list(unik.values())


def ekstrak_kontak(html: str) -> list[dict]:
    kontak: list[dict] = []
    for m in RE_TME.finditer(html):
        kontak.append({"jenis": "telegram", "nilai": m.group(1)})
    for m in RE_WAME.finditer(html):
        kontak.append({"jenis": "whatsapp", "nilai": m.group(1)})
    for m in RE_WAAPI.finditer(html):
        kontak.append({"jenis": "whatsapp", "nilai": m.group(1)})
    unik = {(k["jenis"], k["nilai"]): k for k in kontak}
    return list(unik.values())


def ambil(sesi: requests.Session, domain: str) -> dict:
    hasil: dict = {"domain": domain, "status_http": None, "url_final": None,
                   "judul": None, "favicon_hash": None, "simhash": None,
                   "kontak": [], "uang": [], "galat": None}
    html = None
    for skema in ("https", "http"):
        try:
            r = sesi.get(f"{skema}://{domain}/", timeout=8,
                         allow_redirects=True, stream=True)
            hasil["status_http"] = r.status_code
            hasil["url_final"] = r.url
            buf = bytearray()
            try:
                for potong in r.iter_content(chunk_size=16384):
                    if potong:
                        buf.extend(potong)
                        if len(buf) >= BATAS_HALAMAN:
                            break
            except Exception:
                pass  # koneksi putus di tengah: pakai yang sudah terkumpul
            if buf:
                html = bytes(buf[:BATAS_HALAMAN]).decode("utf-8", "ignore")
                break
            hasil["galat"] = "kosong"
        except requests.RequestException as e:
            hasil["galat"] = type(e).__name__
            continue
    if html is None:
        return hasil

    m = RE_JUDUL.search(html)
    if m:
        hasil["judul"] = re.sub(r"\s+", " ", m.group(1)).strip()[:200]

    teks = RE_TAG.sub(" ", RE_SCRIPT.sub(" ", html))
    teks = re.sub(r"\s+", " ", teks).strip()
    if teks:
        hasil["simhash"] = simhash64(teks)
    hasil["kontak"] = ekstrak_kontak(html)
    hasil["uang"] = ekstrak_uang(teks, html)

    # favicon
    fav_url = None
    m = RE_FAVICON.search(html) or RE_FAVICON2.search(html)
    if m:
        fav_url = m.group(1)
        if fav_url.startswith("//"):
            fav_url = "https:" + fav_url
        elif fav_url.startswith("/"):
            dasar = hasil["url_final"] or f"https://{domain}/"
            fav_url = dasar.split("/", 3)[0] + "//" + \
                dasar.split("/", 3)[2] + fav_url
        elif not fav_url.startswith("http"):
            dasar = (hasil["url_final"] or f"https://{domain}/").rsplit("/", 1)[0]
            fav_url = dasar + "/" + fav_url
    if not fav_url:
        fav_url = f"https://{domain}/favicon.ico"
    try:
        rf = sesi.get(fav_url, timeout=5, stream=True)
        if rf.status_code == 200:
            buf = bytearray()
            try:
                for potong in rf.iter_content(chunk_size=8192):
                    if potong:
                        buf.extend(potong)
                        if len(buf) >= BATAS_FAVICON:
                            break
            except Exception:
                pass
            if len(buf) >= 40:
                hasil["favicon_hash"] = hash_favicon(bytes(buf[:BATAS_FAVICON]))
    except requests.RequestException:
        pass
    return hasil


def pastikan_tabel(db: sqlite3.Connection) -> None:
    db.executescript("""
    CREATE TABLE IF NOT EXISTS sidik (
        domain       TEXT PRIMARY KEY,
        diambil_utc  TEXT NOT NULL,
        status_http  INTEGER,
        url_final    TEXT,
        judul        TEXT,
        favicon_hash INTEGER,
        simhash      INTEGER,
        kontak_json  TEXT,
        galat        TEXT
    );
    CREATE TABLE IF NOT EXISTS uang (
        domain  TEXT NOT NULL,
        jenis   TEXT NOT NULL,
        nilai   TEXT NOT NULL,
        konteks TEXT,
        PRIMARY KEY (domain, jenis, nilai)
    );
    """)
    db.commit()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batas", type=int, default=0, help="maks domain (0=semua)")
    ap.add_argument("--segarkan", action="store_true",
                    help="ambil ulang domain yang sudah punya sidik")
    args = ap.parse_args()

    db = sqlite3.connect(DB, check_same_thread=False, timeout=30)
    pastikan_tabel(db)
    if args.segarkan:
        rows = db.execute("SELECT domain FROM kandidat ORDER BY skor DESC").fetchall()
    else:
        rows = db.execute(
            "SELECT domain FROM kandidat WHERE domain NOT IN "
            "(SELECT domain FROM sidik) ORDER BY skor DESC").fetchall()
    daftar = [r[0] for r in rows]
    if args.batas:
        daftar = daftar[:args.batas]
    print(f"domain diambil: {len(daftar)}", flush=True)

    import threading
    from concurrent.futures import ThreadPoolExecutor

    lokal = threading.local()
    kunci = threading.Lock()
    hitung = {"i": 0, "ok": 0, "gagal": 0}

    def sesi_lokal() -> requests.Session:
        if not hasattr(lokal, "sesi"):
            s = requests.Session()
            s.headers.update({"User-Agent": UA})
            lokal.sesi = s
        return lokal.sesi

    def kerjakan(domain: str) -> None:
        h = ambil(sesi_lokal(), domain)
        with kunci:
            db.execute(
                "INSERT OR REPLACE INTO sidik VALUES (?,?,?,?,?,?,?,?,?)",
                (domain, datetime.now(timezone.utc).isoformat(),
                 h["status_http"], h["url_final"], h["judul"],
                 h["favicon_hash"], ke_signed64(h["simhash"]),
                 json.dumps(h["kontak"]), h["galat"]))
            for u in h["uang"]:
                db.execute("INSERT OR IGNORE INTO uang VALUES (?,?,?,?)",
                           (domain, u["jenis"], u["nilai"], u["konteks"]))
            db.commit()
            hitung["i"] += 1
            if h["status_http"] and h["status_http"] < 500:
                hitung["ok"] += 1
            else:
                hitung["gagal"] += 1
            if hitung["i"] % 25 == 0 or hitung["i"] == len(daftar):
                print(f"  {hitung['i']}/{len(daftar)} ok={hitung['ok']} "
                      f"gagal={hitung['gagal']}", flush=True)

    with ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(kerjakan, daftar))
    print(f"selesai: ok={hitung['ok']} gagal={hitung['gagal']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
