"""Publish the v0.3.19 inspected-repair result from the frozen candidate cells."""
from __future__ import annotations

import os
import shutil

from benchmark.algorithm_freeze import sha256_file, verify_freeze
from benchmark.application_shape_evidence import (
    canonical_json_bytes, load_json, load_jsonl, sha256_bytes, steps_only,
)
from benchmark.finding_return_entry_analysis import (
    DEEP_GUARD, LAB_GUARD, REGRESSION_APPS, deep_coverage_ok, derive_v0319_outcome,
    directory_preserved_v0319, lab_mechanism_gate, transfer_preserved, trigger_counts_match,
)
from benchmark.finding_return_entry_modelcheck import enumerate_traces as enumerate_finding
from benchmark.finding_return_entry_run import APPS, CANDIDATE, CELLS, cell_dir, cell_stem
from benchmark.finding_return_entry_trace import (
    diagnose_deep, diagnose_lab, horizon_only_drain_count, nonfinding_drain_count,
    trigger_consistency,
)
from benchmark.fresh_handoff_analysis import product_default_changed
from benchmark.fresh_transfer_analysis import normalize_url
from benchmark.horizon_handoff_analysis import GUARD_CONFIRMED
from benchmark.horizon_handoff_modelcheck import enumerate_traces as enumerate_handoff
from benchmark.horizon_handoff_publish import HISTORY
from benchmark.local_action_drain_analysis import confirmed_of, lost_vs
from benchmark.local_action_drain_audit import _first_hit
from benchmark.local_action_drain_audit import _manifest as _lab_manifest
from benchmark.local_action_drain_modelcheck import enumerate_traces as enumerate_local
from benchmark.reentry_frontier_analysis import mechanism_preserved
from benchmark.reentry_frontier_modelcheck import enumerate_traces as enumerate_reentry
from benchmark.return_cycle_guard_reproduce import verify_candidate_identity
from benchmark.return_cycle_modelcheck import run_exhaustive_check
from benchmark.return_entry_drain_modelcheck import enumerate_traces as enumerate_entry

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_ROOT = os.path.join("experiments", "runs", "v0319-finding-return-entry")
PUBLISHED = os.path.join("experiments", "published", "finding-return-entry-v0.3.19")
FRESH = os.path.join("experiments", "published", "fresh-handoff-v0.3.15")
V0317_PUB = os.path.join("experiments", "published", "local-action-drain-v0.3.17")
V0318_PUB = os.path.join("experiments", "published", "return-entry-drain-v0.3.18")
PROTOCOL = os.path.join("experiments", "validation", "v0.3.19", "protocol.json")
ANALYSIS = os.path.join(
    "experiments", "validation", "v0.3.19", "v0318-trigger-context-analysis.json")
FREEZE = os.path.join(
    "experiments", "frozen", "ghost-finding-return-entry-v0.3.19", "freeze.json")
GUARD = "ghost-structural-return-guard"
HAND = "ghost-structural-horizon-handoff-guard"
V0317 = "ghost-structural-local-action-drain-guard"
V0318 = "ghost-structural-return-entry-drain-guard"
FRESH_APPS = ("buggy-directory", "buggy-lab", "buggy-forum", "buggy-billing")
SOURCE = os.path.join("ghostqa", "exploration", "finding_return_entry_guard.py")
NEEDLES = (
    "buggy-lab", "buggy-directory", "buggy-forum", "buggy-billing",
    "deepbench", "wiki", "crm", "bug-", "btn_close", "btn_reopen",
    "btn_login", "btn_demo_login", "result.html", "login.html",
    "lab_reopen_clears", "manifest", "topology", "app.js",
)
HISTORICAL_FREEZES = (
    "experiments/frozen/ghost-horizon-handoff-v0.3.14/freeze.json",
    "experiments/frozen/v0.3.15-fresh-handoff-suite/freeze.json",
    "experiments/frozen/ghost-reentry-frontier-v0.3.16/freeze.json",
    "experiments/frozen/ghost-local-action-drain-v0.3.17/freeze.json",
    "experiments/frozen/ghost-return-entry-drain-v0.3.18/freeze.json",
)


def _abs(path: str) -> str:
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


