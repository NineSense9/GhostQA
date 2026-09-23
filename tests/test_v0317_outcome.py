"""Synthetic A/B/C/D derivation for the frozen v0.3.17 gate."""
from benchmark.local_action_drain_analysis import (
    derive_v0317_outcome, directory_preserved, lab_mechanism_gate, passing_facts,
)


def _outcome(**updates):
    facts = passing_facts()
    facts.update(updates)
    return derive_v0317_outcome(**facts)["outcome"]


def test_outcome_a_when_every_gate_passes():
    assert _outcome() == "A"


def test_outcome_c_precedes_d_and_b():
    assert _outcome(
        witness_violations=1,
        lab_drain_engaged=False,
        lab_zero_guard_loss=False,
    ) == "C"
    assert _outcome(model_ok=False) == "C"
    assert _outcome(model_invariant_failures=1) == "C"
    assert _outcome(repeated_local_key_violations=1) == "C"
    assert _outcome(cross_hub_drain_violations=1) == "C"
    assert _outcome(local_action_sequence_accounting_violations=1) == "C"
    assert _outcome(phantom_sequence=True) == "C"
    assert _outcome(fabricated_outer_terminal=True) == "C"
    assert _outcome(promotion_unsafe=True) == "C"
    assert _outcome(double_browser_action=True) == "C"
    assert _outcome(app_specific=True) == "C"
    assert _outcome(hidden_metadata=True) == "C"
    assert _outcome(historical_regression_loss=["BUG-K1"]) == "C"
    assert _outcome(crm_ops_collapse=True) == "C"
    assert _outcome(directory_false_handoff=True) == "C"
    assert _outcome(product_default_changed=True) == "C"
    assert _outcome(post_freeze_edit=True) == "C"
    assert _outcome(safety_ok=False) == "C"


def test_outcome_d_when_lab_drain_does_not_engage():
    assert _outcome(
        lab_drain_engaged=False,
        lab_mechanism_gate=False,
        drain_started_at_run=False,
        lab_zero_guard_loss=False,
    ) == "D"


def test_outcome_b_when_repair_is_partial():
    assert _outcome(lab_zero_guard_loss=False) == "B"
    assert _outcome(billing_full_transfer=False) == "B"
    assert _outcome(forum_full_transfer=False) == "B"
    assert _outcome(close_reopen_before_structural_navigation=False) == "B"
    assert _outcome(directory_preserved=False, directory_false_handoff=False) == "B"
    assert _outcome(crm_preserved=False, crm_ops_collapse=False) == "B"
    assert _outcome(ops_preserved=False, crm_ops_collapse=False) == "B"


def test_lab_mechanism_gate_requires_the_preregistered_checks():
    facts = passing_facts()
    assert lab_mechanism_gate(facts) is True
    facts["same_hub_probe_before_structural_navigation"] = False
    assert lab_mechanism_gate(facts) is False


def test_directory_preservation_requires_zero_handoff_and_guard_bugs():
    row = {
        "horizon_handoff_started_events": 0,
        "max_handoff_stack_depth": 0,
        "witness_violations": 0,
        "terminal_accounting_violations": 0,
        "repeated_local_action_key_violations": 0,
        "local_action_sequence_accounting_violations": 0,
    }
    assert directory_preserved(row, ["BUG-A"], ["BUG-A"]) is True
    assert directory_preserved(row, ["BUG-A"], []) is False
    row["horizon_handoff_started_events"] = 2
    assert directory_preserved(row, ["BUG-A"], ["BUG-A"]) is False
