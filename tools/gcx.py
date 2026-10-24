"""MGS3 PS2 GCX (stage script) string table: decrypt / encrypt / parse.

GCX layout (PS2):
    u32 timestamp (0x4165BABE), u32 0, u32 offsets..., 0xFFFFFFFF      -- header (procedure table)
    sec2 (at header end): u32 size, u32 tab_off, u32 str_off, u32 str_end, u32 seed, ...
        offsets are relative to sec2 (PS2: tab_off = 0x14; PC files: the table sits further on).
        The table (tab_off..str_off) holds u32 entries: 0x80000000|offset = string in the string
        area, otherwise a data offset. Bytes [sec2+str_off, sec2+str_end) are XORed with
        a byte stream: state = state * 0x7D2B89DD + 0xCF9 (32-bit), key byte = (state >> 15) & 0xFF,
        state starts at `seed`. seed == 0 means "not encrypted" (the game zeroes it after decrypting).
Found in the executable: decrypt loop at 0x124128, PRNG at 0x1240F0, caller at 0x1242F0.
"""
import struct

MUL = 0x7D2B89DD
ADD = 0xCF9
M = 0xFFFFFFFF


def keystream(seed, n):
    out = bytearray(n)
    s = seed
    for i in range(n):
        s = (s * MUL + ADD) & M
        out[i] = (s >> 15) & 0xFF
    return bytes(out)


def sec2_offset(gcx):
    j = 4
    while struct.unpack_from("<I", gcx, j)[0] != 0xFFFFFFFF:
        j += 4
    return j + 4


def string_area(gcx):
    """(sec2, start, end, seed) with absolute start/end of the string area."""
    s2 = sec2_offset(gcx)
    _, _, str_off, str_end, seed = struct.unpack_from("<5I", gcx, s2)
    return s2, s2 + str_off, s2 + str_end, seed


def table(gcx):
    """(table entries, decrypted string area) of a GCX."""
    d = xor_area(gcx)
    s2 = sec2_offset(d)
    _, tab_off, str_off, str_end, _ = struct.unpack_from("<5I", d, s2)
    n = (str_off - tab_off) // 4
    return list(struct.unpack_from(f"<{n}I", d, s2 + tab_off)), d[s2 + str_off:s2 + str_end]


def strings(gcx):
    """[(table index, area offset, bytes)] for every string entry."""
    tab, area = table(gcx)
    out = []
    for i, v in enumerate(tab):
        if v & 0x80000000:
            off = v & 0x7FFFFFFF
            out.append((i, off, area[off:area.find(b"\x00", off)]))
    return out


def xor_area(gcx, seed=None):
    """Return a copy of gcx with the string area XORed (decrypt == encrypt)."""
    s2, a, b, file_seed = string_area(gcx)
    seed = file_seed if seed is None else seed
    out = bytearray(gcx)
    if seed:
        ks = keystream(seed, b - a)
        out[a:b] = bytes(x ^ y for x, y in zip(out[a:b], ks))
    return bytes(out)


if __name__ == "__main__":
    import sys
    f = open(sys.argv[1], "rb").read()
    mem = open(sys.argv[2], "rb").read()
    s2, a, b, seed = string_area(f)
    dec = xor_area(f)
    print(f"sec2 {s2:#x}, strings {a:#x}..{b:#x}, seed {seed:#x}; "
          f"decrypted area equals memory: {dec[a:b] == mem[a:b]}")
