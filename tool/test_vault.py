"""Test vectors for the vault: RFC 8439 / RFC 5869, plus container behaviour.

    python -m pytest tool/test_vault.py      (or: python tool/ncseal.py selftest)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from naturalcolor.vault import _aead, _format, _kdf  # noqa: E402

H = bytes.fromhex


class TestChaCha20(unittest.TestCase):
    def test_block_vector_rfc8439_2_3_2(self):
        key = bytes(range(32))
        nonce = H("000000090000004a00000000")
        want = H("10f1e7e4d13b5915500fdd1fa32071c4"
                 "c7d1f4c733c068030422aa9ac3d46c4e"
                 "d2826446079faa0914c2d705d98b02a2"
                 "b5129cd1de164eb9cbd083e8a2503c4e")
        self.assertEqual(_aead.chacha20_block(key, 1, nonce), want)

    def test_scalar_and_numpy_agree(self):
        self.assertEqual(_aead.BACKEND in ("pure", "cryptography"), True)
        key, nonce = bytes(range(32)), bytes(range(12))
        for counter in (0, 1, 7, 2 ** 32 - 2):
            self.assertEqual(_aead.chacha20_block(key, counter, nonce),
                             _aead.chacha20_block_scalar(key, counter, nonce))
        data = os.urandom(4097)
        numpy_out = _aead.chacha20_xor(key, nonce, 1, data)
        scalar_out = b"".join(
            bytes(a ^ b for a, b in zip(data[i:i + 64],
                                        _aead.chacha20_block_scalar(key, 1 + i // 64, nonce)))
            for i in range(0, len(data), 64))
        self.assertEqual(numpy_out, scalar_out)

    def test_xor_is_an_involution(self):
        key, nonce = os.urandom(32), os.urandom(12)
        for n in (1, 63, 64, 65, 1000):
            data = os.urandom(n)
            self.assertEqual(_aead.chacha20_xor(key, nonce, 1,
                                                _aead.chacha20_xor(key, nonce, 1, data)), data)


class TestPoly1305(unittest.TestCase):
    def test_vector_rfc8439_2_5_2(self):
        key = H("85d6be7857556d337f4452fe42d506a8"
                "0103808afb0db2fd4abff6af4149f51b")
        msg = b"Cryptographic Forum Research Group"
        self.assertEqual(_aead.poly1305(key, msg), H("a8061dc1305136c6c22b8baf0c0127a9"))


class TestAEAD(unittest.TestCase):
    PLAINTEXT = (b"Ladies and Gentlemen of the class of '99: If I could offer you "
                 b"only one tip for the future, sunscreen would be it.")
    KEY = H("808182838485868788898a8b8c8d8e8f"
            "909192939495969798999a9b9c9d9e9f")
    NONCE = H("070000004041424344454647")
    AAD = H("50515253c0c1c2c3c4c5c6c7")
    CIPHERTEXT = H(
        "d31a8d34648e60db7b86afbc53ef7ec2"
        "a4aded51296e08fea9e2b5a736ee62d6"
        "3dbea45e8ca9671282fafb69da92728b"
        "1a71de0a9e060b2905d6a5b67ecd3b36"
        "92ddbd7f2d778b8c9803aee328091b58"
        "fab324e4fad675945585808b4831d7bc"
        "3ff4def08e4b7a9de576d26586cec64b"
        "6116")
    TAG = H("1ae10b594f09e26a7e902ecbd0600691")

    def test_vector_rfc8439_2_8_2(self):
        sealed = _aead.seal(self.KEY, self.NONCE, self.PLAINTEXT, self.AAD)
        self.assertEqual(sealed, self.CIPHERTEXT + self.TAG)
        self.assertEqual(_aead.open_(self.KEY, self.NONCE, sealed, self.AAD), self.PLAINTEXT)

    def test_roundtrip_sizes(self):
        key, nonce = os.urandom(32), os.urandom(12)
        for n in (0, 1, 15, 16, 17, 63, 64, 65, 4096, 65537):
            msg = os.urandom(n)
            aad = os.urandom(n % 37)
            self.assertEqual(_aead.open_(key, nonce, _aead.seal(key, nonce, msg, aad), aad), msg)

    def test_tamper_is_detected(self):
        key, nonce = os.urandom(32), os.urandom(12)
        sealed = bytearray(_aead.seal(key, nonce, b"colour core", b"aad"))
        for pos in (0, len(sealed) // 2, len(sealed) - 1):
            bad = bytearray(sealed)
            bad[pos] ^= 0x01
            with self.assertRaises(_aead.AEADError):
                _aead.open_(key, nonce, bytes(bad), b"aad")

    def test_wrong_aad_fails(self):
        key, nonce = os.urandom(32), os.urandom(12)
        sealed = _aead.seal(key, nonce, b"x", b"aad")
        with self.assertRaises(_aead.AEADError):
            _aead.open_(key, nonce, sealed, b"other")


class TestHKDF(unittest.TestCase):
    def test_rfc5869_case_1(self):
        ikm = b"\x0b" * 22
        salt = H("000102030405060708090a0b0c")
        info = H("f0f1f2f3f4f5f6f7f8f9")
        want = H("3cb25f25faacd57a90434f64d0362f2a"
                 "2d2d0a90cf1a5a4c5db02d56ecc4c5bf"
                 "34007208d5b887185865")
        self.assertEqual(_kdf.hkdf(ikm, salt, info, 42), want)


class TestContainer(unittest.TestCase):
    def setUp(self):
        self.master = os.urandom(32)

    def test_module_roundtrip(self):
        payload = b'"""doc"""\nGAIN = 1.25\n'
        blob = _format.seal_blob(self.master, "mod", "naturalcolor.color.engine", payload)
        self.assertTrue(blob.startswith(b"NCV1"))
        self.assertNotIn(b"GAIN", blob)
        self.assertEqual(_format.open_blob(self.master, "mod",
                                           "naturalcolor.color.engine", blob), payload)

    def test_blob_cannot_move_to_another_module(self):
        blob = _format.seal_blob(self.master, "mod", "naturalcolor.color.engine", b"secret")
        with self.assertRaises(_format.IntegrityError):
            _format.open_blob(self.master, "mod", "naturalcolor.color.curves", blob)

    def test_blob_cannot_move_between_kinds(self):
        blob = _format.seal_blob(self.master, "mod", "x.y", b"secret")
        with self.assertRaises(_format.IntegrityError):
            _format.open_blob(self.master, "data", "x.y", blob)

    def test_wrong_master_key_fails(self):
        blob = _format.seal_blob(self.master, "mod", "x.y", b"secret")
        with self.assertRaises(_format.IntegrityError):
            _format.open_blob(os.urandom(32), "mod", "x.y", blob)

    def test_host_binding_requires_the_same_host(self):
        if not _kdf.host_secret():
            self.skipTest("no host identifier on this platform")
        blob = _format.seal_blob(self.master, "mod", "x.y", b"secret", bound=True)
        self.assertTrue(_format.describe(blob)["bound"])
        self.assertEqual(_format.open_blob(self.master, "mod", "x.y", blob), b"secret")
        with self.assertRaises(_format.IntegrityError):
            _format.open_blob(self.master, "mod", "x.y", blob, binding=b"\x07" * 32)

    def test_truncated_blob_is_rejected(self):
        with self.assertRaises(_format.IntegrityError):
            _format.open_blob(self.master, "mod", "x.y", b"NCV1")


class TestSealedWrite(unittest.TestCase):
    """A write in a sealed tree must produce ciphertext, not a plaintext twin."""

    def setUp(self):
        import tempfile
        from naturalcolor.vault import _keys, _manifest
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._saved = (_manifest.REPO_ROOT, _manifest.PACKAGE_ROOT, _manifest.MANIFEST_PATH)
        vault = self.root / "naturalcolor" / "vault"
        vault.mkdir(parents=True)
        _manifest.REPO_ROOT = self.root
        _manifest.MANIFEST_PATH = vault / "manifest.json"
        _manifest.reload()
        _keys._cache = os.urandom(32)
        _manifest.MANIFEST_PATH.write_text(json.dumps(
            {"version": 1, "binding": "portable", "key_mode": "embedded",
             "key_id": _kdf.key_id(_keys._cache), "modules": {}, "data": {}}))
        _manifest.reload()

    def tearDown(self):
        from naturalcolor.vault import _keys, _manifest
        _manifest.REPO_ROOT, _manifest.PACKAGE_ROOT, _manifest.MANIFEST_PATH = self._saved
        _manifest.reload()
        _keys._cache = None
        self._tmp.cleanup()

    def test_write_creates_ciphertext_and_updates_the_manifest(self):
        from naturalcolor.vault import _manifest, data
        target = self.root / "params" / "0044.json"
        data.write_text(target, '{"gain": 1.25}')
        self.assertFalse(target.exists(), "plaintext must not be written")
        self.assertTrue(data.sealed_path(target).is_file())
        self.assertEqual(data.read_text(target), '{"gain": 1.25}')
        entry = _manifest.load()["data"]["params/0044.json"]
        self.assertEqual(entry["sha256"], hashlib.sha256(b'{"gain": 1.25}').hexdigest())
        self.assertNotIn(b"gain", data.sealed_path(target).read_bytes())

    def test_overwrite_is_re_sealed_and_stays_authentic(self):
        from naturalcolor.vault import _manifest, data
        target = self.root / "params" / "x.json"
        data.write_text(target, "first")
        data.write_text(target, "second")
        self.assertEqual(data.read_text(target), "second")
        self.assertEqual(len(_manifest.load()["data"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
