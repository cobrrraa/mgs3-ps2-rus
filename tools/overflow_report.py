"""Report subtitle blocks (DEMO.DAT, MOVIE.DAT) whose Russian text does not fit.
Usage: overflow_report.py ISO TABLE.csv PS2.jsonl OUT.txt OVERRIDES.json [...]
Each block lists: bytes to cut, then its lines (id, aligned record size, EN, RU), longest RU first.
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isols import list_iso, SECTOR  # noqa: E402
from encoding_ru import encode  # noqa: E402
from demo_blocks import blocks  # noqa: E402
from apply_subs import load_texts, BLOCK_FILES  # noqa: E402


def rec_size(text):
    return (16 + len(encode(text)) + 1 + 3) & ~3


def main():
    iso, table, jsonl, out_path, *overrides = sys.argv[1:]
    ru = load_texts(table, overrides)
    with open(jsonl, encoding="utf-8") as f:
        ps2 = [json.loads(line) for line in f]
    lbas = {e[0]: e[1] for e in list_iso(iso)}
    total = 0
    with open(iso, "rb") as f, open(out_path, "w", encoding="utf-8") as out:
        for dat in BLOCK_FILES:
            for run in blocks(ps2, dat):
                if any(not ru[i]["ru"] for i, _ in run):
                    out.write(f"=== {dat} ids {run[0][0]}-{run[-1][0]}: NO TRANSLATION\n")
                    continue
                f.seek(lbas["/MGS/" + dat] * SECTOR + run[0][1]["offset"] - 24)
                room = struct.unpack("<6I", f.read(24))[2] - 24
                need = sum(rec_size(ru[i]["ru"]) for i, _ in run)
                if need <= room:
                    continue
                total += need - room
                out.write(f"=== {dat} ids {run[0][0]}-{run[-1][0]} ({ru[run[0][0]]['pc_file']}): "
                          f"cut {need - room} B\n")
                for i, _ in sorted(run, key=lambda x: -len(ru[x[0]]["ru"])):
                    out.write(f"{i} [{rec_size(ru[i]['ru'])}] EN: {ru[i]['en_ps2']}\n      RU: {ru[i]['ru']}\n")
    print(f"total to cut: {total} B -> {out_path}")


if __name__ == "__main__":
    main()
