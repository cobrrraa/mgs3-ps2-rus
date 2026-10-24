"""Find which STAGE.DAT gcx matches a GCX image found in an EE memory dump (by its header bytes),
and save both for comparison.
Usage: gcx_find.py ISO EEMEM.bin MEM_ADDR OUTDIR
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stagedat as S  # noqa: E402


def header_len(buf, off=0):
    j = off + 8
    while struct.unpack_from("<I", buf, j)[0] != 0xFFFFFFFF:
        j += 4
    return j + 4 - off


def main():
    iso, mem_path, addr, outdir = sys.argv[1:5]
    addr = int(addr, 0)
    mem = open(mem_path, "rb").read()
    hlen = header_len(mem, addr)
    key = mem[addr:addr + hlen]
    os.makedirs(outdir, exist_ok=True)
    sd = S.StageDat(iso)
    for i, (name, _) in enumerate(sd.pages):
        for region, fname, blob in sd.files(i, "gcx", with_data=True):
            if blob[:hlen] == key:
                print(f"match: stage {name} {region} {fname} ({len(blob)} B), header {hlen} B")
                open(os.path.join(outdir, f"{name}_{fname}"), "wb").write(blob)
                open(os.path.join(outdir, f"{name}_{fname}.mem"), "wb").write(mem[addr:addr + len(blob)])


if __name__ == "__main__":
    main()
