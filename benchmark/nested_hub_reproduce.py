"""python -m benchmark.nested_hub_reproduce --root experiments/published/nested-hub-parent-v0.3.12 --verify"""
from __future__ import annotations

import argparse
import json
import os
import sys

from benchmark.algorithm_freeze import DEFAULT_FREEZE, sha256_file, verify_freeze
from benchmark.application_shape_evidence import canonical_json_bytes, sha256_bytes
from benchmark.nested_hub_publish import (
    CANDIDATE_FREEZE, PROTOCOL, PUBLISHED_ROOT, V0311_TARGETS,
    build_all,
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
    cand = verify_freeze(CANDIDATE_FREEZE)
    if cand:
        print("candidate freeze MATCH false")
        for line in cand:
            print(" ", line)
        return 2
    print("candidate freeze match true")
    for name, path in V0311_TARGETS.items():
        bad = verify_freeze(path)
        if bad:
            print(f"{name} target freeze MATCH false")
            for line in bad:
                print(" ", line)
            return 2
        print(f"{name} target freeze match true")
    pub_proto = os.path.join(root, "protocol.json")
    if not os.path.isfile(pub_proto) or not os.path.isfile(PROTOCOL):
        print("protocol identity MATCH false")
        return 2
    if sha256_file(pub_proto) != sha256_file(PROTOCOL):
        print("protocol identity MATCH false")
        return 2
    proto = _load(PROTOCOL)
    if proto.get("candidate", {}).get("identity") != "ghost-structural-nested-return-guard":
        print("protocol identity MATCH false")
        return 2
    if proto.get("matrix", {}).get("budgets") != [40, 80, 120]:
        print("protocol identity MATCH false")
        return 2
    if proto.get("matrix", {}).get("cells_total") != 18:
        print("protocol identity MATCH false")
        return 2
    if proto.get("executed") is not False:
        print("protocol identity MATCH false")
        return 2
    cfg = _load(os.path.join(root, "config.json"))
    for key in ("protocol_commit", "candidate_freeze_commit"):
        sha = cfg.get(key) or ""
        if len(sha) != 40 or any(ch not in "0123456789abcdef" for ch in sha.lower()):
            print("protocol identity MATCH false")
            return 2
    print("protocol identity match true")
    copied = os.path.join(root, "candidate-freeze.json")
    if sha256_file(copied) != sha256_file(CANDIDATE_FREEZE):
        print("candidate freeze copy MATCH false")
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
    mechanism, regression, safety = build_all(root)
    checks = (
        ("mechanism", os.path.join(root, "metrics", "mechanism.json"), mechanism),
        ("regression", os.path.join(root, "metrics", "regression.json"), regression),
        ("safety", os.path.join(root, "metrics", "safety.json"), safety),
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
    print(f"verified_head {repro.get('verified_head') or ''}")
    print("OK")
    return 0


def record_clean_clone(root: str, verified_head: str) -> None:
    path = os.path.join(root, "metrics", "reproduction.json")
    repro = _load(path)
    repro["clean_clone_verified"] = True
    repro["verified_head"] = verified_head
    repro["match"] = True
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(repro, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
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
    with open(man_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(man, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=PUBLISHED_ROOT)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--record-clean-clone", default="")
    args = parser.parse_args(argv)
    if "experiments/runs" in os.path.normpath(args.root).replace("\\", "/"):
        print("FAIL: no experiments/runs fallback", file=sys.stderr)
        return 2
    if args.record_clean_clone:
        record_clean_clone(args.root, args.record_clean_clone)
        print("recorded clean-clone", args.record_clean_clone)
        return 0
    if args.verify:
        return verify(args.root)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
