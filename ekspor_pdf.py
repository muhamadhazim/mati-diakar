#!/usr/bin/env python3
"""Ekspor PDF berkas bukti per jaringan — MATI DI AKAR (H4).

Satu PDF per jaringan (format laporan intelijen, sesuai KONSEP_FINAL.md §
"Ekspor satu berkas bukti per jaringan"): ringkasan jaringan, daftar domain
anggota beserta bukti penggabungan, simpul pembayaran bersama, dan catatan
metodologi/batasan. Isi diambil read-only dari data/matidiakar.db dengan
logika yang sama seperti dasbor (dasbor.py: ambil_jaringan).

Keluaran: ekspor/jaringan_<ID>.pdf + ekspor/DAFTAR_BERKAS.md.
PERINGATAN: PDF berisi nomor rekening/e-wallet asli dari halaman publik
situs (bukti untuk aduan ke Komdigi / permintaan blokir ke bank/OJK).
Folder ekspor/ masuk .gitignore dan TIDAK BOLEH masuk repo publik.

Pakai: .venv/bin/python ekspor_pdf.py [--jaringan J001] [--keluar DIR]
"""

import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone, timedelta

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

DASAR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DASAR, "data", "matidiakar.db")
WIB = timezone(timedelta(hours=7))

GELAP = colors.HexColor("#1a1a1a")
MERAH = colors.HexColor("#8f1d1d")
ABU = colors.HexColor("#555555")
GARIS = colors.HexColor("#999999")
LATAR = colors.HexColor("#f2f2f2")
LATAR_KUAT = colors.HexColor("#fdecec")

STL_JUDUL = ParagraphStyle("judul", fontName="Helvetica-Bold",
                           fontSize=16, leading=20, textColor=GELAP)
STL_SUB = ParagraphStyle("sub", fontName="Helvetica", fontSize=10,
                         leading=14, textColor=ABU)
STL_H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12,
                        leading=15, textColor=GELAP, spaceBefore=14,
                        spaceAfter=6)
STL_BADAN = ParagraphStyle("badan", fontName="Helvetica", fontSize=9.5,
                          leading=13.5, textColor=GELAP, spaceAfter=6)
STL_SEL = ParagraphStyle("sel", fontName="Helvetica", fontSize=8.5,
                         leading=11)
STL_SEL_MONO = ParagraphStyle("selmono", fontName="Courier", fontSize=8.5,
                              leading=11)
STL_SEL_JUDUL = ParagraphStyle("seljudul", fontName="Helvetica-Bold",
                               fontSize=8.5, leading=11, textColor=colors.white)
STL_PERINGATAN = ParagraphStyle("peringatan", fontName="Helvetica-Bold",
                                fontSize=9.5, leading=13, textColor=MERAH)


def db():
    uri = "file:" + DB_PATH + "?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=30)
    con.row_factory = sqlite3.Row
    return con


def kontak_teks(kontak_json):
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


# Nilai kontak generik dari mekanisme berbagi Telegram (t.me/share/url,
# t.me/addlist/...) — token mekanisme, BUKAN identitas kontak operator.
# Sama persis dengan KONTAK_GENERIK di dasbor.py (definisi diperketat atas
# keputusan pengguna, 2026-11-10).
KONTAK_GENERIK = {"share", "addlist"}


def bukti_kuat(bukti):
    """Bukti kuat (aturan ketat) = berbagi favicon / rekening, atau kontak
    operator nyata (bukan simhash saja, bukan kontak generik 'share' /
    'addlist')."""
    if not bukti:
        return False
    for seg in bukti.split(";"):
        seg = seg.strip()
        if seg.startswith(("favicon:", "uang:")):
            return True
        if seg.startswith("kontak:"):
            nilai = seg.split(":", 2)[-1].strip()
            if nilai.lower() not in KONTAK_GENERIK:
                return True
    return False


def potong(teks, maks=90):
    teks = "" if teks is None else str(teks)
    return teks if len(teks) <= maks else teks[:maks - 1] + "…"


