# -*- coding: utf-8 -*-
"""
MATI DI AKAR — modul LAHIR: pemantau langsung log Certificate Transparency.

Catatan rekayasa (9 Nov 2026): aliran publik CertStream (calidog) terbukti
tidak mengalirkan data dari jaringan ini saat pengujian (websocket tersambung
tetapi nol pesan), jadi modul ini memantau log CT secara LANGSUNG memakai
API standar RFC 6962 (get-sth + get-entries) pada beberapa log besar.

Cara kerja:
- Untuk tiap log, kursor indeks terakhir disimpan di tabel ct_state.
- Saat pertama kali, kursor dimulai dari ujung pohon saat itu (tidak
  memproses miliaran entri lama) lalu maju mengikuti entri baru.
- Setiap entri di-parse (ctparse) untuk mengambil nama domain, dinilai
  (penilaian.nilai_domain), dan kandidat di atas ambang disimpan ke tabel
  kandidat di data/matidiakar.db. Statistik ditulis ke data/stats.json.

Berjalan terus-menerus di bawah systemd (Restart=always).
"""
import base64
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ctparse import parse_leaf_bytes          # noqa: E402
from penilaian import nilai_domain, layak_parse, AMBANG_SIMPAN, AMBANG_KUAT  # noqa: E402

DASAR = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(DASAR, "data")
BERKAS_DB = os.path.join(DATA, "matidiakar.db")
BERKAS_STATS = os.path.join(DATA, "stats.json")

# (nama, base URL) — diverifikasi 9 Nov 2026 dari VM ini: argon (Google)
# dan nimbus (Cloudflare) merespons; mammoth/sabre/oak mengembalikan
# respons kosong dari jaringan ini sehingga tidak dipakai.
LOGS = [
    ("argon2026h2", "https://ct.googleapis.com/logs/us1/argon2026h2/"),
    ("nimbus2026", "https://ct.cloudflare.com/logs/nimbus2026/"),
]
UKURAN_BATCH = 1024
BATCH_PER_SIKLUS = 12
JEDA_SIKLUS = 0.5
TIMEOUT = 25

# Satu sesi HTTP bersama: koneksi dipakai ulang (pooling) dan proxy
# lingkungan dibaca otomatis oleh requests. Membuka TLS baru per permintaan
# terbukti menjadi penghambat utama laju pemrosesan.
_SESI = requests.Session()
_SESI.headers.update({"User-Agent": "mati-di-akar/0.2"})

statistik = {
    "mulai_utc": datetime.now(timezone.utc).isoformat(),
    "entri_diproses": 0,
    "domain_dilihat": 0,
    "kandidat_baru": 0,
    "kandidat_kuat": 0,
    "parse_gagal": 0,
    "log": {},
    "terakhir_utc": None,
}
_koneksi = None


def db():
    global _koneksi
    if _koneksi is None:
        os.makedirs(DATA, exist_ok=True)
        _koneksi = sqlite3.connect(BERKAS_DB)
        _koneksi.execute(
            """
            CREATE TABLE IF NOT EXISTS kandidat (
                domain      TEXT PRIMARY KEY,
                pertama_utc TEXT NOT NULL,
                penerbit    TEXT,
                skor        INTEGER NOT NULL,
                alasan      TEXT,
                semua_domain TEXT
            )
            """
        )
        _koneksi.execute(
            """
            CREATE TABLE IF NOT EXISTS ct_state (
                log       TEXT PRIMARY KEY,
                tree_size INTEGER NOT NULL,
                kursor    INTEGER NOT NULL
            )
            """
        )
        _koneksi.commit()
    return _koneksi


def ambil_json(url):
    r = _SESI.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def flush_stats():
    statistik["terakhir_utc"] = datetime.now(timezone.utc).isoformat()
    tmp = BERKAS_STATS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(statistik, f, ensure_ascii=False, indent=1)
    os.replace(tmp, BERKAS_STATS)


