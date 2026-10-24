"""List branches/jumps in [lo, hi) that target the given addresses, with a few instructions of context.
Usage: branch_sources.py EEMEM.bin LO HI TARGET [TARGET ...]
"""
import struct
import sys

import capstone


def target_of(addr, w):
    op = w >> 26
    if op in (0x02, 0x03):  # j / jal
        return ((addr + 4) & 0xF0000000) | ((w & 0x03FFFFFF) << 2)
    if op in (0x01, 0x04, 0x05, 0x06, 0x07, 0x14, 0x15, 0x16, 0x17):  # REGIMM, beq, bne, blez, bgtz, *l
        off = w & 0xFFFF
        off = off - 0x10000 if off & 0x8000 else off
        return addr + 4 + (off << 2)
    return None


def main():
    mem = open(sys.argv[1], "rb").read()
    lo, hi = int(sys.argv[2], 0), int(sys.argv[3], 0)
    targets = {int(t, 0) for t in sys.argv[4:]}
    md = capstone.Cs(capstone.CS_ARCH_MIPS, capstone.CS_MODE_MIPS64 | capstone.CS_MODE_LITTLE_ENDIAN)
    for a in range(lo, hi, 4):
        w = struct.unpack_from("<I", mem, a)[0]
        t = target_of(a, w)
        if t in targets:
            print(f"--- {a:#x} -> {t:#x}")
            for ins in md.disasm(mem[a - 0x18:a + 8], a - 0x18):
                print(f"   {ins.address:08x}  {ins.mnemonic} {ins.op_str}")


if __name__ == "__main__":
    main()
