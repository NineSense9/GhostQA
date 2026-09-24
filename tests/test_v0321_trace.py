"""Waypoint engagement is decided from events, not from target names."""
from benchmark.return_waypoint_frontier_trace import assess_waypoint


def _sample():
    sequence = [
        {
            "event": "parent_frame_resume_to_return",
            "step": 20,
            "stack_depth": 0,
            "resumed_sequence_instance_id": "seq-0001",
            "sequence_instance_id": "seq-0001",
            "original_parent_hub_cluster": "list",
            "resumed_branch": "list:click:open_row",
        },
        {
            "event": "return_waypoint_frontier_escape",
            "step": 21,
            "sequence_instance_id": "seq-0001",
            "stack_depth": 0,
            "reason": "residual_frontier",
            "waypoint_cluster": "entity",
            "original_final_parent_cluster": "list",
            "local_residual_count": 1,
            "structural_residual_count": 1,
            "local_residual_keys": ["entity:button:pin"],
            "structural_residual_keys": ["entity:click:side"],
            "return_success_before": 1,
            "waypoint_match_strength": "cluster",
        },
    ]
    steps = [
        {"kind": "step", "index": 21, "last_label": "return_hub",
         "action": {"target_eid": "nav_up_row"}},
        {"kind": "step", "index": 22, "last_label": "branch",
         "action": {"target_eid": "side"}},
    ]
    return sequence, steps


def test_escape_before_the_historical_parent_return_engages():
    report = assess_waypoint(*_sample())
    assert report["engaged"] is True
    assert report["escape_step"] == 21
    assert report["next_label"] == "branch"
    assert report["next_eid"] == "side"
    assert report["residual_tried"][0]["eid"] == "side"


def test_escape_at_the_parent_or_after_starvation_does_not_engage():
    sequence, steps = _sample()
    sequence[1]["waypoint_cluster"] = "list"
    sequence[1]["original_final_parent_cluster"] = "list"
    assert assess_waypoint(sequence, steps)["engaged"] is False

    sequence, steps = _sample()
    sequence[1]["step"] = 22
    steps[1]["index"] = 23
    assert assess_waypoint(sequence, steps)["engaged"] is False


def test_missing_resume_does_not_engage():
    _sequence, steps = _sample()
    report = assess_waypoint([steps and {
        "event": "return_waypoint_frontier_escape",
        "step": 21,
        "stack_depth": 0,
        "reason": "residual_frontier",
        "waypoint_cluster": "entity",
        "local_residual_count": 1,
        "local_residual_keys": ["entity:button:pin"],
        "structural_residual_count": 0,
        "structural_residual_keys": [],
    }], steps)
    assert report["engaged"] is False
