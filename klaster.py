#!/usr/bin/env python3
"""MATI DI AKAR - Pengelompokan jaringan operator (union-find).

Dua domain digabung ke jaringan yang sama bila berbagi bukti kuat:
  - hash favicon yang sama (bukan hash kosong/default),
  - kontak publik yang sama (Telegram / WhatsApp),
  - nomor rekening / e-wallet yang sama (dari tabel `uang`),
  - simhash halaman sangat dekat (jarak Hamming <= 3) DAN judul sama persis.

Hasil ditulis ke tabel `jaringan` (domain -> id jaringan) dan diringkas ke
layar: jaringan multi-domain diurutkan dari yang terbesar. Domain tunggal
tidak ditulis. Semua penggabungan adalah indikasi untuk verifikasi aparat,
bukan vonis.

Pakai:
  python klaster.py [--tampilkan N]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

AKAR = Path(__file__).resolve().parent
DB = AKAR / "data" / "matidiakar.db"

# Favicon yang terlalu umum (ikon bawaan CMS / placeholder 1x1) tidak boleh
# menggabungkan jaringan; hash yang muncul di > 15 domain dianggap umum.
BATAS_FAVICON_UMUM = 15
HAMMING_SIMHASH = 3


class DSU:
    def __init__(self) -> None:
        self.induk: dict[str, str] = {}

    def cari(self, x: str) -> str:
        self.induk.setdefault(x, x)
        while self.induk[x] != x:
            self.induk[x] = self.induk[self.induk[x]]
            x = self.induk[x]
        return x

    def gabung(self, a: str, b: str) -> None:
        ra, rb = self.cari(a), self.cari(b)
        if ra != rb:
            self.induk[rb] = ra


def ke_unsigned64(n: int) -> int:
    return n + (1 << 64) if n < 0 else n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tampilkan", type=int, default=15)
    args = ap.parse_args()

    db = sqlite3.connect(DB, timeout=30)
    db.execute("""CREATE TABLE IF NOT EXISTS jaringan (
        domain TEXT PRIMARY KEY,
        jaringan_id TEXT NOT NULL,
        bukti TEXT
    )""")

    baris = db.execute(
        "SELECT domain, favicon_hash, simhash, judul, kontak_json "
        "FROM sidik").fetchall()
    uang = db.execute("SELECT domain, jenis, nilai FROM uang "
                      "WHERE nilai != ''").fetchall()

    dsu = DSU()
    bukti: dict[str, list[str]] = defaultdict(list)

    def hubungkan(a: str, b: str, alasan: str) -> None:
        dsu.gabung(a, b)
        bukti[a].append(alasan)
        bukti[b].append(alasan)

    # 1) favicon sama
    per_favicon: dict[int, list[str]] = defaultdict(list)
    for domain, fav, _sim, _judul, _k in baris:
        if fav is not None:
            per_favicon[fav].append(domain)
    for fav, ds in per_favicon.items():
        if 1 < len(ds) <= BATAS_FAVICON_UMUM:
            for lain in ds[1:]:
                hubungkan(ds[0], lain, f"favicon:{fav}")

    # 2) kontak sama
    per_kontak: dict[str, list[str]] = defaultdict(list)
    for domain, _f, _s, _j, kontak_json in baris:
        try:
            for k in json.loads(kontak_json or "[]"):
                per_kontak[f"{k['jenis']}:{k['nilai']}"].append(domain)
        except (ValueError, KeyError):
            continue
    for kunci, ds in per_kontak.items():
        if len(ds) > 1:
            for lain in ds[1:]:
                hubungkan(ds[0], lain, f"kontak:{kunci}")

    # 3) rekening / e-wallet sama
    per_uang: dict[str, list[str]] = defaultdict(list)
    for domain, jenis, nilai in uang:
        per_uang[f"{jenis}:{nilai}"].append(domain)
    for kunci, ds in per_uang.items():
        ds = sorted(set(ds))
        if len(ds) > 1:
            for lain in ds[1:]:
                hubungkan(ds[0], lain, f"uang:{kunci}")

    # 4) simhash dekat + judul sama
    per_judul: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for domain, _f, sim, judul, _k in baris:
        if sim is not None and judul:
            per_judul[judul.strip().lower()].append(
                (domain, ke_unsigned64(sim)))
    for _judul, ds in per_judul.items():
        for i in range(len(ds)):
            for j in range(i + 1, len(ds)):
                jarak = bin(ds[i][1] ^ ds[j][1]).count("1")
                if jarak <= HAMMING_SIMHASH:
                    hubungkan(ds[i][0], ds[j][0], f"simhash:{jarak}")

    # Susun jaringan
    kelompok: dict[str, list[str]] = defaultdict(list)
    for domain in {r[0] for r in baris} | {u[0] for u in uang}:
        kelompok[dsu.cari(domain)].append(domain)
    jaringan = {akar: sorted(ds) for akar, ds in kelompok.items()
                if len(ds) > 1}
    jaringan_urut = sorted(jaringan.values(), key=len, reverse=True)

    db.execute("DELETE FROM jaringan")
    for idx, ds in enumerate(jaringan_urut, 1):
        jid = f"J{idx:03d}"
        for d in ds:
            db.execute("INSERT INTO jaringan VALUES (?,?,?)",
                       (d, jid, "; ".join(sorted(set(bukti.get(d, []))))))
    db.commit()

    total_domain = len({r[0] for r in baris})
    tergabung = sum(len(ds) for ds in jaringan_urut)
    print(f"domain bersidik: {total_domain}")
    print(f"jaringan multi-domain: {len(jaringan_urut)} "
          f"({tergabung} domain tergabung)")
    print()
    for idx, ds in enumerate(jaringan_urut[:args.tampilkan], 1):
        print(f"J{idx:03d} - {len(ds)} domain")
        for d in ds:
            b = sorted(set(bukti.get(d, [])))
            print(f"  {d}  [{'; '.join(b[:3])}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
