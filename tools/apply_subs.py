"""Write Russian subtitles from the correspondence table into DEMO.DAT and MOVIE.DAT of an ISO.

Subtitle block (24-byte header right before the first record), same in both files:
    u32 ?, u32 4, u32 block_size (= align16(24 + records)), u32 start, u32 0, u32 records_size
Records are re-laid out inside the block: each gets exactly the room its text needs; records_size
is updated, block_size never changes (the alignment tail is the only slack). A block whose Russian
text does not fit is left untouched and reported with the number of bytes to cut.

Usage: apply_subs.py ISO TABLE.csv PS2.jsonl [--pc-file NAME ...] [--overrides JSON ...]
Override files map {id: text}; later files win; keys starting with "_" are comments.
"""
import argparse
import csv
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isols import list_iso, SECTOR  # noqa: E402
from encoding_ru import encode  # noqa: E402
from demo_blocks import blocks  # noqa: E402

HEADER = 16
BLOCK_HDR = 0x18
BLOCK_FILES = ("DEMO.DAT", "MOVIE.DAT")


def load_texts(table, overrides):
    """id -> {"ru", "pc_file", ...} with overrides applied and spaces around line breaks stripped."""
    with open(table, encoding="utf-8-sig") as f:
        rows = {int(r["id"]): r for r in csv.DictReader(f, delimiter=";")}
    for path in overrides or []:
        with open(path, encoding="utf-8") as f:
            for k, v in json.load(f).items():
                if not k.startswith("_"):
                    rows[int(k)]["ru"] = v
    for r in rows.values():
        r["ru"] = "|".join(line.strip() for line in r["ru"].split("|"))
    return rows


def record(rec, text, lang=1):
    size = (HEADER + len(text) + 1 + 3) & ~3
    head = struct.pack("<IIIHH", rec["start"], rec["end"], 0, size, lang)
    return head + text + b"\x00" * (size - HEADER - len(text))


def vox_pairs(vox_blocks, ru_by_off):
    """(start, end, english hex) -> Russian, from the lang-1 records of all blocks."""
    return {(r["start"], r["end"], r["text"]): ru_by_off[r["off"]]
            for b in vox_blocks for r in b["recs"] if r["lang"] == 1 and r["off"] in ru_by_off}


def vox_body(blk, ru_by_off, pair):
    """New records area of a VOX block (records + original tail), or None if a line has no Russian.

    lang-1 records take the table text; a lang-7 record copies the Russian of the lang-1 record
    with the same timing and English text (it may sit in the neighbouring block); empty records
    stay empty."""
    out = []
    for r in blk["recs"]:
        if not r["text"]:
            text = b""
        elif r["lang"] == 1:
            if not ru_by_off.get(r["off"]):
                return None
            text = encode(ru_by_off[r["off"]])
        else:
            ru = pair.get((r["start"], r["end"], r["text"]))
            if not ru:
                return None
            text = encode(ru)
        out.append(record(r, text, r["lang"]))
    return b"".join(out) + bytes.fromhex(blk["tail"])


def apply_vox(f, lba, vox_blocks, ps2, ru, dry_run):
    ru_by_off = {r["offset"]: ru[i]["ru"] for i, r in enumerate(ps2) if r["file"] == "VOX.DAT"}
    pair = vox_pairs(vox_blocks, ru_by_off)
    done, short, missing = 0, [], 0
    for blk in vox_blocks:
        body = vox_body(blk, ru_by_off, pair)
        if body is None:
            missing += 1
            continue
        room = blk["bsize"] - BLOCK_HDR
        if len(body) > room:
            short.append((blk["off"], len(body) - room))
            continue
        done += 1
        if dry_run:
            continue
        base = lba * SECTOR + blk["off"]
        f.seek(base)
        f.write(body + b"\x00" * max(0, blk["rsize"] - len(body)))
        f.seek(base - 4)
        f.write(struct.pack("<I", len(body)))
    print(f"VOX.DAT: blocks written {done}, too long {len(short)} "
          f"(sum {sum(o for _, o in short)} B), without translation {missing}")
    return short


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("iso")
    ap.add_argument("table")
    ap.add_argument("ps2_jsonl")
    ap.add_argument("--pc-file", nargs="*", default=[])
    ap.add_argument("--overrides", nargs="*", default=[])
    ap.add_argument("--vox-blocks", help="vox_blocks.py output; enables VOX.DAT")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ru = load_texts(args.table, args.overrides)
    with open(args.ps2_jsonl, encoding="utf-8") as f:
        ps2 = [json.loads(line) for line in f]
    lbas = {e[0]: e[1] for e in list_iso(args.iso)}

    with open(args.iso, "rb" if args.dry_run else "r+b") as f:
        if args.vox_blocks:
            with open(args.vox_blocks, encoding="utf-8") as vf:
                vox_blocks = json.load(vf)
            for off, over in apply_vox(f, lbas["/MGS/VOX.DAT"], vox_blocks, ps2, ru, args.dry_run):
                print(f"  VOX block @{off:#x}: cut {over} bytes")
        for dat in BLOCK_FILES:
            if args.dry_run:
                continue
            lba = lbas["/MGS/" + dat]
            done, short, empty = 0, [], 0
            for run in blocks(ps2, dat):
                if args.pc_file and not any(ru[i]["pc_file"] in args.pc_file for i, _ in run):
                    continue
                if any(not ru[i]["ru"] for i, _ in run):
                    empty += 1  # no translation for some line: keep the block as it is
                    continue
                first = run[0][1]
                base = lba * SECTOR + first["offset"]
                f.seek(base - BLOCK_HDR)
                hdr = bytearray(f.read(BLOCK_HDR))
                _, four, block_size, _start, zero, rec_size = struct.unpack("<IIIIII", hdr)
                # `start` is usually the first record's start time, but not always (0 or another time)
                assert four == 4 and zero == 0, f"{dat} block @{first['offset']:#x}"
                assert rec_size == sum(r["rec_len"] for _, r in run)
                room = block_size - BLOCK_HDR
                body = b"".join(record(r, encode(ru[i]["ru"])) for i, r in run)
                if len(body) > room:
                    short.append((run[0][0], run[-1][0], len(body) - room))
                    continue
                f.seek(base)
                f.write(body + b"\x00" * max(0, rec_size - len(body)))
                struct.pack_into("<I", hdr, 20, len(body))
                f.seek(base - BLOCK_HDR)
                f.write(hdr)
                done += 1
            print(f"{dat}: blocks written {done}, too long {len(short)}, without translation {empty}")
            for a, b, over in short:
                print(f"  ids {a}-{b}: cut {over} bytes")


if __name__ == "__main__":
    main()
