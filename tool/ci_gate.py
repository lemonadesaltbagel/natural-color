#!/usr/bin/env python3
"""Release gate: refuse to publish anything that still contains the colour core.

    python tool/ci_gate.py --profile public  public-repo/
    python tool/ci_gate.py --profile core    working-tree/       # after injecting the private core
    python tool/ci_gate.py --profile release dist/natural-color  # tree, .tar.gz or .zip

Profiles
    public    a tree about to be pushed to the public repository: no core source,
              no calibrated parameters, no ciphertext, still importable
    core      the private core has been injected and is complete enough to seal
    release   a sealed build: ciphertext only, every expected module sealed, no
              plaintext twin, no embedded key in an external-key build

Exit status is 0 only when every fatal check passes.  `--strict` also promotes
the provenance hints (comments that name the reference implementation) to
failures; `--json` prints a machine-readable report.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ncseal import PROTECTED, PROTECTED_DATA          # noqa: E402

#: constants and symbol names that exist only inside the colour core -- fatal
STRONG = [
    "NC_B", "NC_A_NUM", "HB_M_WARM", "HB_T_WARM", "HB_T_COOL", "Y2R_REGISTER",
    "11863", "50464", "56267", "38173", "15500", "film_curve_gain",
    "main_3dlut", "CRawColorCorrection", "GGDirInterpolator", "RawNoiseFilter4",
    "FilmCurve",
]

#: provenance wording: not the algorithm, but it names where it came from
HINTS = ["reference processor", "reconstructed", "reconstruction", "recovered",
         "0xB2CC"]

#: paths that must never appear in the public repository
PUBLIC_FORBIDDEN = [
    "naturalcolor/color", "naturalcolor/model", "naturalcolor/calibrate",
    "naturalcolor/io/demosaic.py", "naturalcolor/io/denoise.py",
    "naturalcolor/verify.py", "naturalcolor/attribute.py",
    "params", "build",
    "data/gradation.bin", "data/gain_curves.json", "data/working_space.json",
    "docs/PIPELINES.md", "docs/PIPELINE-V2.md", "docs/DEV.md",
]

#: the public tree still has to be a usable package
PUBLIC_REQUIRED = [
    "naturalcolor/__init__.py", "naturalcolor/render.py", "naturalcolor/cli.py",
    "naturalcolor/core_api.py", "naturalcolor/vault/__init__.py",
    "tool/ncseal.py", "pyproject.toml",
]

#: sealed when present, but not required (the repository may not carry them)
OPTIONAL_DATA = {"build/iq.pkl"}

PRUNE = {".git", "__pycache__", "node_modules", "dist", "_scratch", "_backup",
         ".venv", "build", "site-packages"}

#: this file necessarily contains every string it searches for, so it is the one
#: path exempt from the text scan; keep the list at exactly this
SELF_EXEMPT = {"tool/ci_gate.py"}

SKIP_SUFFIX = {".ncs", ".pyc", ".icc", ".so", ".dylib", ".png", ".jpg", ".jpeg",
               ".tif", ".tiff", ".bin", ".gz", ".zip", ".whl", ".pkl"}


class Report:
    def __init__(self, profile, root):
        self.profile = profile
        self.root = str(root)
        self.checks = []
        self.warnings = []

    def check(self, ok, name, detail=""):
        self.checks.append({"ok": bool(ok), "name": name, "detail": detail})
        return ok

    def warn(self, name, detail):
        self.warnings.append({"name": name, "detail": detail})

    @property
    def ok(self):
        return all(c["ok"] for c in self.checks)

    def failures(self):
        return [c for c in self.checks if not c["ok"]]

    def as_dict(self):
        return {"profile": self.profile, "root": self.root, "ok": self.ok,
                "checks": self.checks, "warnings": self.warnings}


def _walk(root: Path):
    """Every file under root, pruning virtualenvs, VCS data and build products."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames
                             if d not in PRUNE and not d.startswith(".venv"))
        here = Path(dirpath)
        for name in sorted(filenames):
            yield here / name


