"""Try candidate LCG keys on an encrypted string region of CODEC.DAT and score printability."""
import struct
import sys

KEY = 0x02E90EDD
M = 0xFFFFFFFF


def xor_stream(key_a, key_b, buf, byte_mode=False):
    out = bytearray(buf)
    if byte_mode:
        for i in range(len(out)):
            out[i] ^= key_a & 0xFF
            key_a = (key_a * KEY + key_b) & M
        return bytes(out)
    n = len(buf) // 4
    for i in range(n):
        w = struct.unpack_from("<I", out, i * 4)[0] ^ key_a
        struct.pack_into("<I", out, i * 4, w)
        key_a = (key_a * KEY + key_b) & M
    return bytes(out)


def score(b):
    return sum(1 for c in b if 32 <= c < 127 or c in (0, 10)) / max(1, len(b))


def main():
    data = open(sys.argv[1], "rb").read()
    off, ln = int(sys.argv[2], 0), int(sys.argv[3], 0)
    buf = data[off:off + ln]
    ts = [0x4165BABE, 0x41822C07, 0x80000000]
    cands = []
    for a in ts:
        for b in (a ^ 0xF0F0, a, 0, (a << 7) + a):
            cands.append((a, b & M))
    for a, b in cands:
        for bm in (False, True):
            dec = xor_stream(a, b, buf, bm)
            print(f"A={a:#010x} B={b:#010x} byte={bm} score={score(dec):.2f} {dec[:40]!r}")


if __name__ == "__main__":
    main()
