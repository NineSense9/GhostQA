"""v0.3.16 outcome gate. Does not choose exploration actions."""
from __future__ import annotations

from benchmark.fresh_handoff_analysis import full_transfer
from benchmark.horizon_handoff_analysis import GUARD_CONFIRMED

OUTCOME_MEANING = {
    "A": (
        "Early parent re-entry and local structural frontier lease repair the "
        "inspected v0.3.15 false-activation and starvation failures while "
        "preserving the specified historical mechanisms and regressions"
    ),
    "B": (
        "At least one inspected repair engages safely, but the full "
        "Outcome A gate is incomplete"
    ),
    "C": "unsafe / harmful / protocol-invalid",
    "D": (
        "Safety and protocol pass, but neither early parent re-entry nor the "
        "local frontier lease demonstrates the inspected repair"
    ),
}

LAB_GUARD = ["BUG-L1", "BUG-L10", "BUG-L2", "BUG-L8", "BUG-L9"]
REGRESSION_APPS = ("buggy-desk", "deepbench", "wiki", "buggy-shop")


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def confirmed_of(row: dict | None) -> list:
    return sorted((row or {}).get("confirmed_bugs") or [])


def lost_vs(reference, candidate) -> list:
    return sorted(set(reference or []) - set(candidate or []))


def new_guard_losses(guard, historical, candidate) -> list:
    """Guard bugs the historical candidate still confirmed and the new one lost."""
    return sorted((set(guard or []) & set(historical or [])) - set(candidate or []))


def directory_repair_gate(row: dict | None, guard_confirmed, candidate_confirmed) -> bool:
    cell = row or {}
    return bool(
        _int(cell.get("early_parent_reentry_events")) >= 1
        and _int(cell.get("horizon_handoff_started_events")) == 0
        and _int(cell.get("child_parent_witness_events")) == 0
        and _int(cell.get("max_handoff_stack_depth")) == 0
        and _int(cell.get("witness_violations")) == 0
        and _int(cell.get("terminal_accounting_violations")) == 0
        and set(guard_confirmed or []) <= set(candidate_confirmed or [])
    )


def lab_starvation_gate(row: dict | None) -> bool:
    cell = row or {}
    return bool(
        _int(cell.get("horizon_handoff_started_events")) >= 1
        and _int(cell.get("local_frontier_lease_granted_events")) >= 1
        and _int(cell.get("local_frontier_lease_action_events")) >= 1
        and _int(cell.get("frontier_repeated_key_violations")) == 0
        and _int(cell.get("witness_violations")) == 0
        and _int(cell.get("terminal_accounting_violations")) == 0
        and _int(cell.get("lease_cross_hub_uncancelled")) == 0
        and _int(cell.get("frontier_monotonicity_violations")) == 0
    )


def transfer_preserved(guard_row: dict, candidate_row: dict, evaluable: bool) -> bool:
    report = full_transfer(True, bool(evaluable), guard_row or {}, candidate_row or {})
    lost = lost_vs(confirmed_of(guard_row), confirmed_of(candidate_row))
    return bool(report.get("pass")) and not lost


def mechanism_preserved(row: dict | None) -> dict:
    cell = row or {}
    states = _int(cell.get("states"))
    urls = _int(cell.get("normalized_unique_urls"))
    lost_parent = _int(cell.get("sequence_lost_parent"))
    horizon = _int(cell.get("sequence_horizon_reached"))
    returned = _int(cell.get("sequence_instances_returned"))
    early = _int(cell.get("early_parent_reentry_events"))
    witness = _int(cell.get("child_parent_witness_events"))
    escapes = _int(cell.get("return_cycle_escape_events"))
    handoffs = _int(cell.get("horizon_handoff_started_events"))
    resumes = _int(cell.get("parent_frame_resume_to_return_events"))
    unwinds = _int(cell.get("horizon_handoff_unwind_events"))
    depth = _int(cell.get("max_handoff_stack_depth"))
    violations = _int(cell.get("witness_violations")) + _int(
        cell.get("terminal_accounting_violations"))
    collapse = states <= 5 or urls <= 5
    prehorizon = lost_parent > 0 and horizon == 0 and witness == 0 and early == 0
    runaway = (
        depth > 0 and depth == handoffs and (resumes + unwinds) == 0
        and horizon == 0 and early == 0 and witness == 0
    )
    resolved = horizon > 0 or returned > 0 or early > 0 or witness > 0 or escapes > 0
    ok = (
        not collapse and not prehorizon and not runaway and resolved
        and violations == 0
    )
    return {
        "pass": ok,
        "collapse": bool(collapse or prehorizon or runaway),
        "states": states,
        "urls": urls,
        "resolved": resolved,
    }


