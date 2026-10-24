"""Count subtitle records: [u32 start][u32 end][u32 0][u16 len][u16 lang][text\\0].
Usage:
    subscan.py iso ISO PATH         -> scan a file inside the PS2 ISO
    subscan.py dir DIR              -> scan every file in a PC folder (lang 1 only)
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isols import list_iso, SECTOR  # noqa: E402

# 8 bytes of times, 4 zero bytes, u16 len, u16 lang=1, then a printable-ish first char
REC = re.compile(rb"(?s)(.{4})(.{4})\x00\x00\x00\x00(.{2})\x01\x00(?=[\x20-\x7e\x80-\xff])")


def records(buf):
    for m in REC.finditer(buf):
        start, end = struct.unpack("<II", m.group(1) + m.group(2))
        ln = struct.unpack("<H", m.group(3))[0]
        if not (0 <= start < end < 0x1000000) or not (13 <= ln <= 0x400):
            continue
        tstart = m.end()
        nul = buf.find(b"\x00", tstart, tstart + ln)
        if nul == -1:
            continue
        yield m.start(), start, end, buf[tstart:nul]


def scan_iso(iso, want):
    _, lba, size = next(e for e in list_iso(iso) if e[0].upper() == want.upper())
    n = 0
    samples = []
    chunk = 64 << 20
    with open(iso, "rb") as f:
        pos = 0
        while pos < size:
            f.seek(lba * SECTOR + pos)
            data = f.read(min(chunk + 4096, size - pos))
            for off, s, e, t in records(data):
                if off >= chunk:
                    break
                n += 1
                if len(samples) < 5:
                    samples.append((pos + off, t))
            pos += chunk
    print(f"{want}: {n} records")
    for s in samples:
        print("   ", hex(s[0]), s[1][:70])


def scan_dir(root):
    total = 0
    files = 0
    for dp, _, fns in os.walk(root):
        for fn in fns:
            with open(os.path.join(dp, fn), "rb") as f:
                n = sum(1 for _ in records(f.read()))
            total += n
            files += n > 0
    print(f"{root}: {total} lang-1 records in {files} files")


if __name__ == "__main__":
    if sys.argv[1] == "iso":
        scan_iso(sys.argv[2], sys.argv[3])
    else:
        scan_dir(sys.argv[2])
