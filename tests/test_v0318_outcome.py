"""Synthetic A/B/C/D derivation for the frozen v0.3.18 gate."""
from benchmark.return_entry_drain_analysis import (
    derive_v0318_outcome, directory_preserved_v0318, lab_mechanism_gate, passing_facts,
)


def _outcome(**updates):
    facts = passing_facts()
    facts.update(updates)
    return derive_v0318_outcome(**facts)["outcome"]


def test_outcome_a_when_every_gate_passes():
    assert _outcome() == "A"
    report = derive_v0318_outcome()
    assert report["fresh_validation"] is False
    assert report["inspected_repair_only"] is True
    assert report["promotion_readiness"] == "not_ready"


def test_outcome_c_precedes_d_and_b():
    assert _outcome(
        witness_violations=1,
        result_return_entry_engaged=False,
        lab_zero_guard_loss=False,
    ) == "C"
    assert _outcome(model_ok=False) == "C"
    assert _outcome(model_invariant_failures=1) == "C"
    assert _outcome(model_raw_traces=1) == "C"
    assert _outcome(probe_return_attempt_violations=1) == "C"
    assert _outcome(probe_return_cycle_violations=1) == "C"
    assert _outcome(duplicate_terminal=True) == "C"
    assert _outcome(duplicate_terminal_count=1) == "C"
    assert _outcome(false_return_success=True) == "C"
    assert _outcome(parent_corruption=True) == "C"
    assert _outcome(repeated_key_violations=1) == "C"
    assert _outcome(return_entry_accounting_violations=1) == "C"
    assert _outcome(terminal_accounting_violations=1) == "C"
    assert _outcome(app_specific=True) == "C"
    assert _outcome(historical_regression_loss=["BUG-K1"]) == "C"
    assert _outcome(crm_ops_collapse=True) == "C"
    assert _outcome(directory_false_handoff=True) == "C"
    assert _outcome(product_default_changed=True) == "C"
    assert _outcome(post_freeze_edit=True) == "C"
    assert _outcome(historical_source_mutation=True) == "C"
    assert _outcome(safety_ok=False) == "C"
    assert _outcome(candidate_freeze_ok=False) == "C"
    assert _outcome(protocol_ok=False) == "C"


def test_outcome_d_when_result_return_entry_does_not_engage():
    assert _outcome(
        result_return_entry_engaged=False,
        lab_mechanism_gate=False,
        return_entry_drain_started_at_result=False,
        result_button_probe_before_first_return=False,
        lab_zero_guard_loss=False,
    ) == "D"


def test_outcome_b_when_repair_is_partial():
    assert _outcome(lab_zero_guard_loss=False) == "B"
    assert _outcome(billing_full_transfer=False) == "B"
    assert _outcome(forum_full_transfer=False) == "B"
    assert _outcome(result_button_probe_before_first_return=False) == "B"
    assert _outcome(directory_preserved=False, directory_false_handoff=False) == "B"
    assert _outcome(crm_preserved=False, crm_ops_collapse=False) == "B"
    assert _outcome(ops_preserved=False, crm_ops_collapse=False) == "B"


def test_lab_mechanism_gate_requires_the_preregistered_checks():
    facts = passing_facts()
    assert lab_mechanism_gate(facts) is True
    facts["historical_return_resumes_after_exhaustion"] = False
    assert lab_mechanism_gate(facts) is False


def test_directory_preservation_requires_zero_handoff_and_guard_bugs():
    row = {
        "horizon_handoff_started_events": 0,
        "max_handoff_stack_depth": 0,
        "witness_violations": 0,
        "terminal_accounting_violations": 0,
        "repeated_local_action_key_violations": 0,
        "local_action_sequence_accounting_violations": 0,
        "return_entry_accounting_violations": 0,
    }
    assert directory_preserved_v0318(row, ["BUG-A"], ["BUG-A"]) is True
    assert directory_preserved_v0318(row, ["BUG-A"], []) is False
    row["horizon_handoff_started_events"] = 1
    assert directory_preserved_v0318(row, ["BUG-A"], ["BUG-A"]) is False
    row["horizon_handoff_started_events"] = 0
    row["return_entry_accounting_violations"] = 1
    assert directory_preserved_v0318(row, ["BUG-A"], ["BUG-A"]) is False