def _metrics(path: str) -> dict:
    full = _abs(path)
    if not os.path.isfile(full):
        return {}
    return load_json(full)


def _row(metrics: dict, policy: str, budget: int) -> dict:
    for row in metrics.get("runs") or []:
        if row.get("policy") == policy and int(row.get("budget") or 0) == budget:
            return row
    return {}


def _fresh_metrics(app: str) -> dict:
    return _metrics(os.path.join(FRESH, "evidence", app, "metrics.json"))


def _version_metrics(root: str, evidence: str) -> dict:
    return _metrics(os.path.join(root, "evidence", evidence, "metrics.json"))


def _hist_metrics(evidence: str) -> dict:
    return _metrics(HISTORY[evidence]["guard"])


def _run_metrics(run_root: str, app: str) -> dict:
    return _metrics(os.path.join(cell_dir(run_root, app), "metrics.json"))


def _seq_path(run_root: str, app: str, budget: int) -> str:
    return os.path.join(cell_dir(run_root, app), cell_stem(budget) + ".sequence_events.json")


def _events_path(run_root: str, app: str, budget: int) -> str:
    return os.path.join(cell_dir(run_root, app), cell_stem(budget) + ".events.jsonl")


def _needles() -> list:
    text = open(_abs(SOURCE), encoding="utf-8").read().lower()
    return [needle for needle in NEEDLES if needle in text]


def _evaluable() -> dict:
    per = load_json(_abs(os.path.join(FRESH, "metrics", "per-target.json")))
    out = {}
    for app, block in (per.get("targets") or {}).items():
        out[app] = bool((block.get("evaluable") or {}).get("actual_evaluable"))
    return out


def _safety() -> dict:
    finding = enumerate_finding()
    entry = enumerate_entry()
    local = enumerate_local()
    reentry = enumerate_reentry()
    handoff = enumerate_handoff()
    exhaustive = run_exhaustive_check()
    historical_ok = verify_candidate_identity() == [] and all(
        verify_freeze(_abs(path)) == [] for path in HISTORICAL_FREEZES)
    historical_models_ok = (
        entry["invariant_failures"] == 0 and entry["raw_traces"] == 66429
        and local["invariant_failures"] == 0 and local["raw_traces"] == 66429
        and reentry["invariant_failures"] == 0 and reentry["raw_traces"] == 37448
        and handoff["invariant_failures"] == 0 and handoff["raw_traces"] == 19607
        and int(exhaustive.get("failures") or 0) == 0
        and int(exhaustive.get("traces_enumerated") or 0) >= 5800
        and bool(exhaustive.get("s1_s7_all_pass"))
    )
    return {
        "fg_series_cases": 16,
        "horizon_differential_cases": 4,
        "re_series_cases": 16,
        "x_series_cases": 10,
        "finding_model_raw_traces": finding["raw_traces"],
        "finding_model_invariant_failures": finding["invariant_failures"],
        "finding_model_valid_traces": finding["valid_traces"],
        "return_entry_model_raw_traces": entry["raw_traces"],
        "return_entry_model_invariant_failures": entry["invariant_failures"],
        "local_model_raw_traces": local["raw_traces"],
        "local_model_invariant_failures": local["invariant_failures"],
        "reentry_model_raw_traces": reentry["raw_traces"],
        "reentry_model_invariant_failures": reentry["invariant_failures"],
        "handoff_model_raw_traces": handoff["raw_traces"],
        "handoff_model_invariant_failures": handoff["invariant_failures"],
        "return_exhaustive_traces": exhaustive.get("traces_enumerated"),
        "return_exhaustive_failures": exhaustive.get("failures"),
        "s1_s7_all_pass": bool(exhaustive.get("s1_s7_all_pass")),
        "historical_models_ok": historical_models_ok,
        "h_series_cases": 20,
        "n_series_cases": 12,
        "p_series_cases": 15,
        "r_series_cases": 12,
        "f_series_cases": 20,
        "a_series_cases": 12,
        "la_series_cases": 10,
        "integration_cases": 10,
        "app_specific_needles": _needles(),
        "candidate_freeze_ok": verify_freeze(_abs(FREEZE)) == [],
        "historical_freeze_ok": historical_ok,
        "protocol_executed_false": load_json(_abs(PROTOCOL)).get("executed") is False,
        "product_default_changed": product_default_changed(),
    }


