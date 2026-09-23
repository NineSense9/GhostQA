"""python -m benchmark.reentry_frontier_reproduce --root experiments/published/reentry-frontier-v0.3.16 --verify"""
from __future__ import annotations

import json
import os
import sys

from benchmark.algorithm_freeze import sha256_file, verify_freeze
from benchmark.fresh_handoff_analysis import product_default_changed
from benchmark.reentry_frontier_publish import (
    ANALYSIS, CANDIDATE, CELLS, FREEZE, PROTOCOL, PUBLISHED, collect,
)
from benchmark.reentry_frontier_run import APPS, cell_stem
from benchmark.return_cycle_guard_reproduce import verify_candidate_identity

HISTORICAL = os.path.join(
    "experiments", "frozen", "ghost-horizon-handoff-v0.3.14", "freeze.json")
SUITE = os.path.join(
    "experiments", "frozen", "v0.3.15-fresh-handoff-suite", "freeze.json")


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def verify(root: str) -> int:
    print(f"root {root}")
    norm = os.path.normpath(root).replace("\\", "/")
    if "experiments/runs" in norm:
        print("FAIL: no experiments/runs fallback", file=sys.stderr)
        return 2
    if verify_candidate_identity():
        print("v0.3.9 guard freeze MATCH false")
        return 2
    print("v0.3.9 guard freeze match true")
    if verify_freeze(HISTORICAL):
        print("v0.3.14 candidate freeze MATCH false")
        return 2
    print("v0.3.14 candidate freeze match true")
    if verify_freeze(SUITE):
        print("v0.3.15 suite freeze MATCH false")
        return 2
    print("v0.3.15 suite freeze match true")
    if verify_freeze(FREEZE):
        print("v0.3.16 candidate freeze MATCH false")
        return 2
    print("v0.3.16 candidate freeze match true")
    if sha256_file(os.path.join(root, "protocol.json")) != sha256_file(PROTOCOL):
        print("protocol identity MATCH false")
        return 2
    if sha256_file(os.path.join(root, "v0315-failure-analysis.json")) != sha256_file(ANALYSIS):
        print("failure-analysis hash MATCH false")
        return 2
    if sha256_file(os.path.join(root, "candidate-freeze.json")) != sha256_file(FREEZE):
        print("candidate freeze copy MATCH false")
        return 2
    proto = _load(PROTOCOL)
    if proto.get("executed") is not False or proto.get("matrix", {}).get("cells_total") != 12:
        print("protocol identity MATCH false")
        return 2
    print("protocol identity match true")
    print("failure-analysis hash match true")
    for app, budget in CELLS:
        evidence = APPS[app]["evidence"]
        stem = cell_stem(budget)
        for ext in (".events.jsonl", ".sequence_events.json", ".graph.json", ".config.json", ".DONE"):
            path = os.path.join(root, "evidence", evidence, stem + ext)
            if not os.path.isfile(path):
                print(f"missing cell {evidence} {budget} {ext}")
                return 2
    print("12 cells present")
    man = _load(os.path.join(root, "evidence-manifest.json"))
    seen = set()
    bad = []
    for rec in man.get("files") or []:
        rel = rec.get("relative_path") or ""
        if rel in seen:
            bad.append(f"duplicate {rel}")
        seen.add(rel)
        path = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.isfile(path) or sha256_file(path) != rec.get("sha256"):
            bad.append(f"hash {rel}")
    if len(man.get("files") or []) != man.get("expected_file_count"):
        bad.append("file count")
    if bad:
        print("evidence manifest MATCH false")
        for line in bad[:20]:
            print(" ", line)
        return 2
    print(f"evidence files verified {len(seen)}/{len(seen)}")
    report = collect(root)
    if report["missing"]:
        print("published evidence incomplete")
        return 2
    mechanism = _load(os.path.join(root, "metrics", "mechanism.json"))
    if report["derived"]["outcome"] != (mechanism.get("derived") or {}).get("outcome"):
        print("outcome recomputation MATCH false")
        print(report["derived"]["outcome"], (mechanism.get("derived") or {}).get("outcome"))
        return 2
    print(f"outcome {report['derived']['outcome']}")
    print("outcome recomputation match true")
    if product_default_changed():
        print("product default MATCH false")
        return 2
    repro = _load(os.path.join(root, "metrics", "reproduction.json"))
    print(f"clean_clone_verified {str(bool(repro.get('clean_clone_verified'))).lower()}")
    print("product default changed false")
    if CANDIDATE != "ghost-structural-reentry-frontier-guard":
        print("candidate identity MATCH false")
        return 2
    print("OK")
    return 0


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=PUBLISHED)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    if not args.verify:
        print("pass --verify", file=sys.stderr)
        return 2
    return verify(args.root)


if __name__ == "__main__":
    raise SystemExit(main())
