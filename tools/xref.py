"""Find MIPS code referencing an absolute address via lui + (addiu|lw|sw|lbu|...) pairs.
Usage: xref.py EEMEM.bin ADDR [ADDR ...]   (scans 0x100000-0x2000000)
"""
import struct
import sys

LO, HI = 0x100000, 0x2000000
# opcodes that take base+imm16: addiu, lb, lh, lw, lbu, lhu, sb, sh, sw, ld, sd, lq, sq, lwc1, swc1, ori
IMM_OPS = {0x09, 0x20, 0x21, 0x23, 0x24, 0x25, 0x28, 0x29, 0x2B, 0x37, 0x3F, 0x1E, 0x1F, 0x31, 0x39, 0x0D}


def main():
    mem = open(sys.argv[1], "rb").read()
    targets = [int(a, 0) for a in sys.argv[2:]]
    words = struct.unpack_from(f"<{(HI - LO) // 4}I", mem, LO)
    for i, w in enumerate(words):
        if w >> 26 != 0x0F:  # lui
            continue
        rt = (w >> 16) & 31
        hi = (w & 0xFFFF) << 16
        for j in range(i + 1, min(i + 12, len(words))):
            v = words[j]
            op = v >> 26
            if op in IMM_OPS and (v >> 21) & 31 == rt:
                imm = v & 0xFFFF
                addr = (hi | imm) if op == 0x0D else (hi + (imm - 0x10000 if imm & 0x8000 else imm)) & 0xFFFFFFFF
                if addr in targets:
                    print(f"{hex(addr)}: lui@{LO + 4 * i:#x} use@{LO + 4 * j:#x} op={op:#x}")
            # stop if rt is overwritten by something else
            if op not in (0x2B, 0x29, 0x28, 0x3F, 0x1F, 0x39) and ((v >> 16) & 31) == rt and j != i:
                if op != 0 and op in IMM_OPS | {0x0F}:
                    break


if __name__ == "__main__":
    main()
