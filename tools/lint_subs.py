"""Check Russian subtitle lines for layout problems: pixel width per line, number of lines,
empty lines, stray spaces.
Usage: lint_subs.py FONT_RU.raw TABLE.csv DAT MAX_PX OVERRIDES.json [...]
   e.g. lint_subs.py work/font/383c45_ru.raw work/subs/subs_ps2_ru.csv MOVIE.DAT 600 a.json b.json
The screen is ~640px wide; a 502px line was verified on screen.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_font as M  # noqa: E402
from encoding_ru import encode  # noqa: E402
from apply_subs import load_texts  # noqa: E402


def main():
    font, table, dat, max_px, *overrides = sys.argv[1:]
    max_px = int(max_px)
    glyphs = M.load_glyphs(font)[2]
    rows = [r for r in load_texts(table, overrides).values() if r["ps2_file"] == dat]

    def width(line):
        return sum(glyphs[b].width for b in encode(line))

    problems = 0
    for r in rows:
        ru = r["ru"]
        lines = ru.split("|")
        issues = []
        if not ru:
            issues.append("no translation")
        else:
            w = max(width(l) for l in lines)
            if w > max_px:
                issues.append(f"too wide {w}px")
            if len(lines) > 2:
                issues.append(f"{len(lines)} lines")
            if any(not l for l in lines):
                issues.append("empty line")
            if "  " in ru:
                issues.append("double space")
        if issues:
            problems += 1
            print(f"{r['id']}: {', '.join(issues)} | {ru}".encode("ascii", "backslashreplace").decode())
    print(f"{dat}: {len(rows)} lines, with issues: {problems}")


if __name__ == "__main__":
    main()
