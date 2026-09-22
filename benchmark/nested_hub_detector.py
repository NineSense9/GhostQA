"""Measurement-only nested-hub preemption detector.

Identifies an open sequence terminated lost_parent at a hub branch click
before that instance reached horizon or return. Does not affect exploration
decisions, does not read bug manifests, and does not hardcode historical
counts.
"""
from __future__ import annotations

from benchmark.application_shape_evidence import steps_only


def _index_by_step(seq_events: list) -> dict:
    by_step: dict = {}
    for i, event in enumerate(seq_events or []):
        step = event.get("step")
        if step is None:
            continue
        by_step.setdefault(int(step), []).append((i, event))
    return by_step


def _ledger_before(step_events: list, step: int) -> dict | None:
    """Pre-after ledger. on_step snapshots the controller before sequence.after."""
    for record in steps_only(step_events or []):
        if record.get("index") == step and "commitment_left" in record:
            return record
    return None


def detect_nested_hub_preemptions(seq_events: list,
                                  step_events: list | None = None) -> list:
    """Return structured preemption records, in event order.

    A preemption is a sequence_terminal outcome=lost_parent for an instance
    that, at that step, is on a hub branch click and has not yet emitted
    sequence_horizon_reached or return_attempt.

    commitment_window is true only when the pre-after step ledger shows
    returning false and commitment_left > 0. Missing ledgers stay false
    and set commitment_known false.
    """
    events = list(seq_events or [])
    by_step = _index_by_step(events)
    starts: dict = {}
    horizon_at: dict = {}
    return_at: dict = {}
    out = []

    for index, event in enumerate(events):
        kind = event.get("event")
        iid = event.get("sequence_instance_id")
        if kind == "branch_start" and iid and iid not in starts:
            starts[iid] = event
        elif kind == "sequence_horizon_reached" and iid and iid not in horizon_at:
            horizon_at[iid] = index
        elif kind == "return_attempt" and iid and iid not in return_at:
            return_at[iid] = index
        if kind != "sequence_terminal" or event.get("outcome") != "lost_parent":
            continue
        if not iid:
            continue
        step = event.get("step")
        same = [item for item in by_step.get(int(step), [])] if step is not None else []
        hub_seen = any(
            item[0] <= index and item[1].get("event") == "hub_seen"
            for item in same
        )
        new_start = None
        for item_index, item in same:
            if item.get("event") != "branch_start":
                continue
            if item.get("sequence_instance_id") == iid:
                continue
            if item_index >= index or new_start is None:
                new_start = item
                if item_index >= index:
                    break
        discovered = None
        for item_index, item in same:
            if item.get("event") == "branch_discovered" and item_index <= index:
                discovered = item
        origin = starts.get(iid) or {}
        horizon_before = iid in horizon_at and horizon_at[iid] < index
        return_before = iid in return_at and return_at[iid] < index
        if not (hub_seen and new_start is not None and not horizon_before
                and not return_before):
            continue
        ledger = _ledger_before(step_events or [], int(step)) if step is not None else None
        commitment = None if ledger is None else ledger.get("commitment_left")
        returning = None if ledger is None else bool(ledger.get("returning"))
        known = ledger is not None and commitment is not None
        window = bool(known and returning is False and int(commitment) > 0)
        action = (ledger or {}).get("action") or {}
        out.append({
            "step": step,
            "sequence_instance_id": iid,
            "outer_branch": event.get("branch_key") or origin.get("branch_key") or "",
            "outer_parent_hub_sig": origin.get("exact_sig") or "",
            "outer_parent_hub_cluster": origin.get("cluster_id") or "",
            "nested_hub_sig": event.get("exact_sig") or "",
            "nested_hub_cluster": event.get("cluster_id") or "",
            "nested_branch_key": (new_start or {}).get("branch_key")
            or (discovered or {}).get("branch_key") or "",
            "nested_action": action,
            "commitment_left": commitment,
            "returning_before": returning,
            "commitment_known": known,
            "commitment_window": window,
            "terminal_outcome": "lost_parent",
            "horizon_before_terminal": horizon_before,
            "return_attempt_before_terminal": return_before,
        })
    return out


def count_events(seq_events: list, name: str) -> int:
    return sum(1 for event in seq_events or [] if event.get("event") == name)


def summarize_preemptions(seq_events: list, step_events: list | None = None) -> dict:
    rows = detect_nested_hub_preemptions(seq_events, step_events)
    return {
        "preemptions": len(rows),
        "commitment_window_preemptions": sum(
            1 for row in rows if row.get("commitment_window")),
        "unknown_commitment_preemptions": sum(
            1 for row in rows if not row.get("commitment_known")),
        "sequence_lost_parent": sum(
            1 for event in seq_events or []
            if event.get("event") == "sequence_terminal"
            and event.get("outcome") == "lost_parent"),
        "sequence_horizon_reached": count_events(
            seq_events, "sequence_horizon_reached"),
        "return_attempt_events": count_events(seq_events, "return_attempt"),
        "branch_start_events": count_events(seq_events, "branch_start"),
        "examples": rows[:3],
    }
