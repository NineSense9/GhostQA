"""v0.3.19 outcome gate. Does not choose exploration actions."""
from __future__ import annotations

from benchmark.fresh_handoff_analysis import full_transfer
from benchmark.horizon_handoff_analysis import GUARD_CONFIRMED
from benchmark.local_action_drain_analysis import (
    REGRESSION_APPS, confirmed_of, directory_preserved, lost_vs,
)
from benchmark.reentry_frontier_analysis import mechanism_preserved, new_guard_losses

OUTCOME_MEANING = {
    "A": (
        "Finding-gated Return-Entry Drain preserves the inspected Lab "
        "result-hub repair while removing horizon-triggered return-entry "
        "behavior and preserving the specified inspected and historical suite"
    ),
    "B": (
        "Safety and protocol pass and the finding-gated drain engages, "
        "but the full Outcome A gate is incomplete"
    ),
    "C": "unsafe / harmful / protocol-invalid",
    "D": (
        "Safety and protocol pass, but the Lab finding-terminal return-entry "
        "mechanism does not engage"
    ),
}

LAB_GUARD = ["BUG-L1", "BUG-L2", "BUG-L8", "BUG-L9", "BUG-L10"]
DEEP_GUARD = ["BUG-D6", "BUG-D7", "BUG-D11", "BUG-D12", "BUG-D13", "BUG-D14"]
V0318_DEEP_STATE_COLLAPSE = 8


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def transfer_preserved(guard_row: dict, candidate_row: dict, evaluable: bool) -> bool:
    report = full_transfer(True, bool(evaluable), guard_row or {}, candidate_row or {})
    lost = lost_vs(confirmed_of(guard_row), confirmed_of(candidate_row))
    return bool(report.get("pass")) and not lost


def directory_preserved_v0319(row: dict | None, guard_confirmed, candidate_confirmed) -> bool:
    cell = row or {}
    return bool(
        directory_preserved(cell, guard_confirmed, candidate_confirmed)
        and _int(cell.get("return_entry_accounting_violations")) == 0
        and _int(cell.get("finding_return_entry_trigger_mismatch_violations")) == 0
        and _int(cell.get("finding_return_entry_reused_trigger_violations")) == 0
        and _int(cell.get("finding_return_entry_wrong_instance_violations")) == 0
    )


def trigger_counts_match(row: dict | None) -> bool:
    cell = row or {}
    return _int(cell.get("return_entry_drain_started_events")) == _int(
        cell.get("finding_return_entry_trigger_events"))


def deep_coverage_ok(candidate: dict | None, previous: dict | None) -> dict:
    """Preregistered DeepBench coverage bounds.

    States must exceed the committed v0.3.18 collapse of 8. URLs must be at
    least the committed v0.3.17 count. Guard evidence does not record URLs.
    Return success must not collapse to zero.
    """
    cell = candidate or {}
    prior = previous or {}
    previous_urls = _int(prior.get("normalized_unique_urls"))
    return {
        "states_ok": _int(cell.get("states")) > V0318_DEEP_STATE_COLLAPSE,
        "urls_ok": previous_urls > 0 and _int(cell.get("normalized_unique_urls")) >= previous_urls,
        "return_success_ok": _int(cell.get("return_success")) > 0,
        "previous_urls": previous_urls,
    }


def lab_mechanism_gate(facts: dict) -> bool:
    """Preregistered Lab @120 finding-gated checks. Button ids stay outside the candidate."""
    return bool(
        facts.get("result_hub_reached")
        and facts.get("finding_terminal_false_to_true")
        and facts.get("finding_return_entry_trigger_at_result")
        and facts.get("return_entry_drain_started_at_result")
        and facts.get("result_button_probe_before_first_return")
        and facts.get("stable_order_when_close_reopen_visible")
        and facts.get("bug_l9_confirmed")
        and facts.get("return_attempts_unchanged_during_probes")
        and facts.get("no_duplicate_terminal")
        and facts.get("no_return_cycle_contamination")
        and facts.get("historical_return_resumes_after_exhaustion")
        and _int(facts.get("probe_return_attempt_violations")) == 0
        and _int(facts.get("probe_return_cycle_violations")) == 0
        and _int(facts.get("duplicate_terminal_count")) == 0
        and _int(facts.get("false_return_success_count")) == 0
        and _int(facts.get("parent_corruption_count")) == 0
        and _int(facts.get("repeated_key_violations")) == 0
        and _int(facts.get("return_entry_accounting_violations")) == 0
        and _int(facts.get("witness_violations")) == 0
        and _int(facts.get("terminal_accounting_violations")) == 0
        and _int(facts.get("trigger_mismatch_violations")) == 0
        and _int(facts.get("reused_trigger_violations")) == 0
        and _int(facts.get("wrong_instance_violations")) == 0
    )


