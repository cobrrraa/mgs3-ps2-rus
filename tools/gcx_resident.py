"""Report the resident script strings (r_sna*): byte budget and line widths of the item windows.

The resident GCX is loaded only up to its original size, so its Russian strings must fit into the
original string chains (nothing may be appended). Weapon/item windows (R2/L2) show 5 lines and
wrap at the window width, so every line must stay within LIMIT pixels.

Usage: gcx_resident.py FONT.raw PS2_GCX RU.json [OUT.txt]
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gcx as G  # noqa: E402
import font_ps2 as F  # noqa: E402
from encoding_ru import encode  # noqa: E402
from gcx_build import chains  # noqa: E402

LIMIT = 0  # filled from the English text: widest English line of a window string


class Widths:
    def __init__(self, font):
        self.data, _, self.entries = F.load(font)
        self.space = F.width_of(struct.unpack_from("<I", self.data, 8)[0] >> 16)

    def line(self, b):
        w, i = 0, 0
        while i < len(b):
            c = b[i]
            if 0x80 <= c < 0x90:
                w, i = w + 24, i + 2
                continue
            w += self.space if c == 0x20 else F.width_of(self.entries[c - F.FIRST][1]) if c >= F.FIRST else 0
            i += 1
        return w

    def lines(self, b):
        return [self.line(x) for x in b.split(b"\n") if x]


def strings(gcx):
    s2 = G.sec2_offset(gcx)
    _, tab, so, _, _ = struct.unpack_from("<5I", gcx, s2)
    area = s2 + so
    refs = set()
    for k in range((so - tab) // 4):
        v = struct.unpack_from("<I", gcx, s2 + tab + 4 * k)[0]
        if v & 0x80000000:
            refs.add(v & 0x7FFFFFFF)
    return area, chains(gcx, area, refs)


def main():
    font, path, ru_path = sys.argv[1:4]
    out = open(sys.argv[4], "w", encoding="utf-8") if len(sys.argv) > 4 else sys.stdout
    ru = json.load(open(ru_path, encoding="utf-8"))
    W = Widths(font)
    d = open(path, "rb").read()
    area, chs = strings(d)
    tot_en = tot_ru = 0
    for ch in chs:
        tot_en += ch[-1][1] + 1 - ch[0][0]
        for off, end in ch:
            raw = d[area + off:area + end]
            en = raw.decode("latin-1")
            new = encode(ru[en], bar_newline=False) if en in ru else raw
            tot_ru += len(new) + 1
            print(f"@{off:#06x} EN {len(raw)}B {W.lines(raw)}", file=out)
            print(f"    {en!r}", file=out)
            if en in ru:
                print(f"    RU {len(new)}B {W.lines(new)}", file=out)
                print(f"    {ru[en]!r}", file=out)
    print(f"TOTAL en {tot_en} B, ru {tot_ru} B, over {tot_ru - tot_en} B", file=out)


if __name__ == "__main__":
    main()
