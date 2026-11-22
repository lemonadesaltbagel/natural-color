"""Locating the sealed manifest, and the repo/package roots it is relative to."""
from __future__ import annotations

import json
from pathlib import Path

VAULT_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = VAULT_DIR.parent                     # .../naturalcolor
REPO_ROOT = PACKAGE_ROOT.parent                     # .../natural-color
MANIFEST_PATH = VAULT_DIR / "manifest.json"

_cache: dict | None = None
_loaded = False


def load() -> dict | None:
    """The sealed manifest, or None when this tree is not sealed."""
    global _cache, _loaded
    if _loaded:
        return _cache
    _loaded = True
    try:
        raw = MANIFEST_PATH.read_bytes()
    except OSError:
        _cache = None
        return None
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise RuntimeError(f"{MANIFEST_PATH} is not valid JSON: {exc}") from None
    if data.get("version") != 1:
        raise RuntimeError(f"unsupported sealed manifest version {data.get('version')!r}")
    _cache = data
    return _cache


def entry_for(fullname: str) -> dict | None:
    m = load()
    if not m:
        return None
    return (m.get("modules") or {}).get(fullname)


def data_entry(relative: str) -> dict | None:
    m = load()
    if not m:
        return None
    return (m.get("data") or {}).get(relative)


def binding_material() -> bytes:
    """Host identifier to mix into the key when the build is host-bound."""
    from . import _kdf
    m = load() or {}
    if m.get("binding") != "machine":
        return b""
    return _kdf.host_secret()


def reload():
    global _cache, _loaded
    _cache, _loaded = None, False
