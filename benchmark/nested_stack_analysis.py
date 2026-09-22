"""v0.3.13 measurement gates. Does not choose exploration actions."""
from __future__ import annotations

import os

from ghostqa.exploration.nested_stack_guard import terminal_violations

MIN_EXHAUSTIVE_TRACES = 5800
SOURCE = os.path.join(
    "ghostqa", "exploration", "nested_stack_guard.py")
V0312_LOST = {
    "buggy-desk": ["BUG-K10", "BUG-K3", "BUG-K6", "BUG-K9"],
    "buggy-shop": [],
    "deepbench": ["BUG-D12"],
    "wiki": [],
}
OUTCOME_MEANING = {
    "A": "stack repair succeeds and removes v0.3.12 regressions",
    "B": "mechanism works but regression repair is incomplete",
    "C": "harmful / unsafe",
    "D": "stack mechanism does not repair inspected preemption",
}
APP_NEEDLES = (
    "customer", "members", "bug-", "buggy-", "crm", "desk", "wiki",
    "shop", "deepbench", "settings.html", "handbook", "ticket",
    "article", "nav_activity",
)


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def app_specific_needles(path: str = SOURCE) -> list:
    if not os.path.isfile(path):
        return ["missing-source"]
    text = open(path, encoding="utf-8").read().lower()
    return [needle for needle in APP_NEEDLES if needle in text]


def structural_repair_gate(cell: dict | None) -> bool:
    """Preregistered CRM/Ops gate. Coverage need not beat flattening."""
    row = cell or {}
    return (
        _int(row.get("nested_child_stack_events")) >= 1
        and _int(row.get("commitment_window_preemptions")) == 0
        and bool(row.get("reached_horizon_or_safe_terminal"))
        and bool(row.get("reached_return_or_child_resume"))
        and bool(row.get("expanded_beyond_guard"))
    )


def _additional(lost: dict | None, baseline: dict | None) -> dict:
    extra = {}
    names = set(lost or {}) | set(baseline or {})
    for name in sorted(names):
        more = set((lost or {}).get(name) or []) - set((baseline or {}).get(name) or [])
        if more:
            extra[name] = sorted(more)
    return extra


def _any_lost(lost: dict | None) -> list:
    names = []
    for name in sorted((lost or {})):
        if list((lost or {}).get(name) or []):
            names.append(name)
    return names


