"""python -m benchmark.post_escape_sink_reproduce --root experiments/published/post-escape-sink-v0.3.22 --verify"""
from __future__ import annotations

import json
import os
import subprocess
import sys

from benchmark.algorithm_freeze import sha256_file, verify_freeze
from benchmark.fresh_composite_analysis import product_default_changed
from benchmark.post_escape_sink_analysis import (
    CELLS,
    CANDIDATE_FREEZE,
    HISTORICAL_BUDGET,
    POSITIVE_TARGETS,
    ROOT,
    SUITE_FREEZE,
    VALIDATION_DIR,
    V0321_PUBLICATION,
    target_freeze_path,
)
from benchmark.post_escape_sink_publish import build_payloads
from benchmark.return_waypoint_frontier_reproduce import verify as verify_v0321
from benchmark.fresh_composite_reproduce import verify as verify_v0320


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def record_clean_clone(root: str, verified_head: str) -> None:
    path = os.path.join(root, "metrics", "reproduction.json")
    repro = _load(path)
    repro["clean_clone_verified"] = True
    repro["verified_head"] = verified_head
    text = json.dumps(repro, ensure_ascii=False, indent=2) + "\n"
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
    man_text = json.dumps(man, ensure_ascii=False, indent=2) + "\n"
    with open(man_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(man_text)


def _ancestor(earlier: str, later: str) -> bool:
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", earlier, later],
        cwd=ROOT, capture_output=True, text=True)
    return proc.returncode == 0


def verify(root: str) -> int:
    print(f"root {root}")
    norm = os.path.normpath(root).replace("\\", "/")
    if "experiments/runs" in norm:
        return _fail("FAIL: no experiments/runs fallback")
    if verify_freeze(os.path.join(ROOT, CANDIDATE_FREEZE.replace("/", os.sep))):
        return _fail("v0.3.21 candidate freeze mismatch")
    print("v0.3.21 candidate freeze match true")
    if verify_freeze(os.path.join(ROOT, SUITE_FREEZE.replace("/", os.sep))):
        return _fail("v0.3.20 suite freeze mismatch")
    print("v0.3.20 suite freeze match true")
    for app in POSITIVE_TARGETS:
        if verify_freeze(os.path.join(ROOT, target_freeze_path(app).replace("/", os.sep))):
            return _fail(app + " target freeze mismatch")
    print("four target freezes match true")
    protocol = os.path.join(ROOT, VALIDATION_DIR.replace("/", os.sep), "protocol.json")
    audit = os.path.join(ROOT, VALIDATION_DIR.replace("/", os.sep), "v03121-post-escape-audit.json")
    if sha256_file(os.path.join(root, "protocol.json")) != sha256_file(protocol):
        return _fail("protocol hash mismatch")
    if sha256_file(os.path.join(root, "v03121-post-escape-audit.json")) != sha256_file(audit):
        return _fail("audit hash mismatch")
    print("protocol and audit match true")
    saved_protocol = _load(os.path.join(root, "protocol.json"))
    if saved_protocol.get("starting_head") != "deda60a7ef7494466d12598b9418234c09b543f4":
        return _fail("starting head mismatch")
    if saved_protocol.get("executed") is not False:
        return _fail("preregistered protocol executed flag changed")
    if saved_protocol.get("dominance_threshold") != 0.60:
        return _fail("dominance threshold changed")
    repro = _load(os.path.join(root, "metrics", "reproduction.json"))
    pre = repro.get("preregistration_commit") or ""
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if not pre or not _ancestor(pre, head):
        return _fail("preregistration commit is not an ancestor of HEAD")
    print("starting commit and protocol order true")
    missing = []
    for app, budget in CELLS:
        base = os.path.join(root, "evidence", app, f"b{budget}")
        for name in ("config.json", "events.jsonl", "sequence_events.json", "summary.json", "DONE"):
            if not os.path.isfile(os.path.join(base, name)):
                missing.append(f"{app} b{budget} {name}")
    if missing or len(CELLS) != 8:
        return _fail("missing cells " + ", ".join(missing[:8]))
    print("8 cells present")
    man = _load(os.path.join(root, "evidence-manifest.json"))
    bad = []
    for rec in man.get("files") or []:
        rel = rec.get("relative_path") or ""
        if rel == "evidence-manifest.json":
            return _fail("manifest self-reference")
        path = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.isfile(path) or sha256_file(path) != rec.get("sha256"):
            bad.append(rel)
    if bad:
        return _fail("manifest mismatch " + ", ".join(bad[:8]))
    print(f"evidence files verified {len(man.get('files') or [])}")
    payloads = build_payloads(root, layout="published")
    saved = _load(os.path.join(root, "metrics", "budget-diagnostic.json"))
    if payloads["diagnostic"]["diagnostic_conclusion"] != saved.get("diagnostic_conclusion"):
        return _fail(
            "conclusion recomputation "
            + payloads["diagnostic"]["diagnostic_conclusion"]
            + " != "
            + str(saved.get("diagnostic_conclusion"))
        )
    print("diagnosis " + saved.get("diagnostic_conclusion"))
    hashes = {
        "per-target.json": "per_target_sha256",
        "suffix-recurrence.json": "suffix_recurrence_sha256",
        "scc.json": "scc_sha256",
        "budget-diagnostic.json": "budget_diagnostic_sha256",
    }
    for name, key in hashes.items():
        got = sha256_file(os.path.join(root, "metrics", name))
        if got != repro.get(key):
            return _fail("hash mismatch " + name)
    static_disk = _load(os.path.join(root, "static-scc-analysis.json"))
    if static_disk != payloads["static"]:
        return _fail("static SCC recomputation mismatch")
    per_disk = _load(os.path.join(root, "metrics", "per-target.json"))
    if per_disk != payloads["per_target"]:
        return _fail("per-target recomputation mismatch")
    print("metric hashes and recomputation match true")
    if product_default_changed() or repro.get("product_default_changed") or saved.get("product_default_changed"):
        return _fail("product default changed")
    print("product default changed false")
    if repro.get("clean_clone_verified") and repro.get("verified_head") not in ("", head):
        return _fail("clean clone head mismatch")
    print(f"clean_clone_verified {repro.get('clean_clone_verified')}")
    print(f"historical budget reference {HISTORICAL_BUDGET}")
    print("OK")
    return 0


