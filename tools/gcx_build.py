"""Build a Russian GCX from a decrypted PS2 GCX (seed already 0).

Nothing inside the file moves (the bytecode after the string area is referenced by absolute
offsets). Some menus take only the first string of a list and walk to the next one past its NUL
(the "first time playing MGS?" question), so strings that follow each other directly form a chain
that must stay contiguous. Each chain is re-packed in its own bytes; when the Russian chain is
longer, the strings from the first one that does not fit onwards are appended, still contiguous, at
the end of the file. Every string reference (u32 0x80000000|offset in the table) is redirected.
Offsets are relative to the string area and may point past its end - the game only adds them to
the area base. seed stays 0, so the game does not decrypt.

    build(gcx_bytes, ru_dict) -> (new_bytes, stats)
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gcx as G  # noqa: E402
from encoding_ru import encode  # noqa: E402


def chains(d, area, offsets):
    """Group referenced strings that follow each other directly: [[(off, end), ...], ...]."""
    out = []
    for off in sorted(offsets):
        end = d.index(b"\x00", area + off) - area
        if out and out[-1][-1][1] + 1 == off:
            out[-1].append((off, end))
        else:
            out.append([(off, end)])
    return out


def build(gcx, ru):
    d = bytearray(gcx)
    s2 = G.sec2_offset(d)
    _, tab_off, str_off, str_end, seed = struct.unpack_from("<5I", d, s2)
    assert seed == 0, "expects a decrypted GCX"
    area = s2 + str_off
    n = (str_off - tab_off) // 4
    tab_pos = s2 + tab_off

    refs = {}  # string offset -> table word positions
    for k in range(n):
        v = struct.unpack_from("<I", d, tab_pos + 4 * k)[0]
        if v & 0x80000000:
            refs.setdefault(v & 0x7FFFFFFF, []).append(tab_pos + 4 * k)

    stats = {"in_place": 0, "appended": 0, "kept": 0}
    tail = bytearray()
    for chain in chains(d, area, refs):
        olds = [bytes(d[area + off:area + end]) for off, end in chain]
        news = []
        for old in olds:
            en = old.decode("latin-1")
            if en in ru:
                news.append(encode(ru[en], bar_newline=False))
            else:
                news.append(old)
                stats["kept"] += 1
        if news == olds:
            continue
        lo, hi = chain[0][0], chain[-1][1] + 1
        d[area + lo:area + hi] = b"\x00" * (hi - lo)
        pos, spilled = lo, False
        for (off, _), new in zip(chain, news):
            spilled = spilled or pos + len(new) + 1 > hi
            if spilled:
                new_off = len(d) + len(tail) - area
                tail += new + b"\x00"
                stats["appended"] += 1
            else:
                new_off = pos
                d[area + pos:area + pos + len(new)] = new
                pos += len(new) + 1
                stats["in_place"] += 1
            for p in refs[off]:
                struct.pack_into("<I", d, p, 0x80000000 | new_off)
    tail += b"\x00" * (-len(tail) % 16)
    return bytes(d + tail), stats


if __name__ == "__main__":
    import json
    src, ru_path, dst = sys.argv[1:4]
    out, st = build(open(src, "rb").read(), json.load(open(ru_path, encoding="utf-8")))
    open(dst, "wb").write(out)
    print(st, len(out))
