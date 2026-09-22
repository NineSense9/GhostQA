"""Synthetic A/B/C/D gates. Target evidence is not an input here."""
from benchmark.horizon_handoff_analysis import derive_v0314_outcome, mechanism_repair


def _safe(**overrides):
    values = dict(
        candidate_freeze_ok=True,
        historical_freezes_ok=True,
        h_series_failures=0,
        model_invariant_failures=0,
        historical_safety_regressed=False,
        witness_violations=0,
        terminal_accounting_violations=0,
        return_inflation=False,
        wrong_child_or_parent_resume=False,
        app_specific_logic=False,
        product_default_changed=False,
        post_freeze_semantic_tuning=False,
        crm_repair=True,
        ops_repair=True,
        confirmed={
            "buggy-desk": [
                "BUG-K1", "BUG-K2", "BUG-K3", "BUG-K5", "BUG-K6", "BUG-K9", "BUG-K10"],
            "deepbench": [
                "BUG-D6", "BUG-D7", "BUG-D11", "BUG-D12", "BUG-D13", "BUG-D14"],
            "wiki": ["BUG-W2"],
            "buggy-shop": ["BUG-W5", "BUG-W6", "BUG-W9", "BUG-W10"],
        },
    )
    values.update(overrides)
    return derive_v0314_outcome(**values)


def _cell(**overrides):
    row = dict(
        states=12,
        normalized_unique_urls=8,
        commitment_window_preemptions=0,
        nested_continuation_events=3,
        horizon_handoff_started_events=2,
        sequence_horizon_reached=1,
        return_attempt_events=1,
        sequence_instances_returned=0,
        return_cycle_escape_events=0,
        parent_frame_resume_to_return_events=1,
        horizon_handoff_unwind_events=0,
        max_handoff_stack_depth=1,
        witness_violations=0,
    )
    row.update(overrides)
    return row


def test_outcome_priority_is_c_then_d_then_b_then_a():
    assert _safe()["outcome"] == "A"
    assert _safe()["promotion_prohibited"] is True
    assert _safe()["product_default_changed"] is False
    mixed = _safe(confirmed={
        "buggy-desk": ["BUG-K3", "BUG-K5", "BUG-K6", "BUG-K9", "BUG-K10"],
        "deepbench": ["BUG-D6", "BUG-D7", "BUG-D11", "BUG-D12", "BUG-D13", "BUG-D14"],
        "wiki": ["BUG-W2"],
        "buggy-shop": ["BUG-W5", "BUG-W6", "BUG-W9", "BUG-W10"],
    })
    assert mixed["outcome"] == "B"
    assert "BUG-K1" in mixed["lost_vs_guard"]["buggy-desk"]
    assert _safe(crm_repair=False)["outcome"] == "D"
    assert _safe(ops_repair=False)["outcome"] == "D"
    assert _safe(witness_violations=1, crm_repair=False)["outcome"] == "C"
    assert _safe(model_invariant_failures=1)["outcome"] == "C"
    assert _safe(h_series_failures=1)["outcome"] == "C"
    assert _safe(product_default_changed=True)["outcome"] == "C"
    assert _safe(return_inflation=True)["outcome"] == "C"
    assert _safe(wrong_child_or_parent_resume=True)["outcome"] == "C"
    assert _safe(post_freeze_semantic_tuning=True)["outcome"] == "C"
    assert _safe()["v0_3_13_outcome_preserved"] == "C"
    assert _safe()["v0_3_12_outcome_preserved"] == "C"
    assert _safe()["v0_3_11_outcome_preserved"] == "D"


def test_mechanism_repair_requires_lifecycle_not_more_states_than_flattening():
    guard = {"states": 5, "normalized_unique_urls": 5}
    assert mechanism_repair(_cell(), guard)["pass"] is True
    assert mechanism_repair(_cell(states=6, normalized_unique_urls=6), guard)["pass"] is True
    assert mechanism_repair(_cell(states=5), guard)["pass"] is False
    assert mechanism_repair(_cell(nested_continuation_events=0), guard)["pass"] is False
    assert mechanism_repair(_cell(horizon_handoff_started_events=0), guard)["pass"] is False
    assert mechanism_repair(_cell(sequence_horizon_reached=0), guard)["pass"] is False
    assert mechanism_repair(_cell(return_attempt_events=0), guard)["pass"] is False
    assert mechanism_repair(_cell(commitment_window_preemptions=1), guard)["pass"] is False
    pathological = _cell(
        horizon_handoff_started_events=80,
        parent_frame_resume_to_return_events=0,
        horizon_handoff_unwind_events=0,
        max_handoff_stack_depth=80,
        sequence_horizon_reached=0,
        return_attempt_events=1,
    )
    assert mechanism_repair(pathological, guard)["pass"] is False
    assert mechanism_repair(_cell(), {"states": 20, "normalized_unique_urls": 13})["pass"] is False
    assert mechanism_repair(_cell(witness_violations=1), guard)["pass"] is False
