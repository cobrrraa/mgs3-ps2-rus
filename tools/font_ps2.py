"""MGS3 PS2 subtitle/UI font (init stage, resident 383c45.raw).

Layout (little endian):
    u16 base        offset of glyph data (= end of the glyph table)
    u16 ?           (0x0800)
    u32 data_size
    u32 ?
    entries[(base - 12) / 4]: u16 offset (from base), u16 info
        info bits 4..9 -> width - 1 (pixels); 0x400 / 0x800 are flags (0x800 = descender)
    glyph data: height 24, 2 bits per pixel, MSB first, rows packed bit-continuously.
Character code c (0x21..) uses entry c - 0x21; 0x20 (space) is the glyph at offset 0.

Usage:
    font_ps2.py sheet FONT.raw OUT.png       -> render every glyph with its code
"""
import struct
import sys

from PIL import Image, ImageDraw

HEIGHT = 24
FIRST = 0x21


WIDTH_MASK = 0x3F0   # bits 4..9 = width - 1 (the game reads (entry >> 20) & 0x3F); bits 10+ are flags


def width_of(info):
    return ((info & WIDTH_MASK) >> 4) + 1


def load(path):
    data = open(path, "rb").read()
    base, flags, size, unk = struct.unpack_from("<HHII", data)
    n = (base - 12) // 4
    entries = [struct.unpack_from("<HH", data, 12 + 4 * i) for i in range(n)]
    return data, base, entries


def glyph_pixels(data, base, off, width):
    bits = width * 2
    pix = []
    start = (base + off) * 8
    for y in range(HEIGHT):
        row = []
        for x in range(width):
            p = start + (y * bits) + x * 2
            byte = data[p // 8]
            row.append((byte >> (6 - p % 8)) & 3)
        pix.append(row)
    return pix


def sheet(path, out):
    data, base, entries = load(path)
    cell_w, cell_h, cols = 40, 44, 16
    rows = (len(entries) + 1 + cols - 1) // cols
    img = Image.new("RGB", (cols * cell_w, rows * cell_h), (24, 24, 32))
    d = ImageDraw.Draw(img)
    shades = [(24, 24, 32), (110, 110, 120), (180, 180, 190), (255, 255, 255)]
    glyphs = [(0x20, 0, entries[0][1])] + [(FIRST + i, off, info) for i, (off, info) in enumerate(entries)]
    for k, (code, off, info) in enumerate(glyphs):
        w = width_of(info)
        cx, cy = (k % cols) * cell_w, (k // cols) * cell_h
        d.text((cx + 2, cy + 1), f"{code:02X}", fill=(90, 200, 255))
        if base + off + (w * 2 * HEIGHT + 7) // 8 > len(data) or w > 36:
            continue
        for y, row in enumerate(glyph_pixels(data, base, off, w)):
            for x, v in enumerate(row):
                if v:
                    img.putpixel((cx + 2 + x, cy + 14 + y), shades[v])
    img = img.resize((img.width * 2, img.height * 2), Image.NEAREST)
    img.save(out)
    print(f"{len(glyphs)} glyphs -> {out}")


def extra_sheet(path, out, start=19528, gw=24, gh=24):
    """Render the fixed-size glyph block after the main font (kana, button icons) with indices."""
    data = open(path, "rb").read()
    size = gw * gh * 2 // 8
    n = (len(data) - start) // size
    cell_w, cell_h, cols = 40, 44, 16
    rows = (n + cols - 1) // cols
    img = Image.new("RGB", (cols * cell_w, rows * cell_h), (24, 24, 32))
    d = ImageDraw.Draw(img)
    for k in range(n):
        cx, cy = (k % cols) * cell_w, (k // cols) * cell_h
        d.text((cx + 2, cy + 1), str(k), fill=(90, 200, 255))
        base = start + k * size
        for y in range(gh):
            for x in range(gw):
                p = (y * gw + x) * 2
                v = (data[base + p // 8] >> (6 - p % 8)) & 3
                if v:
                    img.putpixel((cx + 2 + x, cy + 14 + y), (v * 85,) * 3)
    img = img.resize((img.width * 2, img.height * 2), Image.NEAREST)
    img.save(out)
    print(f"{n} glyphs ({(len(data) - start) % size} spare bytes) -> {out}")


if __name__ == "__main__":
    if sys.argv[1] == "sheet":
        sheet(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "extra":
        extra_sheet(sys.argv[2], sys.argv[3])
