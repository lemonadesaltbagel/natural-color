"""ChaCha20-Poly1305 AEAD (RFC 8439), no external dependencies.

Encryption runs once per build and decryption once per sealed import, so the
keystream is vectorised with numpy; a pure-Python path is kept as the
reference implementation that the test suite checks against the RFC vectors.

Wire format produced by `seal`:  ciphertext || tag(16)
"""
from __future__ import annotations

import hashlib
import hmac
import struct

SIGMA = (0x61707865, 0x3320646E, 0x79622D32, 0x6B206574)
BLOCK = 64
TAG_LEN = 16
MASK32 = 0xFFFFFFFF

try:                                             # optional native backend
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305 as _Native
except Exception:                                # pragma: no cover - optional
    _Native = None

BACKEND = "cryptography" if _Native is not None else "pure"


class AEADError(Exception):
    """Authentication failed: wrong key, altered bytes, or a swapped blob."""


# --------------------------------------------------------------------------
# ChaCha20 -- pure Python reference
# --------------------------------------------------------------------------
def _rotl(v, n):
    return ((v << n) & MASK32) | (v >> (32 - n))


def _qr(x, a, b, c, d):
    x[a] = (x[a] + x[b]) & MASK32; x[d] = _rotl(x[d] ^ x[a], 16)
    x[c] = (x[c] + x[d]) & MASK32; x[b] = _rotl(x[b] ^ x[c], 12)
    x[a] = (x[a] + x[b]) & MASK32; x[d] = _rotl(x[d] ^ x[a], 8)
    x[c] = (x[c] + x[d]) & MASK32; x[b] = _rotl(x[b] ^ x[c], 7)


def chacha20_block_scalar(key, counter, nonce):
    """One 64-byte ChaCha20 keystream block (RFC 8439 section 2.3)."""
    state = list(SIGMA) + list(struct.unpack("<8I", key)) + [counter] + list(struct.unpack("<3I", nonce))
    x = state[:]
    for _ in range(10):
        _qr(x, 0, 4, 8, 12); _qr(x, 1, 5, 9, 13)
        _qr(x, 2, 6, 10, 14); _qr(x, 3, 7, 11, 15)
        _qr(x, 0, 5, 10, 15); _qr(x, 1, 6, 11, 12)
        _qr(x, 2, 7, 8, 13); _qr(x, 3, 4, 9, 14)
    return struct.pack("<16I", *[((x[i] + state[i]) & MASK32) for i in range(16)])


# --------------------------------------------------------------------------
# ChaCha20 -- numpy (bulk)
# --------------------------------------------------------------------------
def _blocks_numpy(key, counter, nonce, nblocks):
    """nblocks consecutive keystream blocks as uint8, shape (nblocks, 64)."""
    import numpy as np

    u32 = np.uint32
    state = np.empty((nblocks, 16), dtype=u32)
    state[:, 0:4] = np.array(SIGMA, dtype=u32)
    state[:, 4:12] = np.frombuffer(key, dtype="<u4").astype(u32)
    ctr = (np.arange(nblocks, dtype=np.uint64) + np.uint64(counter)) & np.uint64(MASK32)
    state[:, 12] = ctr.astype(u32)
    state[:, 13:16] = np.frombuffer(nonce, dtype="<u4").astype(u32)

    def rot(v, n):
        return (v << u32(n)) | (v >> u32(32 - n))

    def qr(a, b, c, d):
        xa, xb, xc, xd = x[:, a], x[:, b], x[:, c], x[:, d]
        xa = xa + xb; xd = rot(xd ^ xa, 16)
        xc = xc + xd; xb = rot(xb ^ xc, 12)
        xa = xa + xb; xd = rot(xd ^ xa, 8)
        xc = xc + xd; xb = rot(xb ^ xc, 7)
        x[:, a], x[:, b], x[:, c], x[:, d] = xa, xb, xc, xd

    x = state.copy()
    with np.errstate(over="ignore"):
        for _ in range(10):
            qr(0, 4, 8, 12); qr(1, 5, 9, 13); qr(2, 6, 10, 14); qr(3, 7, 11, 15)
            qr(0, 5, 10, 15); qr(1, 6, 11, 12); qr(2, 7, 8, 13); qr(3, 4, 9, 14)
        x = x + state
    return np.frombuffer(x.astype("<u4").tobytes(), dtype=np.uint8).reshape(nblocks, BLOCK)


