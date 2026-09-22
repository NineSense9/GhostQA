"""python -m benchmark.horizon_handoff_reproduce --root experiments/published/horizon-handoff-v0.3.14 --verify"""
from __future__ import annotations

import argparse
import json
import os
import sys

from benchmark.algorithm_freeze import DEFAULT_FREEZE, sha256_file, verify_freeze
from benchmark.application_shape_evidence import canonical_json_bytes, sha256_bytes
from benchmark.horizon_handoff_publish import (
    CANDIDATE_FREEZE, FLAT_FREEZE, PROTOCOL, PUBLISHED_ROOT, REAUDIT,
    STACK_FREEZE, TARGET_FREEZES, build_mechanism, build_regression,
    build_safety, build_witness_audit,
)
from benchmark.return_cycle_guard_reproduce import verify_candidate_identity


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def verify(root: str) -> int:
    print(f"root {root}")
    norm = os.path.normpath(root).replace("\\", "/")
    if "experiments/runs" in norm:
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
    for label, path in (
        ("v0.3.12", FLAT_FREEZE),
        ("v0.3.13", STACK_FREEZE),
        ("v0.3.14", CANDIDATE_FREEZE),
    ):
        bad = verify_freeze(path)
        if bad:
            print(f"{label} candidate freeze MATCH false")
            for line in bad:
                print(" ", line)
            return 2
        print(f"{label} candidate freeze match true")
    for name, path in TARGET_FREEZES.items():
        bad = verify_freeze(path)
        if bad:
            print(f"{name} target freeze MATCH false")
            for line in bad:
                print(" ", line)
            return 2
        print(f"{name} target freeze match true")
    pub_proto = os.path.join(root, "protocol.json")
    if not os.path.isfile(pub_proto) or sha256_file(pub_proto) != sha256_file(PROTOCOL):
        print("protocol identity MATCH false")
        return 2
    proto = _load(PROTOCOL)
    if proto.get("candidate", {}).get("identity") != "ghost-structural-horizon-handoff-guard":
        print("protocol identity MATCH false")
        return 2
    if proto.get("matrix", {}).get("cells_total") != 10:
        print("protocol identity MATCH false")
        return 2
    if proto.get("matrix", {}).get("seed") != 1:
        print("protocol identity MATCH false")
        return 2
    if proto.get("executed") is not False:
        print("protocol identity MATCH false")
        return 2
    if proto.get("historical_outcomes_preserved", {}).get("v0.3.13") != "C":
        print("protocol identity MATCH false")
        return 2
    pub_reaudit = os.path.join(root, "v0313-restore-reaudit.json")
    if sha256_file(pub_reaudit) != sha256_file(REAUDIT):
        print("re-audit hash MATCH false")
        return 2
    if sha256_file(REAUDIT) != proto.get("reaudit_sha256"):
        print("re-audit hash MATCH false")
        return 2
    print("protocol identity match true")
    print("re-audit hash match true")
    if sha256_file(os.path.join(root, "candidate-freeze.json")) != sha256_file(CANDIDATE_FREEZE):
        print("candidate freeze copy MATCH false")
        return 2
    cfg = _load(os.path.join(root, "config.json"))
    for key in ("protocol_commit", "candidate_freeze_commit", "reaudit_commit", "starting_head"):
        sha = cfg.get(key) or ""
        if len(sha) != 40 or any(ch not in "0123456789abcdef" for ch in sha.lower()):
            print("protocol identity MATCH false")
            return 2
    man_path = os.path.join(root, "evidence-manifest.json")
    if not os.path.isfile(man_path):
        print("FAIL missing evidence-manifest.json")
        return 2
    man = _load(man_path)
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
        if sha256_file(path) != rec.get("sha256"):
            bad.append(f"hash {rel}")
    count = len(man.get("files") or [])
    if man.get("expected_file_count") not in (None, count):
        bad.append(f"file count {count} != expected {man.get('expected_file_count')}")
    if bad:
        print(f"evidence files verified 0/{count}")
        for line in bad:
            print(" ", line)
        return 2
    print(f"evidence files verified {count}/{count}")
    print("evidence manifest pass true")
    safety = build_safety()
    mechanism = build_mechanism(root, safety)
    regression = build_regression(root, mechanism)
    witness = build_witness_audit(root)
    checks = (
        ("mechanism", os.path.join(root, "metrics", "mechanism.json"), mechanism),
        ("regression", os.path.join(root, "metrics", "regression.json"), regression),
        ("safety", os.path.join(root, "metrics", "safety.json"), safety),
        ("witness-audit", os.path.join(root, "metrics", "witness-audit.json"), witness),
    )
    for label, path, obj in checks:
        expected = sha256_file(path)
        reproduced = sha256_bytes(canonical_json_bytes(obj))
        print(f"{label} expected sha256 {expected}")
        print(f"{label} reproduced sha256 {reproduced}")
        if expected != reproduced:
            print(f"{label} match false")
            return 2
        print(f"{label} match true")
    outcome = mechanism["derived"]["outcome"]
    print(f"outcome {outcome}")
    if outcome != cfg.get("outcome"):
        print("outcome recomputation MATCH false")
        return 2
    print("outcome recomputation match true")
    repro = _load(os.path.join(root, "metrics", "reproduction.json"))
    print(f"clean_clone_verified {str(bool(repro.get('clean_clone_verified'))).lower()}")
    if cfg.get("product_default_changed") is not False:
        print("product default MATCH false")
        return 2
    print("product default changed false")
    print("OK")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=PUBLISHED_ROOT)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    if not args.verify:
        print("pass --verify", file=sys.stderr)
        return 2
    return verify(args.root)


if __name__ == "__main__":
    raise SystemExit(main())