def verify_history() -> int:
    checks = [
        ("experiments/published/application-shape-v0.3.8", "benchmark.application_shape_reproduce"),
        ("experiments/published/return-cycle-guard-v0.3.9", "benchmark.return_cycle_guard_reproduce"),
        ("experiments/published/fresh-transfer-v0.3.10", "benchmark.fresh_transfer_reproduce"),
        ("experiments/published/multi-target-replication-v0.3.11", "benchmark.multi_target_reproduce"),
        ("experiments/published/nested-hub-parent-v0.3.12", "benchmark.nested_hub_reproduce"),
        ("experiments/published/nested-stack-v0.3.13", "benchmark.nested_stack_reproduce"),
        ("experiments/published/horizon-handoff-v0.3.14", "benchmark.horizon_handoff_reproduce"),
        ("experiments/published/fresh-handoff-v0.3.15", "benchmark.fresh_handoff_reproduce"),
        ("experiments/published/reentry-frontier-v0.3.16", "benchmark.reentry_frontier_reproduce"),
        ("experiments/published/local-action-drain-v0.3.17", "benchmark.local_action_drain_reproduce"),
        ("experiments/published/return-entry-drain-v0.3.18", "benchmark.return_entry_drain_reproduce"),
        ("experiments/published/finding-return-entry-v0.3.19", "benchmark.finding_return_entry_reproduce"),
    ]
    for root, module in checks:
        proc = subprocess.run(
            [sys.executable, "-m", module, "--root", root, "--verify"],
            cwd=ROOT)
        if proc.returncode != 0:
            return _fail("historical reproduce failed " + root)
        print("historical OK " + root)
    if verify_v0320(os.path.join(ROOT, "experiments", "published", "fresh-composite-v0.3.20")) != 0:
        return _fail("v0.3.20 reproduce failed")
    print("historical OK v0.3.20")
    if verify_v0321(os.path.join(ROOT, V0321_PUBLICATION.replace("/", os.sep))) != 0:
        return _fail("v0.3.21 reproduce failed")
    print("historical OK v0.3.21")
    return 0


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--record-clean-clone", default="")
    parser.add_argument("--history", action="store_true")
    args = parser.parse_args(argv)
    if args.record_clean_clone:
        record_clean_clone(args.root, args.record_clean_clone)
    code = 0
    if args.history:
        code = verify_history()
    if args.verify and code == 0:
        return verify(args.root)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
