"""Shared parser for MGS3 subtitle records (PC .sdt and PS2 DEMO.DAT / VOX.DAT).

Record layout (little endian):
    u32 start, u32 end, u32 zero, u16 rec_len, u16 lang, char text[] '\\0'
rec_len covers the whole record (16-byte header + text + NUL). PS2 pads it to 4 bytes.
"""
import re
import struct

HEADER = 16
LANGS = (1, 2, 3, 4, 5)

_CAND = re.compile(rb"(?s)(?=(.{4}.{4})\x00\x00\x00\x00(.{2})([\x01-\x05])\x00)")


def parse(buf, langs=LANGS, padded=None):
    """Yield (offset, start, end, rec_len, lang, raw_text) for every valid record in buf.

    padded: True = PS2 (rec_len multiple of 4), False = PC (exact), None = accept both.
    """
    for m in _CAND.finditer(buf):
        off = m.start()
        lang = m.group(3)[0]
        if lang not in langs:
            continue
        start, end = struct.unpack("<II", m.group(1))
        rec_len = struct.unpack("<H", m.group(2))[0]
        if not (start < end < 0x01000000) or not (HEADER + 2 <= rec_len <= 0x800):
            continue
        tstart = off + HEADER
        nul = buf.find(b"\x00", tstart, off + rec_len + 1)
        if nul == -1 or nul == tstart:
            continue
        text = buf[tstart:nul]
        if text[0] < 0x20:
            continue
        exact = HEADER + len(text) + 1
        if padded is True and rec_len != (exact + 3) & ~3:
            continue
        if padded is False and rec_len != exact:
            continue
        if padded is None and rec_len not in (exact, (exact + 3) & ~3):
            continue
        yield off, start, end, rec_len, lang, text


def ps2_decode(raw):
    """PS2 single-byte text -> readable str. Newline \\x80| -> '|', other high bytes -> {xx}."""
    out = []
    i = 0
    while i < len(raw):
        b = raw[i]
        if b == 0x80 and i + 1 < len(raw) and raw[i + 1] == 0x7C:
            out.append("|")
            i += 2
            continue
        out.append(chr(b) if 0x20 <= b < 0x7F else f"{{{b:02x}}}")
        i += 1
    return "".join(out)


_NORM = re.compile(r"[^0-9a-z]+")
_PC_FIX = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"',
                         "…": "...", "—": "-", "–": "-"})


def norm(text):
    """Comparison key for English lines: lowercase letters/digits only."""
    return _NORM.sub("", text.translate(_PC_FIX).lower())
