"""Import hook that serves sealed modules straight from memory.

Nothing is written to disk: the payload is decrypted, compiled and executed
inside `exec_module`, and the plaintext source is dropped immediately.  What
stays resident is the ordinary Python code object, exactly as with any import.
"""
from __future__ import annotations

import importlib.abc
import importlib.util
import sys
import threading

from . import _format, _keys, _manifest

LOADER_NAME = "naturalcolor.vault.sealed"


class SealedLoader(importlib.abc.Loader):
    """Decrypts one module and executes it inside its own namespace."""

    def __init__(self, fullname: str, path, kind: str, binding: bytes):
        self.fullname = fullname
        self.path = path
        self.kind = kind
        self.binding = binding

    def create_module(self, spec):
        return None                                  # default module object

    def exec_module(self, module):
        blob = self.path.read_bytes()
        source = _format.open_blob(_keys.master(), self.kind, self.fullname, blob,
                                   binding=self.binding)
        code = compile(source, str(self.path), "exec", dont_inherit=True)
        del source, blob
        exec(code, module.__dict__)

    def get_source(self, fullname):
        # Deliberately not implemented: the payload is only available as bytes.
        raise ImportError(f"{fullname} is sealed; its source is not readable")

    def __repr__(self):
        return f"<sealed loader {self.fullname!r} {self.path}>"


class SealedFinder(importlib.abc.MetaPathFinder):
    """Claims the fully-qualified names listed in the sealed manifest."""

    def __init__(self, entries: dict, binding: bytes):
        self.entries = entries
        self.binding = binding
        self._busy = threading.local()

    def find_spec(self, fullname, path=None, target=None):
        entry = self.entries.get(fullname)
        if entry is None:
            return None
        if getattr(self._busy, "on", False):
            return None
        self._busy.on = True
        try:
            from pathlib import Path
            blob = Path(_manifest.PACKAGE_ROOT) / entry["file"]
            if not blob.is_file():
                raise ImportError(
                    f"{fullname} is listed in the sealed manifest but {blob} is missing")
        finally:
            self._busy.on = False
        loader = SealedLoader(fullname, blob, entry.get("kind", "mod"), self.binding)
        spec = importlib.util.spec_from_loader(fullname, loader, origin=str(blob))
        spec.has_location = True
        return spec

    def invalidate_caches(self):
        pass

    def __repr__(self):
        return f"<sealed finder: {len(self.entries)} modules>"


_installed: SealedFinder | None = None


def install() -> SealedFinder | None:
    """Register the finder if this tree is sealed; idempotent."""
    global _installed
    if _installed is not None:
        return _installed
    manifest = _manifest.load()
    if not manifest:
        return None
    entries = {name: e for name, e in (manifest.get("modules") or {}).items()
               if e.get("kind", "mod") == "mod"}
    if not entries:
        return None
    finder = SealedFinder(entries, _manifest.binding_material())
    for i, existing in enumerate(sys.meta_path):
        if isinstance(existing, SealedFinder):
            sys.meta_path[i] = finder
            break
    else:
        sys.meta_path.insert(0, finder)
    _installed = finder
    return finder


def uninstall():
    global _installed
    sys.meta_path[:] = [f for f in sys.meta_path if not isinstance(f, SealedFinder)]
    _installed = None


def installed() -> SealedFinder | None:
    return _installed
