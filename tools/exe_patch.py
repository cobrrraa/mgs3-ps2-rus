"""Patch the MGS3 (SLUS_209.15) text decoder: bytes 0x90-0xFF become single-byte glyphs of the main
font (Cyrillic in cp1251); 0x80-0x8F stay two-byte lead bytes (0x80 newline, 0x81-0x83 kana and
button icons such as 83 02 = circle, 0x84+ glyph pages such as 8C 02 = infinity).

The executable is a small stub + zlib stream: unpacked image goes to 0x100000, entry 0x100024.
We unpack, patch the 8 decoder copies in place and recompress (must not exceed the original size).

Usage:
    exe_patch.py SLUS_IN SLUS_OUT              -> write patched executable
    exe_patch.py SLUS_IN SLUS_OUT ISO          -> also write it into ISO in place of SLUS_209.15
"""
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isols import list_iso, SECTOR  # noqa: E402

SEG_FILE_OFF = 0x1000
SEG_VADDR = 0x800000
COMP_VADDR = 0x800004
COMP_MAX = 0x503A4          # avail_in hard-coded in the stub (reads 4 bytes past the stream)
COMP_ROOM = 0x503A0         # stream must end before 0x8503A4: unpack address + entry live there
UNPACK_BASE = 0x100000

ZERO, T5, T6, T7 = 0, 13, 14, 15
LEADS = 0x10    # two-byte lead bytes: 0x80 .. 0x80+LEADS-1 (test: byte - 0x80 < LEADS, unsigned)

# Form A: decoder where the caller computed t6 = signed byte, t7 = byte (0..255).
#   (sll_slot, sra_slot, X): sll t6,t7,24 / sra t6,t6,24 before `bne ...,X`; X = bltzl t6
FORM_A = [(0x11EB5C, 0x11EB68, 0x11EC00),
          (0x11ED50, 0x11ED5C, 0x11EDDC),
          (0x11F700, 0x11F70C, 0x11F798),
          (0x11F8EC, 0x11F8F8, 0x11F998)]
# Form B: Y = `sra t7,t7,24; bltzl t7` with t5 = byte (0..255)
FORM_B = [0x11F408, 0x11F430, 0x11F5F4, 0x11F67C, 0x11F7D0, 0x11F85C, 0x11F96C, 0x11F9D8]
# Form C: `[sll t7,t6,24;] sra t7,t7,24; bgez t7,C; ori t6,t5,0x8000; lbu t6,1(base); sll t7,t5,8;
# b C; or t6,t7,t6` - pointer advance is derived from the code later.
#   C1: (delay slot of the incoming bne that held `sll t7,t6,24`, Y = sra)
#   C2: Y = the sll itself (8 free slots)
FORM_C1 = [(0x11F36C, 0x11F3C0)]
FORM_C2 = [0x11F49C]
# glyph blitter skips codes whose low byte is 0, 0xFE or 0xFF: `addiu t7,a0,-1; sltiu t7,t7,0xFD`.
# Cyrillic ю/я are 0xFE/0xFF in cp1251, so only 0 stays skipped.
BLIT_RANGE = 0x11E5C4


def i_type(op, rs, rt, imm):
    return (op << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)


def addiu(rt, rs, imm):
    return i_type(0x09, rs, rt, imm)


def sltiu(rt, rs, imm):
    return i_type(0x0B, rs, rt, imm)


def ori(rt, rs, imm):
    return i_type(0x0D, rs, rt, imm)


def lbu(rt, off, base):
    return i_type(0x24, base, rt, off)


def beq(rs, rt, pc, target):
    return i_type(0x04, rs, rt, (target - (pc + 4)) >> 2)


def b(pc, target):
    return beq(ZERO, ZERO, pc, target)


def sll(rd, rt, sa):
    return (rt << 16) | (rd << 11) | (sa << 6)


def or_(rd, rs, rt):
    return (rs << 21) | (rt << 16) | (rd << 11) | 0x25


class Image:
    def __init__(self, data, base):
        self.data, self.base = bytearray(data), base

    def word(self, addr):
        return struct.unpack_from("<I", self.data, addr - self.base)[0]

    def put(self, addr, words):
        for i, w in enumerate(words):
            struct.pack_into("<I", self.data, addr - self.base + 4 * i, w)


