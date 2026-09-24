"""python -m benchmark.episode_drain_epoch_reproduce --root experiments/published/episode-drain-epoch-v0.3.24 --verify"""
from __future__ import annotations

import json
import os
import subprocess
import sys

from benchmark.algorithm_freeze import sha256_file, verify_freeze
from benchmark.fresh_composite_analysis import product_default_changed
from benchmark.episode_drain_epoch_analysis import derive_v0324_outcome
from benchmark.episode_drain_epoch_publish import AUDIT, FREEZE, PROTOCOL
from benchmark.episode_drain_epoch_run import CELLS, cell_stem
from benchmark.return_cycle_guard_reproduce import verify_candidate_identity

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD_FREEZE = os.path.join(ROOT, "experiments", "frozen", "ghost-return-cycle-guard-v0.3.9", "freeze.json")
FINDING_FREEZE = os.path.join(ROOT, "experiments", "frozen", "ghost-finding-return-entry-v0.3.19", "freeze.json")
WAYPOINT_FREEZE = os.path.join(ROOT, "experiments", "frozen", "ghost-return-waypoint-frontier-v0.3.21", "freeze.json")
DEBT_FREEZE = os.path.join(ROOT, "experiments", "frozen", "ghost-residual-frontier-debt-v0.3.23", "freeze.json")
SUITE_FREEZE = os.path.join(ROOT, "experiments", "frozen", "v0.3.20-fresh-composite-suite", "freeze.json")
EVIDENCE = {"buggy-flow": "deepbench", "buggy-wiki": "wiki"}


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def _ancestor(earlier: str, later: str) -> bool:
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", earlier, later],
        cwd=ROOT, capture_output=True, text=True)
    return proc.returncode == 0


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
    with open(man_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(man, ensure_ascii=False, indent=2) + "\n")


def verify(root: str) -> int:
    print(f"root {root}")
    norm = os.path.normpath(root).replace("\\", "/")
    if "experiments/runs" in norm:
        return _fail("FAIL: no experiments/runs fallback")
    if verify_candidate_identity(GUARD_FREEZE):
        return _fail("v0.3.9 guard identity mismatch")
    print("v0.3.9 guard identity true")
    for path, label in (
        (FINDING_FREEZE, "v0.3.19"),
        (WAYPOINT_FREEZE, "v0.3.21"),
        (SUITE_FREEZE, "v0.3.20 suite"),
        (DEBT_FREEZE, "v0.3.23 candidate"),
        (os.path.join(ROOT, FREEZE), "v0.3.24 candidate"),
    ):
        if verify_freeze(path):
            return _fail(label + " freeze mismatch")
    print("historical and candidate freezes match true")
    if sha256_file(os.path.join(root, "protocol.json")) != sha256_file(os.path.join(ROOT, PROTOCOL)):
        return _fail("protocol hash mismatch")
    if sha256_file(os.path.join(root, "v0323-episode-drain-audit.json")) != sha256_file(os.path.join(ROOT, AUDIT)):
        return _fail("audit hash mismatch")
    protocol = _load(os.path.join(root, "protocol.json"))
    if protocol.get("starting_head") != "4b7886e854254cbcca3d6511a8234f0d69e31047":
        return _fail("starting head mismatch")
    if protocol.get("executed") is not False:
        return _fail("preregistered protocol executed flag changed")
    if protocol.get("matrix", {}).get("cells_total") != 24:
        return _fail("cell count changed")
    print("protocol and audit match true")
    repro = _load(os.path.join(root, "metrics", "reproduction.json"))
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    pre = repro.get("preregistration_commit") or ""
    if not pre or not _ancestor(pre, head):
        return _fail("preregistration commit is not an ancestor of HEAD")
    print("protocol order true")
    missing = []
    if len(CELLS) != 24:
        return _fail("runner cell list is not 24")
    for app, budget in CELLS:
        evidence = EVIDENCE.get(app, app)
        stem = cell_stem(budget)
        base = os.path.join(root, "evidence", evidence)
        for ext in (".config.json", ".events.jsonl", ".sequence_events.json", ".graph.json", ".DONE"):
            if not os.path.isfile(os.path.join(base, stem + ext)):
                missing.append(f"{evidence} {stem}{ext}")
    if missing:
        return _fail("missing cells " + ", ".join(missing[:8]))
    print("24 cells present")
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
    saved = _load(os.path.join(root, "metrics", "safety.json"))
    derived = derive_v0324_outcome(**(saved.get("facts") or {}))
    recorded = _load(os.path.join(root, "metrics", "mechanism.json")).get("derived") or {}
    if derived.get("outcome") != recorded.get("outcome"):
        return _fail("outcome recomputation mismatch")
    print("outcome " + derived["outcome"])
    if product_default_changed() or repro.get("product_default_changed"):
        return _fail("product default changed")
    print("product default changed false")
    if repro.get("clean_clone_verified"):
        verified = repro.get("verified_head") or ""
        if not verified or not _ancestor(verified, head):
            return _fail("clean clone head mismatch")
    print(f"clean_clone_verified {bool(repro.get('clean_clone_verified'))}")
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
