"""Publish v0.3.14 evidence. Numbers come from traces and the frozen gate."""
from __future__ import annotations

import json
import os
import re
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
from benchmark.horizon_handoff_analysis import (
    GUARD_CONFIRMED, derive_v0314_outcome, mechanism_repair,
)
from benchmark.horizon_handoff_modelcheck import RAW_TRACE_COUNT, enumerate_traces
from benchmark.nested_hub_detector import count_events, detect_nested_hub_preemptions
from benchmark.nested_stack_analysis import app_specific_needles
from benchmark.nested_stack_regression import (
    _action_view, _align_key, _bug_index, _first_match, _pair, _urls,
)
from benchmark.return_cycle_guard_reproduce import verify_candidate_identity
from benchmark.return_cycle_modelcheck import run_exhaustive_check
from benchmark.return_cycle_safety import collect_safety_suite
from ghostqa.exploration.horizon_handoff_guard import terminal_violations
from ghostqa.exploration.policy import GhostPolicy

PUBLISHED_ROOT = os.path.join("experiments", "published", "horizon-handoff-v0.3.14")
RUN_ROOT = os.path.join("experiments", "runs", "v0314-horizon")
CANDIDATE_FREEZE = os.path.join(
    "experiments", "frozen", "ghost-horizon-handoff-v0.3.14", "freeze.json")
FLAT_FREEZE = os.path.join(
    "experiments", "frozen", "ghost-nested-hub-guard-v0.3.12", "freeze.json")
STACK_FREEZE = os.path.join(
    "experiments", "frozen", "ghost-nested-stack-guard-v0.3.13", "freeze.json")
PROTOCOL = os.path.join("experiments", "validation", "v0.3.14", "protocol.json")
REAUDIT = os.path.join(
    "experiments", "validation", "v0.3.14", "v0313-restore-reaudit.json")
HAND = "ghost-structural-horizon-handoff-guard"
GUARD = "ghost-structural-return-guard"
FLAT = "ghost-structural-nested-return-guard"
STACK = "ghost-structural-nested-stack-guard"
PRIMARY = 120
TARGET_FREEZES = {
    "buggy-crm": "experiments/frozen/v0.3.11-multitarget/buggy-crm/freeze.json",
    "buggy-ops": "experiments/frozen/v0.3.11-multitarget/buggy-ops/freeze.json",
    "buggy-wiki": "experiments/frozen/v0.3.11-multitarget/buggy-wiki/freeze.json",
    "buggy-desk": "experiments/frozen/buggy-desk-v0.3.10/freeze.json",
}
RUN_APP = {
    "buggy-crm": "buggy-crm",
    "buggy-ops": "buggy-ops",
    "buggy-desk": "buggy-desk",
    "deepbench": "buggy-flow",
    "wiki": "buggy-wiki",
    "buggy-shop": "buggy-shop",
}
BUDGETS = {
    "buggy-crm": (40, 80, 120),
    "buggy-ops": (40, 80, 120),
    "buggy-desk": (120,),
    "deepbench": (120,),
    "wiki": (120,),
    "buggy-shop": (120,),
}
HISTORY = {
    "buggy-crm": {
        "guard": "experiments/published/multi-target-replication-v0.3.11/evidence/buggy-crm/metrics.json",
        "flatten": "experiments/published/nested-hub-parent-v0.3.12/evidence/buggy-crm/metrics.json",
        "stack": "experiments/published/nested-stack-v0.3.13/evidence/buggy-crm/metrics.json",
    },
    "buggy-ops": {
        "guard": "experiments/published/multi-target-replication-v0.3.11/evidence/buggy-ops/metrics.json",
        "flatten": "experiments/published/nested-hub-parent-v0.3.12/evidence/buggy-ops/metrics.json",
        "stack": "experiments/published/nested-stack-v0.3.13/evidence/buggy-ops/metrics.json",
    },
    "buggy-desk": {
        "guard": "experiments/published/fresh-transfer-v0.3.10/evidence/buggy-desk/metrics.json",
        "flatten": "experiments/published/nested-hub-parent-v0.3.12/evidence/regression/buggy-desk/metrics.json",
        "stack": "experiments/published/nested-stack-v0.3.13/evidence/buggy-desk/metrics.json",
        "guard_events": "experiments/published/fresh-transfer-v0.3.10/evidence/buggy-desk/ghost-structural-return-guard_b120_s1.events.jsonl",
        "manifest": "apps/buggy-desk/bugs.manifest.json",
    },
    "deepbench": {
        "guard": "experiments/published/return-cycle-guard-v0.3.9/evidence/deepbench/metrics.json",
        "flatten": "experiments/published/nested-hub-parent-v0.3.12/evidence/regression/deepbench/metrics.json",
        "stack": "experiments/published/nested-stack-v0.3.13/evidence/deepbench/metrics.json",
        "manifest": "apps/buggy-flow/bugs.manifest.json",
    },
    "wiki": {
        "guard": "experiments/published/multi-target-replication-v0.3.11/evidence/buggy-wiki/metrics.json",
        "flatten": "experiments/published/nested-hub-parent-v0.3.12/evidence/regression/buggy-wiki/metrics.json",
        "stack": "experiments/published/nested-stack-v0.3.13/evidence/wiki/metrics.json",
        "manifest": "apps/buggy-wiki/bugs.manifest.json",
    },
    "buggy-shop": {
        "guard": "experiments/published/return-cycle-guard-v0.3.9/evidence/shop/metrics.json",
        "guard_events": "experiments/published/return-cycle-guard-v0.3.9/evidence/shop/ghost-structural-return-guard_b120_s1.events.jsonl",
        "flatten": "experiments/published/nested-hub-parent-v0.3.12/evidence/regression/buggy-shop/metrics.json",
        "stack": "experiments/published/nested-stack-v0.3.13/evidence/buggy-shop/metrics.json",
        "manifest": "apps/buggy-shop/bugs.manifest.json",
    },
}
POLICY_FOR = {"guard": GUARD, "flatten": FLAT, "stack": STACK}
DESK_FOCUS = ("BUG-K1", "BUG-K2", "BUG-K3", "BUG-K6", "BUG-K9", "BUG-K10")


