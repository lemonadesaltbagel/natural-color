"""Command line entry point."""
from __future__ import annotations
import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from naturalcolor.render import PIPELINES, PROFILES


def main(argv=None):
    ap = argparse.ArgumentParser(prog="natural colour")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("render", help="render a raw file")
    r.add_argument("--input", required=True)
    r.add_argument("--output", required=True)
    r.add_argument("--pipeline", default="camera", choices=PIPELINES)
    r.add_argument("--profile", default=None, choices=PROFILES)
    r.add_argument("--params", default=None)
    r.add_argument("--demosaic", default="ours", choices=("ours", "rawpy"))
    r.add_argument("--full", action="store_true")
    r.add_argument("--bits", type=int, default=16, choices=(8, 16), help="TIFF bits per channel")
    r.add_argument("--hdr", action="store_true")
    r.add_argument("--exposure", type=float, default=0.0, help="EV, on the raw before the look")
    r.add_argument("--temp", type=float, default=None, help="white balance K (raw only; default as shot)")
    r.add_argument("--tint", type=float, default=None, help="white balance tint, + = magenta (raw only)")
    r.add_argument("--colormap", default=None, help="studio-lut colour profile name")
    r.add_argument("--lut-table", default=None, help="studio-lut CbCr table, e.g. LUTTableTSRepro")
    r.add_argument("--colormaps", default=None, help="directory of colour-profile XMLs")

    v = sub.add_parser("verify", help="run the validation suite")
    v.add_argument("--width", type=int, default=972)
    v.add_argument("--refs", default=".", help="directory with the reference renders")
    v.add_argument("--raws", default=None, help="directory with the raw files (default: --refs)")

    u = sub.add_parser("ui", help="open the local web interface")
    u.add_argument("photo", nargs="?", help="raw or image file to open at start")
    u.add_argument("--full", action="store_true", help="decode the photo at full resolution")
    u.add_argument("--host", default="127.0.0.1")
    u.add_argument("--port", type=int, default=8765)
    u.add_argument("--no-browser", action="store_true")
    u.add_argument("--colormaps", default=None, help="directory of colour-profile XMLs")

    a = ap.parse_args(argv)
    from naturalcolor.core_api import CoreNotInstalled
    from naturalcolor.vault import VaultError
    try:
        return _run(a)
    except (CoreNotInstalled, VaultError) as e:     # no core, no key, or a tampered build
        print(f"error: {e}", file=sys.stderr)
        return 2


def _run(a):
    if getattr(a, "colormaps", None):
        import os
        from naturalcolor.paths import COLORMAPS_ENV
        os.environ[COLORMAPS_ENV] = os.pathsep.join(filter(None, (a.colormaps, os.environ.get(COLORMAPS_ENV))))
    if a.cmd == "render":
        return _render(a)
    if a.cmd == "verify":
        return _verify(a)
    if a.cmd == "ui":
        from naturalcolor.ui.server import serve
        return serve(a.host, a.port, open_browser=not a.no_browser, photo=a.photo, full=a.full)
    return 1


def _render(a):
    from naturalcolor import render
    cam, info = render.load_camera(a.input, a.demosaic, half=not a.full)
    wb = None
    if a.temp is not None or a.tint is not None:
        if info["wb"] is None:
            print("error: --temp/--tint need a raw file", file=sys.stderr)
            return 2
        shot_temp, shot_tint = info["wb"].as_shot()
        wb = (a.temp if a.temp is not None else shot_temp, a.tint if a.tint is not None else shot_tint)
    base = render.develop(cam, info, exposure=a.exposure, wb=wb)
    img = render.apply_look(base, a.pipeline, a.params, colormap=a.colormap, table=a.lut_table)
    code, profile = render.encode(img.rgb, a.profile, hdr=a.hdr)
    arr = render.save(code, a.output, profile, bits=a.bits)
    print(f"wrote {a.output} {arr.shape} {arr.dtype} ({a.pipeline}, {profile})")
    return 0


def _verify(a):
    try:
        from naturalcolor.verify import run
    except ImportError:
        print("verify is a development tool and is not part of a release build;\n"
              "it needs the vendor reference renders, which are not redistributed.")
        return 2
    return 0 if run(width=a.width, refs=a.refs, raws=a.raws) else 1   # 1: nothing compared


if __name__ == "__main__":
    raise SystemExit(main())