def _is_text(path: Path) -> bool:
    if path.suffix.lower() in SKIP_SUFFIX:
        return False
    try:
        head = path.open("rb").read(4096)
    except OSError:
        return False
    if b"\x00" in head:
        return False
    try:
        head.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _hit(canary: str, text: str) -> bool:
    """Whole-token match, so '15500' does not fire inside a hex digest."""
    pattern = r"(?<![A-Za-z0-9_])" + re.escape(canary) + r"(?![A-Za-z0-9_])"
    return re.search(pattern, text) is not None


def scan_text(root: Path, report: Report, strict=False):
    fatal, hints = [], []
    for path in _walk(root):
        if not _is_text(path):
            continue
        rel = path.relative_to(root).as_posix()
        if rel in SELF_EXEMPT:
            continue
        try:
            text = path.read_text("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for canary in STRONG:
            if _hit(canary, text):
                fatal.append(f"{rel}: {canary!r}")
        for hint in HINTS:
            if _hit(hint, text):
                hints.append(f"{rel}: {hint!r}")
    report.check(not fatal, "no core identifier in readable text",
                 "; ".join(fatal[:6]) + (" ..." if len(fatal) > 6 else ""))
    if hints:
        report.warn("provenance wording found", "; ".join(hints[:8])
                    + (" ..." if len(hints) > 8 else ""))
        if strict:
            report.check(False, "no provenance wording (--strict)", "; ".join(hints[:6]))


def check_public(root: Path, report: Report, strict=False):
    for rel in PUBLIC_FORBIDDEN:
        present = (root / rel).exists()
        report.check(not present, f"absent: {rel}",
                     "" if not present else f"{rel} is in the public tree")
    for rel in PUBLIC_REQUIRED:
        report.check((root / rel).is_file(), f"present: {rel}")
    ncs = [p.relative_to(root).as_posix() for p in _walk(root) if p.suffix == ".ncs"]
    report.check(not ncs, "no ciphertext committed to the source repo", ", ".join(ncs[:5]))
    for junk in ("dist", ".venv", "_backup", "_scratch"):
        report.check(not (root / junk).exists(), f"no {junk}/ in the public tree")
    scan_text(root, report, strict)


def check_core(root: Path, report: Report, strict=False):
    missing = [n for n in PROTECTED
               if not (root / Path(*n.split(".")).with_suffix(".py")).is_file()]
    report.check(not missing, f"all {len(PROTECTED)} core modules injected",
                 ", ".join(missing))
    for pattern in PROTECTED_DATA:
        found = list(root.glob(pattern))
        if pattern in OPTIONAL_DATA:
            if found:
                report.check(True, f"optional data present: {pattern}")
            continue
        report.check(bool(found), f"data present for sealing: {pattern}")
    ncs = [p.relative_to(root).as_posix() for p in _walk(root) if p.suffix == ".ncs"]
    report.check(not ncs, "no stale ciphertext in the working tree", ", ".join(ncs[:5]))
    # no canary scan here: this profile runs *before* sealing, with the plaintext
    # core legitimately present.


def check_release(root: Path, report: Report, allow_tool=False, no_embedded_key=False,
                  strict=False):
    manifest_path = root / "naturalcolor" / "vault" / "manifest.json"
    if not report.check(manifest_path.is_file(), "sealed manifest present"):
        return
    manifest = json.loads(manifest_path.read_text())
    modules = manifest.get("modules") or {}
    data = manifest.get("data") or {}

    unsealed = [name for name in PROTECTED if name not in modules]
    report.check(not unsealed, f"all {len(PROTECTED)} expected modules are sealed",
                 ", ".join(unsealed))

    bad = []
    for name, entry in sorted(modules.items()):
        sealed = root / "naturalcolor" / entry["file"]
        plain = root / Path(*name.split(".")).with_suffix(".py")
        if not sealed.is_file():
            bad.append(f"{entry['file']} missing")
        if plain.exists():
            bad.append(f"{plain.relative_to(root)} still plaintext")
    report.check(not bad, f"{len(modules)} modules are ciphertext only", "; ".join(bad[:6]))

    bad = []
    for name, entry in sorted(data.items()):
        if not (root / entry["file"]).is_file():
            bad.append(f"{entry['file']} missing")
        if (root / name).exists():
            bad.append(f"{name} still plaintext")
    report.check(not bad, f"{len(data)} data files are ciphertext only", "; ".join(bad[:6]))

    if no_embedded_key or manifest.get("key_mode") == "external":
        has_key = (root / "naturalcolor" / "vault" / "_k.py").exists()
        report.check(not has_key, "no embedded key in an external-key build")

    if not allow_tool:
        report.check(not (root / "tool").exists(), "no sealing tool inside the release",
                     "tool/ can unseal; ship it separately (--allow-tool to override)")

    scan_text(root, report, strict)


def _extract(artifact: Path, dest: Path) -> Path:
    if zipfile.is_zipfile(artifact):
        with zipfile.ZipFile(artifact) as zf:
            for member in zf.namelist():
                target = (dest / member).resolve()
                if not str(target).startswith(str(dest.resolve())):
                    raise SystemExit(f"refusing unsafe archive member {member!r}")
            zf.extractall(dest)
    elif tarfile.is_tarfile(artifact):
        with tarfile.open(artifact) as tf:
            try:
                tf.extractall(dest, filter="data")
            except TypeError:                       # Python < 3.12
                tf.extractall(dest)
    else:
        raise SystemExit(f"{artifact} is neither a zip nor a tar archive")
    if (dest / "naturalcolor").is_dir():
        return dest
    roots = [p for p in dest.iterdir() if p.is_dir()]
    return roots[0] if len(roots) == 1 else dest


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ci_gate", description=__doc__.splitlines()[0])
    ap.add_argument("target", help="tree or archive to inspect")
    ap.add_argument("--profile", required=True, choices=("public", "core", "release"))
    ap.add_argument("--strict", action="store_true",
                    help="provenance wording becomes a failure")
    ap.add_argument("--allow-tool", action="store_true", help="release may contain tool/")
    ap.add_argument("--require-embedded-key", action="store_true",
                    help="the build must carry a usable embedded key")
    ap.add_argument("--no-embedded-key", action="store_true",
                    help="the build must not carry a compiled-in key")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    target = Path(args.target).resolve()
    if not target.exists():
        raise SystemExit(f"{target} does not exist")

    with tempfile.TemporaryDirectory() as tmp:
        archive = target.is_file()
        root = _extract(target, Path(tmp)) if archive else target
        report = Report(args.profile, target)
        if args.profile == "public":
            check_public(root, report, args.strict)
        elif args.profile == "core":
            check_core(root, report, args.strict)
        else:
            check_release(root, report, allow_tool=args.allow_tool,
                          no_embedded_key=args.no_embedded_key, strict=args.strict)
        if args.require_embedded_key and args.profile == "release":
            manifest = root / "naturalcolor" / "vault" / "manifest.json"
            mode = json.loads(manifest.read_text()).get("key_mode") if manifest.is_file() else None
            report.check(mode == "embedded", "release carries a usable embedded key",
                         f"key_mode is {mode!r}")

    if args.json:
        print(json.dumps(report.as_dict(), indent=1))
    else:
        label = {"public": "public repo", "core": "private core", "release": "release"}[args.profile]
        print(f"gate: {label}  {target}" + ("  (archive)" if archive else ""))
        for c in report.checks:
            mark = "\033[32mok  \033[0m" if c["ok"] else "\033[31mFAIL\033[0m"
            line = f"  {mark} {c['name']}"
            if not c["ok"] and c["detail"]:
                line += f"\n         -> {c['detail']}"
            print(line)
        for w in report.warnings:
            print(f"  \033[33mwarn\033[0m {w['name']}\n         -> {w['detail']}")
        print(f"\n{len(report.checks)} checks, {len(report.failures())} failed"
              + (f", {len(report.warnings)} warning(s)" if report.warnings else ""))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
