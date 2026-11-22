"""Presence and loading of the colour core.

The public package ships only the framework: the colour core (`naturalcolor.color`,
`naturalcolor.model` and the demosaic / noise reduction in `naturalcolor.io`) is
distributed separately, either as sealed ciphertext
in a release build or as a private wheel.  Everything that needs it calls
:func:`require_core` first, so a missing core produces one clear message instead
of a bare `ModuleNotFoundError` three frames deep.
"""
from __future__ import annotations

import importlib.util
import os

#: import names that only exist when the colour core is installed
CORE_MODULES = ("naturalcolor.color.engine", "naturalcolor.model.camera", "naturalcolor.io.demosaic")

INSTALL_HINT = """\
the colour core is not installed.

It is distributed separately from this package:

  * sealed release build -- unpack it next to this package, then supply the key
        export NATURALCOLOR_VAULT_KEY_FILE=/path/to/vault.key
  * private wheel        -- pip install naturalcolor-core
  * source checkout      -- clone the core repository so that
        naturalcolor/color/, naturalcolor/model/ and io/demosaic.py exist again

Run `python -m naturalcolor.core_api` to see what this installation has.\
"""


class CoreNotInstalled(RuntimeError):
    """Raised when an operation needs the colour core and it is absent."""


def available() -> bool:
    """True when the colour core can be imported (plaintext or sealed)."""
    for name in CORE_MODULES:
        try:
            if importlib.util.find_spec(name) is None:
                return False
        except (ImportError, ValueError, AttributeError):
            return False
    return True


def require_core():
    """Raise CoreNotInstalled with actionable advice if the core is missing."""
    if not available():
        raise CoreNotInstalled(INSTALL_HINT)


def sealed() -> bool:
    """True when the core is present as sealed ciphertext (no readable source)."""
    try:
        from . import vault
        return vault.is_sealed()
    except Exception:
        return False


def key_present() -> bool:
    """True when a vault key can be resolved (only meaningful for sealed builds)."""
    try:
        from .vault import _keys
        _keys.master()
        return True
    except Exception:
        return False


def status() -> dict:
    """One dictionary for a CLI/UI banner."""
    return {
        "version": _version(),
        "core": available(),
        "sealed": sealed(),
        "key": key_present() if sealed() else None,
        "hint": None if available() else INSTALL_HINT,
    }


def _version():
    try:
        from . import __version__
        return __version__
    except Exception:
        return None


def main(argv=None):
    import json
    import sys
    report = status()
    if "--json" in (argv or sys.argv[1:]):
        print(json.dumps(report, indent=1))
    else:
        print(f"naturalcolor {report['version']}")
        print(f"  colour core : {'available' if report['core'] else 'MISSING'}")
        print(f"  sealed      : {'yes' if report['sealed'] else 'no'}")
        if report["sealed"]:
            print(f"  vault key   : {'found' if report['key'] else 'MISSING'}")
        if report["hint"]:
            print()
            print(report["hint"])
    return 0 if report["core"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
