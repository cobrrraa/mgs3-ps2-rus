"""Re-wrap Russian subtitles whose line is wider than the subtitle texture allows.

The game cuts a line at 512px (verified: "...войну." lost "ну." past 512px); LIMIT keeps a margin.
A too-wide subtitle is re-flowed into at most 2 lines, choosing the break that minimises the wider
line. Result: OUT.json {id: text}, applied after the other override files.

Usage: autowrap.py FONT_RU.raw TABLE.csv OUT.json OVERRIDES.json [...]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_font as M  # noqa: E402
from encoding_ru import encode  # noqa: E402
from apply_subs import load_texts  # noqa: E402

LIMIT = 504
FILES = ("DEMO.DAT", "MOVIE.DAT", "VOX.DAT")


def main():
    font, table, out_path, *overrides = sys.argv[1:]
    glyphs = M.load_glyphs(font)[2]

    def width(s):
        return sum(glyphs[b].width for b in encode(s))

    rows = load_texts(table, overrides)
    wraps, failed = {}, []
    for i, r in sorted(rows.items()):
        if r["ps2_file"] not in FILES or not r["ru"]:
            continue
        lines = r["ru"].split("|")
        if max(width(l) for l in lines) <= LIMIT:
            continue
        words = " ".join(lines).split(" ")
        best = None
        for k in range(1, len(words)):
            a, b = " ".join(words[:k]), " ".join(words[k:])
            w = max(width(a), width(b))
            if best is None or w < best[0]:
                best = (w, f"{a}|{b}")
        if best and best[0] <= LIMIT:
            wraps[str(i)] = best[1]
        else:
            failed.append((i, r["ru"]))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(wraps, f, ensure_ascii=False, indent=1)
    print(f"re-wrapped {len(wraps)} subtitles -> {out_path}; cannot fit in 2 lines: {len(failed)}")
    for i, t in failed:
        print(f"  {i}: {t}".encode("ascii", "backslashreplace").decode())


if __name__ == "__main__":
    main()
