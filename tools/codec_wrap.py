"""Re-wrap Russian codec lines that are wider than the codec text window.

The codec window wraps a too-wide line by itself in the middle of a word ("территори|и,"): a line
of 563 px stayed whole in the game, one of 584 px did not, so LIMIT is 560 px. A Russian codec
text with a wider line is joined into one paragraph and wrapped by words again; up to MAX_LINES
lines fit the window (4 Russian lines were seen to fit; English uses up to 3). Personal data
pages and other texts of more than 3 English lines are lists shown elsewhere and keep their lines.

Usage: codec_wrap.py FONT.raw CODEC_DICT.json [MORE.json ...] OUT.json   (later dictionaries override)
Writes {english: re-wrapped russian} overrides for codec_build (applied after the dictionary).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from encoding_ru import encode  # noqa: E402
from gcx_resident import Widths  # noqa: E402
from gcx_short import wrap  # noqa: E402

LIMIT = 560
MAX_LINES = 4


def main():
    font, *dict_paths, out_path = sys.argv[1:]
    W = Widths(font)
    ru = {}
    for path in dict_paths:
        ru.update(json.load(open(path, encoding="utf-8")))
    out, too_long = {}, []
    for en, text in ru.items():
        if en.startswith("PERSONAL DATA") or en.rstrip("\n").count("\n") >= 3:
            continue
        try:
            enc = encode(text, bar_newline=False)
        except ValueError:
            continue
        if not W.lines(enc) or max(W.lines(enc)) <= LIMIT:
            continue
        lines = wrap(W, " ".join(text.split()).split(" "), LIMIT)
        new = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
        out[en] = new
        if len(lines) > MAX_LINES:
            too_long.append(new)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"re-wrapped {len(out)} codec texts -> {out_path}; more than {MAX_LINES} lines: {len(too_long)}")


if __name__ == "__main__":
    main()