def _have_numpy():
    try:
        import numpy  # noqa: F401
        return True
    except Exception:
        return False


def chacha20_block(key, counter, nonce):
    """One 64-byte keystream block."""
    if _have_numpy():
        return _blocks_numpy(key, counter, nonce, 1)[0].tobytes()
    return chacha20_block_scalar(key, counter, nonce)


def chacha20_xor(key, nonce, counter, data):
    """XOR `data` with the keystream (encryption and decryption are identical)."""
    data = bytes(data)
    if not data:
        return b""
    nblocks = (len(data) + BLOCK - 1) // BLOCK
    if not _have_numpy():
        out = bytearray()
        for i in range(nblocks):
            ks = chacha20_block_scalar(key, counter + i, nonce)
            chunk = data[i * BLOCK:(i + 1) * BLOCK]
            out += bytes(a ^ b for a, b in zip(chunk, ks))
        return bytes(out)
    import numpy as np
    ks = _blocks_numpy(key, counter, nonce, nblocks).reshape(-1)[:len(data)]
    return (np.frombuffer(data, dtype=np.uint8) ^ ks).tobytes()


# --------------------------------------------------------------------------
# Poly1305
# --------------------------------------------------------------------------
_P1305 = (1 << 130) - 5


def poly1305(key, msg):
    r = int.from_bytes(key[:16], "little") & 0x0FFFFFFC0FFFFFFC0FFFFFFC0FFFFFFF
    s = int.from_bytes(key[16:32], "little")
    acc = 0
    for i in range(0, len(msg), 16):
        acc = ((acc + int.from_bytes(msg[i:i + 16] + b"\x01", "little")) * r) % _P1305
    return ((acc + s) & ((1 << 128) - 1)).to_bytes(16, "little")


def _tag(key, nonce, aad, ct):
    otk = chacha20_block(key, 0, nonce)[:32]
    pad = lambda b: b"\x00" * (-len(b) % 16)  # noqa: E731
    mac_data = (aad + pad(aad) + ct + pad(ct)
                + struct.pack("<Q", len(aad)) + struct.pack("<Q", len(ct)))
    return poly1305(otk, mac_data)


# --------------------------------------------------------------------------
# AEAD
# --------------------------------------------------------------------------
def seal(key, nonce, plaintext, aad=b""):
    """Encrypt and authenticate.  Returns ciphertext || 16-byte tag."""
    if len(key) != 32:
        raise ValueError("ChaCha20-Poly1305 needs a 32-byte key")
    if len(nonce) != 12:
        raise ValueError("nonce must be 12 bytes")
    if _Native is not None:
        return _Native(key).encrypt(nonce, bytes(plaintext), bytes(aad))
    ct = chacha20_xor(key, nonce, 1, plaintext)
    return ct + _tag(key, nonce, aad, ct)


def open_(key, nonce, sealed, aad=b""):
    """Verify and decrypt a blob from `seal`; raises AEADError."""
    if len(sealed) < TAG_LEN:
        raise AEADError("blob is shorter than its authentication tag")
    if _Native is not None:
        try:
            return _Native(key).decrypt(nonce, bytes(sealed), bytes(aad))
        except Exception as exc:
            raise AEADError(str(exc) or "authentication failed") from None
    ct, tag = sealed[:-TAG_LEN], sealed[-TAG_LEN:]
    if not hmac.compare_digest(_tag(key, nonce, aad, ct), tag):
        raise AEADError("authentication failed (wrong key or modified blob)")
    return chacha20_xor(key, nonce, 1, ct)


def digest(*parts):
    h = hashlib.sha256()
    for p in parts:
        h.update(p if isinstance(p, bytes) else str(p).encode("utf-8"))
        h.update(b"\x00")
    return h.digest()
