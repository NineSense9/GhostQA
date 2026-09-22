"""Synthetic A/B/C/D gates for the preregistered v0.3.12 outcome function."""
from benchmark.nested_hub_analysis import (
    MIN_EXHAUSTIVE_TRACES, assess_target, candidate_accounting_inflation,
    derive_v0312_outcome, horizon_or_terminal_after_followup,
    preservation_parent_intact, reached_return_phase,
)


def _repair_cell():
    return {
        "historical_preemptions": 10,
        "nested_branch_followup_events": 4,
        "commitment_window_preemptions": 0,
        "reached_horizon_or_terminal_after_followup": True,
        "reached_return_phase": True,
        "expanded_beyond_historical": True,
    }


def _base(**overrides):
    payload = dict(
        candidate_freeze_ok=True,
        historical_freezes_ok=True,
        n_series_failures=0,
        s1_s7_pass=True,
        exhaustive_failures=0,
        exhaustive_traces=MIN_EXHAUSTIVE_TRACES,
        crm=_repair_cell(),
        ops=_repair_cell(),
        return_inflation=False,
        parent_corruption=False,
        app_specific_logic=False,
        product_default_changed=False,
        lost_confirmed={"wiki": [], "buggy-desk": [], "buggy-shop": [],
                        "deepbench": []},
        detector_historical_ok=True,
    )
    payload.update(overrides)
    return payload


def _outcome(**overrides):
    return derive_v0312_outcome(**_base(**overrides))["outcome"]


def test_outcome_a_when_both_mechanism_cases_repair():
    got = derive_v0312_outcome(**_base())
    assert got["outcome"] == "A"
    assert got["outcome_meaning"] == "mechanism repaired, regression-safe"
    assert got["generalization_claim"] is False
    assert got["product_default_changed"] is False
    assert got["crm_repair"] is True
    assert got["ops_repair"] is True


def test_outcome_b_when_only_one_target_repairs():
    ops = _repair_cell()
    ops["reached_return_phase"] = False
    ops["expanded_beyond_historical"] = False
    assert _outcome(ops=ops) == "B"


def test_outcome_b_when_preemption_gone_but_one_does_not_expand():
    ops = _repair_cell()
    ops["expanded_beyond_historical"] = False
    ops["reached_horizon_or_terminal_after_followup"] = True
    ops["reached_return_phase"] = True
    assert _outcome(ops=ops) == "B"


def test_outcome_d_when_historical_preemption_missing():
    assert _outcome(detector_historical_ok=False) == "D"


def test_outcome_d_when_neither_target_eliminates_preemption():
    crm = _repair_cell()
    ops = _repair_cell()
    crm["commitment_window_preemptions"] = 3
    ops["commitment_window_preemptions"] = 2
    crm["reached_return_phase"] = False
    ops["reached_return_phase"] = False
    assert _outcome(crm=crm, ops=ops) == "D"


def test_outcome_c_dominates_d_when_safety_fails():
    crm = _repair_cell()
    ops = _repair_cell()
    crm["commitment_window_preemptions"] = 3
    ops["commitment_window_preemptions"] = 2
    assert _outcome(
        crm=crm, ops=ops, detector_historical_ok=False,
        n_series_failures=1) == "C"


def test_outcome_c_on_each_safety_regression():
    assert _outcome(n_series_failures=1) == "C"
    assert _outcome(s1_s7_pass=False) == "C"
    assert _outcome(exhaustive_failures=1) == "C"
    assert _outcome(exhaustive_traces=MIN_EXHAUSTIVE_TRACES - 1) == "C"
    assert _outcome(return_inflation=True) == "C"
    assert _outcome(parent_corruption=True) == "C"
    assert _outcome(app_specific_logic=True) == "C"
    assert _outcome(product_default_changed=True) == "C"
    assert _outcome(candidate_freeze_ok=False) == "C"
    assert _outcome(historical_freezes_ok=False) == "C"
    assert _outcome(lost_confirmed={"wiki": ["BUG-W2"], "buggy-desk": [],
                                    "buggy-shop": [], "deepbench": []}) == "C"
    assert _outcome(lost_confirmed={"wiki": [], "buggy-desk": ["K1"],
                                    "buggy-shop": [], "deepbench": []}) == "C"
    assert _outcome(lost_confirmed={"wiki": [], "buggy-desk": [],
                                    "buggy-shop": ["W5"], "deepbench": []}) == "C"
    assert _outcome(lost_confirmed={"wiki": [], "buggy-desk": [],
                                    "buggy-shop": [], "deepbench": ["D6"]}) == "C"


