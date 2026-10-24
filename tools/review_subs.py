"""Write a human-readable review of weak matches and ambiguous Russian variants.
Usage: review_subs.py TABLE.csv PC.jsonl OUT.txt
"""
import collections
import csv
import json
import sys


def main():
    table, pc_path, out_path = sys.argv[1:4]
    with open(table, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    with open(pc_path, encoding="utf-8") as f:
        pc = [json.loads(line) for line in f]

    with open(out_path, "w", encoding="utf-8") as out:
        out.write("=== weak / missing matches\n")
        for r in rows:
            if r["match"] in ("none", "text", "fuzzy"):
                out.write(f"[{r['match']}] id={r['id']} {r['ps2_file']} {r['ps2_offset']} "
                          f"t={r['start']}-{r['end']}\n  PS2: {r['en_ps2']}\n  PC : {r['en_pc']}\n"
                          f"  RU : {r['ru']}\n")

        groups = collections.defaultdict(set)
        for p in pc:
            groups[(p["kind"], p["start"], p["end"], p["en"])].add(p["ru"])
        amb = [(k, v) for k, v in groups.items() if len(v) > 1]
        out.write(f"\n=== same EN + timing, different RU: {len(amb)} groups\n")
        for k, v in amb[:30]:
            out.write(f"{k[0]} {k[3]!r} -> {sorted(v)}\n")

        worst = sorted((r for r in rows if int(r["overflow"])), key=lambda r: -int(r["overflow"]))
        out.write(f"\n=== largest overflows ({len(worst)} lines)\n")
        for r in worst[:15]:
            out.write(f"+{r['overflow']} B  cap={r['capacity']}  {r['en_ps2']}\n   -> {r['ru']}\n")


if __name__ == "__main__":
    main()
