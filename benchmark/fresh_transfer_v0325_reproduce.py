"""python -m benchmark.fresh_transfer_v0325_reproduce --root experiments/published/fresh-transfer-v0.3.25 --verify"""
from __future__ import annotations

import json
import os
import subprocess
import sys

from benchmark.algorithm_freeze import sha256_file, verify_freeze
from benchmark.fresh_composite_analysis import product_default_changed
from benchmark.fresh_transfer_v0325_analysis import derive_v0325_outcome
from benchmark.fresh_transfer_v0325_publish import CANDIDATE_FREEZE, PROTOCOL, SUITE
from benchmark.fresh_transfer_v0325_run import CELLS, _dir, _evidence, _stem

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_SHA = "9403e81f34625ff225f4cca69bf65c992d937305cb3a516a8be12a7bc9e08d45"


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
    if verify_freeze(os.path.join(ROOT, SUITE)):
        return _fail("suite freeze mismatch")
    if verify_freeze(os.path.join(ROOT, CANDIDATE_FREEZE)):
        return _fail("candidate freeze mismatch")
    if sha256_file(os.path.join(
        ROOT, "ghostqa", "exploration", "episode_drain_epoch_guard.py"
    )) != SOURCE_SHA:
        return _fail("candidate source changed")
    print("freezes match true")
    if sha256_file(os.path.join(root, "protocol.json")) != sha256_file(os.path.join(ROOT, PROTOCOL)):
        return _fail("protocol hash mismatch")
    protocol = _load(os.path.join(root, "protocol.json"))
    if protocol.get("executed") is not False or protocol.get("matrix", {}).get("cells_total") != 38:
        return _fail("protocol identity changed")
    print("protocol match true")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    repro = _load(os.path.join(root, "metrics", "reproduction.json"))
    pre = repro.get("preregistration_commit") or ""
    if not pre or not _ancestor(pre, head):
        return _fail("preregistration commit is not an ancestor of HEAD")
    print("protocol order true")
    if len(CELLS) != 38:
        return _fail("cell list is not 38")
    missing = []
    for app, policy, budget in CELLS:
        base = os.path.join(root, "evidence", _evidence(app))
        stem = _stem(policy, budget)
        for ext in (".config.json", ".events.jsonl", ".sequence_events.json", ".graph.json", ".DONE"):
            if not os.path.isfile(os.path.join(base, stem + ext)):
                missing.append(f"{app} {stem}{ext}")
    if missing:
        return _fail("missing cells " + ", ".join(missing[:8]))
    print("38 cells present")
    man = _load(os.path.join(root, "evidence-manifest.json"))
    bad = []
    for rec in man.get("files") or []:
        rel = rec.get("relative_path") or ""
        path = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.isfile(path) or sha256_file(path) != rec.get("sha256"):
            bad.append(rel)
    if bad:
        return _fail("manifest mismatch " + ", ".join(bad[:8]))
    print(f"evidence files verified {len(man.get('files') or [])}")
    saved = _load(os.path.join(root, "metrics", "safety.json"))
    derived = derive_v0325_outcome(**(saved.get("facts") or {}))
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
        print("recorded clean-clone", args.record_clean_clone)
    if args.verify:
        return verify(args.root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
