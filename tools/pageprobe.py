"""Try Shagohod-style page decryption + zlib at candidate offsets.
Page format: first u16 = key salt; buffer is XOR-decrypted, then bytes 0..1 become 78 9C.
Usage: pageprobe.py FILE START END STEP
"""
import struct
import sys
import zlib

KEY = 0x02E90EDD
M = 0xFFFFFFFF


def decode_buffer(key_a, key_b, buf):
    n = len(buf) // 4
    words = list(struct.unpack_from(f"<{n}I", buf))
    for i in range(n):
        nxt = (key_a * KEY + key_b) & M
        words[i] ^= key_a
        key_a = nxt
    return struct.pack(f"<{n}I", *words) + buf[n * 4:]


def decode_page(buf):
    salt = struct.unpack_from("<H", buf)[0] ^ 0x9385
    key_a = ((salt ^ 0x6576) << 16 | salt) & M
    key_b = (salt * 0x0116) & M
    out = bytearray(decode_buffer(key_a, key_b, buf))
    out[0:2] = b"\x78\x9c"
    return bytes(out)


def main():
    data = open(sys.argv[1], "rb").read()
    start, end, step = (int(x, 0) for x in sys.argv[2:5])
    found = 0
    for off in range(start, min(end, len(data) - 64), step):
        chunk = decode_page(data[off:off + 0x10000])
        d = zlib.decompressobj()
        try:
            out = d.decompress(chunk, 4096)
        except zlib.error:
            continue
        if len(out) >= 16:
            found += 1
            print(f"{off:#x}: ok, first bytes {out[:48]!r}")
            if found > 20:
                break


if __name__ == "__main__":
    main()
