"""Trace checks for the preregistered v0.3.19 trigger gates.

Reads sequence events and browser steps after a run. Does not choose
exploration actions. Button ids are audit assertions, not candidate rules.
"""
from __future__ import annotations

from benchmark.fresh_transfer_analysis import normalize_url
from benchmark.return_entry_drain_trace import diagnose_lab as diagnose_return_entry_lab

RESULT_LOCAL = ("btn_close", "btn_reopen")
L9_ASSERT = "lab_reopen_clears"


def _named(events: list, name: str) -> list:
    return [event for event in events or [] if event.get("event") == name]


def _eid(key: str) -> str:
    text = str(key or "")
    marker = ":button:"
    if marker in text:
        return text.split(marker, 1)[1]
    return text


def _browser(steps: list, index: int) -> dict:
    for step in steps or []:
        if step.get("index") == index:
            return step
    return {}


def _assert_ids(step: dict) -> set:
    return {
        item.get("assert_id")
        for item in (step.get("findings") or [])
        if item.get("assert_id")
    }


def _on_result(steps: list, event: dict) -> bool:
    browser = _browser(steps, event.get("step"))
    dst = normalize_url(browser.get("dst_url") or "")
    src = normalize_url(browser.get("src_url") or "")
    if "result.html" in dst or "result.html" in src:
        return True
    visible = [_eid(key) for key in (event.get("visible_eligible_keys") or [])]
    return set(RESULT_LOCAL) <= set(visible)


def _step_events(events: list, step) -> list:
    return [event for event in events or [] if event.get("step") == step]


def horizon_only_drain_count(events: list) -> int:
    count = 0
    for start in _named(events, "return_entry_drain_started"):
        same = _step_events(events, start.get("step"))
        finding = any(
            event.get("event") == "sequence_terminal" and event.get("outcome") == "finding"
            for event in same
        )
        horizon = any(event.get("event") == "sequence_horizon_reached" for event in same)
        if horizon and not finding:
            count += 1
    return count


def nonfinding_drain_count(events: list) -> int:
    count = 0
    for start in _named(events, "return_entry_drain_started"):
        same = _step_events(events, start.get("step"))
        terminals = [
            event for event in same if event.get("event") == "sequence_terminal"
        ]
        finding = any(event.get("outcome") == "finding" for event in terminals)
        if terminals and not finding:
            count += 1
    return count


def horizon_only_steps(events: list) -> int:
    steps = set()
    for event in _named(events, "sequence_horizon_reached"):
        step = event.get("step")
        same = _step_events(events, step)
        finding = any(
            item.get("event") == "sequence_terminal" and item.get("outcome") == "finding"
            for item in same
        )
        if not finding:
            steps.add(step)
    return len(steps)


def trigger_consistency(events: list) -> dict:
    starts = _named(events, "return_entry_drain_started")
    triggers = _named(events, "finding_return_entry_trigger")
    mismatch = 0
    reused = 0
    wrong = 0
    seen = set()
    by_step = {}
    for event in triggers:
        by_step.setdefault(event.get("step"), []).append(event)
        key = (event.get("sequence_instance_id") or "", event.get("terminal_event_index"))
        if key in seen:
            reused += 1
        seen.add(key)
        if event.get("terminal_outcome") != "finding":
            mismatch += 1
        if event.get("provenance_mode") not in ("sequence_instance", "branch_step_fallback"):
            mismatch += 1
    for start in starts:
        rows = by_step.get(start.get("step")) or []
        if len(rows) != 1:
            mismatch += 1
            continue
        trigger = rows[0]
        if trigger.get("step") != start.get("step"):
            mismatch += 1
        if (trigger.get("branch_key") or "") != (start.get("active_branch") or start.get("branch_key") or ""):
            if trigger.get("branch_key") and start.get("active_branch"):
                wrong += 1
    if len(starts) != len(triggers):
        mismatch += 1
    return {
        "drain_starts": len(starts),
        "trigger_events": len(triggers),
        "counts_match": len(starts) == len(triggers) and mismatch == 0 and reused == 0 and wrong == 0,
        "mismatch": mismatch,
        "reused": reused,
        "wrong_instance": wrong,
        "horizon_only_drains": horizon_only_drain_count(events),
        "nonfinding_drains": nonfinding_drain_count(events),
        "horizon_bypass_events": len(_named(events, "finding_return_entry_horizon_bypassed")),
        "nonfinding_bypass_events": len(_named(events, "finding_return_entry_nonfinding_bypassed")),
        "horizon_only_steps": horizon_only_steps(events),
    }


