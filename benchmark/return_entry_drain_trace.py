"""Trace checks for the preregistered v0.3.18 lab mechanism gate.

Reads sequence events and browser steps after a run. Does not choose
exploration actions. Button ids are audit assertions, not candidate rules.
"""
from __future__ import annotations

from benchmark.fresh_transfer_analysis import normalize_url

RESULT_LOCAL = ("btn_close", "btn_reopen")
PROBE_EVENTS = (
    "return_entry_probe_completed",
    "return_entry_probe_left_hub",
    "return_entry_probe_finding",
)


def _eid(key: str) -> str:
    text = str(key or "")
    for marker in (":local-button:", ":button:", ":click:"):
        if marker in text:
            return text.split(marker, 1)[1]
    return text


def _named(events: list, name: str) -> list:
    return [event for event in events or [] if event.get("event") == name]


def _browser(steps: list, index: int) -> dict:
    for step in steps or []:
        if step.get("index") == index:
            return step
    return {}


def _url(step: dict, field: str) -> str:
    return normalize_url(step.get(field) or "")


def _result_step(step: dict) -> bool:
    return "result.html" in _url(step, "dst_url") or "result.html" in _url(step, "src_url")


def _visible(event: dict) -> list:
    return [_eid(key) for key in (event.get("visible_eligible_keys") or [])]


def _same(event: dict, start: dict, field: str):
    if field not in event or field not in start:
        return True
    return event.get(field) == start.get(field)


def diagnose_lab(events: list, steps: list | None = None, row: dict | None = None) -> dict:
    """Preregistered lab return-entry facts from one candidate trace."""
    cell = row or {}
    steps = steps or []
    result_reached = any("result.html" in _url(step, "dst_url") for step in steps)
    starts = []
    for event in _named(events, "return_entry_drain_started"):
        browser = _browser(steps, event.get("step"))
        on_result = bool(browser) and "result.html" in _url(browser, "dst_url")
        if on_result or (not steps and set(RESULT_LOCAL) & set(_visible(event))):
            starts.append(event)
    start = None if not starts else min(starts, key=lambda event: event.get("step") or 0)
    start_step = None if start is None else start.get("step")
    cluster = "" if start is None else (start.get("hub_cluster") or start.get("cluster_id") or "")
    later_returns = [
        event for event in _named(events, "return_attempt")
        if isinstance(event.get("step"), int) and isinstance(start_step, int)
        and event["step"] > start_step
    ]
    first_return = None if not later_returns else min(event["step"] for event in later_returns)
    selected = []
    probe_steps = set()
    attempt_mismatch = 0
    cycle_mismatch = 0
    success_mismatch = 0
    parent_mismatch = 0
    terminals_on_probe = 0
    escapes_on_probe = 0
    returns_on_probe = 0
    if start is not None:
        for event in events or []:
            step = event.get("step")
            if not isinstance(step, int) or not isinstance(start_step, int) or step <= start_step:
                continue
            if first_return is not None and step >= first_return:
                continue
            if cluster and (event.get("hub_cluster") or event.get("cluster_id") or "") not in (
                "", cluster,
            ):
                continue
            if event.get("event") == "return_entry_probe_selected":
                selected.append(event.get("eid") or _eid(event.get("key") or ""))
                probe_steps.add(step)
            if event.get("event") in PROBE_EVENTS or event.get("event") == "return_entry_probe_selected":
                probe_steps.add(step)
                if not _same(event, start, "return_attempts"):
                    attempt_mismatch += 1
                if not _same(event, start, "return_cycle_history_count"):
                    cycle_mismatch += 1
                if not _same(event, start, "return_success"):
                    success_mismatch += 1
                if (not _same(event, start, "active_branch")
                        or not _same(event, start, "parent_hub_sig")
                        or not _same(event, start, "parent_hub_cluster")):
                    parent_mismatch += 1
        probe_event_steps = {
            event.get("step") for event in events or []
            if event.get("event") in PROBE_EVENTS
            or event.get("event") == "return_entry_probe_selected"
        }
        probe_event_steps = {
            step for step in probe_event_steps
            if isinstance(step, int) and isinstance(start_step, int) and step > start_step
        }
        for event in events or []:
            if event.get("step") not in probe_steps and event.get("step") not in probe_event_steps:
                continue
            if event.get("event") == "sequence_terminal":
                terminals_on_probe += 1
            if event.get("event") == "return_cycle_escape":
                escapes_on_probe += 1
            if event.get("event") == "return_attempt":
                returns_on_probe += 1
    visible = [] if start is None else _visible(start)
    required = [name for name in RESULT_LOCAL if name in visible]
    order_ok = True
    if len(required) == len(RESULT_LOCAL):
        order_ok = (
            all(name in selected for name in required)
            and selected.index(required[0]) < selected.index(required[1])
        )
    exhausted = [
        event for event in _named(events, "return_entry_drain_exhausted")
        if start is not None and isinstance(event.get("step"), int)
        and isinstance(start_step, int) and event["step"] >= start_step
        and (not cluster or (event.get("hub_cluster") or event.get("cluster_id") or "") in ("", cluster))
    ]
    resumed = False
    if exhausted:
        exhaust_step = min(event["step"] for event in exhausted)
        resumed = any(
            isinstance(event.get("step"), int) and event["step"] > exhaust_step
            for event in _named(events, "return_attempt")
        )
    repeated = 0
    seen = set()
    for event in _named(events, "return_entry_probe_selected"):
        key = event.get("key") or ""
        if not key:
            continue
        if key in seen:
            repeated += 1
        seen.add(key)
    repeated += int(cell.get("repeated_local_action_key_violations") or 0)
    accounting = int(cell.get("return_entry_accounting_violations") or 0)
    witness = int(cell.get("witness_violations") or 0)
    terminal = int(cell.get("terminal_accounting_violations") or 0)
    probe_before = bool(selected)
    started = start is not None
    engaged = bool(result_reached and started and probe_before) or (
        not steps and started and probe_before
    )
    clean_attempts = attempt_mismatch == 0 and returns_on_probe == 0
    clean_cycle = cycle_mismatch == 0 and escapes_on_probe == 0
    clean_terminal = terminals_on_probe == 0
    return {
        "result_hub_reached": bool(result_reached or (not steps and started)),
        "false_to_true_at_result": started,
        "return_entry_drain_started_at_result": started,
        "result_button_probe_before_first_return": probe_before,
        "stable_order_when_close_reopen_visible": order_ok,
        "return_attempts_unchanged_during_probes": clean_attempts,
        "no_duplicate_terminal": clean_terminal,
        "no_return_cycle_contamination": clean_cycle,
        "historical_return_resumes_after_exhaustion": resumed,
        "result_return_entry_engaged": engaged,
        "probe_return_attempt_violations": attempt_mismatch + returns_on_probe,
        "probe_return_cycle_violations": cycle_mismatch + escapes_on_probe,
        "duplicate_terminal_count": terminals_on_probe,
        "false_return_success_count": success_mismatch,
        "parent_corruption_count": parent_mismatch,
        "repeated_key_violations": repeated,
        "return_entry_accounting_violations": accounting,
        "witness_violations": witness,
        "terminal_accounting_violations": terminal,
        "result": {
            "started": started,
            "step": start_step,
            "hub_cluster": cluster,
            "visible_eids": visible,
            "selected_eids": selected,
            "first_return_step": first_return,
            "exhaust_resumed": resumed,
            "return_attempts_at_start": None if start is None else start.get("return_attempts"),
        },
    }
