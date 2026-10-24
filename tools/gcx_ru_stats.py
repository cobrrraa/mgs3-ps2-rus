"""Rough statistics of Russian text in the PC russifier GCX files vs the original (fr slot) files:
how many NUL/length-delimited text runs contain Cyrillic, and samples.
Usage: gcx_ru_stats.py RUS_GCX_DIR ORIG_GCX_DIR OUT.txt
"""
import os
import re
import sys

RUN = re.compile(rb"[\x20-\x7e\xa8\xb8\xc0-\xff]{3,}")


def runs(data):
    return [m.group() for m in RUN.finditer(data)]


def main():
    ru_dir, orig_dir, out_path = sys.argv[1:4]
    total_ru, files_ru = 0, 0
    samples = []
    for fn in sorted(os.listdir(ru_dir)):
        ru = open(os.path.join(ru_dir, fn), "rb").read()
        cyr = [r for r in runs(ru) if sum(b >= 0xC0 for b in r) >= 3]
        if cyr:
            files_ru += 1
            total_ru += len(cyr)
            samples.append((fn, cyr[:6]))
    with open(out_path, "w", encoding="utf-8") as out:
        out.write(f"files with Russian: {files_ru}, Cyrillic runs: {total_ru}\n")
        for fn, cy in samples:
            out.write(f"== {fn}\n")
            for r in cy:
                out.write("   " + r.decode("cp1251", "replace") + "\n")
    print(f"files with Russian: {files_ru} of {len(os.listdir(ru_dir))}, Cyrillic runs: {total_ru}")


if __name__ == "__main__":
    main()