def _write_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(canonical_json_bytes(obj))


def _stem(policy: str, budget: int) -> str:
    return f"{policy}_b{budget}_s1"


def _hist_row(path: str, policy: str, budget: int = PRIMARY) -> dict:
    if not os.path.isfile(path):
        raise SystemExit(f"missing historical metrics {path}")
    data = load_json(path)
    for row in data.get("runs") or []:
        if row.get("policy") == policy and int(row.get("budget") or 0) == budget:
            return row
    raise SystemExit(f"missing {policy}@{budget} in {path}")


def _coverage(row: dict, events_path: str | None = None) -> dict:
    urls = row.get("normalized_unique_urls")
    if urls is None and events_path and os.path.isfile(events_path):
        urls = len(_urls(load_jsonl(events_path)))
    return {
        "states": row.get("states"),
        "normalized_unique_urls": urls,
        "confirmed_bugs": sorted(row.get("confirmed_bugs") or []),
    }


def _load_pair(root: str, folder: str, budget: int):
    base = os.path.join(root, "evidence", folder, _stem(HAND, budget))
    seq_path = base + ".sequence_events.json"
    ev_path = base + ".events.jsonl"
    if not os.path.isfile(seq_path) or not os.path.isfile(ev_path):
        raise SystemExit(f"missing candidate trace {base}")
    return load_json(seq_path), load_jsonl(ev_path)


def _metric_row(root: str, folder: str, budget: int) -> dict:
    path = os.path.join(root, "evidence", folder, "metrics.json")
    data = load_json(path)
    for row in data.get("runs") or []:
        if row.get("policy") == HAND and int(row.get("budget") or 0) == budget:
            return row
    raise SystemExit(f"missing candidate metrics {folder}@{budget}")


