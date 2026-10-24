"""Python port of Shagohod's MGS3 (PS2) STAGE.DAT reader.

Usage:
    stagedat.py list ISO [EXT]                  -> list files of every stage page (optionally only EXT)
    stagedat.py extract ISO STAGE OUTDIR [EXT]  -> extract files of one stage page
    stagedat.py slot-list / slot-extract ...    -> same for SLOT.DAT (pages are numbered)

STAGE.DAT layout:
    header: u32 timestamp, then 12 bytes encrypted (version, pageSize, numPages, ...)
    page table: numPages * (char name[8], u32 sector) encrypted, same key stream continues
    page: CNF header (u32 numTags, numTags * (u32 id, i32 offset)) encrypted with
          keyA = strcode(stage name), keyB = timestamp; then sector-aligned sections,
          optionally XOR-encrypted + zlib-compressed.
"""
import os
import struct
import sys
import zlib

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isols import list_iso, SECTOR  # noqa: E402

KEY = 0x02E90EDD
M = 0xFFFFFFFF

EXT = {0x02: "gcx", 0x26: "bhv", 0x03: "tri", 0x12: "zon", 0x22: "rcm", 0x08: "mtar", 0x23: "gnv",
       0x0B: "mtcm", 0x07: "cv2", 0x05: "mds", 0x15: "hzt", 0x16: "hz2", 0x06: "lt2", 0x20: "cvg",
       0x25: "rpd", 0x0C: "geom", 0x1D: "cvd", 0x1F: "mtra", 0x04: "mdh", 0x19: "nhz", 0x0D: "mdl",
       0x0E: "mdb", 0x18: "eft", 0x1E: "sar", 0x09: "mtsq", 0x14: "row", 0x1C: "mtz", 0xFF: "psq",
       0x60: "slot", 0x01: "bin", 0x0F: "nav", 0x17: "fnt", 0x24: "sta", 0x11: "eft", 0x21: "efg",
       0x0A: "far", 0x13: "rpd", 0x1B: "mtn", 0x10: "cvd", 0x1A: "trz", 0x5F: "la2", 0x6B: "rat",
       0x69: "img", 0x68: "var", 0x6E: "raw", 0x5E: "ico", 0x6C: "rcm"}
REGION = {0x00000000: "end", 0x00010000: "nocache", 0x2: "cache", 0x3: "resident",
          0x4: "delayload", 0x5: "delayload_w", 0x10: "sound"}


def strcode(s):
    h = 0
    for c in s.encode():
        h = ((h >> 19) | (h << 5)) & M
        h = (h + c) & 0xFFFFFF
    return h or 1


def keystream(key_a, key_b, n):
    """n words of the LCG key stream (vectorised by repeated doubling)."""
    out = np.empty(n, dtype=np.uint32)
    if n == 0:
        return out, key_a
    out[0] = key_a
    filled = 1
    # step coefficients for advancing `filled` positions: k' = A*k + B
    A, B = KEY, key_b
    with np.errstate(over="ignore"):
        while filled < n:
            take = min(filled, n - filled)
            out[filled:filled + take] = out[:take] * np.uint32(A) + np.uint32(B)
            filled += take
            A, B = (A * A) & M, (A * B + B) & M
    nxt = (int(out[-1]) * KEY + key_b) & M
    return out, nxt


def decode_buffer(key_a, key_b, buf):
    n = len(buf) // 4
    ks, nxt = keystream(key_a, key_b, n)
    words = np.frombuffer(buf[:n * 4], dtype="<u4") ^ ks
    return words.astype("<u4").tobytes() + bytes(buf[n * 4:]), nxt


def decode_page(buf):
    salt = struct.unpack_from("<H", buf)[0] ^ 0x9385
    key_a = (((salt ^ 0x6576) << 16) | salt) & M
    key_b = (salt * 0x0116) & M
    out, _ = decode_buffer(key_a, key_b, buf)
    return b"\x78\x9c" + out[2:]


def cnf_keys(name, timestamp):
    salt_a = strcode(name)

    def mk(a, b):
        return ((b << 7) + b + a) & M

    return (mk(0xA78925D9, salt_a) + timestamp) & M, mk(0x7A88FB59, salt_a)


class StageDat:
    def __init__(self, iso):
        self.iso = iso
        _, self.lba, self.size = next(e for e in list_iso(iso) if e[0].upper() == "/MGS/STAGE.DAT")
        self.f = open(iso, "rb")
        hdr = self.read(0, 16)
        self.timestamp = struct.unpack_from("<I", hdr)[0]
        key_a, key_b = self.timestamp, self.timestamp ^ 0xF0F0
        dec, key_a = decode_buffer(key_a, key_b, hdr[4:16])
        self.version, self.page_size, self.num_pages = struct.unpack_from("<HHH", dec)
        table, _ = decode_buffer(key_a, key_b, self.read(16, 12 * self.num_pages))
        self.pages = []
        for i in range(self.num_pages):
            name = table[i * 12:i * 12 + 8].split(b"\0")[0].decode("ascii", "replace")
            sector = struct.unpack_from("<I", table, i * 12 + 8)[0]
            self.pages.append((name, sector * SECTOR))

    def read(self, off, n):
        self.f.seek(self.lba * SECTOR + off)
        return self.f.read(n)

    def page_bytes(self, i):
        name, off = self.pages[i]
        end = self.pages[i + 1][1] if i + 1 < self.num_pages else self.size
        return name, bytearray(self.read(off, end - off))

    def files(self, i, want_ext=None, with_data=False):
        """Yield (region, filename, data_or_None) for page i."""
        name, data = self.page_bytes(i)
        key_a, key_b = cnf_keys(name, self.timestamp)
        n_tags = struct.unpack("<I", decode_buffer(key_a, key_b, bytes(data[:4]))[0])[0]
        hdr_size = 4 + 8 * n_tags
        if n_tags > 100000 or hdr_size > len(data):
            raise ValueError(f"bad CNF header in page {name}")
        data[:hdr_size], _ = decode_buffer(key_a, key_b, bytes(data[:hdr_size]))
        yield from cnf_files(data, want_ext, with_data)


