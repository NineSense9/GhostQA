"""v0.3.25 outcome gate. Written before any fresh policy result."""
from __future__ import annotations

OUTCOME_MEANING = {
    "A": "The frozen v0.3.24 candidate transfers to at least three new positive applications, preserves Guard bugs, and keeps the negative controls free of nested handoff",
    "B": "Safety and Guard preservation hold and at least three positives are evaluable, but fewer than three reach the preregistered structure while keeping Guard bugs",
    "C": "unsafe, harmful, or protocol-invalid",
    "D": "Safety holds, but fewer than three new positives are structurally evaluable",
}


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def passing_facts() -> dict:
    return {
        "protocol_ok": True,
        "suite_freeze_ok": True,
        "candidate_freeze_ok": True,
        "candidate_edited": False,
        "product_default_changed": False,
        "app_specific": False,
        "fresh_guard_loss": [],
        "historical_guard_loss": [],
        "episode_without_relocation": 0,
        "cross_hub_invalidations": 0,
        "restore_probes": 0,
        "negative_handoff": 0,
        "evaluable_positives": 4,
        "structured_positives": 4,
    }


def derive_v0325_outcome(**facts) -> dict:
    data = passing_facts()
    data.update(facts)
    harmful = (
        not data["protocol_ok"]
        or not data["suite_freeze_ok"]
        or not data["candidate_freeze_ok"]
        or bool(data["candidate_edited"])
        or bool(data["product_default_changed"])
        or bool(data["app_specific"])
        or bool(data["fresh_guard_loss"])
        or bool(data["historical_guard_loss"])
        or _int(data["episode_without_relocation"]) > 0
        or _int(data["cross_hub_invalidations"]) > 0
        or _int(data["restore_probes"]) > 0
        or _int(data["negative_handoff"]) > 0
    )
    evaluable = _int(data["evaluable_positives"])
    structured = _int(data["structured_positives"])
    if harmful:
        outcome = "C"
    elif evaluable < 3:
        outcome = "D"
    elif structured < 3:
        outcome = "B"
    else:
        outcome = "A"
    return {
        "outcome": outcome,
        "outcome_meaning": OUTCOME_MEANING[outcome],
        "promotion_readiness": "not_ready",
        "fresh_validation": True,
        "product_default_changed": bool(data["product_default_changed"]),
    }