def bangun_pdf(jid, anggota, uang, jalan_keluar, dibuat_wib):
    kuat = sum(1 for r in anggota if bukti_kuat(r["bukti"]))
    kontak_unik = set()
    for r in anggota:
        teks = kontak_teks(r["kontak_json"])
        if teks:
            kontak_unik.add(teks)
    nilai_uang = sorted({(u["jenis"], u["nilai"]) for u in uang if u["nilai"]})

    def kepala(kanvas, dokumen):
        kanvas.saveState()
        kanvas.setFont("Helvetica-Bold", 9)
        kanvas.setFillColor(GELAP)
        kanvas.drawString(15 * mm, 282 * mm, "MATI DI AKAR — Berkas Bukti Jaringan")
        kanvas.setFont("Helvetica", 9)
        kanvas.setFillColor(ABU)
        kanvas.drawRightString(195 * mm, 282 * mm, "Kartika Cyber Hackathon 2026")
        kanvas.setStrokeColor(GARIS)
        kanvas.line(15 * mm, 280 * mm, 195 * mm, 280 * mm)
        kanvas.setFont("Helvetica", 8)
        kanvas.drawString(15 * mm, 12 * mm,
                          "Indikasi intelijen untuk diverifikasi pihak berwenang, bukan vonis.")
        kanvas.drawRightString(195 * mm, 12 * mm, f"Halaman {dokumen.page}")
        kanvas.restoreState()

    dokumen = BaseDocTemplate(jalan_keluar, pagesize=A4,
                              leftMargin=15 * mm, rightMargin=15 * mm,
                              topMargin=22 * mm, bottomMargin=16 * mm,
                              title=f"MATI DI AKAR — Berkas Jaringan {jid}",
                              author="MATI DI AKAR")
    bingkai = Frame(dokumen.leftMargin, dokumen.bottomMargin,
                    dokumen.width, dokumen.height, id="isi")
    dokumen.addPageTemplates([PageTemplate(id="halaman", frames=[bingkai],
                                           onPage=kepala)])

    unsur = [
        Paragraph(f"Berkas Bukti Jaringan {jid}", STL_JUDUL),
        Paragraph("Sistem Intelijen Jaringan Judi Online — deteksi saat lahir, "
                  "pemetaan klaster cermin, penindakan simpul pembayaran.",
                  STL_SUB),
        Spacer(1, 4 * mm),
        Paragraph("STATUS: INDIKASI INTELIJEN — temuan di berkas ini berasal "
                  "dari data publik (log Certificate Transparency dan halaman "
                  "publik situs) dan wajib diverifikasi pihak berwenang "
                  "sebelum penindakan. Bukan vonis.", STL_PERINGATAN),
        Paragraph(f"Dibuat: {dibuat_wib.strftime('%d %B %Y, %H:%M WIB')} · "
                  f"Sumber data: log CT Google Argon 2026h2 + Cloudflare "
                  f"Nimbus 2026, sidik jari situs (modul SIDIK), ekstraksi "
                  f"pembayaran (modul UANG).", STL_BADAN),
        Paragraph("Ringkasan jaringan", STL_H2),
    ]

    ringkasan = Table([
        [Paragraph("Domain anggota", STL_SEL),
         Paragraph(str(len(anggota)), STL_SEL)],
        [Paragraph("Domain berbukti kuat (berbagi kontak operator / favicon / rekening)",
                   STL_SEL),
         Paragraph(str(kuat), STL_SEL)],
        [Paragraph("Domain berbukti lemah saja (kemiripan halaman/simhash)",
                   STL_SEL),
         Paragraph(str(len(anggota) - kuat), STL_SEL)],
        [Paragraph("Temuan pembayaran (simpul uang)", STL_SEL),
         Paragraph(str(len(uang)), STL_SEL)],
        [Paragraph("Simpul pembayaran berbeda (jenis + nilai)", STL_SEL),
         Paragraph(str(len(nilai_uang)), STL_SEL)],
        [Paragraph("Kontak publik berbeda", STL_SEL),
         Paragraph(str(len(kontak_unik)), STL_SEL)],
    ], colWidths=[120 * mm, 60 * mm])
    ringkasan.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LATAR),
        ("GRID", (0, 0), (-1, -1), 0.5, GARIS),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    unsur.append(ringkasan)
    unsur.append(Paragraph(
        "Simpul pembayaran yang perlu ditindak perbankan: satu rekening atau "
        "e-wallet yang dipakai bersama oleh banyak domain dalam jaringan ini "
        "adalah akar yang mematikan seluruh situs pemakainya bila diblokir. "
        "Domain adalah barang sekali pakai bagi operator; rekening tidak, "
        "karena butuh identitas dan verifikasi bank.", STL_BADAN))

    unsur.append(Paragraph("Domain anggota dan bukti penggabungan", STL_H2))
    baris = [[Paragraph("Domain", STL_SEL_JUDUL),
              Paragraph("Bukti penggabungan", STL_SEL_JUDUL),
              Paragraph("Judul halaman", STL_SEL_JUDUL),
              Paragraph("Kontak publik", STL_SEL_JUDUL)]]
    for r in anggota:
        baris.append([
            Paragraph(potong(r["domain"], 34), STL_SEL_MONO),
            Paragraph(potong(r["bukti"], 60), STL_SEL),
            Paragraph(potong(r["judul"], 40), STL_SEL),
            Paragraph(potong(kontak_teks(r["kontak_json"]), 50), STL_SEL),
        ])
    tabel = Table(baris, colWidths=[48 * mm, 52 * mm, 38 * mm, 42 * mm],
                  repeatRows=1)
    gaya = [("BACKGROUND", (0, 0), (-1, 0), GELAP),
            ("GRID", (0, 0), (-1, -1), 0.5, GARIS),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    for i, r in enumerate(anggota, start=1):
        if bukti_kuat(r["bukti"]):
            gaya.append(("BACKGROUND", (0, i), (-1, i), LATAR_KUAT))
    tabel.setStyle(TableStyle(gaya))
    unsur.append(tabel)
    unsur.append(Paragraph(
        "Baris berarsir merah muda = domain berbukti kuat (berbagi kontak "
        "operator, favicon identik, atau rekening). Baris tanpa arsir = hanya kemiripan "
        "halaman (simhash); itu bukti lemah karena banyak situs judol memakai "
        "template white-label yang sama dari penyedia yang sama.",
        STL_BADAN))

    unsur.append(Paragraph("Simpul pembayaran anggota", STL_H2))
    if uang:
        baris_uang = [[Paragraph("Domain", STL_SEL_JUDUL),
                       Paragraph("Jenis", STL_SEL_JUDUL),
                       Paragraph("Nilai", STL_SEL_JUDUL),
                       Paragraph("Konteks", STL_SEL_JUDUL)]]
        for u in uang:
            baris_uang.append([
                Paragraph(potong(u["domain"], 34), STL_SEL_MONO),
                Paragraph(potong(u["jenis"], 22), STL_SEL),
                Paragraph(potong(u["nilai"], 30), STL_SEL_MONO),
                Paragraph(potong(u["konteks"], 60), STL_SEL),
            ])
        tabel_uang = Table(baris_uang,
                           colWidths=[48 * mm, 30 * mm, 42 * mm, 60 * mm],
                           repeatRows=1)
        tabel_uang.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), GELAP),
            ("GRID", (0, 0), (-1, -1), 0.5, GARIS),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        unsur.append(tabel_uang)
    else:
        unsur.append(Paragraph("Belum ada temuan pembayaran pada jaringan ini.",
                               STL_BADAN))

    unsur.append(Paragraph("Metodologi dan batasan", STL_H2))
    unsur.append(Paragraph(
        "1) LAHIR: domain ditangkap dari log Certificate Transparency saat "
        "sertifikatnya terbit, dinilai dari leksikon judol Indonesia, "
        "kemiripan batang merek daftar blokir Komdigi (BrigsLabs/judol), dan "
        "pola nama domain. 2) SIDIK: sidik jari tiap situs (hash favicon, "
        "simhash isi halaman, kontak publik) lalu klaster union-find. "
        "3) UANG: pola angka di dekat nama bank/e-wallet pada halaman publik; "
        "penyaring tanggal (DDMMYYYY/YYYYMMDD) membuang temuan palsu berupa "
        "tanggal promo. Hanya observasi pasif data publik: tanpa transaksi, "
        "tanpa pendaftaran akun, tanpa interaksi dengan operator. Sebagian "
        "situs menyembunyikan info deposit di balik login dan tidak terjangkau "
        "metode ini, jadi cakupan bukan 100%.", STL_BADAN))
    dokumen.build(unsur)
    return {"jaringan_id": jid, "domain": len(anggota), "kuat": kuat,
            "uang": len(uang), "berkas": jalan_keluar}


