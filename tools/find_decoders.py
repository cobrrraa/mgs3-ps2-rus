"""Find text-decoding loops: `bltz/bltzl rX` whose delay slot or next instructions load the
second byte (`lbu rY, 1(rB)`), near a compare against 0x1F. Prints a small disassembly around each hit.
Usage: find_decoders.py EEMEM.bin [START END]
"""
import struct
import sys

import capstone


def main():
    mem = open(sys.argv[1], "rb").read()
    lo = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x100000
    hi = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0x2000000
    md = capstone.Cs(capstone.CS_ARCH_MIPS, capstone.CS_MODE_MIPS64 | capstone.CS_MODE_LITTLE_ENDIAN)
    words = struct.unpack_from(f"<{(hi - lo) // 4}I", mem, lo)
    for i, w in enumerate(words[:-1]):
        op, rt = w >> 26, (w >> 16) & 31
        if op != 1 or rt not in (0, 2):  # REGIMM bltz / bltzl
            continue
        nxt = words[i + 1]
        if nxt >> 26 != 0x24 or nxt & 0xFFFF != 1:  # lbu rY, 1(rB)
            continue
        # a 0x1F constant nearby (addiu/ori rZ, zero, 0x1f) within 48 instructions before
        window = words[max(0, i - 48):i]
        if not any((v >> 26) in (0x09, 0x0D) and (v >> 21) & 31 == 0 and v & 0xFFFF == 0x1F for v in window):
            continue
        addr = lo + 4 * i
        print(f"=== decoder branch at {addr:#x}")
        for ins in md.disasm(mem[addr - 0x30:addr + 0x24], addr - 0x30):
            mark = ">>" if ins.address == addr else "  "
            print(f"{mark} {ins.address:08x}  {int.from_bytes(ins.bytes, 'little'):08x}  {ins.mnemonic} {ins.op_str}")


if __name__ == "__main__":
    main()
