"""TIFF/DNG tag reader (ColorMatrix, AsShotNeutral, BaselineExposure, DefaultCrop).

Every TIFF-shaped raw (DNG, 3FR, ARW, NEF, PEF, ...) is read the same way: IFD0
plus its SubIFDs, in either byte order, with the DNG tag semantics.  A file
that is not TIFF-shaped (CR3, RAF, ...) simply has no tags, and every caller
falls back to what LibRaw reports.
"""
from __future__ import annotations
import mmap
import struct
from pathlib import Path
import numpy as np

TAG_NAMES = {254: "subfile_type", 256: "w", 257: "h", 330: "subifd",
             50719: "crop_origin", 50720: "crop_size", 50721: "cm1", 50722: "cm2",
             50728: "neutral", 50730: "baseline_exposure", 50731: "baseline_noise",
             50732: "baseline_sharpness", 50778: "illuminant1", 50779: "illuminant2"}

# type -> (struct code per value, bytes per value); rationals are two codes
_TYPES = {1: ("B", 1), 3: ("H", 2), 4: ("I", 4), 5: ("I", 8), 6: ("b", 1),
          8: ("h", 2), 9: ("i", 4), 10: ("i", 8), 11: ("f", 4), 12: ("d", 8), 13: ("I", 4)}

# EXIF LightSource code -> correlated colour temperature (K), for picking the
# ColorMatrix calibrated nearest to daylight
ILLUMINANT_CCT = {1: 5500, 2: 4150, 3: 2856, 4: 5500, 9: 5500, 10: 6500, 11: 7500,
                  12: 6430, 13: 5000, 14: 4150, 15: 3450, 17: 2856, 18: 4874,
                  19: 6774, 20: 5503, 21: 6504, 22: 7504, 23: 5003, 24: 3200}
D65_CCT = 6504


def _ifd(data, off, bo):
    """One IFD -> {tag: [values]}; rationals become floats, bad entries are skipped."""
    n = struct.unpack_from(bo + "H", data, off)[0]
    out = {}
    for i in range(n):
        e = off + 2 + 12*i
        if e + 12 > len(data):
            break
        tag, typ, cnt = struct.unpack_from(bo + "HHI", data, e)
        if typ not in _TYPES:
            continue
        code, size = _TYPES[typ]
        nbytes = size * cnt
        voff = e + 8 if nbytes <= 4 else struct.unpack_from(bo + "I", data, e + 8)[0]
        if voff + nbytes > len(data):
            continue
        if typ in (5, 10):
            v = struct.unpack_from(f"{bo}{2*cnt}{code}", data, voff)
            out[tag] = [v[2*j] / v[2*j + 1] if v[2*j + 1] else 0.0 for j in range(cnt)]
        else:
            out[tag] = list(struct.unpack_from(f"{bo}{cnt}{code}", data, voff))
    return out


def _read_ifds(path):
    """(IFD0, [SubIFDs]) of a TIFF-shaped file; ({}, []) for anything else."""
    with open(path, "rb") as f:
        try:
            data = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        except ValueError:                      # empty file
            return {}, []
    with data:
        if len(data) < 8 or data[:4] not in (b"II*\0", b"MM\0*"):
            return {}, []
        bo = "<" if data[:2] == b"II" else ">"
        first = struct.unpack_from(bo + "I", data, 4)[0]
        if not 8 <= first < len(data):
            return {}, []
        ifd0 = _ifd(data, first, bo)
        subs = []
        for off in ifd0.get(330, []):
            if 8 <= off < len(data):
                try:
                    subs.append(_ifd(data, off, bo))
                except struct.error:
                    pass
        return ifd0, subs


def _raw_ifd(ifd0, subs):
    """The IFD holding the full-resolution raw (NewSubFileType 0) with a DefaultCrop."""
    cands = [d for d in (*subs, ifd0) if 50720 in d]
    full = [d for d in cands if d.get(254, [0])[0] == 0]
    return (full or cands or [{}])[0]


def read_tags(path):
    """Colour and framing metadata of any raw file; missing tags are simply absent."""
    try:
        ifd0, subs = _read_ifds(path)
    except (OSError, struct.error):
        return {}
    res = {}
    for tag, key in ((50721, "cm1"), (50722, "cm2")):
        if len(ifd0.get(tag, [])) == 9:
            res[key] = np.array(ifd0[tag], float).reshape(3, 3)
    for tag, key in ((50778, "illuminant1"), (50779, "illuminant2")):
        if ifd0.get(tag):
            res[key] = int(ifd0[tag][0])
    if len(ifd0.get(50728, [])) == 3:
        res["neutral"] = np.array(ifd0[50728], float)
    for tag, key in ((50730, "baseline_exposure"), (50732, "baseline_sharpness")):
        if ifd0.get(tag):
            res[key] = float(ifd0[tag][0])
    raw = _raw_ifd(ifd0, subs)
    origin, size = raw.get(50719, [0, 0]), raw.get(50720)
    if size and len(size) == 2 and len(origin) == 2:
        res["crop_origin"] = (int(round(origin[0])), int(round(origin[1])))
        res["crop_size"] = (int(round(size[0])), int(round(size[1])))
    return res


def color_matrix(tags):
    """The ColorMatrix calibrated nearest to D65 (DNG: CM2 is usually D65, CM1 StdA)."""
    mats = [(tags.get(f"illuminant{i}"), tags[f"cm{i}"]) for i in (1, 2) if f"cm{i}" in tags]
    if not mats:
        return None
    def distance(m):
        cct = ILLUMINANT_CCT.get(m[0])
        return abs(cct - D65_CCT) if cct else float("inf")
    return min(mats, key=distance)[1]       # ties (incl. untagged) keep CM1


def default_crop(tags):
    """(ox, oy, w, h) from DefaultCropOrigin/Size, or None."""
    if tags.get("crop_size"):
        return (*tags.get("crop_origin", (0, 0)), *tags["crop_size"])
    return None


def exposure_gain(path_or_tags):
    """Linear gain implied by DNG BaselineExposure (1.0 when the file has none)."""
    t = path_or_tags if isinstance(path_or_tags, dict) else read_tags(path_or_tags)
    return float(2.0 ** t.get("baseline_exposure", 0.0))
