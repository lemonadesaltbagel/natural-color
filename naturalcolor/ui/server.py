"""Local web interface: a stdlib HTTP server around naturalcolor.render.

A session keeps the decoded photo in white-balanced camera space, so the
capture settings (exposure, white balance) are applied by render.develop before
the matrix and the look, exactly as on export.  Develop and every look are
per-pixel transforms, so previews are rendered on a downscaled copy of the
camera data and match the full-size export.
"""
from __future__ import annotations
import base64, io, json, re, shutil, tempfile, threading, time, traceback, uuid, webbrowser
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import numpy as np

from .. import __version__, render
from ..core_api import CoreNotInstalled
from ..vault import VaultError
from ..paths import PARAMS
from ..vault import data as vaultdata

STATIC = Path(__file__).resolve().parent / "static"
PREVIEW_EDGE = 1600
MAX_SESSIONS = 3
CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                 ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml"}


# ---- params ----------------------------------------------------------------
def params_kind(name):
    """Which look a params file belongs to, from its file name."""
    return ["studio"] if name.startswith("post_") else ["camera"]


def list_params():
    return [{"name": p.name, "scene": re.sub(r"\D", "", p.stem) or p.stem,
             "pipelines": params_kind(p.name)} for p in vaultdata.list_dir(PARAMS, ".json")]


def _thin(xs, ys, n=96):
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    if xs.size <= n:
        return xs.tolist(), ys.tolist()
    idx = np.unique(np.linspace(0, xs.size - 1, n).round().astype(int))
    return xs[idx].tolist(), ys[idx].tolist()


def params_summary(name):
    path = PARAMS / Path(name).name
    d = vaultdata.read_json(path)
    out = {"name": path.name, "gain": d.get("gain"), "trim": d.get("trim"),
           "chroma": d.get("chroma"), "curves": [], "tone": None}
    for g in d.get("gamma") or []:
        x, y = _thin(g["x"], g["y"])
        out["curves"].append({"x": x, "y": y})
    if d.get("tone"):
        x, y = _thin(d["tone"]["x"], d["tone"]["y"])
        out["tone"] = {"x": x, "y": y}
    return out


# ---- sessions --------------------------------------------------------------
class Session:
    def __init__(self, path, name, full, owned=True):
        self.id = uuid.uuid4().hex[:12]
        self.path, self.name, self.full = path, name, full
        self.owned = owned          # path sits in a temp dir this session made
        t0 = time.perf_counter()
        self.cam, self.info = render.load_camera(path, half=not full)
        self.decode_s = time.perf_counter() - t0
        self.preview = downscale(self.cam, PREVIEW_EDGE)       # camera space, not yet developed
        self.meta = describe(self.info, self.cam)

    def base(self, q):
        """Linear sRGB preview base for a request's develop settings (export uses render.export)."""
        exposure, wb = develop_settings(q)
        return render.develop(self.preview, self.info, exposure, wb)

    def close(self):
        if self.owned:
            shutil.rmtree(Path(self.path).parent, ignore_errors=True)

    def payload(self):
        return {"id": self.id, "name": self.name, "full": self.full,
                "decode_s": round(self.decode_s, 3), "meta": self.meta,
                "before": jpeg_data_url(render.develop(self.preview, self.info))}


SESSIONS: OrderedDict[str, Session] = OrderedDict()
LOCK = threading.Lock()
INITIAL: dict = {}              # {"id": ...} of a photo opened from the command line
#: set by the desktop app: a per-launch secret that lets the window write an
#: export straight to a path chosen in the native save dialog.  Only that window
#: knows it (other pages cannot send the header without a CORS preflight, which
#: this server never grants), so no web page can make the server write a file.
APP: dict = {"token": None}
EXPORT_EXT = {".jpg": "jpg", ".jpeg": "jpg", ".tif": "tif", ".tiff": "tif"}


def add_session(s):
    with LOCK:
        SESSIONS[s.id] = s
        while len(SESSIONS) > MAX_SESSIONS:
            SESSIONS.popitem(last=False)[1].close()


