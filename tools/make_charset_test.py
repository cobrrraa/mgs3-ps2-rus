"""Build a test ISO: subtitles of the opening plane scene (v020_010) show every code 0x81-0xFF.
Usage: make_charset_test.py ISO PS2.jsonl OUT_ISO

Records are rewritten in place (size unchanged). PS2 subtitle ids (order in ps2_en.jsonl):
    1900 "Flying over Pakistan..."     -> "81:" 0x81..0x8F | "90:" 0x90..0x9F
    1901 "Approaching Soviet airspace" -> "A0:" 0xA0..0xAF
    1902 "Twenty minutes to dropoff"   -> "B0:" ...
    1903 "Commencing internal ..."     -> "C0:" ...
    1904 "Equipment check..."          -> "D0:" ...
    1905 "Arm main parachute."         -> "E0:" ...
    1908 "Drop zone still showing..."  -> "F0:" ...
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isols import list_iso, SECTOR  # noqa: E402

HEADER = 16
NEWLINE = b"\x80|"


def chunk(lo, hi):
    return f"{lo:02X}:".encode() + bytes(range(lo, hi + 1))


PLAN = {
    1900: chunk(0x81, 0x8F) + NEWLINE + chunk(0x90, 0x9F),
    1901: chunk(0xA0, 0xAF),
    1902: chunk(0xB0, 0xBF),
    1903: chunk(0xC0, 0xCF),
    1904: chunk(0xD0, 0xDF),
    1905: chunk(0xE0, 0xEF),
    1908: chunk(0xF0, 0xFF),
}


def main():
    iso, ps2_jsonl, out_iso = sys.argv[1:4]
    with open(ps2_jsonl, encoding="utf-8") as f:
        recs = [json.loads(line) for line in f]
    if not os.path.exists(out_iso):
        print("copying ISO...")
        shutil.copyfile(iso, out_iso)
    _, lba, _ = next(e for e in list_iso(out_iso) if e[0] == "/MGS/DEMO.DAT")
    with open(out_iso, "r+b") as f:
        for rid, text in PLAN.items():
            rec = recs[rid]
            assert rec["file"] == "DEMO.DAT"
            cap = rec["rec_len"] - HEADER - 1
            if len(text) > cap:
                sys.exit(f"id {rid}: line too long for record: {len(text)} > {cap}")
            body = text + b"\x00" * (rec["rec_len"] - HEADER - len(text))
            f.seek(lba * SECTOR + rec["offset"] + HEADER)
            f.write(body)
            print(f"id {rid} {rec['offset']:#x}: {rec['text'][:30]!r} -> {text!r}")
    print("done:", out_iso)


if __name__ == "__main__":
    main()
