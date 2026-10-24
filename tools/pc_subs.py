"""Extract English (original) and Russian (translation) lang-1 subtitles from PC .sdt files.
Usage: pc_subs.py PC_MGS3_DIR RUS_DIR OUT.jsonl
Each line: {"kind", "file", "idx", "start", "end", "en", "ru"}
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from subrec import parse  # noqa: E402

KINDS = (("demo", r"us\demo\_bp"), ("vox", r"us\vox\_bp"), ("movie", r"us\movie\_bp"))


def lang1(path):
    with open(path, "rb") as f:
        data = f.read()
    return [(s, e, t.decode("utf-8", "replace"))
            for _, s, e, _, _, t in parse(data, langs=(1,), padded=False)]


def main():
    pc_root, ru_root, out_path = sys.argv[1:4]
    stats = {}
    with open(out_path, "w", encoding="utf-8") as out:
        for kind, rel in KINDS:
            st = stats.setdefault(kind, {"files": 0, "lines": 0, "ru": 0, "no_ru_file": 0, "mismatch": []})
            for fn in sorted(os.listdir(os.path.join(pc_root, rel))):
                en = lang1(os.path.join(pc_root, rel, fn))
                if not en:
                    continue
                st["files"] += 1
                ru_path = os.path.join(ru_root, rel, fn)
                ru = lang1(ru_path) if os.path.exists(ru_path) else None
                if ru is None:
                    st["no_ru_file"] += 1
                elif len(ru) != len(en) or any(a[:2] != b[:2] for a, b in zip(en, ru)):
                    st["mismatch"].append(fn)
                    ru = None
                for i, (s, e, t) in enumerate(en):
                    r = ru[i][2] if ru else None
                    st["lines"] += 1
                    st["ru"] += r is not None
                    out.write(json.dumps({"kind": kind, "file": fn, "idx": i, "start": s, "end": e,
                                          "en": t, "ru": r}, ensure_ascii=False) + "\n")
    for kind, st in stats.items():
        mm = st.pop("mismatch")
        print(kind, st, "timing/count mismatch files:", len(mm), mm[:10])


if __name__ == "__main__":
    main()
