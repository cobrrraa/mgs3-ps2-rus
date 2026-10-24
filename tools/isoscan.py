"""Scan a file inside the ISO for byte patterns without extracting it.
Usage: isoscan.py ISO PATH pattern1 [pattern2 ...]   (patterns are ASCII; prefix hex: for hex)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isols import list_iso, SECTOR  # noqa: E402

CHUNK = 64 << 20


def parse(p):
    return bytes.fromhex(p[4:]) if p.startswith("hex:") else p.encode()


def main():
    iso, want, *pats = sys.argv[1:]
    pats = [parse(p) for p in pats]
    entry = next(e for e in list_iso(iso) if e[0].upper() == want.upper())
    _, lba, size = entry
    counts = {p: 0 for p in pats}
    first = {p: [] for p in pats}
    overlap = max(len(p) for p in pats) - 1
    with open(iso, "rb") as f:
        pos = 0
        tail = b""
        while pos < size:
            f.seek(lba * SECTOR + pos)
            data = f.read(min(CHUNK, size - pos))
            buf = tail + data
            base = pos - len(tail)
            for p in pats:
                i = buf.find(p)
                while i != -1:
                    if i + len(p) > len(tail):
                        counts[p] += 1
                        if len(first[p]) < 8:
                            first[p].append(base + i)
                    i = buf.find(p, i + 1)
            tail = buf[-overlap:] if overlap else b""
            pos += len(data)
    for p in pats:
        print(p, counts[p], [hex(x) for x in first[p]])


if __name__ == "__main__":
    main()
