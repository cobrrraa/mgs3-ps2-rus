"""Shorten and re-wrap the resident script strings (r_sna*: R2/L2 weapon and item windows).

The resident GCX must keep its original size (the game loads only that much, an appended string
reads garbage), and the item window shows 5 lines, wrapping a longer line in the middle of a word.
So for every r_sna string: join the body into one paragraph, apply the phrase rules below, take the
manual text from SHORT_MANUAL if there is one, and wrap to WIDTH pixels; then check line count and
the byte budget of the whole string area.

Usage: gcx_short.py FONT.raw PS2_RSNA_GCX RU.json MANUAL.json OUT.json
Writes {english: russian} overrides for gcx_apply (applied on top of RU.json) and OUT_todo.json with
the strings that still do not fit (MANUAL.json is {english: russian} with explicit line breaks).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from encoding_ru import encode  # noqa: E402
from gcx_resident import Widths, strings  # noqa: E402

WIDTH = 366      # measured: lines up to 370 px stay whole in the game, 374 px already wrap
MAX_LINES = 5

# (pattern on the joined paragraph, replacement)
RULES = [
    (r"Нажмите \{83\}\{04\}, чтобы замахнуться и отпустите, чтобы бросить\. "
     r"Чем сильнее будет нажатие, тем дальше (будет )?бросок\.",
     "Зажмите {83}{04} и отпустите, чтобы бросить. Дальность зависит от силы нажатия."),
    (r"Зажмите \{83\}\{04\}, чтобы взять на изготовку и отпустите, чтобы выстрелить\.",
     "Зажмите {83}{04} - изготовка, отпустите - выстрел."),
    (r"Слегка нажмите \{83\}\{04\}, чтобы взять на изготовку; нажмите сильнее, чтобы открыть огонь\.",
     "Слегка нажмите {83}{04} - изготовка, сильнее - огонь."),
    (r"Нажмите L1, чтобы использовать оптический прицел\.", "L1 - оптический прицел."),
    (r"Нажмите \{83\}\{03\}, чтобы выбрать кратность\.", "{83}{03} - кратность."),
    (r"Нажмите \{83\}\{03\} на этом экране, чтобы переключить режим огня\.",
     "{83}{03} в этом окне - режим огня."),
    (r"Нажмите (\{8C\}\{01\}|\{83\}\{02\}) (?:на этом экране|в этом окне), чтобы (принять|нанести)\.",
     lambda m: f"{m.group(2).capitalize()}: {m.group(1)} в этом окне."),
    (r"Пилюля, разработанная в ЦРУ для шпионов\.", "Шпионская пилюля ЦРУ."),
    (r"Расходует заряд батареи(?: когда включён)?\.", "Расходует батарею."),
    (r"Экипируйте, чтобы залезть внутрь\.", "Наденьте, чтобы спрятаться."),
    (r"Экипируйте, чтобы использовать\.", "Работает, когда выбран."),
]


def page_codes_ok(b):
    """The game moves glyph-page codes walking the old way (every byte >= 0x80 or 0x1F starts a
    pair, see encoding_ru.MOVED): every real 8C-8F code must start a pair in that walk too, and
    no other byte starting a pair may look like one."""
    real, i = set(), 0
    while i < len(b):
        if 0x80 <= b[i] < 0x90:
            real.add(i)
            i += 2
        else:
            i += 1
    old, i = set(), 0
    while i < len(b):
        if b[i] >= 0x80 or b[i] == 0x1F:
            old.add(i)
            i += 2
        else:
            i += 1
    moved = {p for p in old if (b[p] & 0x9F) in range(0x8C, 0x90)}
    return moved == {p for p in real if b[p] in range(0x8C, 0x90)}


def paragraph(text):
    """'Title:\\nbody...' -> (title or None, body joined into one line, trailing newline kept?)"""
    lines = text.rstrip("\n").split("\n")
    title = None
    if lines[0].endswith(":"):
        title, lines = lines[0], lines[1:]
    body = re.sub(r"\s+", " ", " ".join(lines)).strip()
    return title, body


def wrap(W, words, width):
    out, cur = [], ""
    for w in words:
        cand = f"{cur} {w}" if cur else w
        if cur and W.line(encode(cand, bar_newline=False)) > width:
            out.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        out.append(cur)
    return out


def shorten(W, en, text, manual):
    text = manual.get(en, text)  # a manual text is wrapped the same way
    title, body = paragraph(text)
    for pat, rep in RULES:
        body = re.sub(pat, rep, body)
    lines = ([title] if title else []) + wrap(W, body.split(" "), WIDTH)
    return "\n".join(lines) + "\n"


def main():
    font, gcx_path, ru_path, manual_path, out_path = sys.argv[1:6]
    ru = json.load(open(ru_path, encoding="utf-8"))
    manual = {}
    if os.path.exists(manual_path):
        manual = {k: v for k, v in json.load(open(manual_path, encoding="utf-8")).items()
                  if not k.startswith("_")}
    W = Widths(font)
    d = open(gcx_path, "rb").read()
    area, chs = strings(d)
    out, todo, budget, used, bad = {}, {}, 0, 0, 0
    for ch in chs:
        budget += ch[-1][1] + 1 - ch[0][0]
        for off, end in ch:
            raw = d[area + off:area + end]
            en = raw.decode("latin-1")
            if en not in ru:
                used += len(raw) + 1
                continue
            # only multi-line window texts are re-flowed; short labels (codec names) stay
            new = shorten(W, en, ru[en], manual) if "\n" in ru[en] else manual.get(en, ru[en])
            if new != ru[en]:
                out[en] = new
            enc = encode(new, bar_newline=False)
            used += len(enc) + 1
            widths = W.lines(enc)
            if len(widths) > MAX_LINES or any(w > WIDTH for w in widths) or not page_codes_ok(enc):
                bad += 1
                todo[en] = new
                print(f"DOES NOT FIT {widths}: {en!r}")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    with open(out_path.replace(".json", "_todo.json"), "w", encoding="utf-8") as f:
        json.dump(todo, f, ensure_ascii=False, indent=1)
    print(f"{len(out)} overrides, {bad} do not fit; bytes {used} / {budget} "
          f"({'OK' if used <= budget else 'OVER by %d' % (used - budget)})")


if __name__ == "__main__":
    main()