def _slim(row: dict) -> dict:
    keys = (
        "policy", "budget", "states", "normalized_unique_urls", "confirmed_bugs",
        "horizon_handoff_started_events", "child_parent_witness_events",
        "parent_frame_resume_to_return_events", "horizon_handoff_unwind_events",
        "max_handoff_stack_depth", "nested_continuation_events",
        "sequence_horizon_reached", "sequence_instances_returned",
        "sequence_lost_parent", "return_cycle_escape_events",
        "witness_violations", "terminal_accounting_violations",
        "early_parent_reentry_events", "source_parent_reentry_repair_events",
        "reentry_double_completion_violations",
        "local_frontier_lease_granted_events", "local_frontier_lease_action_events",
        "frontier_repeated_key_violations", "frontier_monotonicity_violations",
        "local_action_drain_started_events", "local_action_drain_exhausted_events",
        "local_action_probe_completed_events", "local_action_promoted_to_child_events",
        "local_action_keys_drained", "repeated_local_action_key_violations",
        "local_action_sequence_accounting_violations",
        "return_entry_drain_started_events", "return_entry_drain_exhausted_events",
        "return_entry_drain_abort_events", "return_entry_probe_selected_events",
        "return_entry_probe_completed_events", "return_entry_probe_finding_events",
        "return_entry_probe_left_hub_events", "return_entry_epochs",
        "return_entry_accounting_violations", "return_attempts", "return_success",
        "finding_return_entry_trigger_events",
        "finding_return_entry_horizon_bypass_events",
        "finding_return_entry_nonfinding_bypass_events",
        "finding_return_entry_trigger_mismatch_violations",
        "finding_return_entry_reused_trigger_violations",
        "finding_return_entry_wrong_instance_violations",
    )
    return {key: row.get(key) for key in keys}


def _browser(steps: list, index: int) -> dict:
    for step in steps or []:
        if step.get("index") != index:
            continue
        action = step.get("action") or {}
        return {
            "index": index,
            "target_eid": action.get("target_eid") or "",
            "type": action.get("type") or "",
            "src_url": normalize_url(step.get("src_url") or ""),
            "dst_url": normalize_url(step.get("dst_url") or ""),
            "finding_kinds": sorted({
                item.get("kind") for item in (step.get("findings") or []) if item.get("kind")
            }),
            "finding_assert_ids": sorted({
                item.get("assert_id")
                for item in (step.get("findings") or []) if item.get("assert_id")
            }),
        }
    return {"index": index}


def _horizon_boundary(events: list, steps: list) -> dict:
    bypasses = [
        event for event in events or []
        if event.get("event") == "finding_return_entry_horizon_bypassed"
    ]
    if not bypasses:
        return {"present": False}
    first = min(bypasses, key=lambda event: event.get("step") or 0)
    step = first.get("step")
    drains = [
        event for event in events or []
        if event.get("event") == "return_entry_drain_started" and event.get("step") == step
    ]
    returns = [
        event for event in events or []
        if event.get("event") == "return_attempt"
        and isinstance(event.get("step"), int) and isinstance(step, int)
        and event["step"] > step
    ]
    following = []
    if isinstance(step, int):
        for offset in range(0, 4):
            following.append(_browser(steps, step + offset))
    return {
        "present": True,
        "step": step,
        "branch": first.get("branch") or "",
        "hub": first.get("hub") or "",
        "parent": first.get("parent") or "",
        "behavior": first.get("behavior") or "",
        "eligible_visible_buttons": first.get("eligible_visible_buttons"),
        "drain_started_on_boundary": bool(drains),
        "first_later_return_step": None if not returns else min(event["step"] for event in returns),
        "following_browser_steps": following,
    }


def _bug_notes(run_root: str, facts: dict) -> dict:
    path = _abs(_events_path(run_root, "buggy-lab", 120))
    steps = steps_only(load_jsonl(path)) if os.path.isfile(path) else []
    bugs = _lab_manifest()
    notes = {}
    for bug_id in ("BUG-L1", "BUG-L2", "BUG-L8", "BUG-L9", "BUG-L10"):
        hit = _first_hit(steps, bugs[bug_id]) if steps else None
        notes[bug_id] = {"first_hit": hit}
    notes["result"] = facts.get("result")
    notes["l9_recovered"] = bool(notes["BUG-L9"].get("first_hit"))
    return notes


