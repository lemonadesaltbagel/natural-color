#!/usr/bin/env python3
"""Prove that a sealed build is both unreadable and bit-exact.

    python tool/verify_sealed.py --root dist/natural-color

Checks, in order:

  1. layout      every protected module and data file is ciphertext only
  2. opacity     no plaintext identifier survives in the build (files, strings)
  3. integrity   every payload decrypts and matches its recorded digest
  4. tamper      a single flipped byte is rejected, not silently accepted
  5. fidelity    the sealed build renders byte-identical images to the source tree

Exit status 0 only when all five pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# Identifiers that only exist in the colour core; the list lives in ci_gate.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ci_gate import STRONG as CANARIES          # noqa: E402

RENDERS = [
    ("camera-0044", ["--pipeline", "camera", "--params", "params/0044.json"], "jpg"),
    ("camera-0125", ["--pipeline", "camera", "--params", "params/0125.json"], "jpg"),
    ("studio-0044", ["--pipeline", "studio", "--params", "params/post_0044.json"], "jpg"),
    ("hdr", ["--pipeline", "studio", "--params", "params/post_0044.json", "--hdr"], "jpg"),
    ("adobe16", ["--pipeline", "studio", "--params", "params/post_0044.json",
                 "--profile", "adobe", "--bits", "16"], "tif"),
]


class Checker:
    def __init__(self):
        self.failures = 0

    def step(self, title):
        print(f"\n\033[1m{title}\033[0m")

    def ok(self, msg):
        print(f"  \033[32mok\033[0m   {msg}")

    def bad(self, msg):
        self.failures += 1
        print(f"  \033[31mFAIL\033[0m {msg}")

    def expect(self, cond, msg):
        (self.ok if cond else self.bad)(msg)
        return cond


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def run(cmd, cwd):
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["SOURCE_DATE_EPOCH"] = "1700000000"      # freeze the ICC date: reproducible files
    key_file = env.get("NATURALCOLOR_VAULT_KEY_FILE")
    if key_file and not os.path.isabs(key_file):
        env["NATURALCOLOR_VAULT_KEY_FILE"] = str((Path.cwd() / key_file).resolve())
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, env=env)


def make_input(path):
    import numpy as np
    from PIL import Image
    y, x = np.mgrid[0:240, 0:360]
    img = np.stack([0.5 + 0.5 * np.sin(x / 28.0),
                    0.5 + 0.5 * np.sin(y / 19.0 + 1.0),
                    0.5 + 0.5 * np.sin((x + y) / 41.0 + 2.0)], -1)
    rng = np.random.default_rng(3)
    img = np.clip(img * 0.8 + 0.1 + rng.normal(0, 0.02, img.shape), 0, 1)
    Image.fromarray((img * 255).astype("uint8")).save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="dist/natural-color")
    ap.add_argument("--source", default=str(REPO))
    ap.add_argument("--python", default=sys.executable)
    args = ap.parse_args()

    root, source = Path(args.root).resolve(), Path(args.source).resolve()
    manifest_path = root / "naturalcolor" / "vault" / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"{root} has no sealed manifest -- build it first")
    manifest = json.loads(manifest_path.read_text())
    c = Checker()

    # 1 -------------------------------------------------------------------
    c.step("1. layout")
    for fullname, entry in sorted(manifest["modules"].items()):
        plain = root / Path(*fullname.split(".")).with_suffix(".py")
        sealed = root / "naturalcolor" / entry["file"]
        c.expect(sealed.is_file(), f"{entry['file']} present")
        c.expect(not plain.exists(), f"{plain.relative_to(root)} removed")
    for name, entry in sorted(manifest["data"].items()):
        c.expect((root / entry["file"]).is_file(), f"{entry['file']} present")
        c.expect(not (root / name).exists(), f"{name} removed")

    # 2 -------------------------------------------------------------------
    c.step("2. opacity")
    hits = []
    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if path.suffix in {".ncs"}:
            continue
        try:
            text = path.read_bytes().decode("utf-8", "ignore")
        except OSError:
            continue
        for canary in CANARIES:
            if canary in text:
                hits.append(f"{path.relative_to(root)} contains {canary!r}")
    c.expect(not hits, "no core identifier found outside ciphertext"
             if not hits else "; ".join(hits[:4]))
    blobs = sorted(root.rglob("*.ncs"))
    texty = []
    for path in blobs:
        data = path.read_bytes()
        printable = sum(1 for b in data if 32 <= b < 127) / max(len(data), 1)
        if printable > 0.75:
            texty.append(f"{path.relative_to(root).as_posix()} ({printable:.0%} printable)")
    c.expect(not texty, f"{len(blobs)} blobs look like ciphertext, not text"
             if not texty else f"word-like payloads: {texty[:3]}")

    # 3 -------------------------------------------------------------------
    c.step("3. integrity")
    code = "import json,naturalcolor.vault as v;print(json.dumps(v.verify()))"
    proc = run([args.python, "-c", code], root)
    report = {}
    for line in reversed(proc.stdout.strip().splitlines()):
        try:
            report = json.loads(line)
            break
        except ValueError:
            continue
    c.expect(report.get("ok") is True,
             f"{len(report.get('modules', []))} modules + {len(report.get('data', []))} data "
             f"payloads authenticate (key {report.get('key_id')})"
             if report.get("ok") else f"verify failed: {report.get('error') or proc.stderr[-300:]}")

    # 4 -------------------------------------------------------------------
    c.step("4. tamper")
    target = root / "naturalcolor" / manifest["modules"][sorted(manifest["modules"])[0]]["file"]
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "tampered.ncs"
        data = bytearray(target.read_bytes())
        data[len(data) // 2] ^= 0x01
        copy.write_bytes(bytes(data))
        name = sorted(manifest["modules"])[0]
        probe = (
            "import json,sys,naturalcolor.vault as v\n"
            "from naturalcolor.vault import _manifest\n"
            f"blob=open({str(copy)!r},'rb').read()\n"
            "try:\n"
            f"    v.open_blob(v.master(),'mod',{name!r},blob,binding=_manifest.binding_material())\n"
            "    print('ACCEPTED')\n"
            "except v.IntegrityError as e:\n"
            "    print('REJECTED')\n"
        )
        proc = run([args.python, "-c", probe], root)
        c.expect("REJECTED" in proc.stdout,
                 f"one flipped bit in {target.name} is rejected"
                 if "REJECTED" in proc.stdout else f"tampered blob accepted: {proc.stdout}{proc.stderr}")

    # 5 -------------------------------------------------------------------
    c.step("5. fidelity")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        src_png = tmp / "in.png"
        make_input(src_png)
        for label, flags, ext in RENDERS:
            outs = {}
            for who, tree in (("source", source), ("sealed", root)):
                out = tmp / f"{who}-{label}.{ext}"
                proc = run([args.python, "-m", "naturalcolor", "render",
                            "--input", str(src_png), "--output", str(out)] + flags, tree)
                if proc.returncode != 0:
                    c.bad(f"{who} {label}: render failed: {proc.stderr.strip().splitlines()[-1:]}")
                    outs = {}
                    break
                outs[who] = sha(out)
            if outs:
                c.expect(outs["source"] == outs["sealed"],
                         f"{label:<12} byte-identical ({outs['source']})"
                         if outs["source"] == outs["sealed"]
                         else f"{label}: {outs['source']} != {outs['sealed']}")

    print()
    if c.failures:
        print(f"\033[31m{c.failures} check(s) failed\033[0m")
        return 1
    print("\033[32mall checks passed\033[0m")
    return 0


def _printable_runs(data: bytes, minimum: int = 6):
    out, cur = [], bytearray()
    for byte in data:
        if 32 <= byte < 127:
            cur.append(byte)
        else:
            if len(cur) >= minimum:
                out.append(cur.decode("ascii"))
            cur = bytearray()
    if len(cur) >= minimum:
        out.append(cur.decode("ascii"))
    return out


if __name__ == "__main__":
    raise SystemExit(main())