def _cell(row: dict, seq: list, steps: list) -> dict:
    pre = detect_nested_hub_preemptions(seq, steps)
    window = sum(1 for item in pre if item.get("commitment_window"))
    audit = audit_trace(seq)
    returned = sum(
        1 for event in seq
        if event.get("event") == "sequence_terminal" and event.get("outcome") == "returned")
    return {
        "policy": HAND,
        "budget": row.get("budget"),
        "states": row.get("states"),
        "normalized_unique_urls": row.get("normalized_unique_urls"),
        "confirmed_bugs": sorted(row.get("confirmed_bugs") or []),
        "sequence_lost_parent": sum(
            1 for event in seq
            if event.get("event") == "sequence_terminal"
            and event.get("outcome") == "lost_parent"),
        "sequence_horizon_reached": count_events(seq, "sequence_horizon_reached"),
        "return_attempt_events": count_events(seq, "return_attempt"),
        "sequence_instances_returned": returned,
        "return_cycle_escape_events": count_events(seq, "return_cycle_escape"),
        "nested_continuation_events": count_events(seq, "nested_continuation"),
        "unique_nested_continuations": len({
            event.get("nested_branch")
            for event in seq
            if event.get("event") == "nested_continuation" and event.get("nested_branch")
        }),
        "horizon_handoff_started_events": count_events(seq, "horizon_handoff_started"),
        "handoff_child_started_events": sum(
            1 for event in seq
            if event.get("event") == "horizon_handoff_started"
            and event.get("child_sequence_instance_id")),
        "child_parent_witness_events": count_events(seq, "child_parent_witness"),
        "child_parent_exact_witness_events": sum(
            1 for event in seq
            if event.get("event") == "child_parent_witness"
            and event.get("witness_strength") == "exact"),
        "child_parent_cluster_witness_events": sum(
            1 for event in seq
            if event.get("event") == "child_parent_witness"
            and event.get("witness_strength") == "cluster"),
        "same_step_terminal_witness_events": sum(
            1 for event in seq
            if event.get("event") == "child_parent_witness"
            and event.get("terminal_context") in (
                "returned", "finding_same_step", "crash_same_step")),
        "witness_rejection_events": count_events(seq, "witness_rejection"),
        "parent_frame_resume_to_return_events": count_events(
            seq, "parent_frame_resume_to_return"),
        "horizon_handoff_unwind_events": count_events(seq, "horizon_handoff_unwind"),
        "max_handoff_stack_depth": _max_depth(seq),
        "handoff_stack_depth_at_budget_end": _budget_depth(seq),
        "handoff_frames_abandoned": sum(
            1 for event in seq
            if event.get("event") == "sequence_terminal"
            and event.get("outcome") == "horizon_handoff_abandoned"),
        "deferred_horizon_events": sum(
            1 for event in seq
            if event.get("event") == "horizon_handoff_started"
            and event.get("deferred_horizon") is True),
        "resolved_deferred_horizon_events": sum(
            1 for event in seq
            if event.get("event") == "sequence_horizon_reached"
            and event.get("reason") == "horizon_handoff_resolved"),
        "witness_violations": audit["witness_violations"],
        "terminal_accounting_violations": len(terminal_violations(seq)),
        "return_inflation": audit["return_inflation"],
        "wrong_child_or_parent_resume": audit["wrong_child_or_parent_resume"],
        "commitment_window_preemptions": window,
        "active_budget_end_count": row.get("active_budget_end_count"),
        "suspended_budget_end_count": row.get("suspended_budget_end_count"),
    }


def _max_depth(seq: list) -> int:
    depths = [0]
    for event in seq:
        if event.get("event") == "horizon_handoff_started":
            depths.append(int(event.get("stack_depth") or 0))
        if event.get("stack_depth_before_pop") is not None:
            depths.append(int(event.get("stack_depth_before_pop") or 0))
        if event.get("stack_depth_before") is not None:
            depths.append(int(event.get("stack_depth_before") or 0))
    return max(depths)


def _budget_depth(seq: list) -> int:
    for event in seq:
        if event.get("event") == "sequence_terminal" and event.get("outcome") == "budget_end":
            if event.get("stack_depth_at_budget_end") is not None:
                return int(event.get("stack_depth_at_budget_end") or 0)
    return 0


def audit_trace(seq: list) -> dict:
    """Offline witness and terminal-inflation check. Does not choose actions."""
    violations = []
    resumes = []
    witnesses_by_step = {}
    for index, event in enumerate(seq or []):
        if event.get("event") == "child_parent_witness":
            witnesses_by_step.setdefault(event.get("step"), []).append((index, event))
            strength = event.get("witness_strength")
            if strength not in ("exact", "cluster"):
                violations.append({"index": index, "reason": "witness_strength"})
            if event.get("terminal_context") == "none":
                violations.append({"index": index, "reason": "terminal_context_none"})
        elif event.get("event") == "parent_frame_resume_to_return":
            resumes.append((index, event))
    for index, event in resumes:
        step = event.get("step")
        prior = [
            item for item_index, item in witnesses_by_step.get(step, [])
            if item_index < index
        ]
        if not prior:
            violations.append({"index": index, "reason": "resume_without_witness", "step": step})
        if event.get("returning") is not True or event.get("commitment_left") != 0:
            violations.append({"index": index, "reason": "resume_not_return_phase", "step": step})
        if any(item.get("event") == "return_cycle_escape" and item.get("step") == step
               for item in seq):
            violations.append({"index": index, "reason": "escape_same_step", "step": step})
    for index, event in resumes:
        outer = event.get("resumed_sequence_instance_id")
        frame = None
        for prior_index, prior in enumerate(seq or []):
            if prior_index >= index:
                break
            if (prior.get("event") == "horizon_handoff_started"
                    and prior.get("suspended_sequence_instance_id") == outer):
                frame = prior
        if frame is None:
            violations.append({
                "step": event.get("step"),
                "reason": "resume_without_handoff_frame",
                "sequence_instance_id": outer,
            })
            continue
        if event.get("original_parent_hub_sig") != frame.get("suspended_parent_hub_sig"):
            violations.append({
                "step": event.get("step"),
                "reason": "wrong_parent_resume",
                "sequence_instance_id": outer,
            })
        if event.get("resumed_branch") != frame.get("suspended_branch"):
            violations.append({
                "step": event.get("step"),
                "reason": "wrong_child_resume",
                "sequence_instance_id": outer,
            })
    per_instance = {}
    inflation = []
    for event in seq or []:
        if event.get("event") != "sequence_terminal":
            continue
        iid = event.get("sequence_instance_id")
        per_instance.setdefault(iid, []).append(event.get("outcome") or "")
    for iid, outcomes in per_instance.items():
        if outcomes.count("returned") > 1:
            inflation.append({"id": iid, "reason": "duplicate_returned"})
        if "returned" in outcomes and "return_cycle_abandoned" in outcomes:
            inflation.append({"id": iid, "reason": "returned_and_abandoned"})
        if "returned" in outcomes and "horizon_handoff_abandoned" in outcomes:
            inflation.append({"id": iid, "reason": "returned_and_unwound"})
    wrong = any(item.get("reason") in ("wrong_parent_resume", "wrong_child_resume", "resume_without_witness")
                for item in violations)
    return {
        "witness_violations": len(violations),
        "violations": violations,
        "return_inflation": bool(inflation),
        "inflation": inflation,
        "wrong_child_or_parent_resume": wrong,
        "terminal_accounting_violations": len(terminal_violations(seq)),
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
        "candidate_action": _action_view(other_rows[prefix]["step"]),
    }


