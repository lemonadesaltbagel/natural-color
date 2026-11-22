"""Sealed-blob container: header, per-file key derivation, integrity.

Layout (all integers little-endian)

    0    4   magic  b"NCV1"
    4    1   version (1)
    5    1   flags   bit0 payload is zlib-compressed, bit1 host-bound
    6    2   reserved
    8   16   salt
    24  12   nonce
    36   n   ciphertext || tag(16)

The whole header plus the logical name and kind are authenticated as
associated data, so a blob moved to another module, or edited, fails to open.
"""
from __future__ import annotations

import os
import zlib

from . import _aead, _kdf

MAGIC = b"NCV1"
VERSION = 1
FLAG_COMPRESSED = 1
FLAG_BOUND = 2
HEADER_LEN = 36
TAG_LEN = _aead.TAG_LEN


class VaultError(Exception):
    """Base class for every vault failure."""


class NotSealed(VaultError):
    """No sealed payload exists for this path."""


class IntegrityError(VaultError):
    """Authentication failed for a sealed payload."""


def header(salt: bytes, nonce: bytes, flags: int) -> bytes:
    return MAGIC + bytes([VERSION, flags]) + b"\x00\x00" + salt + nonce


def seal_blob(master: bytes, kind: str, name: str, payload: bytes, *,
              bound: bool = False, binding: bytes = b"", compress: bool = True) -> bytes:
    flags = 0
    body = payload
    if compress:
        packed = zlib.compress(payload, 9)
        if len(packed) < len(payload):
            body, flags = packed, flags | FLAG_COMPRESSED
    if bound:
        flags |= FLAG_BOUND
        if not binding:
            binding = _kdf.host_secret()
            if not binding:
                raise VaultError("host binding requested but this host has no stable identifier")
    salt, nonce = os.urandom(16), os.urandom(12)
    head = header(salt, nonce, flags)
    key = _kdf.subkey(master, salt, kind, name, binding if bound else b"")
    aad = head + b"|" + kind.encode() + b"|" + name.encode("utf-8")
    return head + _aead.seal(key, nonce, body, aad)


def open_blob(master: bytes, kind: str, name: str, blob: bytes, *,
              binding: bytes = b"") -> bytes:
    if len(blob) < HEADER_LEN + TAG_LEN:
        raise IntegrityError("sealed blob is truncated")
    if blob[:4] != MAGIC:
        raise IntegrityError("not a sealed blob (bad magic)")
    version, flags = blob[4], blob[5]
    if version != VERSION:
        raise IntegrityError(f"unsupported sealed-blob version {version}")
    salt, nonce = blob[8:24], blob[24:HEADER_LEN]
    head = blob[:HEADER_LEN]
    aad = head + b"|" + kind.encode() + b"|" + name.encode("utf-8")
    bound = bool(flags & FLAG_BOUND)
    if bound and not binding:
        binding = _kdf.host_secret()
        if not binding:
            raise VaultError("this blob is bound to a host that cannot be identified")
    key = _kdf.subkey(master, salt, kind, name, binding if bound else b"")
    try:
        body = _aead.open_(key, nonce, blob[HEADER_LEN:], aad)
    except _aead.AEADError as exc:
        raise IntegrityError(
            f"cannot open sealed {kind} {name!r}: {exc}. "
            "The blob was modified or belongs to another key/host.") from None
    if flags & FLAG_COMPRESSED:
        try:
            body = zlib.decompress(body)
        except zlib.error as exc:
            raise IntegrityError(f"sealed {kind} {name!r} has a corrupt payload: {exc}") from None
    return body


def describe(blob: bytes) -> dict:
    """Header facts without decrypting (for `ncseal status`)."""
    if len(blob) < HEADER_LEN or blob[:4] != MAGIC:
        return {"sealed": False}
    flags = blob[5]
    return {"sealed": True, "version": blob[4], "flags": flags,
            "compressed": bool(flags & FLAG_COMPRESSED),
            "bound": bool(flags & FLAG_BOUND),
            "size": len(blob)}
