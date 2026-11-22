"""Transparent access to sealed data files (params, gain curves).

Every reader falls back to a plain file when no sealed sibling exists, so the
same code runs in a development tree and in a sealed build.

Writers are symmetric: in a sealed tree a write re-encrypts and updates the
manifest entry, so calibration produces ciphertext instead of leaking a
plaintext parameter file next to its sealed twin.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path

from . import _format, _keys, _manifest

SUFFIX = ".ncs"


def sealed_path(path) -> Path:
    p = Path(path)
    return p.with_name(p.name + SUFFIX)


def is_sealed(path) -> bool:
    return sealed_path(path).is_file()


def exists(path) -> bool:
    p = Path(path)
    return p.exists() or sealed_path(p).is_file()


def _logical(path) -> str | None:
    """Repo-relative posix name used to bind the payload, or None if outside."""
    try:
        p = Path(path).resolve()
        return p.relative_to(_manifest.REPO_ROOT.resolve()).as_posix()
    except (ValueError, OSError):
        return None


# --------------------------------------------------------------------------
# read
# --------------------------------------------------------------------------
def read_bytes(path) -> bytes:
    """Bytes of a data file; a sealed sibling wins and is authenticated."""
    p = Path(path)
    blob_path = sealed_path(p)
    if blob_path.is_file() and _manifest.load():
        name = _logical(p)
        if name is not None and _manifest.data_entry(name) is None:
            name = None                              # unknown name: plain read
        if name is not None:
            return _format.open_blob(_keys.master(), "data", name,
                                     blob_path.read_bytes(),
                                     binding=_manifest.binding_material())
    return p.read_bytes()


def read_text(path, encoding: str = "utf-8") -> str:
    return read_bytes(path).decode(encoding)


def read_json(path):
    return json.loads(read_text(path))


def read_array(path, dtype):
    """A numpy array from a (possibly sealed) raw binary file; copies the buffer."""
    import numpy as np
    return np.frombuffer(read_bytes(path), dtype=dtype).copy()


def list_dir(directory, suffix: str = ".json") -> list[Path]:
    """Logical paths (sealed suffixes stripped) in a directory, sorted."""
    d = Path(directory)
    seen: dict[str, Path] = {}
    if d.is_dir():
        for p in sorted(d.iterdir()):
            if p.name.endswith(SUFFIX):
                seen.setdefault(p.name[:-len(SUFFIX)], d / p.name[:-len(SUFFIX)])
            elif p.is_file() and p.suffix == suffix:
                seen.setdefault(p.name, p)
    return [seen[k] for k in sorted(seen)]


# --------------------------------------------------------------------------
# write
# --------------------------------------------------------------------------
def write_bytes(path, payload: bytes) -> Path:
    """Write a data file; sealed trees get ciphertext and a manifest update.

    Returns the path actually written (the `.ncs` path in a sealed tree).
    """
    p = Path(path)
    payload = bytes(payload)
    manifest = _manifest.load()
    name = _logical(p) if manifest else None
    if manifest and name is not None:
        return _write_sealed(p, name, payload, manifest)
    _atomic_write(p, payload)
    return p


def write_text(path, text: str, encoding: str = "utf-8") -> Path:
    return write_bytes(path, text.encode(encoding))


def write_json(path, data, indent: int = 1) -> Path:
    return write_text(path, json.dumps(data, indent=indent))


def _write_sealed(p: Path, name: str, payload: bytes, manifest: dict) -> Path:
    bound = manifest.get("binding") == "machine"
    blob = _format.seal_blob(_keys.master(), "data", name, payload,
                             bound=bound, binding=_manifest.binding_material())
    dest = sealed_path(p)
    _atomic_write(dest, blob)
    _record(name, payload, blob, manifest)
    return dest


def _record(name: str, payload: bytes, blob: bytes, manifest: dict):
    """Keep manifest.json truthful after an in-place re-seal."""
    doc = copy.deepcopy(manifest)
    doc.setdefault("data", {})
    doc["data"][name] = {
        "file": Path(name).as_posix() + SUFFIX,
        "kind": "data",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "flags": _format.describe(blob)["flags"],
    }
    _atomic_write(_manifest.MANIFEST_PATH,
                  (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode())
    _manifest.reload()


def _atomic_write(path: Path, payload: bytes):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