def _pytest_result(args: list) -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=no", *args],
        capture_output=True, text=True)
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    failed = 0
    passed = 0
    failed_match = re.search(r"(\d+) failed", text)
    passed_match = re.search(r"(\d+) passed", text)
    if failed_match:
        failed = int(failed_match.group(1))
    if passed_match:
        passed = int(passed_match.group(1))
    if proc.returncode != 0 and failed == 0:
        failed = 1
    return {"passed": passed, "failed": failed, "returncode": proc.returncode}


def build_safety() -> dict:
    h_tests = _pytest_result([
        "tests/test_horizon_handoff_guard.py", "-k", "test_h and not source",
    ])
    model = enumerate_traces()
    suite = collect_safety_suite()
    exhaustive = run_exhaustive_check()
    n_tests = _pytest_result([
        "tests/test_nested_hub_guard.py", "-k", " or ".join(
            f"test_n{i}_" for i in range(1, 13)),
    ])
    p_tests = _pytest_result([
        "tests/test_nested_stack_guard.py", "-k", " or ".join(
            f"test_p{i}_" for i in range(1, 16)),
    ])
    s_fail = sum(1 for row in suite.get("rows") or [] if not row.get("pass"))
    default = GhostPolicy(llm=None, use_frontier=False)
    product_changed = not (
        default.name == "ghost"
        and default.use_frontier is False
        and default.sequence_mode == "off")
    needles = app_specific_needles(os.path.join(
        "ghostqa", "exploration", "horizon_handoff_guard.py"))
    historical = []
    if verify_freeze(DEFAULT_FREEZE):
        historical.append("c1")
    if verify_candidate_identity():
        historical.append("v0.3.9-guard")
    if verify_freeze(FLAT_FREEZE):
        historical.append("v0.3.12-candidate")
    if verify_freeze(STACK_FREEZE):
        historical.append("v0.3.13-candidate")
    for name, path in TARGET_FREEZES.items():
        if verify_freeze(path):
            historical.append(name)
    candidate_ok = verify_freeze(CANDIDATE_FREEZE) == []
    regressed = bool(
        s_fail or n_tests["failed"] or p_tests["failed"]
        or int(exhaustive.get("failures") or 0)
        or int(exhaustive.get("traces_enumerated") or 0) < 5800)
    return {
        "h_series_cases": h_tests["passed"] + h_tests["failed"],
        "h_series_failures": h_tests["failed"],
        "model_raw_traces": int(model.get("raw_traces") or 0),
        "model_valid_traces": int(model.get("valid_traces") or 0),
        "model_rejected_traces": int(model.get("rejected_traces") or 0),
        "model_invariant_failures": int(model.get("invariant_failures") or 0),
        "model_raw_expected": RAW_TRACE_COUNT,
        "s1_s7_cases": len(suite.get("rows") or []),
        "s1_s7_failures": s_fail,
        "s1_s7_all_pass": bool(suite.get("all_pass")),
        "exhaustive_traces": int(exhaustive.get("traces_enumerated") or 0),
        "exhaustive_failures": int(exhaustive.get("failures") or 0),
        "n_series_cases": n_tests["passed"] + n_tests["failed"],
        "n_series_failures": n_tests["failed"],
        "p_series_cases": p_tests["passed"] + p_tests["failed"],
        "p_series_failures": p_tests["failed"],
        "app_specific_needles": needles,
        "app_specific_logic": bool(needles),
        "product_default_changed": product_changed,
        "historical_freeze_failures": historical,
        "candidate_freeze_ok": candidate_ok,
        "historical_freezes_ok": not historical,
        "historical_safety_regressed": regressed,
        "post_freeze_semantic_tuning": not candidate_ok,
    }


