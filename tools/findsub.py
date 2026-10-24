"""Find subtitle lines by English text in the PS2 and PC extracts.
Usage: findsub.py PS2.jsonl PC.jsonl TEXT [TEXT ...]
"""
import json
import sys


def main():
    ps2_path, pc_path, *keys = sys.argv[1:]
    with open(ps2_path, encoding="utf-8") as f:
        ps2 = [json.loads(line) for line in f]
    with open(pc_path, encoding="utf-8") as f:
        pc = [json.loads(line) for line in f]
    demo_idx = 0
    for r in ps2:
        r["demo_idx"] = demo_idx if r["file"] == "DEMO.DAT" else None
        demo_idx += r["file"] == "DEMO.DAT"
    for k in keys:
        for i, r in enumerate(ps2):
            if k in r["text"]:
                print(f"PS2 {k!r}: id={i} {r['file']} off={r['offset']:#x} rec_len={r['rec_len']} "
                      f"start={r['start']}")
        print(f"PC  {k!r}:", [(p["file"], p["idx"]) for p in pc if k in p["en"]])


if __name__ == "__main__":
    main()
