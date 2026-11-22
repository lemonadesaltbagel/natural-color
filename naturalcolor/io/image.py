"""Minimal image container: linear-light float64 RGB plus metadata."""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np


@dataclass
class Image:
    """Scene-referred linear RGB (float64, no clipping)."""
    rgb: np.ndarray
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        a = np.asarray(self.rgb)
        if a.ndim != 3 or a.shape[2] != 3:
            raise ValueError(f"expected HxWx3, got {a.shape}")
        self.rgb = a.astype(np.float64, copy=False)

    @property
    def shape(self):
        return self.rgb.shape

    def luma(self, weights=(0.2126, 0.7152, 0.0722)):
        return self.rgb @ np.asarray(weights, dtype=np.float64)

    def copy(self, **meta):
        m = dict(self.meta); m.update(meta)
        return Image(self.rgb.copy(), m)

    def resized(self, w, h):
        from PIL import Image as PILImage
        out = np.stack([
            np.asarray(PILImage.fromarray(self.rgb[..., c].astype(np.float32), mode="F")
                       .resize((w, h), PILImage.LANCZOS))
            for c in range(3)], -1)
        return Image(out, dict(self.meta))

    def clipped(self, lo=0.0, hi=1.0):
        return Image(np.clip(self.rgb, lo, hi), dict(self.meta))