def build_mechanism(root: str, safety: dict) -> dict:
    targets = {}
    witness_total = 0
    terminal_total = 0
    inflation = False
    wrong = False
    for app in ("buggy-crm", "buggy-ops", "buggy-desk", "deepbench", "wiki", "buggy-shop"):
        cells = {}
        audits = []
        for budget in BUDGETS[app]:
            row = _metric_row(root, app, budget)
            seq, steps = _load_pair(root, app, budget)
            view = _cell(row, seq, steps)
            cells[f"{HAND}@{budget}"] = view
            audits.append(audit_trace(seq))
            witness_total += view["witness_violations"]
            terminal_total += view["terminal_accounting_violations"]
            inflation = inflation or view["return_inflation"]
            wrong = wrong or view["wrong_child_or_parent_resume"]
        history = {}
        for label in ("guard", "flatten", "stack"):
            events_path = HISTORY[app].get(f"{label}_events")
            history[label] = _coverage(
                _hist_row(HISTORY[app][label], POLICY_FOR[label]), events_path)
        block = {"cells": cells, "history_120": history, "audits": [
            {"witness_violations": item["witness_violations"],
             "return_inflation": item["return_inflation"],
             "wrong_child_or_parent_resume": item["wrong_child_or_parent_resume"],
             "examples": (item["violations"] or [])[:8]}
            for item in audits
        ]}
        if app in ("buggy-crm", "buggy-ops"):
            guard = history["guard"]
            candidate = cells[f"{HAND}@{PRIMARY}"]
            repair = mechanism_repair(candidate, guard)
            block["assessment_120"] = repair
        targets[app] = block
    confirmed = {}
    for app in ("buggy-desk", "deepbench", "wiki", "buggy-shop"):
        confirmed[app] = targets[app]["cells"][f"{HAND}@{PRIMARY}"]["confirmed_bugs"]
    reference = {}
    for app in confirmed:
        loaded = targets[app]["history_120"]["guard"]["confirmed_bugs"]
        reference[app] = loaded
        expected = sorted(GUARD_CONFIRMED[app])
        if loaded != expected:
            raise SystemExit(
                f"{app} guard confirmed {loaded} != preregistered {expected}")
    derived = derive_v0314_outcome(
        candidate_freeze_ok=bool(safety.get("candidate_freeze_ok")),
        historical_freezes_ok=bool(safety.get("historical_freezes_ok")),
        h_series_failures=int(safety.get("h_series_failures") or 0),
        model_invariant_failures=int(safety.get("model_invariant_failures") or 0),
        historical_safety_regressed=bool(safety.get("historical_safety_regressed")),
        witness_violations=witness_total,
        terminal_accounting_violations=terminal_total,
        return_inflation=inflation,
        wrong_child_or_parent_resume=wrong,
        app_specific_logic=bool(safety.get("app_specific_logic")),
        product_default_changed=bool(safety.get("product_default_changed")),
        post_freeze_semantic_tuning=bool(safety.get("post_freeze_semantic_tuning")),
        crm_repair=bool((targets["buggy-crm"].get("assessment_120") or {}).get("pass")),
        ops_repair=bool((targets["buggy-ops"].get("assessment_120") or {}).get("pass")),
        confirmed=confirmed,
    )
    return {
        "targets": targets,
        "witness_violations": witness_total,
        "terminal_accounting_violations": terminal_total,
        "return_inflation": inflation,
        "wrong_child_or_parent_resume": wrong,
        "reference_confirmed": reference,
        "derived": derived,
    }


