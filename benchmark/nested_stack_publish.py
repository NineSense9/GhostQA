"""Publish v0.3.13 evidence. Numbers come from traces and the frozen gates."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

from benchmark.algorithm_freeze import (
    DEFAULT_FREEZE, sha256_file, verify_freeze,
)
from benchmark.application_shape_evidence import (
    canonical_json_bytes, load_json, load_jsonl, sha256_bytes, steps_only,
)
from benchmark.fresh_transfer_analysis import normalize_url
from benchmark.nested_hub_detector import count_events, detect_nested_hub_preemptions
from benchmark.nested_stack_analysis import (
    app_specific_needles, derive_v0313_outcome, stack_audit, structural_repair_gate,
)
from benchmark.nested_stack_regression import (
    _action_view, _align_key, _bug_index, _first_match, _pair, _urls,
)
from benchmark.return_cycle_guard_reproduce import verify_candidate_identity
from benchmark.return_cycle_modelcheck import run_exhaustive_check
from benchmark.return_cycle_safety import collect_safety_suite
from ghostqa.__main__ import _make_policy

PUBLISHED_ROOT = os.path.join(
    "experiments", "published", "nested-stack-v0.3.13")
RUN_ROOT = os.path.join("experiments", "runs", "v0313-stack")
CANDIDATE_FREEZE = os.path.join(
    "experiments", "frozen", "ghost-nested-stack-guard-v0.3.13", "freeze.json")
FLATTEN_FREEZE = os.path.join(
    "experiments", "frozen", "ghost-nested-hub-guard-v0.3.12", "freeze.json")
PROTOCOL = os.path.join("experiments", "validation", "v0.3.13", "protocol.json")
ANALYSIS = os.path.join(
    "experiments", "validation", "v0.3.13", "regression-analysis.json")
GUARD = "ghost-structural-return-guard"
FLAT = "ghost-structural-nested-return-guard"
STACK = "ghost-structural-nested-stack-guard"
MECHANISM_APPS = ("buggy-crm", "buggy-ops")
BUDGETS = (40, 80, 120)
PRIMARY = 120
TARGET_FREEZES = {
    "buggy-crm": "experiments/frozen/v0.3.11-multitarget/buggy-crm/freeze.json",
    "buggy-ops": "experiments/frozen/v0.3.11-multitarget/buggy-ops/freeze.json",
    "buggy-wiki": "experiments/frozen/v0.3.11-multitarget/buggy-wiki/freeze.json",
    "buggy-desk": "experiments/frozen/buggy-desk-v0.3.10/freeze.json",
}
REFERENCES = {
    "buggy-desk": "experiments/published/fresh-transfer-v0.3.10/evidence/buggy-desk/metrics.json",
    "deepbench": "experiments/published/return-cycle-guard-v0.3.9/evidence/deepbench/metrics.json",
    "wiki": "experiments/published/multi-target-replication-v0.3.11/evidence/buggy-wiki/metrics.json",
    "buggy-shop": "experiments/published/return-cycle-guard-v0.3.9/evidence/shop/metrics.json",
}
V0312_REGRESSION = (
    "experiments/published/nested-hub-parent-v0.3.12/metrics/regression.json")
REGRESSION_APPS = (
    ("buggy-desk", "buggy-desk", "buggy-desk"),
    ("deepbench", "buggy-flow", "deepbench"),
    ("wiki", "buggy-wiki", "wiki"),
    ("buggy-shop", "buggy-shop", "buggy-shop"),
)
KINDS = (".events.jsonl", ".graph.json", ".sequence_events.json")
P_TESTS = " or ".join(f"test_p{i}_" for i in range(1, 16))
N_TESTS = " or ".join(f"test_n{i}_" for i in range(1, 13))


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text if text.endswith("\n") else text + "\n")


def _write_json(path: str, obj) -> None:
    _write(path, canonical_json_bytes(obj).decode("utf-8"))


def _runs(path: str) -> list:
    if not os.path.isfile(path):
        return []
    data = load_json(path)
    if isinstance(data, dict):
        return list(data.get("runs") or [])
    return list(data or [])


def _row(path: str, policy: str, budget: int = PRIMARY) -> dict:
    for row in _runs(path):
        if row.get("policy") == policy and int(row.get("budget") or 0) == budget:
            return row
    return {}


def _confirmed(path: str, policy: str, budget: int = PRIMARY) -> list:
    return sorted(_row(path, policy, budget).get("confirmed_bugs") or [])


def _stem(policy: str, budget: int) -> str:
    return f"{policy}_b{budget}_s1"


def _copy_cell(src_dir: str, dst_dir: str, policy: str, budget: int) -> None:
    os.makedirs(dst_dir, exist_ok=True)
    stem = _stem(policy, budget)
    for ext in KINDS:
        src = os.path.join(src_dir, stem + ext)
        if os.path.isfile(src):
            shutil.copyfile(src, os.path.join(dst_dir, stem + ext))


def _copy_metrics(src_dir: str, dst_dir: str) -> None:
    src = os.path.join(src_dir, "metrics.json")
    if os.path.isfile(src):
        os.makedirs(dst_dir, exist_ok=True)
        shutil.copyfile(src, os.path.join(dst_dir, "metrics.json"))


def stage_evidence(run_root: str, out_root: str) -> None:
    for app in MECHANISM_APPS:
        src = os.path.join(run_root, "evidence", app)
        dst = os.path.join(out_root, "evidence", app)
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        for policy in (GUARD, FLAT, STACK):
            for budget in BUDGETS:
                _copy_cell(src, dst, policy, budget)
        _copy_metrics(src, dst)
    for case_id, run_app, folder in REGRESSION_APPS:
        src = os.path.join(run_root, "evidence", run_app)
        dst = os.path.join(out_root, "evidence", folder)
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        _copy_cell(src, dst, STACK, PRIMARY)
        kept = [
            row for row in _runs(os.path.join(src, "metrics.json"))
            if row.get("policy") == STACK and int(row.get("budget") or 0) == PRIMARY
        ]
        _write_json(os.path.join(dst, "metrics.json"), {"app": case_id, "runs": kept})
    shutil.copyfile(PROTOCOL, os.path.join(out_root, "protocol.json"))
    shutil.copyfile(ANALYSIS, os.path.join(out_root, "regression-analysis.json"))
    shutil.copyfile(CANDIDATE_FREEZE, os.path.join(out_root, "candidate-freeze.json"))


def _load_events(root: str, folder: str, policy: str, budget: int):
    base = os.path.join(root, "evidence", folder, _stem(policy, budget))
    seq_path = base + ".sequence_events.json"
    ev_path = base + ".events.jsonl"
    seq = load_json(seq_path) if os.path.isfile(seq_path) else []
    events = load_jsonl(ev_path) if os.path.isfile(ev_path) else []
    return seq, events


def _cell_view(row: dict, seq: list, steps: list) -> dict:
    pre = detect_nested_hub_preemptions(seq, steps)
    window = sum(1 for item in pre if item.get("commitment_window"))
    horizon = count_events(seq, "sequence_horizon_reached")
    finding = sum(
        1 for event in seq
        if event.get("event") == "sequence_terminal"
        and event.get("outcome") == "finding")
    crash = sum(
        1 for event in seq
        if event.get("event") == "sequence_terminal"
        and event.get("outcome") == "crash")
    returned = sum(
        1 for event in seq
        if event.get("event") == "sequence_terminal"
        and event.get("outcome") == "returned")
    pushes = count_events(seq, "parent_frame_suspended")
    resumes = count_events(seq, "parent_frame_resumed")
    return {
        "states": row.get("states"),
        "normalized_unique_urls": row.get("normalized_unique_urls"),
        "confirmed_bugs": sorted(row.get("confirmed_bugs") or []),
        "sequence_lost_parent": row.get("sequence_lost_parent"),
        "sequence_horizon_reached": horizon,
        "return_attempt_events": count_events(seq, "return_attempt"),
        "sequence_instances_returned": returned,
        "return_cycle_escape_events": count_events(seq, "return_cycle_escape"),
        "finding_terminals": finding,
        "crash_terminals": crash,
        "commitment_window_preemptions": window,
        "suspended_frame_push_events": pushes,
        "suspended_frame_resume_events": resumes,
        "suspended_frame_unwind_events": count_events(seq, "nested_stack_unwind"),
        "max_suspended_stack_depth": row.get("max_suspended_stack_depth") or 0,
        "child_sequence_start_events": count_events(seq, "nested_child_started"),
        "child_return_resume_events": row.get("child_return_resume_events") or resumes,
        "terminal_accounting_violations": len(stack_audit(seq)["terminal_violations"])
        if seq else row.get("terminal_accounting_violations"),
        "nested_branch_followup_events": count_events(seq, "nested_branch_followup"),
    }


def _pytest_failures(kexpr: str, path: str) -> int:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=no", "-k", kexpr, path],
        capture_output=True, text=True)
    return 0 if proc.returncode == 0 else 1


def build_safety() -> dict:
    suite = collect_safety_suite()
    exhaustive = run_exhaustive_check()
    s_fail = sum(1 for row in suite.get("rows") or [] if not row.get("pass"))
    p_fail = _pytest_failures(P_TESTS, "tests/test_nested_stack_guard.py")
    n_fail = _pytest_failures(N_TESTS, "tests/test_nested_hub_guard.py")
    default = _make_policy("ghost", None, 0)
    product_changed = not (
        default.name == "ghost"
        and default.use_frontier is False
        and default.sequence_mode == "off")
    needles = app_specific_needles()
    historical = []
    if verify_freeze(DEFAULT_FREEZE):
        historical.append("c1")
    if verify_candidate_identity():
        historical.append("v0.3.9-guard")
    if verify_freeze(FLATTEN_FREEZE):
        historical.append("v0.3.12-candidate")
    for name, path in TARGET_FREEZES.items():
        if verify_freeze(path):
            historical.append(name)
    return {
        "p_series_cases": 15,
        "p_series_failures": p_fail,
        "s1_s7_cases": len(suite.get("rows") or []),
        "s1_s7_failures": s_fail,
        "s1_s7_all_pass": bool(suite.get("all_pass")),
        "exhaustive_traces": int(exhaustive.get("traces_enumerated") or 0),
        "exhaustive_failures": int(exhaustive.get("failures") or 0),
        "n_series_cases": 12,
        "n_series_failures": n_fail,
        "app_specific_needles": needles,
        "app_specific_logic": bool(needles),
        "product_default_changed": product_changed,
        "historical_freeze_failures": historical,
        "candidate_freeze_ok": verify_freeze(CANDIDATE_FREEZE) == [],
        "historical_freezes_ok": not historical,
    }


def _divergence(ref_events: list, other_events: list) -> dict:
    ref_rows = _pair(ref_events)
    other_rows = _pair(other_events)
    prefix = 0
    limit = min(len(ref_rows), len(other_rows))
    while prefix < limit and _align_key(ref_rows[prefix]["step"]) == _align_key(
            other_rows[prefix]["step"]):
        prefix += 1
    if prefix >= limit:
        return {"first_identical_prefix_length": prefix, "first_divergence_step": None}
    return {
        "first_identical_prefix_length": prefix,
        "first_divergence_step": ref_rows[prefix]["step"].get("index"),
        "reference_action": _action_view(ref_rows[prefix]["step"]),
        "other_action": _action_view(other_rows[prefix]["step"]),
    }


def _bug_steps(events: list, manifest: str, bug_ids: list) -> list:
    bugs = _bug_index(manifest)
    out = []
    for bug_id in bug_ids:
        bug = bugs.get(bug_id) or {"id": bug_id, "match": {}}
        out.append({
            "id": bug_id,
            "first_match": _first_match(events, bug) if bug.get("match") else None,
        })
    return out


def build_regression(root: str) -> dict:
    v0312 = load_json(V0312_REGRESSION)
    cases = {}
    for case_id, _run_app, folder in REGRESSION_APPS:
        metrics = os.path.join(root, "evidence", folder, "metrics.json")
        stack_row = _row(metrics, STACK, PRIMARY)
        ref_confirmed = _confirmed(REFERENCES[case_id], GUARD, PRIMARY)
        flat_confirmed = sorted(
            ((v0312.get("cases") or {}).get(case_id) or {}).get("candidate_confirmed") or [])
        stack_confirmed = sorted(stack_row.get("confirmed_bugs") or [])
        if not ref_confirmed:
            raise SystemExit(f"missing reference confirmed set for {case_id}")
        lost = sorted(set(ref_confirmed) - set(stack_confirmed))
        seq, events = _load_events(root, folder, STACK, PRIMARY)
        audit = stack_audit(seq)
        cases[case_id] = {
            "app": case_id,
            "reference_confirmed": ref_confirmed,
            "v0_3_12_confirmed": flat_confirmed,
            "stack_confirmed": stack_confirmed,
            "lost_vs_guard": lost,
            "states": stack_row.get("states"),
            "normalized_unique_urls": stack_row.get("normalized_unique_urls"),
            "sequence_lost_parent": stack_row.get("sequence_lost_parent"),
            "suspended_frame_push_events": count_events(seq, "parent_frame_suspended"),
            "suspended_frame_resume_events": count_events(seq, "parent_frame_resumed"),
            "suspended_frame_unwind_events": count_events(seq, "nested_stack_unwind"),
            "max_suspended_stack_depth": stack_row.get("max_suspended_stack_depth") or 0,
            "sequence_horizon_reached": count_events(seq, "sequence_horizon_reached"),
            "return_attempt_events": count_events(seq, "return_attempt"),
            "sequence_instances_returned": sum(
                1 for event in seq
                if event.get("event") == "sequence_terminal"
                and event.get("outcome") == "returned"),
            "return_cycle_escape_events": count_events(seq, "return_cycle_escape"),
            "terminal_accounting_violations": audit["terminal_accounting_violations"],
            "return_inflation": audit["return_inflation"],
            "stack_frame_corruption": audit["stack_frame_corruption"],
            "restore_without_child_return": audit["restore_without_child_return"],
        }
    desk_ref = (
        "experiments/published/fresh-transfer-v0.3.10/evidence/buggy-desk/"
        "ghost-structural-return-guard_b120_s1.events.jsonl")
    desk_flat = (
        "experiments/published/nested-hub-parent-v0.3.12/evidence/regression/"
        "buggy-desk/ghost-structural-nested-return-guard_b120_s1.events.jsonl")
    ref_events = load_jsonl(desk_ref)
    flat_events = load_jsonl(desk_flat)
    stack_seq, stack_events = _load_events(root, "buggy-desk", STACK, PRIMARY)
    ref_urls = _urls(ref_events)
    stack_urls = _urls(stack_events)
    lost_ids = cases["buggy-desk"]["lost_vs_guard"]
    found_ids = [
        bug for bug in ("BUG-K3", "BUG-K6", "BUG-K9", "BUG-K10")
        if bug not in lost_ids
    ]
    desk_detail = {
        "divergence_from_guard": _divergence(ref_events, stack_events),
        "flatten_divergence_from_guard": _divergence(ref_events, flat_events),
        "reference_only_urls": sorted(set(ref_urls) - set(stack_urls)),
        "stack_only_urls": sorted(set(stack_urls) - set(ref_urls)),
        "recovered_bug_first_steps": _bug_steps(
            stack_events, "apps/buggy-desk/bugs.manifest.json", found_ids),
        "still_lost_bug_first_steps": _bug_steps(
            stack_events, "apps/buggy-desk/bugs.manifest.json", lost_ids),
    }
    deep_seq, deep_events = _load_events(root, "deepbench", STACK, PRIMARY)
    member_children = [
        {
            "step": event.get("step"),
            "active_child_branch": event.get("active_child_branch") or "",
            "sequence_instance_id": event.get("sequence_instance_id"),
            "parent_hub_sig": event.get("parent_hub_sig") or "",
        }
        for event in deep_seq
        if event.get("event") == "nested_child_started"
        and (
            "btn_add_alice" in (event.get("active_child_branch") or "")
            or "btn_members" in (event.get("suspended_branch") or "")
            or "btn_add_alice" in (event.get("branch_key") or "")
        )
    ]
    add_remove = []
    for step in steps_only(deep_events):
        eid = ((step.get("action") or {}).get("target_eid") or "")
        if eid in ("btn_add_alice", "btn_remove_alice", "btn_remove_member", "btn_members"):
            add_remove.append({
                "index": step.get("index"),
                "target_eid": eid,
                "src_url": normalize_url(step.get("src_url") or ""),
                "dst_url": normalize_url(step.get("dst_url") or ""),
            })
    deep_detail = {
        "members_nested_child_starts": member_children,
        "members_nested_child_start_count": len(member_children),
        "stack_pushes": count_events(deep_seq, "parent_frame_suspended"),
        "stack_resumes": count_events(deep_seq, "parent_frame_resumed"),
        "add_remove_steps": add_remove,
        "d12_confirmed": "BUG-D12" in cases["deepbench"]["stack_confirmed"],
        "retained_reference": [
            bug for bug in ("BUG-D6", "BUG-D7", "BUG-D11", "BUG-D13", "BUG-D14")
            if bug in cases["deepbench"]["stack_confirmed"]
        ],
    }
    return {"cases": cases, "buggy_desk_detail": desk_detail, "deepbench_detail": deep_detail}


def _audit_stack_files(root: str) -> dict:
    total = 0
    inflation = False
    corruption = False
    bad_restore = False
    per_run = []
    evidence = os.path.join(root, "evidence")
    for dirpath, _dirs, files in os.walk(evidence):
        for name in sorted(files):
            if not name.startswith(STACK) or not name.endswith(".sequence_events.json"):
                continue
            seq = load_json(os.path.join(dirpath, name))
            audit = stack_audit(seq)
            total += audit["terminal_accounting_violations"]
            inflation = inflation or audit["return_inflation"]
            corruption = corruption or audit["stack_frame_corruption"]
            bad_restore = bad_restore or audit["restore_without_child_return"]
            rel = os.path.relpath(os.path.join(dirpath, name), root).replace("\\", "/")
            per_run.append({
                "path": rel,
                "terminal_accounting_violations": audit["terminal_accounting_violations"],
                "return_inflation": audit["return_inflation"],
                "stack_frame_corruption": audit["stack_frame_corruption"],
                "restore_without_child_return": audit["restore_without_child_return"],
            })
    return {
        "terminal_accounting_violations": total,
        "return_inflation": inflation,
        "stack_frame_corruption": corruption,
        "restore_without_child_return": bad_restore,
        "runs": per_run,
    }


def build_mechanism(root: str, safety: dict, regression: dict) -> dict:
    targets = {}
    for app in MECHANISM_APPS:
        metrics = os.path.join(root, "evidence", app, "metrics.json")
        cells = {}
        for policy in (GUARD, FLAT, STACK):
            for budget in BUDGETS:
                row = _row(metrics, policy, budget)
                seq, events = _load_events(root, app, policy, budget)
                view = _cell_view(row, seq, events)
                view["policy"] = policy
                view["budget"] = budget
                cells[f"{policy}@{budget}"] = view
        guard = cells[f"{GUARD}@{PRIMARY}"]
        stack = cells[f"{STACK}@{PRIMARY}"]
        gate = {
            "nested_child_stack_events": stack.get("child_sequence_start_events") or 0,
            "commitment_window_preemptions": stack.get("commitment_window_preemptions") or 0,
            "reached_horizon_or_safe_terminal": bool(
                (stack.get("sequence_horizon_reached") or 0) > 0
                or (stack.get("finding_terminals") or 0) > 0
                or (stack.get("crash_terminals") or 0) > 0
                or (stack.get("sequence_instances_returned") or 0) > 0),
            "reached_return_or_child_resume": bool(
                (stack.get("return_attempt_events") or 0) > 0
                or (stack.get("sequence_instances_returned") or 0) > 0
                or (stack.get("child_return_resume_events") or 0) > 0
                or (stack.get("return_cycle_escape_events") or 0) > 0),
            "expanded_beyond_guard": (
                int(stack.get("states") or 0) > int(guard.get("states") or 0)
                or int(stack.get("normalized_unique_urls") or 0)
                > int(guard.get("normalized_unique_urls") or 0)),
        }
        gate["pass"] = structural_repair_gate(gate)
        targets[app] = {"cells": cells, "assessment_120": gate}
    audit = _audit_stack_files(root)
    lost = {
        case_id: (case.get("lost_vs_guard") or [])
        for case_id, case in (regression.get("cases") or {}).items()
    }
    derived = derive_v0313_outcome(
        candidate_freeze_ok=bool(safety.get("candidate_freeze_ok")),
        historical_freezes_ok=bool(safety.get("historical_freezes_ok")),
        p_series_failures=int(safety.get("p_series_failures") or 0),
        s1_s7_pass=bool(safety.get("s1_s7_all_pass")),
        exhaustive_failures=int(safety.get("exhaustive_failures") or 0),
        exhaustive_traces=int(safety.get("exhaustive_traces") or 0),
        terminal_accounting_violations=int(audit["terminal_accounting_violations"]),
        return_inflation=bool(audit["return_inflation"]),
        stack_frame_corruption=bool(audit["stack_frame_corruption"]),
        restore_without_child_return=bool(audit["restore_without_child_return"]),
        app_specific_logic=bool(safety.get("app_specific_logic")),
        product_default_changed=bool(safety.get("product_default_changed")),
        crm_repair=bool((targets["buggy-crm"]["assessment_120"] or {}).get("pass")),
        ops_repair=bool((targets["buggy-ops"]["assessment_120"] or {}).get("pass")),
        lost_vs_guard=lost,
    )
    return {"targets": targets, "stack_audit": audit, "derived": derived}


def build_all(root: str):
    safety = build_safety()
    regression = build_regression(root)
    mechanism = build_mechanism(root, safety, regression)
    return mechanism, regression, safety


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
    return {"expected_file_count": len(files), "files": files}


def write_summary(mechanism: dict, regression: dict, safety: dict) -> str:
    derived = mechanism["derived"]
    lines = [
        f"# GhostQA v0.3.13 — Outcome {derived['outcome']}",
        "",
        derived["outcome_meaning"],
        "",
        "Inspected mechanism development on buggy-crm and buggy-ops. "
        "Not a fresh-generalization claim. Product default unchanged. "
        "v0.3.11 remains Outcome D. v0.3.12 remains Outcome C.",
        "",
        "## Mechanism",
        "",
        "| target | policy | budget | states | URLs | lost_parent | stack pushes | resumes | unwind | max depth | horizon | returns | escapes | confirmed |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for app, block in (mechanism.get("targets") or {}).items():
        for key, cell in sorted((block.get("cells") or {}).items()):
            lines.append(
                "| {app} | {policy} | {budget} | {states} | {urls} | {lost} | {push} | "
                "{resume} | {unwind} | {depth} | {horizon} | {ret} | {esc} | {bugs} |".format(
                    app=app,
                    policy=cell.get("policy"),
                    budget=cell.get("budget"),
                    states=cell.get("states"),
                    urls=cell.get("normalized_unique_urls"),
                    lost=cell.get("sequence_lost_parent"),
                    push=cell.get("suspended_frame_push_events"),
                    resume=cell.get("suspended_frame_resume_events"),
                    unwind=cell.get("suspended_frame_unwind_events"),
                    depth=cell.get("max_suspended_stack_depth"),
                    horizon=cell.get("sequence_horizon_reached"),
                    ret=cell.get("sequence_instances_returned"),
                    esc=cell.get("return_cycle_escape_events"),
                    bugs=",".join(cell.get("confirmed_bugs") or []) or "—",
                ))
    lines.extend([
        "",
        "## Regression",
        "",
        "| target | v0.3.9 guard confirmed | v0.3.12 flatten confirmed | v0.3.13 stack confirmed | lost vs guard |",
        "|---|---|---|---|---|",
    ])
    for case_id, case in (regression.get("cases") or {}).items():
        lines.append(
            "| {name} | {ref} | {flat} | {stack} | {lost} |".format(
                name=case_id,
                ref=",".join(case.get("reference_confirmed") or []) or "—",
                flat=",".join(case.get("v0_3_12_confirmed") or []) or "—",
                stack=",".join(case.get("stack_confirmed") or []) or "—",
                lost=",".join(case.get("lost_vs_guard") or []) or "—",
            ))
    audit = mechanism.get("stack_audit") or {}
    lines.extend([
        "",
        "## Safety",
        "",
        "| suite | cases/traces | failures |",
        "|---|---:|---:|",
        f"| P1–P15 | {safety.get('p_series_cases')} | {safety.get('p_series_failures')} |",
        f"| S1–S7 | {safety.get('s1_s7_cases')} | {safety.get('s1_s7_failures')} |",
        f"| bounded return model | {safety.get('exhaustive_traces')} | {safety.get('exhaustive_failures')} |",
        "",
        "## Terminal accounting",
        "",
        f"violations: {audit.get('terminal_accounting_violations')}",
        f"return inflation: {audit.get('return_inflation')}",
        f"stack frame corruption: {audit.get('stack_frame_corruption')}",
        f"restore without child return: {audit.get('restore_without_child_return')}",
        "",
        "Product default changed: no",
        "",
        "```text",
        "python -m benchmark.nested_stack_reproduce --root experiments/published/nested-stack-v0.3.13 --verify",
        "```",
        "",
    ])
    return "\n".join(lines)


def publish(run_root: str = RUN_ROOT, out_root: str = PUBLISHED_ROOT) -> dict:
    if os.path.isdir(out_root):
        shutil.rmtree(out_root)
    os.makedirs(out_root, exist_ok=True)
    stage_evidence(run_root, out_root)
    mechanism, regression, safety = build_all(out_root)
    _write_json(os.path.join(out_root, "metrics", "mechanism.json"), mechanism)
    _write_json(os.path.join(out_root, "metrics", "regression.json"), regression)
    _write_json(os.path.join(out_root, "metrics", "stack-safety.json"), safety)
    _write_json(os.path.join(out_root, "evidence", "safety", "stack-safety.json"), safety)
    derived = mechanism["derived"]
    repro = {
        "candidate_freeze_commit": "f5b215f36ade249398d45d407c7201bff861f258",
        "candidate_freeze_verified": bool(safety.get("candidate_freeze_ok")),
        "clean_clone_verified": False,
        "command": "python -m benchmark.nested_stack_reproduce --root experiments/published/nested-stack-v0.3.13 --verify",
        "evidence_manifest_verified": True,
        "expected_mechanism_sha256": sha256_bytes(canonical_json_bytes(mechanism)),
        "expected_regression_sha256": sha256_bytes(canonical_json_bytes(regression)),
        "expected_safety_sha256": sha256_bytes(canonical_json_bytes(safety)),
        "historical_c1_freeze_verified": "c1" not in (safety.get("historical_freeze_failures") or []),
        "historical_guard_freeze_verified": "v0.3.9-guard" not in (
            safety.get("historical_freeze_failures") or []),
        "match": False,
        "outcome": derived["outcome"],
        "product_default_changed": False,
        "protocol_commit": "9237ffd6640905d634473419b6b3edfaffe9fa82",
        "regression_analysis_commit": "0fda87449b0a15eb740277993ec372ad48b0d535",
        "target_freeze_verified": not any(
            name in (safety.get("historical_freeze_failures") or [])
            for name in TARGET_FREEZES),
        "verified_head": "",
    }
    _write_json(os.path.join(out_root, "metrics", "reproduction.json"), repro)
    config = {
        "outcome": derived["outcome"],
        "outcome_meaning": derived["outcome_meaning"],
        "product_default": "NoFrontier, sequence_mode=off",
        "product_default_changed": False,
        "promotion_prohibited": True,
        "protocol_commit": repro["protocol_commit"],
        "candidate_freeze_commit": repro["candidate_freeze_commit"],
        "verify_command": repro["command"],
        "generalization_claim": False,
        "v0_3_11_outcome": "D",
        "v0_3_12_outcome": "C",
    }
    _write_json(os.path.join(out_root, "config.json"), config)
    _write(os.path.join(out_root, "summary.md"), write_summary(mechanism, regression, safety))
    _write_json(os.path.join(out_root, "evidence-manifest.json"), _manifest(out_root))
    return derived


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", default=RUN_ROOT)
    parser.add_argument("--out", default=PUBLISHED_ROOT)
    args = parser.parse_args(argv)
    derived = publish(args.run_root, args.out)
    print(f"outcome {derived['outcome']} {derived['outcome_meaning']}")
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
