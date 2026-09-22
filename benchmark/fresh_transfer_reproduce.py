"""python -m benchmark.fresh_transfer_reproduce --root experiments/published/fresh-transfer-v0.3.10 --verify
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from benchmark.algorithm_freeze import DEFAULT_FREEZE, verify_freeze
from benchmark.application_shape_evidence import (
    canonical_json_bytes, sha256_bytes, sha256_file,
)
from benchmark.fresh_transfer_analysis import PUBLISHED_ROOT, derive_bundle
from benchmark.return_cycle_guard_reproduce import verify_candidate_identity
from benchmark.target_freeze import DESK_FREEZE

PROTOCOL = os.path.join("experiments", "validation", "v0.3.10", "protocol.json")


def load_manifest(root: str) -> dict:
    path = os.path.join(root, "evidence-manifest.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def verify_protocol(root: str) -> list:
    bad = []
    proto_pub = os.path.join(root, "protocol.json")
    if not os.path.isfile(proto_pub) or not os.path.isfile(PROTOCOL):
        return ["missing protocol.json"]
    if sha256_file(proto_pub) != sha256_file(PROTOCOL):
        bad.append("protocol.json hash mismatch vs experiments/validation/v0.3.10")
    proto = json.load(open(PROTOCOL, encoding="utf-8"))
    if proto.get("candidate", {}).get("identity") != "ghost-structural-return-guard":
        bad.append("candidate identity")
    if proto.get("matrix", {}).get("budgets") != [40, 80, 120]:
        bad.append("budgets")
    if proto.get("matrix", {}).get("seeds") != [1]:
        bad.append("seeds")
    return bad


def verify(root: str) -> int:
    print(f"root {root}")
    if "experiments/runs" in os.path.normpath(root).replace("\\", "/"):
        print("FAIL: no experiments/runs fallback", file=sys.stderr)
        return 2
    if verify_freeze(DEFAULT_FREEZE):
        print("historical C1 freeze MATCH false")
        return 2
    print("historical C1 freeze match true")
    ident = verify_candidate_identity()
    if ident:
        print("v0.3.9 guard freeze MATCH false")
        for line in ident:
            print(" ", line)
        return 2
    print("v0.3.9 guard freeze match true")
    desk = verify_freeze(DESK_FREEZE)
    if desk:
        print("BuggyDesk target freeze MATCH false")
        for line in desk:
            print(" ", line)
        return 2
    print("BuggyDesk target freeze match true")
    pbad = verify_protocol(root)
    if pbad:
        print("protocol identity MATCH false")
        for line in pbad:
            print(" ", line)
        return 2
    print("protocol identity match true")
    man_path = os.path.join(root, "evidence-manifest.json")
    if not os.path.isfile(man_path):
        print("FAIL missing evidence-manifest.json")
        return 2
    man = load_manifest(root)
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
    expected_n = man.get("expected_file_count")
    if expected_n is not None and expected_n != n:
        bad.append(f"file count {n} != expected {expected_n}")
    if bad:
        print(f"evidence files verified 0/{n}")
        for line in bad:
            print(" ", line)
        return 2
    print(f"evidence files verified {n}/{n}")
    print("evidence manifest pass true")
    bundle = derive_bundle(root)
    reproduced = sha256_bytes(canonical_json_bytes(bundle))
    derived_path = os.path.join(root, "metrics", "derived.json")
    expected_path = os.path.join(root, "metrics", "metrics.json")
    expected = sha256_file(expected_path) if os.path.isfile(expected_path) else ""
    derived_hash = sha256_file(derived_path) if os.path.isfile(derived_path) else ""
    print(f"metrics expected sha256 {expected}")
    print(f"metrics reproduced sha256 {reproduced}")
    match = expected == reproduced
    print(f"metrics match {str(match).lower()}")
    if derived_hash:
        print(f"derived sha256 {derived_hash}")
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