def get_session(sid):
    s = SESSIONS.get(sid)
    if s is None:
        raise LookupError("This photo is no longer loaded. Open it again.")
    return s


def downscale(rgb, edge):
    """Box-average in linear light so the preview keeps the exact colours."""
    h, w = rgb.shape[:2]
    k = int(np.ceil(max(h, w) / edge))
    if k <= 1:
        return rgb
    h2, w2 = h // k, w // k
    return rgb[:h2*k, :w2*k].reshape(h2, k, w2, k, 3).mean((1, 3))


def describe(info, base):
    out = {"width": int(base.shape[1]), "height": int(base.shape[0]),
           "matrix": np.asarray(info["matrix"]).round(4).tolist(),
           "baseline_ev": round(float(np.log2(info.get("exposure_gain", 1.0))), 3)}
    meta = info.get("meta")
    if meta is not None:
        out.update(wb=np.asarray(meta.wb).round(4).tolist(),
                   black=np.asarray(meta.black).round(1).tolist(),
                   white=float(meta.white), raw=True)
    else:
        out["raw"] = False
    wb = info.get("wb")
    if wb is not None:
        temp, tint = wb.as_shot()
        out["as_shot"] = {"temp": round(temp), "tint": round(tint, 1), "source": wb.source}
    return out


EXPOSURE_RANGE = (-5.0, 5.0)
TEMP_RANGE = (1700.0, 25000.0)
TINT_RANGE = (-150.0, 150.0)


def develop_settings(q):
    """(exposure EV, wb) from a request: wb None = as shot, else (temperature, tint)."""
    try:
        exposure = float(q.get("exposure") or 0.0)
    except (TypeError, ValueError):
        raise ValueError("exposure must be a number of stops") from None
    if not EXPOSURE_RANGE[0] <= exposure <= EXPOSURE_RANGE[1]:
        raise ValueError(f"exposure must be within {EXPOSURE_RANGE[0]:+g}..{EXPOSURE_RANGE[1]:+g} EV")
    wb = q.get("wb")
    if wb is None:
        return exposure, None
    try:
        temp, tint = float(wb["temp"]), float(wb.get("tint", 0.0))
    except (TypeError, ValueError, KeyError):
        raise ValueError("wb must be {temp, tint}") from None
    if not (TEMP_RANGE[0] <= temp <= TEMP_RANGE[1] and TINT_RANGE[0] <= tint <= TINT_RANGE[1]):
        raise ValueError("white balance is out of range")
    return exposure, (temp, tint)


