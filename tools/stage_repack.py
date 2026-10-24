"""Replace a file inside STAGE.DAT in place (same file size), re-compressing and re-encrypting
its section so that the section's encrypted size and every header stay untouched.

Usage: stage_repack.py ISO STAGE FILE NEW_FILE      e.g. stage_repack.py test.iso init 383c45.raw font.raw
       stage_repack.py ISO all   FILE NEW_FILE      -> every stage that contains FILE

Section encryption (see stagedat.decode_page): the stored first u16 is the key salt; the whole
buffer (full words only) is XORed with the LCG key stream and bytes 0..1 are then forced to 78 9C.
So encrypting = XOR with the same stream, then putting the salt back into bytes 0..1.
"""
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stagedat as S  # noqa: E402
from isols import SECTOR  # noqa: E402


def page_header(sd, i):
    """(page bytes, cnf keys, decrypted tags) of page i."""
    name, data = sd.page_bytes(i)
    ka, kb = S.cnf_keys(name, sd.timestamp)
    n = struct.unpack("<I", S.decode_buffer(ka, kb, bytes(data[:4]))[0])[0]
    hdr, _ = S.decode_buffer(ka, kb, bytes(data[:4 + 8 * n]))
    return data, (ka, kb), [list(struct.unpack_from("<Ii", hdr, 4 + 8 * t)) for t in range(n)]


def page_layout(sd, i):
    """Decrypted CNF tags of page i with the section each file belongs to.
    Sections carry the tag indices of their start / end tags; files carry their tag index."""
    data, _, tags = page_header(sd, i)
    n = len(tags)
    sections, files = [], {}
    ptr = 4 + 8 * n
    cur = None
    for t in range(n - 1):
        tid, toff = tags[t]
        kind = tid >> 24
        if kind == 0x7F:
            if tid & 0xFFFFFF:
                ptr += (-ptr) % SECTOR
                cur = {"ptr": ptr, "size": toff, "enc": 0, "region": tid & 0xFFFFFF, "start_tag": t}
                sections.append(cur)
            else:
                ptr += cur["enc"] or toff
                cur["end_tag"] = t
        elif kind == 0x7E:
            cur["enc"] = tid & 0xFFFFFF
        elif kind not in (0x00, 0x7D):
            fname = f"{tid & 0xFFFFFF:06x}.{S.EXT.get(kind, f'x{kind:02x}')}"
            files[fname] = (cur, toff, max(0, tags[t + 1][1] - toff), t)
    return data, sections, files


def compress(plain, limit):
    """zlib level 9, or zopfli when level 9 does not fit into `limit` bytes; None if neither fits."""
    stream = zlib.compress(plain, 9)
    if len(stream) > limit:
        import zopfli.zlib
        stream = zopfli.zlib.compress(plain, numiterations=5)
    return stream if len(stream) <= limit else None


def encrypt_section(plain, salt_bytes):
    salt = struct.unpack_from("<H", salt_bytes)[0] ^ 0x9385
    key_a = (((salt ^ 0x6576) << 16) | salt) & S.M
    key_b = (salt * 0x0116) & S.M
    enc, _ = S.decode_buffer(key_a, key_b, plain)
    return salt_bytes + enc[2:]


def replace_in_page(sd, iso_path, i, fname, new_blob):
    data, sections, files = page_layout(sd, i)
    if fname not in files:
        return False
    sec, foff, fsize, tag_idx = files[fname]
    if not sec["enc"]:
        raise SystemExit(f"{sd.pages[i][0]}: section of {fname} is not compressed (not supported yet)")
    grow = len(new_blob) - fsize
    if grow and tag_idx + 1 != sec["end_tag"]:
        raise SystemExit(f"{sd.pages[i][0]}: {fname} changes size but is not the last file of its section")
    if grow < 0:  # keep the old size; trailing zeros are harmless
        new_blob, grow = new_blob + b"\x00" * -grow, 0
    stored = bytes(data[sec["ptr"]:sec["ptr"] + sec["enc"]])
    plain_old = S.zlib.decompressobj(-15).decompress(S.decode_page(stored)[2:], sec["size"])
    assert len(plain_old) == sec["size"]
    plain_new = plain_old[:foff] + new_blob + plain_old[foff + fsize:]

    stream = compress(plain_new, sec["enc"])
    if stream is None:
        raise SystemExit(f"{sd.pages[i][0]}: recompressed section does not fit into {sec['enc']} bytes")
    padded = stream + b"\x00" * (sec["enc"] - len(stream))
    blob = encrypt_section(padded, stored[:2])

    # verify with the reader's own decryption before touching the ISO
    check = S.zlib.decompressobj(-15).decompress(S.decode_page(blob)[2:], len(plain_new))
    assert check == plain_new, "round trip failed"
    with open(iso_path, "r+b") as f:
        f.seek(sd.lba * SECTOR + sd.pages[i][1] + sec["ptr"])
        f.write(blob)
        if grow:  # the section got longer: its start and end tags hold the section size
            _, (ka, kb), tags = page_header(sd, i)
            for t in (sec["start_tag"], sec["end_tag"]):
                tags[t][1] += grow
            plain_hdr = struct.pack("<I", len(tags)) + b"".join(struct.pack("<Ii", *t) for t in tags)
            enc_hdr, _ = S.decode_buffer(ka, kb, plain_hdr)
            f.seek(sd.lba * SECTOR + sd.pages[i][1])
            f.write(enc_hdr)
    print(f"{sd.pages[i][0]:8s} {fname}: section {sec['size']}+{grow} B, "
          f"compressed {len(stream)} / {sec['enc']} B")
    return True


def main():
    iso, stage, fname, new_path = sys.argv[1:5]
    new_blob = open(new_path, "rb").read()
    sd = S.StageDat(iso)
    targets = range(sd.num_pages) if stage == "all" else \
        [k for k, p in enumerate(sd.pages) if p[0] == stage]
    done = [sd.pages[i][0] for i in targets if replace_in_page(sd, iso, i, fname, new_blob)]
    print("replaced in:", ", ".join(done) or "nothing")


if __name__ == "__main__":
    main()
