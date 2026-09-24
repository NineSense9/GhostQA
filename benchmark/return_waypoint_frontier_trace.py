"""Read waypoint-escape evidence. Does not choose exploration actions."""
from __future__ import annotations

from benchmark.return_waypoint_frontier_analysis import HISTORICAL_STARVATION_INDEX


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _eid(key: str) -> str:
    parts = str(key or "").split(":")
    return parts[-1] if parts else ""


def _steps(events: list) -> list:
    return [row for row in events or [] if row.get("kind") == "step"]


def assess_waypoint(sequence: list, trace_events: list,
                    starvation_index: int = HISTORICAL_STARVATION_INDEX) -> dict:
    """Decide whether one inspected positive trace meets the waypoint gate."""
    sequence = sequence or []
    resumes = [
        event for event in sequence
        if event.get("event") == "parent_frame_resume_to_return"
        and _int(event.get("stack_depth")) == 0
    ]
    escapes = [
        event for event in sequence
        if event.get("event") == "return_waypoint_frontier_escape"
    ]
    resume = resumes[0] if resumes else {}
    instance = resume.get("resumed_sequence_instance_id") or resume.get("sequence_instance_id")
    parent_cluster = resume.get("original_parent_hub_cluster") or ""
    matched = []
    for event in escapes:
        event_instance = event.get("sequence_instance_id") or event.get("resumed_sequence_instance_id")
        if instance and event_instance and event_instance != instance:
            continue
        if _int(event.get("step")) <= _int(resume.get("step")):
            continue
        matched.append(event)
    escape = matched[0] if matched else (escapes[0] if escapes and not resume else {})
    waypoint_cluster = escape.get("waypoint_cluster") or ""
    residual_keys = list(escape.get("local_residual_keys") or []) + list(
        escape.get("structural_residual_keys") or [])
    residual_eids = {_eid(key) for key in residual_keys if _eid(key)}
    escape_step = escape.get("step")
    same_step_returned = any(
        event.get("event") == "sequence_terminal"
        and event.get("outcome") == "returned"
        and event.get("step") == escape_step
        and event.get("sequence_instance_id") == escape.get("sequence_instance_id")
        for event in sequence
    )
    next_label = ""
    next_eid = ""
    tried = []
    if escape_step is not None:
        for step in _steps(trace_events):
            index = _int(step.get("index"))
            action = (step.get("action") or {}).get("target_eid") or ""
            if index == _int(escape_step) + 1:
                next_label = step.get("last_label") or ""
                next_eid = action
            if index > _int(escape_step) and action in residual_eids:
                tried.append({"index": index, "eid": action})
    violations = sum(
        _int(escape.get(name))
        for name in (
            "return_waypoint_false_success_violations",
            "return_waypoint_terminal_accounting_violations",
            "return_waypoint_parent_precedence_violations",
            "return_waypoint_stack_scope_violations",
            "return_waypoint_unknown_hub_violations",
            "return_waypoint_repeat_escape_violations",
        )
    )
    engaged = bool(
        resume
        and escape
        and waypoint_cluster
        and waypoint_cluster != parent_cluster
        and _int(escape.get("stack_depth")) == 0
        and escape.get("reason") == "residual_frontier"
        and _int(escape.get("local_residual_count")) + _int(escape.get("structural_residual_count")) >= 1
        and escape_step is not None
        and _int(escape_step) < _int(starvation_index)
        and not same_step_returned
        and next_label not in ("", "return_hub")
        and tried
        and violations == 0
    )
    return {
        "resume_step": resume.get("step"),
        "escape_step": escape_step,
        "waypoint_cluster": waypoint_cluster,
        "parent_cluster": parent_cluster,
        "stack_depth": escape.get("stack_depth"),
        "match_strength": escape.get("waypoint_match_strength") or "",
        "local_residual_count": _int(escape.get("local_residual_count")),
        "structural_residual_count": _int(escape.get("structural_residual_count")),
        "return_success_before": escape.get("return_success_before"),
        "next_label": next_label,
        "next_eid": next_eid,
        "residual_tried": tried,
        "escape_events": len(escapes),
        "engaged": engaged,
        "waypoint_reached": bool(resume and escape and waypoint_cluster and waypoint_cluster != parent_cluster),
        "residual_escape": bool(escape and residual_keys),
    }
