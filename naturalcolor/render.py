"""Shared render steps used by the CLI and the UI.

    load_camera raw / image file -> white-balanced camera RGB (crop, demosaic) + info
    develop     camera RGB -> linear sRGB base (white balance, matrix, exposure)
    load_base   load_camera + develop
    export      camera RGB -> file in one banded pass (develop, look, encode,
                quantise): no full-size floating-point intermediates
    apply_look  base -> display-linear Image for one pipeline
    encode      display-linear -> output code values 0..1
    save        code values -> JPEG / TIFF on disk, tagged with the output's ICC profile
"""
from __future__ import annotations
from pathlib import Path

import numpy as np

from . import parallel
from .io.image import Image
from .paths import PARAMS
from .vault import data as vdata

PIPELINES = ("camera", "studio")
PROFILES = ("srgb", "adobe", "p3", "pq")
IMAGE_EXT = (".tif", ".tiff", ".jpg", ".jpeg", ".png")


def resolve_params(p):
    """A params path as given, else relative to the repository's params/ dir.

    Sealed builds keep `0044.json.ncs` next to where `0044.json` would be; the
    logical `.json` path is returned either way.
    """
    if p is None:
        return None
    path = Path(p)
    if vdata.exists(path):
        return path
    for cand in (PARAMS / path.name, PARAMS.parent / path):
        if vdata.exists(cand):
            return cand
    return path


def default_params(pipeline):
    return {"camera": "0125.json", "studio": "post_0125.json"}[pipeline]


def load_input(path, demosaic="ours", half=True):
    """File -> (camera RGB, info). info["matrix"] is set when it is already known.

    Any Bayer raw goes through the same path: the CFA layout and the image area
    come from the file (RGGB on the overwhelming majority of sensors), there is
    no per-format branch.
    """
    from PIL import Image as PILImage
    from .core_api import require_core
    require_core()                      # the matrix and the encoders live in the core
    if Path(path).suffix.lower() in IMAGE_EXT:
        from .color.profiles import srgb_eotf
        PILImage.MAX_IMAGE_PIXELS = None
        im = np.asarray(PILImage.open(path).convert("RGB")).astype(np.float64)/255.
        return srgb_eotf(im), {"matrix": np.eye(3)}
    if demosaic == "ours":
        from .io.demosaic import load_demosaiced
        cam, meta = load_demosaiced(path, half=half)
        return cam, {"meta": meta, "matrix": None}
    from generic_raw import load_linear_srgb
    lin, cam, M, meta = load_linear_srgb(path, half=half)
    return cam, {"meta": meta, "matrix": M}


def camera_matrix(path, hint=None, tags=None):
    """Camera -> linear sRGB matrix.

    The file's DNG `ColorMatrix` when the container carries one; otherwise the
    matrix is solved against LibRaw's own sRGB render (see io.matrix.from_file).
    """
    if hint is not None:
        return hint
    from .io.matrix import from_file
    return from_file(path, tags)


def load_camera(path, demosaic="ours", half=True):
    """File -> (white-balanced camera RGB, info): everything before the develop settings.

    info carries what `develop` needs: the camera -> linear sRGB matrix, the
    file's DNG `BaselineExposure` gain (1 when it has none) and, for a raw, the
    white-balance model ("wb", see color.whitebalance).  An already rendered
    image comes back as linear sRGB with an identity matrix and no WB model.
    """
    cam, info = load_input(path, demosaic, half=half)
    info["exposure_gain"], info["wb"] = 1.0, None
    if info.get("meta") is not None:            # a raw, not an already rendered image
        from .io.tags import read_tags, exposure_gain
        from .color.whitebalance import camera_wb
        tags = read_tags(path)
        info["exposure_gain"] = exposure_gain(tags)
        info["matrix"] = camera_matrix(path, info.get("matrix"), tags)
        meta = info["meta"]
        info["wb"] = camera_wb(tags, getattr(meta, "xyz_cam", None), meta.wb, info["matrix"])
    return np.asarray(cam, dtype=np.float64), info


def develop(cam, info, exposure=0.0, wb=None):
    """Camera RGB -> linear sRGB base, with the capture settings applied.

    wb: None for the camera's as-shot white balance, else (temperature K, tint).
    It scales the raw channels before the matrix, exactly as setting it in the
    camera would, so every later stage sees it as part of the capture.
    exposure: EV on top of the file's BaselineExposure, linear and before the look.
    """
    return parallel.map_rows(_develop_fn(info, exposure, wb), cam)


