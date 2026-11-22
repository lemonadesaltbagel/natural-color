"""Shared render steps used by the CLI and the UI.

    load_camera raw / image file -> white-balanced camera RGB (crop, demosaic) + info
    develop     camera RGB -> linear sRGB base (white balance, matrix, exposure)
    load_base   load_camera + develop
    apply_look  base -> display-linear Image for one pipeline
    encode      display-linear -> output code values 0..1
    save        code values -> JPEG / TIFF on disk, tagged with the output's ICC profile
"""
from __future__ import annotations
from pathlib import Path

import numpy as np

from .paths import PARAMS
from .vault import data as vdata

PIPELINES = ("camera", "studio", "studio-lut", "portable")
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
    return {"camera": "0125.json", "portable": "0125.json",
            "studio": "post_0125.json", "studio-lut": "post_lut_0125.json"}[pipeline]


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
    x = cam
    if wb is not None:
        if info.get("wb") is None:
            raise ValueError("white balance can only be set on a raw file")
        x = cam * info["wb"].gains(*wb)
    gain = info["exposure_gain"] * 2.0 ** float(exposure)
    return np.clip(x @ info["matrix"].T, 0, None) * gain


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


def apply_look(base, pipeline="camera", params=None, colormap=None, table=None):
    """Linear sRGB base -> display-linear Image for the chosen pipeline.

    colormap / table pick the colour profile and CbCr table for studio-lut.
    """
    from .core_api import require_core

    require_core()                      # one clear message when the core is absent
    from .model.camera import CameraModel
    from .model.post import PostModel
    from .model.portable import PortableLook
    p = resolve_params(params or default_params(pipeline))
    if pipeline == "camera":
        return CameraModel(p).render(base)
    if pipeline in ("studio", "studio-lut"):
        from .color import lut3d
        key = "mt" if "0044" in p.name else "mf"
        mode = "calibrated" if pipeline == "studio" else "extracted"
        model = PostModel(p, key=key, colormap=colormap or lut3d.default_colormap(),
                          table=table or lut3d.DEFAULT_TABLE)
        return model.render(base, mode=mode)
    if pipeline == "portable":
        model = CameraModel(p)
        look = PortableLook(type("L", (), {"apply": staticmethod(model.apply)})())
        return look.render(np.clip(base, 0, None))
    raise ValueError(f"unknown pipeline {pipeline!r}")


def encode(rgb, profile=None, hdr=False):
    """Display-linear sRGB -> (code values 0..1, profile name)."""
    from .color import profiles
    from .model.hdr import HDRRendition
    profile = "pq" if hdr else (profile or "srgb")
    if hdr:
        return profiles.encode_pq(HDRRendition().expand(rgb)), profile
    if profile == "pq":
        return profiles.encode_pq(rgb), profile
    return profiles.ENCODERS[profile](rgb), profile


def to_u8(code):
    return (np.clip(code, 0, 1)*255 + 0.5).astype(np.uint8)


def to_u16(code):
    return (np.clip(code, 0, 1)*65535 + 0.5).astype(np.uint16)


def is_tiff(output):
    return str(output).lower().endswith((".tif", ".tiff"))


def save(code, output, profile="srgb", bits=16):
    """Write code values with the profile's ICC embedded; returns the array written.

    JPEG is always 8-bit (quality 94); TIFF is `bits` per channel, Deflate compressed.
    """
    from .color.icc import for_profile
    icc = for_profile(profile)
    if is_tiff(output):
        from .io.tiff import write_rgb
        arr = to_u16(code) if bits == 16 else to_u8(code)
        write_rgb(output, arr, icc=icc)
        return arr
    from PIL import Image as PILImage
    arr = to_u8(code)
    PILImage.fromarray(arr).save(output, quality=94, icc_profile=icc)
    return arr
