# -*- coding: utf-8 -*-
"""
Penilaian domain kandidat judi online (MATI DI AKAR — modul LAHIR).

Skor berbasis sinyal berlapis pada nama domain:
- kata kunci kuat khas judol Indonesia (bobot besar),
- kata kunci lemah (hanya dihitung bila ada sinyal lain),
- substring merek dari daftar benih (data/merek.txt),
- TLD yang sering dipakai situs judol,
- pola angka pada label domain.

Ambang simpan: skor >= AMBANG_SIMPAN. Label "kuat": skor >= AMBANG_KUAT.
Semua hasil adalah INDIKASI untuk diverifikasi, bukan vonis.

Fungsi layak_parse() adalah saringan cepat tingkat byte untuk aliran CT:
domain yang bisa mencapai ambang simpan PASTI memuat minimal satu kata
kuat atau batang merek (sinyal lain maksimal bernilai 2), jadi entri log
yang byte-nya tidak memuat token apa pun boleh dilewati tanpa parse DER.
"""
import os
import re

DASAR = os.path.dirname(os.path.abspath(__file__))
BERKAS_MEREK = os.path.join(DASAR, "data", "merek.txt")

AMBANG_SIMPAN = 4
AMBANG_KUAT = 6

# Kata kunci kuat: hampir selalu judol bila muncul di nama domain.
KATA_KUAT = {
    "gacor": 3,
    "maxwin": 3,
    "qiuqiu": 3,
    "togel": 3,
    "judol": 3,
    "slot": 2,
    "kasino": 2,
    "casino": 2,
    "mahjong": 2,
    "zeus": 2,
    "olympus": 2,
    "scatter": 2,
    "jackpot": 2,
    "spaceman": 2,
    "situsjud": 3,
    "agenjud": 3,
    "bandarjudi": 3,
    "taruhan": 2,
    "sbobet": 3,
    "idnplay": 3,
    "pragmatic": 2,
    "habanero": 2,
    "joker123": 3,
    "tangkas": 2,
    "hoki": 2,
    "aviator": 2,
    "cuan": 2,
}

# Kata kunci lemah: hanya bernilai bila ada sinyal kuat/merek lain.
KATA_LEMAH = {
    "bet": 1,
    "toto": 1,
    "rtp": 1,
    "poker": 1,
    "domino": 1,
    "bandar": 1,
    "depo": 1,
    "win": 1,
    "bola": 1,
    "qq": 1,
    "88": 1,
    "777": 1,
    "138": 1,
    "365": 1,
}

TLD_MENCURIGAKAN = {
    "xyz", "top", "click", "vip", "live", "fun", "site", "online",
    "store", "bet", "casino", "poker", "win", "today", "buzz", "sbs",
    "cfd", "club", "link", "one", "uno", "pro", "asia", "info", "icu",
    "monster", "rest", "quest", "bond", "cyou", "lol", "autos",
}


def muat_merek():
    """Muat daftar batang merek dari data/merek.txt (satu per baris)."""
    merek = []
    if os.path.exists(BERKAS_MEREK):
        with open(BERKAS_MEREK, encoding="utf-8") as f:
            for baris in f:
                b = baris.strip().lower()
                if len(b) >= 4:
                    merek.append(b)
    return merek


MEREK = muat_merek()

# Batang murni huruf yang merupakan kata umum (Inggris/Indonesia) tidak boleh
# menjadi pemicu tunggal: di daftar benih kata seperti "group", "paris",
# "royal", "sport" muncul sebagai bagian nama operator, tetapi di internet
# umum kata-kata ini mayoritas situs sah. Bobotnya diturunkan menjadi +2
# sehingga tetap berguna sebagai sinyal pendukung, tidak cukup sendirian.
STOP_GENERIK = {
    "group", "paris", "royal", "sport", "sports", "global", "online",
    "digital", "media", "star", "stars", "club", "asia", "mega", "super",
    "grand", "prima", "jaya", "link", "play", "game", "games", "king",
    "queen", "dewa", "raja", "indo", "nusantara", "abadi", "sejahtera",
    "makmur", "sentosa", "berkah", "bank", "cash", "gold", "diamond",
    "platinum", "happy", "lucky", "fortune", "dragon", "tiger", "lion",
    "eagle", "garuda", "merdeka", "union", "trust", "prime", "plus",
    "world", "inter", "multi", "sinar", "cahaya", "fajar", "bintang",
}

# --- Saringan byte cepat untuk aliran CT -------------------------------------
_TOKEN_SARING = set(KATA_KUAT) | set(MEREK)
_TOKEN_SARING |= {k for k in KATA_LEMAH if len(k) >= 3 and k.isalpha()}
POLA_SARING = re.compile(
    b"|".join(re.escape(t.encode("ascii", "ignore")) for t in sorted(_TOKEN_SARING))
)


def layak_parse(leaf_bytes_kecil):
    """True bila byte entri log (sudah dilowercase) memuat token sinyal."""
    return POLA_SARING.search(leaf_bytes_kecil) is not None


def _label_utama(domain):
    """Ambil label terdaftar (SLD) + gabungan label tanpa TLD."""
    d = domain.lower().strip().strip(".")
    if d.startswith("*."):
        d = d[2:]
    bagian = d.split(".")
    tanpa_tld = "".join(bagian[:-1]) if len(bagian) > 1 else d
    sld = bagian[-2] if len(bagian) > 1 else bagian[0]
    tld = bagian[-1] if len(bagian) > 1 else ""
    return sld, tanpa_tld, tld


def nilai_domain(domain):
    """Kembalikan (skor:int, alasan:list[str])."""
    sld, tanpa_tld, tld = _label_utama(domain)
    teks = tanpa_tld.replace("-", "")
    alasan = []
    skor = 0

    kena_kuat = []
    for kata, bobot in KATA_KUAT.items():
        if kata in teks:
            skor += bobot
            kena_kuat.append(kata)
    if kena_kuat:
        alasan.append("kata-kuat:" + ",".join(sorted(set(kena_kuat))))

    kena_merek = None
    for m in MEREK:
        if m in teks:
            kena_merek = m
            break
    if kena_merek:
        # Batang murni huruf yang pendek (<= 6) atau kata umum tidak boleh
        # menjadi pemicu tunggal; batang berangka adalah pola khas keluarga
        # domain operator dan mempertahankan bobot penuh.
        if kena_merek.isalpha() and (len(kena_merek) <= 6
                                     or kena_merek in STOP_GENERIK):
            skor += 2
            alasan.append("merek-umum:" + kena_merek)
        else:
            skor += 4
            alasan.append("merek:" + kena_merek)

    if kena_kuat or kena_merek:
        kena_lemah = [k for k in KATA_LEMAH if k in teks]
        if kena_lemah:
            skor += min(2, len(kena_lemah))
            alasan.append("kata-lemah:" + ",".join(sorted(set(kena_lemah))))

    if tld in TLD_MENCURIGAKAN:
        skor += 1
        alasan.append("tld:" + tld)

    digit = sum(c.isdigit() for c in sld)
    if len(sld) >= 6 and digit / max(1, len(sld)) >= 0.4:
        skor += 1
        alasan.append("pola-angka")

    return skor, alasan
