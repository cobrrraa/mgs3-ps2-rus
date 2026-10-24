"""Print EN / RU (with overrides) for given subtitle ids into a UTF-8 file.
Usage: show_ids.py TABLE.csv OUT.txt ID[,ID...] OVERRIDES.json [...]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from apply_subs import load_texts  # noqa: E402


def main():
    table, out_path, ids, *overrides = sys.argv[1:]
    rows = load_texts(table, overrides)
    with open(out_path, "w", encoding="utf-8") as out:
        for i in (int(x) for x in ids.split(",")):
            out.write(f"{i} ({rows[i]['pc_file']})\n  EN: {rows[i]['en_ps2']}\n  RU: {rows[i]['ru']}\n")


if __name__ == "__main__":
    main()
