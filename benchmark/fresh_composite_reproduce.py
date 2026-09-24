"""python -m benchmark.fresh_composite_reproduce --root experiments/published/fresh-composite-v0.3.20 --verify"""
from __future__ import annotations

import json
import os
import sys

from benchmark.algorithm_freeze import sha256_file, verify_freeze
from benchmark.application_shape_evidence import sha256_file as sha_file
from benchmark.fresh_composite_analysis import derive_v0320_outcome, product_default_changed
from benchmark.fresh_composite_publish import (
    CANDIDATE_SHA, FREEZE_COMMIT, PROTOCOL_COMMIT, STARTING,
)
from benchmark.fresh_composite_qualify import _public_qualification, qualify_path
from benchmark.fresh_composite_run import APPS, CELLS, POLICY, cell_stem
from benchmark.return_cycle_guard_reproduce import verify_candidate_identity

GUARD_FREEZE = os.path.join(
    "experiments", "frozen", "ghost-return-cycle-guard-v0.3.9", "freeze.json")
C1_FREEZE = os.path.join(
    "experiments", "frozen", "ghost-structural-v0.3.6", "freeze.json")
CANDIDATE_FREEZE = os.path.join(
    "experiments", "frozen", "ghost-finding-return-entry-v0.3.19", "freeze.json")
SUITE = os.path.join(
    "experiments", "frozen", "v0.3.20-fresh-composite-suite", "freeze.json")
PROTOCOL = os.path.join("experiments", "validation", "v0.3.20", "protocol.json")
QUAL = os.path.join("experiments", "validation", "v0.3.20", "static-qualification.json")


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
    if verify_candidate_identity():
        print("v0.3.9 guard freeze MATCH false")
        return 2
    print("v0.3.9 guard freeze match true")
    if verify_freeze(C1_FREEZE):
        print("v0.3.6 C1 freeze MATCH false")
        return 2
    print("v0.3.6 C1 freeze match true")
    if verify_freeze(CANDIDATE_FREEZE):
        print("v0.3.19 candidate freeze MATCH false")
        return 2
    if sha256_file(os.path.join("ghostqa", "exploration", "finding_return_entry_guard.py")) != CANDIDATE_SHA:
        print("candidate source hash mismatch")
        return 2
    print("v0.3.19 candidate freeze match true")
    if verify_freeze(SUITE):
        print("v0.3.20 suite freeze MATCH false")
        return 2
    print("v0.3.20 suite freeze match true")
    for app, meta in APPS.items():
        if verify_freeze(meta["freeze"]):
            print(f"{app} target freeze MATCH false")
            return 2
    print("six target freezes match true")
    proto = _load(os.path.join(root, "protocol.json"))
    if proto.get("version") != "v0.3.20" or proto.get("starting_head") != STARTING:
        print("protocol identity mismatch")
        return 2
    if sha256_file(os.path.join(root, "protocol.json")) != sha256_file(PROTOCOL):
        print("published protocol hash mismatch")
        return 2
    print("protocol identity match true")
    if proto.get("matrix", {}).get("cells_total") != 42 or len(CELLS) != 42:
        print("cell count mismatch")
        return 2
    saved_qual = _load(os.path.join(root, "static-qualification.json"))
    live_qual = _load(QUAL)
    if saved_qual != live_qual:
        print("static qualification mismatch")
        return 2
    for app in APPS:
        got = _public_qualification(qualify_path(os.path.join(APPS[app]["dir"], "topology.json")))
        if got != saved_qual["apps"][app]:
            print(f"qualification recompute mismatch {app}")
            return 2
    print("static qualification recompute match true")
    missing = []
    for cell in CELLS:
        stem = cell_stem(POLICY[cell["policy"]], cell["budget"])
        base = os.path.join(root, "evidence", cell["app"])
        for ext in (".events.jsonl", ".sequence_events.json", ".graph.json", ".config.json", ".DONE"):
            if not os.path.isfile(os.path.join(base, stem + ext)):
                missing.append(cell["app"] + " " + stem + ext)
    if missing:
        print("missing cells " + ", ".join(missing[:8]))
        return 2
    print("42 cells present")
    man = _load(os.path.join(root, "evidence-manifest.json"))
    bad = 0
    for rec in man.get("files") or []:
        path = os.path.join(root, rec["relative_path"].replace("/", os.sep))
        if sha_file(path) != rec["sha256"]:
            print("manifest mismatch", rec["relative_path"])
            bad += 1
    if bad or len(man.get("files") or []) != man.get("expected_file_count"):
        return 2
    print(f"evidence files verified {len(man.get('files') or [])}")
    per = _load(os.path.join(root, "metrics", "per-target.json"))
    derived = derive_v0320_outcome(per)
    aggregate = _load(os.path.join(root, "metrics", "aggregate.json"))
    if derived["outcome"] != aggregate["outcome"]:
        print("outcome recomputation mismatch", derived["outcome"], aggregate["outcome"])
        return 2
    print("outcome", derived["outcome"])
    print("outcome recomputation match true")
    repro = _load(os.path.join(root, "metrics", "reproduction.json"))
    print("clean_clone_verified", bool(repro.get("clean_clone_verified")))
    if product_default_changed() or aggregate.get("product_default_changed"):
        print("product default changed")
        return 2
    print("product default changed false")
    if aggregate.get("promotion_readiness") not in ("not_ready", "evidence_supports_productization_study"):
        print("promotion readiness invalid")
        return 2
    if derived["outcome"] != "A" and aggregate.get("promotion_readiness") != "not_ready":
        print("promotion readiness does not match outcome")
        return 2
    print("promotion readiness", aggregate.get("promotion_readiness"))
    if repro.get("protocol_commit") != PROTOCOL_COMMIT or repro.get("suite_freeze_commit") != FREEZE_COMMIT:
        print("phase commit identity mismatch")
        return 2
    print("phase commits match true")
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
