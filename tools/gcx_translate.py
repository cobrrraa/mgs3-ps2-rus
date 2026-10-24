"""Build Russian texts for the PS2 GCX strings.

Sources, in order:
  1. exact English match with a PC line translated by the russifier (gcx_dict.json);
  2. a PC line that differs only by button icons / accents / a PS2-only prefix (fuzzy match);
  3. manual translations (gcx_manual.json, {english: russian}).
PC button icons (private-use U+E080.., U+3000) are replaced by the PS2 codes found at the same
position in the PS2 English line; PS2 two-byte codes are written as {xx}{yy} (see encoding_ru).
Memory-card messages and song titles are left in English on purpose.

Usage: gcx_translate.py PC_GCX_DIR RUS_GCX_DIR PS2_STRINGS.json DICT.json MANUAL.json OUT.json TODO.txt
OUT: {ps2 english (latin-1 str): russian (encode() syntax)}
"""
import difflib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gcx_pc_align import runs, decode_ru  # noqa: E402
from encoding_ru import encode  # noqa: E402

# left in English on purpose: memory card, network / DNAS / camouflage download (dead online
# service), song titles, brand names
SKIP = re.compile(r"memory\s+card|Memory\s+card|MEMORY CARD|DNAS|Network|network|Unique ID Error|"
                  r"Camouflage (?:data|download|list|save|information)|Download this Camouflage|"
                  r"Downloading Camouflage|Select Camouflage|Discard downloaded|Cancel Camouflage|"
                  r"Connect with these settings|Connecting to|Disconnect|communications device|"
                  r"Internet service provider|SCEA|^[A-Z' ]+ / [A-Z.' ]+$|^Calorie Mate\n$|^EZ GUN$")
PS2_TOKEN = re.compile(r"[\x80-\x8f].|\b[LR][12]\b", re.S)
PC_ICON = re.compile(r"[-　]")


def raw(tok):
    """PS2 token (str of latin-1 chars) -> encode() syntax."""
    if len(tok) == 2 and "\x80" <= tok[0] <= "\x8f":
        return "".join(f"{{{ord(c):02X}}}" for c in tok)
    return tok


def letters(s):
    return re.sub(r"[^a-z]", "", s.lower())


def accent_free(s):
    """PS2 writes accents as 1F xx escapes; PC as UTF-8. Compare without them."""
    s = re.sub(r"\x1f.", "e", s)
    return s.replace("é", "e").replace("è", "e").replace("ê", "e").replace("û", "u").replace("ü", "u")


def convert(ps2_en, pc_en, ru):
    """Map PC icons in `ru` to PS2 codes; None if it cannot be done safely."""
    s_tok = PS2_TOKEN.findall(ps2_en)
    p_tok = PC_ICON.findall(pc_en)
    mapping = {}
    if len(p_tok) == len(s_tok):
        for p, s in zip(p_tok, s_tok):
            if mapping.get(p, s) != s:
                return None
            mapping[p] = s
    out = []
    for ch in ru:
        if PC_ICON.fullmatch(ch):
            if ch in mapping:
                out.append(raw(mapping[ch]))
            elif len(set(s_tok)) == 1 and len(set(p_tok)) == 1:
                out.append(raw(s_tok[0]))
            elif ch == "　":
                out.append("{83}{01}")
            else:
                return None
        else:
            out.append(ch)
    text = "".join(out)
    # PS2-only leading codes (e.g. "\x82\x0b\x82\x15\n" before a name)
    lead = re.match(r"((?:[\x80-\x8f].)+\n?)", ps2_en, re.S)
    if lead and not PC_ICON.match(pc_en):
        text = raw_all(lead.group(1)) + text
    return text


def raw_all(s):
    return "".join(raw(t) if len(t) == 2 else t for t in re.findall(r"[\x80-\x8f].|.", s, re.S))


def main():
    pc_dir, ru_dir, ps2_json, dict_json, manual_json, out_path, todo_path = sys.argv[1:8]
    with open(ps2_json, encoding="utf-8") as f:
        table = json.load(f)["table"]
    with open(dict_json, encoding="utf-8") as f:
        exact = json.load(f)
    manual = {}
    if os.path.exists(manual_json):
        with open(manual_json, encoding="utf-8") as f:
            manual = {k: v for k, v in json.load(f).items() if not k.startswith("_")}

    pairs = {}
    for fn in sorted(os.listdir(ru_dir)):
        pc_path = os.path.join(pc_dir, fn)
        if not os.path.exists(pc_path):
            continue
        a, b = runs(open(pc_path, "rb").read()), runs(open(os.path.join(ru_dir, fn), "rb").read())
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if tag == "replace" and i2 - i1 == j2 - j1:
                for x, y in zip(a[i1:i2], b[j1:j2]):
                    if any(c >= 0xC0 for c in y) and re.search(rb"[A-Za-z]{3}", x):
                        pairs.setdefault(decode_ru(x), decode_ru(y))
    by_letters = {}
    for en in pairs:
        by_letters.setdefault(letters(accent_free(PC_ICON.sub("", en))), en)

    out, todo, stats = {}, [], {"exact": 0, "fuzzy": 0, "manual": 0, "skip": 0, "todo": 0, "bad": 0}
    for en in table:
        if len(re.findall(r"[A-Za-z]", en)) < 3:
            continue
        if SKIP.search(en):
            stats["skip"] += 1
            continue
        if en in manual:
            ru, how = manual[en], "manual"
        elif en in exact:
            ru, how = convert(en, en, exact[en]), "exact"
        else:
            key = letters(accent_free(PS2_TOKEN.sub("", en)))
            pc_en = by_letters.get(key)
            if not pc_en:
                key2 = letters(accent_free(PS2_TOKEN.sub("", re.sub(r"^(?:[\x80-\x8f].)+\n?", "", en, flags=re.S))))
                pc_en = by_letters.get(key2)
            ru, how = (convert(en, pc_en, pairs[pc_en]), "fuzzy") if pc_en else (None, "todo")
        if ru is not None:
            ru = ru.replace("\r", "")
            try:
                encode(ru)
            except ValueError:
                ru, how = None, "bad"
        if ru is None:
            stats["todo" if how == "todo" else "bad"] += 1
            todo.append(en)
            continue
        stats[how] += 1
        out[en] = ru
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    with open(todo_path, "w", encoding="utf-8") as f:
        json.dump(sorted(todo, key=lambda s: (-len(table[s]), s)), f, ensure_ascii=False, indent=1)
    print(stats)


if __name__ == "__main__":
    main()
