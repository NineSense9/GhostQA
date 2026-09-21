"""python -m benchmark.return_cycle_guard_reproduce --root experiments/published/return-cycle-guard-v0.3.9 --verify"""
from __future__ import annotations

import argparse
import json
import os
import sys

from benchmark.algorithm_freeze import DEFAULT_FREEZE, verify_freeze
from benchmark.application_shape_evidence import (
    canonical_json_bytes, sha256_bytes, sha256_file,
)
from benchmark.return_cycle_guard_analysis import PUBLISHED_ROOT, derive_bundle

CANDIDATE_FREEZE = os.path.join(
    "experiments", "frozen", "ghost-return-cycle-guard-v0.3.9", "freeze.json")


def verify(root: str) -> int:
    print(f"root {root}")
    if verify_freeze(DEFAULT_FREEZE):
        print("historical C1 freeze MATCH false")
        return 2
    print("historical C1 freeze match true")
    if verify_freeze(CANDIDATE_FREEZE):
        print("candidate freeze MATCH false")
        return 2
    print("candidate freeze match true")
    man_path = os.path.join(root, "evidence-manifest.json")
    if not os.path.isfile(man_path):
        print("FAIL missing evidence-manifest.json")
        return 2
    with open(man_path, encoding="utf-8") as f:
        man = json.load(f)
    bad = []
    seen = set()
    for rec in man.get("files") or []:
        rel = rec.get("relative_path") or ""
        if rel in seen:
            bad.append(f"duplicate {rel}")
        seen.add(rel)
        path = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.isfile(path):
            bad.append(f"missing {rel}")
            continue
        got = sha256_file(path)
        if got != rec.get("sha256"):
            bad.append(f"hash {rel}")
    n = len(man.get("files") or [])
    if bad:
        print(f"evidence files verified 0/{n}")
        for line in bad:
            print(" ", line)
        return 2
    print(f"evidence files verified {n}/{n}")
    print("evidence manifest pass true")
    bundle = derive_bundle(root)
    reproduced = sha256_bytes(canonical_json_bytes(bundle))
    expected_path = os.path.join(root, "metrics", "metrics.json")
    expected = sha256_file(expected_path)
    print(f"metrics expected sha256 {expected}")
    print(f"metrics reproduced sha256 {reproduced}")
    match = expected == reproduced
    print(f"metrics match {str(match).lower()}")
    print(f"outcome {bundle['derived']['outcome']}")
    if not match:
        return 2
    print("OK")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=PUBLISHED_ROOT)
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args(argv)
    if "experiments/runs" in os.path.normpath(args.root).replace("\\", "/"):
        print("FAIL: no experiments/runs fallback", file=sys.stderr)
        return 2
    if args.verify:
        return verify(args.root)
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