def branch_target(pc, w):
    off = w & 0xFFFF
    off = off - 0x10000 if off & 0x8000 else off
    return pc + 4 + (off << 2)


def expect(cond, what):
    if not cond:
        raise SystemExit(f"unexpected code: {what}")


def patch_form_a(img, sll_slot, sra_slot, x):
    expect(img.word(sll_slot) == sll(T6, T7, 24), f"{sll_slot:#x} sll t6,t7,24")
    expect(img.word(sra_slot) == 0x000E7603, f"{sra_slot:#x} sra t6,t6,24")
    expect(img.word(x) >> 16 == 0x05C2, f"{x:#x} bltzl t6")
    ld = img.word(x + 4)
    expect(ld >> 26 == 0x24 and (ld >> 16) & 31 == T6 and ld & 0xFFFF == 1, f"{x + 4:#x} lbu t6,1(base)")
    base = (ld >> 21) & 31
    expect(img.word(x + 8) == ori(T7, T7, 0x8000), f"{x + 8:#x} ori t7,t7,0x8000")
    common = branch_target(x + 12, img.word(x + 12))
    adv = img.word(x + 16)
    expect(adv >> 26 == 0x09 and adv & 0xFFFF == 1, f"{x + 16:#x} addiu A,base,1")
    a_reg = (adv >> 16) & 31

    img.put(sll_slot, [addiu(T6, T7, -0x80)])      # t6 = byte - 0x80
    img.put(sra_slot, [sltiu(T6, T6, LEADS)])      # t6 = byte is a lead byte
    img.put(x, [
        beq(T6, ZERO, x, x + 0x18),                # single byte -> x+0x18
        lbu(T6, 1, base),                          # (delay) second byte
        sll(T7, T7, 8),
        addiu(a_reg, base, 2),
        b(x + 0x10, common),
        or_(T7, T7, T6),
        ori(T7, T7, 0x8000),                       # x+0x18: single-byte code
        b(x + 0x1C, common),
        addiu(a_reg, base, 1),
    ])


def patch_form_b(img, y):
    expect(img.word(y) == 0x000F7E03, f"{y:#x} sra t7,t7,24")
    expect(img.word(y + 4) >> 16 == 0x05E2, f"{y + 4:#x} bltzl t7")
    ld = img.word(y + 8)
    expect(ld >> 26 == 0x24 and (ld >> 16) & 31 == T6 and ld & 0xFFFF == 1, f"{y + 8:#x} lbu t6,1(base)")
    base = (ld >> 21) & 31
    single = img.word(y + 12)
    expect(single >> 26 == 0x0D and (single >> 21) & 31 == T5 and single & 0xFFFF == 0x8000,
           f"{y + 12:#x} ori R,t5,0x8000")
    res = (single >> 16) & 31
    common = branch_target(y + 16, img.word(y + 16))
    adv = img.word(y + 20)
    expect(adv >> 26 == 0x09 and adv & 0xFFFF == 1, f"{y + 20:#x} addiu A,base,1")
    a_reg = (adv >> 16) & 31
    flag = T7 if res == T6 else T6                 # scratch register not holding the result
    # the delay slot below already advanced A by one; when A is also the base pointer,
    # the two-byte path must read/advance relative to the new value
    second, rest = (0, 1) if a_reg == base else (1, 2)

    img.put(y, [
        addiu(flag, T5, -0x80),
        sltiu(flag, flag, LEADS),                  # flag = byte is a lead byte
        ori(res, T5, 0x8000),                      # single-byte code by default
        beq(flag, ZERO, y + 12, common),
        addiu(a_reg, base, 1),                     # (delay)
        lbu(T6, second, base),                     # two-byte code
        sll(T7, T5, 8),
        addiu(a_reg, base, rest),
        b(y + 32, common),
        or_(res, T7, T6),
    ])


