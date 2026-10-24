"""Mine English -> Russian pairs from the PC GCX files by aligning text runs.

PC GCX keep many strings inline in the bytecode (not in the string table), so the original
(fr slot) and the russified file are both cut into NUL-terminated text runs and aligned with
difflib; a replaced run whose original is one of the PS2 GCX strings gives a pair.

Usage: gcx_pc_align.py PC_GCX_DIR RUS_GCX_DIR PS2_STRINGS.json OUT.json REPORT.txt
"""
import collections
import difflib
import json
import os
import re
import sys

RUN = re.compile(rb"[^\x00]{1,600}(?=\x00)")


def runs(data):
    return [m.group() for m in RUN.finditer(data)]


def decode_ru(b):
    """The russifier mixes UTF-8 and cp1251 strings in GCX files."""
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("cp1251", "replace")


def main():
    pc_dir, ru_dir, ps2_json, out_path, report_path = sys.argv[1:6]
    with open(ps2_json, encoding="utf-8") as f:
        ps2 = set(json.load(f)["table"])
    ps2_bytes = {s.encode("latin-1") for s in ps2}
    pairs = collections.defaultdict(collections.Counter)
    for fn in sorted(os.listdir(ru_dir)):
        pc_path = os.path.join(pc_dir, fn)
        if not os.path.exists(pc_path):
            continue
        a = runs(open(pc_path, "rb").read())
        b = runs(open(os.path.join(ru_dir, fn), "rb").read())
        sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != "replace" or (i2 - i1) != (j2 - j1):
                continue
            for x, y in zip(a[i1:i2], b[j1:j2]):
                if x in ps2_bytes and any(c >= 0xC0 for c in y):
                    pairs[x.decode("latin-1")][decode_ru(y)] += 1
    result = {en: c.most_common(1)[0][0] for en, c in pairs.items()}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    short = [s for s in ps2 if s not in result]
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"PS2 strings {len(ps2)}, with Russian from PC: {len(result)}, missing {len(short)}\n\n")
        for en, r in sorted(result.items())[:80]:
            f.write(f"{en!r} -> {r!r}\n")
        f.write("\n--- missing (sample)\n")
        for s in sorted(short, key=len)[:120]:
            f.write(f"{s!r}\n")
    print(f"PS2 strings {len(ps2)}, with Russian from PC: {len(result)}, missing {len(short)}")


if __name__ == "__main__":
    main()
