"""Extract entries from a PCSX2 savestate (.p2s = zip with zstd-compressed members, method 93).
Usage: p2s_extract.py STATE.p2s OUTDIR [NAME ...]
"""
import os
import struct
import sys
import zipfile

import zstandard


def read_member(path, info):
    with open(path, "rb") as f:
        f.seek(info.header_offset)
        hdr = f.read(30)
        name_len, extra_len = struct.unpack_from("<HH", hdr, 26)
        f.seek(info.header_offset + 30 + name_len + extra_len)
        raw = f.read(info.compress_size)
    if info.compress_type == 0:
        return raw
    if info.compress_type == 93:
        return zstandard.ZstdDecompressor().decompress(raw, max_output_size=info.file_size)
    raise ValueError(f"unsupported compression {info.compress_type}")


def main():
    path, outdir, *names = sys.argv[1:]
    os.makedirs(outdir, exist_ok=True)
    for info in zipfile.ZipFile(path).infolist():
        if names and info.filename not in names:
            continue
        data = read_member(path, info)
        out = os.path.join(outdir, info.filename)
        with open(out, "wb") as o:
            o.write(data)
        print(out, len(data))


if __name__ == "__main__":
    main()
