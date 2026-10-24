"""For PS2 GCX strings without a Russian translation, find the closest PC English line that the
russifier translated (all aligned PC pairs, not only exact PS2 matches) as a starting point.

Usage: gcx_fuzzy.py PC_GCX_DIR RUS_GCX_DIR PS2_STRINGS.json DICT.json OUT.txt
OUT lists, per missing string: its usage count, the PS2 text, the closest PC English + Russian.
Memory-card messages (left in English on purpose) are skipped.
"""
import difflib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gcx_pc_align import runs, decode_ru  # noqa: E402

SKIP = re.compile(r"memory card|Memory card", re.I)


def main():
    pc_dir, ru_dir, ps2_json, dict_json, out_path = sys.argv[1:6]
    with open(ps2_json, encoding="utf-8") as f:
        table = json.load(f)["table"]
    with open(dict_json, encoding="utf-8") as f:
        done = json.load(f)
    all_pairs = {}
    for fn in sorted(os.listdir(ru_dir)):
        pc_path = os.path.join(pc_dir, fn)
        if not os.path.exists(pc_path):
            continue
        a = runs(open(pc_path, "rb").read())
        b = runs(open(os.path.join(ru_dir, fn), "rb").read())
        sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "replace" and i2 - i1 == j2 - j1:
                for x, y in zip(a[i1:i2], b[j1:j2]):
                    if any(c >= 0xC0 for c in y) and re.search(rb"[A-Za-z]{3}", x):
                        all_pairs.setdefault(x.decode("latin-1"), decode_ru(y))
    keys = list(all_pairs)
    missing = [t for t in table if len(re.findall(r"[A-Za-z]", t)) >= 3
               and t not in done and not SKIP.search(t)]
    with open(out_path, "w", encoding="utf-8") as out:
        for t in sorted(missing, key=lambda s: -len(table[s])):
            best = difflib.get_close_matches(t, keys, n=1, cutoff=0.6)
            out.write(f"### {len(table[t])}x\nEN: {t!r}\n")
            if best:
                ratio = difflib.SequenceMatcher(None, t, best[0]).ratio()
                out.write(f"PC({ratio:.2f}): {best[0]!r}\nRU: {all_pairs[best[0]]!r}\n")
            out.write("\n")
    print(f"PC pairs {len(all_pairs)}, missing (without memory card) {len(missing)} -> {out_path}")


if __name__ == "__main__":
    main()
