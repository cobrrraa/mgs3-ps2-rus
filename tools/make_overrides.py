"""Build manual overrides for PS2 lines whose split/markup differs from the PC version.
Usage: make_overrides.py PC.jsonl OUT.json
Output: {"<ps2 id>": {"ru": "...", "note": "..."}}
"""
import json
import sys


def main():
    pc_path, out_path = sys.argv[1:3]
    with open(pc_path, encoding="utf-8") as f:
        pc = {(p["file"], p["idx"]): p for p in map(json.loads, f)}

    shago_a = pc[("v090_010_p010.sdt", 12)]["ru"]
    shago_b = pc[("v090_010_p010.sdt", 13)]["ru"]
    first, _, second = shago_a.partition("|")
    over = {
        # PC: "Yes. The Shagohod|- "The Treading Behemoth" -" + "a tank capable of launching|nuclear IRBMs."
        # PS2: "Yes. The Shagohod -" + ""The Treading Behemoth" - a tank|capable of launching nuclear IRBMs."
        "128": {"ru": first, "note": "PC line split differently (v090_010_p010 #12, part 1)"},
        "129": {"ru": f"{second} {shago_b.replace('|', ' ')}",
                "note": "PC v090_010_p010 #12 part 2 + #13; line breaks need manual layout"},
    }
    # PC shows button icons as private-use glyphs; PS2 spells the button out.
    for pid, ru in (("2427", "Нажми R1 или R2|на экране рации..."),
                    ("3840", "Когда во время заставки|горит \"R1\"...")):
        over[pid] = {"ru": ru, "note": "button icon restored as text; check wording"}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(over, f, ensure_ascii=False, indent=1)
    for k, v in over.items():
        print(k, json.dumps(v, ensure_ascii=True))


if __name__ == "__main__":
    main()
