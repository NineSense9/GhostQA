"""The lab mechanism audit follows the preregistered trace rules."""
from benchmark.local_action_drain_trace import diagnose_lab


def _drain(step, cluster, eids, outer="seq-outer"):
    return {
        "event": "local_action_drain_started",
        "step": step,
        "hub_cluster": cluster,
        "hub_sig": cluster + ":sig",
        "suspended_outer_id": outer,
        "visible_eligible_keys": [f"{cluster}:button:{eid}" for eid in eids],
    }


def _probe(step, cluster, eid):
    return {
        "event": "local_action_probe_completed",
        "step": step,
        "hub_cluster": cluster,
        "key": f"{cluster}:button:{eid}",
        "eid": eid,
    }


def _selected(step, cluster, eid):
    return {
        "event": "local_action_probe_selected",
        "step": step,
        "hub_cluster": cluster,
        "key": f"{cluster}:button:{eid}",
        "eid": eid,
    }


def _lease(step, cluster, eid):
    return {
        "event": "local_frontier_lease_action",
        "step": step,
        "hub_cluster": cluster,
        "chosen_branch_key": f"{cluster}:click:{eid}",
    }


def test_run_and_result_order_satisfies_the_mechanism_facts():
    events = [
        {"event": "child_parent_witness", "step": 4, "child_branch": "c:click:open_sample_s1"},
        _drain(4, "run", ["btn_staff_note", "btn_cool"]),
        _selected(5, "run", "btn_staff_note"),
        _probe(5, "run", "btn_staff_note"),
        _selected(6, "run", "btn_cool"),
        _probe(6, "run", "btn_cool"),
        _lease(7, "run", "open_result_from_run"),
        {"event": "child_parent_witness", "step": 12, "child_branch": "c:click:open_compare"},
        _drain(12, "result", ["btn_close", "btn_reopen"]),
        _selected(13, "result", "btn_close"),
        _probe(13, "result", "btn_close"),
        _selected(14, "result", "btn_reopen"),
        _probe(14, "result", "btn_reopen"),
        _lease(15, "result", "open_notebook"),
    ]
    facts = diagnose_lab(events, {})
    assert facts["sample_child_witness"] is True
    assert facts["drain_started_at_run"] is True
    assert facts["same_hub_probe_before_structural_navigation"] is True
    assert facts["result_drain_started"] is True
    assert facts["close_reopen_before_structural_navigation"] is True
    assert facts["lab_drain_engaged"] is True
    assert facts["run"]["selected_eids"] == ["btn_staff_note", "btn_cool"]
    assert facts["run"]["structural_event"] == "local_frontier_lease_action"


def test_structural_before_any_probe_does_not_count_as_engaged_repair():
    events = [
        _drain(4, "run", ["btn_staff_note"]),
        _lease(5, "run", "open_result_from_run"),
        _selected(9, "run", "btn_staff_note"),
        _probe(9, "run", "btn_staff_note"),
    ]
    facts = diagnose_lab(events, {})
    assert facts["same_hub_probe_before_structural_navigation"] is False
    assert facts["lab_drain_engaged"] is False


def test_repeated_probe_key_is_counted():
    events = [
        _drain(1, "run", ["btn_cool"]),
        _selected(2, "run", "btn_cool"),
        _probe(2, "run", "btn_cool"),
        _selected(3, "run", "btn_cool"),
        _probe(3, "run", "btn_cool"),
    ]
    facts = diagnose_lab(events, {"repeated_local_action_key_violations": 0})
    assert facts["repeated_local_key_violations"] == 1
