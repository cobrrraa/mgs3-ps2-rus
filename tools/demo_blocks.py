"""Group PS2 DEMO.DAT subtitle records into blocks and check the block header:
    u16 type(0x84), u16 ?, u32 4, u32 block_size, u32 first_start, u32 0, u32 records_size
followed by the records (records_size = sum of rec_len). Reports how many blocks match.
Usage: demo_blocks.py ISO PS2.jsonl
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isols import list_iso, SECTOR  # noqa: E402

HDR = 0x18                 # header bytes right before the first record


def blocks(ps2, dat="DEMO.DAT"):
    """Contiguous runs of records of one .DAT (DEMO.DAT / MOVIE.DAT) -> list of lists of (id, record)."""
    runs = []
    end = None
    for i, r in enumerate(ps2):
        if r["file"] != dat:
            continue
        if end != r["offset"]:
            runs.append([])
        runs[-1].append((i, r))
        end = r["offset"] + r["rec_len"]
    return runs


def main():
    iso, jsonl = sys.argv[1:3]
    with open(jsonl, encoding="utf-8") as f:
        ps2 = [json.loads(line) for line in f]
    lba = next(e[1] for e in list_iso(iso) if e[0] == "/MGS/DEMO.DAT")
    ok = bad = 0
    with open(iso, "rb") as f:
        for run in blocks(ps2):
            first = run[0][1]
            size = sum(r["rec_len"] for _, r in run)
            f.seek(lba * SECTOR + first["offset"] - HDR)
            h = struct.unpack("<HHIIIII", f.read(HDR))
            if h[0] == 0x84 and h[2] == 4 and h[6] == size and h[3] == size + 0x1C and h[4] == first["start"]:
                ok += 1
            else:
                bad += 1
                print(f"block @{first['offset']:#x} ids {run[0][0]}-{run[-1][0]}: header {h}, records {size}")
    print(f"blocks with matching header: {ok}, other: {bad}")


if __name__ == "__main__":
    main()