def _develop_fn(info, exposure=0.0, wb=None):
    """The develop step as a per-pixel function of camera RGB."""
    gains = None
    if wb is not None:
        if info.get("wb") is None:
            raise ValueError("white balance can only be set on a raw file")
        gains = info["wb"].gains(*wb)
    gain = info["exposure_gain"] * 2.0 ** float(exposure)
    M = info["matrix"]

    def band(c):
        x = c if gains is None else c * gains
        return np.clip(x @ M.T, 0, None) * gain

    return band


def load_base(path, demosaic="ours", half=True, exposure=0.0, wb=None):
    """File -> (linear sRGB base, info).

    The one place a raw becomes a base, used by the CLI, the UI, verify and
    calibration alike: image-area crop, demosaic, white balance, camera matrix,
    then exposure (the file's BaselineExposure plus `exposure` EV).
    """
    cam, info = load_camera(path, demosaic, half=half)
    return develop(cam, info, exposure, wb), info


def core_available() -> bool:
    """True when the colour core (plaintext or sealed) can be imported."""
    from .core_api import available
    return available()


def apply_look(base, pipeline="camera", params=None):
    """Linear sRGB base -> display-linear Image for the chosen look.

    Every look is per pixel, so large images are rendered in parallel row bands.
    """
    look = _look(pipeline, params)
    meta = look(base[:1, :1]).meta
    return Image(parallel.map_rows(lambda b: look(b).rgb, base), meta)


def _look(pipeline, params):
    """The chosen look as a function base -> Image."""
    from .core_api import require_core

    require_core()                      # one clear message when the core is absent
    from .model.camera import CameraModel
    from .model.post import PostModel
    if pipeline not in PIPELINES:
        raise ValueError(f"unknown look {pipeline!r}; choose from {', '.join(PIPELINES)}")
    p = resolve_params(params or default_params(pipeline))
    if pipeline == "camera":
        return CameraModel(p).render
    return PostModel(p).render


def encode(rgb, profile=None, hdr=False):
    """Display-linear sRGB -> (code values 0..1, profile name)."""
    fn, profile = _encoder(profile, hdr)
    return parallel.map_rows(fn, rgb), profile


def _encoder(profile=None, hdr=False):
    """(per-pixel encoder display-linear -> code values, profile name)."""
    from .color import profiles
    from .model.hdr import HDRRendition
    profile = "pq" if hdr else (profile or "srgb")
    if hdr:
        r = HDRRendition()
        return (lambda b: profiles.encode_pq(r.expand(b))), profile
    if profile == "pq":
        return profiles.encode_pq, profile
    return profiles.ENCODERS[profile], profile


def to_u8(code):
    return (np.clip(code, 0, 1)*255 + 0.5).astype(np.uint8)


def to_u16(code):
    return (np.clip(code, 0, 1)*65535 + 0.5).astype(np.uint16)


def is_tiff(output):
    return str(output).lower().endswith((".tif", ".tiff"))


def _quantizer(output, bits=16):
    """JPEG is always 8-bit; TIFF is `bits` per channel."""
    return to_u16 if is_tiff(output) and bits == 16 else to_u8


def save(code, output, profile="srgb", bits=16):
    """Write code values with the profile's ICC embedded; returns the array written.

    JPEG is always 8-bit (quality 94); TIFF is `bits` per channel, Deflate compressed.
    """
    arr = _quantizer(output, bits)(code)
    write(arr, output, profile)
    return arr


def write(arr, output, profile="srgb"):
    """Write an already quantised uint8/uint16 image with the profile's ICC embedded."""
    from .color.icc import for_profile
    icc = for_profile(profile)
    if is_tiff(output):
        from .io.tiff import write_rgb
        write_rgb(output, arr, icc=icc)
        return
    from PIL import Image as PILImage
    PILImage.fromarray(arr).save(output, quality=94, icc_profile=icc)


def export(cam, info, output, pipeline="camera", params=None,
           exposure=0.0, wb=None, profile=None, hdr=False, bits=16):
    """Camera RGB -> image file, every stage fused per row band.

    The same arithmetic as develop -> apply_look -> encode -> save, so the file
    is bit-identical, but only the final 8/16-bit image is ever full size: no
    floating-point base, look or code-value image is allocated for the frame.
    Returns (array written, profile name).
    """
    dev = _develop_fn(info, exposure, wb)
    look = _look(pipeline, params)
    enc, profile = _encoder(profile, hdr)
    quant = _quantizer(output, bits)
    fn = lambda c: quant(enc(look(dev(c)).rgb))
    arr = parallel.map_rows(fn, cam)
    write(arr, output, profile)
    return arr, profile
