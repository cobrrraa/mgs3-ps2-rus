"""Minimal ISO9660 lister/extractor (no Joliet). Usage:
    isols.py ISO                 -> list all files with LBA and size
    isols.py ISO PATH OUTFILE    -> extract one file
"""
import struct
import sys

SECTOR = 2048


def read_sector(f, lba, count=1):
    f.seek(lba * SECTOR)
    return f.read(SECTOR * count)


def parse_dir(f, lba, size, prefix, out):
    data = read_sector(f, lba, (size + SECTOR - 1) // SECTOR)
    pos = 0
    while pos < len(data):
        ln = data[pos]
        if ln == 0:
            # skip to next sector boundary
            pos = (pos // SECTOR + 1) * SECTOR
            continue
        rec = data[pos:pos + ln]
        ext_lba = struct.unpack_from("<I", rec, 2)[0]
        ext_size = struct.unpack_from("<I", rec, 10)[0]
        flags = rec[25]
        name_len = rec[32]
        name = rec[33:33 + name_len]
        pos += ln
        if name in (b"\x00", b"\x01"):
            continue
        name = name.decode("ascii", "replace").split(";")[0]
        path = f"{prefix}/{name}"
        if flags & 2:
            parse_dir(f, ext_lba, ext_size, path, out)
        else:
            out.append((path, ext_lba, ext_size))


def list_iso(iso):
    with open(iso, "rb") as f:
        pvd = read_sector(f, 16)
        assert pvd[1:6] == b"CD001", "not ISO9660"
        root = pvd[156:156 + 34]
        lba = struct.unpack_from("<I", root, 2)[0]
        size = struct.unpack_from("<I", root, 10)[0]
        out = []
        parse_dir(f, lba, size, "", out)
        return out


def main():
    iso = sys.argv[1]
    files = list_iso(iso)
    if len(sys.argv) == 2:
        for path, lba, size in files:
            print(f"{lba:8d} {size:12d} {path}")
        return
    want = sys.argv[2].upper()
    for path, lba, size in files:
        if path.upper() == want:
            with open(iso, "rb") as f, open(sys.argv[3], "wb") as o:
                f.seek(lba * SECTOR)
                left = size
                while left:
                    chunk = f.read(min(left, 1 << 20))
                    o.write(chunk)
                    left -= len(chunk)
            print(f"extracted {path} ({size} bytes)")
            return
    sys.exit(f"not found: {want}")


if __name__ == "__main__":
    main()