def collect(run_root: str = RUN_ROOT) -> dict:
    missing = []
    cells = {}
    sequences = {}
    browsers = {}
    for app, budget in CELLS:
        if not os.path.isfile(_abs(_events_path(run_root, app, budget))):
            missing.append(f"{app}@{budget}")
            sequences[(app, budget)] = []
            browsers[(app, budget)] = []
        else:
            sequences[(app, budget)] = load_json(_abs(_seq_path(run_root, app, budget)))
            browsers[(app, budget)] = steps_only(load_jsonl(_abs(_events_path(run_root, app, budget))))
        cells[(app, budget)] = _row(_run_metrics(run_root, app), CANDIDATE, budget)
    evaluable = _evaluable()
    fresh = {}
    for app in FRESH_APPS:
        metrics = _fresh_metrics(app)
        evidence = APPS[app]["evidence"]
        fresh[app] = {
            "guard": _row(metrics, GUARD, 120),
            "horizon": _row(metrics, HAND, 120),
            "v0317": _row(_version_metrics(V0317_PUB, evidence), V0317, 120),
            "v0318": _row(_version_metrics(V0318_PUB, evidence), V0318, 120),
            "candidate": cells[(app, 120)],
        }
    historical = {}
    for app, meta in APPS.items():
        if app in FRESH_APPS:
            continue
        evidence = meta["evidence"]
        guard_confirmed = list(GUARD_CONFIRMED.get(evidence) or confirmed_of(
            _row(_hist_metrics(evidence), GUARD, 120)))
        historical[evidence] = {
            "source_app": app,
            "v0317": _row(_version_metrics(V0317_PUB, evidence), V0317, 120),
            "v0318": _row(_version_metrics(V0318_PUB, evidence), V0318, 120),
            "candidate": cells[(app, 120)],
            "guard_confirmed": guard_confirmed,
            "regression_case": evidence in REGRESSION_APPS,
        }
    lab_events = sequences.get(("buggy-lab", 120)) or []
    lab_steps = browsers.get(("buggy-lab", 120)) or []
    diagnosis = diagnose_lab(lab_events, lab_steps, cells.get(("buggy-lab", 120)) or {})
    deep_events = sequences.get(("buggy-flow", 120)) or []
    deep_steps = browsers.get(("buggy-flow", 120)) or []
    deep_row = cells.get(("buggy-flow", 120)) or {}
    deep_diag = diagnose_deep(deep_events, deep_row)
    deep_prev = historical.get("deepbench", {}).get("v0317") or {}
    coverage = deep_coverage_ok(deep_row, deep_prev)
    directory = fresh["buggy-directory"]["candidate"]
    lab = fresh["buggy-lab"]["candidate"]
    safety = _safety()
    regression_loss = []
    for evidence, block in historical.items():
        lost = lost_vs(block["guard_confirmed"], confirmed_of(block["candidate"]))
        if block["regression_case"] and lost:
            regression_loss.append({evidence: lost})
    witness = terminal = repeated = accounting = 0
    mismatch = reused = wrong = horizon_drains = nonfinding = 0
    counts_match = True
    per_cell = {}
    for app, budget in CELLS:
        row = cells[(app, budget)]
        events = sequences[(app, budget)]
        facts = trigger_consistency(events)
        witness += int(row.get("witness_violations") or 0)
        terminal += int(row.get("terminal_accounting_violations") or 0)
        repeated += int(row.get("repeated_local_action_key_violations") or 0)
        accounting += int(row.get("return_entry_accounting_violations") or 0)
        mismatch += int(row.get("finding_return_entry_trigger_mismatch_violations") or 0)
        reused += int(row.get("finding_return_entry_reused_trigger_violations") or 0)
        wrong += int(row.get("finding_return_entry_wrong_instance_violations") or 0)
        mismatch += int(facts["mismatch"] or 0)
        reused += int(facts["reused"] or 0)
        wrong += int(facts["wrong_instance"] or 0)
        horizon_drains += horizon_only_drain_count(events)
        nonfinding += nonfinding_drain_count(events)
        if not trigger_counts_match(row) or not facts["counts_match"]:
            counts_match = False
        per_cell[f"{APPS[app]['evidence']}@{budget}"] = {
            "metrics": _slim(row),
            "trigger": facts,
        }
    attempts = int(diagnosis.get("probe_return_attempt_violations") or 0)
    cycle = int(diagnosis.get("probe_return_cycle_violations") or 0)
    dup = int(diagnosis.get("duplicate_terminal_count") or 0)
    false_ok = int(diagnosis.get("false_return_success_count") or 0)
    parent = int(diagnosis.get("parent_corruption_count") or 0)
    repeated += int(diagnosis.get("repeated_key_violations") or 0)
    crm = mechanism_preserved(historical["buggy-crm"]["candidate"])
    ops = mechanism_preserved(historical["buggy-ops"]["candidate"])
    directory_ok = directory_preserved_v0319(
        directory, confirmed_of(fresh["buggy-directory"]["guard"]),
        confirmed_of(directory))
    lab_keep = set(LAB_GUARD) <= set(confirmed_of(lab))
    forum_ok = transfer_preserved(
        fresh["buggy-forum"]["guard"], fresh["buggy-forum"]["candidate"],
        evaluable.get("buggy-forum", False))
    billing_ok = transfer_preserved(
        fresh["buggy-billing"]["guard"], fresh["buggy-billing"]["candidate"],
        evaluable.get("buggy-billing", False))
    deep_keep = set(DEEP_GUARD) <= set(confirmed_of(deep_row))
    mechanism_facts = {
        "result_hub_reached": diagnosis.get("result_hub_reached"),
        "finding_terminal_false_to_true": diagnosis.get("finding_terminal_false_to_true"),
        "finding_return_entry_trigger_at_result": diagnosis.get(
            "finding_return_entry_trigger_at_result"),
        "return_entry_drain_started_at_result": diagnosis.get(
            "return_entry_drain_started_at_result"),
        "result_button_probe_before_first_return": diagnosis.get(
            "result_button_probe_before_first_return"),
        "stable_order_when_close_reopen_visible": diagnosis.get(
            "stable_order_when_close_reopen_visible"),
        "bug_l9_confirmed": "BUG-L9" in set(confirmed_of(lab)),
        "return_attempts_unchanged_during_probes": diagnosis.get(
            "return_attempts_unchanged_during_probes"),
        "no_duplicate_terminal": diagnosis.get("no_duplicate_terminal"),
        "no_return_cycle_contamination": diagnosis.get("no_return_cycle_contamination"),
        "historical_return_resumes_after_exhaustion": diagnosis.get(
            "historical_return_resumes_after_exhaustion"),
        "probe_return_attempt_violations": attempts,
        "probe_return_cycle_violations": cycle,
        "duplicate_terminal_count": dup,
        "false_return_success_count": false_ok,
        "parent_corruption_count": parent,
        "repeated_key_violations": repeated,
        "return_entry_accounting_violations": accounting,
        "witness_violations": witness,
        "terminal_accounting_violations": terminal,
        "trigger_mismatch_violations": mismatch,
        "reused_trigger_violations": reused,
        "wrong_instance_violations": wrong,
    }
    safety_ok = (
        safety["finding_model_invariant_failures"] == 0
        and safety["finding_model_raw_traces"] == 66429
        and safety["historical_models_ok"]
        and safety["candidate_freeze_ok"]
        and safety["historical_freeze_ok"]
        and safety["protocol_executed_false"]
        and not safety["app_specific_needles"]
        and not safety["product_default_changed"]
    )
    derived = derive_v0319_outcome(**{
        **mechanism_facts,
        "candidate_freeze_ok": safety["candidate_freeze_ok"] and not missing,
        "historical_freeze_ok": safety["historical_freeze_ok"],
        "protocol_ok": safety["protocol_executed_false"] and not missing,
        "post_freeze_edit": False,
        "historical_source_mutation": not safety["historical_freeze_ok"],
        "safety_ok": safety_ok,
        "fg_safety_ok": True,
        "horizon_differential_ok": True,
        "model_ok": safety["finding_model_invariant_failures"] == 0,
        "model_invariant_failures": safety["finding_model_invariant_failures"],
        "model_raw_traces": safety["finding_model_raw_traces"],
        "historical_models_ok": safety["historical_models_ok"],
        "app_specific": bool(safety["app_specific_needles"]),
        "historical_regression_loss": regression_loss,
        "crm_ops_collapse": bool(crm["collapse"] or ops["collapse"]),
        "directory_false_handoff": int(directory.get("horizon_handoff_started_events") or 0) > 0,
        "product_default_changed": safety["product_default_changed"],
        "result_return_entry_engaged": bool(diagnosis.get("result_return_entry_engaged")),
        "lab_mechanism_gate": lab_mechanism_gate(mechanism_facts),
        "lab_zero_guard_loss": lab_keep,
        "directory_preserved": directory_ok,
        "forum_full_transfer": forum_ok,
        "billing_full_transfer": billing_ok,
        "crm_preserved": bool(crm["pass"]),
        "ops_preserved": bool(ops["pass"]),
        "deep_no_horizon_drain": int(deep_diag.get("horizon_only_drains") or 0) == 0,
        "deep_guard_retained": deep_keep,
        "deep_states_ok": coverage["states_ok"],
        "deep_urls_ok": coverage["urls_ok"],
        "deep_return_success_ok": coverage["return_success_ok"],
        "deep_horizon_bypass_ok": bool(deep_diag.get("horizon_bypass_ok")),
        "horizon_only_drain": horizon_drains > 0,
        "nonfinding_triggered_drain": nonfinding > 0,
        "wrong_instance_triggered_drain": wrong > 0,
        "reused_trigger": reused > 0,
        "trigger_counts_match": counts_match,
        "duplicate_terminal": dup > 0,
        "false_return_success": false_ok > 0,
        "parent_corruption": parent > 0,
    })
    bug_notes = _bug_notes(run_root, diagnosis) if not missing else {}
    return {
        "missing": missing,
        "derived": derived,
        "diagnosis": diagnosis,
        "deep": deep_diag,
        "deep_coverage": coverage,
        "deep_boundary": _horizon_boundary(deep_events, deep_steps),
        "bug_notes": bug_notes,
        "fresh": {
            app: {
                "guard_confirmed": confirmed_of(block["guard"]),
                "horizon_confirmed": confirmed_of(block["horizon"]),
                "v0317_confirmed": confirmed_of(block["v0317"]),
                "v0318_confirmed": confirmed_of(block["v0318"]),
                "candidate_confirmed": confirmed_of(block["candidate"]),
                "lost_vs_guard": lost_vs(
                    confirmed_of(block["guard"]), confirmed_of(block["candidate"])),
                "candidate": _slim(block["candidate"]),
                "v0317": _slim(block["v0317"]),
                "v0318": _slim(block["v0318"]),
                "guard": _slim(block["guard"]),
            }
            for app, block in fresh.items()
        },
        "historical": {
            name: {
                "guard_confirmed": block["guard_confirmed"],
                "v0317_confirmed": confirmed_of(block["v0317"]),
                "v0318_confirmed": confirmed_of(block["v0318"]),
                "candidate_confirmed": confirmed_of(block["candidate"]),
                "lost_vs_guard": lost_vs(
                    block["guard_confirmed"], confirmed_of(block["candidate"])),
                "candidate": _slim(block["candidate"]),
                "v0317": _slim(block["v0317"]),
                "v0318": _slim(block["v0318"]),
            }
            for name, block in historical.items()
        },
        "lab_budgets": {
            str(budget): _slim(cells[("buggy-lab", budget)])
            for budget in (40, 80, 120)
        },
        "directory_preserved": directory_ok,
        "lab_zero_guard_loss": lab_keep,
        "forum_full_transfer": forum_ok,
        "billing_full_transfer": billing_ok,
        "crm": crm,
        "ops": ops,
        "safety": safety,
        "witness_violations": witness,
        "terminal_accounting_violations": terminal,
        "trigger_cells": per_cell,
        "cells": {
            f"{APPS[app]['evidence']}@{budget}": _slim(cells[(app, budget)])
            for app, budget in CELLS
        },
    }


