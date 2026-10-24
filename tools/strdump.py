"""Dump text runs from files into a UTF-8 report.
Usage: strdump.py OUT FROM TO TAG:ENC:PATH [TAG:ENC:PATH ...]
"""
import re
import sys

RUN = re.compile(rb"[\x20-\x7e\x80-\xff]{12,}")


def main():
    out_path, lo, hi, *specs = sys.argv[1:]
    lo, hi = int(lo), int(hi)
    with open(out_path, "w", encoding="utf-8") as out:
        for spec in specs:
            tag, enc, path = spec.split(":", 2)
            data = open(path, "rb").read()
            runs = list(RUN.finditer(data))
            out.write(f"=== {tag} size={len(data)} runs={len(runs)}\n")
            for m in runs[lo:hi]:
                out.write(f"{m.start():#x} {m.group()[:160].decode(enc, 'replace')}\n")


if __name__ == "__main__":
    main()
