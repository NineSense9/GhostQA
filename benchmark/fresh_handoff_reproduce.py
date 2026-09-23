"""python -m benchmark.fresh_handoff_reproduce --root experiments/published/fresh-handoff-v0.3.15 --verify"""
from __future__ import annotations

import json
import os
import sys

from benchmark.algorithm_freeze import DEFAULT_FREEZE, sha256_file, verify_freeze
from benchmark.application_shape_evidence import canonical_json_bytes, sha256_bytes
from benchmark.fresh_handoff_publish import (
    CANDIDATE_FREEZE, CANDIDATE_SHA, FREEZE_COMMIT, MEASUREMENT_COMMIT,
    NEGATIVE, POLICY, POSITIVE, PROTOCOL, PROTOCOL_COMMIT, QUAL, STARTING,
    SUITE_FREEZE, _expected_cells, collect,
)
from benchmark.fresh_handoff_analysis import derive_v0315_outcome
from benchmark.return_cycle_guard_reproduce import verify_candidate_identity

PUBLISHED_ROOT = os.path.join("experiments", "published", "fresh-handoff-v0.3.15")


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
    if verify_candidate_identity():
        print("v0.3.9 guard freeze MATCH false")
        return 2
    print("v0.3.9 guard freeze match true")
    if verify_freeze(CANDIDATE_FREEZE) or sha256_file(
        "ghostqa/exploration/horizon_handoff_guard.py") != CANDIDATE_SHA:
        print("v0.3.14 candidate freeze MATCH false")
        return 2
    print("v0.3.14 candidate freeze match true")
    if verify_freeze(SUITE_FREEZE):
        print("v0.3.15 suite freeze MATCH false")
        return 2
    print("v0.3.15 suite freeze match true")
    for app in list(POSITIVE) + [NEGATIVE]:
        path = os.path.join(
            "experiments", "frozen", "v0.3.15-fresh-handoff-suite", app, "freeze.json")
        if verify_freeze(path):
            print(f"{app} target freeze MATCH false")
            return 2
        print(f"{app} target freeze match true")
    if sha256_file(os.path.join(root, "protocol.json")) != sha256_file(PROTOCOL):
        print("protocol identity MATCH false")
        return 2
    proto = _load(PROTOCOL)
    if proto.get("executed") is not False or proto.get("matrix", {}).get("cells_total") != 30:
        print("protocol identity MATCH false")
        return 2
    if proto.get("matrix", {}).get("seed") != 1:
        print("protocol identity MATCH false")
        return 2
    if sha256_file(os.path.join(root, "topology-qualification.json")) != sha256_file(QUAL):
        print("qualification hash MATCH false")
        return 2
    print("protocol identity match true")
    print("qualification hash match true")
    cfg = _load(os.path.join(root, "config.json"))
    for key, value in (
        ("starting_head", STARTING),
        ("protocol_commit", PROTOCOL_COMMIT),
        ("suite_freeze_commit", FREEZE_COMMIT),
        ("measurement_commit", MEASUREMENT_COMMIT),
    ):
        if cfg.get(key) != value:
            print("protocol identity MATCH false")
            return 2
    if cfg.get("product_default_changed") is not False:
        print("product default MATCH false")
        return 2
    man = _load(os.path.join(root, "evidence-manifest.json"))
    bad = []
    seen = set()
    for rec in man.get("files") or []:
        rel = rec.get("relative_path") or ""
        if rel in seen or rel == "evidence-manifest.json":
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
    print("evidence manifest pass true")
    cells = _expected_cells()
    for app, code, budget in cells:
        stem = f"{POLICY[code]}_b{budget}_s1"
        for ext in (".events.jsonl", ".sequence_events.json", ".graph.json", ".config.json", ".DONE"):
            if not os.path.isfile(os.path.join(root, "evidence", app, stem + ext)):
                print(f"missing cell {app} {code} {budget}")
                return 2
    if len(cells) != 30:
        print("cell count MATCH false")
        return 2
    print("30 cells present")
    # Recompute gates from the published evidence copy.
    published_run = root
    # collect() reads experiments/runs layout: evidence/<app> under the root.
    report = collect(published_run)
    if report["missing"]:
        print("published evidence incomplete")
        return 2
    aggregate = _load(os.path.join(root, "metrics", "aggregate.json"))
    reproduced = {
        "static_positive_targets": 3,
        "actual_evaluable_positive_targets": aggregate["derived"]["actual_evaluable_positive_targets"],
        "full_transfer_targets": aggregate["derived"]["full_transfer_targets"],
        "bug_loss_apps": aggregate["bug_loss_apps"],
        "negative_control_handoffs": aggregate["negative_control_handoffs"],
        "witness_violations": aggregate["witness_violations"],
        "terminal_accounting_violations": aggregate["terminal_accounting_violations"],
        "derived": aggregate["derived"],
    }
    # Rebuild the derived outcome from the published per-target file's inputs.
    per = report
    evaluable = sum(1 for app in POSITIVE if per["targets"][app]["evaluable"]["actual_evaluable"])
    transferred = sum(1 for app in POSITIVE if per["targets"][app]["full_transfer"]["pass"])
    losses = [app for app in list(POSITIVE) + [NEGATIVE] if per["targets"][app]["lost_vs_guard"]]
    witness = sum(
        int((per["targets"][app]["cells"].get("H@120") or {}).get("witness_violations") or 0)
        for app in list(POSITIVE) + [NEGATIVE]
    )
    terminal = sum(
        int((per["targets"][app]["cells"].get("H@120") or {}).get("terminal_accounting_violations") or 0)
        for app in list(POSITIVE) + [NEGATIVE]
    )
    safety = _load(os.path.join(root, "metrics", "safety.json"))
    derived = derive_v0315_outcome(
        candidate_freeze_ok=True,
        suite_freeze_ok=True,
        protocol_ok=True,
        static_qualification_ok=True,
        historical_safety_ok=safety.get("handoff_model_invariant_failures") == 0
        and safety.get("historical_return_all_pass") is True
        and safety.get("handoff_model_raw_traces") == 19607,
        source_isolation_ok=not safety.get("app_specific_needles"),
        witness_violations=witness,
        terminal_accounting_violations=terminal,
        app_specific_logic=bool(safety.get("app_specific_needles")),
        bug_loss_apps=losses,
        negative_control_handoffs=int(
            per["targets"][NEGATIVE]["negative_control"]["horizon_handoff_started_events"] or 0),
        product_default_changed=False,
        post_freeze_tuning=False,
        judge_leakage=False,
        event_match_ok=not per["match_failures"],
        actual_evaluable_positive_targets=evaluable,
        full_transfer_targets=transferred,
    )
    if derived["outcome"] != aggregate["derived"]["outcome"]:
        print("outcome recomputation MATCH false")
        print(derived["outcome"], aggregate["derived"]["outcome"])
        return 2
    if sha256_bytes(canonical_json_bytes(aggregate)) != sha256_file(
        os.path.join(root, "metrics", "aggregate.json")):
        print("aggregate hash MATCH false")
        return 2
    print("aggregate match true")
    print(f"outcome {derived['outcome']}")
    print("outcome recomputation match true")
    repro = _load(os.path.join(root, "metrics", "reproduction.json"))
    print(f"clean_clone_verified {str(bool(repro.get('clean_clone_verified'))).lower()}")
    print("product default changed false")
    print("OK")
    return 0


def main(argv=None) -> int:
    import argparse
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
