"""Russian text encoding for the PS2 font: Windows-1251 letters with a few moved/reserved codes.

    0x00-0x7F  ASCII as in the original font
    0x80-0x8F  reserved: two-byte codes (80 7C newline, 81-83 xx kana / button icons, 84-8F xx glyph
               pages) - keep them in text as raw bytes written {83}{02}
    0xC0-0xFF  А-Я а-я (cp1251)
    0xA8/0xB8  Ё / ё
    0x96 –   0x97 —   0xAB «   0xBB »   0xB9 №   0x9F …  (… is 0x85 in cp1251, moved out of 0x80-0x8F)
    0x90-0x95, 0x98, 0x9A  М Н О П м н о п, moved from 0xCC-0xCF / 0xEC-0xEF (see MOVED)
Other codes 0x90-0xBF are blank in the font except a few symbols kept at their cp1251 places.

PC russifier text decoded from cp1251/UTF-8 goes through encode(), so the moves are transparent.
"""
import re

NEWLINE = b"\x80|"
ELLIPSIS = 0x9F

# When the resident script (r_sna) is loaded, the game walks its strings the old way (every byte
# >= 0x80 starts a two-byte code) and moves glyph-page codes: a first byte with (b & 0x9F) in
# 0x8C-0x8F gets 4 subtracted (8C 01 -> 88 01). The cp1251 letters at 0xCC-0xCF and 0xEC-0xEF match
# that test (о -> к, н -> й in weapon/item descriptions), so they live at codes the test skips.
MOVED = {"М": 0x90, "Н": 0x91, "О": 0x92, "П": 0x93, "м": 0x94, "н": 0x95, "о": 0x98, "п": 0x9A}

# code -> character drawn in the PS2 font
REDRAW = {code: bytes([code]).decode("cp1251") for code in
          list(range(0xC0, 0x100)) + [0xA8, 0xB8, 0x96, 0x97, 0xAB, 0xBB, 0xB9]}
for _ch, _code in MOVED.items():
    del REDRAW[_ch.encode("cp1251")[0]]
    REDRAW[_code] = _ch
REDRAW[ELLIPSIS] = "…"
CHAR_TO_CODE = {ch: code for code, ch in REDRAW.items()}
# Cyrillic letters that hang below the baseline (font flag 0x800, like g j p q y)
DESCENDERS = set("ДЦЩдцщруф")
RAW = re.compile(r"\{([0-9A-Fa-f]{2})\}")


def encode(text, bar_newline=True):
    """Text ('|' = subtitle line break, '{xx}' = raw byte) -> PS2 bytes.
    bar_newline=False keeps '|' as a plain character (GCX strings break lines with '\\n').
    Raises on characters the font cannot show."""
    out = bytearray()
    for line_no, line in enumerate(text.split("|") if bar_newline else [text]):
        if line_no:
            out += NEWLINE
        pos = 0
        for m in list(RAW.finditer(line)) + [None]:
            chunk = line[pos:m.start() if m else len(line)]
            for ch in chunk:
                if ch < "\x80":
                    out += ch.encode("ascii")
                elif ch in CHAR_TO_CODE:
                    out.append(CHAR_TO_CODE[ch])
                else:
                    raise ValueError(f"character {ch!r} (U+{ord(ch):04X}) is not in the PS2 Russian font")
            if m:
                out.append(int(m.group(1), 16))
                pos = m.end()
    return bytes(out)


def decode(raw):
    """PS2 bytes -> text; two-byte codes and unknown bytes come back as {xx}."""
    out = []
    i = 0
    while i < len(raw):
        b = raw[i]
        if raw[i:i + 2] == NEWLINE:
            out.append("|")
            i += 2
            continue
        if 0x80 <= b < 0x90 and i + 1 < len(raw):
            out.append(f"{{{b:02X}}}{{{raw[i + 1]:02X}}}")
            i += 2
            continue
        if b < 0x80 and (b >= 0x20 or b == 0x0A):
            out.append(chr(b))
        elif b in REDRAW:
            out.append(REDRAW[b])
        else:
            out.append(f"{{{b:02X}}}")
        i += 1
    return "".join(out)


if __name__ == "__main__":
    sample = "Это Оцелот, их командир!|Ёлки — «№1»… Нажмите {83}{02}."
    enc = encode(sample)
    print(enc.hex(" "))
    assert decode(enc) == sample, decode(enc)
    print("ok")
