"""Synthetic lab-gate traces. Button ids are audit assertions only."""
from benchmark.return_entry_drain_trace import diagnose_lab


def _step(index, src, dst, eid):
    return {
        "kind": "step",
        "index": index,
        "src_url": src,
        "dst_url": dst,
        "action": {"type": "click", "target_eid": eid},
        "findings": [],
    }


def _trace():
    steps = [
        _step(10, "/run.html", "/result.html?id=q1", "open_q"),
        _step(11, "/result.html?id=q1", "/result.html?id=q1", "btn_close"),
        _step(12, "/result.html?id=q1", "/result.html?id=q1", "btn_reopen"),
        _step(13, "/result.html?id=q1", "/experiment.html", "nav_up"),
    ]
    common = {
        "hub_cluster": "result",
        "return_attempts": 1,
        "return_success": 0,
        "return_cycle_history_count": 1,
        "active_branch": "hub:click:open_q",
        "parent_hub_sig": "parent",
        "parent_hub_cluster": "parent",
    }
    events = [
        {
            "event": "return_entry_drain_started",
            "step": 10,
            "visible_eligible_keys": ["result:button:btn_close", "result:button:btn_reopen"],
            **common,
        },
        {"event": "return_entry_probe_selected", "step": 11, "eid": "btn_close",
         "key": "result:button:btn_close", **common},
        {"event": "return_entry_probe_completed", "step": 11,
         "key": "result:button:btn_close", **common},
        {"event": "return_entry_probe_selected", "step": 12, "eid": "btn_reopen",
         "key": "result:button:btn_reopen", **common},
        {"event": "return_entry_probe_completed", "step": 12,
         "key": "result:button:btn_reopen", **common},
        {"event": "return_entry_probe_finding", "step": 12,
         "key": "result:button:btn_reopen", **common},
        {"event": "return_entry_drain_exhausted", "step": 12, **common},
        {"event": "return_attempt", "step": 13, "branch_key": common["active_branch"]},
    ]
    return events, steps


def test_result_return_entry_gate_accepts_stable_order():
    facts = diagnose_lab(*_trace())
    assert facts["result_return_entry_engaged"] is True
    assert facts["stable_order_when_close_reopen_visible"] is True
    assert facts["historical_return_resumes_after_exhaustion"] is True
    assert facts["probe_return_attempt_violations"] == 0
    assert facts["duplicate_terminal_count"] == 0
    assert facts["result"]["selected_eids"] == ["btn_close", "btn_reopen"]
    assert facts["result"]["first_return_step"] == 13


def test_probe_that_is_a_return_attempt_is_visible_to_the_gate():
    events, steps = _trace()
    events.append({"event": "return_attempt", "step": 11, "branch_key": "x"})
    facts = diagnose_lab(events, steps)
    assert facts["probe_return_attempt_violations"] > 0
    assert facts["return_attempts_unchanged_during_probes"] is False
