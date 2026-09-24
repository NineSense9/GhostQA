"""Synthetic A/B/C/D derivation for the frozen v0.3.19 gate."""
from benchmark.finding_return_entry_analysis import (
    deep_coverage_ok, derive_v0319_outcome, directory_preserved_v0319,
    lab_mechanism_gate, passing_facts,
)


def _outcome(**updates):
    facts = passing_facts()
    facts.update(updates)
    return derive_v0319_outcome(**facts)["outcome"]


def test_outcome_a_when_every_gate_passes():
    assert _outcome() == "A"
    report = derive_v0319_outcome()
    assert report["fresh_validation"] is False
    assert report["inspected_repair_only"] is True
    assert report["promotion_readiness"] == "not_ready"
    assert report["generalization_claim"] is False


def test_outcome_c_precedes_d_and_b():
    assert _outcome(
        witness_violations=1,
        result_return_entry_engaged=False,
        lab_zero_guard_loss=False,
    ) == "C"
    assert _outcome(model_ok=False) == "C"
    assert _outcome(model_invariant_failures=1) == "C"
    assert _outcome(model_raw_traces=1) == "C"
    assert _outcome(historical_models_ok=False) == "C"
    assert _outcome(fg_safety_ok=False) == "C"
    assert _outcome(horizon_differential_ok=False) == "C"
    assert _outcome(probe_return_attempt_violations=1) == "C"
    assert _outcome(duplicate_terminal=True) == "C"
    assert _outcome(parent_corruption=True) == "C"
    assert _outcome(repeated_key_violations=1) == "C"
    assert _outcome(return_entry_accounting_violations=1) == "C"
    assert _outcome(trigger_mismatch_violations=1) == "C"
    assert _outcome(reused_trigger_violations=1) == "C"
    assert _outcome(wrong_instance_violations=1) == "C"
    assert _outcome(horizon_only_drain=True) == "C"
    assert _outcome(nonfinding_triggered_drain=True) == "C"
    assert _outcome(wrong_instance_triggered_drain=True) == "C"
    assert _outcome(reused_trigger=True) == "C"
    assert _outcome(trigger_counts_match=False) == "C"
    assert _outcome(deep_no_horizon_drain=False) == "C"
    assert _outcome(app_specific=True) == "C"
    assert _outcome(historical_regression_loss=["BUG-D6"]) == "C"
    assert _outcome(crm_ops_collapse=True) == "C"
    assert _outcome(directory_false_handoff=True) == "C"
    assert _outcome(product_default_changed=True) == "C"
    assert _outcome(post_freeze_edit=True) == "C"
    assert _outcome(historical_source_mutation=True) == "C"
    assert _outcome(safety_ok=False) == "C"
    assert _outcome(candidate_freeze_ok=False) == "C"
    assert _outcome(protocol_ok=False) == "C"


def test_outcome_d_when_finding_trigger_does_not_engage():
    assert _outcome(
        result_return_entry_engaged=False,
        lab_mechanism_gate=False,
        finding_terminal_false_to_true=True,
        finding_return_entry_trigger_at_result=False,
        return_entry_drain_started_at_result=False,
        result_button_probe_before_first_return=False,
        bug_l9_confirmed=False,
        lab_zero_guard_loss=False,
    ) == "D"


def test_outcome_b_when_repair_is_partial():
    assert _outcome(lab_zero_guard_loss=False, bug_l9_confirmed=False) == "B"
    assert _outcome(billing_full_transfer=False) == "B"
    assert _outcome(forum_full_transfer=False) == "B"
    assert _outcome(deep_guard_retained=False, historical_regression_loss=[]) == "B"
    assert _outcome(deep_states_ok=False) == "B"
    assert _outcome(deep_urls_ok=False) == "B"
    assert _outcome(deep_return_success_ok=False) == "B"
    assert _outcome(deep_horizon_bypass_ok=False) == "B"
    assert _outcome(directory_preserved=False, directory_false_handoff=False) == "B"
    assert _outcome(crm_preserved=False, crm_ops_collapse=False) == "B"
    assert _outcome(ops_preserved=False, crm_ops_collapse=False) == "B"


def test_lab_mechanism_gate_requires_the_finding_trigger():
    facts = passing_facts()
    assert lab_mechanism_gate(facts) is True
    facts["finding_terminal_false_to_true"] = False
    assert lab_mechanism_gate(facts) is False
    facts = passing_facts()
    facts["bug_l9_confirmed"] = False
    assert lab_mechanism_gate(facts) is False


def test_deep_coverage_uses_the_preregistered_bounds():
    previous = {"normalized_unique_urls": 8}
    assert deep_coverage_ok(
        {"states": 24, "normalized_unique_urls": 8, "return_success": 40}, previous,
    ) == {
        "states_ok": True,
        "urls_ok": True,
        "return_success_ok": True,
        "previous_urls": 8,
    }
    collapsed = deep_coverage_ok(
        {"states": 8, "normalized_unique_urls": 6, "return_success": 0}, previous,
    )
    assert collapsed["states_ok"] is False
    assert collapsed["urls_ok"] is False
    assert collapsed["return_success_ok"] is False


def test_directory_preservation_rejects_false_handoff_and_trigger_violations():
    row = {
        "horizon_handoff_started_events": 0,
        "max_handoff_stack_depth": 0,
        "witness_violations": 0,
        "terminal_accounting_violations": 0,
        "repeated_local_action_key_violations": 0,
        "local_action_sequence_accounting_violations": 0,
        "return_entry_accounting_violations": 0,
        "finding_return_entry_trigger_mismatch_violations": 0,
        "finding_return_entry_reused_trigger_violations": 0,
        "finding_return_entry_wrong_instance_violations": 0,
    }
    assert directory_preserved_v0319(row, ["BUG-A"], ["BUG-A"]) is True
    row["horizon_handoff_started_events"] = 1
    assert directory_preserved_v0319(row, ["BUG-A"], ["BUG-A"]) is False
    row["horizon_handoff_started_events"] = 0
    row["finding_return_entry_trigger_mismatch_violations"] = 1
    assert directory_preserved_v0319(row, ["BUG-A"], ["BUG-A"]) is False