def test_followup_reaches_horizon_and_return_helpers():
    seq = [
        {"event": "branch_start", "sequence_instance_id": "seq-0001",
         "exact_sig": "P", "cluster_id": "pc", "branch_key": "pc:click:a",
         "step": 0},
        {"event": "nested_branch_followup", "sequence_instance_id": "seq-0001",
         "step": 1, "outer_branch": "pc:click:a",
         "outer_parent_hub_sig": "P", "outer_parent_hub_cluster": "pc",
         "commitment_left_before": 2, "branch_key": "pc:click:a"},
        {"event": "sequence_horizon_reached", "sequence_instance_id": "seq-0001",
         "step": 2},
        {"event": "return_attempt", "sequence_instance_id": "seq-0001", "step": 3},
        {"event": "sequence_terminal", "sequence_instance_id": "seq-0001",
         "outcome": "returned", "step": 4, "branch_key": "pc:click:a"},
    ]
    assert horizon_or_terminal_after_followup(seq) is True
    assert reached_return_phase(seq) is True
    assert preservation_parent_intact(seq) is True
    assert candidate_accounting_inflation(seq) is False


def test_parent_overwrite_and_double_terminal_are_visible():
    seq = [
        {"event": "branch_start", "sequence_instance_id": "seq-0001",
         "exact_sig": "P", "cluster_id": "pc", "branch_key": "pc:click:a",
         "step": 0},
        {"event": "nested_branch_followup", "sequence_instance_id": "seq-0001",
         "step": 1, "outer_branch": "pc:click:a",
         "outer_parent_hub_sig": "P", "outer_parent_hub_cluster": "pc",
         "commitment_left_before": 2, "branch_key": "pc:click:a"},
        {"event": "branch_start", "sequence_instance_id": "seq-0002",
         "exact_sig": "N", "cluster_id": "nc", "branch_key": "nc:click:b",
         "step": 1},
    ]
    assert preservation_parent_intact(seq) is False
    doubled = [
        {"event": "sequence_terminal", "sequence_instance_id": "seq-0001",
         "outcome": "finding", "step": 2},
        {"event": "sequence_terminal", "sequence_instance_id": "seq-0001",
         "outcome": "finding", "step": 2},
    ]
    assert candidate_accounting_inflation(doubled) is True


def test_assess_target_repair_from_synthetic_traces():
    guard = [
        {"step": 0, "event": "branch_start", "exact_sig": "P", "cluster_id": "pc",
         "branch_key": "pc:click:a", "sequence_instance_id": "seq-0001"},
        {"step": 1, "event": "hub_seen", "exact_sig": "N", "cluster_id": "nc",
         "sequence_instance_id": "seq-0001"},
        {"step": 1, "event": "sequence_terminal", "exact_sig": "N",
         "cluster_id": "nc", "branch_key": "pc:click:a",
         "sequence_instance_id": "seq-0001", "outcome": "lost_parent"},
        {"step": 1, "event": "branch_start", "exact_sig": "N", "cluster_id": "nc",
         "branch_key": "nc:click:b", "sequence_instance_id": "seq-0002"},
    ]
    steps = [{"kind": "step", "index": 1, "commitment_left": 2, "returning": False,
              "action": {"type": "click", "target_eid": "b"}}]
    nested = [
        {"step": 0, "event": "branch_start", "exact_sig": "P", "cluster_id": "pc",
         "branch_key": "pc:click:a", "sequence_instance_id": "seq-0001"},
        {"step": 1, "event": "nested_branch_followup", "exact_sig": "N",
         "cluster_id": "nc", "branch_key": "pc:click:a",
         "sequence_instance_id": "seq-0001", "outer_branch": "pc:click:a",
         "outer_parent_hub_sig": "P", "outer_parent_hub_cluster": "pc",
         "nested_branch_key": "nc:click:b", "commitment_left_before": 2},
        {"step": 2, "event": "sequence_horizon_reached",
         "sequence_instance_id": "seq-0001", "branch_key": "pc:click:a"},
        {"step": 3, "event": "return_attempt", "sequence_instance_id": "seq-0001"},
    ]
    nested_steps = [
        {"kind": "step", "index": 1, "dst_sig": "L", "dst_is_new": True,
         "dst_url": "http://h/leaf", "src_sig": "N", "src_url": "http://h/n"},
    ]
    cell = assess_target(
        guard, steps, nested, nested_steps,
        guard_states=5, guard_urls=5, nested_states=8, nested_urls=6)
    assert cell["mechanism_repair"] is True
    assert cell["preemption_eliminated"] is True
    assert cell["historical_preemptions"] == 1
    assert cell["commitment_window_preemptions"] == 0
    assert cell["expanded_beyond_historical"] is True
