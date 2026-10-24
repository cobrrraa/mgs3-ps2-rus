"""Write a file that no longer fits its place to the end of the MGS3 ISO (ISO9660 + UDF bridge).

The disc ends with the UDF anchor (AVDP) in its last sector. The new file data goes where that
anchor was, the anchor moves to the new last sector, and these are updated:
  - ISO9660: the file's directory record (extent LBA, size; both byte orders), volume space size;
  - UDF: the file's File Entry (information length, blocks recorded, short_ad), both Partition
    Descriptors (partition length), the anchor's own location; descriptor tags get new CRC/checksum.
The old copy of the file stays where it was (unused).

    relocate(iso_path, "/MGS/CODEC.DAT", data)
Usage: iso_relocate.py ISO /PATH/IN/ISO NEWFILE
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isols import SECTOR, read_sector  # noqa: E402

UDF_SCAN = range(0, 1024)  # sectors searched for UDF descriptors (all of them sit before the data)


def crc_itu(data):
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return crc


def fix_tag(desc):
    """Recompute a UDF descriptor tag's CRC and checksum in place."""
    crc_len = struct.unpack_from("<H", desc, 10)[0]
    struct.pack_into("<H", desc, 8, crc_itu(desc[16:16 + crc_len]))
    desc[4] = sum(desc[i] for i in range(16) if i != 4) & 0xFF


def find_record(f, path):
    """Absolute byte offset of the ISO9660 directory record of `path`."""
    pvd = read_sector(f, 16)
    want = [p.upper() for p in path.strip("/").split("/")]
    lba, size = struct.unpack_from("<I", pvd, 158)[0], struct.unpack_from("<I", pvd, 166)[0]
    for depth, part in enumerate(want):
        data = read_sector(f, lba, (size + SECTOR - 1) // SECTOR)
        pos = 0
        while pos < len(data):
            ln = data[pos]
            if ln == 0:
                pos = (pos // SECTOR + 1) * SECTOR
                continue
            name = data[pos + 33:pos + 33 + data[pos + 32]].decode("ascii", "replace").split(";")[0]
            if name.upper() == part:
                if depth == len(want) - 1:
                    return lba * SECTOR + pos
                lba, size = struct.unpack_from("<I", data, pos + 2)[0], struct.unpack_from("<I", data, pos + 10)[0]
                break
            pos += ln
        else:
            raise SystemExit(f"{path}: not found")
    raise SystemExit(f"{path}: not found")


def relocate(iso_path, path, data):
    with open(iso_path, "r+b") as f:
        pvd = bytearray(read_sector(f, 16))
        total = struct.unpack_from("<I", pvd, 80)[0]
        anchor = bytearray(read_sector(f, total - 1))
        assert struct.unpack_from("<H", anchor, 0)[0] == 2, "no UDF anchor in the last sector"
        rec = find_record(f, path)
        f.seek(rec)
        r = bytearray(f.read(34))
        old_lba, old_size = struct.unpack_from("<I", r, 2)[0], struct.unpack_from("<I", r, 10)[0]

        new_lba = total - 1
        nsec = (len(data) + SECTOR - 1) // SECTOR
        new_total = new_lba + nsec + 1
        f.seek(new_lba * SECTOR)
        f.write(data + b"\x00" * (nsec * SECTOR - len(data)))
        struct.pack_into("<I", anchor, 12, new_total - 1)
        fix_tag(anchor)
        f.write(anchor)
        f.truncate(new_total * SECTOR)

        struct.pack_into("<I", r, 2, new_lba)
        struct.pack_into(">I", r, 6, new_lba)
        struct.pack_into("<I", r, 10, len(data))
        struct.pack_into(">I", r, 14, len(data))
        f.seek(rec)
        f.write(r)
        struct.pack_into("<I", pvd, 80, new_total)
        struct.pack_into(">I", pvd, 84, new_total)
        f.seek(16 * SECTOR)
        f.write(pvd)

        part_start, fe_done, pd_done = None, 0, 0
        for s in UDF_SCAN:
            d = bytearray(read_sector(f, s))
            tag, loc = struct.unpack_from("<H", d, 0)[0], struct.unpack_from("<I", d, 12)[0]
            if tag == 5 and loc == s:  # Partition Descriptor
                part_start = struct.unpack_from("<I", d, 188)[0]
                struct.pack_into("<I", d, 192, new_total - 1 - part_start)
                fix_tag(d)
                f.seek(s * SECTOR)
                f.write(d)
                pd_done += 1
        assert part_start is not None and pd_done, "UDF partition descriptor not found"
        for s in UDF_SCAN:
            d = bytearray(read_sector(f, s))
            if struct.unpack_from("<H", d, 0)[0] != 261:  # File Entry
                continue
            l_ea, l_ad = struct.unpack_from("<II", d, 168)
            ad = 176 + l_ea
            ln, pos = struct.unpack_from("<II", d, ad)
            if l_ad == 8 and ln & 0x3FFFFFFF == old_size and pos == old_lba - part_start:
                struct.pack_into("<Q", d, 56, len(data))
                struct.pack_into("<Q", d, 64, nsec)
                struct.pack_into("<II", d, ad, (ln & 0xC0000000) | len(data), new_lba - part_start)
                fix_tag(d)
                f.seek(s * SECTOR)
                f.write(d)
                fe_done += 1
        assert fe_done == 1, f"UDF file entry for {path}: found {fe_done}"
    return old_lba, new_lba, new_total


def main():
    iso, path, src = sys.argv[1:4]
    old, new, total = relocate(iso, path, open(src, "rb").read())
    print(f"{path}: LBA {old} -> {new}, image {total} sectors ({total * SECTOR} bytes)")


if __name__ == "__main__":
    main()
