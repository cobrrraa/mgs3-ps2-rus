"""Build the Russian ISO from the original one in one go.

Usage: build_ru.py ORIGINAL.iso OUT.iso [--pc-file NAME ...]

Steps (all in place on the copy, file sizes and ISO layout unchanged):
  1. copy the original ISO
  2. patch SLUS_209.15 (single-byte 0x82-0xFF text, glyph range)          tools/exe_patch.py
  3. replace the font in all STAGE.DAT copies                              tools/stage_repack.py
  4. write Russian subtitles into DEMO.DAT, MOVIE.DAT and VOX.DAT           tools/apply_subs.py
     text = table, then work/subs/translations_new.json, edits.json, vox_auto.json, vox_edits.json,
     then phrase rules (vox_rules.json), then auto re-wrap of lines wider than the 512px
     subtitle texture (wraps.json)
  5. write Russian GCX strings (stage scripts: items, menus, hints) into STAGE.DAT  tools/gcx_apply.py
     (work/gcx/gcx_ru.json, built by tools/gcx_translate.py, then work/gcx/gcx_short.json: the
     resident weapon/item window texts shortened and re-wrapped by tools/gcx_short.py)
  6. rebuild CODEC.DAT with Russian codec text (tools/codec_build.py, work/codec/codec_dict.json,
     PC button icons replaced by PS2 button names by tools/codec_buttons.py, own fixes in
     work/codec/codec_manual.json, lines wider than the
     codec window re-wrapped by tools/codec_wrap.py);
     it grows, so it is moved to the end of the image (tools/iso_relocate.py) and the codec call
     IDs in the stage scripts are remapped in step 5 (--codec-layout)
"""
import argparse
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
WORK = os.path.join(ROOT, "work")


def run(*args):
    print(">", " ".join(os.path.basename(a) if a.endswith(".py") else a for a in args), flush=True)
    subprocess.run([sys.executable, "-E", *args], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("original")
    ap.add_argument("out")
    ap.add_argument("--pc-file", nargs="*", default=[], help="only these cutscenes (PC .sdt names)")
    args = ap.parse_args()

    if os.path.abspath(args.original) == os.path.abspath(args.out):
        sys.exit("refusing to build over the original ISO")
    print("copying ISO...", flush=True)
    shutil.copyfile(args.original, args.out)

    slus = os.path.join(WORK, "ps2", "SLUS_209.15")
    run(os.path.join(TOOLS, "isols.py"), args.original, "/SLUS_209.15", slus)
    run(os.path.join(TOOLS, "exe_patch.py"), slus, slus + ".patched", args.out)

    font_orig = os.path.join(WORK, "stage", "init", "resident_383c45.raw")
    font_ru = os.path.join(WORK, "font", "383c45_ru.raw")
    run(os.path.join(TOOLS, "make_font.py"), font_orig, font_ru, os.path.join(WORK, "font", "preview_ru.png"))
    run(os.path.join(TOOLS, "stage_repack.py"), args.out, "all", "383c45.raw", font_ru)

    subs = os.path.join(WORK, "subs")
    table = os.path.join(subs, "subs_ps2_ru.csv")
    overrides = [os.path.join(subs, name) for name in
                 ("translations_new.json", "edits.json", "vox_auto.json", "vox_edits.json")]
    rules = os.path.join(subs, "vox_rules.json")
    run(os.path.join(TOOLS, "text_rules.py"), table, "VOX.DAT", rules, *overrides)
    wraps = os.path.join(subs, "wraps.json")
    run(os.path.join(TOOLS, "autowrap.py"), font_ru, table, wraps, *overrides, rules)
    vox_blocks = os.path.join(subs, "vox_blocks.json")
    if not os.path.exists(vox_blocks):
        run(os.path.join(TOOLS, "vox_blocks.py"), args.original, vox_blocks)
    cmd = [os.path.join(TOOLS, "apply_subs.py"), args.out, table, os.path.join(subs, "ps2_en.jsonl"),
           "--overrides", *overrides, rules, wraps, "--vox-blocks", vox_blocks]
    if args.pc_file:
        cmd += ["--pc-file", *args.pc_file]
    run(*cmd)

    codec = os.path.join(WORK, "codec")
    codec_orig = os.path.join(WORK, "ps2", "CODEC.DAT")
    if not os.path.exists(codec_orig):
        run(os.path.join(TOOLS, "isols.py"), args.original, "/MGS/CODEC.DAT", codec_orig)
    codec_new, layout = os.path.join(codec, "CODEC_RU.DAT"), os.path.join(codec, "layout.json")
    codec_dict, codec_wraps = os.path.join(codec, "codec_dict.json"), os.path.join(codec, "codec_wraps.json")
    codec_buttons = os.path.join(codec, "codec_buttons.json")
    run(os.path.join(TOOLS, "codec_buttons.py"), codec_dict, codec_buttons)
    codec_manual = os.path.join(codec, "codec_manual.json")  # own fixes and translations
    codec_texts = [codec_dict, codec_buttons, codec_manual]
    run(os.path.join(TOOLS, "codec_wrap.py"), font_ru, *codec_texts, codec_wraps)
    run(os.path.join(TOOLS, "codec_build.py"), codec_orig, *codec_texts, codec_wraps, codec_new, layout)
    run(os.path.join(TOOLS, "iso_relocate.py"), args.out, "/MGS/CODEC.DAT", codec_new)

    gcx = os.path.join(WORK, "gcx")
    run(os.path.join(TOOLS, "gcx_short.py"), font_ru, os.path.join(gcx, "ps2", "r_sna01_180720.gcx"),
        os.path.join(gcx, "gcx_ru.json"), os.path.join(gcx, "gcx_short_manual.json"),
        os.path.join(gcx, "gcx_short.json"))
    run(os.path.join(TOOLS, "gcx_apply.py"), args.out, os.path.join(gcx, "gcx_ru.json"),
        os.path.join(gcx, "gcx_short.json"), "--codec-layout", layout)
    print("done:", args.out)


if __name__ == "__main__":
    main()
