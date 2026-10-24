"""Find every subtitle block of VOX.DAT by its header and list all records inside (any language).

Block header (24 bytes): u32 ?, u32 4, u32 block_size, u32 start, u32 flags, u32 records_size, with
block_size == align16(24 + records_size). Records follow and are walked by rec_len; whatever is
left of records_size after the last record ("tail", 0..few dozen bytes, meaning unknown) is kept
verbatim. VOX blocks often hold each line twice: lang 1 and lang 7 (same text).

Usage: vox_blocks.py ISO OUT.json
OUT: [{"off": records offset in VOX.DAT, "bsize", "rsize", "tail": hex,
       "recs": [{"off", "start", "end", "len", "lang", "text": hex}]}]
"""
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isols import list_iso, SECTOR  # noqa: E402

CHUNK = 64 << 20
# lookahead: matches may overlap (audio bytes right before a header can look like one)
HDR = re.compile(rb"(?s)(?=\x04\x00\x00\x00(.{4})(.{4})(.{4})(.{4}))")
MAX_TAIL = 0x400


def walk(buf, pos, rsize):
    """(records, tail bytes) of a block starting at buf[pos], or None if it does not look like one."""
    recs, end = [], pos + rsize
    while pos + 16 <= end:
        start, stop, zero, ln, lang = struct.unpack_from("<IIIHH", buf, pos)
        if zero or not (16 < ln <= end - pos) or not (1 <= lang <= 7) or stop < start:
            break
        nul = buf.find(b"\x00", pos + 16, pos + ln)  # empty text exists (some lang-7 records)
        if nul == -1:
            break
        recs.append({"off": pos, "start": start, "end": stop, "len": ln, "lang": lang,
                     "text": buf[pos + 16:nul].hex()})
        pos += ln
    if not recs or end - pos > MAX_TAIL:
        return None
    return recs, buf[pos:end]


def main():
    iso, out_path = sys.argv[1:3]
    _, lba, size = next(e for e in list_iso(iso) if e[0] == "/MGS/VOX.DAT")
    found = []
    with open(iso, "rb") as f:
        pos = 0
        while pos < size:
            f.seek(lba * SECTOR + pos)
            buf = f.read(min(CHUNK + 0x2000, size - pos))
            for m in HDR.finditer(buf):
                if m.start() >= CHUNK:
                    break
                bsize, _, _, rsize = (struct.unpack("<I", g)[0] for g in m.groups())
                if not (0 < rsize < 0x2000 and bsize == (24 + rsize + 15) & ~15):
                    continue
                res = walk(buf, m.start() + 20, rsize)
                if res:
                    recs, tail = res
                    for r in recs:
                        r["off"] += pos
                    found.append({"off": pos + m.start() + 20, "bsize": bsize, "rsize": rsize,
                                  "tail": tail.hex(), "recs": recs})
            pos += CHUNK
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(found, f)
    langs = {}
    for b in found:
        for r in b["recs"]:
            langs[r["lang"]] = langs.get(r["lang"], 0) + 1
    print(f"blocks: {len(found)}, records by language: {langs}")


if __name__ == "__main__":
    main()
