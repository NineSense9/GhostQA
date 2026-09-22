"""python -m benchmark.multi_target_reproduce --root experiments/published/multi-target-replication-v0.3.11 --verify
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
from benchmark.multi_target_analysis import PUBLISHED_ROOT, derive_suite
from benchmark.return_cycle_guard_reproduce import verify_candidate_identity
from benchmark.target_freeze import V0311_SUITE_FREEZE, V0311_TARGET_FREEZES
from benchmark.multitarget_vocab import APP_NAMES
from benchmark.return_cycle_modelcheck import run_exhaustive_check
from benchmark.return_cycle_safety import collect_safety_suite

PROTOCOL = os.path.join("experiments", "validation", "v0.3.11", "protocol.json")


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
        bad.append("protocol.json hash mismatch vs experiments/validation/v0.3.11")
    proto = json.load(open(PROTOCOL, encoding="utf-8"))
    if proto.get("candidate", {}).get("identity") != "ghost-structural-return-guard":
        bad.append("candidate identity")
    if proto.get("matrix", {}).get("primary_budgets") != [40, 80, 120]:
        bad.append("budgets")
    if proto.get("matrix", {}).get("seeds") != [1]:
        bad.append("seeds")
    if proto.get("matrix", {}).get("apps") != list(APP_NAMES):
        bad.append("apps")
    cfg_path = os.path.join(root, "config.json")
    if os.path.isfile(cfg_path):
        cfg = json.load(open(cfg_path, encoding="utf-8"))
        sha = cfg.get("protocol_commit") or ""
        if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha.lower()):
            bad.append("protocol_commit identity")
        freeze_sha = cfg.get("suite_freeze_commit") or ""
        if len(freeze_sha) != 40 or any(
                c not in "0123456789abcdef" for c in freeze_sha.lower()):
            bad.append("suite_freeze_commit identity")
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
    suite_bad = verify_freeze(V0311_SUITE_FREEZE)
    if suite_bad:
        print("generator/suite freeze MATCH false")
        for line in suite_bad:
            print(" ", line)
        return 2
    print("generator freeze match true")
    for name, path in V0311_TARGET_FREEZES.items():
        bad = verify_freeze(path)
        if bad:
            print(f"{name} target freeze MATCH false")
            for line in bad:
                print(" ", line)
            return 2
        print(f"{name} target freeze match true")
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
    safety_path = os.path.join(root, "evidence", "safety", "safety.json")
    safety = json.load(open(safety_path, encoding="utf-8")) if os.path.isfile(safety_path) else {}
    s17 = collect_safety_suite()
    if not s17.get("all_pass"):
        print("S1-S7 MATCH false")
        return 2
    print("S1-S7 pass true")
    exhaustive = run_exhaustive_check()
    if exhaustive.get("failures"):
        print("exhaustive safety MATCH false")
        return 2
    print(f"exhaustive traces {exhaustive.get('traces_enumerated')} failures 0")
    suite = derive_suite(
        root, safety=safety, historical_ok=True, freeze_ok=True)
    reproduced = sha256_bytes(canonical_json_bytes({
        "derived": suite["derived"],
        "interpretation": suite["interpretation"],
        "replication": [
            {
                "target": app,
                "opportunity": (t.get("c1_120") or {}).get("c1_opportunity_count"),
                "escape": t.get("guard_escapes"),
                "novel_after_escape": t.get("post_escape_novelty"),
                "c1_bugs_lost": t.get("lost_c1_bugs"),
                "return_regression": t.get("lost_meaningful_return_keys"),
                "transfer_demonstrated": bool(
                    t.get("guard_escapes") and t.get("post_escape_novelty")),
            }
            for app, t in suite["targets"].items()
        ],
    }))
    expected_path = os.path.join(root, "metrics", "metrics.json")
    expected = sha256_file(expected_path) if os.path.isfile(expected_path) else ""
    print(f"metrics expected sha256 {expected}")
    print(f"metrics reproduced sha256 {reproduced}")
    match = expected == reproduced
    print(f"metrics match {str(match).lower()}")
    print(f"outcome {suite['derived']['outcome']}")
    cfg = json.load(open(os.path.join(root, "config.json"), encoding="utf-8"))
    per_path = os.path.join(root, "metrics", "per-target.json")
    if os.path.isfile(per_path) and cfg.get("expected_per_target_sha256"):
        per_got = sha256_file(per_path)
        per_exp = cfg["expected_per_target_sha256"]
        print(f"per-target expected sha256 {per_exp}")
        print(f"per-target file sha256 {per_got}")
        if per_got != per_exp:
            print("per-target hash MATCH false")
            return 2
        print("per-target hash match true")
    if not match:
        return 2
    print("OK")
    return 0


def record_clean_clone(root: str, verified_head: str) -> None:
    """Update reproduction.json after a successful clean-clone verify.

    Rebuilds only the reproduction.json hash in evidence-manifest.json.
    """
    path = os.path.join(root, "metrics", "reproduction.json")
    with open(path, encoding="utf-8") as f:
        repro = json.load(f)
    repro["clean_clone_verified"] = True
    repro["verified_head"] = verified_head
    repro["match"] = True
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(repro, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    man_path = os.path.join(root, "evidence-manifest.json")
    man = json.load(open(man_path, encoding="utf-8"))
    new_hash = sha256_file(path)
    found = False
    for rec in man.get("files") or []:
        if rec.get("relative_path") == "metrics/reproduction.json":
            rec["sha256"] = new_hash
            found = True
    if not found:
        raise SystemExit("metrics/reproduction.json missing from evidence-manifest.json")
    with open(man_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(man, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=PUBLISHED_ROOT)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--record-clean-clone", default="",
                    help="publication SHA to store after a successful clean-clone verify")
    args = ap.parse_args(argv)
    if "experiments/runs" in os.path.normpath(args.root).replace("\\", "/"):
        print("FAIL: no experiments/runs fallback", file=sys.stderr)
        return 2
    if args.record_clean_clone:
        record_clean_clone(args.root, args.record_clean_clone)
        print("recorded clean-clone", args.record_clean_clone)
        return 0
    if args.verify:
        return verify(args.root)
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
