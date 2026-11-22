"""Row-band parallelism for the per-pixel and small-neighbourhood stages.

numpy ufuncs, BLAS and scipy.ndimage all release the GIL, so plain threads
scale across cores.  An image is cut into horizontal bands that are processed
independently: a per-pixel stage needs nothing else, a neighbourhood stage
reads a halo of extra rows around its band.  Each output pixel goes through
exactly the arithmetic it would whole-image, so the result is bit-identical.

NATURALCOLOR_THREADS=1 turns it off; small images (the UI preview) never pay
the thread overhead.
"""
from __future__ import annotations
import os
import threading
from concurrent.futures import ThreadPoolExecutor

import numpy as np

MIN_PIXELS = 2_000_000          # below this a single thread is faster
BAND_PIXELS = 1_000_000         # pixels per band: small enough to stay in cache-friendly sizes

_pool: ThreadPoolExecutor | None = None
_pool_lock = threading.Lock()
_inside = threading.local()      # set on pool threads: nested calls run serially


def workers() -> int:
    n = os.environ.get("NATURALCOLOR_THREADS")
    try:
        return max(1, int(n)) if n else (os.cpu_count() or 1)
    except ValueError:
        return os.cpu_count() or 1


def _executor() -> ThreadPoolExecutor:
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = ThreadPoolExecutor(workers(), thread_name_prefix="naturalcolor",
                                       initializer=lambda: setattr(_inside, "on", True))
        return _pool


def enabled(h: int, w: int) -> bool:
    return h * w >= MIN_PIXELS and workers() > 1 and not getattr(_inside, "on", False)


def bands(h: int, w: int, align: int = 1) -> list[tuple[int, int]]:
    """[(y0, y1)] covering 0..h; every y0 is a multiple of `align`."""
    rows = max(align, BAND_PIXELS // max(w, 1) // align * align)
    return [(y, min(y + rows, h)) for y in range(0, h, rows)]


def run(fn, items) -> list:
    """fn over items on the shared pool (serially when nested); keeps order, re-raises."""
    items = list(items)
    if getattr(_inside, "on", False) or len(items) < 2:
        return [fn(i) for i in items]
    return list(_executor().map(fn, items))


def map_rows(fn, x, align: int = 1, rows_out=lambda n: n):
    """fn applied to row bands of x and stacked along the rows.

    fn must treat rows independently in groups of `align` (a per-pixel stage
    has align=1; a 2x2 downsample has align=2 and rows_out=lambda n: n // 2).
    """
    x = np.asarray(x)
    h, w = x.shape[:2]
    if not enabled(h, w):
        return fn(x)
    bs = bands(h, w, align)
    first = fn(x[bs[0][0]:bs[0][1]])
    starts = np.cumsum([0] + [rows_out(b - a) for a, b in bs])
    out = np.empty((int(starts[-1]),) + first.shape[1:], first.dtype)
    out[:starts[1]] = first

    def one(i):
        a, b = bs[i]
        out[starts[i]:starts[i + 1]] = fn(x[a:b])

    run(one, range(1, len(bs)))
    return out
