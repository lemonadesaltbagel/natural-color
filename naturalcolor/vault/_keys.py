"""Where the vault master key comes from.

Resolution order (first hit wins):

    1. $NATURALCOLOR_VAULT_KEY          hex (64 chars) or base64, 32 bytes
    2. $NATURALCOLOR_VAULT_KEY_FILE     path to a key file
    3. ~/.config/natural-color/vault.key
    4. naturalcolor/vault/_k.py         key material compiled into the build

Mode 1-3 keep the key away from the shipped code, which is what makes the
sealed blobs useless on their own.  Mode 4 is the "single artefact" build:
convenient, but anyone who has the tree also has the loader and the key.
"""
from __future__ import annotations

import base64
import binascii
import os
from pathlib import Path

from ._format import VaultError

ENV_KEY = "NATURALCOLOR_VAULT_KEY"
ENV_KEY_FILE = "NATURALCOLOR_VAULT_KEY_FILE"
DEFAULT_KEY_FILE = Path.home() / ".config" / "natural-color" / "vault.key"

_cache: bytes | None = None


class MissingKey(VaultError):
    """No master key could be resolved."""


def _decode(text: str) -> bytes | None:
    t = "".join(text.split())
    if not t:
        return None
    if len(t) == 64:
        try:
            return bytes.fromhex(t)
        except ValueError:
            pass
    for decoder in (base64.b64decode, base64.urlsafe_b64decode):
        try:
            raw = decoder(t + "=" * (-len(t) % 4))
        except (binascii.Error, ValueError):
            continue
        if len(raw) == 32:
            return raw
    try:
        raw = bytes.fromhex(t)
        return raw if len(raw) == 32 else None
    except ValueError:
        return None


def _from_env() -> bytes | None:
    raw = os.environ.get(ENV_KEY)
    if not raw:
        return None
    key = _decode(raw)
    if key is None:
        raise MissingKey(f"{ENV_KEY} is set but is not a 32-byte hex or base64 key")
    return key


def _from_file(path) -> bytes | None:
    p = Path(path).expanduser()
    if not p.is_file():
        return None
    data = p.read_bytes()
    if len(data) == 32 and b"\n" not in data:
        return data
    key = _decode(data.decode("utf-8", "replace"))
    if key is None:
        raise MissingKey(f"{p} does not contain a 32-byte hex or base64 key")
    return key


def _from_embedded() -> bytes | None:
    try:
        from . import _k
    except ImportError:
        return None
    return _k.material()


def master() -> bytes:
    """The 32-byte vault master key; raises MissingKey when unavailable."""
    global _cache
    if _cache is not None:
        return _cache
    key = _from_env()
    if key is None:
        key = _from_file(os.environ.get(ENV_KEY_FILE, "") or DEFAULT_KEY_FILE)
    if key is None:
        key = _from_embedded()
    if key is None:
        raise MissingKey(
            "no vault key found. Set $NATURALCOLOR_VAULT_KEY (hex or base64), "
            f"put one in {DEFAULT_KEY_FILE}, or build with --key-mode embedded.")
    if len(key) != 32:
        raise MissingKey("vault key must be exactly 32 bytes")
    _cache = key
    return key


def reset_cache():
    global _cache
    _cache = None


def key_fingerprint() -> str:
    from . import _kdf
    return _kdf.key_id(master())
