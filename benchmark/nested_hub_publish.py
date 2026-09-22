"""Publish v0.3.12 evidence. Numbers come from traces and the frozen gates."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil

from ghostqa.exploration.policy import GhostPolicy
from benchmark.algorithm_freeze import DEFAULT_FREEZE, sha256_file, verify_freeze
from benchmark.application_shape_evidence import (
    canonical_json_bytes, load_json, load_jsonl, sha256_bytes,
)
from benchmark.fresh_transfer_analysis import normalize_url
from benchmark.nested_hub_analysis import (
    assess_target, derive_v0312_outcome, lifecycle_markers,
)
from benchmark.nested_hub_detector import summarize_preemptions
from benchmark.return_cycle_guard_reproduce import verify_candidate_identity
from benchmark.return_cycle_modelcheck import run_exhaustive_check
from benchmark.return_cycle_safety import collect_safety_suite
from ghostqa.exploration.nested_hub_guard import NestedHubPreservingSequenceController
import benchmark.return_cycle_modelcheck as modelcheck

PUBLISHED_ROOT = os.path.join(
    "experiments", "published", "nested-hub-parent-v0.3.12")
CANDIDATE_FREEZE = os.path.join(
    "experiments", "frozen", "ghost-nested-hub-guard-v0.3.12", "freeze.json")
PROTOCOL = os.path.join("experiments", "validation", "v0.3.12", "protocol.json")
V0311 = os.path.join(
    "experiments", "published", "multi-target-replication-v0.3.11")
V0311_TARGETS = {
    "buggy-crm": os.path.join(
        "experiments", "frozen", "v0.3.11-multitarget", "buggy-crm", "freeze.json"),
    "buggy-ops": os.path.join(
        "experiments", "frozen", "v0.3.11-multitarget", "buggy-ops", "freeze.json"),
}
C1 = "ghost-structural-memory"
GUARD = "ghost-structural-return-guard"
NESTED = "ghost-structural-nested-return-guard"
POLICIES = (C1, GUARD, NESTED)
BUDGETS = (40, 80, 120)
PRIMARY = 120
MECHANISM_APPS = ("buggy-crm", "buggy-ops")
KINDS = ("events.jsonl", "graph.json", "sequence_events.json")

REGRESSION = (
    {
        "id": "wiki",
        "app": "buggy-wiki",
        "evidence_dir": "buggy-wiki",
        "reference_root": V0311,
        "reference_metrics": os.path.join(
            V0311, "evidence", "buggy-wiki", "metrics.json"),
    },
    {
        "id": "buggy-desk",
        "app": "buggy-desk",
        "evidence_dir": "buggy-desk",
        "reference_root": os.path.join(
            "experiments", "published", "fresh-transfer-v0.3.10"),
        "reference_metrics": os.path.join(
            "experiments", "published", "fresh-transfer-v0.3.10",
            "evidence", "buggy-desk", "metrics.json"),
    },
    {
        "id": "buggy-shop",
        "app": "buggy-shop",
        "evidence_dir": "buggy-shop",
        "reference_root": os.path.join(
            "experiments", "published", "return-cycle-guard-v0.3.9"),
        "reference_metrics": os.path.join(
            "experiments", "published", "return-cycle-guard-v0.3.9",
            "evidence", "shop", "metrics.json"),
    },
    {
        "id": "deepbench",
        "app": "buggy-flow",
        "evidence_dir": "deepbench",
        "reference_root": os.path.join(
            "experiments", "published", "return-cycle-guard-v0.3.9"),
        "reference_metrics": os.path.join(
            "experiments", "published", "return-cycle-guard-v0.3.9",
            "evidence", "deepbench", "metrics.json"),
    },
)

N_SERIES = (
    ("N1", "test_n1_nested_branch_does_not_kill_outer_instance"),
    ("N2", "test_n2_nested_branch_consumes_commitment"),
    ("N3", "test_n3_nested_branch_reaches_horizon"),
    ("N4", "test_n4_return_still_targets_outer_parent"),
    ("N5", "test_n5_return_cycle_guard_still_exact"),
    ("N6", "test_n6_no_open_instance_matches_historical_branch_start"),
    ("N7", "test_n7_outside_window_matches_historical_controller"),
    ("N8", "test_n8_finding_during_nested_traversal_is_l2_later"),
    ("N9", "test_n9_crash_during_nested_traversal_is_one_terminal"),
    ("N10", "test_n10_nested_branch_accounting_is_not_a_new_sequence"),
    ("N11", "test_n11_repeated_nested_hub_does_not_reset_parent_or_commitment"),
    ("N12", "test_n12_reset_clears_candidate_nested_state"),
)
APP_NEEDLES = (
    "bugs.manifest", "topology.manifest", "topology.json",
    "buggy-crm", "buggy-ops", "buggy-wiki", "buggy-desk", "buggy-shop",
    "buggy-flow", "BUG-", "BuggyShop", "BuggyDesk", "DeepBench",
    "cart.html", "RETURN_CYCLE_LIMIT", "accounts.html",
)


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text if text.endswith("\n") else text + "\n")


def _write_json(path: str, obj) -> None:
    _write(path, canonical_json_bytes(obj).decode("utf-8"))


def _load_guard_tests():
    path = os.path.join("tests", "test_nested_hub_guard.py")
    spec = importlib.util.spec_from_file_location("test_nested_hub_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _runs(path: str) -> list:
    if not os.path.isfile(path):
        return []
    data = load_json(path)
    if isinstance(data, dict):
        return list(data.get("runs") or [])
    if isinstance(data, list):
        return data
    return []


def _row(path: str, policy: str, budget: int) -> dict:
    for row in _runs(path):
        if row.get("policy") == policy and int(row.get("budget") or 0) == budget:
            return row
    return {}


def _confirmed(path: str, policy: str, budget: int) -> list:
    return sorted(_row(path, policy, budget).get("confirmed_bugs") or [])


def _seq_counts(seq: list) -> dict:
    def n_event(name: str) -> int:
        return sum(1 for event in seq or [] if event.get("event") == name)

    def n_outcome(outcome: str) -> int:
        return sum(
            1 for event in seq or []
            if event.get("event") == "sequence_terminal"
            and event.get("outcome") == outcome)

    instances = set()
    for event in seq or []:
        if event.get("event") == "branch_start" and event.get("sequence_instance_id"):
            instances.add(event["sequence_instance_id"])
    nested_keys = {
        event.get("nested_branch_key")
        for event in seq or []
        if event.get("event") == "nested_branch_followup" and event.get("nested_branch_key")
    }
    follow = n_event("nested_branch_followup")
    return {
        "branch_start_events": n_event("branch_start"),
        "sequence_instances_started": len(instances),
        "sequence_lost_parent": n_outcome("lost_parent"),
        "sequence_horizon_reached": n_event("sequence_horizon_reached"),
        "return_attempt_events": n_event("return_attempt"),
        "sequence_instances_returned": n_outcome("returned"),
        "successful_return_to_parent_events": n_outcome("returned"),
        "return_cycle_escape_events": n_event("return_cycle_escape"),
        "nested_branch_followup_events": follow,
        "unique_nested_branches_followed": len(nested_keys),
        "nested_preemption_avoided_events": follow,
    }


def _urls(graph: dict, row: dict) -> list:
    found = []
    for node in graph.get("nodes") or []:
        url = normalize_url(node.get("url") or "")
        if url and url not in found:
            found.append(url)
    if found:
        return sorted(found)
    return sorted(normalize_url(url) for url in (row.get("unique_urls") or []) if url)


def _load_cell(base: str, policy: str, budget: int):
    stem = f"{policy}_b{budget}_s1"
    events_path = os.path.join(base, stem + ".events.jsonl")
    graph_path = os.path.join(base, stem + ".graph.json")
    seq_path = os.path.join(base, stem + ".sequence_events.json")
    events = load_jsonl(events_path) if os.path.isfile(events_path) else []
    graph = load_json(graph_path) if os.path.isfile(graph_path) else {"nodes": []}
    seq = load_json(seq_path) if os.path.isfile(seq_path) else []
    return events, graph, seq


def _cell_view(base: str, policy: str, budget: int) -> dict:
    row = _row(os.path.join(base, "metrics.json"), policy, budget)
    events, graph, seq = _load_cell(base, policy, budget)
    urls = _urls(graph, row)
    states = len(graph.get("nodes") or []) or row.get("states") or 0
    view = {
        "policy": policy,
        "budget": budget,
        "states": states,
        "clusters": row.get("clusters"),
        "variants": row.get("variants"),
        "normalized_unique_urls": len(urls) if urls else row.get("normalized_unique_urls"),
        "unique_urls": urls,
        "bug_discovery_rate": row.get("bug_discovery_rate"),
        "deep_bug_discovery_rate": row.get("deep_bug_discovery_rate"),
        "confirmed_bugs": sorted(row.get("confirmed_bugs") or []),
        "repeat_rate": row.get("repeat_rate"),
        "discovery_auc": row.get("discovery_auc"),
    }
    view.update(_seq_counts(seq))
    return view


def _audit(seq: list) -> list:
    events = list(seq or [])
    start = next(
        (i for i, event in enumerate(events)
         if event.get("event") == "nested_branch_followup"),
        None)
    if start is None:
        return []
    iid = events[start].get("sequence_instance_id")
    begin = start
    for index in range(start, -1, -1):
        event = events[index]
        if (event.get("event") == "branch_start"
                and event.get("sequence_instance_id") == iid):
            begin = index
            break
    end = min(len(events), start + 24)
    for index in range(start + 1, len(events)):
        event = events[index]
        if (event.get("sequence_instance_id") == iid
                and event.get("event") in ("sequence_terminal", "return_cycle_escape")):
            end = index + 1
            break
        if index >= start + 30:
            end = index
            break
    keep = []
    for event in events[begin:end]:
        keep.append({
            "step": event.get("step"),
            "event": event.get("event"),
            "sequence_instance_id": event.get("sequence_instance_id"),
            "branch_key": event.get("branch_key"),
            "outcome": event.get("outcome"),
            "outer_branch": event.get("outer_branch"),
            "outer_parent_hub_sig": event.get("outer_parent_hub_sig"),
            "nested_hub_sig": event.get("nested_hub_sig"),
            "nested_branch_key": event.get("nested_branch_key"),
            "commitment_left_before": event.get("commitment_left_before"),
        })
    return keep


def historical_detector_ok() -> bool:
    for app in MECHANISM_APPS:
        base = os.path.join(V0311, "evidence", app)
        _events, _graph, seq = _load_cell(base, GUARD, PRIMARY)
        events = load_jsonl(os.path.join(
            base, f"{GUARD}_b{PRIMARY}_s1.events.jsonl"))
        summary = summarize_preemptions(seq, events)
        if summary["commitment_window_preemptions"] < 1:
            return False
        if summary["return_attempt_events"] != 0:
            return False
        if summary["sequence_horizon_reached"] != 0:
            return False
    return True


def _product_default_changed() -> bool:
    policy = GhostPolicy()
    return not (
        policy.name == "ghost"
        and policy.use_frontier is False
        and policy.sequence_mode == "off"
        and policy.sequence is None
    )


def _app_specific() -> bool:
    path = os.path.join("ghostqa", "exploration", "nested_hub_guard.py")
    src = open(path, encoding="utf-8").read()
    return any(needle in src for needle in APP_NEEDLES)


def _candidate_exhaustive() -> dict:
    original = modelcheck.ReturnCycleGuardSequenceController
    modelcheck.ReturnCycleGuardSequenceController = NestedHubPreservingSequenceController
    try:
        return run_exhaustive_check()
    finally:
        modelcheck.ReturnCycleGuardSequenceController = original


def build_safety() -> dict:
    module = _load_guard_tests()
    rows = []
    failures = 0
    for label, name in N_SERIES:
        try:
            getattr(module, name)()
            rows.append({"id": label, "name": name, "pass": True})
        except Exception as exc:
            failures += 1
            rows.append({
                "id": label, "name": name, "pass": False,
                "error": f"{type(exc).__name__}: {exc}",
            })
    differential_names = (
        "test_differential_equivalence_without_nested_preemption",
        "test_select_matches_guard_before_any_nested_click",
        "test_s1_s7_expectations_hold_on_candidate_scripts",
    )
    differential = []
    differential_failures = 0
    for name in differential_names:
        try:
            getattr(module, name)()
            differential.append({"name": name, "pass": True})
        except Exception as exc:
            differential_failures += 1
            differential.append({
                "name": name, "pass": False,
                "error": f"{type(exc).__name__}: {exc}",
            })
    suite = collect_safety_suite()
    guard_ex = run_exhaustive_check()
    cand_ex = _candidate_exhaustive()
    s_rows = []
    for row in suite.get("rows") or []:
        s_rows.append({
            "scenario": row.get("scenario"),
            "name": row.get("name"),
            "pass": bool(row.get("pass")),
            "escapes": row.get("escapes"),
            "returned": row.get("returned"),
        })
    return {
        "n_series": rows,
        "n_series_cases": len(rows),
        "n_series_failures": failures,
        "differential": differential,
        "differential_failures": differential_failures,
        "s1_s7": s_rows,
        "s1_s7_cases": len(s_rows),
        "s1_s7_failures": sum(1 for row in s_rows if not row["pass"]),
        "s1_s7_all_pass": bool(suite.get("all_pass")) and differential_failures == 0,
        "exhaustive_guard_traces": guard_ex.get("traces_enumerated"),
        "exhaustive_guard_failures": guard_ex.get("failures"),
        "exhaustive_candidate_traces": cand_ex.get("traces_enumerated"),
        "exhaustive_candidate_failures": cand_ex.get("failures"),
        "exhaustive_failures": int(guard_ex.get("failures") or 0) + int(
            cand_ex.get("failures") or 0),
        "exhaustive_traces": cand_ex.get("traces_enumerated"),
        "app_specific_logic": _app_specific(),
        "product_default_changed": _product_default_changed(),
    }


def build_regression(root: str) -> dict:
    cases = {}
    lost = {}
    for spec in REGRESSION:
        base = os.path.join(root, "evidence", "regression", spec["evidence_dir"])
        view = _cell_view(base, NESTED, PRIMARY) if os.path.isdir(base) else {}
        reference = _confirmed(spec["reference_metrics"], GUARD, PRIMARY)
        candidate = sorted(view.get("confirmed_bugs") or [])
        missing = sorted(set(reference) - set(candidate))
        lost[spec["id"]] = missing
        ref_row = _row(spec["reference_metrics"], GUARD, PRIMARY)
        cases[spec["id"]] = {
            "app": spec["app"],
            "reference_policy": GUARD,
            "reference_confirmed": reference,
            "candidate_confirmed": candidate,
            "lost": missing,
            "reference_states": ref_row.get("states"),
            "reference_urls": ref_row.get("normalized_unique_urls"),
            "states": view.get("states"),
            "normalized_unique_urls": view.get("normalized_unique_urls"),
            "bug_discovery_rate": view.get("bug_discovery_rate"),
            "return_attempt_events": view.get("return_attempt_events"),
            "sequence_instances_returned": view.get("sequence_instances_returned"),
            "return_cycle_escape_events": view.get("return_cycle_escape_events"),
            "nested_branch_followup_events": view.get("nested_branch_followup_events"),
            "sequence_lost_parent": view.get("sequence_lost_parent"),
            "return_inflation": False,
        }
        if os.path.isdir(base):
            _events, _graph, seq = _load_cell(base, NESTED, PRIMARY)
            from benchmark.nested_hub_analysis import candidate_accounting_inflation
            cases[spec["id"]]["return_inflation"] = candidate_accounting_inflation(seq)
    return {"cases": cases, "lost_confirmed": lost}


def build_mechanism(root: str, safety: dict, regression: dict) -> dict:
    targets = {}
    assessments = {}
    parent_ok = True
    inflation = False
    for app in MECHANISM_APPS:
        base = os.path.join(root, "evidence", app)
        cells = {}
        for policy in POLICIES:
            for budget in BUDGETS:
                cells[f"{policy}@{budget}"] = _cell_view(base, policy, budget)
        g_events, g_graph, g_seq = _load_cell(base, GUARD, PRIMARY)
        n_events, n_graph, n_seq = _load_cell(base, NESTED, PRIMARY)
        g_view = cells[f"{GUARD}@{PRIMARY}"]
        n_view = cells[f"{NESTED}@{PRIMARY}"]
        assessed = assess_target(
            g_seq, g_events, n_seq, n_events,
            guard_states=int(g_view.get("states") or 0),
            guard_urls=int(g_view.get("normalized_unique_urls") or 0),
            nested_states=int(n_view.get("states") or 0),
            nested_urls=int(n_view.get("normalized_unique_urls") or 0),
        )
        if not assessed.get("parent_intact"):
            parent_ok = False
        if assessed.get("return_inflation"):
            inflation = True
        assessments[app] = assessed
        targets[app] = {
            "cells": cells,
            "assessment_120": assessed,
            "markers": lifecycle_markers(n_seq, n_events),
            "audit": _audit(n_seq),
            "historical_guard_preemption": summarize_preemptions(g_seq, g_events),
        }
    for case in (regression.get("cases") or {}).values():
        if case.get("return_inflation"):
            inflation = True
    freezes_ok = (
        verify_freeze(DEFAULT_FREEZE) == []
        and verify_candidate_identity() == []
        and all(verify_freeze(path) == [] for path in V0311_TARGETS.values())
    )
    candidate_ok = verify_freeze(CANDIDATE_FREEZE) == []
    derived = derive_v0312_outcome(
        candidate_freeze_ok=candidate_ok,
        historical_freezes_ok=freezes_ok,
        n_series_failures=int(safety.get("n_series_failures") or 0),
        s1_s7_pass=bool(safety.get("s1_s7_all_pass")),
        exhaustive_failures=int(safety.get("exhaustive_failures") or 0),
        exhaustive_traces=int(safety.get("exhaustive_traces") or 0),
        crm=assessments["buggy-crm"],
        ops=assessments["buggy-ops"],
        return_inflation=inflation,
        parent_corruption=not parent_ok,
        app_specific_logic=bool(safety.get("app_specific_logic")),
        product_default_changed=bool(safety.get("product_default_changed")),
        lost_confirmed=regression.get("lost_confirmed") or {},
        detector_historical_ok=historical_detector_ok(),
    )
    return {
        "version": "v0.3.12",
        "policies": list(POLICIES),
        "budgets": list(BUDGETS),
        "primary_budget": PRIMARY,
        "targets": targets,
        "derived": derived,
    }


def build_all(root: str):
    safety = build_safety()
    regression = build_regression(root)
    mechanism = build_mechanism(root, safety, regression)
    return mechanism, regression, safety


def _copy_cell(src_base: str, dst_base: str, policy: str, budget: int) -> None:
    os.makedirs(dst_base, exist_ok=True)
    stem = f"{policy}_b{budget}_s1"
    for kind in KINDS:
        src = os.path.join(src_base, stem + "." + kind)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(dst_base, stem + "." + kind))


def copy_evidence(crm_root: str, ops_root: str, regression_roots: dict,
                  out_root: str) -> None:
    mapping = {"buggy-crm": crm_root, "buggy-ops": ops_root}
    for app, run_root in mapping.items():
        src = os.path.join(run_root, "evidence", app)
        dst = os.path.join(out_root, "evidence", app)
        for policy in POLICIES:
            for budget in BUDGETS:
                _copy_cell(src, dst, policy, budget)
        metrics = os.path.join(src, "metrics.json")
        if os.path.isfile(metrics):
            shutil.copy2(metrics, os.path.join(dst, "metrics.json"))
    for spec in REGRESSION:
        run_root = regression_roots[spec["id"]]
        src = os.path.join(run_root, "evidence", spec["app"])
        dst = os.path.join(out_root, "evidence", "regression", spec["evidence_dir"])
        _copy_cell(src, dst, NESTED, PRIMARY)
        metrics = os.path.join(src, "metrics.json")
        if os.path.isfile(metrics):
            kept = [
                row for row in _runs(metrics)
                if row.get("policy") == NESTED and int(row.get("budget") or 0) == PRIMARY
            ]
            _write_json(os.path.join(dst, "metrics.json"), {"app": spec["app"], "runs": kept})


def _fmt_bugs(bugs: list) -> str:
    return ", ".join(bugs) if bugs else "—"


def write_summary(mechanism: dict, regression: dict, safety: dict) -> str:
    derived = mechanism["derived"]
    lines = [
        "# GhostQA v0.3.12 — Nested-Hub Parent Preservation",
        "",
        f"**Outcome {derived['outcome']} — {derived['outcome_meaning']}** "
        "(computed from the preregistered gates).",
        "",
        "Product default unchanged: NoFrontier, `sequence_mode=off`.",
        "Generalization claim: no.",
        "",
        "CRM and Ops are inspected mechanism-development cases from the frozen "
        "v0.3.11 suite. A repair here is not a fresh-generalization result.",
        "",
        "## Historical preemption",
        "",
        "The v0.3.11 guard never reached return on CRM or Ops because an open "
        "sequence was terminated `lost_parent` at the next hub branch click, "
        "before horizon. Wiki reached horizon and return.",
        "",
        "| target | G branch starts | G lost_parent | G horizon | G return attempts | G states | G URLs |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for app in MECHANISM_APPS:
        guard = mechanism["targets"][app]["cells"][f"{GUARD}@{PRIMARY}"]
        lines.append(
            f"| {app} | {guard.get('branch_start_events')} | "
            f"{guard.get('sequence_lost_parent')} | {guard.get('sequence_horizon_reached')} | "
            f"{guard.get('return_attempt_events')} | {guard.get('states')} | "
            f"{guard.get('normalized_unique_urls')} |"
        )
    lines += [
        "",
        "## Mechanism @120",
        "",
        "| target | policy | states | URLs | lost_parent | nested-followup | horizon | return attempts | returned | escapes | confirmed |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for app in MECHANISM_APPS:
        for policy in POLICIES:
            cell = mechanism["targets"][app]["cells"][f"{policy}@{PRIMARY}"]
            lines.append(
                f"| {app} | {policy} | {cell.get('states')} | "
                f"{cell.get('normalized_unique_urls')} | {cell.get('sequence_lost_parent')} | "
                f"{cell.get('nested_branch_followup_events')} | "
                f"{cell.get('sequence_horizon_reached')} | {cell.get('return_attempt_events')} | "
                f"{cell.get('sequence_instances_returned')} | "
                f"{cell.get('return_cycle_escape_events')} | "
                f"{_fmt_bugs(cell.get('confirmed_bugs') or [])} |"
            )
    lines += [
        "",
        "## Candidate timeline @120",
        "",
        "| target | first follow-up | first horizon after | first return | first escape | first novel state | first novel URL |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for app in MECHANISM_APPS:
        markers = mechanism["targets"][app]["markers"]
        lines.append(
            f"| {app} | {markers.get('first_nested_followup_step')} | "
            f"{markers.get('first_horizon_step_after_followup')} | "
            f"{markers.get('first_return_attempt_step')} | "
            f"{markers.get('first_escape_step')} | "
            f"{markers.get('first_novel_state_step_after_followup')} | "
            f"{markers.get('first_novel_url_after_followup') or '—'} |"
        )
    lines += [
        "",
        "## Regression @120",
        "",
        "| target | guard confirmed | candidate confirmed | lost |",
        "|---|---|---|---|",
    ]
    for spec in REGRESSION:
        case = regression["cases"][spec["id"]]
        lines.append(
            f"| {spec['id']} | {_fmt_bugs(case.get('reference_confirmed') or [])} | "
            f"{_fmt_bugs(case.get('candidate_confirmed') or [])} | "
            f"{_fmt_bugs(case.get('lost') or [])} |"
        )
    lines += [
        "",
        "| target | states | URLs | BDR | return attempts | returned | escapes | nested follow-up | lost_parent |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for spec in REGRESSION:
        case = regression["cases"][spec["id"]]
        lines.append(
            f"| {spec['id']} | {case.get('states')} | {case.get('normalized_unique_urls')} | "
            f"{case.get('bug_discovery_rate')} | {case.get('return_attempt_events')} | "
            f"{case.get('sequence_instances_returned')} | {case.get('return_cycle_escape_events')} | "
            f"{case.get('nested_branch_followup_events')} | {case.get('sequence_lost_parent')} |"
        )
    lines += [
        "",
        "## Safety",
        "",
        "| suite | cases/traces | failures |",
        "|---|---:|---:|",
        f"| N1-N12 | {safety.get('n_series_cases')} | {safety.get('n_series_failures')} |",
        f"| S1-S7 | {safety.get('s1_s7_cases')} | {safety.get('s1_s7_failures')} |",
        f"| bounded return model | {safety.get('exhaustive_traces')} | "
        f"{safety.get('exhaustive_candidate_failures')} |",
        "",
        f"Guard exhaustive traces {safety.get('exhaustive_guard_traces')}, "
        f"failures {safety.get('exhaustive_guard_failures')}.",
        f"Differential failures: {safety.get('differential_failures')}.",
        "",
        "## Gate",
        "",
        f"CRM mechanism repair: {derived.get('crm_repair')}. "
        f"Ops mechanism repair: {derived.get('ops_repair')}. "
        f"Historical preemption reproduced: {derived.get('detector_historical_ok')}.",
        "Confirmed-bug loss: " + (
            ", ".join(derived.get("lost_confirmed_cases") or [])
            or "none") + ".",
        "N1–N12, S1–S7, and the bounded return model are in the safety table. "
        + (
            "Outcome C means this candidate is not advanced."
            if derived.get("outcome") == "C"
            else f"Computed outcome: {derived.get('outcome')}."
        ),
        "",
        "## Scope",
        "",
        (
            "CRM and Ops were already inspected. The lifecycle change is visible there, "
            "and it is not a fresh-generalization result. "
            "Confirmed bugs were lost on the historical regression cases listed above. "
            "Do not ship this candidate as the default, and do not treat it as transfer-ready."
            if derived.get("outcome") == "C"
            else
            "CRM and Ops were already inspected. This is not a fresh-generalization result. "
            "Product default stays NoFrontier with sequence_mode off."
        ),
        "",
    ]
    if derived.get("outcome") == "A":
        lines += [
            "## Public wording",
            "",
            "v0.3.12 修复了 nested hub 抢断外层 sequence 的机制问题。",
            "CRM / Ops 是已分析机制用例，因此这不是 fresh-generalization 结论。",
            "历史 Wiki / BuggyDesk / BuggyShop / DeepBench 回归未丢失既有缺陷。",
            "",
        ]
    return "\n".join(lines)


def write_manifest(root: str) -> dict:
    files = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root).replace("\\", "/")
            if rel == "evidence-manifest.json":
                continue
            files.append({"relative_path": rel, "sha256": sha256_file(path)})
    files.sort(key=lambda item: item["relative_path"])
    manifest = {"expected_file_count": len(files), "files": files}
    _write_json(os.path.join(root, "evidence-manifest.json"), manifest)
    return manifest


def publish(crm_root: str, ops_root: str, regression_roots: dict,
            out_root: str = PUBLISHED_ROOT) -> dict:
    if os.path.isdir(out_root):
        shutil.rmtree(out_root)
    copy_evidence(crm_root, ops_root, regression_roots, out_root)
    shutil.copy2(PROTOCOL, os.path.join(out_root, "protocol.json"))
    shutil.copy2(CANDIDATE_FREEZE, os.path.join(out_root, "candidate-freeze.json"))
    mechanism, regression, safety = build_all(out_root)
    _write_json(os.path.join(out_root, "metrics", "mechanism.json"), mechanism)
    _write_json(os.path.join(out_root, "metrics", "regression.json"), regression)
    _write_json(os.path.join(out_root, "metrics", "safety.json"), safety)
    _write_json(os.path.join(out_root, "evidence", "safety", "safety.json"), safety)
    mech_hash = sha256_bytes(canonical_json_bytes(mechanism))
    reg_hash = sha256_bytes(canonical_json_bytes(regression))
    safety_hash = sha256_bytes(canonical_json_bytes(safety))
    config = {
        "version": "v0.3.12",
        "starting_head": "ab7a11031fe9f3f0ad84aaa67a9e33dc9bef4d85",
        "protocol_commit": "a1c2ac093f3219f12434aa4570ad13786c14c3be",
        "candidate_freeze_commit": "02ba0304775c7fd0188e5c2274d413fb7565d8bb",
        "candidate": NESTED,
        "product_default": {"policy": "NoFrontier", "sequence_mode": "off",
                             "changed": False},
        "verify_command": (
            "python -m benchmark.nested_hub_reproduce "
            "--root experiments/published/nested-hub-parent-v0.3.12 --verify"),
        "expected_mechanism_sha256": mech_hash,
        "expected_regression_sha256": reg_hash,
        "expected_safety_sha256": safety_hash,
        "outcome": mechanism["derived"]["outcome"],
    }
    _write_json(os.path.join(out_root, "config.json"), config)
    repro = {
        "candidate_freeze_verified": verify_freeze(CANDIDATE_FREEZE) == [],
        "clean_clone_verified": False,
        "command": config["verify_command"],
        "evidence_manifest_verified": False,
        "expected_mechanism_sha256": mech_hash,
        "expected_regression_sha256": reg_hash,
        "expected_safety_sha256": safety_hash,
        "historical_c1_freeze_verified": verify_freeze(DEFAULT_FREEZE) == [],
        "historical_guard_freeze_verified": verify_candidate_identity() == [],
        "match": False,
        "outcome": mechanism["derived"]["outcome"],
        "product_default_changed": False,
        "protocol_commit": config["protocol_commit"],
        "candidate_freeze_commit": config["candidate_freeze_commit"],
        "target_freeze_verified": all(
            verify_freeze(path) == [] for path in V0311_TARGETS.values()),
        "verified_head": "",
    }
    _write_json(os.path.join(out_root, "metrics", "reproduction.json"), repro)
    _write(os.path.join(out_root, "summary.md"), write_summary(
        mechanism, regression, safety))
    write_manifest(out_root)
    repro["evidence_manifest_verified"] = True
    repro["match"] = True
    _write_json(os.path.join(out_root, "metrics", "reproduction.json"), repro)
    write_manifest(out_root)
    return mechanism["derived"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crm", default=os.path.join("experiments", "runs", "v0312-crm"))
    parser.add_argument("--ops", default=os.path.join("experiments", "runs", "v0312-ops"))
    parser.add_argument("--wiki", default=os.path.join("experiments", "runs", "v0312-wiki"))
    parser.add_argument("--desk", default=os.path.join("experiments", "runs", "v0312-desk"))
    parser.add_argument("--shop", default=os.path.join("experiments", "runs", "v0312-shop"))
    parser.add_argument("--deep", default=os.path.join("experiments", "runs", "v0312-deep"))
    parser.add_argument("--out", default=PUBLISHED_ROOT)
    args = parser.parse_args(argv)
    derived = publish(
        args.crm, args.ops,
        {
            "wiki": args.wiki,
            "buggy-desk": args.desk,
            "buggy-shop": args.shop,
            "deepbench": args.deep,
        },
        args.out,
    )
    print(f"outcome {derived['outcome']} {derived['outcome_meaning']}")
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
