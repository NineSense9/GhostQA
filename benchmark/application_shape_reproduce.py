"""Clean-clone reproduction for v0.3.8 published evidence.

python -m benchmark.application_shape_reproduce --root experiments/published/application-shape-v0.3.8 --verify
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from benchmark.algorithm_freeze import DEFAULT_FREEZE, verify_freeze
from benchmark.application_shape_evidence import (
    PUBLISHED_ROOT, canonical_json_bytes, derive_canonical_analysis,
    sha256_bytes, sha256_file, verify_manifest, write_derived,
)


def load_manifest(root: str) -> dict:
    path = os.path.join(root, "evidence-manifest.json")
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def verify(root: str, rewrite_derived: bool = False) -> int:
    print(f"root {root}")
    freeze_bad = verify_freeze(DEFAULT_FREEZE)
    if freeze_bad:
        print("freeze MATCH false")
        for line in freeze_bad:
            print(" ", line)
        return 2
    print("freeze match true")

    manifest = load_manifest(root)
    bad = verify_manifest(root, manifest)
    n = len(manifest.get("files") or [])
    if bad:
        print(f"evidence files verified 0/{n}")
        print("evidence manifest pass false")
        for line in bad:
            print(" ", line)
        return 2
    print(f"evidence files verified {n}/{n}")
    print("evidence manifest pass true")

    if rewrite_derived:
        out = write_derived(root)
        reproduced = out["analysis_sha256"]
    else:
        analysis = derive_canonical_analysis(root)
        reproduced = sha256_bytes(canonical_json_bytes(analysis))

    expected_path = os.path.join(root, "metrics", "analysis.json")
    if not os.path.isfile(expected_path):
        print("FAIL: published analysis.json missing")
        return 2
    expected = sha256_file(expected_path)
    print(f"analysis expected sha256 {expected}")
    print(f"analysis reproduced sha256 {reproduced}")
    match = expected == reproduced
    print(f"analysis match {str(match).lower()}")
    if not match:
        return 2
    print("OK")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=PUBLISHED_ROOT)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--verify-evidence", action="store_true")
    ap.add_argument("--write-derived", action="store_true")
    args = ap.parse_args(argv)
    root = args.root
    if "experiments/runs" in os.path.normpath(root).replace("\\", "/"):
        print("FAIL: reproduction must not use experiments/runs", file=sys.stderr)
        return 2
    if args.write_derived:
        write_derived(root)
        print("wrote derived metrics")
        return 0
    if args.verify or args.verify_evidence:
        return verify(root, rewrite_derived=False)
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
