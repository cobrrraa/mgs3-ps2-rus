"""Rebuild CODEC.DAT with Russian strings and remap the codec call IDs.

A codec call is addressed by a 32-bit ID written in the stage scripts' bytecode (tag byte 0x0A,
then the u32, little-endian), found by tracing the codec module (0x387EC8 in the call savestate):
    low 24 bits  = script offset in CODEC.DAT / 16 (sector = low >> 7, script at (low << 4) & 0x7FF)
    high 8 bits  = read size: (hi + 1) * 0x2000 bytes from the start of that sector
The game reads that many bytes, so a read may also cover the scripts that follow (a few IDs read
up to 109 * 8 KB at once). Rebuilt scripts grow, so every ID gets the new offset and a size that
covers the same scripts as before, keeping the spare 8 KB units the original had.

Scripts 0-15 (debug/test data, offsets below FIRST_CALL) are left untouched and never move.

    build(codec_bytes, ru) -> (new_bytes, layout)   layout = [(old_start, old_end, new_start, new_end)]
    remap(v, layout) -> new ID or None if v is not a call ID
    patch_ids(gcx_bytes, layout) -> (bytes, count)
Usage: codec_build.py CODEC.DAT RU.json [MORE.json ...] OUT.DAT LAYOUT.json
"""
import bisect
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gcx as G  # noqa: E402
from codec_dat import blocks  # noqa: E402
from gcx_build import build as build_gcx  # noqa: E402
from encoding_ru import encode  # noqa: E402

FIRST_SCRIPT = 16          # scripts before this one are test data and stay as they are
UNIT = 0x2000
ID_TAG = 0x0A
ID_PREFIX = set(range(0x36, 0x3B)) | {0x6E, 0x7A}   # byte before the tag in every real reference


def usable(ru):
    """Drop translations the PS2 font cannot show yet (they stay English)."""
    out, dropped = {}, 0
    for en, text in ru.items():
        try:
            encode(text, bar_newline=False)
            out[en] = text
        except ValueError:
            dropped += 1
    return out, dropped


def build(data, ru):
    out = bytearray()
    layout = []
    for k, (a, b) in enumerate(blocks(data)):
        if k < FIRST_SCRIPT:
            assert len(out) == a
            new = data[a:b]
        else:
            d = bytearray(G.xor_area(data[a:b]))
            struct.pack_into("<I", d, G.sec2_offset(d) + 16, 0)  # decrypted: seed 0
            new, _ = build_gcx(bytes(d), ru)
            new += b"\x00" * (-len(new) % 16)
        layout.append((a, b, len(out), len(out) + len(new)))
        out += new
    return bytes(out), layout


class Remap:
    def __init__(self, layout):
        self.layout = layout
        self.old_start = [x[0] for x in layout]
        self.by_low = {x[0] >> 4: i for i, x in enumerate(layout) if i >= FIRST_SCRIPT}

    def __call__(self, v):
        low, hi = v & 0xFFFFFF, v >> 24
        i = self.by_low.get(low)
        if i is None:
            return None
        a, b, na, nb = self.layout[i]
        sector = a & ~0x7FF
        covered = sector + (hi + 1) * UNIT
        if covered < b:
            return None  # the read would not even cover its own script: not a call ID
        # last script that the original read covered completely
        j = bisect.bisect_right(self.old_start, covered) - 1
        while self.layout[j][1] > covered:
            j -= 1
        spare = hi - (self.layout[j][1] - sector - 1) // UNIT
        need = self.layout[j][3] - (na & ~0x7FF)
        new_hi = (need - 1) // UNIT + spare
        assert na % 16 == 0 and na >> 4 < 1 << 24 and new_hi < 256
        return (new_hi << 24) | (na >> 4)


def find_ids(gcx, remap):
    """Positions of call IDs in the bytecode (after the string area) of a GCX: [(pos, old, new)]."""
    out = []
    s2, _, code, _ = G.string_area(gcx)
    i = gcx.find(bytes([ID_TAG]), code)
    while i != -1 and i + 5 <= len(gcx):
        if gcx[i - 1] in ID_PREFIX:
            v = struct.unpack_from("<I", gcx, i + 1)[0]
            new = remap(v)
            if new is not None:
                out.append((i + 1, v, new))
        i = gcx.find(bytes([ID_TAG]), i + 1)
    return out


def patch_ids(gcx, remap):
    d = bytearray(gcx)
    ids = find_ids(gcx, remap)
    for pos, _, new in ids:
        struct.pack_into("<I", d, pos, new)
    return bytes(d), len(ids)


def main():
    src, *rest = sys.argv[1:]
    *ru_paths, out_dat, out_layout = rest
    ru = {}
    for p in ru_paths:
        ru.update(json.load(open(p, encoding="utf-8")))
    ru, dropped = usable(ru)
    data = open(src, "rb").read()
    new, layout = build(data, ru)
    # IDs inside the codec scripts themselves
    remap = Remap(layout)
    inner = 0
    out = bytearray(new)
    for i, (a, b, na, nb) in enumerate(layout):
        if i >= FIRST_SCRIPT:
            out[na:nb], n = patch_ids(bytes(out[na:nb]), remap)
            inner += n
    open(out_dat, "wb").write(out)
    with open(out_layout, "w") as f:
        json.dump(layout, f)
    print(f"{len(layout)} scripts, {len(data)} -> {len(out)} bytes (+{len(out) - len(data)}), "
          f"{dropped} translations dropped (characters outside the font), {inner} IDs inside codec")


if __name__ == "__main__":
    main()
