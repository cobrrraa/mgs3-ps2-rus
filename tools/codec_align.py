"""Mine English -> Russian codec pairs from the PC codec scripts (fr/codec/_bp/*.sdt).

A PC codec file holds the English lines, then the same lines in French. The russifier replaced the
English runs with Russian (cp1251) and kept the French ones, with their accented letters mangled.
Both files are cut into NUL-terminated runs; when the run counts match (almost always) runs pair up
by position. Otherwise (a run added or dropped somewhere) runs pair by position from the start and
from the end for as long as the pairs are compatible (English vs Russian, or the same French run),
and the rest in the middle is aligned by difflib on keys (French/English runs: their ASCII letters,
Russian runs: a unique key).

PS2 lines without an exact PC twin (the PC text was edited for Subsistence / Master Collection)
take the Russian of the most similar PC line: ratio >= AUTO goes into OUT.json, REVIEW..AUTO into
OUT_fuzzy.json for a manual look.

Usage: codec_align.py PC_CODEC_DIR RUS_CODEC_DIR PS2_STRINGS.json OUT.json REPORT.txt
"""
import collections
import difflib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gcx_pc_align import runs, decode_ru  # noqa: E402

AUTO, REVIEW = 0.9, 0.75
CYR = re.compile(rb"[\xc0-\xff\xa8\xb8]{2}")


def key(run):
    if CYR.search(run):
        return None  # Russian: never equal to anything
    return re.sub(rb"[^A-Za-z]", b"", run).lower() or run


def compatible(x, y):
    """Runs at the same place in the original and the russified file."""
    if x == y:
        return True
    if CYR.search(y):
        return not CYR.search(x)
    return key(x) == key(y)


def plausible(en, ru):
    """Russian text that keeps the shape of the English line. Short lines ("...", "Hmm?") appear in
    hundreds of files, so a single misaligned pair must not give them someone else's long line."""
    if any(ord(c) < 32 and c != "\n" for c in ru):
        return False
    if en.endswith("\n") != ru.endswith("\n"):
        return False
    le, lr = len(en.strip()), len(ru.strip())
    if not re.search("[A-Za-z]", en):
        return not re.search("[A-Za-zА-Яа-яЁёÀ-ÿ]", ru)
    if le <= 12 and lr > max(3 * le, 25):
        return False
    if le > 12 and not 0.35 * le <= lr <= 2.6 * le:
        return False
    return bool(re.search("[А-Яа-яЁё]", ru)) or ru.strip() == en.strip()


def main():
    pc_dir, ru_dir, ps2_json, out_path, report_path = sys.argv[1:6]
    with open(ps2_json, encoding="utf-8") as f:
        ps2 = set(json.load(f)["table"])
    ps2_bytes = {s.encode("latin-1") for s in ps2}
    pairs = collections.defaultdict(collections.Counter)
    pc_all = collections.defaultdict(collections.Counter)  # every PC English line -> Russian
    for fn in sorted(os.listdir(ru_dir)):
        pc_path = os.path.join(pc_dir, fn)
        if not os.path.exists(pc_path):
            continue
        a = runs(open(pc_path, "rb").read())
        b = runs(open(os.path.join(ru_dir, fn), "rb").read())
        if len(a) == len(b):
            blocks = [(a, b)]
        else:
            head = 0
            while head < min(len(a), len(b)) and compatible(a[head], b[head]):
                head += 1
            tail = 0
            while tail < min(len(a), len(b)) - head and compatible(a[-1 - tail], b[-1 - tail]):
                tail += 1
            blocks = [(a[:head], b[:head]), (a[len(a) - tail:], b[len(b) - tail:])]
            ma, mb = a[head:len(a) - tail], b[head:len(b) - tail]
            ka = [key(x) for x in ma]
            kb = [key(y) or ("ru", j) for j, y in enumerate(mb)]
            sm = difflib.SequenceMatcher(None, ka, kb, autojunk=False)
            blocks += [(ma[i1:i2], mb[j1:j2]) for tag, i1, i2, j1, j2 in sm.get_opcodes()
                       if tag == "replace" and (i2 - i1) == (j2 - j1)]
        for xs, ys in blocks:
            for x, y in zip(xs, ys):
                if CYR.search(y) and max(x) < 0x80:
                    en, ru = x.decode("latin-1"), decode_ru(y)
                    if plausible(en, ru):
                        (pairs if x in ps2_bytes else pc_all)[en][ru] += 1
    result = {en: c.most_common(1)[0][0] for en, c in pairs.items()}
    pc_all = {en: c.most_common(1)[0][0] for en, c in pc_all.items()}
    fuzzy = {}
    for s in ps2:
        if s in result or not re.search("[a-z]{3}", s):
            continue
        best, ratio = None, 0
        for en in pc_all:
            sm = difflib.SequenceMatcher(None, s, en, autojunk=False)
            if sm.real_quick_ratio() < max(ratio, REVIEW) or sm.quick_ratio() < max(ratio, REVIEW):
                continue
            r = sm.ratio()
            if r > ratio and r >= REVIEW:
                best, ratio = en, r
        if best is None:
            continue
        if ratio >= AUTO:
            result[s] = pc_all[best]
        else:
            fuzzy[s] = {"pc_en": best, "ru": pc_all[best], "ratio": round(ratio, 3)}
    with open(out_path.replace(".json", "_fuzzy.json"), "w", encoding="utf-8") as f:
        json.dump(fuzzy, f, ensure_ascii=False, indent=1)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    missing = sorted((s for s in ps2 if s not in result), key=len)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"PS2 strings {len(ps2)}, with Russian from PC: {len(result)}, missing {len(missing)}\n")
        conflicts = [(en, c) for en, c in pairs.items() if len(c) > 1]
        f.write(f"strings with several Russian variants: {len(conflicts)}\n\n--- missing\n")
        for s in missing:
            f.write(f"{s!r}\n")
    print(f"PS2 strings {len(ps2)}, with Russian: {len(result)}, for review {len(fuzzy)}, "
          f"missing {len(missing)}")


if __name__ == "__main__":
    main()