def stack_audit(seq_events: list | None) -> dict:
    """LIFO restoration, false returns, and one terminal per instance."""
    events = list(seq_events or [])
    violations = terminal_violations(events)
    frames = []
    corruption = []
    bad_restore = []
    inflation = []
    for index, event in enumerate(events):
        kind = event.get("event")
        if kind == "parent_frame_suspended":
            frames.append(event)
            if _int(event.get("stack_depth")) != len(frames):
                corruption.append({"index": index, "reason": "push_depth"})
        elif kind == "parent_frame_resumed":
            if not frames:
                corruption.append({"index": index, "reason": "resume_empty"})
                continue
            top = frames.pop()
            resumed = event.get("resumed_sequence_instance_id") or event.get(
                "sequence_instance_id")
            suspended = top.get("suspended_sequence_instance_id")
            if resumed != suspended:
                corruption.append({"index": index, "reason": "lifo_id"})
            if event.get("remaining_commitment") != top.get("commitment_left"):
                corruption.append({"index": index, "reason": "commitment"})
            if _int(event.get("stack_depth")) != len(frames):
                corruption.append({"index": index, "reason": "pop_depth"})
            if event.get("reason") != "child_returned_to_parent":
                bad_restore.append({"index": index, "reason": "reason"})
            if event.get("child_parent_matched") is not True:
                bad_restore.append({"index": index, "reason": "parent_match"})
            child = event.get("child_sequence_instance_id")
            step = event.get("step")
            child_terminals = [
                item for item in events
                if item.get("event") == "sequence_terminal"
                and item.get("sequence_instance_id") == child
            ]
            same_step_returned = [
                item for item in child_terminals
                if item.get("outcome") == "returned" and item.get("step") == step
            ]
            prior = [
                item for item in child_terminals
                if item.get("step") is not None and step is not None
                and int(item.get("step")) < int(step)
            ]
            prior_outcomes = {item.get("outcome") for item in prior}
            if "returned" in prior_outcomes or "nested_descendant_abandoned" in prior_outcomes:
                inflation.append({"index": index, "reason": "child_already_closed"})
            if same_step_returned:
                pass
            elif prior_outcomes & {"finding", "crash"}:
                pass
            else:
                bad_restore.append({"index": index, "reason": "no_child_return_evidence"})
            resumed_same_step = [
                item for item in events
                if item.get("event") == "sequence_terminal"
                and item.get("sequence_instance_id") == resumed
                and item.get("step") == step
            ]
            if resumed_same_step:
                inflation.append({"index": index, "reason": "resume_terminal"})
            if any(item.get("event") == "return_cycle_escape"
                   and item.get("step") == step for item in events):
                bad_restore.append({"index": index, "reason": "escape_same_step"})
        elif kind == "nested_stack_unwind":
            if _int(event.get("stack_depth")) != 0:
                corruption.append({"index": index, "reason": "unwind_depth"})
            if not frames and _int(event.get("stack_depth_before")) == 0:
                corruption.append({"index": index, "reason": "unwind_empty"})
            frames.clear()
    per_instance: dict = {}
    for event in events:
        if event.get("event") != "sequence_terminal":
            continue
        iid = event.get("sequence_instance_id")
        per_instance.setdefault(iid, []).append(event.get("outcome") or "")
    for iid, outcomes in per_instance.items():
        if outcomes.count("returned") > 1:
            inflation.append({"id": iid, "reason": "duplicate_returned"})
        if "returned" in outcomes and "return_cycle_abandoned" in outcomes:
            inflation.append({"id": iid, "reason": "returned_and_abandoned"})
        if "returned" in outcomes and "nested_descendant_abandoned" in outcomes:
            inflation.append({"id": iid, "reason": "returned_and_unwound"})
    return {
        "terminal_violations": violations,
        "terminal_accounting_violations": len(violations),
        "stack_frame_corruption": bool(corruption),
        "corruption": corruption,
        "restore_without_child_return": bool(bad_restore),
        "bad_restore": bad_restore,
        "return_inflation": bool(inflation),
        "inflation": inflation,
    }


def derive_v0313_outcome(
    *,
    candidate_freeze_ok: bool,
    historical_freezes_ok: bool,
    p_series_failures: int,
    s1_s7_pass: bool,
    exhaustive_failures: int,
    exhaustive_traces: int,
    terminal_accounting_violations: int,
    return_inflation: bool,
    stack_frame_corruption: bool,
    restore_without_child_return: bool,
    app_specific_logic: bool,
    product_default_changed: bool,
    crm_repair: bool,
    ops_repair: bool,
    lost_vs_guard: dict | None,
    v0312_lost: dict | None = None,
) -> dict:
    """Preregistered A/B/C/D. C, then D, then B, else A."""
    baseline = V0312_LOST if v0312_lost is None else v0312_lost
    lost = {
        name: sorted(set(bugs or []))
        for name, bugs in (lost_vs_guard or {}).items()
    }
    additional = _additional(lost, baseline)
    harmful = (
        not candidate_freeze_ok
        or not historical_freezes_ok
        or _int(p_series_failures) > 0
        or not s1_s7_pass
        or _int(exhaustive_failures) > 0
        or _int(exhaustive_traces) < MIN_EXHAUSTIVE_TRACES
        or _int(terminal_accounting_violations) > 0
        or bool(return_inflation)
        or bool(stack_frame_corruption)
        or bool(restore_without_child_return)
        or bool(app_specific_logic)
        or bool(product_default_changed)
        or bool(additional)
    )
    both_repair = bool(crm_repair) and bool(ops_repair)
    lost_cases = _any_lost(lost)
    if harmful:
        outcome = "C"
    elif not both_repair:
        outcome = "D"
    elif lost_cases:
        outcome = "B"
    else:
        outcome = "A"
    return {
        "outcome": outcome,
        "outcome_meaning": OUTCOME_MEANING[outcome],
        "product_default_changed": bool(product_default_changed),
        "generalization_claim": False,
        "promotion_prohibited": True,
        "crm_repair": bool(crm_repair),
        "ops_repair": bool(ops_repair),
        "lost_cases": lost_cases,
        "additional_lost": additional,
        "lost_vs_guard": lost,
        "safety_failure": harmful,
        "v0_3_12_outcome_preserved": "C",
        "v0_3_11_outcome_preserved": "D",
    }