def passing_facts() -> dict:
    """Synthetic inputs that satisfy Outcome A. Tests mutate a copy."""
    return {
        "candidate_freeze_ok": True,
        "historical_freeze_ok": True,
        "protocol_ok": True,
        "post_freeze_edit": False,
        "safety_ok": True,
        "model_ok": True,
        "double_completion": 0,
        "false_return_inflation": 0,
        "witness_violations": 0,
        "terminal_accounting_violations": 0,
        "repeated_lease_key_violations": 0,
        "lease_cross_hub_uncancelled": 0,
        "monotonicity_violations": 0,
        "app_specific": False,
        "new_guard_bug_loss": [],
        "historical_regression_loss": [],
        "crm_ops_collapse": False,
        "product_default_changed": False,
        "directory_same_parent_handoffs": 0,
        "directory_early_reentry_events": 1,
        "directory_source_repair_events": 0,
        "directory_repair_gate": True,
        "lab_lease_granted_events": 1,
        "lab_starvation_gate": True,
        "lab_zero_guard_loss": True,
        "forum_full_transfer": True,
        "billing_full_transfer": True,
        "crm_preserved": True,
        "ops_preserved": True,
    }


def derive_v0316_outcome(**facts) -> dict:
    """Preregistered order: C, then D, then B, else A."""
    data = passing_facts()
    data.update(facts)
    harmful = (
        not data["candidate_freeze_ok"]
        or not data["historical_freeze_ok"]
        or not data["protocol_ok"]
        or bool(data["post_freeze_edit"])
        or not data["safety_ok"]
        or not data["model_ok"]
        or _int(data["double_completion"]) > 0
        or _int(data["false_return_inflation"]) > 0
        or _int(data["witness_violations"]) > 0
        or _int(data["terminal_accounting_violations"]) > 0
        or _int(data["repeated_lease_key_violations"]) > 0
        or _int(data["lease_cross_hub_uncancelled"]) > 0
        or _int(data["monotonicity_violations"]) > 0
        or bool(data["app_specific"])
        or bool(data["new_guard_bug_loss"])
        or bool(data["historical_regression_loss"])
        or bool(data["crm_ops_collapse"])
        or bool(data["product_default_changed"])
    )
    directory_unrepaired = (
        _int(data["directory_same_parent_handoffs"]) > 0
        and _int(data["directory_early_reentry_events"]) == 0
        and _int(data["directory_source_repair_events"]) == 0
    )
    lab_unrepaired = _int(data["lab_lease_granted_events"]) == 0
    complete = (
        bool(data["directory_repair_gate"])
        and bool(data["lab_starvation_gate"])
        and bool(data["lab_zero_guard_loss"])
        and bool(data["forum_full_transfer"])
        and bool(data["billing_full_transfer"])
        and bool(data["crm_preserved"])
        and bool(data["ops_preserved"])
    )
    if harmful:
        outcome = "C"
    elif directory_unrepaired and lab_unrepaired:
        outcome = "D"
    elif not complete:
        outcome = "B"
    else:
        outcome = "A"
    return {
        "outcome": outcome,
        "outcome_meaning": OUTCOME_MEANING[outcome],
        "promotion_readiness": "not_ready",
        "product_default_changed": bool(data["product_default_changed"]),
        "generalization_claim": False,
        "fresh_validation": False,
        "directory_unrepaired": directory_unrepaired,
        "lab_unrepaired": lab_unrepaired,
        "outcome_a_complete": complete,
        "guard_confirmed_reference": {
            "lab": list(LAB_GUARD),
            **{name: list(GUARD_CONFIRMED[name]) for name in REGRESSION_APPS},
        },
    }
