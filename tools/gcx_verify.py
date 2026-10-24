"""Check that every GCX in a built ISO equals what gcx_build produces from the original ISO.
Usage: gcx_verify.py ORIGINAL.iso BUILT.iso RU.json [MORE.json ...] [--codec-layout LAYOUT.json]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stagedat as S  # noqa: E402
from gcx_apply import parse_args, build_stage_gcx  # noqa: E402


def gcx_files(iso):
    sd = S.StageDat(iso)
    return {name: blob for i, (name, _) in enumerate(sd.pages)
            for _, _, blob in sd.files(i, "gcx", with_data=True)}


def main():
    orig_iso, *rest = sys.argv[1:]
    new_iso, ru, remap, _ = parse_args(rest)
    orig, new = gcx_files(orig_iso), gcx_files(new_iso)
    bad = 0
    for name, blob in orig.items():
        want, _, _ = build_stage_gcx(blob, ru, remap)
        got = new[name]
        if got[:len(want)] != want or any(got[len(want):]):
            bad += 1
            print("mismatch:", name)
    print(f"gcx checked {len(orig)}, mismatches {bad}")


if __name__ == "__main__":
    main()
