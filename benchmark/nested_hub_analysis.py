"""v0.3.12 mechanism-repair gates. Measurement and outcome only.

The branching in derive_v0312_outcome is the preregistered A/B/C/D rule.
It does not read bug manifests and does not choose exploration actions.
"""
from __future__ import annotations

from benchmark.fresh_transfer_analysis import normalize_url
from benchmark.nested_hub_detector import (
    count_events, detect_nested_hub_preemptions,
)
from benchmark.return_cycle_accounting import classify_escape_lifecycle
from benchmark.application_shape_evidence import steps_only

MIN_EXHAUSTIVE_TRACES = 5800

OUTCOME_MEANING = {
    "A": "mechanism repaired, regression-safe",
    "B": "partial mechanism repair",
    "C": "harmful/regression",
    "D": "no demonstrated effect / mechanism mismatch",
}

REGRESSION_CASES = ("wiki", "buggy-desk", "buggy-shop", "deepbench")


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def horizon_or_terminal_after_followup(seq_events: list) -> bool:
    """Horizon, finding, or crash for the preserved instance after a follow-up."""
    events = list(seq_events or [])
    for index, event in enumerate(events):
        if event.get("event") != "nested_branch_followup":
            continue
        iid = event.get("sequence_instance_id")
        for later in events[index + 1:]:
            if iid and later.get("sequence_instance_id") not in (iid, None):
                continue
            if iid and later.get("sequence_instance_id") != iid:
                continue
            if later.get("event") == "sequence_horizon_reached":
                return True
            if (later.get("event") == "sequence_terminal"
                    and later.get("outcome") in ("finding", "crash")):
                return True
    return False


def reached_return_phase(seq_events: list) -> bool:
    for event in seq_events or []:
        if event.get("event") in ("return_attempt", "return_cycle_escape"):
            return True
        if (event.get("event") == "sequence_terminal"
                and event.get("outcome") == "returned"):
            return True
    return False


def preservation_parent_intact(seq_events: list) -> bool:
    """Outer parent recorded on each follow-up still matches that instance.

    A later branch_start for a different instance before the outer instance
    reaches horizon or a terminal means the parent was overwritten.
    """
    events = list(seq_events or [])
    origins = {}
    for event in events:
        if event.get("event") == "branch_start" and event.get("sequence_instance_id"):
            iid = event["sequence_instance_id"]
            origins.setdefault(iid, event)
    for index, event in enumerate(events):
        if event.get("event") != "nested_branch_followup":
            continue
        iid = event.get("sequence_instance_id")
        origin = origins.get(iid) or {}
        if event.get("outer_parent_hub_sig") != (origin.get("exact_sig") or ""):
            return False
        if event.get("outer_parent_hub_cluster") != (origin.get("cluster_id") or ""):
            return False
        if event.get("outer_branch") != (origin.get("branch_key") or ""):
            return False
        if _int(event.get("commitment_left_before")) <= 0:
            return False
        for later in events[index + 1:]:
            if (later.get("sequence_instance_id") == iid
                    and later.get("event") in (
                        "sequence_horizon_reached", "sequence_terminal")):
                break
            if (later.get("event") == "branch_start"
                    and later.get("sequence_instance_id") != iid):
                return False
    return True


def candidate_accounting_inflation(seq_events: list) -> bool:
    """Returned/completed inflation, double terminals, or escape counted returned."""
    life = classify_escape_lifecycle(seq_events)
    if life.get("return_inflation_events"):
        return True
    if int(life.get("unclassified") or 0) > 0:
        return True
    per_instance: dict = {}
    for event in seq_events or []:
        if event.get("event") != "sequence_terminal":
            continue
        iid = event.get("sequence_instance_id")
        per_instance.setdefault(iid, []).append(event.get("outcome") or "")
    for outcomes in per_instance.values():
        for name in ("finding", "crash", "returned", "return_cycle_abandoned"):
            if outcomes.count(name) > 1:
                return True
        if "returned" in outcomes and "return_cycle_abandoned" in outcomes:
            return True
    return False


def is_mechanism_repair(cell: dict) -> bool:
    return (
        _int(cell.get("historical_preemptions")) >= 1
        and _int(cell.get("nested_branch_followup_events")) >= 1
        and _int(cell.get("commitment_window_preemptions")) == 0
        and bool(cell.get("reached_horizon_or_terminal_after_followup"))
        and bool(cell.get("reached_return_phase"))
        and bool(cell.get("expanded_beyond_historical"))
    )


