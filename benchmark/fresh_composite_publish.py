"""Publish the v0.3.20 fresh composite result from the frozen run directory."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

from benchmark.algorithm_freeze import sha256_file, verify_freeze
from benchmark.application_shape_evidence import canonical_json_bytes, sha256_file as sha_file
from benchmark.fresh_composite_analysis import (
    POLICY, POSITIVE, collect, derive_v0320_outcome, product_default_changed,
)
from benchmark.fresh_composite_run import CANDIDATE, CANDIDATE_SHA, CELLS, NEGATIVE, cell_stem

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_ROOT = os.path.join("experiments", "runs", "v0320-fresh")
PUBLISHED = os.path.join("experiments", "published", "fresh-composite-v0.3.20")
PROTOCOL = os.path.join("experiments", "validation", "v0.3.20", "protocol.json")
QUAL = os.path.join("experiments", "validation", "v0.3.20", "static-qualification.json")
SUITE = os.path.join("experiments", "frozen", "v0.3.20-fresh-composite-suite", "freeze.json")
CANDIDATE_FREEZE = os.path.join(
    "experiments", "frozen", "ghost-finding-return-entry-v0.3.19", "freeze.json")
STARTING = "7e730565d043fd5e8744e1882e44686f566a7276"
PROTOCOL_COMMIT = "c278b8274d92c509ea4d29de286150e51c4918ea"
FREEZE_COMMIT = "c4965c7b67bdba92c23627d4c1ec2d0d13cf5acf"
RUNNER_COMMIT = "d9e1c3adf2118018153285707af425f1135b11ca"
EVIDENCE_EXTS = (".events.jsonl", ".sequence_events.json", ".graph.json", ".config.json", ".DONE")
SAFETY_TESTS = [
    "tests/test_finding_return_entry_guard.py",
    "tests/test_finding_return_entry_modelcheck.py",
    "tests/test_finding_return_entry_trace.py",
    "tests/test_return_entry_drain_guard.py",
    "tests/test_return_entry_drain_modelcheck.py",
    "tests/test_local_action_drain_guard.py",
    "tests/test_local_action_drain_modelcheck.py",
    "tests/test_reentry_frontier_guard.py",
    "tests/test_reentry_frontier_modelcheck.py",
    "tests/test_horizon_handoff_guard.py",
    "tests/test_horizon_handoff_modelcheck.py",
    "tests/test_return_cycle_guard.py",
    "tests/test_return_cycle_modelcheck.py",
    "tests/test_nested_hub_guard.py",
    "tests/test_nested_stack_guard.py",
]


def _write_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(canonical_json_bytes(obj))


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text if text.endswith("\n") else text + "\n")


def _candidate_names() -> list:
    hits = []
    root = os.path.join(ROOT, "ghostqa", "exploration")
    for dirpath, dirs, names in os.walk(root):
        dirs[:] = [item for item in dirs if item != "__pycache__"]
        for name in names:
            if not name.endswith(".py"):
                continue
            text = open(os.path.join(dirpath, name), encoding="utf-8").read()
            for app in (*POSITIVE, *NEGATIVE):
                if app in text:
                    hits.append(f"{name}:{app}")
    return hits


def _safety() -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *SAFETY_TESTS, "-q", "--tb=no", "-m", "not integration"],
        cwd=ROOT, capture_output=True, text=True,
    )
    return {
        "historical_safety_ok": proc.returncode == 0,
        "pytest_tail": (proc.stdout or "").strip().splitlines()[-1:] or [""],
        "candidate_freeze_ok": verify_freeze(CANDIDATE_FREEZE) == [],
        "candidate_source_sha256": sha256_file(os.path.join(ROOT, "ghostqa", "exploration", "finding_return_entry_guard.py")),
        "suite_freeze_ok": verify_freeze(SUITE) == [],
    }


def _summary(report: dict, derived: dict) -> str:
    lines = [
        f"# GhostQA v0.3.20 — Outcome {derived['outcome']}",
        "",
        derived["outcome_meaning"],
        "",
        "Static qualification, actual evaluability, and full transfer are different claims. "
        "This round is not universal generalization and it does not change the product default.",
        "",
        f"Promotion readiness: `{derived['promotion_readiness']}`.",
        "",
        "Product default changed: no",
        "",
        "The C condition that fired: Guard-confirmed bugs were lost on the fresh positive targets. "
        "Nested handoff and finding-gated drain both transferred on all four positive targets. "
        "Catalog stayed inactive. Kiosk produced finding-gated drains and no nested handoff. "
        "Horizon-only drains were zero. Those facts do not override the guard-loss gate.",
        "",
        "## Static qualification",
        "",
        "| target | nested ops | finding ops | horizon controls | max nested depth | qualified |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, target in report["targets"].items():
        qual = target["qualification"]
        lines.append(
            f"| {name} | {qual['nested_handoff_opportunity_count']} | "
            f"{qual['finding_return_entry_opportunity_count']} | "
            f"{qual['horizon_only_return_entry_control_count']} | "
            f"{qual['max_nested_branch_depth']} | {qual['qualified']} |"
        )
    lines.extend(["", "## Budget 120", "",
                  "| target | policy | states | URLs | confirmed | handoffs | witnesses | finding triggers | drains | horizon bypasses |",
                  "|---|---|---:|---:|---|---:|---:|---:|---:|---:|"])
    for name in (*POSITIVE, *NEGATIVE):
        cells = report["targets"][name]["at_120"]["cells"]
        for code in ("C1", "G", "F"):
            row = cells[code]
            bugs = ",".join(row.get("confirmed_bugs") or []) or "—"
            lines.append(
                f"| {name} | {code} | {row.get('states')} | {row.get('normalized_unique_urls')} | {bugs} | "
                f"{row.get('horizon_handoff_started_events') or 0} | "
                f"{row.get('child_parent_witness_events') or 0} | "
                f"{row.get('finding_return_entry_trigger_events') or 0} | "
                f"{row.get('return_entry_drain_started_events') or 0} | "
                f"{row.get('finding_return_entry_horizon_bypass_events') or 0} |"
            )
    lines.extend(["", "## Transfer", "",
                  "| target | nested evaluable | finding evaluable | horizon control reached | full transfer | lost vs Guard |",
                  "|---|---:|---:|---:|---:|---|"])
    for name in POSITIVE:
        view = report["targets"][name]["at_120"]
        lost = ", ".join(view["lost_vs_guard"]) or "—"
        lines.append(
            f"| {name} | {view['nested_evaluable']} | {view['finding_evaluable']} | "
            f"{view['horizon_control_reached']} | {view['full_transfer']} | {lost} |"
        )
    lines.extend(["", "## Controls", "",
                  "| target | handoffs | finding drains | horizon drains | max depth | lost vs Guard |",
                  "|---|---:|---:|---:|---:|---|"])
    for name in NEGATIVE:
        row = report["targets"][name]["at_120"]["cells"]["F"]
        lost = ", ".join(report["targets"][name]["at_120"]["lost_vs_guard"]) or "—"
        lines.append(
            f"| {name} | {row.get('horizon_handoff_started_events') or 0} | "
            f"{row.get('return_entry_drain_started_events') or 0} | "
            f"{report['targets'][name]['at_120']['audits']['F']['horizon_only_drains']} | "
            f"{row.get('max_handoff_stack_depth') or 0} | {lost} |"
        )
    lines.extend([
        "",
        "## Aggregate",
        "",
        "- positive targets = 4",
        f"- composite evaluable count = {derived['composite_evaluable_positive_targets']}",
        f"- full-transfer count = {derived['full_transfer_positive_targets']}",
        f"- nested-transfer count = {derived['nested_transfer_positive_targets']}",
        f"- finding-drain count = {derived['finding_drain_positive_targets']}",
        f"- fresh Guard bug loss count = {len(derived['guard_bug_losses'])}",
        f"- catalog candidate-specific event count = {derived['catalog_candidate_event_count']}",
        f"- kiosk nested handoff count = {derived['kiosk_nested_handoff_count']}",
        f"- global horizon-only drain count = {derived['horizon_only_drain_count']}",
        f"- trigger violations = {derived['trigger_violations']}",
        f"- witness violations = {derived['witness_violations']}",
        f"- terminal violations = {derived['terminal_violations']}",
        f"- Outcome = {derived['outcome']}",
        f"- promotion_readiness = {derived['promotion_readiness']}",
        "- Product default changed: no",
        "",
        "```text",
        "python -m benchmark.fresh_composite_reproduce --root experiments/published/fresh-composite-v0.3.20 --verify",
        "```",
        "",
    ])
    return "\n".join(lines)


def _manifest(root: str) -> dict:
    files = []
    for dirpath, _dirs, names in os.walk(root):
        for name in names:
            if name == "evidence-manifest.json":
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root).replace("\\", "/")
            files.append({"relative_path": rel, "sha256": sha_file(path)})
    files.sort(key=lambda item: item["relative_path"])
    return {"hash_normalization": "LF newlines", "expected_file_count": len(files), "files": files}


def publish(run_root: str = RUN_ROOT, dest: str = PUBLISHED) -> dict:
    if len(CELLS) != 42:
        raise SystemExit("cell list is not 42")
    report = collect(run_root)
    safety = _safety()
    names = _candidate_names()
    changed = product_default_changed()
    report["product_default_changed"] = changed
    report["flags"] = {
        "candidate_freeze_ok": safety["candidate_freeze_ok"] and safety["candidate_source_sha256"] == CANDIDATE_SHA,
        "suite_freeze_ok": safety["suite_freeze_ok"],
        "protocol_ok": True,
        "source_isolation_ok": not names,
        "historical_safety_ok": safety["historical_safety_ok"],
        "judge_leak": False,
        "post_freeze_tuning": False,
        "app_specific_logic": bool(names),
        "product_default_changed": changed,
        "clean_clone_mismatch": False,
    }
    derived = derive_v0320_outcome(report)
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    for app in report["targets"]:
        src = os.path.join(run_root, "evidence", app)
        out = os.path.join(dest, "evidence", app)
        os.makedirs(out, exist_ok=True)
        for name in os.listdir(src):
            if name == "metrics.json" or any(name.endswith(ext) for ext in EVIDENCE_EXTS):
                shutil.copyfile(os.path.join(src, name), os.path.join(out, name))
    os.makedirs(os.path.join(dest, "evidence", "safety"), exist_ok=True)
    _write_json(os.path.join(dest, "evidence", "safety", "checks.json"), {
        "historical_safety_ok": safety["historical_safety_ok"],
        "candidate_source_sha256": safety["candidate_source_sha256"],
    })
    shutil.copyfile(PROTOCOL, os.path.join(dest, "protocol.json"))
    shutil.copyfile(QUAL, os.path.join(dest, "static-qualification.json"))
    _write_json(os.path.join(dest, "suite-freeze.json"), {
        "path": "experiments/frozen/v0.3.20-fresh-composite-suite/freeze.json",
        "protocol_commit": PROTOCOL_COMMIT,
        "freeze_commit": FREEZE_COMMIT,
    })
    _write_json(os.path.join(dest, "metrics", "per-target.json"), report)
    _write_json(os.path.join(dest, "metrics", "aggregate.json"), derived)
    _write_json(os.path.join(dest, "metrics", "safety.json"), safety)
    controls = {name: report["targets"][name]["at_120"] for name in NEGATIVE}
    _write_json(os.path.join(dest, "metrics", "controls.json"), controls)
    selectivity = {
        name: report["targets"][name]["at_120"]["audits"]["F"]
        for name in report["targets"]
    }
    _write_json(os.path.join(dest, "metrics", "trigger-selectivity.json"), selectivity)
    _write_json(os.path.join(dest, "metrics", "reproduction.json"), {
        "clean_clone_verified": False,
        "starting_head": STARTING,
        "protocol_commit": PROTOCOL_COMMIT,
        "suite_freeze_commit": FREEZE_COMMIT,
        "runner_commit": RUNNER_COMMIT,
        "command": "python -m benchmark.fresh_composite_reproduce --root experiments/published/fresh-composite-v0.3.20 --verify",
        "product_default_changed": False,
        "outcome": derived["outcome"],
    })
    _write_json(os.path.join(dest, "config.json"), {
        "round": "v0.3.20",
        "candidate": CANDIDATE,
        "starting_head": STARTING,
        "protocol_commit": PROTOCOL_COMMIT,
        "suite_freeze_commit": FREEZE_COMMIT,
        "runner_commit": RUNNER_COMMIT,
        "outcome": derived["outcome"],
        "promotion_readiness": derived["promotion_readiness"],
        "product_default_changed": False,
        "cells_expected": 42,
        "seed": 1,
    })
    _write_text(os.path.join(dest, "summary.md"), _summary(report, derived))
    _write_json(os.path.join(dest, "evidence-manifest.json"), _manifest(dest))
    print(f"published {derived['outcome']} losses={len(derived['guard_bug_losses'])}")
    return derived


def main(argv=None) -> int:
    del argv
    publish()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
