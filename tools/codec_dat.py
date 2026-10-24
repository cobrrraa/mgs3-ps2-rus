"""MGS3 PS2 CODEC.DAT: a plain sequence of GCX scripts (one per codec call / data set).

Each script starts with the GCX timestamp 0x4165BABE and is 16-byte aligned; the string areas are
encrypted like the stage GCX (tools/gcx.py, seed 0x41822C07). All codec dialogue, personal data
and save screen text is in the string tables.

    blocks(data) -> [(offset, end)]
Usage: codec_dat.py CODEC.DAT OUT_STRINGS.json   (unique strings, latin-1, as {"table": [...]})
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gcx as G  # noqa: E402

MAGIC = b"\xbe\xba\x65\x41"


def blocks(data):
    pos, i = [], data.find(MAGIC)
    while i != -1:
        pos.append(i)
        i = data.find(MAGIC, i + 4)
    return list(zip(pos, pos[1:] + [len(data)]))


def main():
    src, out = sys.argv[1:3]
    data = open(src, "rb").read()
    uniq, total = set(), 0
    for a, b in blocks(data):
        for _, _, s in G.strings(data[a:b]):
            uniq.add(s.decode("latin-1"))
            total += 1
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"table": sorted(uniq)}, f, ensure_ascii=False, indent=1)
    print(f"{len(blocks(data))} scripts, {total} string refs, {len(uniq)} unique -> {out}")


if __name__ == "__main__":
    main()