def preemption_eliminated(cell: dict) -> bool:
    return (
        _int(cell.get("historical_preemptions")) >= 1
        and _int(cell.get("commitment_window_preemptions")) == 0
    )


def assess_target(guard_seq: list, guard_steps: list, nested_seq: list,
                  nested_steps: list, *, guard_states: int, guard_urls: int,
                  nested_states: int, nested_urls: int) -> dict:
    """One inspected target at the primary budget. G is historical, N is candidate."""
    historical = detect_nested_hub_preemptions(guard_seq, guard_steps)
    candidate = detect_nested_hub_preemptions(nested_seq, nested_steps)
    window = sum(1 for row in candidate if row.get("commitment_window"))
    cell = {
        "historical_preemptions": len(historical),
        "historical_commitment_window_preemptions": sum(
            1 for row in historical if row.get("commitment_window")),
        "historical_return_attempt_events": count_events(
            guard_seq, "return_attempt"),
        "historical_horizon": count_events(guard_seq, "sequence_horizon_reached"),
        "historical_lost_parent": sum(
            1 for event in guard_seq or []
            if event.get("event") == "sequence_terminal"
            and event.get("outcome") == "lost_parent"),
        "historical_states": guard_states,
        "historical_urls": guard_urls,
        "nested_branch_followup_events": count_events(
            nested_seq, "nested_branch_followup"),
        "commitment_window_preemptions": window,
        "nested_lost_parent": sum(
            1 for event in nested_seq or []
            if event.get("event") == "sequence_terminal"
            and event.get("outcome") == "lost_parent"),
        "nested_horizon": count_events(nested_seq, "sequence_horizon_reached"),
        "nested_return_attempt_events": count_events(nested_seq, "return_attempt"),
        "nested_returned": sum(
            1 for event in nested_seq or []
            if event.get("event") == "sequence_terminal"
            and event.get("outcome") == "returned"),
        "nested_escapes": count_events(nested_seq, "return_cycle_escape"),
        "nested_states": nested_states,
        "nested_urls": nested_urls,
        "reached_horizon_or_terminal_after_followup": (
            horizon_or_terminal_after_followup(nested_seq)),
        "reached_return_phase": reached_return_phase(nested_seq),
        "expanded_beyond_historical": (
            int(nested_states) > int(guard_states)
            or int(nested_urls) > int(guard_urls)),
        "parent_intact": preservation_parent_intact(nested_seq),
        "return_inflation": candidate_accounting_inflation(nested_seq),
    }
    cell["mechanism_repair"] = is_mechanism_repair(cell)
    cell["preemption_eliminated"] = preemption_eliminated(cell)
    return cell


def lost_confirmed_cases(lost_confirmed: dict | None) -> list:
    lost = []
    for name in REGRESSION_CASES:
        bugs = (lost_confirmed or {}).get(name) or []
        if list(bugs):
            lost.append(name)
    for name, bugs in (lost_confirmed or {}).items():
        if name not in REGRESSION_CASES and list(bugs or []):
            lost.append(name)
    return lost


def derive_v0312_outcome(
    *,
    candidate_freeze_ok: bool,
    historical_freezes_ok: bool,
    n_series_failures: int,
    s1_s7_pass: bool,
    exhaustive_failures: int,
    exhaustive_traces: int,
    crm: dict,
    ops: dict,
    return_inflation: bool,
    parent_corruption: bool,
    app_specific_logic: bool,
    product_default_changed: bool,
    lost_confirmed: dict | None,
    detector_historical_ok: bool,
) -> dict:
    """Preregistered v0.3.12 Outcome A/B/C/D.

    C is evaluated first. D is used only when safety holds and the historical
    preemption is missing or the candidate removes it on neither mechanism case.
    """
    lost_names = lost_confirmed_cases(lost_confirmed)
    safety_failure = (
        not candidate_freeze_ok
        or not historical_freezes_ok
        or _int(n_series_failures) > 0
        or not s1_s7_pass
        or _int(exhaustive_failures) > 0
        or _int(exhaustive_traces) < MIN_EXHAUSTIVE_TRACES
        or bool(return_inflation)
        or bool(parent_corruption)
        or bool(app_specific_logic)
        or bool(product_default_changed)
        or bool(lost_names)
    )
    crm_repair = is_mechanism_repair(crm or {})
    ops_repair = is_mechanism_repair(ops or {})
    crm_elim = preemption_eliminated(crm or {})
    ops_elim = preemption_eliminated(ops or {})
    if safety_failure:
        outcome = "C"
    elif not detector_historical_ok:
        outcome = "D"
    elif not crm_elim and not ops_elim:
        outcome = "D"
    elif crm_repair and ops_repair:
        outcome = "A"
    else:
        outcome = "B"
    return {
        "outcome": outcome,
        "outcome_meaning": OUTCOME_MEANING[outcome],
        "product_default_changed": bool(product_default_changed),
        "generalization_claim": False,
        "crm_repair": crm_repair,
        "ops_repair": ops_repair,
        "crm_preemption_eliminated": crm_elim,
        "ops_preemption_eliminated": ops_elim,
        "lost_confirmed_cases": lost_names,
        "safety_failure": safety_failure,
        "detector_historical_ok": bool(detector_historical_ok),
    }


