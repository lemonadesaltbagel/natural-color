"""Sealed source protection for the colour core.

Typical use is automatic: importing :mod:`naturalcolor` installs the import
hook when ``naturalcolor/vault/manifest.json`` exists, and the modules listed
there are decrypted in memory instead of being read from ``.py`` files.

Build side (see ``tool/ncseal.py``)::

    from naturalcolor.vault import seal_blob
    blob = seal_blob(master, "mod", "naturalcolor.color.engine", source, bound=False)

Run side::

    from naturalcolor.vault import is_sealed, verify
    is_sealed()          # True in a sealed build
    verify()             # decrypt + hash every sealed payload without importing
"""
from __future__ import annotations

import hashlib

from . import data
from ._format import (IntegrityError, NotSealed, VaultError, describe,
                      open_blob, seal_blob)
from ._finder import install, installed, uninstall
from ._keys import MissingKey, master
from ._manifest import MANIFEST_PATH, PACKAGE_ROOT, REPO_ROOT, load as manifest


def is_sealed() -> bool:
    """True when this tree carries a sealed manifest."""
    return manifest() is not None


def install_if_sealed():
    """Install the import hook; a no-op in an ordinary development tree."""
    return install()


def status() -> dict:
    m = manifest()
    if not m:
        return {"sealed": False, "manifest": str(MANIFEST_PATH)}
    return {
        "sealed": True,
        "manifest": str(MANIFEST_PATH),
        "build": m.get("build"),
        "key_mode": m.get("key_mode"),
        "binding": m.get("binding"),
        "key_id": m.get("key_id"),
        "modules": len(m.get("modules") or {}),
        "data": len(m.get("data") or {}),
        "cipher": m.get("cipher"),
    }


def verify(check_key: bool = True) -> dict:
    """Decrypt every sealed payload and check its recorded digest.

    Nothing is imported or executed; this is a build-integrity check that
    needs the same key the runtime would need.
    """
    m = manifest()
    if not m:
        return {"sealed": False, "ok": True, "modules": [], "data": []}
    from . import _kdf
    report = {"sealed": True, "ok": True, "modules": [], "data": [],
              "key_id": m.get("key_id")}
    if check_key:
        try:
            got = _kdf.key_id(master())
        except VaultError as exc:
            return {**report, "ok": False, "error": str(exc)}
        report["key_id_actual"] = got
        if m.get("key_id") and got != m["key_id"]:
            return {**report, "ok": False,
                    "error": f"key mismatch: build used {m['key_id']}, this key is {got}"}
    binding = m.get("binding") == "machine" and _kdf.host_secret() or b""
    for kind, base, table in (("mod", PACKAGE_ROOT, m.get("modules") or {}),
                              ("data", REPO_ROOT, m.get("data") or {})):
        for name, entry in sorted(table.items()):
            path = base / entry["file"]
            row = {"name": name, "file": str(path)}
            try:
                payload = open_blob(master(), kind, name, path.read_bytes(), binding=binding)
            except (OSError, VaultError) as exc:
                row.update(ok=False, error=str(exc))
                report["ok"] = False
            else:
                got = hashlib.sha256(payload).hexdigest()
                want = entry.get("sha256", "")
                row.update(ok=(got == want), size=len(payload), sha256=got[:16])
                if not row["ok"]:
                    row["error"] = "payload does not match the recorded digest"
                    report["ok"] = False
            report[kind if kind == "data" else "modules"].append(row)
    return report


__all__ = [
    "IntegrityError", "MANIFEST_PATH", "MissingKey", "NotSealed", "PACKAGE_ROOT",
    "REPO_ROOT", "VaultError", "data", "describe", "install", "install_if_sealed",
    "installed", "is_sealed", "manifest", "master", "open_blob", "seal_blob",
    "status", "uninstall", "verify",
]
