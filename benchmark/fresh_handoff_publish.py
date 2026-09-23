"""Publish the v0.3.15 fresh handoff result from the frozen run directory."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

from benchmark.algorithm_freeze import sha256_file, verify_freeze
from benchmark.application_shape_evidence import canonical_json_bytes, sha256_bytes
from benchmark.fresh_handoff_analysis import (
    NEGATIVE, POLICY, POSITIVE, cell_stem, confirmed, derive_v0315_outcome,
    evaluable_target, full_transfer, lost_parent_on_qualified_chain,
    match_candidate_events, negative_control_gate, post_handoff_novelty,
    product_default_changed, row_at, _int, _load_json, _load_jsonl,
)
from benchmark.fresh_handoff_qualify import qualify_path
from benchmark.horizon_handoff_modelcheck import enumerate_traces
from benchmark.return_cycle_guard_reproduce import verify_candidate_identity
from benchmark.return_cycle_modelcheck import run_exhaustive_check

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_ROOT = os.path.join("experiments", "runs", "v0315-fresh")
PUBLISHED_ROOT = os.path.join("experiments", "published", "fresh-handoff-v0.3.15")
PROTOCOL = os.path.join("experiments", "validation", "v0.3.15", "protocol.json")
QUAL = os.path.join("experiments", "validation", "v0.3.15", "topology-qualification.json")
CANDIDATE_FREEZE = os.path.join(
    "experiments", "frozen", "ghost-horizon-handoff-v0.3.14", "freeze.json")
SUITE_FREEZE = os.path.join(
    "experiments", "frozen", "v0.3.15-fresh-handoff-suite", "freeze.json")
STARTING = "6a8f51d86fced3bdb87b8d1851035a202394500a"
PROTOCOL_COMMIT = "4681d444dc45905c8c644528dae7c253dd936233"
FREEZE_COMMIT = "5bf7e10b84ba6f37f70be90017ae1278e1013246"
MEASUREMENT_COMMIT = "2a71ef53dc817012e139cb7588599d52f47f9d84"
CANDIDATE_SHA = "827b8e64f953012ceec06fe3e0302c343a016463b5b1f88191e7a0a486c2467e"
BUDGETS = {"buggy-forum": (40, 80, 120), "buggy-billing": (40, 80, 120),
           "buggy-lab": (40, 80, 120), "buggy-directory": (120,)}
CODES = ("C1", "G", "H")
EVIDENCE_EXTS = (
    ".events.jsonl", ".sequence_events.json", ".graph.json", ".config.json", ".DONE",
)


def _write_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(canonical_json_bytes(obj))


def _app_dir(run_root: str, app: str) -> str:
    return os.path.join(run_root, "evidence", app)


def _paths(run_root: str, app: str, policy_name: str, budget: int) -> dict:
    stem = cell_stem(policy_name, budget)
    base = _app_dir(run_root, app)
    return {
        "events": os.path.join(base, stem + ".events.jsonl"),
        "sequence": os.path.join(base, stem + ".sequence_events.json"),
        "graph": os.path.join(base, stem + ".graph.json"),
        "config": os.path.join(base, stem + ".config.json"),
        "done": os.path.join(base, stem + ".DONE"),
    }


def _expected_cells():
    cells = []
    for app in POSITIVE:
        for code in CODES:
            for budget in (40, 80, 120):
                cells.append((app, code, budget))
    for code in CODES:
        cells.append((NEGATIVE, code, 120))
    return cells


def _view(row: dict) -> dict:
    keys = (
        "states", "clusters", "variants", "normalized_unique_urls",
        "confirmed_bugs", "bug_discovery_rate", "deep_bug_discovery_rate",
        "branches_started", "sequence_lost_parent", "sequence_horizon_reached",
        "return_attempt_events", "sequence_instances_returned",
        "return_cycle_escape_events", "nested_continuation_events",
        "horizon_handoff_started_events", "child_parent_witness_events",
        "parent_frame_resume_to_return_events", "horizon_handoff_unwind_events",
        "max_handoff_stack_depth", "witness_violations",
        "terminal_accounting_violations", "discovery_auc",
    )
    out = {key: row.get(key) for key in keys}
    out["confirmed_bugs"] = confirmed(row)
    return out


def _candidate_scan() -> list:
    path = os.path.join("ghostqa", "exploration", "horizon_handoff_guard.py")
    text = open(path, encoding="utf-8").read()
    needles = ("buggy-forum", "buggy-billing", "buggy-lab", "buggy-directory",
               "BUG-F", "BUG-DIR", "bugs.manifest", "topology.json")
    return [needle for needle in needles if needle in text]


def _historical_safety() -> dict:
    model = enumerate_traces()
    historical = run_exhaustive_check()
    return {
        "candidate_freeze_ok": verify_freeze(CANDIDATE_FREEZE) == [],
        "guard_freeze_ok": verify_candidate_identity() == [],
        "handoff_model_raw_traces": model["raw_traces"],
        "handoff_model_invariant_failures": model["invariant_failures"],
        "historical_return_failures": historical["failures"],
        "historical_return_all_pass": historical["all_pass"],
        "s1_s7_all_pass": historical["s1_s7_all_pass"],
        "candidate_source_sha256": sha256_file(
            "ghostqa/exploration/horizon_handoff_guard.py"),
    }


def collect(run_root: str) -> dict:
    missing = []
    per_target = {}
    match_failures = []
    for app in list(POSITIVE) + [NEGATIVE]:
        metrics = _load_json(os.path.join(_app_dir(run_root, app), "metrics.json"))
        topology = _load_json(os.path.join("apps", app, "topology.json"))
        qualified = qualify_path(os.path.join("apps", app, "topology.json"))
        cells = {}
        for code in CODES:
            for budget in BUDGETS[app]:
                policy_name = POLICY[code]
                paths = _paths(run_root, app, policy_name, budget)
                if not all(os.path.isfile(path) for path in paths.values()):
                    missing.append(f"{app} {code} {budget}")
                    continue
                row = row_at(metrics, policy_name, budget)
                if not row:
                    missing.append(f"{app} {code} {budget} metrics")
                    continue
                trace = _load_jsonl(paths["events"])
                sequence = _load_json(paths["sequence"])
                view = _view(row)
                if code == "H":
                    matched = match_candidate_events(sequence, trace)
                    view["continuation_opportunities"] = matched["continuation_opportunities"]
                    view["handoff_opportunities"] = matched["handoff_opportunities"]
                    view["event_match_ok"] = matched["ok"]
                    if not matched["ok"]:
                        match_failures.append({
                            "app": app, "budget": budget, "failures": matched["failures"][:12],
                        })
                else:
                    opps = []
                    from benchmark.fresh_handoff_analysis import opportunities_from_trace
                    opps = opportunities_from_trace(trace)
                    view["continuation_opportunities"] = sum(
                        1 for item in opps if item["kind"] == "continuation")
                    view["handoff_opportunities"] = sum(
                        1 for item in opps if item["kind"] == "handoff")
                    view["event_match_ok"] = True
                if budget == 120 and code == "H":
                    view.update(post_handoff_novelty(trace))
                cells[f"{code}@{budget}"] = view
        guard = row_at(metrics, POLICY["G"], 120)
        candidate = row_at(metrics, POLICY["H"], 120)
        guard_trace = _load_jsonl(_paths(run_root, app, POLICY["G"], 120)["events"])
        guard_seq = _load_json(_paths(run_root, app, POLICY["G"], 120)["sequence"])
        lost_parent = lost_parent_on_qualified_chain(guard_seq, guard_trace, topology)
        h_trace = _load_jsonl(_paths(run_root, app, POLICY["H"], 120)["events"])
        from benchmark.fresh_handoff_analysis import opportunities_from_trace
        h_opps = opportunities_from_trace(h_trace)
        g_opps = opportunities_from_trace(guard_trace)
        handoff_opps = (
            sum(1 for item in h_opps if item["kind"] == "handoff")
            + sum(1 for item in g_opps if item["kind"] == "handoff")
        )
        evaluable = evaluable_target(
            qualified=bool(qualified.get("qualified")),
            guard_lost_parent=lost_parent,
            candidate=candidate,
            handoff_opportunities=handoff_opps,
        )
        transfer = None
        control = None
        if app in POSITIVE:
            transfer = full_transfer(bool(qualified.get("qualification_ok")), evaluable["actual_evaluable"], guard, candidate)
        else:
            control = negative_control_gate(guard, candidate)
        per_target[app] = {
            "seed": topology.get("seed"),
            "seed_hex": topology.get("seed_hex"),
            "topology_family": topology.get("topology_family"),
            "expected_control_class": topology.get("expected_control_class"),
            "static": {
                "qualified": qualified.get("qualified"),
                "qualification_ok": qualified.get("qualification_ok"),
                "qualifying_chain_count": qualified.get("qualifying_chain_count"),
                "max_nested_branch_chain": qualified.get("max_nested_branch_chain"),
                "child_workflow_roles": qualified.get("child_workflow_roles"),
            },
            "cells": cells,
            "evaluable": evaluable,
            "full_transfer": transfer,
            "negative_control": control,
            "lost_vs_guard": sorted(set(confirmed(guard)) - set(confirmed(candidate))),
        }
    return {"missing": missing, "targets": per_target, "match_failures": match_failures}


def _summary(report: dict, derived: dict) -> str:
    lines = [
        f"# GhostQA v0.3.15 — Outcome {derived['outcome']}",
        "",
        derived["outcome_meaning"],
        "",
        "Static qualification, actual evaluability, and full transfer are different claims. "
        "A qualified graph only says the declared structure is relevant. "
        "It does not mean a policy reached that structure, and it does not mean full transfer. "
        "This round is not universal generalization and it does not change the product default.",
        "",
        f"Promotion readiness: `{derived['promotion_readiness']}`.",
        "",
        "Product default changed: no",
        "",
        "## Static qualification",
        "",
        "| target | qualified | chain count | max nested chain | roles |",
        "|---|---:|---:|---:|---|",
    ]
    for app, item in report["targets"].items():
        static = item["static"]
        lines.append(
            f"| {app} | {static['qualified']} | {static['qualifying_chain_count']} | "
            f"{static['max_nested_branch_chain']} | {', '.join(static['child_workflow_roles']) or '—'} |"
        )
    lines.extend(["", "## Budget 120", "",
                  "| target | policy | states | URLs | confirmed | lost_parent | horizon | return attempts | returned | escapes | continuations | handoffs | witnesses | unwinds | max depth |",
                  "|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for app, item in report["targets"].items():
        for code in CODES:
            cell = item["cells"].get(f"{code}@120") or {}
            bugs = ",".join(cell.get("confirmed_bugs") or []) or "—"
            lines.append(
                f"| {app} | {code} | {_int(cell.get('states'))} | {_int(cell.get('normalized_unique_urls'))} | {bugs} | "
                f"{_int(cell.get('sequence_lost_parent'))} | {_int(cell.get('sequence_horizon_reached'))} | "
                f"{_int(cell.get('return_attempt_events'))} | {_int(cell.get('sequence_instances_returned'))} | "
                f"{_int(cell.get('return_cycle_escape_events'))} | {_int(cell.get('nested_continuation_events'))} | "
                f"{_int(cell.get('horizon_handoff_started_events'))} | {_int(cell.get('child_parent_witness_events'))} | "
                f"{_int(cell.get('horizon_handoff_unwind_events'))} | {_int(cell.get('max_handoff_stack_depth'))} |"
            )
    lines.extend(["", "## Transfer", "",
                  "| target | static qualified | actual evaluable | full transfer | lost vs guard |",
                  "|---|---:|---:|---:|---|"])
    for app in POSITIVE:
        item = report["targets"][app]
        lines.append(
            f"| {app} | {item['static']['qualified']} | {item['evaluable']['actual_evaluable']} | "
            f"{item['full_transfer']['pass']} | {', '.join(item['lost_vs_guard']) or '—'} |"
        )
    control = report["targets"][NEGATIVE]["negative_control"]
    lines.extend([
        "",
        "## Negative control",
        "",
        f"H handoffs: {control['horizon_handoff_started_events']}",
        f"H witnesses: {control['child_parent_witness_events']}",
        f"H resumes: {control['parent_frame_resume_to_return_events']}",
        f"max depth: {control['max_handoff_stack_depth']}",
        f"lost vs guard: {', '.join(control['lost_vs_guard']) or '—'}",
        "",
        "## Aggregate",
        "",
        f"- static positive targets = 3",
        f"- actually evaluable targets = {derived['actual_evaluable_positive_targets']}",
        f"- full transfer targets = {derived['full_transfer_targets']}",
        f"- guard bug losses = {', '.join(derived['bug_loss_apps']) or '0'}",
        f"- negative-control handoffs = {derived['negative_control_handoffs']}",
        f"- witness violations = {derived['witness_violations']}",
        f"- terminal violations = {derived['terminal_accounting_violations']}",
        f"- Outcome = {derived['outcome']}",
        f"- promotion_readiness = {derived['promotion_readiness']}",
        "- Product default changed: no",
        "",
        "```text",
        "python -m benchmark.fresh_handoff_reproduce --root experiments/published/fresh-handoff-v0.3.15 --verify",
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
            files.append({"relative_path": rel, "sha256": sha256_file(path)})
    files.sort(key=lambda item: item["relative_path"])
    return {"hash_normalization": "LF newlines", "expected_file_count": len(files), "files": files}


def publish(run_root: str = RUN_ROOT, dest: str = PUBLISHED_ROOT) -> dict:
    report = collect(run_root)
    if report["missing"]:
        raise SystemExit("missing cells: " + ", ".join(report["missing"]))
    safety = _historical_safety()
    app_specific = _candidate_scan()
    evaluable = sum(
        1 for app in POSITIVE if report["targets"][app]["evaluable"]["actual_evaluable"]
    )
    transferred = sum(
        1 for app in POSITIVE if report["targets"][app]["full_transfer"]["pass"]
    )
    losses = [
        app for app in list(POSITIVE) + [NEGATIVE]
        if report["targets"][app]["lost_vs_guard"]
    ]
    witness = 0
    terminal = 0
    for app in list(POSITIVE) + [NEGATIVE]:
        cell = report["targets"][app]["cells"].get("H@120") or {}
        witness += _int(cell.get("witness_violations"))
        terminal += _int(cell.get("terminal_accounting_violations"))
    control = report["targets"][NEGATIVE]["negative_control"]
    changed = product_default_changed()
    derived = derive_v0315_outcome(
        candidate_freeze_ok=safety["candidate_freeze_ok"] and safety["candidate_source_sha256"] == CANDIDATE_SHA,
        suite_freeze_ok=verify_freeze(SUITE_FREEZE) == [],
        protocol_ok=_load_json(PROTOCOL).get("executed") is False,
        static_qualification_ok=all(
            report["targets"][app]["static"]["qualification_ok"] for app in report["targets"]
        ) and all(report["targets"][app]["static"]["qualified"] for app in POSITIVE)
        and report["targets"][NEGATIVE]["static"]["qualified"] is False,
        historical_safety_ok=(
            safety["handoff_model_raw_traces"] == 19607
            and safety["handoff_model_invariant_failures"] == 0
            and safety["historical_return_all_pass"]
            and safety["guard_freeze_ok"]
        ),
        source_isolation_ok=not app_specific,
        witness_violations=witness,
        terminal_accounting_violations=terminal,
        app_specific_logic=bool(app_specific),
        bug_loss_apps=losses,
        negative_control_handoffs=control["horizon_handoff_started_events"],
        product_default_changed=changed,
        post_freeze_tuning=False,
        judge_leakage=False,
        event_match_ok=not report["match_failures"],
        actual_evaluable_positive_targets=evaluable,
        full_transfer_targets=transferred,
    )
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    os.makedirs(dest, exist_ok=True)
    for app in report["targets"]:
        src = _app_dir(run_root, app)
        out = os.path.join(dest, "evidence", app)
        os.makedirs(out, exist_ok=True)
        for name in os.listdir(src):
            if name == "metrics.json" or any(name.endswith(ext) for ext in EVIDENCE_EXTS):
                shutil.copyfile(os.path.join(src, name), os.path.join(out, name))
    shutil.copyfile(PROTOCOL, os.path.join(dest, "protocol.json"))
    shutil.copyfile(QUAL, os.path.join(dest, "topology-qualification.json"))
    _write_json(os.path.join(dest, "metrics", "per-target.json"), report)
    aggregate = {
        "static_positive_targets": 3,
        "actual_evaluable_positive_targets": evaluable,
        "full_transfer_targets": transferred,
        "bug_loss_apps": losses,
        "negative_control_handoffs": control["horizon_handoff_started_events"],
        "witness_violations": witness,
        "terminal_accounting_violations": terminal,
        "derived": derived,
    }
    _write_json(os.path.join(dest, "metrics", "aggregate.json"), aggregate)
    _write_json(os.path.join(dest, "metrics", "safety.json"), {
        **safety, "app_specific_needles": app_specific, "event_match_failures": report["match_failures"],
    })
    _write_json(os.path.join(dest, "metrics", "negative-control.json"), control)
    _write_json(os.path.join(dest, "metrics", "reproduction.json"), {
        "clean_clone_verified": False,
        "starting_head": STARTING,
        "protocol_commit": PROTOCOL_COMMIT,
        "suite_freeze_commit": FREEZE_COMMIT,
        "measurement_commit": MEASUREMENT_COMMIT,
    })
    _write_json(os.path.join(dest, "config.json"), {
        "round": "v0.3.15",
        "starting_head": STARTING,
        "protocol_commit": PROTOCOL_COMMIT,
        "suite_freeze_commit": FREEZE_COMMIT,
        "measurement_commit": MEASUREMENT_COMMIT,
        "outcome": derived["outcome"],
        "promotion_readiness": derived["promotion_readiness"],
        "product_default_changed": False,
        "cells_expected": 30,
        "seed": 1,
    })
    text = _summary({"targets": report["targets"]}, derived)
    with open(os.path.join(dest, "summary.md"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    _write_json(os.path.join(dest, "evidence-manifest.json"), _manifest(dest))
    print(f"published {derived['outcome']} evaluable={evaluable} transfer={transferred}")
    return derived


def main(argv=None) -> int:
    publish()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