def horizon_bypass_ok(events: list) -> bool:
    facts = trigger_consistency(events)
    if facts["horizon_only_drains"] or facts["nonfinding_drains"]:
        return False
    if facts["horizon_only_steps"] == 0:
        return True
    return facts["horizon_bypass_events"] >= 1


def diagnose_lab(events: list, steps: list | None = None, row: dict | None = None) -> dict:
    """Preregistered lab finding-trigger facts from one candidate trace."""
    base = diagnose_return_entry_lab(events, steps, row)
    steps = steps or []
    cell = row or {}
    starts = [
        event for event in _named(events, "return_entry_drain_started")
        if _on_result(steps, event) or (
            not steps and set(RESULT_LOCAL) & {_eid(key) for key in (event.get("visible_eligible_keys") or [])}
        )
    ]
    start = None if not starts else min(starts, key=lambda event: event.get("step") or 0)
    trigger = None
    finding_terminal = False
    if start is not None:
        same = _step_events(events, start.get("step"))
        finding_terminal = any(
            event.get("event") == "sequence_terminal" and event.get("outcome") == "finding"
            for event in same
        )
        for event in _named(events, "finding_return_entry_trigger"):
            if event.get("step") == start.get("step"):
                trigger = event
                break
    reopen_l9 = False
    if start is not None:
        for event in _named(events, "return_entry_probe_selected"):
            step = event.get("step")
            if not isinstance(step, int) or not isinstance(start.get("step"), int):
                continue
            if step <= start.get("step"):
                continue
            eid = event.get("eid") or _eid(event.get("key") or "")
            if eid == "btn_reopen" and L9_ASSERT in _assert_ids(_browser(steps, step)):
                reopen_l9 = True
    confirmed = set(cell.get("confirmed_bugs") or [])
    bug_l9 = "BUG-L9" in confirmed or reopen_l9
    trigger_ok = bool(
        trigger
        and trigger.get("terminal_outcome") == "finding"
        and trigger.get("step") == (None if start is None else start.get("step"))
        and finding_terminal
    )
    engaged = bool(
        base.get("result_hub_reached")
        and finding_terminal
        and trigger_ok
        and base.get("return_entry_drain_started_at_result")
        and base.get("result_button_probe_before_first_return")
    )
    facts = dict(base)
    facts.update({
        "finding_terminal_false_to_true": bool(finding_terminal and start is not None),
        "finding_return_entry_trigger_at_result": trigger_ok,
        "bug_l9_confirmed": bug_l9,
        "l9_assert_on_reopen_probe": reopen_l9,
        "result_return_entry_engaged": engaged,
        "trigger": {
            "present": trigger is not None,
            "step": None if trigger is None else trigger.get("step"),
            "outcome": None if trigger is None else trigger.get("terminal_outcome"),
            "provenance_mode": None if trigger is None else trigger.get("provenance_mode"),
            "branch_key": None if trigger is None else trigger.get("branch_key"),
        },
    })
    return facts


def diagnose_deep(events: list, row: dict | None = None) -> dict:
    """DeepBench horizon-boundary facts. No app-specific action choice."""
    cell = row or {}
    facts = trigger_consistency(events)
    return {
        "states": cell.get("states"),
        "urls": cell.get("normalized_unique_urls"),
        "return_success": cell.get("return_success"),
        "return_cycle_escape_events": cell.get("return_cycle_escape_events"),
        "confirmed_bugs": sorted(cell.get("confirmed_bugs") or []),
        "horizon_only_drains": facts["horizon_only_drains"],
        "finding_drains": facts["drain_starts"] - facts["horizon_only_drains"] - facts["nonfinding_drains"],
        "horizon_bypass_events": facts["horizon_bypass_events"],
        "horizon_only_steps": facts["horizon_only_steps"],
        "horizon_bypass_ok": horizon_bypass_ok(events),
        "trigger_counts_match": facts["counts_match"],
        "witness_violations": int(cell.get("witness_violations") or 0),
        "terminal_accounting_violations": int(cell.get("terminal_accounting_violations") or 0),
        "return_entry_accounting_violations": int(cell.get("return_entry_accounting_violations") or 0),
    }
