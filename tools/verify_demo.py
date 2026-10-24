"""Verify a built ISO's DEMO.DAT and MOVIE.DAT against the original:
  1. every translated subtitle block reads back as the expected Russian text;
  2. no byte outside the subtitle blocks (header's records_size field + records area) changed.
Usage: verify_demo.py ORIGINAL.iso BUILT.iso TABLE.csv PS2.jsonl OVERRIDES.json [...] [--vox-blocks JSON]
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isols import list_iso, SECTOR  # noqa: E402
from encoding_ru import encode  # noqa: E402
from demo_blocks import blocks  # noqa: E402
from apply_subs import load_texts, vox_body, vox_pairs, BLOCK_FILES  # noqa: E402

CHUNK = 64 << 20


def check_text(f, lba, ps2, dat, ru):
    """Returns (allowed byte ranges, mismatch count) for one .DAT."""
    allowed, bad = [], 0
    for run in blocks(ps2, dat):
        if any(not ru[i]["ru"] for i, _ in run):
            continue  # untranslated block must stay identical -> not allowed to differ
        first = run[0][1]
        f.seek(lba * SECTOR + first["offset"] - 24)
        hdr = struct.unpack("<6I", f.read(24))
        allowed.append((first["offset"] - 4, first["offset"] + hdr[2] - 24))
        body = f.read(hdr[5])
        pos = 0
        for i, r in run:
            start, end, zero, rec_len, lang = struct.unpack_from("<IIIHH", body, pos)
            text = body[pos + 16:body.index(b"\x00", pos + 16)]
            if (start, end, zero, lang) != (r["start"], r["end"], 0, 1) or text != encode(ru[i]["ru"]):
                bad += 1
                print(f"{dat} id {i}: mismatch")
            pos += rec_len
        if pos != hdr[5]:
            bad += 1
            print(f"{dat} block @{first['offset']:#x}: records_size {hdr[5]} but walked {pos}")
    return sorted(allowed), bad


def changed_outside(orig_iso, new_iso, lba, size, allowed):
    outside, k, pos = 0, 0, 0
    with open(orig_iso, "rb") as fo, open(new_iso, "rb") as fn:
        while pos < size:
            n = min(CHUNK, size - pos)
            fo.seek(lba * SECTOR + pos)
            fn.seek(lba * SECTOR + pos)
            a, b = fo.read(n), fn.read(n)
            if a != b:
                for j in range(n):
                    if a[j] != b[j]:
                        off = pos + j
                        while k < len(allowed) and allowed[k][1] <= off:
                            k += 1
                        if not (k < len(allowed) and allowed[k][0] <= off < allowed[k][1]):
                            outside += 1
            pos += n
    return outside


def check_vox(f, lba, vox_blocks, ps2, ru):
    """Each VOX block must hold exactly the body apply_subs builds; returns (allowed, mismatches)."""
    ru_by_off = {r["offset"]: ru[i]["ru"] for i, r in enumerate(ps2) if r["file"] == "VOX.DAT"}
    pair = vox_pairs(vox_blocks, ru_by_off)
    allowed, bad = [], 0
    for blk in vox_blocks:
        body = vox_body(blk, ru_by_off, pair)
        if body is None or len(body) > blk["bsize"] - 24:
            continue
        allowed.append((blk["off"] - 4, blk["off"] + blk["bsize"] - 24))
        f.seek(lba * SECTOR + blk["off"] - 4)
        rsize = struct.unpack("<I", f.read(4))[0]
        if rsize != len(body) or f.read(rsize) != body:
            bad += 1
            print(f"VOX block @{blk['off']:#x}: mismatch")
    return sorted(allowed), bad


def main():
    args = sys.argv[1:]
    vox_path = None
    if "--vox-blocks" in args:
        k = args.index("--vox-blocks")
        vox_path = args[k + 1]
        del args[k:k + 2]
    orig_iso, new_iso, table, jsonl, *overrides = args
    ru = load_texts(table, overrides)
    with open(jsonl, encoding="utf-8") as f:
        ps2 = [json.loads(line) for line in f]
    entries = {e[0]: e for e in list_iso(new_iso)}
    if vox_path:
        with open(vox_path, encoding="utf-8") as f:
            vox_blocks = json.load(f)
        _, lba, size = entries["/MGS/VOX.DAT"]
        with open(new_iso, "rb") as f:
            allowed, bad = check_vox(f, lba, vox_blocks, ps2, ru)
        outside = changed_outside(orig_iso, new_iso, lba, size, allowed)
        print(f"VOX.DAT: translated blocks {len(allowed)}, mismatches {bad}, "
              f"changed bytes outside blocks {outside}")
    for dat in BLOCK_FILES:
        _, lba, size = entries["/MGS/" + dat]
        with open(new_iso, "rb") as f:
            allowed, bad = check_text(f, lba, ps2, dat, ru)
        outside = changed_outside(orig_iso, new_iso, lba, size, allowed)
        print(f"{dat}: translated blocks {len(allowed)}, text mismatches {bad}, "
              f"changed bytes outside blocks {outside}")


if __name__ == "__main__":
    main()