def proses_domain(daftar_domain, sumber_log):
    kini = datetime.now(timezone.utc).isoformat()
    for mentah in daftar_domain:
        d = (mentah or "").lower().strip().strip(".")
        if d.startswith("*."):
            d = d[2:]
        if not d or "." not in d:
            continue
        statistik["domain_dilihat"] += 1
        skor, alasan = nilai_domain(d)
        if skor < AMBANG_SIMPAN:
            continue
        try:
            cur = db().execute(
                "INSERT OR IGNORE INTO kandidat VALUES (?,?,?,?,?,?)",
                (d, kini, sumber_log, skor, "; ".join(alasan),
                 json.dumps(daftar_domain)[:2000]),
            )
            if cur.rowcount:
                statistik["kandidat_baru"] += 1
                if skor >= AMBANG_KUAT:
                    statistik["kandidat_kuat"] += 1
                print("[TANGKAP] %s skor=%d %s" % (d, skor, "; ".join(alasan)),
                      flush=True)
        except sqlite3.Error as e:
            print("[DB-ERR]", e, flush=True)


def poll_log(nama, base):
    """Proses entri baru dari satu log hingga mengejar ujung pohon."""
    info = statistik["log"].setdefault(nama, {"status": "?", "tertinggal": None})
    try:
        sth = ambil_json(base + "ct/v1/get-sth")
        tree_size = int(sth["tree_size"])
    except Exception as e:  # noqa: BLE001
        info["status"] = "tidak-terjangkau: %s" % type(e).__name__
        return
    info["status"] = "ok"
    baris = db().execute("SELECT kursor FROM ct_state WHERE log=?",
                         (nama,)).fetchone()
    if baris is None:
        kursor = tree_size  # mulai dari sekarang, bukan dari nol
        db().execute("INSERT INTO ct_state VALUES (?,?,?)",
                     (nama, tree_size, kursor))
        db().commit()
        print("[CT] %s: mulai memantau dari indeks %d" % (nama, kursor),
              flush=True)
    else:
        kursor = int(baris[0])

    for _ in range(BATCH_PER_SIKLUS):
        if kursor >= tree_size:
            break
        akhir = min(tree_size - 1, kursor + UKURAN_BATCH - 1)
        try:
            resp = ambil_json("%sct/v1/get-entries?start=%d&end=%d"
                              % (base, kursor, akhir))
        except Exception as e:  # noqa: BLE001
            print("[CT] %s get-entries gagal: %r" % (nama, e), flush=True)
            break
        entri = resp.get("entries") or []
        if not entri:
            break
        for e in entri:
            statistik["entri_diproses"] += 1
            try:
                leaf = base64.b64decode(e.get("leaf_input", ""))
            except Exception:  # noqa: BLE001
                statistik["parse_gagal"] += 1
                continue
            # Saringan byte cepat: lewati entri tanpa token sinyal sama sekali.
            if not layak_parse(leaf.lower()):
                statistik["entri_tersaring"] = \
                    statistik.get("entri_tersaring", 0) + 1
                continue
            daftar = parse_leaf_bytes(leaf)
            if not daftar:
                statistik["parse_gagal"] += 1
                continue
            proses_domain(daftar, nama)
        kursor += len(entri)
        db().execute("UPDATE ct_state SET tree_size=?, kursor=? WHERE log=?",
                     (tree_size, kursor, nama))
        db().commit()
    info["tertinggal"] = tree_size - kursor


def main():
    db()
    flush_stats()
    print("[CT] Pemantau log CT mulai. Log target: %s"
          % ", ".join(n for n, _ in LOGS), flush=True)
    while True:
        for nama, base in LOGS:
            try:
                poll_log(nama, base)
            except Exception as e:  # noqa: BLE001
                print("[CT] %s gangguan tak terduga: %r" % (nama, e), flush=True)
        flush_stats()
        time.sleep(JEDA_SIKLUS)


if __name__ == "__main__":
    main()
