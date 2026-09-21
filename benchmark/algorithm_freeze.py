"""Verify a frozen algorithm tree has not been silently edited.

Used by validation runs. Does not score bugs and does not read manifests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_FREEZE = os.path.join(
    ROOT, "experiments", "frozen", "ghost-structural-v0.3.6", "freeze.json")


def sha256_file(path: str) -> str:
    with open(path, "rb") as f:
        data = f.read().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def load_freeze(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def verify_freeze(freeze_path: str, root: str = ROOT) -> list:
    """Return a list of mismatch strings. Empty means OK."""
    freeze = load_freeze(freeze_path)
    mismatches = []
    files = freeze.get("files") or {}
    for rel, meta in files.items():
        path = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.isfile(path):
            mismatches.append(f"missing {rel}")
            continue
        got = sha256_file(path)
        want = meta.get("sha256")
        if want and got != want:
            mismatches.append(f"{rel}: sha256 {got} != frozen {want}")
    return mismatches


def assert_frozen(freeze_path: str, root: str = ROOT) -> None:
    bad = verify_freeze(freeze_path, root)
    if bad:
        raise SystemExit(
            "abort validation: frozen algorithm files changed\n" + "\n".join(bad))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["verify"])
    ap.add_argument("freeze", nargs="?", default=DEFAULT_FREEZE)
    args = ap.parse_args(argv)
    if args.cmd == "verify":
        bad = verify_freeze(args.freeze)
        if bad:
            print("MISMATCH", file=sys.stderr)
            for line in bad:
                print(line, file=sys.stderr)
            return 2
        print("OK")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
