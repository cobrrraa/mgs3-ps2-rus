"""Show the table neighbours (previous / next string) of untranslated GCX strings, with their
Russian if already translated, so multi-page tutorial texts can be translated as a whole.
Usage: gcx_context.py PS2_GCX_DIR TODO.json RU.json OUT.txt
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gcx as G  # noqa: E402


def main():
    gdir, todo_path, ru_path, out_path = sys.argv[1:5]
    todo = json.load(open(todo_path, encoding="utf-8"))
    ru = json.load(open(ru_path, encoding="utf-8"))
    want = set(todo)
    ctx = {}
    for fn in sorted(os.listdir(gdir)):
        if not fn.endswith(".gcx"):
            continue
        s = [t.decode("latin-1") for _, _, t in G.strings(open(os.path.join(gdir, fn), "rb").read())]
        for k, t in enumerate(s):
            if t in want and t not in ctx:
                ctx[t] = (s[k - 1] if k else None, s[k + 1] if k + 1 < len(s) else None)
    with open(out_path, "w", encoding="utf-8") as out:
        for t in todo:
            prev, nxt = ctx.get(t, (None, None))
            out.write(f"=== {t!r}\n   prev: {prev!r}\n        -> {ru.get(prev)!r}\n"
                      f"   next: {nxt!r}\n        -> {ru.get(nxt)!r}\n")
    print("written", out_path)


if __name__ == "__main__":
    main()
