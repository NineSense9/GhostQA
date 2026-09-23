"""Trace checks for the preregistered v0.3.17 lab mechanism gate.

Reads sequence events after a run. Does not choose exploration actions.
Button ids are audit assertions, not candidate rules.
"""
from __future__ import annotations

RUN_LOCAL = ("btn_cool", "btn_staff_note")
RUN_STRUCTURAL = ("open_result_from_run", "open_sample_s1", "open_sample_s2")
RESULT_LOCAL = ("btn_close", "btn_reopen")
RESULT_STRUCTURAL = ("open_notebook", "open_run_again", "open_compare")


def _eid(key: str) -> str:
    text = str(key or "")
    for marker in (":local-button:", ":button:", ":click:"):
        if marker in text:
            return text.split(marker, 1)[1]
    return text


def _named(events: list, name: str) -> list:
    return [event for event in events or [] if event.get("event") == name]


def _visible_eids(event: dict) -> list:
    keys = event.get("visible_eligible_keys") or []
    return [_eid(key) for key in keys]


def _branch_eid(event: dict) -> str:
    for field in ("chosen_branch_key", "child_branch", "branch_key", "button_key", "key"):
        if event.get(field):
            return _eid(event.get(field))
    return ""


def _cluster(event: dict) -> str:
    return event.get("hub_cluster") or event.get("cluster_id") or ""


def _first_structural(events: list, cluster: str, names: tuple, after: int):
    hits = []
    for event in events or []:
        if event.get("event") not in (
            "local_frontier_lease_action", "horizon_handoff_started",
            "local_action_promoted_to_child",
        ):
            continue
        step = event.get("step")
        if not isinstance(step, int) or step <= after:
            continue
        if cluster and _cluster(event) not in ("", cluster):
            continue
        eid = _branch_eid(event)
        if eid in names:
            hits.append(event)
    if not hits:
        return None
    return min(hits, key=lambda event: event["step"])


def _drains_for(events: list, names: tuple) -> list:
    found = []
    for event in _named(events, "local_action_drain_started"):
        if set(names) & set(_visible_eids(event)):
            found.append(event)
    return found


def _probes_before(events: list, cluster: str, start: int, limit):
    rows = []
    for event in _named(events, "local_action_probe_completed"):
        step = event.get("step")
        if not isinstance(step, int) or step < start:
            continue
        if limit is not None and step >= limit:
            continue
        if cluster and _cluster(event) not in ("", cluster):
            continue
        rows.append(event)
    return rows


def _selected_eids(events: list, cluster: str, start: int, limit) -> list:
    rows = []
    for event in _named(events, "local_action_probe_selected"):
        step = event.get("step")
        if not isinstance(step, int) or step < start:
            continue
        if limit is not None and step >= limit:
            continue
        if cluster and _cluster(event) not in ("", cluster):
            continue
        rows.append(event.get("eid") or _eid(event.get("key") or ""))
    return rows


def _hub_report(events: list, local_names: tuple, structural_names: tuple) -> dict:
    drains = _drains_for(events, local_names)
    if not drains:
        return {
            "started": False,
            "probe_before_structural": False,
            "local_names_selected_before_structural": False,
            "visible_eids": [],
            "selected_eids": [],
            "structural_eid": "",
            "structural_event": "",
            "structural_step": None,
        }
    drain = min(drains, key=lambda event: event.get("step") or 0)
    start = int(drain.get("step") or 0)
    cluster = _cluster(drain)
    structural = _first_structural(events, cluster, structural_names, start)
    limit = None if structural is None else structural.get("step")
    probes = _probes_before(events, cluster, start, limit)
    selected = _selected_eids(events, cluster, start, limit)
    visible = _visible_eids(drain)
    required = [name for name in local_names if name in visible]
    return {
        "started": True,
        "step": start,
        "hub_cluster": cluster,
        "hub_sig": drain.get("hub_sig") or drain.get("exact_sig") or "",
        "suspended_outer_id": drain.get("suspended_outer_id"),
        "visible_eids": visible,
        "selected_eids": selected,
        "probe_completed": len(probes),
        "probe_before_structural": bool(probes),
        "local_names_selected_before_structural": all(name in selected for name in required),
        "required_local_eids": required,
        "structural_eid": "" if structural is None else _branch_eid(structural),
        "structural_event": "" if structural is None else structural.get("event") or "",
        "structural_step": None if structural is None else structural.get("step"),
    }


def _sample_witness(events: list) -> bool:
    for event in _named(events, "child_parent_witness"):
        eid = _eid(event.get("child_branch") or "")
        if eid.startswith("open_sample"):
            return True
    return False


def _repeated(events: list) -> int:
    seen = set()
    repeats = 0
    for event in _named(events, "local_action_probe_selected"):
        key = event.get("key") or ""
        if not key:
            continue
        if key in seen:
            repeats += 1
        seen.add(key)
    return repeats


def diagnose_lab(events: list, row: dict | None = None) -> dict:
    """Preregistered lab mechanism facts from one candidate trace."""
    cell = row or {}
    run = _hub_report(events, RUN_LOCAL, RUN_STRUCTURAL)
    result = _hub_report(events, RESULT_LOCAL, RESULT_STRUCTURAL)
    repeated = int(cell.get("repeated_local_action_key_violations") or 0) + _repeated(events)
    accounting = int(cell.get("local_action_sequence_accounting_violations") or 0)
    witness = int(cell.get("witness_violations") or 0)
    terminal = int(cell.get("terminal_accounting_violations") or 0)
    engaged = bool(
        (run["started"] and run["probe_before_structural"])
        or (result["started"] and result["probe_completed"])
    )
    return {
        "sample_child_witness": _sample_witness(events),
        "drain_started_at_run": bool(run["started"]),
        "same_hub_probe_before_structural_navigation": bool(run["probe_before_structural"]),
        "result_drain_started": bool(result["started"]),
        "close_reopen_before_structural_navigation": bool(
            result["started"] and result["local_names_selected_before_structural"]
        ),
        "repeated_local_key_violations": repeated,
        "local_action_sequence_accounting_violations": accounting,
        "witness_violations": witness,
        "terminal_accounting_violations": terminal,
        "lab_drain_engaged": engaged,
        "run": run,
        "result": result,
    }
