"""Count high bytes (0x80-0xBF) inside cp1251 text runs of the PC Russian codec and GCX files,
i.e. which punctuation beyond plain letters the translation relies on.
Usage: charset_rus.py RUS_DIR
"""
import collections
import os
import re
import sys

# a text run: printable ASCII / cp1251 high bytes, at least 6 bytes, with at least 2 Cyrillic letters
RUN = re.compile(rb"[\x20-\x7e\x80-\xff]{6,}")


def main():
    root = sys.argv[1]
    counts = collections.Counter()
    examples = {}
    for sub in (r"fr\codec\_bp", r"assets\gcx\fr\_bp"):
        for dp, _, fns in os.walk(os.path.join(root, sub)):
            for fn in fns:
                data = open(os.path.join(dp, fn), "rb").read()
                for m in RUN.finditer(data):
                    run = m.group()
                    # real text: NUL/newline-terminated, mostly letters and spaces (audio data is not)
                    end = data[m.end():m.end() + 1]
                    letters = sum(b >= 0xC0 or 0x41 <= (b | 0x20) <= 0x7A or b == 0x20 for b in run)
                    if end not in (b"\x00", b"\n") or sum(b >= 0xC0 for b in run) < 2 \
                            or letters < 0.8 * len(run):
                        continue
                    for b in run:
                        if 0x80 <= b < 0xC0:
                            counts[b] += 1
                            examples.setdefault(b, run[:60].decode("cp1251", "replace"))
    for b, n in counts.most_common():
        ch = bytes([b]).decode("cp1251", "replace")
        print(f"{b:02X} {ch!r:6} x{n:<6} e.g. {examples[b]!r}".encode("ascii", "backslashreplace").decode())


if __name__ == "__main__":
    main()
