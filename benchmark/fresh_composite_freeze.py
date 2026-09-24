"""Write the v0.3.20 suite and per-target freezes. No policy execution."""
from __future__ import annotations

import hashlib
import json
import os

from benchmark.fresh_composite_generator import APP_NAMES, generated_relpaths
from benchmark.fresh_composite_qualify import write_qualification

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROTOCOL_COMMIT = "c278b8274d92c509ea4d29de286150e51c4918ea"
CANDIDATE_SHA = "0bfec3c7bd2811f154daa83bc81fde632976b8ab6e1da9ee6a208cf81c4bb42c"
SUITE = os.path.join("experiments", "frozen", "v0.3.20-fresh-composite-suite")
SOURCE = (
    "benchmark/fresh_composite_generator.py",
    "benchmark/fresh_composite_vocab.py",
    "benchmark/fresh_composite_js.py",
    "benchmark/fresh_composite_qualify.py",
    "apps/generate_v0320_targets.py",
    "experiments/validation/v0.3.20/protocol.json",
    "experiments/validation/v0.3.20/README.md",
    "experiments/validation/v0.3.20/static-qualification.json",
)


def _record(rel: str) -> dict:
    path = os.path.join(ROOT, rel.replace("/", os.sep))
    data = open(path, "rb").read().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def _header(target: str) -> dict:
    return {
        "round": "v0.3.20",
        "purpose": "v0.3.20 fresh composite suite freeze before policy evaluation",
        "protocol_commit": PROTOCOL_COMMIT,
        "freeze_commit": "pending",
        "candidate_identity": "ghost-structural-finding-return-entry-drain-guard",
        "candidate_source_sha256": CANDIDATE_SHA,
        "candidate_freeze": "experiments/frozen/ghost-finding-return-entry-v0.3.19/freeze.json",
        "no_target_policy_evaluation_before_freeze": True,
        "manifest_is_judge_only": True,
        "mechanism_opportunities_are_judge_only": True,
        "post_evaluation_changes_invalidate_protocol_identity": True,
        "hash_normalization": "LF newlines",
        "target": target,
        "qualification": "experiments/validation/v0.3.20/static-qualification.json",
    }


def _dump(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> int:
    qual = os.path.join(ROOT, "experiments", "validation", "v0.3.20", "static-qualification.json")
    write_qualification(os.path.join(ROOT, "apps"), qual)
    suite_files = []
    for rel in SOURCE:
        suite_files.append(rel)
    per = {}
    for name in APP_NAMES:
        rels = list(generated_relpaths(name))
        per[name] = rels
        for rel in rels:
            if rel not in suite_files:
                suite_files.append(rel)
    suite = _header("v0.3.20-fresh-composite-suite")
    suite["files"] = {rel: _record(rel) for rel in suite_files}
    _dump(os.path.join(ROOT, SUITE, "freeze.json"), suite)
    for name, rels in per.items():
        payload = _header(name)
        payload["purpose"] = "v0.3.20 fresh target freeze before policy evaluation"
        payload["files"] = {rel: _record(rel) for rel in rels}
        _dump(os.path.join(ROOT, SUITE, name, "freeze.json"), payload)
    print("wrote suite freeze", len(suite_files), "files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
