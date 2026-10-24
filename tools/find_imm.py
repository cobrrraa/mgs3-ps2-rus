"""Find MIPS instructions with a given 16-bit immediate (ori/addiu/slti/sltiu/andi/xori, any regs).
Usage: find_imm.py EEMEM.bin IMM [IMM ...]  (scans 0x100000-0x2000000)
"""
import struct
import sys

OPS = {0x08: "addi", 0x09: "addiu", 0x0A: "slti", 0x0B: "sltiu", 0x0C: "andi", 0x0D: "ori", 0x0E: "xori"}
LO, HI = 0x100000, 0x2000000


def main():
    mem = open(sys.argv[1], "rb").read()
    imms = {int(x, 0) & 0xFFFF for x in sys.argv[2:]}
    words = struct.unpack_from(f"<{(HI - LO) // 4}I", mem, LO)
    for i, w in enumerate(words):
        op = w >> 26
        if op in OPS and (w & 0xFFFF) in imms:
            print(f"{LO + 4 * i:#010x}  {OPS[op]} r{(w >> 16) & 31}, r{(w >> 21) & 31}, {w & 0xFFFF:#x}")


if __name__ == "__main__":
    main()
