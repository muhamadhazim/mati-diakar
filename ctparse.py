# -*- coding: utf-8 -*-
"""
Parser minimal DER untuk mengekstrak nama domain (SAN dNSName + CN subjek)
dari sertifikat X.509 dan TBSCertificate pra-sertifikat pada entri log CT.

Hanya memakai pustaka standar. Semua fungsi aman terhadap data rusak:
kesalahan parse menghasilkan daftar kosong, tidak pernah melempar keluar.
"""
import base64

OID_SAN = b"\x55\x1d\x11"  # 2.5.29.17 subjectAltName
OID_CN = b"\x55\x04\x03"   # 2.5.4.3 commonName


def _tlv(buf, off):
    """Baca satu TLV. Kembalikan (tag, awal_isi, panjang_isi, akhir_tlv)."""
    if off + 2 > len(buf):
        raise ValueError("eof")
    tag = buf[off]
    p = off + 1
    lb = buf[p]
    p += 1
    if lb & 0x80:
        n = lb & 0x7F
        if n == 0 or n > 4 or p + n > len(buf):
            raise ValueError("panjang tidak valid")
        ln = int.from_bytes(buf[p:p + n], "big")
        p += n
    else:
        ln = lb
    if p + ln > len(buf):
        raise ValueError("overflow")
    return tag, p, ln, p + ln


def _walk(buf, start, end):
    """Iterasi TLV anak pada rentang [start, end). Hasil: (tag, awal_tlv, awal_isi, panjang_isi)."""
    off = start
    while off < end:
        tag, cs, ln, nxt = _tlv(buf, off)
        yield tag, off, cs, ln
        off = nxt


def _domains_from_san(val):
    """val = isi OCTET STRING ekstensi SAN (DER SEQUENCE of GeneralName)."""
    out = []
    try:
        tag, cs, ln, _ = _tlv(val, 0)
        if tag != 0x30:
            return out
        for t, _awal, s, l in _walk(val, cs, cs + ln):
            if t == 0x82:  # dNSName IA5String
                try:
                    out.append(val[s:s + l].decode("ascii").lower())
                except UnicodeDecodeError:
                    pass
    except ValueError:
        pass
    return out


def _cn_from_name(buf, start, ln):
    """Cari CN pada Name (SEQUENCE of SET of SEQUENCE{OID, nilai})."""
    try:
        for _t, _a, s, l in _walk(buf, start, start + ln):  # SET
            for _t2, _a2, s2, l2 in _walk(buf, s, s + l):   # SEQUENCE AV
                parts = list(_walk(buf, s2, s2 + l2))
                if len(parts) == 2:
                    _ot, _oa, os_, ol = parts[0]
                    _vt, _va, vs, vl = parts[1]
                    if buf[os_:os_ + ol] == OID_CN:
                        return buf[vs:vs + vl].decode("utf-8", "ignore").lower()
    except ValueError:
        pass
    return None


def domains_from_tbs(tbs):
    """Ekstrak domain dari TBSCertificate (DER, termasuk tag SEQUENCE-nya)."""
    domains = []
    try:
        tag, cs, ln, _ = _tlv(tbs, 0)
        if tag != 0x30:
            return domains
        nama_ke = 0
        for t, awal, s, l in _walk(tbs, cs, cs + ln):
            if t == 0x30:
                # Name dikenali dari anak pertamanya SET (0x31).
                try:
                    anak, _aa, _as, _al = next(_walk(tbs, s, s + l))
                except StopIteration:
                    continue
                if anak == 0x31:
                    nama_ke += 1
                    if nama_ke == 2:  # subjek (setelah penerbit)
                        cn = _cn_from_name(tbs, s, l)
                        if cn and "*" not in cn:
                            domains.append(cn)
            elif t == 0xA3:  # extensions [3]
                t2, _a2, s2, l2 = _tlv(tbs, s)
                if t2 != 0x30:
                    continue
                for et, _ea, es, el in _walk(tbs, s2, s2 + l2):
                    if et != 0x30:
                        continue
                    parts = list(_walk(tbs, es, es + el))
                    if len(parts) < 2:
                        continue
                    _ot, _oa, os_, ol = parts[0]
                    if tbs[os_:os_ + ol] != OID_SAN:
                        continue
                    vt, _va, vs, vl = parts[-1]
                    if vt == 0x04:  # OCTET STRING
                        domains.extend(_domains_from_san(tbs[vs:vs + vl]))
    except ValueError:
        pass
    return domains


def domains_from_cert(cert_der):
    """Ekstrak domain dari sertifikat penuh (DER)."""
    try:
        tag, cs, ln, _ = _tlv(cert_der, 0)
        if tag != 0x30:
            return []
        # Anak pertama sertifikat adalah TBSCertificate.
        _t, tlv_start, s, l = next(_walk(cert_der, cs, cs + ln))
        return domains_from_tbs(cert_der[tlv_start:s + l])
    except (ValueError, StopIteration):
        return []


def parse_leaf_bytes(leaf):
    """Parse byte leaf_input (sudah di-decode base64) -> daftar domain."""
    try:
        if len(leaf) < 12:
            return []
        entry_type = int.from_bytes(leaf[10:12], "big")
        if entry_type == 0:  # x509_entry
            ln = int.from_bytes(leaf[12:15], "big")
            return domains_from_cert(leaf[15:15 + ln])
        if entry_type == 1:  # precert_entry
            ln = int.from_bytes(leaf[44:47], "big")
            return domains_from_tbs(leaf[47:47 + ln])
    except Exception:
        pass
    return []


def parse_leaf_input(leaf_b64):
    """Parse field leaf_input satu entri get-entries -> daftar domain."""
    try:
        leaf = base64.b64decode(leaf_b64)
    except Exception:
        return []
    return parse_leaf_bytes(leaf)