def build_regression(root: str, mechanism: dict) -> dict:
    cases = {}
    for app in ("buggy-desk", "deepbench", "wiki", "buggy-shop"):
        block = mechanism["targets"][app]
        cell = block["cells"][f"{HAND}@{PRIMARY}"]
        history = block["history_120"]
        ref = history["guard"]["confirmed_bugs"]
        flat = history["flatten"]["confirmed_bugs"]
        stack = history["stack"]["confirmed_bugs"]
        got = cell["confirmed_bugs"]
        lost = sorted(set(ref) - set(got))
        seq, events = _load_pair(root, app, PRIMARY)
        case = {
            "app": app,
            "reference_confirmed": ref,
            "v0_3_12_confirmed": flat,
            "v0_3_13_confirmed": stack,
            "candidate_confirmed": got,
            "lost_vs_guard": lost,
            "states": cell["states"],
            "normalized_unique_urls": cell["normalized_unique_urls"],
            "guard_states": history["guard"]["states"],
            "guard_urls": history["guard"]["normalized_unique_urls"],
            "flatten_states": history["flatten"]["states"],
            "flatten_urls": history["flatten"]["normalized_unique_urls"],
            "stack_states": history["stack"]["states"],
            "stack_urls": history["stack"]["normalized_unique_urls"],
            "nested_continuation_events": cell["nested_continuation_events"],
            "horizon_handoff_started_events": cell["horizon_handoff_started_events"],
            "child_parent_witness_events": cell["child_parent_witness_events"],
            "child_parent_exact_witness_events": cell["child_parent_exact_witness_events"],
            "child_parent_cluster_witness_events": cell["child_parent_cluster_witness_events"],
            "same_step_terminal_witness_events": cell["same_step_terminal_witness_events"],
            "parent_frame_resume_to_return_events": cell["parent_frame_resume_to_return_events"],
            "horizon_handoff_unwind_events": cell["horizon_handoff_unwind_events"],
            "max_handoff_stack_depth": cell["max_handoff_stack_depth"],
            "sequence_horizon_reached": cell["sequence_horizon_reached"],
            "return_attempt_events": cell["return_attempt_events"],
            "sequence_instances_returned": cell["sequence_instances_returned"],
            "return_cycle_escape_events": cell["return_cycle_escape_events"],
            "witness_violations": cell["witness_violations"],
            "terminal_accounting_violations": cell["terminal_accounting_violations"],
        }
        manifest = HISTORY[app].get("manifest")
        if manifest:
            case["bug_first_steps"] = _bug_steps(events, manifest, ref)
        if app == "buggy-desk" and os.path.isfile(HISTORY[app]["guard_events"]):
            ref_events = load_jsonl(HISTORY[app]["guard_events"])
            case["divergence_from_guard"] = _divergence(ref_events, events)
            case["focus_bug_first_steps"] = _bug_steps(events, manifest, list(DESK_FOCUS))
            ref_urls = set(_urls(ref_events))
            cand_urls = set(_urls(events))
            case["reference_only_urls"] = sorted(ref_urls - cand_urls)
            case["candidate_only_urls"] = sorted(cand_urls - ref_urls)
        if app == "deepbench":
            case["guard_events_available"] = False
            case["d12_confirmed"] = "BUG-D12" in got
            case["member_workflow_note"] = (
                "DeepBench guard reference is the committed v0.3.9 metrics file. "
                "That publication has no event trace. D12 is reported from the "
                "candidate confirmed set and its first matching step.")
        cases[app] = case
    return {"cases": cases}


def build_witness_audit(root: str) -> dict:
    apps = {}
    total = 0
    for app, budgets in BUDGETS.items():
        rows = []
        for budget in budgets:
            seq, _steps = _load_pair(root, app, budget)
            audit = audit_trace(seq)
            audit["budget"] = budget
            audit["violations"] = (audit["violations"] or [])[:12]
            total += audit["witness_violations"]
            rows.append(audit)
        apps[app] = rows
    return {"witness_violations": total, "apps": apps}


def stage_evidence(run_root: str, out_root: str) -> None:
    for app, run_app in RUN_APP.items():
        src = os.path.join(run_root, "evidence", run_app)
        dst = os.path.join(out_root, "evidence", app)
        os.makedirs(dst, exist_ok=True)
        kept = []
        metrics = load_json(os.path.join(src, "metrics.json"))
        for budget in BUDGETS[app]:
            stem = _stem(HAND, budget)
            for ext in (".events.jsonl", ".graph.json", ".sequence_events.json"):
                origin = os.path.join(src, stem + ext)
                if not os.path.isfile(origin):
                    raise SystemExit(f"missing run file {origin}")
                shutil.copyfile(origin, os.path.join(dst, stem + ext))
            for row in metrics.get("runs") or []:
                if row.get("policy") == HAND and int(row.get("budget") or 0) == budget:
                    kept.append(row)
        _write_json(os.path.join(dst, "metrics.json"), {"app": app, "runs": kept})


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


def _join(values) -> str:
    return ",".join(values) if values else "—"


def _pair_text(row: dict, states_key="states", urls_key="normalized_unique_urls") -> str:
    states = row.get(states_key)
    urls = row.get(urls_key)
    if states is None and urls is None:
        return "—"
    return f"{states if states is not None else '—'}/{urls if urls is not None else '—'}"


