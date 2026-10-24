"""List VOX blocks whose Russian text does not fit: bytes to cut, EN/RU of their lang-1 lines.
Usage: vox_overflow.py TABLE.csv PS2.jsonl VOX_BLOCKS.json OUT.txt OVERRIDES.json [...]
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from apply_subs import load_texts, vox_body, vox_pairs, BLOCK_HDR  # noqa: E402


def main():
    table, jsonl, blocks_path, out_path, *overrides = sys.argv[1:]
    ru = load_texts(table, overrides)
    with open(jsonl, encoding="utf-8") as f:
        ps2 = [json.loads(line) for line in f]
    with open(blocks_path, encoding="utf-8") as f:
        vox = json.load(f)
    id_by_off = {r["offset"]: i for i, r in enumerate(ps2) if r["file"] == "VOX.DAT"}
    ru_by_off = {o: ru[i]["ru"] for o, i in id_by_off.items()}
    pair = vox_pairs(vox, ru_by_off)
    by_line = collections.Counter()
    with open(out_path, "w", encoding="utf-8") as out:
        for blk in vox:
            body = vox_body(blk, ru_by_off, pair)
            if body is None:
                out.write(f"=== @{blk['off']:#x}: NO TRANSLATION\n")
                continue
            over = len(body) - (blk["bsize"] - BLOCK_HDR)
            if over <= 0:
                continue
            ids = [id_by_off[r["off"]] for r in blk["recs"] if r["lang"] == 1 and r["off"] in id_by_off]
            out.write(f"=== @{blk['off']:#x} cut {over} B, recs {len(blk['recs'])}, tail {len(blk['tail']) // 2}\n")
            for i in ids:
                out.write(f"  {i}: {ru[i]['en_ps2']} -> {ru[i]['ru']}\n")
                by_line[(ru[i]["en_ps2"], ru[i]["ru"])] += 1
        out.write("\n=== most frequent overflowing lines\n")
        for (en, r), n in by_line.most_common(60):
            out.write(f"{n:4d}  {en} -> {r}\n")
    print(f"distinct overflowing lines: {len(by_line)} -> {out_path}")


if __name__ == "__main__":
    main()
