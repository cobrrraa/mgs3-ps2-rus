"""Build every intermediate file the Russian build needs, from the three inputs nobody may
redistribute: the PS2 US image, the PC Master Collection game folder and the PC russifier folder.

Usage: prepare.py ORIGINAL.iso PC_MGS3_DIR RUSSIFIER_DIR
    ORIGINAL.iso   Metal Gear Solid 3: Snake Eater, PS2 NTSC-U (SLUS-20915), 4 558 848 000 bytes
    PC_MGS3_DIR    the MGS3 folder of METAL GEAR SOLID: MASTER COLLECTION Vol.1 (has fr/, assets/)
    RUSSIFIER_DIR  the unpacked PC russifier (its own fr/, assets/ folders)

Then:  build_ru.py ORIGINAL.iso OUT.iso

Steps (all outputs under work/):
  1. original font from STAGE.DAT (init/resident 383c45.raw)          tools/stagedat.py extract
  2. PS2 English subtitles DEMO/VOX/MOVIE -> subs/ps2_en.jsonl          tools/ps2_subs.py
  3. PC English + Russian subtitles -> subs/pc_en_ru.jsonl              tools/pc_subs.py
  4. PC-only overrides + PS2 <-> PC table -> subs/subs_ps2_ru.csv       tools/make_overrides.py, match_subs.py
  5. VOX subtitle blocks -> subs/vox_blocks.json                       tools/vox_blocks.py
  6. PS2 stage scripts (GCX) decrypted -> gcx/ps2/*.gcx, strings.json   tools/gcx_dump_all.py
  7. GCX English -> Russian from the PC scripts -> gcx/gcx_ru.json      tools/gcx_pc_align.py, gcx_translate.py
  8. CODEC.DAT strings, English -> Russian from the PC codec            tools/codec_dat.py, codec_align.py
Own translations and edits (work/subs/*.json, work/gcx/*_manual.json, work/codec/codec_manual.json)
are part of the repository and are only read here.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
WORK = os.path.join(ROOT, "work")


def run(*args):
    print(">", " ".join(os.path.basename(a) if a.endswith(".py") else a for a in args), flush=True)
    subprocess.run([sys.executable, "-E", *args], check=True)


def tool(name):
    return os.path.join(TOOLS, name)


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    iso, pc, rus = (os.path.abspath(a) for a in sys.argv[1:4])
    for path in (iso, os.path.join(pc, "fr", "codec", "_bp"), os.path.join(rus, "fr", "codec", "_bp")):
        if not os.path.exists(path):
            sys.exit(f"not found: {path}")
    subs, gcx, codec = (os.path.join(WORK, d) for d in ("subs", "gcx", "codec"))
    for d in (subs, gcx, codec, os.path.join(WORK, "ps2"), os.path.join(WORK, "font"), os.path.join(WORK, "iso")):
        os.makedirs(d, exist_ok=True)

    run(tool("stagedat.py"), "extract", iso, "init", os.path.join(WORK, "stage", "init"), "raw")

    ps2_en, pc_en_ru = os.path.join(subs, "ps2_en.jsonl"), os.path.join(subs, "pc_en_ru.jsonl")
    run(tool("ps2_subs.py"), iso, ps2_en)
    run(tool("pc_subs.py"), pc, rus, pc_en_ru)
    overrides = os.path.join(subs, "overrides.json")
    run(tool("make_overrides.py"), pc_en_ru, overrides)
    run(tool("match_subs.py"), ps2_en, pc_en_ru, os.path.join(subs, "subs_ps2_ru.csv"), overrides)
    run(tool("vox_blocks.py"), iso, os.path.join(subs, "vox_blocks.json"))

    gcx_ps2 = os.path.join(gcx, "ps2")
    run(tool("gcx_dump_all.py"), iso, gcx_ps2)
    pc_gcx, rus_gcx = (os.path.join(d, "assets", "gcx", "fr", "_bp") for d in (pc, rus))
    strings = os.path.join(gcx_ps2, "strings.json")
    gcx_dict = os.path.join(gcx, "gcx_dict.json")
    run(tool("gcx_pc_align.py"), pc_gcx, rus_gcx, strings, gcx_dict, os.path.join(gcx, "gcx_dict_report.txt"))
    run(tool("gcx_translate.py"), pc_gcx, rus_gcx, strings, gcx_dict, os.path.join(gcx, "gcx_manual.json"),
        os.path.join(gcx, "gcx_ru.json"), os.path.join(gcx, "gcx_todo.txt"))

    codec_dat = os.path.join(WORK, "ps2", "CODEC.DAT")
    run(tool("isols.py"), iso, "/MGS/CODEC.DAT", codec_dat)
    codec_strings = os.path.join(codec, "strings.json")
    run(tool("codec_dat.py"), codec_dat, codec_strings)
    pc_codec, rus_codec = (os.path.join(d, "fr", "codec", "_bp") for d in (pc, rus))
    run(tool("codec_align.py"), pc_codec, rus_codec, codec_strings, os.path.join(codec, "codec_dict.json"),
        os.path.join(codec, "align_report.txt"))
    print("prepared; now run: build_ru.py", iso, "OUT.iso")


if __name__ == "__main__":
    main()
