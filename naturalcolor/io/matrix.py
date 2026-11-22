"""Camera -> linear sRGB matrix for a raw file (no external database)."""
from __future__ import annotations
import numpy as np


def from_file(path, tags=None):
    """Camera -> linear sRGB matrix, the same two steps for every raw.

    The file's own DNG `ColorMatrix` (the one calibrated nearest D65) when the
    container carries one; otherwise the matrix is solved against LibRaw's sRGB
    render.  Either way it is normalised to one white convention (camera
    neutral -> XYZ (1,1,1)), so a look behaves the same on every camera.
    """
    from ..color.matrices import camera_to_sRGB, normalise_sRGB_matrix
    from .tags import read_tags, color_matrix
    cm = color_matrix(read_tags(path) if tags is None else tags)
    if cm is not None:
        return camera_to_sRGB(cm)
    return normalise_sRGB_matrix(solve_against_libraw(path))


def libraw_srgb(path, half=True):
    import rawpy
    with rawpy.imread(str(path)) as raw:
        rgb = raw.postprocess(gamma=(1, 1), no_auto_bright=True, output_bps=16,
                              use_camera_wb=True, half_size=half,
                              output_color=rawpy.ColorSpace.sRGB,
                              demosaic_algorithm=rawpy.DemosaicAlgorithm.AHD)
    return rgb.astype(np.float64) / 65535.0


def solve_against_libraw(path, samples=400_000):
    """Least-squares camera->sRGB matrix from our demosaic and LibRaw's render."""
    from .demosaic import load_demosaiced
    cam, _ = load_demosaiced(path, half=True, crop=None)    # LibRaw renders the uncropped area
    ref = libraw_srgb(path, half=True)
    h = min(cam.shape[0], ref.shape[0]); w = min(cam.shape[1], ref.shape[1])
    x = cam[:h, :w].reshape(-1, 3); y = ref[:h, :w].reshape(-1, 3)
    rng = np.random.default_rng(0)
    idx = rng.choice(x.shape[0], min(samples, x.shape[0]), replace=False)
    xs, ys = x[idx], y[idx]
    m = (xs.max(1) > 0.005) & (xs.max(1) < 1.5) & (ys.max(1) < 0.85) & (ys.min(1) >= 0)
    if m.sum() < 1000:
        m = xs.max(1) > 1e-5
    mid = m & (ys.max(1) > 0.02) & (ys.max(1) < 0.6)
    if mid.sum() > 1000:
        xs = xs * (np.median(ys[mid], 0) / np.maximum(np.median(xs[mid], 0), 1e-6))
    M, *_ = np.linalg.lstsq(xs[m], ys[m], rcond=None)
    return M.T
