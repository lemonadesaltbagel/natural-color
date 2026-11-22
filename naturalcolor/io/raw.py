"""Raw file access: metadata + bare CFA mosaic (no demosaic, no LibRaw render)."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np


@dataclass
class RawMeta:
    pattern: np.ndarray        # 2x2 CFA indices (0=R, 1=G, 2=B, 3=G2)
    black: np.ndarray          # per-CFA-position black level
    white: float
    wb: np.ndarray             # as-shot white balance gains
    flip: int                  # LibRaw orientation code
    width: int
    height: int
    crop: tuple | None = None  # (ox, oy, w, h) of the image area, sensor coordinates
    xyz_cam: np.ndarray | None = None  # LibRaw's XYZ -> camera matrix (zeros if unknown)


def read_raw(path) -> tuple[np.ndarray, RawMeta]:
    """Bare mosaic in sensor orientation, black subtracted, normalised to white."""
    import rawpy
    with rawpy.imread(str(path)) as raw:
        flip = int(raw.sizes.flip)
        mosaic = raw.raw_image_visible.astype(np.float64)
        black = np.asarray(raw.black_level_per_channel, dtype=np.float64)
        white = float(raw.white_level)
        wb = np.asarray(raw.camera_whitebalance[:3], dtype=np.float64)
        pat = np.asarray(raw.raw_pattern).copy()
        if pat.size != 4:                      # LibRaw may report a filters code
            pat = np.array([[0, 1], [3, 2]])
        pat = pat.reshape(2, 2)
        h, w = mosaic.shape
        crop = _crop(raw.sizes, path, w, h)
        xyz_cam = np.asarray(raw.rgb_xyz_matrix, dtype=np.float64)[:3].copy()
    idx = np.tile(pat, (h//2 + 1, w//2 + 1))[:h, :w]
    bl = np.zeros_like(mosaic)
    for k, v in enumerate(black):
        bl[idx == k] = v
    mosaic = (mosaic - bl) / max(white - float(black.mean()), 1.0)
    meta = RawMeta(pattern=pat, black=black, white=white, wb=wb, flip=flip,
                   width=w, height=h, crop=crop, xyz_cam=xyz_cam)
    return np.clip(mosaic, 0, None), meta


def _crop(sizes, path, w, h):
    """Image area inside the visible mosaic, the same way for every format.

    LibRaw's inset crop (raw coordinates) when it knows one, otherwise the DNG
    DefaultCrop tags (relative to the visible / active area); None when neither
    exists or the result does not fit.
    """
    from .tags import read_tags, default_crop
    crop = None
    if getattr(sizes, "crop_width", 0) and getattr(sizes, "crop_height", 0):
        crop = (sizes.crop_left_margin - sizes.left_margin,
                sizes.crop_top_margin - sizes.top_margin,
                sizes.crop_width, sizes.crop_height)
    else:
        crop = default_crop(read_tags(path))
    if crop is None:
        return None
    ox, oy, cw, ch = (int(v) for v in crop)
    if ox < 0 or oy < 0 or cw <= 0 or ch <= 0 or ox + cw > w or oy + ch > h:
        return None
    if (ox, oy, cw, ch) == (0, 0, w, h):
        return None
    return ox, oy, cw, ch