def write_summary(mechanism: dict, regression: dict, safety: dict, reaudit: dict) -> str:
    derived = mechanism["derived"]
    lines = [
        f"# GhostQA v0.3.14 — Outcome {derived['outcome']}",
        "",
        derived["outcome_meaning"],
        "",
        "Inspected mechanism development on buggy-crm and buggy-ops. "
        "Not a fresh-generalization claim. Product default unchanged. "
        "v0.3.11 remains Outcome D. v0.3.12 remains Outcome C. "
        "v0.3.13 remains Outcome C.",
        "",
        "## Mechanism",
        "",
        "| target | G states/URLs | F states/URLs | S states/URLs | H states/URLs | continuations | handoffs | witnesses | resumes | unwinds | max depth | horizon | return | confirmed |",
        "|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    order = ("buggy-crm", "buggy-ops", "buggy-desk", "deepbench", "wiki", "buggy-shop")
    for app in order:
        block = mechanism["targets"][app]
        for budget in BUDGETS[app]:
            cell = block["cells"][f"{HAND}@{budget}"]
            if budget != PRIMARY and app not in ("buggy-crm", "buggy-ops"):
                continue
            hist = block["history_120"]
            label = app if budget == PRIMARY else f"{app}@{budget}"
            g = hist["guard"] if budget == PRIMARY else {"states": "—", "normalized_unique_urls": "—"}
            f = hist["flatten"] if budget == PRIMARY else {"states": "—", "normalized_unique_urls": "—"}
            s = hist["stack"] if budget == PRIMARY else {"states": "—", "normalized_unique_urls": "—"}
            lines.append(
                "| {label} | {g} | {f} | {s} | {h} | {cont} | {hand} | {wit} | {res} | {un} | {depth} | {hor} | {ret} | {bugs} |".format(
                    label=label,
                    g=_pair_text(g) if budget == PRIMARY else "—",
                    f=_pair_text(f) if budget == PRIMARY else "—",
                    s=_pair_text(s) if budget == PRIMARY else "—",
                    h=_pair_text(cell),
                    cont=cell["nested_continuation_events"],
                    hand=cell["horizon_handoff_started_events"],
                    wit=cell["child_parent_witness_events"],
                    res=cell["parent_frame_resume_to_return_events"],
                    un=cell["horizon_handoff_unwind_events"],
                    depth=cell["max_handoff_stack_depth"],
                    hor=cell["sequence_horizon_reached"],
                    ret=cell["sequence_instances_returned"],
                    bugs=_join(cell["confirmed_bugs"]),
                ))
    lines.extend([
        "",
        "## Regression",
        "",
        "| target | guard confirmed | v0.3.12 | v0.3.13 | v0.3.14 | lost vs guard |",
        "|---|---|---|---|---|---|",
    ])
    for app, case in (regression.get("cases") or {}).items():
        lines.append(
            "| {name} | {ref} | {flat} | {stack} | {cand} | {lost} |".format(
                name=app,
                ref=_join(case.get("reference_confirmed") or []),
                flat=_join(case.get("v0_3_12_confirmed") or []),
                stack=_join(case.get("v0_3_13_confirmed") or []),
                cand=_join(case.get("candidate_confirmed") or []),
                lost=_join(case.get("lost_vs_guard") or []),
            ))
    lines.extend([
        "",
        "## v0.3.13 restore re-audit",
        "",
        "The corrected join does not change the published v0.3.13 Outcome C.",
        "",
        "| target | resumes | old bad restore | same-step terminal witness | corrected residual |",
        "|---|---:|---:|---:|---:|",
    ])
    for app, row in (reaudit.get("apps") or {}).items():
        same = (
            int(row.get("same_step_finding_witness_count") or 0)
            + int(row.get("same_step_crash_witness_count") or 0)
            + int(row.get("same_step_returned_count") or 0))
        lines.append(
            f"| {app} | {row.get('resume_count')} | {row.get('old_bad_restore_count')} | {same} | {row.get('corrected_residual_bad_count')} |")
    lines.extend([
        "",
        "## Safety",
        "",
        "| suite | cases/traces | failures |",
        "|---|---:|---:|",
        f"| H1–H20 | {safety.get('h_series_cases')} | {safety.get('h_series_failures')} |",
        f"| handoff model raw traces | {safety.get('model_raw_traces')} | {safety.get('model_invariant_failures')} |",
        f"| S1–S7 | {safety.get('s1_s7_cases')} | {safety.get('s1_s7_failures')} |",
        f"| historical return model | {safety.get('exhaustive_traces')} | {safety.get('exhaustive_failures')} |",
        f"| N1–N12 historical | {safety.get('n_series_cases')} | {safety.get('n_series_failures')} |",
        f"| P1–P15 historical | {safety.get('p_series_cases')} | {safety.get('p_series_failures')} |",
        "",
        f"witness violations: {mechanism.get('witness_violations')}",
        f"terminal accounting violations: {mechanism.get('terminal_accounting_violations')}",
        "",
        "Product default changed: no",
        "",
        "```text",
        "python -m benchmark.horizon_handoff_reproduce --root experiments/published/horizon-handoff-v0.3.14 --verify",
        "```",
        "",
    ])
    return "\n".join(lines)


def publish(run_root: str = RUN_ROOT, out_root: str = PUBLISHED_ROOT) -> dict:
    if os.path.isdir(out_root):
        shutil.rmtree(out_root)
    os.makedirs(out_root, exist_ok=True)
    stage_evidence(run_root, out_root)
    shutil.copyfile(PROTOCOL, os.path.join(out_root, "protocol.json"))
    shutil.copyfile(REAUDIT, os.path.join(out_root, "v0313-restore-reaudit.json"))
    shutil.copyfile(CANDIDATE_FREEZE, os.path.join(out_root, "candidate-freeze.json"))
    safety = build_safety()
    mechanism = build_mechanism(out_root, safety)
    regression = build_regression(out_root, mechanism)
    witness = build_witness_audit(out_root)
    derived = mechanism["derived"]
    _write_json(os.path.join(out_root, "metrics", "mechanism.json"), mechanism)
    _write_json(os.path.join(out_root, "metrics", "regression.json"), regression)
    _write_json(os.path.join(out_root, "metrics", "safety.json"), safety)
    _write_json(os.path.join(out_root, "metrics", "witness-audit.json"), witness)
    _write_json(os.path.join(out_root, "evidence", "safety", "safety.json"), safety)
    config = {
        "candidate_freeze_commit": "7c34c60f641a31901c86eed718eccd4957462b24",
        "generalization_claim": False,
        "outcome": derived["outcome"],
        "outcome_meaning": derived["outcome_meaning"],
        "product_default": "NoFrontier, sequence_mode=off",
        "product_default_changed": False,
        "promotion_prohibited": True,
        "protocol_commit": "ab883e94a6661f1183e30dccba84ed506e92dab6",
        "reaudit_commit": "f7f40864e3eceefae4bc02d1f7e270c07253cc0f",
        "starting_head": "202abe12310f30e552fbff5317e593682f60a726",
        "v0_3_11_outcome": "D",
        "v0_3_12_outcome": "C",
        "v0_3_13_outcome": "C",
        "verify_command": (
            "python -m benchmark.horizon_handoff_reproduce "
            "--root experiments/published/horizon-handoff-v0.3.14 --verify"),
    }
    _write_json(os.path.join(out_root, "config.json"), config)
    reaudit = load_json(os.path.join(out_root, "v0313-restore-reaudit.json"))
    summary = write_summary(mechanism, regression, safety, reaudit)
    with open(os.path.join(out_root, "summary.md"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(summary)
    repro = {
        "candidate_freeze_commit": config["candidate_freeze_commit"],
        "candidate_freeze_verified": bool(safety.get("candidate_freeze_ok")),
        "clean_clone_verified": False,
        "command": config["verify_command"],
        "evidence_manifest_verified": True,
        "expected_mechanism_sha256": sha256_bytes(canonical_json_bytes(mechanism)),
        "expected_regression_sha256": sha256_bytes(canonical_json_bytes(regression)),
        "expected_safety_sha256": sha256_bytes(canonical_json_bytes(safety)),
        "expected_witness_audit_sha256": sha256_bytes(canonical_json_bytes(witness)),
        "historical_c1_freeze_verified": "c1" not in (safety.get("historical_freeze_failures") or []),
        "historical_guard_freeze_verified": "v0.3.9-guard" not in (
            safety.get("historical_freeze_failures") or []),
        "historical_flatten_freeze_verified": "v0.3.12-candidate" not in (
            safety.get("historical_freeze_failures") or []),
        "historical_stack_freeze_verified": "v0.3.13-candidate" not in (
            safety.get("historical_freeze_failures") or []),
        "match": False,
        "outcome": derived["outcome"],
        "product_default_changed": False,
        "protocol_commit": config["protocol_commit"],
        "reaudit_commit": config["reaudit_commit"],
        "reaudit_sha256": sha256_file(REAUDIT),
        "target_freeze_verified": not any(
            name in (safety.get("historical_freeze_failures") or [])
            for name in TARGET_FREEZES),
    }
    _write_json(os.path.join(out_root, "metrics", "reproduction.json"), repro)
    man = _manifest(out_root)
    _write_json(os.path.join(out_root, "evidence-manifest.json"), man)
    return {"outcome": derived["outcome"], "config": config, "files": man["expected_file_count"]}


def main(argv=None) -> int:
    del argv
    result = publish()
    print(f"outcome {result['outcome']}")
    print(f"files {result['files']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
