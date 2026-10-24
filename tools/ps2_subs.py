"""Extract English subtitle records from PS2 DEMO.DAT and VOX.DAT (read straight from the ISO).
Usage: ps2_subs.py ISO OUT.jsonl
Each line: {"file", "offset", "start", "end", "rec_len", "raw_hex", "text"}
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isols import list_iso, SECTOR  # noqa: E402
from subrec import parse, ps2_decode  # noqa: E402

CHUNK = 64 << 20
OVERLAP = 0x1000
# order matters: record ids are positions in the output, MOVIE.DAT was added last to keep old ids
TARGETS = ("/MGS/DEMO.DAT", "/MGS/VOX.DAT", "/MGS/MOVIE.DAT")


def scan(f, lba, size):
    pos = 0
    while pos < size:
        f.seek(lba * SECTOR + pos)
        data = f.read(min(CHUNK + OVERLAP, size - pos))
        for off, start, end, rec_len, lang, raw in parse(data, langs=(1,), padded=True):
            if off >= CHUNK:  # handled by the next chunk
                break
            yield pos + off, start, end, rec_len, raw
        pos += CHUNK


def main():
    iso, out_path = sys.argv[1:3]
    entries = {e[0].upper(): e for e in list_iso(iso)}
    high = collections.Counter()
    with open(iso, "rb") as f, open(out_path, "w", encoding="utf-8") as out:
        for target in TARGETS:
            _, lba, size = entries[target]
            n = 0
            for off, start, end, rec_len, raw in scan(f, lba, size):
                text = ps2_decode(raw)
                high.update(b for b in raw.replace(b"\x80|", b"") if b >= 0x7F)
                out.write(json.dumps({"file": target.rsplit("/", 1)[1], "offset": off, "start": start,
                                      "end": end, "rec_len": rec_len, "raw_hex": raw.hex(),
                                      "text": text}, ensure_ascii=False) + "\n")
                n += 1
            print(f"{target}: {n} records")
    print("non-ASCII bytes (excluding \\x80| newline):",
          {f"{b:02x}": c for b, c in high.most_common()})


if __name__ == "__main__":
    main()