class SlotDat:
    """SLOT.DAT: plaintext header (u32 ts, u16 ver, u16 pageSize, u16 numPages, ...),
    pages back to back from sector 1, each with an unencrypted CNF header."""

    def __init__(self, iso, path="/MGS/SLOT.DAT"):
        _, self.lba, self.size = next(e for e in list_iso(iso) if e[0].upper() == path)
        self.f = open(iso, "rb")
        hdr = self.read(0, 16)
        self.timestamp, self.version, self.page_size, self.num_pages = struct.unpack_from("<IHHH", hdr)
        self.pages = []
        off = SECTOR
        for i in range(self.num_pages):
            n_tags = struct.unpack("<I", self.read(off, 4))[0]
            tags = self.read(off + 4, 8 * n_tags)
            size = 4 + 8 * n_tags
            size += (-size) % SECTOR
            for t in range(n_tags):
                tid, toff = struct.unpack_from("<Ii", tags, 8 * t)
                if tid >> 24 == 0x7F and tid & 0xFFFFFF:
                    size += toff + (-toff) % SECTOR
            self.pages.append((str(i), off, size))
            off += size

    def read(self, off, n):
        self.f.seek(self.lba * SECTOR + off)
        return self.f.read(n)

    def files(self, i, want_ext=None, with_data=False):
        _, off, size = self.pages[i]
        yield from cnf_files(bytearray(self.read(off, size)), want_ext, with_data)


def cnf_files(data, want_ext=None, with_data=False):
    """Walk a decrypted CNF page; yield (region, filename, data_or_size)."""
    n_tags = struct.unpack_from("<I", data)[0]
    hdr_size = 4 + 8 * n_tags
    tags = [struct.unpack_from("<Ii", data, 4 + 8 * t) for t in range(n_tags)]
    ptr = hdr_size
    section = b""
    section_size = 0
    enc_size = 0
    region = ""
    for t in range(n_tags - 1):
        tid, toff = tags[t]
        kind = tid >> 24
        if kind == 0x7F:
            flag = tid & 0xFFFFFF
            if flag:
                region = REGION.get(flag, hex(flag))
                section_size = toff
                ptr += (-ptr) % SECTOR
                section = data[ptr:]
            else:
                ptr += enc_size if enc_size else toff
                enc_size = 0
        elif kind == 0x7E:
            enc_size = tid & 0xFFFFFF
            if with_data:
                raw = decode_page(bytes(section[:enc_size]))
                # raw deflate: the Adler-32 trailer is not reliable after decryption
                section = zlib.decompressobj(-15).decompress(raw[2:], section_size)
        elif kind in (0x00, 0x7D):
            continue
        else:
            ext = EXT.get(kind, f"x{kind:02x}")
            fname = f"{tid & 0xFFFFFF:06x}.{ext}"
            if want_ext and ext != want_ext:
                continue
            nxt = tags[t + 1][1]
            size = max(0, nxt - toff)
            yield region, fname, (bytes(section[toff:toff + size]) if with_data else size)


def main():
    cmd, iso = sys.argv[1:3]
    if cmd.startswith("slot-"):
        cmd, sd = cmd[5:], SlotDat(iso)
    else:
        sd = StageDat(iso)
    if cmd == "list":
        want = sys.argv[3] if len(sys.argv) > 3 else None
        print(f"timestamp={sd.timestamp:#x} version={sd.version} pages={sd.num_pages}")
        for i, (name, *_) in enumerate(sd.pages):
            try:
                for region, fname, size in sd.files(i, want):
                    print(f"{name:10s} {region:12s} {fname:16s} {size}")
            except Exception as e:  # keep listing other pages
                print(f"{name:10s} ERROR {e}")
    elif cmd == "extract":
        stage, outdir = sys.argv[3:5]
        want = sys.argv[5] if len(sys.argv) > 5 else None
        i = next(k for k, (n, *_) in enumerate(sd.pages) if n == stage)
        os.makedirs(outdir, exist_ok=True)
        for region, fname, blob in sd.files(i, want, with_data=True):
            path = os.path.join(outdir, f"{region}_{fname}")
            with open(path, "wb") as o:
                o.write(blob)
            print(path, len(blob))


if __name__ == "__main__":
    main()
