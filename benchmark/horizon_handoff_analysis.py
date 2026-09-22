"""v0.3.14 outcome gate. Does not choose exploration actions."""
from __future__ import annotations

OUTCOME_MEANING = {
    "A": (
        "Horizon Handoff repairs the inspected nested-boundary mechanism "
        "and passes the specified historical regression suite"
    ),
    "B": "mechanism repaired, regression mixed",
    "C": "unsafe / protocol-invalid",
    "D": "safe but mechanism not repaired",
}
GUARD_CONFIRMED = {
    "buggy-desk": ["BUG-K1", "BUG-K2", "BUG-K3", "BUG-K5", "BUG-K6", "BUG-K9", "BUG-K10"],
    "deepbench": ["BUG-D6", "BUG-D7", "BUG-D11", "BUG-D12", "BUG-D13", "BUG-D14"],
    "wiki": ["BUG-W2"],
    "buggy-shop": ["BUG-W5", "BUG-W6", "BUG-W9", "BUG-W10"],
}


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def mechanism_repair(candidate: dict | None, guard: dict | None = None) -> dict:
    """CRM/Ops lifecycle repair. Coverage need not beat flattening."""
    row = candidate or {}
    baseline = guard or {}
    guard_states = _int(baseline.get("states"))
    guard_urls = _int(baseline.get("normalized_unique_urls"))
    baseline_ok = guard_states == 5 and guard_urls == 5
    states_ok = _int(row.get("states")) > 5
    urls_ok = _int(row.get("normalized_unique_urls")) > 5
    preemptions = _int(row.get("commitment_window_preemptions"))
    continuations = _int(row.get("nested_continuation_events"))
    handoffs = _int(row.get("horizon_handoff_started_events"))
    horizon = _int(row.get("sequence_horizon_reached"))
    returns = (
        _int(row.get("return_attempt_events")) > 0
        or _int(row.get("sequence_instances_returned")) > 0
        or _int(row.get("return_cycle_escape_events")) > 0
    )
    resumes = _int(row.get("parent_frame_resume_to_return_events"))
    unwinds = _int(row.get("horizon_handoff_unwind_events"))
    depth = _int(row.get("max_handoff_stack_depth"))
    pathological = (
        handoffs > 0
        and resumes == 0
        and unwinds == 0
        and depth == handoffs
        and horizon == 0
    )
    violations = _int(row.get("witness_violations"))
    ok = bool(
        baseline_ok
        and states_ok
        and urls_ok
        and preemptions == 0
        and continuations > 0
        and handoffs > 0
        and horizon > 0
        and returns
        and not pathological
        and violations == 0
    )
    return {
        "pass": ok,
        "baseline_5_5": baseline_ok,
        "states_above_guard_collapse": states_ok,
        "urls_above_guard_collapse": urls_ok,
        "commitment_window_preemptions": preemptions,
        "nested_continuation_events": continuations,
        "horizon_handoff_started_events": handoffs,
        "sequence_horizon_reached": horizon,
        "reached_return_lifecycle": returns,
        "pathological_unresolved_stack": pathological,
        "witness_violations": violations,
    }


def _lost(confirmed: dict | None, reference: dict | None = None) -> dict:
    ref = GUARD_CONFIRMED if reference is None else reference
    lost = {}
    names = set(ref) | set(confirmed or {})
    for name in sorted(names):
        missing = sorted(set(ref.get(name) or []) - set((confirmed or {}).get(name) or []))
        lost[name] = missing
    return lost


def derive_v0314_outcome(
    *,
    candidate_freeze_ok: bool,
    historical_freezes_ok: bool,
    h_series_failures: int,
    model_invariant_failures: int,
    historical_safety_regressed: bool,
    witness_violations: int,
    terminal_accounting_violations: int,
    return_inflation: bool,
    wrong_child_or_parent_resume: bool,
    app_specific_logic: bool,
    product_default_changed: bool,
    post_freeze_semantic_tuning: bool,
    crm_repair: bool,
    ops_repair: bool,
    confirmed: dict | None = None,
    lost_vs_guard: dict | None = None,
) -> dict:
    """Preregistered A/B/C/D. C, then D, then B, else A."""
    lost = _lost(confirmed) if lost_vs_guard is None else {
        name: sorted(set(bugs or []))
        for name, bugs in (lost_vs_guard or {}).items()
    }
    lost_cases = [name for name in sorted(lost) if list(lost.get(name) or [])]
    harmful = (
        not candidate_freeze_ok
        or not historical_freezes_ok
        or _int(h_series_failures) > 0
        or _int(model_invariant_failures) > 0
        or bool(historical_safety_regressed)
        or _int(witness_violations) > 0
        or _int(terminal_accounting_violations) > 0
        or bool(return_inflation)
        or bool(wrong_child_or_parent_resume)
        or bool(app_specific_logic)
        or bool(product_default_changed)
        or bool(post_freeze_semantic_tuning)
    )
    if harmful:
        outcome = "C"
    elif not (bool(crm_repair) and bool(ops_repair)):
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
        "lost_vs_guard": lost,
        "safety_failure": harmful,
        "v0_3_11_outcome_preserved": "D",
        "v0_3_12_outcome_preserved": "C",
        "v0_3_13_outcome_preserved": "C",
    }
