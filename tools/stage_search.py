"""Search decompressed STAGE.DAT files of every stage for byte patterns.
Usage: stage_search.py ISO PATTERN [PATTERN ...]
Prints stage, region, file name, file size, offsets of each hit (first 3).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stagedat as S  # noqa: E402


def main():
    iso, *pats = sys.argv[1:]
    pats = [p.encode() for p in pats]
    sd = S.StageDat(iso)
    files_hit = 0
    for i, (name, _) in enumerate(sd.pages):
        try:
            for region, fname, blob in sd.files(i, with_data=True):
                for p in pats:
                    k = blob.find(p)
                    if k != -1:
                        hits = []
                        while k != -1 and len(hits) < 3:
                            hits.append(hex(k))
                            k = blob.find(p, k + 1)
                        files_hit += 1
                        print(f"{name:10s} {region:10s} {fname:16s} {len(blob):9d} {p!r} {hits}")
        except Exception as e:  # keep going over other stages
            print(f"{name}: error {e}")
    print("files with hits:", files_hit)


if __name__ == "__main__":
    main()