def jpeg_data_url(lin_srgb):
    from PIL import Image as PILImage
    from ..color.profiles import encode_srgb
    buf = io.BytesIO()
    PILImage.fromarray(render.to_u8(encode_srgb(lin_srgb))).save(buf, "JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def options():
    unavailable = {} if render.core_available() else {p: "core" for p in render.PIPELINES}
    return {"version": __version__, "pipelines": list(render.PIPELINES),
            "profiles": list(render.PROFILES), "params": list_params(),
            "unavailable": unavailable,
            "initial": INITIAL.get("id") if INITIAL.get("id") in SESSIONS else None}


# ---- HTTP ------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "NaturalColor/" + __version__

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json", headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def _guard(self, fn):
        try:
            fn()
        except ValueError as e:
            self._send(400, {"error": str(e)})
        except LookupError as e:
            self._send(404, {"error": str(e)})
        except PermissionError as e:
            self._send(403, {"error": str(e)})
        except (CoreNotInstalled, VaultError) as e:     # no core, no key, or a tampered build
            self._send(503, {"error": str(e)})
        except FileNotFoundError as e:
            self._send(422, {"error": str(e)})
        except Exception as e:
            traceback.print_exc()
            self._send(500, {"error": f"{type(e).__name__}: {e}"})

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/api/options":
            return self._guard(lambda: self._send(200, options()))
        if url.path.startswith("/api/session/"):
            sid = url.path.rsplit("/", 1)[1]
            return self._guard(lambda: self._send(200, get_session(sid).payload()))
        if url.path.startswith("/api/params/"):
            name = unquote(url.path.rsplit("/", 1)[1])
            return self._guard(lambda: self._send(200, params_summary(name)))
        rel = "index.html" if url.path in ("", "/") else url.path.lstrip("/")
        f = (STATIC / rel).resolve()
        if STATIC in f.parents and f.is_file():
            return self._send(200, f.read_bytes(), CONTENT_TYPES.get(f.suffix, "application/octet-stream"))
        self._send(404, {"error": "not found"})

    def do_POST(self):
        route = urlparse(self.path).path
        handler = {"/api/open": self.open_file, "/api/reopen": self.reopen,
                   "/api/render": self.render_look, "/api/export": self.export,
                   "/api/wb/pick": self.pick_wb}.get(route)
        if handler is None:
            return self._send(404, {"error": "not found"})
        self._guard(handler)

    # POST /api/open  body = file bytes, X-Filename, X-Full: 1|0
    def open_file(self):
        name = Path(unquote(self.headers.get("X-Filename") or "upload")).name
        full = self.headers.get("X-Full") == "1"
        n = int(self.headers.get("Content-Length") or 0)
        tmp = Path(tempfile.mkdtemp(prefix="naturalcolor-"))
        path = tmp / name
        with open(path, "wb") as f:
            left = n
            while left > 0:
                chunk = self.rfile.read(min(left, 1 << 20))
                if not chunk:
                    break
                f.write(chunk)
                left -= len(chunk)
        try:
            s = Session(str(path), name, full)
        except Exception:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        add_session(s)
        self._send(200, s.payload())

    # POST /api/reopen  {id, full}  decode the same file again, e.g. at full resolution
    def reopen(self):
        q = self._json()
        old = get_session(q.get("id"))
        s = Session(old.path, old.name, bool(q.get("full")), owned=old.owned)
        with LOCK:
            old.owned = False       # the file now belongs to the new session
            SESSIONS.pop(old.id, None)
            if INITIAL.get("id") == old.id:
                INITIAL["id"] = s.id
        add_session(s)
        self._send(200, s.payload())

    # POST /api/render  {id, pipeline, params, exposure?, wb?}
    def render_look(self):
        q = self._json()
        s = get_session(q.get("id"))
        t0 = time.perf_counter()
        base = s.base(q)
        img = render.apply_look(base, q.get("pipeline", "camera"), q.get("params"))
        look_s = time.perf_counter() - t0
        self._send(200, {"after": jpeg_data_url(img.rgb), "before": jpeg_data_url(base),
                         "look_s": round(look_s, 3)})

    # POST /api/wb/pick  {id, x, y}  x, y in 0..1 of the preview: the WB that makes that spot grey
    def pick_wb(self):
        q = self._json()
        s = get_session(q.get("id"))
        wb = s.info.get("wb")
        if wb is None:
            raise ValueError("white balance can only be set on a raw file")
        h, w = s.preview.shape[:2]
        try:
            x, y = float(q["x"]), float(q["y"])
        except (TypeError, ValueError, KeyError):
            raise ValueError("x and y must be numbers in 0..1") from None
        if not (0 <= x < 1 and 0 <= y < 1):
            raise ValueError("x and y must be numbers in 0..1")
        r = max(1, round(min(h, w) / 200))              # a small patch, not one noisy pixel
        cx, cy = int(x * w), int(y * h)
        patch = s.preview[max(0, cy - r):cy + r + 1, max(0, cx - r):cx + r + 1].reshape(-1, 3)
        if (patch / wb.as_shot_gains).max() >= 0.97:   # native raw: 1 is the sensor's white level
            raise ValueError("the picked area is clipped; pick a neutral area that is not blown out")
        temp, tint = wb.from_sample(patch.mean(0))
        temp = float(np.clip(temp, *TEMP_RANGE)); tint = float(np.clip(tint, *TINT_RANGE))
        self._send(200, {"temp": round(temp), "tint": round(tint, 1)})

    # POST /api/export  {id, pipeline, params, exposure?, wb?, profile, hdr, format, bits?}
    def export(self):
        q = self._json()
        s = get_session(q.get("id"))
        dest = q.get("dest")
        if dest is not None:
            return self.export_to(q, s, dest)
        fmt = "tif" if q.get("format") == "tif" else "jpg"
        hdr = bool(q.get("hdr"))
        bits = int(q.get("bits") or 16)
        if bits not in (8, 16):
            raise ValueError(f"bits must be 8 or 16, not {bits}")
        t0 = time.perf_counter()
        exposure, wb = develop_settings(q)
        profile = "pq" if hdr else (q.get("profile") or "srgb")
        name = f"{Path(s.name).stem}_{q.get('pipeline')}_{profile}.{fmt}"
        # a private scratch directory per export: never next to the user's photo,
        # never shared by two exports running at once
        with tempfile.TemporaryDirectory(prefix="naturalcolor-export-") as tmp:
            out = Path(tmp) / name
            render.export(s.cam, s.info, str(out), q.get("pipeline", "camera"), q.get("params"),
                          exposure=exposure, wb=wb, profile=q.get("profile"), hdr=hdr, bits=bits)
            body = out.read_bytes()
        self._send(200, body, "image/tiff" if fmt == "tif" else "image/jpeg", {
            "Content-Disposition": f'attachment; filename="{name}"',
            "X-Render-Seconds": f"{time.perf_counter() - t0:.3f}",
            "Access-Control-Expose-Headers": "Content-Disposition, X-Render-Seconds"})

    # POST /api/export with "dest": the desktop app writes to the path its native
    # save dialog returned; needs the per-launch X-App-Token
    def export_to(self, q, s, dest):
        token = APP.get("token")
        if not token or self.headers.get("X-App-Token") != token:
            raise PermissionError("saving to a path is only available in the desktop app")
        out = Path(dest).expanduser()
        fmt = EXPORT_EXT.get(out.suffix.lower())
        if fmt is None:
            raise ValueError("save as .jpg or .tif")
        if not out.parent.is_dir():
            raise ValueError(f"{out.parent} is not a folder")
        hdr = bool(q.get("hdr"))
        bits = int(q.get("bits") or 16)
        if bits not in (8, 16):
            raise ValueError(f"bits must be 8 or 16, not {bits}")
        exposure, wb = develop_settings(q)
        t0 = time.perf_counter()
        _, profile = render.export(s.cam, s.info, str(out), q.get("pipeline", "camera"), q.get("params"),
                                   exposure=exposure, wb=wb, profile=q.get("profile"), hdr=hdr,
                                   bits=bits if fmt == "tif" else 8)
        self._send(200, {"path": str(out), "name": out.name, "profile": profile,
                         "seconds": round(time.perf_counter() - t0, 3)})


def make_server(host="127.0.0.1", port=8765, photo=None, full=False):
    """The HTTP server (not yet serving), with `photo` already decoded if given."""
    if photo:
        path = Path(photo).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"no such file: {photo}")
        print(f"Decoding {path.name} ...")
        s = Session(str(path), path.name, full, owned=False)
        add_session(s)
        INITIAL["id"] = s.id
    return ThreadingHTTPServer((host, port), Handler)


def close_sessions():
    for s in list(SESSIONS.values()):
        s.close()


def serve(host="127.0.0.1", port=8765, open_browser=True, photo=None, full=False):
    try:
        httpd = make_server(host, port, photo, full)
    except FileNotFoundError as e:
        print(e)
        return 2
    url = f"http://{host}:{httpd.server_address[1]}/"
    print(f"Natural Color UI running at {url}  (Ctrl+C to stop)")
    if open_browser:
        threading.Timer(0.4, webbrowser.open, args=(url,)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        close_sessions()
    return 0
