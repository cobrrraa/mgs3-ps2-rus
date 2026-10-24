"""Apply phrase replacements to every Russian line of one .DAT (after all other overrides),
so a shortened phrase reads the same everywhere.
Usage: text_rules.py TABLE.csv DAT OUT.json OVERRIDES.json [...]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from apply_subs import load_texts  # noqa: E402

RULES = [
    ("Запрос огневой поддержки", "Запрос артподдержки"),
    ("обаружена", "обнаружена"),
]


def main():
    table, dat, out_path, *overrides = sys.argv[1:]
    rows = load_texts(table, overrides)
    out = {}
    for i, r in rows.items():
        if r["ps2_file"] != dat:
            continue
        t = r["ru"]
        for a, b in RULES:
            t = t.replace(a, b)
        if t != r["ru"]:
            out[str(i)] = t
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"{dat}: {len(out)} lines changed by rules -> {out_path}")


if __name__ == "__main__":
    main()
