# -*- coding: utf-8 -*-
"""
Muat daftar benih domain judi online publik dan ekstrak batang merek.

Sumber benih (publik, untuk konteks merek yang sudah dikenal/diblokir):
- BrigsLabs/judol — Judi Online Domains Blacklist (GitHub)

Keluaran:
- data/benih_judol.txt : daftar domain mentah apa adanya dari sumber.
- data/merek.txt        : batang SLD yang muncul >= AMBANG kali (keluarga
                          domain operator), dipakai modul penilaian.
"""
import os
import re
import sys
import urllib.request
from collections import Counter

DASAR = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(DASAR, "data")
URL_BENIH = "https://raw.githubusercontent.com/BrigsLabs/judol/main/judol_domains.txt"
AMBANG_MEREK = 4


def main():
    os.makedirs(DATA, exist_ok=True)
    tujuan = os.path.join(DATA, "benih_judol.txt")
    print("Mengunduh", URL_BENIH)
    req = urllib.request.Request(URL_BENIH, headers={"User-Agent": "mati-di-akar/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        isi = r.read().decode("utf-8", "replace")
    with open(tujuan, "w", encoding="utf-8") as f:
        f.write(isi)

    domain = []
    for baris in isi.splitlines():
        b = baris.strip().lower()
        if not b or b.startswith("#"):
            continue
        b = b.split("#")[0].strip()
        b = b.split()[0] if b.split() else ""
        if "." in b:
            domain.append(b)
    print("Domain benih terbaca:", len(domain))

    hitung = Counter()
    for d in domain:
        bagian = d.split(".")
        sld = bagian[-2] if len(bagian) > 1 else bagian[0]
        sld = re.sub(r"[^a-z0-9]", "", sld)
        if len(sld) < 4:
            continue
        # Keluarga domain operator memakai pola merek+angka di kedua sisi
        # (mis. 001gb777, gb777x, 88winpro). Hitung semua varian potongan
        # angka agar inti mereknya muncul sebagai batang merek.
        varian = {
            sld,
            sld.lstrip("0123456789"),
            sld.rstrip("0123456789"),
            sld.strip("0123456789"),
        }
        for v in varian:
            if len(v) >= 4 and not v.isdigit():
                # Inti murni huruf yang terlalu pendek rawan tabrakan umum.
                if v.isalpha() and len(v) < 5:
                    continue
                hitung[v] += 1
    merek = sorted(m for m, n in hitung.items() if n >= AMBANG_MEREK)
    with open(os.path.join(DATA, "merek.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(merek) + "\n")
    print("Batang merek (frekuensi >= %d): %d" % (AMBANG_MEREK, len(merek)))
    print("Contoh merek:", ", ".join(merek[:15]))


if __name__ == "__main__":
    sys.exit(main())
