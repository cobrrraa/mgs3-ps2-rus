"""Extract and decrypt every GCX of STAGE.DAT; count string-table strings and length-prefixed
(0x07 len) strings found inside data entries.
Usage: gcx_dump_all.py ISO OUTDIR
Writes OUTDIR/<stage>_<file>.gcx (decrypted) and OUTDIR/strings.json:
    {"table": {text: [stage, ...]}, "inline": {text: [stage, ...]}}
"""
import collections
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stagedat as S  # noqa: E402
import gcx as G  # noqa: E402

INLINE = re.compile(rb"\x07([\x02-\x7f])")


def main():
    iso, outdir = sys.argv[1:3]
    os.makedirs(outdir, exist_ok=True)
    sd = S.StageDat(iso)
    table, inline = collections.defaultdict(list), collections.defaultdict(list)
    n_files = 0
    for i, (name, _) in enumerate(sd.pages):
        for region, fname, blob in sd.files(i, "gcx", with_data=True):
            d = bytearray(G.xor_area(blob))
            s2 = G.sec2_offset(d)
            struct.pack_into("<I", d, s2 + 16, 0)  # seed = 0: decrypted, like the game does
            d = bytes(d)
            n_files += 1
            open(os.path.join(outdir, f"{name}_{fname}"), "wb").write(d)
            s2, a, b, _ = G.string_area(d)
            n = (a - (s2 + 0x14)) // 4
            area = d[a:b]
            for v in struct.unpack_from(f"<{n}I", d, s2 + 0x14):
                if v & 0x80000000:
                    off = v & 0x7FFFFFFF
                    t = area[off:area.find(b"\x00", off)].decode("latin-1")
                    if t.strip():
                        table[t].append(name)
            for m in INLINE.finditer(area):
                ln = m.group(1)[0]
                s = area[m.end():m.end() + ln]
                if len(s) == ln and s.endswith(b"\x00") and re.fullmatch(rb"[\x20-\x7e]+", s[:-1] or b"\x01"):
                    inline[s[:-1].decode("latin-1")].append(name)
    with open(os.path.join(outdir, "strings.json"), "w", encoding="utf-8") as f:
        json.dump({"table": table, "inline": inline}, f, ensure_ascii=False, indent=0)
    print(f"gcx files: {n_files}; distinct table strings: {len(table)} "
          f"({sum(len(t) for t in table)} chars); distinct inline strings: {len(inline)}")


if __name__ == "__main__":
    main()