def form_c_tail(img, y):
    """Check `sra t7,t7,24; bgez t7,C; ori t6,t5,0x8000; lbu t6,1(base); sll t7,t5,8; b C; or t6,t7,t6`."""
    expect(img.word(y) == 0x000F7E03, f"{y:#x} sra t7,t7,24")
    expect(img.word(y + 4) >> 16 == 0x05E1, f"{y + 4:#x} bgez t7")
    common = branch_target(y + 4, img.word(y + 4))
    expect(img.word(y + 8) == ori(T6, T5, 0x8000), f"{y + 8:#x} ori t6,t5,0x8000")
    ld = img.word(y + 12)
    expect(ld >> 26 == 0x24 and (ld >> 16) & 31 == T6 and ld & 0xFFFF == 1, f"{y + 12:#x} lbu t6,1(base)")
    expect(img.word(y + 16) == sll(T7, T5, 8), f"{y + 16:#x} sll t7,t5,8")
    expect(branch_target(y + 20, img.word(y + 20)) == common, f"{y + 20:#x} b C")
    expect(img.word(y + 24) == or_(T6, T7, T6), f"{y + 24:#x} or t6,t7,t6")
    return common, (ld >> 21) & 31


def form_c_body(pc, common, base):
    """7 words: flag in t7 already = byte - 0x80."""
    return [
        sltiu(T7, T7, LEADS),
        beq(T7, ZERO, pc + 4, common),
        ori(T6, T5, 0x8000),                       # (delay) single-byte code
        lbu(T6, 1, base),
        sll(T7, T5, 8),
        b(pc + 20, common),
        or_(T6, T7, T6),
    ]


def patch_form_c1(img, delay_slot, y):
    expect(img.word(delay_slot) == sll(T7, T6, 24), f"{delay_slot:#x} sll t7,t6,24")
    common, base = form_c_tail(img, y)
    img.put(delay_slot, [addiu(T7, T5, -0x80)])
    img.put(y, form_c_body(y, common, base))


def patch_form_c2(img, y):
    expect(img.word(y) == sll(T7, T6, 24), f"{y:#x} sll t7,t6,24")
    common, base = form_c_tail(img, y + 4)
    img.put(y, [addiu(T7, T5, -0x80)] + form_c_body(y + 4, common, base))


def main():
    src, dst = sys.argv[1:3]
    iso = sys.argv[3] if len(sys.argv) > 3 else None
    elf = bytearray(open(src, "rb").read())
    seg = Image(elf[SEG_FILE_OFF:], SEG_VADDR)
    comp = bytes(seg.data[COMP_VADDR - SEG_VADDR:COMP_VADDR - SEG_VADDR + COMP_MAX])
    raw = zlib.decompressobj().decompress(comp)
    expect(seg.word(0x8503A4) == UNPACK_BASE, "unpack address")

    img = Image(raw, UNPACK_BASE)
    for args in FORM_A:
        patch_form_a(img, *args)
    for y in FORM_B:
        patch_form_b(img, y)
    for args in FORM_C1:
        patch_form_c1(img, *args)
    for y in FORM_C2:
        patch_form_c2(img, y)
    n_sites = len(FORM_A) + len(FORM_B) + len(FORM_C1) + len(FORM_C2)
    expect(img.word(BLIT_RANGE) == sltiu(T7, T7, 0xFD), f"{BLIT_RANGE:#x} sltiu t7,t7,0xfd")
    img.put(BLIT_RANGE, [sltiu(T7, T7, 0xFF)])

    new = zlib.compress(bytes(img.data), 9)
    if len(new) > COMP_ROOM:
        raise SystemExit(f"recompressed image too big: {len(new)} > {COMP_ROOM}")
    off = SEG_FILE_OFF + (COMP_VADDR - SEG_VADDR)
    tail = bytes(elf[off + COMP_ROOM:off + COMP_ROOM + 8])
    elf[off:off + COMP_ROOM] = new + b"\x00" * (COMP_ROOM - len(new))
    # the words after the stream (unpack address, entry point) must be untouched
    assert bytes(elf[off + COMP_ROOM:off + COMP_ROOM + 8]) == tail
    assert struct.unpack_from("<I", elf, off + COMP_ROOM)[0] == UNPACK_BASE
    assert zlib.decompressobj().decompress(bytes(elf[off:off + COMP_MAX])) == bytes(img.data)
    with open(dst, "wb") as f:
        f.write(elf)
    print(f"patched {n_sites} decoders; zlib {len(new)} / {COMP_ROOM} bytes -> {dst}")

    if iso:
        _, lba, size = next(e for e in list_iso(iso) if e[0] == "/SLUS_209.15")
        expect(size == len(elf), "executable size in ISO")
        with open(iso, "r+b") as f:
            f.seek(lba * SECTOR)
            f.write(elf)
        print(f"written into {iso} at LBA {lba}")


if __name__ == "__main__":
    main()
