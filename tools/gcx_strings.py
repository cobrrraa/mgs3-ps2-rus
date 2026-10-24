"""List the string entries of a GCX (PS2: encrypted LCG-XOR string area; PC: plain, LCGB header).
Usage: gcx_strings.py FILE [ENC] [LIMIT]
Each string entry of the table (flag 0x80000000) is printed as: index, offset, text.
"""
import struct
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gcx as G  # noqa: E402


def entries(data):
    """[(index, is_string, offset_in_area)], area bytes (decrypted)."""
    d = G.xor_area(data)
    s2, a, b, _ = G.string_area(d)
    n = (a - (s2 + 0x14)) // 4
    tab = struct.unpack_from(f"<{n}I", d, s2 + 0x14)
    return [(i, bool(v & 0x80000000), v & 0x7FFFFFFF) for i, v in enumerate(tab)], d[a:b]


def text_at(area, off):
    end = area.find(b"\x00", off)
    return area[off:end]


def main():
    path = sys.argv[1]
    enc = sys.argv[2] if len(sys.argv) > 2 else "latin-1"
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    ents, area = entries(open(path, "rb").read())
    strs = [(i, o) for i, s, o in ents if s]
    data_offs = [o for i, s, o in ents if not s]
    print(f"entries {len(ents)}, strings {len(strs)}, data {len(data_offs)}, area {len(area)} B")
    if strs and data_offs:
        print(f"strings span {min(o for _, o in strs):#x}..{max(o for _, o in strs):#x}, "
              f"data span {min(data_offs):#x}..{max(data_offs):#x}")
    for i, o in strs[:limit]:
        print(f"{i:5d} {o:#07x} {text_at(area, o).decode(enc, 'replace')!r}"
              .encode("ascii", "backslashreplace").decode())


if __name__ == "__main__":
    main()