def passing_facts() -> dict:
    """Synthetic inputs that satisfy Outcome A. Tests mutate a copy."""
    return {
        "candidate_freeze_ok": True,
        "historical_freeze_ok": True,
        "protocol_ok": True,
        "historical_source_mutation": False,
        "post_freeze_edit": False,
        "safety_ok": True,
        "fg_safety_ok": True,
        "horizon_differential_ok": True,
        "model_ok": True,
        "model_invariant_failures": 0,
        "model_raw_traces": 66429,
        "historical_models_ok": True,
        "probe_return_attempt_violations": 0,
        "probe_return_cycle_violations": 0,
        "duplicate_terminal": False,
        "duplicate_terminal_count": 0,
        "false_return_success": False,
        "false_return_success_count": 0,
        "parent_corruption": False,
        "parent_corruption_count": 0,
        "repeated_key_violations": 0,
        "return_entry_accounting_violations": 0,
        "witness_violations": 0,
        "terminal_accounting_violations": 0,
        "trigger_mismatch_violations": 0,
        "reused_trigger_violations": 0,
        "wrong_instance_violations": 0,
        "horizon_only_drain": False,
        "nonfinding_triggered_drain": False,
        "wrong_instance_triggered_drain": False,
        "reused_trigger": False,
        "trigger_counts_match": True,
        "app_specific": False,
        "directory_false_handoff": False,
        "crm_ops_collapse": False,
        "historical_regression_loss": [],
        "product_default_changed": False,
        "result_return_entry_engaged": True,
        "lab_mechanism_gate": True,
        "result_hub_reached": True,
        "finding_terminal_false_to_true": True,
        "finding_return_entry_trigger_at_result": True,
        "return_entry_drain_started_at_result": True,
        "result_button_probe_before_first_return": True,
        "stable_order_when_close_reopen_visible": True,
        "bug_l9_confirmed": True,
        "return_attempts_unchanged_during_probes": True,
        "no_duplicate_terminal": True,
        "no_return_cycle_contamination": True,
        "historical_return_resumes_after_exhaustion": True,
        "lab_zero_guard_loss": True,
        "directory_preserved": True,
        "forum_full_transfer": True,
        "billing_full_transfer": True,
        "crm_preserved": True,
        "ops_preserved": True,
        "deep_no_horizon_drain": True,
        "deep_guard_retained": True,
        "deep_states_ok": True,
        "deep_urls_ok": True,
        "deep_return_success_ok": True,
        "deep_horizon_bypass_ok": True,
    }


def derive_v0319_outcome(**facts) -> dict:
    """Preregistered order: C, then D, then B, else A."""
    data = passing_facts()
    data.update(facts)
    data["lab_mechanism_gate"] = bool(data["lab_mechanism_gate"]) and lab_mechanism_gate(data)
    harmful = (
        not data["candidate_freeze_ok"]
        or not data["historical_freeze_ok"]
        or not data["protocol_ok"]
        or bool(data["historical_source_mutation"])
        or bool(data["post_freeze_edit"])
        or not data["safety_ok"]
        or not data["fg_safety_ok"]
        or not data["horizon_differential_ok"]
        or not data["model_ok"]
        or not data["historical_models_ok"]
        or _int(data["model_invariant_failures"]) > 0
        or _int(data["model_raw_traces"]) != 66429
        or _int(data["probe_return_attempt_violations"]) > 0
        or _int(data["probe_return_cycle_violations"]) > 0
        or bool(data["duplicate_terminal"])
        or _int(data["duplicate_terminal_count"]) > 0
        or bool(data["false_return_success"])
        or _int(data["false_return_success_count"]) > 0
        or bool(data["parent_corruption"])
        or _int(data["parent_corruption_count"]) > 0
        or _int(data["repeated_key_violations"]) > 0
        or _int(data["return_entry_accounting_violations"]) > 0
        or _int(data["witness_violations"]) > 0
        or _int(data["terminal_accounting_violations"]) > 0
        or _int(data["trigger_mismatch_violations"]) > 0
        or _int(data["reused_trigger_violations"]) > 0
        or _int(data["wrong_instance_violations"]) > 0
        or bool(data["horizon_only_drain"])
        or bool(data["nonfinding_triggered_drain"])
        or bool(data["wrong_instance_triggered_drain"])
        or bool(data["reused_trigger"])
        or not data["trigger_counts_match"]
        or not data["deep_no_horizon_drain"]
        or bool(data["app_specific"])
        or bool(data["directory_false_handoff"])
        or bool(data["crm_ops_collapse"])
        or bool(data["historical_regression_loss"])
        or bool(data["product_default_changed"])
    )
    engaged = bool(data["result_return_entry_engaged"])
    complete = (
        bool(data["directory_preserved"])
        and bool(data["lab_mechanism_gate"])
        and bool(data["lab_zero_guard_loss"])
        and bool(data["forum_full_transfer"])
        and bool(data["billing_full_transfer"])
        and bool(data["crm_preserved"])
        and bool(data["ops_preserved"])
        and bool(data["deep_no_horizon_drain"])
        and bool(data["deep_guard_retained"])
        and bool(data["deep_states_ok"])
        and bool(data["deep_urls_ok"])
        and bool(data["deep_return_success_ok"])
        and bool(data["deep_horizon_bypass_ok"])
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
        "inspected_repair_only": True,
        "result_return_entry_engaged": engaged,
        "outcome_a_complete": complete and not harmful,
        "guard_confirmed_reference": {
            "lab": list(LAB_GUARD),
            "deepbench": list(DEEP_GUARD),
            **{name: list(GUARD_CONFIRMED[name]) for name in REGRESSION_APPS},
        },
    }


__all__ = [
    "DEEP_GUARD",
    "LAB_GUARD",
    "REGRESSION_APPS",
    "V0318_DEEP_STATE_COLLAPSE",
    "confirmed_of",
    "deep_coverage_ok",
    "derive_v0319_outcome",
    "directory_preserved_v0319",
    "lab_mechanism_gate",
    "lost_vs",
    "mechanism_preserved",
    "new_guard_losses",
    "passing_facts",
    "transfer_preserved",
    "trigger_counts_match",
]
