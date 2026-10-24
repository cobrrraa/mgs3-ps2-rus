"""Replace PC button icons in the Russian codec text with the PS2 button names.

The PC russifier marks controller buttons with icons: private-use characters (U+E080...), stored as
UTF-8 (EE 82 xx) inside cp1251 text, so they also come out as "о‚" plus a stray character. The PS2
English text names the buttons in words ("press the Action Button", "the START button", "the left
analog stick"), in the same order
as the icons, so each icon becomes the Russian name of the English button at the same position.
Names go in quotes («Действие») so they read in any grammatical case; START/L1/... stay as they are.

Usage: codec_buttons.py CODEC_DICT.json OUT.json
Writes {english: russian} overrides for codec_build; prints the texts it could not resolve.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from encoding_ru import CHAR_TO_CODE  # noqa: E402

NAMES = {
    "action": "Действие", "weapon": "Оружие", "enter": "Ввод", "crawl": "Ползти", "aim": "Прицел",
    "cqc": "CQC", "punch": "Удар", "weapon window": "Окно оружия", "item window": "Окно предметов",
    "item": "Предмет", "viewer": "Просмотр", "first person view": "Вид от 1-го лица",
    "left step": "Шаг влево", "right step": "Шаг вправо", "camera": "Камера",
    "left analog stick": "левый стик", "right analog stick": "правый стик",
    "directional buttons": "крестовина",
}
PLAIN = {"start", "select", "l1", "l2", "r1", "r2", "l3", "r3"}
EN_BUTTON = re.compile(r"(left analog stick|right analog stick|directional buttons|"
                       r"(?:[A-Z0-9]{2,}|[A-Z][a-z]+(?: [A-Z][a-z]+)*) [Bb]utton)")


def icon_spans(text):
    """[(start, end)] of the icons in a Russian text: a PUA char, or its UTF-8 bytes EE 82 xx read
    as cp1251 ("о‚" + one more char), or a stray pair from 82 xx."""
    spans, i = [], 0
    while i < len(text):
        c = text[i]
        if "\ue000" <= c <= "\uf8ff":
            spans.append((i, i + 1))
        elif text[i:i + 2] == "\u043e\u201a" and i + 2 < len(text):
            spans.append((i, i + 3))
            i += 2
        elif c >= "\x80" and c not in CHAR_TO_CODE:
            spans.append((i, i + 2))
            i += 1
        i += 1
    return spans


def russian_name(en_name):
    key = re.sub(r"(?i)^the |\s*button$", "", en_name).lower()
    if key in PLAIN:
        return key.upper(), True
    if key in NAMES:
        return NAMES[key], key.endswith(("stick", "buttons"))
    return None, False


def fix(en, ru):
    spans = icon_spans(ru)
    if not spans:
        return ru
    names = EN_BUTTON.findall(en.replace("\n", " "))
    if len(names) != len(spans):
        return None
    out, pos = [], 0
    for (a, b), en_name in zip(spans, names):
        name, bare = russian_name(en_name)
        if name is None:
            return None
        before = ru[max(0, a - 12):a].lower()
        label = name if bare or name.isupper() else f"«{name}»"
        if not bare and not name.isupper() and "кнопк" not in before:
            label = f"кнопку {label}" if before.rstrip().endswith(("нажми", "нажмите", "нажать")) else label
        out += [ru[pos:a].rstrip(" ") + " " if a and ru[a - 1] == " " else ru[pos:a], label]
        pos = b
    out.append(ru[pos:])
    return re.sub(r" +([.,!?])", r"\1", "".join(out))


def main():
    dict_path, out_path = sys.argv[1:3]
    ru = json.load(open(dict_path, encoding="utf-8"))
    out, failed = {}, []
    for en, text in ru.items():
        if not icon_spans(text):
            continue
        new = fix(en, text)
        if new is None:
            failed.append((en, text))
        else:
            out[en] = new
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    with open(out_path.replace(".json", "_todo.json"), "w", encoding="utf-8") as f:
        json.dump(dict(failed), f, ensure_ascii=False, indent=1)
    print(f"buttons named in {len(out)} codec texts, unresolved {len(failed)} -> {out_path}")


if __name__ == "__main__":
    main()
