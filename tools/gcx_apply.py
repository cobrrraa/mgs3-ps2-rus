"""Write Russian strings into every GCX of STAGE.DAT in an ISO.
Usage: gcx_apply.py ISO RU.json [MORE.json ...] [--codec-layout LAYOUT.json] [STAGE ...]
Later dictionaries override earlier ones. The resident script (RESIDENT) is loaded only up to its
original size, so it must not grow. With --codec-layout (from tools/codec_build.py) the codec call
IDs in the bytecode are moved to the rebuilt CODEC.DAT.
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stagedat as S  # noqa: E402
import stage_repack as R  # noqa: E402
import gcx as G  # noqa: E402
from gcx_build import build  # noqa: E402
import codec_build as C  # noqa: E402

RESIDENT = ("r_sna01", "r_sna02", "r_sna03")


def load_ru(paths):
    ru = {}
    for path in paths:
        ru.update(json.load(open(path, encoding="utf-8")))
    return ru


def parse_args(argv):
    """-> (iso, ru dict, codec Remap or None, only stages)"""
    iso, *rest = argv
    remap = None
    if "--codec-layout" in rest:
        k = rest.index("--codec-layout")
        remap = C.Remap(json.load(open(rest[k + 1])))
        del rest[k:k + 2]
    ru = load_ru([a for a in rest if a.endswith(".json")])
    return iso, ru, remap, [a for a in rest if not a.endswith(".json")]


def build_stage_gcx(blob, ru, remap):
    """Decrypt (seed 0), write the Russian strings, move codec call IDs -> (bytes, stats, ids)."""
    d = bytearray(G.xor_area(blob))
    struct.pack_into("<I", d, G.sec2_offset(d) + 16, 0)
    ids = 0
    if remap:
        d, ids = C.patch_ids(bytes(d), remap)
    new, st = build(bytes(d), ru)
    return new, st, ids


def main():
    iso, ru, remap, only = parse_args(sys.argv[1:])
    sd = S.StageDat(iso)
    totals = {"in_place": 0, "appended": 0, "kept": 0, "codec_ids": 0}
    failed = []
    for i, (name, _) in enumerate(sd.pages):
        if only and name not in only:
            continue
        for region, fname, blob in sd.files(i, "gcx", with_data=True):
            new, st, ids = build_stage_gcx(blob, ru, remap)
            if name in RESIDENT and len(new) != len(blob):
                failed.append((name, f"resident script grew {len(blob)} -> {len(new)} B"))
                continue
            for k in st:
                totals[k] += st[k]
            totals["codec_ids"] += ids
            try:
                R.replace_in_page(sd, iso, i, fname, new)
            except SystemExit as e:
                failed.append((name, str(e)))
    print("strings:", totals)
    print("failed stages:", len(failed))
    for name, err in failed:
        print("  ", name, err)


if __name__ == "__main__":
    main()
