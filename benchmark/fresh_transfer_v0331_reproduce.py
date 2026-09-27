"""Recompute the published v0.3.31 outcome from the frozen tree."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

from benchmark.algorithm_freeze import sha256_file, verify_freeze
from benchmark.fresh_composite_analysis import product_default_changed
from benchmark.fresh_transfer_v0331_analysis import derive_v0331_outcome
from benchmark.fresh_transfer_v0331_publish import collect

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARENT_SHA = "9403e81f34625ff225f4cca69bf65c992d937305cb3a516a8be12a7bc9e08d45"
SOURCE_SHA = "fef17c7441df69e68f083ec04e201e2a942b0be6cacf59a054e135d09b49d018"
PROTOCOL_COMMIT = "9d7f6b137646e06a66ba79d69366a6202658712a"


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


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
    if not os.path.isdir(root):
        return _fail(f"missing {root}")
    bad = verify_freeze(os.path.join(ROOT, "experiments", "frozen", "v0.3.31-fresh-transfer-suite", "freeze.json"))
    bad += verify_freeze(os.path.join(ROOT, "experiments", "frozen", "ghost-alternate-payload-v0.3.31", "freeze.json"))
    if bad:
        return _fail("freeze mismatch\n" + "\n".join(bad))
    if sha256_file(os.path.join(ROOT, "ghostqa", "exploration", "episode_drain_epoch_guard.py")) != PARENT_SHA:
        return _fail("v0.3.24 candidate changed")
    if sha256_file(os.path.join(ROOT, "ghostqa", "exploration", "untried_sibling_guard.py")) != "0a425a46df8884bc8260bf2c9fa1ac3c85da6a7931b7dec2899a94b9daac35dd":
        return _fail("v0.3.26 candidate changed")
    if sha256_file(os.path.join(ROOT, "ghostqa", "exploration", "parent_hub_sibling_guard.py")) != "33a479db2f062071438bb05c4b8dcc90a7a85bdcec4b97e54ebf06d2ebf7183b":
        return _fail("v0.3.27 candidate changed")
    if sha256_file(os.path.join(ROOT, "ghostqa", "exploration", "repeat_click_guard.py")) != "e52e87a312120f838e6b9d922928f7666824d6f7fd32c4e73c3b5e538f41b501":
        return _fail("v0.3.30 candidate changed")
    if sha256_file(os.path.join(ROOT, "ghostqa", "exploration", "alternate_payload_guard.py")) != SOURCE_SHA:
        return _fail("v0.3.31 candidate changed")
    protocol = _load(os.path.join(ROOT, "experiments", "validation", "v0.3.31", "protocol.json"))
    if protocol.get("executed") is not False or protocol.get("matrix", {}).get("cells_total") != 40:
        return _fail("protocol mismatch")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    if not _ancestor(PROTOCOL_COMMIT, head):
        return _fail("protocol commit is not an ancestor")
    if product_default_changed():
        return _fail("product default changed")
    report = collect(root)
    derived = derive_v0331_outcome(**report["facts"])
    published = _load(os.path.join(root, "metrics", "mechanism.json")).get("derived") or {}
    if derived["outcome"] != published.get("outcome"):
        return _fail(f"outcome {derived['outcome']} != published {published.get('outcome')}")
    manifest = _load(os.path.join(root, "evidence-manifest.json"))
    files = manifest.get("files") or []
    if len(files) != manifest.get("expected_file_count"):
        return _fail("manifest count mismatch")
    for rec in files:
        path = os.path.join(root, rec["relative_path"].replace("/", os.sep))
        if not os.path.isfile(path) or sha256_file(path) != rec.get("sha256"):
            return _fail(f"evidence hash mismatch {rec.get('relative_path')}")
    repro = _load(os.path.join(root, "metrics", "reproduction.json"))
    if repro.get("clean_clone_verified"):
        verified = repro.get("verified_head") or ""
        if not verified or not _ancestor(verified, head):
            return _fail("clean clone head mismatch")
    print(f"evidence files {len(files)}")
    print(f"outcome {derived['outcome']}")
    print("product default changed false")
    print(f"clean_clone_verified {bool(repro.get('clean_clone_verified'))}")
    print("OK")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--record-clean-clone", default="")
    args = parser.parse_args(argv)
    root = args.root if os.path.isabs(args.root) else os.path.join(ROOT, args.root)
    if args.record_clean_clone:
        record_clean_clone(root, args.record_clean_clone)
        print("recorded clean-clone", args.record_clean_clone)
    if args.verify:
        return verify(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
