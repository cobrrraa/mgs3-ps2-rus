"""Hex-dump a region of a file inside the ISO.
Usage: isodump.py ISO PATH OFFSET LENGTH   (offset/length accept 0x prefix)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isols import list_iso, SECTOR  # noqa: E402


def main():
    iso, want, off, ln = sys.argv[1:5]
    off, ln = int(off, 0), int(ln, 0)
    _, lba, size = next(e for e in list_iso(iso) if e[0].upper() == want.upper())
    with open(iso, "rb") as f:
        f.seek(lba * SECTOR + off)
        data = f.read(min(ln, size - off))
    for i in range(0, len(data), 16):
        c = data[i:i + 16]
        hx = " ".join(f"{b:02x}" for b in c).ljust(47)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in c)
        print(f"{off + i:08x}  {hx}  {asc}")


if __name__ == "__main__":
    main()
