"""Estimate how much each PS2 GCX would grow with Russian strings, and describe what follows the
string area (to know whether the area can be extended).
Usage: gcx_growth.py PS2_GCX_DIR RU.json
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gcx as G  # noqa: E402
from encoding_ru import encode  # noqa: E402


def main():
    gdir, ru_path = sys.argv[1:3]
    ru = json.load(open(ru_path, encoding="utf-8"))
    total_grow = 0
    rows = []
    for fn in sorted(os.listdir(gdir)):
        if not fn.endswith(".gcx"):
            continue
        d = open(os.path.join(gdir, fn), "rb").read()
        s2 = G.sec2_offset(d)
        size, tab_off, str_off, str_end, seed = struct.unpack_from("<5I", d, s2)
        en_bytes = ru_bytes = grow = 0
        seen = set()
        for _, off, t in G.strings(d):
            k = t.decode("latin-1")
            if off in seen or k not in ru:
                continue
            seen.add(off)
            new = len(encode(ru[k], bar_newline=False))
            en_bytes += len(t)
            ru_bytes += new
            grow += max(0, new - len(t))
        total_grow += grow
        rows.append((fn, len(d), s2, size, str_end, en_bytes, ru_bytes, grow))
    for fn, ln, s2, size, str_end, en, r, g in rows[:12]:
        print(f"{fn:24s} file {ln:7d} sec2 {s2:#x} size {size:#x} str_end {str_end:#x} "
              f"tail {ln - (s2 + size):6d} | EN {en:6d} RU {r:6d} grow {g:6d}")
    print("...")
    print(f"files {len(rows)}, total growth if appended: {total_grow} B, "
          f"max per file {max(r[7] for r in rows)} B")


if __name__ == "__main__":
    main()