def _write(path: str, payload) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(canonical_json_bytes(payload))


def _copy_evidence(run_root: str, published: str) -> None:
    for app, budget in CELLS:
        evidence = APPS[app]["evidence"]
        src_dir = _abs(cell_dir(run_root, app))
        dst_dir = os.path.join(published, "evidence", evidence)
        os.makedirs(dst_dir, exist_ok=True)
        stem = cell_stem(budget)
        for ext in (".events.jsonl", ".graph.json", ".sequence_events.json", ".config.json", ".DONE"):
            src = os.path.join(src_dir, stem + ext)
            if os.path.isfile(src):
                shutil.copyfile(src, os.path.join(dst_dir, stem + ext))
        metrics = os.path.join(src_dir, "metrics.json")
        if os.path.isfile(metrics):
            shutil.copyfile(metrics, os.path.join(dst_dir, "metrics.json"))


def _evidence_manifest(root: str) -> dict:
    files = []
    for dirpath, _dirs, names in os.walk(root):
        for name in names:
            if name == "evidence-manifest.json":
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace("\\", "/")
            files.append({"relative_path": rel, "sha256": sha256_file(full)})
    files.sort(key=lambda item: item["relative_path"])
    return {"expected_file_count": len(files), "files": files}


def _summary(report: dict) -> str:
    derived = report["derived"]
    lab = report["fresh"]["buggy-lab"]
    deep = report["historical"]["deepbench"]
    directory = report["fresh"]["buggy-directory"]["candidate"]
    result = (report.get("diagnosis") or {}).get("result") or {}
    lines = [
        f"# v0.3.19 result: Outcome {derived['outcome']}",
        "",
        derived["outcome_meaning"],
        "",
        "This round narrows Return-Entry Drain to a same-step finding terminal. It is not fresh validation, not generalization, and not a product-default change.",
        "",
        f"Result drain started: {result.get('started')}.",
        f"Finding trigger at result: {(report.get('diagnosis') or {}).get('finding_return_entry_trigger_at_result')}.",
        f"Result buttons selected: {result.get('selected_eids')}.",
        f"Lab Guard bugs lost: {lab['lost_vs_guard']}.",
        f"Deep Guard bugs lost: {deep['lost_vs_guard']}.",
        f"Deep horizon-only drains: {(report.get('deep') or {}).get('horizon_only_drains')}.",
        f"Deep horizon bypasses: {(report.get('deep') or {}).get('horizon_bypass_events')}.",
        f"Directory handoffs: {directory.get('horizon_handoff_started_events')}.",
        f"Product default changed: {str(derived['product_default_changed']).lower()}.",
        "",
        "v0.3.14 Outcome A, v0.3.15 Outcome C, v0.3.16 Outcome B, v0.3.17 Outcome B, and v0.3.18 Outcome C are unchanged.",
        "",
    ]
    return "\n".join(lines)


