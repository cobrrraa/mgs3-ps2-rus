"""Validate subtitle block headers of one .DAT and count blocks whose Russian text fits.
Usage: fit_stats.py ISO TABLE.csv PS2.jsonl DAT OVERRIDES.json [...]
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isols import list_iso, SECTOR  # noqa: E402
from encoding_ru import encode  # noqa: E402
from demo_blocks import blocks  # noqa: E402
from apply_subs import load_texts  # noqa: E402


def main():
    iso, table, jsonl, dat, *overrides = sys.argv[1:]
    ru = load_texts(table, overrides)
    with open(jsonl, encoding="utf-8") as f:
        ps2 = [json.loads(line) for line in f]
    lba = next(e[1] for e in list_iso(iso) if e[0] == "/MGS/" + dat)
    ok = bad_hdr = fit = 0
    over = []
    multi = 0
    with open(iso, "rb") as f:
        for run in blocks(ps2, dat):
            first = run[0][1]
            f.seek(lba * SECTOR + first["offset"] - 24)
            _, four, bsize, _, zero, rsize = struct.unpack("<6I", f.read(24))
            if not (four == 4 and zero == 0 and rsize == sum(r["rec_len"] for _, r in run)
                    and bsize == (24 + rsize + 15) & ~15):
                bad_hdr += 1
                if bad_hdr <= 5:
                    print(f"odd header @{first['offset']:#x}: {four} {bsize} {zero} {rsize}")
                continue
            ok += 1
            multi += len(run) > 1
            need = sum((16 + len(encode(ru[i]["ru"])) + 1 + 3) & ~3 for i, _ in run)
            if need <= bsize - 24:
                fit += 1
            else:
                over.append(need - (bsize - 24))
    print(f"{dat}: blocks {ok} (multi-record {multi}), odd headers {bad_hdr}, fit {fit}, "
          f"over {len(over)} (sum {sum(over)} B, max {max(over, default=0)} B)")


if __name__ == "__main__":
    main()
