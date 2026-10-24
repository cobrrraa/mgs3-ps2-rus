"""Disassemble EE memory (R5900, little-endian MIPS) with capstone.
Usage: disasm.py IMAGE START END [OUT.txt|-] [BASE]
BASE = address of file offset 0 (default 0, i.e. a raw EE memory dump).
"""
import sys

import capstone


def main():
    mem = open(sys.argv[1], "rb").read()
    start, end = int(sys.argv[2], 0), int(sys.argv[3], 0)
    out_arg = sys.argv[4] if len(sys.argv) > 4 else "-"
    out = sys.stdout if out_arg == "-" else open(out_arg, "w", encoding="utf-8")
    base = int(sys.argv[5], 0) if len(sys.argv) > 5 else 0
    md = capstone.Cs(capstone.CS_ARCH_MIPS, capstone.CS_MODE_MIPS64 | capstone.CS_MODE_LITTLE_ENDIAN)
    md.skipdata = True
    for ins in md.disasm(mem[start - base:end - base], start):
        word = int.from_bytes(ins.bytes, "little")
        out.write(f"{ins.address:08x}  {word:08x}  {ins.mnemonic:8s} {ins.op_str}\n")


if __name__ == "__main__":
    main()
