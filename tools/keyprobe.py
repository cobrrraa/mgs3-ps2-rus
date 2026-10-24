"""Look for runs of zero plaintext in data encrypted with the MGS3 LCG XOR stream
(key[i+1] = key[i] * 0x02E90EDD + keyB). Where plaintext is zero, ciphertext words
are the key stream itself, so three consecutive words agree on one keyB.
Usage: keyprobe.py FILE [limit]
"""
import struct
import sys
from collections import Counter

KEY = 0x02E90EDD
M = 0xFFFFFFFF


def main():
    data = open(sys.argv[1], "rb").read()
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    words = struct.unpack_from(f"<{len(data) // 4}I", data)
    keyBs = Counter()
    hits = []
    for i in range(len(words) - 3):
        w0, w1, w2, w3 = words[i:i + 4]
        if w0 == w1:
            continue
        kb = (w1 - w0 * KEY) & M
        if (w1 * KEY + kb) & M == w2 and (w2 * KEY + kb) & M == w3:
            keyBs[kb] += 1
            if len(hits) < limit:
                hits.append((i * 4, kb, w0))
    print("distinct keyB:", len(keyBs))
    for kb, n in keyBs.most_common(15):
        print(f"  keyB={kb:#010x} runs={n}")
    for off, kb, w0 in hits:
        print(f"  off={off:#x} keyB={kb:#010x} key={w0:#010x}")


if __name__ == "__main__":
    main()
