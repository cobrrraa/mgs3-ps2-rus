"""Match PS2 subtitle records to PC English/Russian lines and write the correspondence table.
Usage: match_subs.py PS2.jsonl PC.jsonl OUT.csv [OVERRIDES.json]

Overrides ({"<ps2 id>": {"ru": ..., "note": ...}}) replace the Russian text and set match=manual.
Russian line breaks are normalized to the PC '|' marker (some PC lines use a raw '\\n').

Match order for each PS2 record:
  exact   - same timing + same normalized English
  text    - same normalized English, different timing
  fuzzy   - same timing, English similar (ratio >= 0.6)
  none    - not found
When several PC lines qualify, prefer the PC file that matched the previous PS2 record.
"""
import collections
import csv
import difflib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from subrec import HEADER, norm  # noqa: E402

KIND = {"DEMO.DAT": "demo", "VOX.DAT": "vox", "MOVIE.DAT": "movie"}
# PC draws button icons with private-use glyphs; PS2 subtitles spell the button out.
PC_ICONS = {"": "кнопку действия"}


def ps2_bytes(ru):
    """Size of a Russian line in a single-byte PS2 encoding ('|' becomes the 2-byte \\x80| newline)."""
    return len(ru) + ru.count("|")


def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def pick(cands, prev_file):
    for c in cands:
        if c["file"] == prev_file:
            return c
    return cands[0]


def main():
    ps2_path, pc_path, out_path = sys.argv[1:4]
    overrides = {}
    if len(sys.argv) > 4:
        with open(sys.argv[4], encoding="utf-8") as f:
            overrides = json.load(f)
    ps2 = load(ps2_path)
    pc = load(pc_path)

    by_exact = collections.defaultdict(list)
    by_text = collections.defaultdict(list)
    by_time = collections.defaultdict(list)
    for p in pc:
        n = norm(p["en"])
        by_exact[(p["kind"], p["start"], p["end"], n)].append(p)
        by_text[(p["kind"], n)].append(p)
        by_time[(p["kind"], p["start"], p["end"])].append(p)

    used = set()
    stats = collections.Counter()
    ambiguous = 0
    prev_file = None
    rows = []
    for i, r in enumerate(ps2):
        kind = KIND[r["file"]]
        n = norm(r["text"])
        how, cands = "none", []
        if (kind, r["start"], r["end"], n) in by_exact:
            how, cands = "exact", by_exact[(kind, r["start"], r["end"], n)]
        elif (kind, n) in by_text:
            how, cands = "text", by_text[(kind, n)]
        else:
            scored = [(difflib.SequenceMatcher(None, n, norm(c["en"])).ratio(), c)
                      for c in by_time.get((kind, r["start"], r["end"]), [])]
            scored = [sc for sc in scored if sc[0] >= 0.6]
            if scored:
                scored.sort(key=lambda sc: -sc[0])
                how, cands = "fuzzy", [c for _, c in scored]
        pc_line = pick(cands, prev_file) if cands else None
        if pc_line:
            prev_file = pc_line["file"]
            used.add((pc_line["kind"], pc_line["file"], pc_line["idx"]))
            if len({c["ru"] for c in cands}) > 1:
                ambiguous += 1
        ru = pc_line["ru"] if pc_line else ""
        note = ""
        if pc_line and ru is None:  # the PC russifier has no translation for this file
            how, ru, note = "no_ru", "", "no Russian in the PC russifier"
        if str(i) in overrides:
            how, ru, note = "manual", overrides[str(i)]["ru"], overrides[str(i)]["note"]
        stats[how] += 1
        ru = ru.replace("\r\n", "|").replace("\n", "|")
        for icon, words in PC_ICONS.items():
            if icon in ru:
                ru = ru.replace(icon, words)
                note = note or "button icon replaced with words; check wording"

        cap = r["rec_len"] - HEADER - 1
        need = ps2_bytes(ru) if ru else 0
        rows.append({
            "id": i,
            "ps2_file": r["file"],
            "ps2_offset": f"{r['offset']:#x}",
            "start": r["start"],
            "end": r["end"],
            "rec_len": r["rec_len"],
            "en_ps2": r["text"],
            "ru": ru,
            "match": how,
            "variants": len({c["ru"] for c in cands}),
            "pc_file": pc_line["file"] if pc_line else "",
            "pc_idx": pc_line["idx"] if pc_line else "",
            "en_pc": pc_line["en"] if pc_line else "",
            "en_bytes": len(r["text"]) + r["text"].count("|"),
            "ru_bytes": need,
            "capacity": cap,
            "overflow": max(0, need - cap),
            "note": note,
        })

    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=";")
        w.writeheader()
        w.writerows(rows)

    pc_unused = [p for p in pc if (p["kind"], p["file"], p["idx"]) not in used]
    matched = [x for x in rows if x["match"] != "none"]
    over = [x for x in matched if x["overflow"]]
    print(f"PS2 records: {len(rows)}  matches: {dict(stats)}  ambiguous RU: {ambiguous}")
    print(f"PC lines never used: {len(pc_unused)}")
    for kind in KIND:
        sub = [x for x in matched if x["ps2_file"] == kind]
        en = sum(x["en_bytes"] for x in sub)
        ru = sum(x["ru_bytes"] for x in sub)
        cap = sum(x["capacity"] for x in sub)
        ov = [x for x in sub if x["overflow"]]
        print(f"{kind}: EN {en} B, RU {ru} B ({ru / en:.0%}), in-place capacity {cap} B, "
              f"lines that overflow their record: {len(ov)} of {len(sub)}")
    print(f"total overflow lines: {len(over)}")

    chars = collections.Counter(ch for x in rows for ch in x["ru"])
    cyr = sorted(c for c in chars if "Ѐ" <= c <= "ӿ")
    other = sorted(c for c in chars if not (" " <= c <= "~") and c not in cyr)
    print(f"Cyrillic letters used ({len(cyr)}): {''.join(cyr)}")
    print("other non-ASCII:", {f"U+{ord(c):04X}": chars[c] for c in other})


if __name__ == "__main__":
    main()
