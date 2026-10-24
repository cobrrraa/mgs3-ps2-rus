"""Make overflowing VOX blocks fit with meaning-preserving shortenings, block by block:
  1. "!!!" -> "!!", "?!!" -> "?!", "... " -> "...", drop stray empty lines;
  2. a shorter Russian variant used elsewhere in the PC russifier for the same English line.
Lines are shortened only as far as their block needs. Output: {id: text} for the remaining
manual pass, plus a list of blocks that still do not fit.

Usage: vox_autoshort.py TABLE.csv PS2.jsonl PC.jsonl VOX_BLOCKS.json OUT.json OVERRIDES.json [...]
"""
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from apply_subs import load_texts, vox_body, vox_pairs, BLOCK_HDR  # noqa: E402
from subrec import norm  # noqa: E402
from encoding_ru import encode  # noqa: E402


def encodable(t):
    try:
        encode(t)
        return True
    except (ValueError, UnicodeEncodeError):  # e.g. PC button-icon glyphs
        return False


def punct(t):
    t = re.sub(r"!{3,}", "!!", t)
    t = t.replace("?!!", "?!").replace("... ", "...").replace("||", "|")
    return t.strip("|")


def main():
    table, jsonl, pc_path, blocks_path, out_path, *overrides = sys.argv[1:]
    ru = load_texts(table, overrides)
    with open(jsonl, encoding="utf-8") as f:
        ps2 = [json.loads(line) for line in f]
    with open(pc_path, encoding="utf-8") as f:
        variants = collections.defaultdict(set)
        for p in map(json.loads, f):
            if p["ru"]:
                variants[norm(p["en"])].add(p["ru"].replace("\r\n", "|").replace("\n", "|"))
    with open(blocks_path, encoding="utf-8") as f:
        vox = json.load(f)

    id_by_off = {r["offset"]: i for i, r in enumerate(ps2) if r["file"] == "VOX.DAT"}
    text = {o: ru[i]["ru"] for o, i in id_by_off.items()}
    edits, left = {}, []
    for blk in vox:
        room = blk["bsize"] - BLOCK_HDR
        body = vox_body(blk, text, vox_pairs(vox, text))
        if body is None or len(body) <= room:
            continue
        offs = [r["off"] for r in blk["recs"] if r["lang"] == 1 and r["off"] in id_by_off]
        for o in offs:
            i = id_by_off[o]
            cands = {punct(text[o])} | {punct(v) for v in variants[norm(ru[i]["en_ps2"])]}
            best = min((c for c in cands if encodable(c)), key=len)
            if len(best) < len(text[o]):
                text[o] = best
                edits[str(i)] = best
            if len(vox_body(blk, text, vox_pairs(vox, text))) <= room:
                break
        if len(vox_body(blk, text, vox_pairs(vox, text))) > room:
            left.append((blk["off"], len(vox_body(blk, text, vox_pairs(vox, text))) - room,
                         [(id_by_off[o], ru[id_by_off[o]]["en_ps2"], text[o]) for o in offs]))

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(edits, f, ensure_ascii=False, indent=1)
    report = out_path.replace(".json", "_left.txt")
    with open(report, "w", encoding="utf-8") as f:
        for off, over, lines in left:
            f.write(f"=== @{off:#x} cut {over} B\n")
            for i, en, t in lines:
                f.write(f"  {i}: {en} -> {t}\n")
    print(f"auto-shortened {len(edits)} lines; blocks still too long: {len(left)} -> {report}")


if __name__ == "__main__":
    main()
