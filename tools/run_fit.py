"""Group PS2 subtitle records into contiguous runs (each record ends where the next begins)
and check whether the Russian text fits each run as a whole (records re-packed inside the run,
total run size unchanged).
Usage: run_fit.py TABLE.csv
"""
import csv
import sys

HEADER = 16


def padded(n):
    return (n + 3) & ~3


def main():
    with open(sys.argv[1], encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    runs = []
    for r in rows:
        off, ln = int(r["ps2_offset"], 16), int(r["rec_len"])
        if runs and runs[-1]["file"] == r["ps2_file"] and runs[-1]["end"] == off:
            run = runs[-1]
        else:
            run = {"file": r["ps2_file"], "start": off, "end": off, "size": 0, "need": 0, "n": 0}
            runs.append(run)
        run["end"] = off + ln
        run["size"] += ln
        run["need"] += padded(HEADER + int(r["ru_bytes"]) + 1)
        run["n"] += 1

    for kind in ("DEMO.DAT", "VOX.DAT"):
        rs = [x for x in runs if x["file"] == kind]
        bad = [x for x in rs if x["need"] > x["size"]]
        lines_bad = sum(x["n"] for x in bad)
        print(f"{kind}: {len(rs)} runs, {len(bad)} runs overflow "
              f"({lines_bad} lines, worst +{max((x['need'] - x['size'] for x in bad), default=0)} B)")
        for x in sorted(bad, key=lambda x: x["size"] - x["need"])[:5]:
            print(f"   run @{x['start']:#x} lines={x['n']} size={x['size']} need={x['need']}")


if __name__ == "__main__":
    main()
