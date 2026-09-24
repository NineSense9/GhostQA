"""v0.3.24 outcome gate. Does not choose exploration actions."""
from __future__ import annotations

OUTCOME_MEANING = {
    "A": (
        "Episode-scoped revalidation of same-hub local drain memory repairs "
        "the inspected reset-staleness loss on Campus and Studio while "
        "preserving the specified productive, control, and historical suite"
    ),
    "B": (
        "Safety and protocol pass and the episode mechanism engages on at "
        "least one diagnosed target, but the repair or preservation gate is incomplete"
    ),
    "C": "unsafe, harmful, or protocol-invalid",
    "D": (
        "Safety and protocol pass, but the episode mechanism does not engage "
        "on the diagnosed relocation targets"
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
        "post_freeze_edit": False,
        "safety_ok": True,
        "ee_series_ok": True,
        "model_ok": True,
        "historical_models_ok": True,
        "model_invariant_failures": 0,
        "model_raw_traces": MODEL_RAW_TRACES,
        "app_specific": False,
        "product_default_changed": False,
        "episode_without_relocation": 0,
        "cross_hub_invalidations": 0,
        "structural_memory_cleared": False,
        "restore_probe_violations": 0,
        "new_drain_trigger": False,
        "forced_action": False,
        "duplicate_same_episode": 0,
        "false_success": 0,
        "guard_bug_loss": [],
        "catalog_episode_advances": 0,
        "catalog_revalidated": 0,
        "catalog_relocations": 0,
        "kiosk_episode_advances": 0,
        "kiosk_revalidated": 0,
        "kiosk_relocations": 0,
        "deep_episode_advances": 0,
        "deep_relocations": 0,
        "deep_retained": True,
        "campus_engaged": True,
        "studio_engaged": True,
        "campus_mechanism": True,
        "studio_mechanism": True,
        "campus_589": True,
        "studio_589": True,
        "campus_guard_loss": False,
        "studio_guard_loss": False,
        "warehouse_589": True,
        "booking_589": True,
        "warehouse_relocations": 0,
        "booking_relocations": 0,
        "warehouse_episode_advances": 0,
        "booking_episode_advances": 0,
        "warehouse_revalidated": 0,
        "booking_revalidated": 0,
        "warehouse_guard_loss": False,
        "booking_guard_loss": False,
        "historical_ok": True,
    }


def derive_v0324_outcome(**facts) -> dict:
    """Preregistered order: C, then D, then B, else A."""
    data = passing_facts()
    data.update(facts)
    loss = list(data.get("guard_bug_loss") or [])
    warehouse_unbacked = (
        _int(data["warehouse_episode_advances"]) > 0
        and _int(data["warehouse_relocations"]) <= 0
    )
    booking_unbacked = (
        _int(data["booking_episode_advances"]) > 0
        and _int(data["booking_relocations"]) <= 0
    )
    deep_unbacked = (
        _int(data["deep_episode_advances"]) > 0
        and _int(data["deep_relocations"]) <= 0
    )
    harmful = (
        not data["protocol_ok"]
        or not data["candidate_freeze_ok"]
        or not data["historical_freeze_ok"]
        or bool(data["historical_source_mutation"])
        or bool(data["post_freeze_edit"])
        or not data["safety_ok"]
        or not data["ee_series_ok"]
        or not data["model_ok"]
        or not data["historical_models_ok"]
        or _int(data["model_invariant_failures"]) > 0
        or _int(data["model_raw_traces"]) != MODEL_RAW_TRACES
        or bool(data["app_specific"])
        or bool(data["product_default_changed"])
        or _int(data["episode_without_relocation"]) > 0
        or _int(data["cross_hub_invalidations"]) > 0
        or bool(data["structural_memory_cleared"])
        or _int(data["restore_probe_violations"]) > 0
        or bool(data["new_drain_trigger"])
        or bool(data["forced_action"])
        or _int(data["duplicate_same_episode"]) > 0
        or _int(data["false_success"]) > 0
        or bool(loss)
        or bool(data["campus_guard_loss"])
        or bool(data["studio_guard_loss"])
        or bool(data["warehouse_guard_loss"])
        or bool(data["booking_guard_loss"])
        or not data["deep_retained"]
        or not data["historical_ok"]
        or warehouse_unbacked
        or booking_unbacked
        or deep_unbacked
        or _int(data["catalog_episode_advances"]) > 0
        or _int(data["catalog_revalidated"]) > 0
        or _int(data["catalog_relocations"]) > 0
        or _int(data["kiosk_episode_advances"]) > 0
        or _int(data["kiosk_revalidated"]) > 0
        or _int(data["kiosk_relocations"]) > 0
    )
    if harmful:
        outcome = "C"
    elif not data["campus_engaged"] and not data["studio_engaged"]:
        outcome = "D"
    elif not (
        data["campus_mechanism"]
        and data["studio_mechanism"]
        and data["campus_589"]
        and data["studio_589"]
        and data["warehouse_589"]
        and data["booking_589"]
        and _int(data["warehouse_episode_advances"]) == 0
        and _int(data["booking_episode_advances"]) == 0
        and _int(data["warehouse_relocations"]) == 0
        and _int(data["booking_relocations"]) == 0
        and _int(data["warehouse_revalidated"]) == 0
        and _int(data["booking_revalidated"]) == 0
        and _int(data["deep_episode_advances"]) == 0
        and data["campus_engaged"]
        and data["studio_engaged"]
    ):
        outcome = "B"
    else:
        outcome = "A"
    return {
        "outcome": outcome,
        "outcome_meaning": OUTCOME_MEANING[outcome],
        "promotion_readiness": "not_ready",
        "inspected_repair": True,
        "fresh_validation": False,
        "generalization_claim": False,
        "product_default_changed": bool(data["product_default_changed"]),
        "campus_engaged": bool(data["campus_engaged"]),
        "studio_engaged": bool(data["studio_engaged"]),
        "guard_bug_loss": loss,
        "outcome_a_complete": outcome == "A",
    }
