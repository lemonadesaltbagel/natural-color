"""Baseline TIFF writer for 8- or 16-bit RGB with an embedded ICC profile.

Pillow cannot write 16 bits per channel RGB, so this writes the file directly:
little-endian, chunky RGB, Adobe Deflate with the horizontal predictor, one
IFD.  Strips are compressed in parallel (zlib releases the GIL).
"""
from __future__ import annotations
import struct, zlib
from concurrent.futures import ThreadPoolExecutor

import numpy as np

SHORT, LONG, RATIONAL, ASCII, UNDEFINED = 3, 4, 5, 2, 7
_SIZE = {SHORT: 2, LONG: 4, RATIONAL: 8, ASCII: 1, UNDEFINED: 1}
STRIP_BYTES = 1 << 20


def _predict(a):
    """TIFF predictor 2: horizontal differences per channel, modulo the sample size."""
    d = a.copy()
    d[:, 1:] -= a[:, :-1]
    return d


def write_rgb(path, rgb, icc=None, compress=True, software="Natural Color", level=6):
    """rgb: HxWx3 uint8 or uint16 array."""
    a = np.ascontiguousarray(rgb)
    if a.ndim != 3 or a.shape[2] != 3 or a.dtype not in (np.uint8, np.uint16):
        raise ValueError(f"expected HxWx3 uint8/uint16, got {a.shape} {a.dtype}")
    a = a.astype(a.dtype.newbyteorder("<"), copy=False)
    h, w = a.shape[:2]
    bits = a.dtype.itemsize * 8
    rows = max(1, STRIP_BYTES // (w * 3 * a.dtype.itemsize))
    bands = [a[y:y + rows] for y in range(0, h, rows)]
    if compress:
        with ThreadPoolExecutor() as pool:
            strips = list(pool.map(lambda b: zlib.compress(_predict(b).tobytes(), level), bands))
    else:
        strips = [b.tobytes() for b in bands]

    # layout: header | strips | out-of-line tag values | IFD
    out = bytearray(b"II*\0\0\0\0\0")
    offsets = []
    for s in strips:
        offsets.append(len(out))
        out += s
        if len(out) % 2:
            out += b"\0"

    tags = [
        (256, LONG, [w]), (257, LONG, [h]), (258, SHORT, [bits] * 3),
        (259, SHORT, [8 if compress else 1]), (262, SHORT, [2]),
        (273, LONG, offsets), (277, SHORT, [3]), (278, LONG, [rows]),
        (279, LONG, [len(s) for s in strips]),
        (282, RATIONAL, [(300, 1)]), (283, RATIONAL, [(300, 1)]),
        (284, SHORT, [1]), (296, SHORT, [2]),
        (305, ASCII, software.encode("ascii") + b"\0"),
    ]
    if compress:
        tags.append((317, SHORT, [2]))
    tags.append((339, SHORT, [1] * 3))
    if icc:
        tags.append((34675, UNDEFINED, bytes(icc)))

    def pack(typ, vals):
        if typ in (ASCII, UNDEFINED):
            return bytes(vals)
        if typ == RATIONAL:
            return b"".join(struct.pack("<II", *v) for v in vals)
        return struct.pack("<%d%s" % (len(vals), "H" if typ == SHORT else "I"), *vals)

    entries = []
    for tag, typ, vals in tags:
        data = pack(typ, vals)
        count = len(data) // _SIZE[typ]
        if len(data) <= 4:
            entries.append(struct.pack("<HHI", tag, typ, count) + data.ljust(4, b"\0"))
        else:
            entries.append(struct.pack("<HHII", tag, typ, count, len(out)))
            out += data
            if len(out) % 2:
                out += b"\0"
    ifd = len(out)
    if ifd >= 1 << 32:
        raise ValueError("image too large for a classic TIFF (4 GB)")
    out += struct.pack("<H", len(entries)) + b"".join(entries) + struct.pack("<I", 0)
    out[4:8] = struct.pack("<I", ifd)
    with open(path, "wb") as f:
        f.write(out)


def read_rgb(path):
    """Baseline chunky RGB TIFF -> (HxWx3 uint8/uint16 array, ICC bytes or None).

    Pillow reads 16-bit RGB as 8 bits, which is ruinous for PQ shadows, so the
    strips are read directly: either byte order, uncompressed (memory-mapped)
    or Deflate with or without the horizontal predictor.
    """
    import mmap
    with open(path, "rb") as f:
        data = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    bo = {b"II": "<", b"MM": ">"}.get(data[:2])
    if bo is None or struct.unpack_from(bo + "H", data, 2)[0] != 42:
        raise ValueError(f"{path}: not a classic TIFF")
    ifd = struct.unpack_from(bo + "I", data, 4)[0]
    tags = {}
    for i in range(struct.unpack_from(bo + "H", data, ifd)[0]):
        tag, typ, cnt = struct.unpack_from(bo + "HHI", data, ifd + 2 + 12*i)
        size = {1: 1, 2: 1, 3: 2, 4: 4, 7: 1}.get(typ)
        if size is None:
            continue
        off = ifd + 10 + 12*i if size*cnt <= 4 else struct.unpack_from(bo + "I", data, ifd + 10 + 12*i)[0]
        if typ in (3, 4):
            tags[tag] = list(struct.unpack_from(f"{bo}{cnt}{'H' if typ == 3 else 'I'}", data, off))
        else:
            tags[tag] = bytes(data[off:off + cnt])
    w, h = tags[256][0], tags[257][0]
    bits, spp = tags.get(258, [8])[0], tags.get(277, [1])[0]
    comp, pred = tags.get(259, [1])[0], tags.get(317, [1])[0]
    if spp < 3 or bits not in (8, 16) or tags.get(284, [1])[0] != 1 or comp not in (1, 8, 32946):
        raise ValueError(f"{path}: unsupported TIFF layout (spp={spp} bits={bits} compression={comp})")
    dt = np.dtype(bo + ("u2" if bits == 16 else "u1"))
    rows = tags.get(278, [h])[0]
    out = np.empty((h, w, spp), dt.newbyteorder("="))
    for k, (off, n) in enumerate(zip(tags[273], tags[279])):
        y0 = k * rows
        nrow = min(rows, h - y0)
        buf = data[off:off + n] if comp == 1 else zlib.decompress(data[off:off + n])
        strip = np.frombuffer(buf, dt, count=nrow * w * spp).reshape(nrow, w, spp)
        if pred == 2:
            strip = np.cumsum(strip, axis=1, dtype=strip.dtype)
        out[y0:y0 + nrow] = strip
    data.close()
    return out[..., :3], tags.get(34675)
