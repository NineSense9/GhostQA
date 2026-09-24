"""Classifier checks for the preregistered v0.3.19 trace measurements."""
from benchmark.finding_return_entry_trace import (
    horizon_bypass_ok, horizon_only_drain_count, trigger_consistency,
)


def _trigger(step, branch="branch-a", index=1):
    return {
        "event": "finding_return_entry_trigger",
        "step": step,
        "terminal_outcome": "finding",
        "branch_key": branch,
        "active_branch": branch,
        "provenance_mode": "sequence_instance",
        "terminal_event_index": index,
        "sequence_instance_id": "seq-0001",
    }


def test_horizon_only_drain_is_distinct_from_a_finding_trigger():
    events = [
        {"event": "sequence_horizon_reached", "step": 7},
        {
            "event": "return_entry_drain_started",
            "step": 7,
            "active_branch": "branch-a",
        },
        {"event": "sequence_terminal", "step": 16, "outcome": "finding"},
        {
            "event": "return_entry_drain_started",
            "step": 16,
            "active_branch": "branch-a",
        },
        _trigger(16),
    ]
    assert horizon_only_drain_count(events) == 1
    facts = trigger_consistency(events)
    assert facts["counts_match"] is False
    assert facts["horizon_bypass_events"] == 0
    assert horizon_bypass_ok(events) is False


def test_finding_trigger_consistency_accepts_one_provenance_per_drain():
    events = [
        {"event": "sequence_terminal", "step": 4, "outcome": "finding"},
        {
            "event": "return_entry_drain_started",
            "step": 4,
            "active_branch": "branch-a",
        },
        _trigger(4),
        {"event": "sequence_horizon_reached", "step": 9},
        {
            "event": "finding_return_entry_horizon_bypassed",
            "step": 9,
            "behavior": "v0317_fallback",
        },
    ]
    facts = trigger_consistency(events)
    assert facts["drain_starts"] == 1
    assert facts["trigger_events"] == 1
    assert facts["horizon_only_drains"] == 0
    assert facts["counts_match"] is True
    assert horizon_bypass_ok(events) is True


def test_reused_terminal_index_breaks_consistency():
    first = _trigger(4, index=2)
    second = _trigger(8, index=2)
    events = [
        {"event": "return_entry_drain_started", "step": 4, "active_branch": "branch-a"},
        first,
        {"event": "return_entry_drain_started", "step": 8, "active_branch": "branch-a"},
        second,
    ]
    facts = trigger_consistency(events)
    assert facts["reused"] == 1
    assert facts["counts_match"] is False