def utama():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jaringan", help="hanya ekspor satu jaringan")
    parser.add_argument("--keluar", default=os.path.join(DASAR, "ekspor"),
                        help="folder keluaran")
    args = parser.parse_args()
    os.makedirs(args.keluar, exist_ok=True)
    dibuat = datetime.now(WIB)

    con = db()
    try:
        if args.jaringan:
            ids = [args.jaringan]
        else:
            ids = [r[0] for r in con.execute(
                "SELECT DISTINCT jaringan_id FROM jaringan ORDER BY 1")]
        hasil = []
        for jid in ids:
            anggota = con.execute(
                "SELECT j.domain, j.bukti, s.judul, s.favicon_hash, "
                "s.kontak_json FROM jaringan j "
                "LEFT JOIN sidik s ON s.domain = j.domain "
                "WHERE j.jaringan_id = ? ORDER BY j.domain",
                (jid,)).fetchall()
            if not anggota:
                print(f"{jid}: tidak ada anggota, dilewati")
                continue
            uang = con.execute(
                "SELECT u.domain, u.jenis, u.nilai, u.konteks FROM uang u "
                "JOIN jaringan j ON j.domain = u.domain "
                "WHERE j.jaringan_id = ? ORDER BY u.domain, u.jenis",
                (jid,)).fetchall()
            jalan = os.path.join(args.keluar, f"jaringan_{jid}.pdf")
            hasil.append(bangun_pdf(jid, anggota, uang, jalan, dibuat))
            print(f"{jid}: {len(anggota)} domain, "
                  f"{hasil[-1]['kuat']} kuat, {len(uang)} temuan uang -> {jalan}")
    finally:
        con.close()

    if not args.jaringan:
        daftar = os.path.join(args.keluar, "DAFTAR_BERKAS.md")
        baris = ["# Daftar berkas bukti MATI DI AKAR",
                 "",
                 f"Dibuat: {dibuat.strftime('%d %B %Y, %H:%M WIB')}. "
                 "Satu PDF per jaringan. Status: indikasi intelijen untuk "
                 "diverifikasi pihak berwenang, bukan vonis.",
                 "",
                 "| Berkas | Domain | Berbukti kuat | Temuan uang |",
                 "| --- | ---: | ---: | ---: |"]
        for h in hasil:
            baris.append(f"| jaringan_{h['jaringan_id']}.pdf | {h['domain']} | "
                         f"{h['kuat']} | {h['uang']} |")
        baris += ["",
                  f"Total: {len(hasil)} jaringan, "
                  f"{sum(h['domain'] for h in hasil)} domain, "
                  f"{sum(h['uang'] for h in hasil)} temuan uang.",
                  "",
                  "PERINGATAN: berkas-berkas ini berisi nomor rekening / "
                  "e-wallet asli dari halaman publik situs dan TIDAK BOLEH "
                  "masuk repo publik atau dibagikan tanpa penyamaran."]
        with open(daftar, "w", encoding="utf-8") as f:
            f.write("\n".join(baris) + "\n")
        print(f"Indeks: {daftar}")
        print(f"SELESAI: {len(hasil)} berkas PDF, "
              f"{sum(h['domain'] for h in hasil)} domain, "
              f"{sum(h['uang'] for h in hasil)} temuan uang.")


if __name__ == "__main__":
    utama()
