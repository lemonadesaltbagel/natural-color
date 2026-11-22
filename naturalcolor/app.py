"""Desktop app: the local UI in a native window.

    python -m naturalcolor.app [photo]      # what the packaged .app / .exe runs
    python -m naturalcolor.app --selftest [raw]   # no window: render through the sealed core, exit 0/1

The UI server runs on a free loopback port in a background thread and a
pywebview window shows it.  Exports go through the native save dialog: the
window gets a per-launch token that lets the server write to the chosen path
(see ui.server.APP).  Without pywebview the UI opens in the default browser.
"""
from __future__ import annotations
import secrets
import sys
import threading

TITLE = "Natural Color"


class Api:
    """Functions the page can call as window.pywebview.api.*"""

    def __init__(self, token):
        self._token = token
        self._window = None

    def token(self):
        return self._token

    def save_path(self, suggested):
        """Native save dialog; returns the chosen path or None."""
        import webview
        kind = getattr(getattr(webview, "FileDialog", None), "SAVE", None) or webview.SAVE_DIALOG
        name = str(suggested or "export.jpg")
        types = ("TIFF (*.tif)",) if name.lower().endswith((".tif", ".tiff")) else ("JPEG (*.jpg)",)
        result = self._window.create_file_dialog(kind, save_filename=name, file_types=types)
        if not result:
            return None
        return result if isinstance(result, str) else result[0]


def selftest(raw=None) -> int:
    """Decrypt and run every look and encoder on a synthetic image (and, if given, a raw
    file through decode, white balance and export); 0 when all is well."""
    import tempfile
    from pathlib import Path
    import numpy as np
    from . import core_api, render
    log = []
    try:
        core_api.require_core()
        y, x = np.mgrid[0:96, 0:128]
        base = np.stack([x / 128.0, y / 96.0, (x + y) / 224.0], -1) * 0.8 + 0.05
        with tempfile.TemporaryDirectory() as tmp:
            for pipeline in ("camera", "studio"):
                img = render.apply_look(base, pipeline)
                for profile, hdr in (("srgb", False), ("adobe", False), ("p3", False), (None, True)):
                    code, name = render.encode(img.rgb, profile, hdr=hdr)
                    for ext in ("jpg", "tif"):
                        out = Path(tmp) / f"{pipeline}_{name}.{ext}"
                        render.save(code, out, name, bits=16)
                        if out.stat().st_size < 1000:
                            raise RuntimeError(f"{out.name} is suspiciously small")
                log.append(f"ok {pipeline}")
            if raw:
                cam, info = render.load_camera(raw, half=True)
                arr, _ = render.export(cam, info, str(Path(tmp) / "raw.jpg"), "studio",
                                       exposure=0.3, wb=info["wb"].as_shot() if info["wb"] else None)
                log.append(f"ok raw {Path(raw).name} -> {arr.shape[1]}x{arr.shape[0]}")
        from .color import whitebalance          # sealed: imported only to prove it decrypts
        log.append(f"ok whitebalance {whitebalance.planckian_xy(6504).round(4).tolist()}")
        status = 0
    except Exception as e:                     # report, never hang a CI job
        log.append(f"FAIL {type(e).__name__}: {e}")
        status = 1
    _emit("\n".join(log))
    return status


def _emit(text):
    """stdout may be absent in a windowed (no console) build."""
    try:
        if sys.stdout is not None:
            print(text, flush=True)
    except OSError:
        pass


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--selftest" in argv:
        rest = [a for a in argv if a != "--selftest"]
        return selftest(rest[0] if rest else None)
    photo = next((a for a in argv if not a.startswith("-")), None)

    from .ui import server
    token = secrets.token_urlsafe(24)
    server.APP["token"] = token
    httpd = server.make_server("127.0.0.1", 0, photo=photo)
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    thread = threading.Thread(target=httpd.serve_forever, name="naturalcolor-ui", daemon=True)
    thread.start()
    try:
        try:
            import webview
        except ImportError:
            import webbrowser
            server.APP["token"] = None         # a browser tab must not hold the write token
            webbrowser.open(url)
            _emit(f"{TITLE} is running at {url} (Ctrl+C to quit)")
            thread.join()
            return 0
        api = Api(token)
        api._window = webview.create_window(TITLE, url, js_api=api, width=1440, height=920,
                                            min_size=(960, 640), background_color="#333333")
        webview.start()
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        httpd.shutdown()
        httpd.server_close()
        server.close_sessions()


if __name__ == "__main__":
    raise SystemExit(main())