def _first(seq_events: list, name: str, *, after_index: int = -1,
           instance_id: str = "") -> dict | None:
    for index, event in enumerate(seq_events or []):
        if index <= after_index:
            continue
        if event.get("event") != name:
            continue
        if instance_id and event.get("sequence_instance_id") not in (
                instance_id, None):
            continue
        return event
    return None


def lifecycle_markers(seq_events: list, step_events: list | None = None) -> dict:
    """Compact audit of the first preserved nested traversal. Reporting only."""
    events = list(seq_events or [])
    follow = _first(events, "nested_branch_followup")
    if follow is None:
        return {
            "first_nested_followup_step": None,
            "first_horizon_step_after_followup": None,
            "first_return_attempt_step": None,
            "first_escape_step": None,
            "first_novel_state_step_after_followup": None,
            "first_novel_url_after_followup": None,
            "first_novel_url_step_after_followup": None,
        }
    follow_index = events.index(follow)
    iid = follow.get("sequence_instance_id") or ""
    horizon = None
    for event in events[follow_index + 1:]:
        if event.get("event") != "sequence_horizon_reached":
            continue
        if iid and event.get("sequence_instance_id") not in (iid, None):
            continue
        horizon = event
        break
    ret = _first(events, "return_attempt", after_index=follow_index)
    esc = _first(events, "return_cycle_escape", after_index=follow_index)
    follow_step = follow.get("step")
    seen_sigs = set()
    seen_urls = set()
    novel_state_step = None
    novel_url = None
    novel_url_step = None
    for record in steps_only(step_events or []):
        idx = record.get("index")
        if idx is None or follow_step is None:
            continue
        url = normalize_url(record.get("dst_url") or "")
        src_url = normalize_url(record.get("src_url") or "")
        if int(idx) < int(follow_step):
            if record.get("src_sig"):
                seen_sigs.add(record.get("src_sig"))
            if record.get("dst_sig"):
                seen_sigs.add(record.get("dst_sig"))
            if url:
                seen_urls.add(url)
            if src_url:
                seen_urls.add(src_url)
            continue
        dst = record.get("dst_sig") or ""
        if (novel_state_step is None and record.get("dst_is_new")
                and dst and dst not in seen_sigs):
            novel_state_step = idx
        if novel_url_step is None and url and url not in seen_urls:
            novel_url = url
            novel_url_step = idx
        if dst:
            seen_sigs.add(dst)
        if url:
            seen_urls.add(url)
        if src_url:
            seen_urls.add(src_url)
    return {
        "first_nested_followup_step": follow_step,
        "first_horizon_step_after_followup": None if horizon is None else horizon.get("step"),
        "first_return_attempt_step": None if ret is None else ret.get("step"),
        "first_escape_step": None if esc is None else esc.get("step"),
        "first_novel_state_step_after_followup": novel_state_step,
        "first_novel_url_after_followup": novel_url,
        "first_novel_url_step_after_followup": novel_url_step,
        "outer_sequence_instance_id": iid,
        "outer_branch": follow.get("outer_branch") or follow.get("branch_key") or "",
        "outer_parent_hub_sig": follow.get("outer_parent_hub_sig") or "",
        "commitment_left_before": follow.get("commitment_left_before"),
    }
