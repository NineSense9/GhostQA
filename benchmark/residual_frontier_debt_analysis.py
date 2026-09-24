"""v0.3.23 outcome gate. Does not choose exploration actions."""
from __future__ import annotations

OUTCOME_MEANING = {
    "A": (
        "Residual Frontier Debt Escape repairs the inspected closed-SCC "
        "post-terminal starvation on Campus and Studio while preserving the "
        "specified productive targets, controls, and historical suite"
    ),
    "B": (
        "Safety and protocol pass and the debt relocation engages on at least "
        "one of Campus or Studio, but the repair or preservation gate is incomplete"
    ),
    "C": "unsafe, harmful, or protocol-invalid",
    "D": (
        "Safety and protocol pass, but the preregistered residual-debt "
        "relocation does not engage on Campus or Studio"
    ),
}

MODEL_RAW_TRACES = 66429


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def passing_facts() -> dict:
    """Synthetic inputs that satisfy Outcome A. Tests mutate a copy."""
    return {
        "protocol_ok": True,
        "candidate_freeze_ok": True,
        "historical_freeze_ok": True,
        "historical_source_mutation": False,
        "target_generator_changed": False,
        "post_freeze_edit": False,
        "safety_ok": True,
        "rd_series_ok": True,
        "model_ok": True,
        "model_invariant_failures": 0,
        "model_raw_traces": MODEL_RAW_TRACES,
        "historical_models_ok": True,
        "app_specific": False,
        "product_default_changed": False,
        "relocation_lifecycle_violations": 0,
        "relocation_open_scc_violations": 0,
        "relocation_pending_scc_violations": 0,
        "relocation_without_debt": 0,
        "relocation_inside_scc": 0,
        "replay_path_invalid": 0,
        "restore_sequence_violations": 0,
        "arrival_clears_debt": 0,
        "consumption_violations": 0,
        "false_success_violations": 0,
        "zero_normal_loop_violations": 0,
        "guard_bug_loss": [],
        "campus_engaged": True,
        "studio_engaged": True,
        "campus_mechanism": True,
        "studio_mechanism": True,
        "campus_589": True,
        "studio_589": True,
        "campus_guard_loss": False,
        "studio_guard_loss": False,
        "warehouse_guard_loss": False,
        "booking_guard_loss": False,
        "warehouse_589": True,
        "booking_589": True,
        "warehouse_harmful_relocation": False,
        "booking_harmful_relocation": False,
        "catalog_relocations": 0,
        "kiosk_relocations": 0,
        "kiosk_nested_handoff": 0,
        "historical_ok": True,
    }


def derive_v0323_outcome(**facts) -> dict:
    """Preregistered order: C, then D, then B, else A."""
    data = passing_facts()
    data.update(facts)
    loss = list(data.get("guard_bug_loss") or [])
    harmful = (
        not data["protocol_ok"]
        or not data["candidate_freeze_ok"]
        or not data["historical_freeze_ok"]
        or bool(data["historical_source_mutation"])
        or bool(data["target_generator_changed"])
        or bool(data["post_freeze_edit"])
        or not data["safety_ok"]
        or not data["rd_series_ok"]
        or not data["model_ok"]
        or not data["historical_models_ok"]
        or _int(data["model_invariant_failures"]) > 0
        or _int(data["model_raw_traces"]) != MODEL_RAW_TRACES
        or bool(data["app_specific"])
        or bool(data["product_default_changed"])
        or _int(data["relocation_lifecycle_violations"]) > 0
        or _int(data["relocation_open_scc_violations"]) > 0
        or _int(data["relocation_pending_scc_violations"]) > 0
        or _int(data["relocation_without_debt"]) > 0
        or _int(data["relocation_inside_scc"]) > 0
        or _int(data["replay_path_invalid"]) > 0
        or _int(data["restore_sequence_violations"]) > 0
        or _int(data["arrival_clears_debt"]) > 0
        or _int(data["consumption_violations"]) > 0
        or _int(data["false_success_violations"]) > 0
        or _int(data["zero_normal_loop_violations"]) > 0
        or bool(loss)
        or bool(data["campus_guard_loss"])
        or bool(data["studio_guard_loss"])
        or bool(data["warehouse_guard_loss"])
        or bool(data["booking_guard_loss"])
        or bool(data["warehouse_harmful_relocation"])
        or bool(data["booking_harmful_relocation"])
        or _int(data["catalog_relocations"]) > 0
        or _int(data["kiosk_relocations"]) > 0
        or not data["historical_ok"]
    )
    engaged = bool(data["campus_engaged"]) or bool(data["studio_engaged"])
    complete = (
        bool(data["campus_mechanism"])
        and bool(data["studio_mechanism"])
        and bool(data["campus_589"])
        and bool(data["studio_589"])
        and not data["campus_guard_loss"]
        and not data["studio_guard_loss"]
        and not data["warehouse_guard_loss"]
        and not data["booking_guard_loss"]
        and bool(data["warehouse_589"])
        and bool(data["booking_589"])
        and not data["warehouse_harmful_relocation"]
        and not data["booking_harmful_relocation"]
        and _int(data["catalog_relocations"]) == 0
        and _int(data["kiosk_relocations"]) == 0
        and _int(data["kiosk_nested_handoff"]) == 0
        and bool(data["historical_ok"])
        and not data["app_specific"]
        and not data["product_default_changed"]
        and _int(data["relocation_lifecycle_violations"]) == 0
        and _int(data["consumption_violations"]) == 0
        and _int(data["false_success_violations"]) == 0
        and _int(data["restore_sequence_violations"]) == 0
        and _int(data["zero_normal_loop_violations"]) == 0
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
        "inspected_repair": True,
        "campus_engaged": bool(data["campus_engaged"]),
        "studio_engaged": bool(data["studio_engaged"]),
        "guard_bug_loss": loss,
        "outcome_a_complete": outcome == "A",
    }


__all__ = [
    "MODEL_RAW_TRACES",
    "OUTCOME_MEANING",
    "derive_v0323_outcome",
    "passing_facts",
]
