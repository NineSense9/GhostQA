"""Synthetic A/B/C/D derivation for the frozen v0.3.16 gate."""
from benchmark.reentry_frontier_analysis import (
    derive_v0316_outcome, directory_repair_gate, lab_starvation_gate,
    mechanism_preserved, new_guard_losses, passing_facts,
)


def _outcome(**updates):
    facts = passing_facts()
    facts.update(updates)
    return derive_v0316_outcome(**facts)["outcome"]


def test_outcome_a_when_every_gate_passes():
    assert _outcome() == "A"


def test_outcome_c_precedes_d_when_unsafe():
    assert _outcome(
        witness_violations=1,
        directory_same_parent_handoffs=2,
        directory_early_reentry_events=0,
        directory_source_repair_events=0,
        lab_lease_granted_events=0,
    ) == "C"


def test_outcome_c_on_new_loss_regression_and_default():
    assert _outcome(new_guard_bug_loss=["BUG-L2"]) == "C"
    assert _outcome(historical_regression_loss=["BUG-K1"]) == "C"
    assert _outcome(product_default_changed=True) == "C"
    assert _outcome(repeated_lease_key_violations=1) == "C"
    assert _outcome(model_ok=False) == "C"
    assert _outcome(crm_ops_collapse=True) == "C"
    assert _outcome(double_completion=1) == "C"
    assert _outcome(app_specific=True) == "C"


def test_outcome_d_when_neither_mechanism_engages():
    assert _outcome(
        directory_same_parent_handoffs=2,
        directory_early_reentry_events=0,
        directory_source_repair_events=0,
        directory_repair_gate=False,
        lab_lease_granted_events=0,
        lab_starvation_gate=False,
        lab_zero_guard_loss=False,
    ) == "D"


def test_outcome_b_when_repair_is_partial():
    assert _outcome(lab_zero_guard_loss=False, lab_starvation_gate=True) == "B"
    assert _outcome(
        directory_repair_gate=False,
        directory_same_parent_handoffs=2,
        directory_early_reentry_events=2,
        lab_starvation_gate=True,
        lab_zero_guard_loss=True,
    ) == "B"
    assert _outcome(forum_full_transfer=False) == "B"
    assert _outcome(crm_preserved=False, crm_ops_collapse=False) == "B"


def test_directory_and_lab_gates_are_structural():
    row = {
        "early_parent_reentry_events": 1,
        "horizon_handoff_started_events": 0,
        "child_parent_witness_events": 0,
        "max_handoff_stack_depth": 0,
        "witness_violations": 0,
        "terminal_accounting_violations": 0,
    }
    assert directory_repair_gate(row, ["BUG-A"], ["BUG-A", "BUG-B"]) is True
    assert directory_repair_gate(row, ["BUG-A"], []) is False
    lab = {
        "horizon_handoff_started_events": 1,
        "local_frontier_lease_granted_events": 1,
        "local_frontier_lease_action_events": 1,
        "frontier_repeated_key_violations": 0,
        "witness_violations": 0,
        "terminal_accounting_violations": 0,
        "lease_cross_hub_uncancelled": 0,
        "frontier_monotonicity_violations": 0,
    }
    assert lab_starvation_gate(lab) is True
    lab["local_frontier_lease_action_events"] = 0
    assert lab_starvation_gate(lab) is False


def test_new_loss_ignores_bugs_the_historical_candidate_already_lost():
    assert new_guard_losses(
        ["BUG-L1", "BUG-L2"], ["BUG-L2"], ["BUG-L2"]) == []
    assert new_guard_losses(
        ["BUG-L1", "BUG-L2"], ["BUG-L1", "BUG-L2"], ["BUG-L2"]) == ["BUG-L1"]


def test_mechanism_collapse_is_separate_from_a_soft_miss():
    assert mechanism_preserved({
        "states": 8, "normalized_unique_urls": 7,
        "sequence_horizon_reached": 1, "witness_violations": 0,
        "terminal_accounting_violations": 0,
    })["pass"] is True
    collapsed = mechanism_preserved({"states": 5, "normalized_unique_urls": 5})
    assert collapsed["collapse"] is True
    assert collapsed["pass"] is False
