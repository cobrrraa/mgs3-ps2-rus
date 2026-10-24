"""Hex-dump two versions of a file side by side, showing only differing 16-byte rows."""
import sys


def rows(data):
    for off in range(0, len(data), 16):
        yield off, data[off:off + 16]


def fmt(chunk):
    hx = " ".join(f"{b:02x}" for b in chunk).ljust(47)
    asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
    return f"{hx}  {asc}"


def main(a_path, b_path, limit=60, head=0):
    a = open(a_path, "rb").read()
    b = open(b_path, "rb").read()
    print(f"A={len(a)} B={len(b)}")
    if head:
        for off, chunk in rows(a[:head]):
            print(f"{off:08x}  {fmt(chunk)}")
        print("---")
    shown = 0
    for off in range(0, max(len(a), len(b)), 16):
        ca, cb = a[off:off + 16], b[off:off + 16]
        if ca != cb:
            print(f"{off:08x} A {fmt(ca)}")
            print(f"{off:08x} B {fmt(cb)}")
            shown += 1
            if shown >= limit:
                break


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 60,
         int(sys.argv[4]) if len(sys.argv) > 4 else 0)
