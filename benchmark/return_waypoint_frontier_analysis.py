"""v0.3.21 outcome gate. Does not choose exploration actions."""
from __future__ import annotations

OUTCOME_MEANING = {
    "A": (
        "Return-Waypoint Frontier Escape repairs the inspected systematic "
        "v0.3.20 fresh regression by preventing a handoff-resolved outer return "
        "from starving known residual frontier at an intermediate waypoint, "
        "while preserving the specified composite and historical suite"
    ),
    "B": (
        "Safety and protocol pass and the waypoint escape engages on at least "
        "three of four inspected positives, but the repair or transfer gate "
        "is incomplete"
    ),
    "C": "unsafe, harmful, or protocol-invalid",
    "D": (
        "Safety and protocol pass, but the preregistered resumed-return "
        "waypoint mechanism does not engage on three of four inspected positives"
    ),
}

POSITIVE = ("buggy-campus", "buggy-warehouse", "buggy-studio", "buggy-booking")
HISTORICAL_STARVATION_INDEX = 22


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def passing_facts() -> dict:
    """Synthetic inputs that satisfy Outcome A. Tests mutate a copy."""
    return {
        "candidate_freeze_ok": True,
        "historical_freeze_ok": True,
        "protocol_ok": True,
        "historical_source_mutation": False,
        "post_freeze_edit": False,
        "safety_ok": True,
        "w_series_ok": True,
        "model_ok": True,
        "model_invariant_failures": 0,
        "model_raw_traces": 37448,
        "historical_models_ok": True,
        "app_specific": False,
        "product_default_changed": False,
        "waypoint_scope_violation": False,
        "waypoint_parent_escape": False,
        "waypoint_depth_escape": False,
        "waypoint_unknown_hub_escape": False,
        "escape_false_success": False,
        "escape_emitted_returned": False,
        "duplicate_terminal": False,
        "repeat_escape": False,
        "waypoint_accounting_violations": 0,
        "witness_terminal_trigger_violations": 0,
        "horizon_only_drain_count": 0,
        "catalog_waypoint_escapes": 0,
        "kiosk_waypoint_escapes": 0,
        "catalog_safety_failure": False,
        "kiosk_safety_failure": False,
        "historical_guard_loss": [],
        "regression_vs_v0320_f": [],
        "crm_ops_collapse": False,
        "control_selectivity_failure": False,
        "waypoint_reached_count": 4,
        "residual_escape_count": 4,
        "mechanism_engaged_count": 4,
        "positives_fully_recovered": 4,
        "template_589_recovered": 4,
        "nested_transfer_ok": True,
        "finding_provenance_ok": True,
        "lab_retained": True,
        "deep_retained": True,
        "forum_billing_ok": True,
        "directory_ok": True,
        "crm_ops_ok": True,
        "desk_wiki_shop_ok": True,
    }


def derive_v0321_outcome(**facts) -> dict:
    """Preregistered order: C, then D, then B, else A.

    A remaining template 5/8/9 miss on an inspected positive is a partial
    repair when the mechanism engaged and v0.3.20 F's own confirmed bugs
    were kept. Losing a bug v0.3.20 F already confirmed, or any listed
    historical Guard bug, is C.
    """
    data = passing_facts()
    data.update(facts)
    historical_loss = list(data.get("historical_guard_loss") or [])
    regression = list(data.get("regression_vs_v0320_f") or [])
    engaged = _int(data.get("mechanism_engaged_count"))
    reached = _int(data.get("waypoint_reached_count"))
    escaped = _int(data.get("residual_escape_count"))
    harmful = (
        not data["candidate_freeze_ok"]
        or not data["historical_freeze_ok"]
        or not data["protocol_ok"]
        or bool(data["historical_source_mutation"])
        or bool(data["post_freeze_edit"])
        or not data["safety_ok"]
        or not data["w_series_ok"]
        or not data["model_ok"]
        or not data["historical_models_ok"]
        or _int(data["model_invariant_failures"]) > 0
        or _int(data["model_raw_traces"]) != 37448
        or bool(data["app_specific"])
        or bool(data["product_default_changed"])
        or bool(data["waypoint_scope_violation"])
        or bool(data["waypoint_parent_escape"])
        or bool(data["waypoint_depth_escape"])
        or bool(data["waypoint_unknown_hub_escape"])
        or bool(data["escape_false_success"])
        or bool(data["escape_emitted_returned"])
        or bool(data["duplicate_terminal"])
        or bool(data["repeat_escape"])
        or _int(data["waypoint_accounting_violations"]) > 0
        or _int(data["witness_terminal_trigger_violations"]) > 0
        or _int(data["horizon_only_drain_count"]) > 0
        or _int(data["catalog_waypoint_escapes"]) > 0
        or _int(data["kiosk_waypoint_escapes"]) > 0
        or bool(data["catalog_safety_failure"])
        or bool(data["kiosk_safety_failure"])
        or bool(data["control_selectivity_failure"])
        or bool(historical_loss)
        or bool(regression)
        or bool(data["crm_ops_collapse"])
        or not data["lab_retained"]
        or not data["deep_retained"]
        or not data["forum_billing_ok"]
        or not data["directory_ok"]
        or not data["crm_ops_ok"]
        or not data["desk_wiki_shop_ok"]
    )
    mechanism_short = reached < 3 or escaped < 3 or engaged < 3
    complete = (
        engaged >= 3
        and _int(data["positives_fully_recovered"]) == 4
        and _int(data["template_589_recovered"]) == 4
        and bool(data["nested_transfer_ok"])
        and bool(data["finding_provenance_ok"])
        and _int(data["horizon_only_drain_count"]) == 0
        and _int(data["catalog_waypoint_escapes"]) == 0
        and _int(data["kiosk_waypoint_escapes"]) == 0
        and bool(data["lab_retained"])
        and bool(data["deep_retained"])
        and bool(data["forum_billing_ok"])
        and bool(data["directory_ok"])
        and bool(data["crm_ops_ok"])
        and bool(data["desk_wiki_shop_ok"])
        and _int(data["waypoint_accounting_violations"]) == 0
        and _int(data["witness_terminal_trigger_violations"]) == 0
        and not data["app_specific"]
        and not data["product_default_changed"]
    )
    if harmful:
        outcome = "C"
    elif mechanism_short:
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
        "inspected_repair": True,
        "mechanism_engaged_count": engaged,
        "waypoint_reached_count": reached,
        "residual_escape_count": escaped,
        "positives_fully_recovered": _int(data["positives_fully_recovered"]),
        "historical_guard_loss": historical_loss,
        "regression_vs_v0320_f": regression,
        "outcome_a_complete": outcome == "A",
    }


__all__ = [
    "HISTORICAL_STARVATION_INDEX",
    "OUTCOME_MEANING",
    "POSITIVE",
    "derive_v0321_outcome",
    "passing_facts",
]
