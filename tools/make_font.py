"""Build the Russian PS2 font: cp1251 Cyrillic + punctuation drawn into the main font
(383c45.raw), keeping the file size and the kana block offset unchanged.

Usage: make_font.py ORIG_FONT.raw OUT_FONT.raw PREVIEW.png [TTF]

Glyph sources:
  - Cyrillic letters that look like Latin ones are copied from the font itself;
  - Ё/ё, … – — « » are copied from existing Mac Roman glyphs;
  - everything else is rendered from a TTF (Arial by default) to the font's metrics:
    caps rows 3..20, x-height rows 8..20, descenders down to row 23, 1-bit (values 0/3).
"""
import os
import struct
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import font_ps2 as F  # noqa: E402
from encoding_ru import REDRAW, DESCENDERS, encode  # noqa: E402

H = F.HEIGHT
BASELINE = 21          # first row below the baseline (row 20 is the last ink row of 'H')
CAP_TOP = 3
SCALE = 4
FLAG_DESC = 0x800

# Cyrillic char -> source char in the original (Mac Roman) font
COPY = {
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P", "С": "C",
    "Т": "T", "Х": "X", "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x",
    "Ё": "\u00cb", "ё": "\u00eb", "…": "\u2026", "–": "\u2013", "—": "\u2014",
    "«": "\u00ab", "»": "\u00bb",
}


# 0x80-0xBF follow cp1251 too: keep these symbols at their cp1251 codes (copied from Mac Roman:
# TM, nbsp, section, copyright, registered, degree, plus-minus, middle dot), blank every other
# code of 0x80-0xFF that is not redrawn (the old places of the MOVED letters included) to make
# room for the wider Cyrillic glyphs.
KEEP = {0x99: 0xAA, 0xA0: 0xCA, 0xA7: 0xA4, 0xA9: 0xA9, 0xAE: 0xA8, 0xB0: 0xA1, 0xB1: 0xB1, 0xB7: 0xE1}


class Glyph:
    def __init__(self, rows, flags):
        self.rows, self.flags = rows, flags

    @property
    def width(self):
        return len(self.rows[0])


def load_glyphs(path):
    data, base, entries = F.load(path)
    # entry for 0x20 lives in the header slot at +8 (info in the high half)
    space_info = struct.unpack_from("<I", data, 8)[0] >> 16
    glyphs = {0x20: Glyph(F.glyph_pixels(data, base, 0, F.width_of(space_info)), space_info & ~F.WIDTH_MASK)}
    for i, (off, info) in enumerate(entries):
        glyphs[F.FIRST + i] = Glyph(F.glyph_pixels(data, base, off, F.width_of(info)), info & ~F.WIDTH_MASK)
    return data, base, glyphs


def fit_font(ttf):
    """TTF size (in SCALE-d pixels) whose 'H' is exactly as tall as the PS2 font caps."""
    cap = (BASELINE - CAP_TOP) * SCALE
    for s in range(8 * SCALE, 80 * SCALE):
        fnt = ImageFont.truetype(ttf, s)
        if -fnt.getbbox("H", anchor="ls")[1] >= cap:
            return fnt, s
    raise SystemExit("no TTF size matches the cap height")


def render(ch, font):
    """Render one character to the font metrics; returns a Glyph."""
    big = Image.new("L", (64 * SCALE, H * SCALE), 0)
    d = ImageDraw.Draw(big)
    d.text((8 * SCALE, BASELINE * SCALE), ch, font=font, fill=255, anchor="ls")
    small = big.resize((64, H), Image.BOX)
    px = small.load()
    rows = [[3 if px[x, y] >= 120 else 0 for x in range(64)] for y in range(H)]
    cols = [x for x in range(64) if any(rows[y][x] for y in range(H))]
    left, right = cols[0], cols[-1]
    lb, rb = (2, 2) if ch.isupper() else (1, 2)
    width = lb + (right - left + 1) + rb
    out = [[0] * width for _ in range(H)]
    for y in range(H):
        for x in range(left, right + 1):
            out[y][lb + x - left] = rows[y][x]
    return Glyph(out, FLAG_DESC if ch in DESCENDERS else 0)


def pack(glyphs, orig, base):
    """Rebuild the table + glyph data with the same base and data_end as the original file."""
    data_end = struct.unpack_from("<I", orig, 4)[0]
    out = bytearray(orig)
    blob = bytearray()
    offsets = {}
    for code in range(0x20, 0x100):
        offsets[code] = len(blob)
        bits = []
        for row in glyphs[code].rows:
            for v in row:
                bits += [(v >> 1) & 1, v & 1]
        bits += [0] * (-len(bits) % 8)
        blob += bytes(int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8))
    room = data_end - base
    if len(blob) > room:
        raise SystemExit(f"glyph data {len(blob)} B does not fit into {room} B")
    out[base:data_end] = blob + b"\x00" * (room - len(blob))
    for code in range(0x20, 0x100):
        g = glyphs[code]
        info = ((g.width - 1) << 4) | g.flags
        slot = 8 if code == 0x20 else 12 + 4 * (code - F.FIRST)
        struct.pack_into("<HH", out, slot, offsets[code], info)
    return bytes(out), len(blob), room


def preview(font_path, out_png, lines):
    glyphs = load_glyphs(font_path)[2]
    width = max(sum(glyphs[b].width for b in line) for line in lines) + 8
    img = Image.new("RGB", (width, len(lines) * (H + 4) + 4), (16, 16, 20))
    for n, line in enumerate(lines):
        x = 4
        for b in line:
            g = glyphs[b]
            for y, row in enumerate(g.rows):
                for gx, v in enumerate(row):
                    if v:
                        img.putpixel((x + gx, 4 + n * (H + 4) + y), (235, 235, 235))
            x += g.width
    img = img.resize((img.width * 3, img.height * 3), Image.NEAREST)
    img.save(out_png)


def main():
    src, dst, png = sys.argv[1:4]
    ttf = sys.argv[4] if len(sys.argv) > 4 else r"C:\Windows\Fonts\arial.ttf"
    orig = open(src, "rb").read()
    _, base, glyphs = load_glyphs(src)
    font, size = fit_font(ttf)

    source = dict(glyphs)
    blank = Glyph([[0] for _ in range(H)], 0)
    for code in range(0x80, 0x100):
        glyphs[code] = source[KEEP[code]] if code in KEEP else blank

    copied = rendered = 0
    for code, ch in sorted(REDRAW.items()):
        if ch in COPY:
            glyphs[code] = source[COPY[ch].encode("mac_roman")[0]]
            copied += 1
        else:
            glyphs[code] = render(ch, font)
            rendered += 1

    new, used, room = pack(glyphs, orig, base)
    assert len(new) == len(orig)
    open(dst, "wb").write(new)
    print(f"{copied} copied, {rendered} rendered (TTF {size / SCALE:.2f}px); "
          f"glyph data {used} / {room} B -> {dst}")

    sample = ["СЪЕШЬ ЖЕ ЕЩЁ ЭТИХ МЯГКИХ ФРАНЦУЗСКИХ БУЛОК, ДА ВЫПЕЙ ЧАЮ",
              "съешь же ещё этих мягких французских булок, да выпей чаю",
              "Это Оцелот, их командир! — «№1»… Hello, Snake.",
              "Не скажу, что приятно убивать товарища, даже ради ГРУ."]
    preview(dst, png, [encode(s) for s in sample])
    print("preview ->", png)


if __name__ == "__main__":
    main()