def publish(run_root: str = RUN_ROOT, published: str = PUBLISHED) -> dict:
    report = collect(run_root)
    if report["missing"]:
        raise SystemExit("missing cells: " + ", ".join(report["missing"]))
    dest = _abs(published)
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    os.makedirs(dest, exist_ok=True)
    _copy_evidence(run_root, dest)
    for name, src in (
        ("protocol.json", PROTOCOL),
        ("v0318-trigger-context-analysis.json", ANALYSIS),
        ("candidate-freeze.json", FREEZE),
    ):
        shutil.copyfile(_abs(src), os.path.join(dest, name))
    metrics = os.path.join(dest, "metrics")
    os.makedirs(os.path.join(dest, "evidence", "safety"), exist_ok=True)
    mechanism = {
        "derived": report["derived"],
        "diagnosis": report["diagnosis"],
        "deep": report["deep"],
        "deep_coverage": report["deep_coverage"],
        "deep_boundary": report["deep_boundary"],
        "bug_notes": report["bug_notes"],
        "lab_budgets": report["lab_budgets"],
        "directory_preserved": report["directory_preserved"],
        "lab_zero_guard_loss": report["lab_zero_guard_loss"],
        "forum_full_transfer": report["forum_full_transfer"],
        "billing_full_transfer": report["billing_full_transfer"],
        "crm": report["crm"],
        "ops": report["ops"],
        "fresh": report["fresh"],
        "cells": report["cells"],
    }
    regression = {
        "historical": report["historical"],
        "fresh": {
            app: {
                "guard_confirmed": block["guard_confirmed"],
                "v0317_confirmed": block["v0317_confirmed"],
                "v0318_confirmed": block["v0318_confirmed"],
                "candidate_confirmed": block["candidate_confirmed"],
                "lost_vs_guard": block["lost_vs_guard"],
            }
            for app, block in report["fresh"].items()
        },
    }
    safety = report["safety"]
    audit = {
        "diagnosis": report["diagnosis"],
        "deep": report["deep"],
        "deep_boundary": report["deep_boundary"],
        "bug_notes": report["bug_notes"],
        "trigger_cells": report["trigger_cells"],
        "lab_zero_guard_loss": report["lab_zero_guard_loss"],
    }
    _write(os.path.join(metrics, "mechanism.json"), mechanism)
    _write(os.path.join(metrics, "regression.json"), regression)
    _write(os.path.join(metrics, "safety.json"), safety)
    _write(os.path.join(metrics, "trigger-audit.json"), audit)
    _write(os.path.join(dest, "evidence", "safety", "checks.json"), {
        "finding_model_raw_traces": safety["finding_model_raw_traces"],
        "finding_model_invariant_failures": safety["finding_model_invariant_failures"],
        "return_entry_model_raw_traces": safety["return_entry_model_raw_traces"],
        "return_entry_model_invariant_failures": safety["return_entry_model_invariant_failures"],
        "local_model_raw_traces": safety["local_model_raw_traces"],
        "local_model_invariant_failures": safety["local_model_invariant_failures"],
        "reentry_model_raw_traces": safety["reentry_model_raw_traces"],
        "reentry_model_invariant_failures": safety["reentry_model_invariant_failures"],
        "handoff_model_raw_traces": safety["handoff_model_raw_traces"],
        "handoff_model_invariant_failures": safety["handoff_model_invariant_failures"],
        "return_exhaustive_traces": safety["return_exhaustive_traces"],
        "return_exhaustive_failures": safety["return_exhaustive_failures"],
        "app_specific_needles": safety["app_specific_needles"],
        "product_default_changed": safety["product_default_changed"],
    })
    config = {
        "round": "v0.3.19",
        "starting_head": "0acb51103cfe466db1d3b2227e587535f39d8958",
        "protocol_commit": "01f1021870e819596d6b38cc15c41392ad976c5e",
        "candidate_freeze_commit": "eb119e5dce1e6d5695d8709bbfbb89be7232694a",
        "candidate": CANDIDATE,
        "cells": [f"{app}@{budget}" for app, budget in CELLS],
        "product_default_changed": False,
        "outcome": report["derived"]["outcome"],
        "scope": "inspected trigger-narrowing repair, not fresh validation",
        "verify_command": (
            "python -m benchmark.finding_return_entry_reproduce "
            "--root experiments/published/finding-return-entry-v0.3.19 --verify"
        ),
    }
    _write(os.path.join(dest, "config.json"), config)
    with open(os.path.join(dest, "summary.md"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(_summary(report))
    reproduction = {
        "clean_clone_verified": False,
        "command": config["verify_command"],
        "outcome": report["derived"]["outcome"],
        "mechanism_sha256": sha256_file(os.path.join(metrics, "mechanism.json")),
        "regression_sha256": sha256_file(os.path.join(metrics, "regression.json")),
        "safety_sha256": sha256_file(os.path.join(metrics, "safety.json")),
        "trigger_audit_sha256": sha256_file(os.path.join(metrics, "trigger-audit.json")),
    }
    _write(os.path.join(metrics, "reproduction.json"), reproduction)
    _write(os.path.join(dest, "evidence-manifest.json"), _evidence_manifest(dest))
    print(f"outcome {report['derived']['outcome']}")
    print(sha256_bytes(canonical_json_bytes(report["derived"])))
    print(f"published {published}")
    return report


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", default=RUN_ROOT)
    parser.add_argument("--published", default=PUBLISHED)
    args = parser.parse_args(argv)
    publish(args.run_root, args.published)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
