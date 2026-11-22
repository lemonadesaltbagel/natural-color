"""Key derivation and host binding for the vault."""
from __future__ import annotations

import functools
import hashlib
import os
import platform
import re
import subprocess
import sys

INFO_PREFIX = b"ncvault/1"


def hkdf(ikm: bytes, salt: bytes, info: bytes, length: int = 32) -> bytes:
    """RFC 5869 HKDF-SHA256 (extract + expand)."""
    prk = hmac_sha256(salt or b"\x00" * 32, ikm)
    out, t, i = b"", b"", 1
    while len(out) < length:
        t = hmac_sha256(prk, t + info + bytes([i]))
        out += t
        i += 1
    return out[:length]


def hmac_sha256(key: bytes, msg: bytes) -> bytes:
    import hmac
    return hmac.new(key, msg, hashlib.sha256).digest()


# --------------------------------------------------------------------------
# host binding
# --------------------------------------------------------------------------
def _read_first(patterns):
    for pat in patterns:
        try:
            with open(pat, "rb") as fh:
                v = fh.read().strip()
            if v:
                return v
        except OSError:
            continue
    return None


def _mac_hardware_uuid():
    if sys.platform != "darwin":
        return None
    try:
        out = subprocess.run(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                             capture_output=True, text=True, timeout=10,
                             check=False).stdout
    except Exception:
        return None
    m = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', out)
    return m.group(1).encode() if m else None


@functools.lru_cache(maxsize=1)
def host_secret() -> bytes:
    """A stable per-machine identifier, hashed to 32 bytes.

    macOS: IOPlatformUUID; Linux: machine-id; anything else: MAC address.
    Returns b"" when nothing can be read, which disables machine binding.
    """
    raw = _mac_hardware_uuid()
    if raw is None:
        raw = _read_first(("/etc/machine-id", "/var/lib/dbus/machine-id"))
    if raw is None:
        try:
            import uuid
            node = uuid.getnode()
            raw = node.to_bytes(6, "big") if node else None
        except Exception:
            raw = None
    if not raw:
        return b""
    return hashlib.sha256(b"nchost\x00" + platform.system().encode() + b"\x00" + raw).digest()


def subkey(master: bytes, salt: bytes, kind: str, name: str, binding: bytes = b"") -> bytes:
    info = INFO_PREFIX + b"|" + kind.encode() + b"|" + name.encode("utf-8")
    return hkdf(master + binding, salt, info, 32)


def key_id(master: bytes) -> str:
    return hashlib.sha256(b"ncvault-key\x00" + master).hexdigest()[:16]
