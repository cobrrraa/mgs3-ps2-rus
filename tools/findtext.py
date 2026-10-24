"""Find a byte pattern in every file under a directory.
Usage: findtext.py DIR PATTERN [CONTEXT]
"""
import os
import sys


def main():
    root, pat = sys.argv[1], sys.argv[2].encode("utf-8")
    ctx = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    for dp, _, fns in os.walk(root):
        for fn in fns:
            p = os.path.join(dp, fn)
            with open(p, "rb") as f:
                d = f.read()
            i = d.find(pat)
            while i != -1:
                print(f"{p} @ {i:#x}")
                if ctx:
                    print("   ", d[max(0, i - ctx):i + len(pat) + ctx])
                i = d.find(pat, i + 1)


if __name__ == "__main__":
    main()
