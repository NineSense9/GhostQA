"""python -m benchmark.return_waypoint_frontier_reproduce --root experiments/published/return-waypoint-frontier-v0.3.21 --verify"""
from __future__ import annotations

import json
import os
import sys

from benchmark.algorithm_freeze import sha256_file, verify_freeze
from benchmark.fresh_composite_analysis import product_default_changed
from benchmark.return_cycle_guard_reproduce import verify_candidate_identity
from benchmark.return_waypoint_frontier_analysis import derive_v0321_outcome
from benchmark.return_waypoint_frontier_publish import collect
from benchmark.return_waypoint_frontier_run import CELLS, cell_stem

GUARD_FREEZE = os.path.join(
    "experiments", "frozen", "ghost-return-cycle-guard-v0.3.9", "freeze.json")
FINDING_FREEZE = os.path.join(
    "experiments", "frozen", "ghost-finding-return-entry-v0.3.19", "freeze.json")
SUITE_FREEZE = os.path.join(
    "experiments", "frozen", "v0.3.20-fresh-composite-suite", "freeze.json")
CANDIDATE_FREEZE = os.path.join(
    "experiments", "frozen", "ghost-return-waypoint-frontier-v0.3.21", "freeze.json")
PROTOCOL = os.path.join("experiments", "validation", "v0.3.21", "protocol.json")
AUDIT = os.path.join("experiments", "validation", "v0.3.21", "v0320-waypoint-loss-analysis.json")
EVIDENCE_NAME = {"buggy-flow": "deepbench", "buggy-wiki": "wiki"}


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def record_clean_clone(root: str, verified_head: str) -> None:
    path = os.path.join(root, "metrics", "reproduction.json")
    repro = _load(path)
    repro["clean_clone_verified"] = True
    repro["verified_head"] = verified_head
    text = json.dumps(repro, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    man_path = os.path.join(root, "evidence-manifest.json")
    man = _load(man_path)
    new_hash = sha256_file(path)
    found = False
    for rec in man.get("files") or []:
        if rec.get("relative_path") == "metrics/reproduction.json":
            rec["sha256"] = new_hash
            found = True
    if not found:
        raise SystemExit("metrics/reproduction.json missing from evidence-manifest.json")
    man_text = json.dumps(man, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with open(man_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(man_text)


def verify(root: str) -> int:
    print(f"root {root}")
    norm = os.path.normpath(root).replace("\\", "/")
    if "experiments/runs" in norm:
        print("FAIL: no experiments/runs fallback", file=sys.stderr)
        return 2
    if verify_candidate_identity(GUARD_FREEZE):
        print("v0.3.9 guard identity MATCH false")
        return 2
    print("v0.3.9 guard identity match true")
    if verify_freeze(FINDING_FREEZE):
        print("v0.3.19 candidate freeze MATCH false")
        return 2
    print("v0.3.19 candidate freeze match true")
    if verify_freeze(SUITE_FREEZE):
        print("v0.3.20 suite freeze MATCH false")
        return 2
    print("v0.3.20 suite freeze match true")
    if verify_freeze(CANDIDATE_FREEZE):
        print("v0.3.21 candidate freeze MATCH false")
        return 2
    print("v0.3.21 candidate freeze match true")
    if sha256_file(os.path.join(root, "protocol.json")) != sha256_file(PROTOCOL):
        print("protocol hash mismatch")
        return 2
    if sha256_file(os.path.join(root, "v0320-waypoint-loss-analysis.json")) != sha256_file(AUDIT):
        print("waypoint loss audit hash mismatch")
        return 2
    print("protocol and loss audit match true")
    missing = []
    for app, budget in CELLS:
        evidence = EVIDENCE_NAME.get(app, app)
        stem = cell_stem(budget)
        base = os.path.join(root, "evidence", evidence)
        for ext in (".events.jsonl", ".sequence_events.json", ".graph.json", ".config.json", ".DONE"):
            if not os.path.isfile(os.path.join(base, stem + ext)):
                missing.append(evidence + " " + stem + ext)
    if missing or len(CELLS) != 24:
        print("missing cells " + ", ".join(missing[:8]))
        return 2
    print("24 cells present")
    man = _load(os.path.join(root, "evidence-manifest.json"))
    bad = []
    for rec in man.get("files") or []:
        rel = rec.get("relative_path") or ""
        path = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.isfile(path) or sha256_file(path) != rec.get("sha256"):
            bad.append(rel)
    if bad:
        print("manifest mismatch " + ", ".join(bad[:8]))
        return 2
    print(f"evidence files verified {len(man.get('files') or [])}")
    report = collect(root)
    if report["missing"]:
        print("recompute missing " + ", ".join(report["missing"]))
        return 2
    saved = _load(os.path.join(root, "metrics", "mechanism.json"))
    recomputed = derive_v0321_outcome(**report["facts"])
    if recomputed["outcome"] != saved["derived"]["outcome"]:
        print(f"outcome recomputation {recomputed['outcome']} != {saved['derived']['outcome']}")
        return 2
    print(f"outcome {recomputed['outcome']}")
    hashes = {
        "mechanism.json": "mechanism_sha256",
        "fresh-repair.json": "fresh_repair_sha256",
        "controls.json": "controls_sha256",
        "regression.json": "regression_sha256",
        "safety.json": "safety_sha256",
        "waypoint-audit.json": "waypoint_audit_sha256",
    }
    repro = _load(os.path.join(root, "metrics", "reproduction.json"))
    for name, key in hashes.items():
        got = sha256_file(os.path.join(root, "metrics", name))
        if got != repro.get(key):
            print(f"hash mismatch {name}")
            return 2
    print("metric hashes match true")
    if product_default_changed() or repro.get("product_default_changed") or saved["derived"].get("product_default_changed"):
        print("product default changed")
        return 2
    print("product default changed false")
    print(f"clean_clone_verified {repro.get('clean_clone_verified')}")
    print("OK")
    return 0


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--record-clean-clone", default="")
    args = parser.parse_args(argv)
    if args.record_clean_clone:
        record_clean_clone(args.root, args.record_clean_clone)
    if args.verify:
        return verify(args.root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
