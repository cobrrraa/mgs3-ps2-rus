"""Build an English -> Russian dictionary from the PC GCX files.

PC (fr slot) GCX string tables hold language pairs; the russifier replaced some entries with
cp1251 Russian. For every entry the russifier changed, look at the neighbouring entries of the
original file for the English line (the one that is plain ASCII and also present in the PS2 GCX).

Usage: gcx_pc_pairs.py PC_GCX_DIR RUS_GCX_DIR PS2_STRINGS.json OUT.json REPORT.txt
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gcx as G  # noqa: E402


def main():
    pc_dir, ru_dir, ps2_json, out_path, report_path = sys.argv[1:6]
    with open(ps2_json, encoding="utf-8") as f:
        ps2 = set(json.load(f)["table"])
    pairs = collections.defaultdict(collections.Counter)
    changed = unmatched = 0
    samples = []
    for fn in sorted(os.listdir(ru_dir)):
        pc_path = os.path.join(pc_dir, fn)
        if not os.path.exists(pc_path):
            continue
        en = G.strings(open(pc_path, "rb").read())
        ru = G.strings(open(os.path.join(ru_dir, fn), "rb").read())
        if len(en) != len(ru):
            print(f"{fn}: entry count differs ({len(en)} vs {len(ru)}), skipped")
            continue
        by_idx = {i: t for i, _, t in en}
        for (i, _, a), (_, _, b) in zip(en, ru):
            if a == b:
                continue
            changed += 1
            ru_text = b.decode("cp1251", "replace")
            cand = [by_idx.get(i + d) for d in (1, -1, 2, -2)]
            eng = next((c.decode("latin-1") for c in cand if c is not None
                        and c.decode("latin-1") in ps2), None)
            if eng is None:
                unmatched += 1
                if len(samples) < 40:
                    samples.append((fn, i, a.decode("utf-8", "replace"), ru_text))
                continue
            pairs[eng][ru_text] += 1
    result = {en: c.most_common(1)[0][0] for en, c in pairs.items()}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"changed entries {changed}, paired {changed - unmatched}, unmatched {unmatched}\n")
        f.write(f"distinct English lines with Russian: {len(result)} of {len(ps2)} PS2 strings\n\n")
        for fn, i, a, b in samples:
            f.write(f"{fn} #{i}: {a!r} -> {b!r}\n")
        f.write("\n--- sample pairs\n")
        for en, r in list(result.items())[:60]:
            f.write(f"{en!r} -> {r!r}\n")
    print(f"changed {changed}, paired {changed - unmatched}; dictionary {len(result)} of {len(ps2)} PS2 strings")


if __name__ == "__main__":
    main()
