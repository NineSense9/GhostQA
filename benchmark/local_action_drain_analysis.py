"""v0.3.17 outcome gate. Does not choose exploration actions."""
from __future__ import annotations

from benchmark.fresh_handoff_analysis import full_transfer
from benchmark.horizon_handoff_analysis import GUARD_CONFIRMED
from benchmark.reentry_frontier_analysis import (
    directory_repair_gate, mechanism_preserved, new_guard_losses,
)

OUTCOME_MEANING = {
    "A": (
        "Local Action Drain repairs the inspected remaining Lab local-action "
        "starvation while preserving directory selectivity, prior fresh-transfer "
        "cases, inspected mechanism cases, and historical regressions"
    ),
    "B": (
        "Safety and protocol pass, directory and historical regression stay "
        "safe, and local action drain engages, but the full Outcome A gate "
        "is incomplete"
    ),
    "C": "unsafe / harmful / protocol-invalid",
    "D": (
        "Safety and protocol pass, but the diagnosed Lab local-action drain "
        "does not engage"
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


def transfer_preserved(guard_row: dict, candidate_row: dict, evaluable: bool) -> bool:
    report = full_transfer(True, bool(evaluable), guard_row or {}, candidate_row or {})
    lost = lost_vs(confirmed_of(guard_row), confirmed_of(candidate_row))
    return bool(report.get("pass")) and not lost


def directory_preserved(row: dict | None, guard_confirmed, candidate_confirmed) -> bool:
    cell = row or {}
    clean = (
        _int(cell.get("horizon_handoff_started_events")) == 0
        and _int(cell.get("max_handoff_stack_depth")) == 0
        and _int(cell.get("witness_violations")) == 0
        and _int(cell.get("terminal_accounting_violations")) == 0
        and _int(cell.get("repeated_local_action_key_violations")) == 0
        and _int(cell.get("local_action_sequence_accounting_violations")) == 0
        and set(guard_confirmed or []) <= set(candidate_confirmed or [])
    )
    return bool(clean)


def lab_mechanism_gate(facts: dict) -> bool:
    """Preregistered Lab @120 local-action checks. Button ids stay outside the candidate."""
    return bool(
        facts.get("sample_child_witness")
        and facts.get("drain_started_at_run")
        and facts.get("same_hub_probe_before_structural_navigation")
        and facts.get("result_drain_started")
        and facts.get("close_reopen_before_structural_navigation")
        and _int(facts.get("repeated_local_key_violations")) == 0
        and _int(facts.get("local_action_sequence_accounting_violations")) == 0
        and _int(facts.get("witness_violations")) == 0
        and _int(facts.get("terminal_accounting_violations")) == 0
    )


def passing_facts() -> dict:
    """Synthetic inputs that satisfy Outcome A. Tests mutate a copy."""
    return {
        "candidate_freeze_ok": True,
        "historical_freeze_ok": True,
        "protocol_ok": True,
        "post_freeze_edit": False,
        "safety_ok": True,
        "model_ok": True,
        "model_invariant_failures": 0,
        "model_raw_traces": 66429,
        "repeated_local_key_violations": 0,
        "cross_hub_drain_violations": 0,
        "local_action_sequence_accounting_violations": 0,
        "phantom_sequence": False,
        "fabricated_outer_terminal": False,
        "promotion_unsafe": False,
        "double_browser_action": False,
        "witness_violations": 0,
        "terminal_accounting_violations": 0,
        "app_specific": False,
        "hidden_metadata": False,
        "historical_regression_loss": [],
        "crm_ops_collapse": False,
        "directory_false_handoff": False,
        "product_default_changed": False,
        "lab_drain_engaged": True,
        "lab_mechanism_gate": True,
        "lab_zero_guard_loss": True,
        "directory_preserved": True,
        "forum_full_transfer": True,
        "billing_full_transfer": True,
        "crm_preserved": True,
        "ops_preserved": True,
        "sample_child_witness": True,
        "drain_started_at_run": True,
        "same_hub_probe_before_structural_navigation": True,
        "result_drain_started": True,
        "close_reopen_before_structural_navigation": True,
    }


def derive_v0317_outcome(**facts) -> dict:
    """Preregistered order: C, then D, then B, else A."""
    data = passing_facts()
    data.update(facts)
    data["lab_mechanism_gate"] = bool(data["lab_mechanism_gate"]) and lab_mechanism_gate(data)
    harmful = (
        not data["candidate_freeze_ok"]
        or not data["historical_freeze_ok"]
        or not data["protocol_ok"]
        or bool(data["post_freeze_edit"])
        or not data["safety_ok"]
        or not data["model_ok"]
        or _int(data["model_invariant_failures"]) > 0
        or _int(data["model_raw_traces"]) != 66429
        or _int(data["repeated_local_key_violations"]) > 0
        or _int(data["cross_hub_drain_violations"]) > 0
        or _int(data["local_action_sequence_accounting_violations"]) > 0
        or bool(data["phantom_sequence"])
        or bool(data["fabricated_outer_terminal"])
        or bool(data["promotion_unsafe"])
        or bool(data["double_browser_action"])
        or _int(data["witness_violations"]) > 0
        or _int(data["terminal_accounting_violations"]) > 0
        or bool(data["app_specific"])
        or bool(data["hidden_metadata"])
        or bool(data["historical_regression_loss"])
        or bool(data["crm_ops_collapse"])
        or bool(data["directory_false_handoff"])
        or bool(data["product_default_changed"])
    )
    engaged = bool(data["lab_drain_engaged"])
    complete = (
        bool(data["directory_preserved"])
        and bool(data["lab_mechanism_gate"])
        and bool(data["lab_zero_guard_loss"])
        and bool(data["forum_full_transfer"])
        and bool(data["billing_full_transfer"])
        and bool(data["crm_preserved"])
        and bool(data["ops_preserved"])
        and not data["historical_regression_loss"]
    )
    if harmful:
        outcome = "C"
    elif not engaged:
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
        "lab_drain_engaged": engaged,
        "outcome_a_complete": complete and not harmful,
        "guard_confirmed_reference": {
            "lab": list(LAB_GUARD),
            **{name: list(GUARD_CONFIRMED[name]) for name in REGRESSION_APPS},
        },
    }


__all__ = [
    "LAB_GUARD",
    "REGRESSION_APPS",
    "confirmed_of",
    "derive_v0317_outcome",
    "directory_preserved",
    "directory_repair_gate",
    "lab_mechanism_gate",
    "lost_vs",
    "mechanism_preserved",
    "new_guard_losses",
    "passing_facts",
    "transfer_preserved",
]
