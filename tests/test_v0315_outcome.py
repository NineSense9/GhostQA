"""Synthetic A/B/C/D and detector matching. No browser and no frozen counts."""
from benchmark.fresh_handoff_analysis import (
    derive_v0315_outcome, match_candidate_events, opportunities_from_trace,
)


def _ok(**overrides):
    payload = dict(
        candidate_freeze_ok=True,
        suite_freeze_ok=True,
        protocol_ok=True,
        static_qualification_ok=True,
        historical_safety_ok=True,
        source_isolation_ok=True,
        witness_violations=0,
        terminal_accounting_violations=0,
        app_specific_logic=False,
        bug_loss_apps=[],
        negative_control_handoffs=0,
        product_default_changed=False,
        post_freeze_tuning=False,
        judge_leakage=False,
        actual_evaluable_positive_targets=3,
        full_transfer_targets=2,
    )
    payload.update(overrides)
    return derive_v0315_outcome(**payload)


def test_outcome_a_is_transfer_not_promotion():
    result = _ok()
    assert result["outcome"] == "A"
    assert result["promotion_readiness"] == "evidence_supports_productization_study"
    assert result["product_default_changed"] is False
    assert result["generalization_claim"] is False


def test_outcome_b_when_transfer_is_below_two():
    result = _ok(full_transfer_targets=1, actual_evaluable_positive_targets=2)
    assert result["outcome"] == "B"
    assert result["promotion_readiness"] == "not_ready"


def test_outcome_d_when_fewer_than_two_are_evaluable():
    result = _ok(actual_evaluable_positive_targets=1, full_transfer_targets=1)
    assert result["outcome"] == "D"
    assert result["promotion_readiness"] == "not_ready"


def test_outcome_c_precedes_d_and_a():
    assert _ok(negative_control_handoffs=1, actual_evaluable_positive_targets=0)["outcome"] == "C"
    assert _ok(bug_loss_apps=["buggy-forum"])["outcome"] == "C"
    assert _ok(witness_violations=1)["outcome"] == "C"
    assert _ok(product_default_changed=True)["outcome"] == "C"
    assert _ok(candidate_freeze_ok=False)["outcome"] == "C"
    assert _ok(post_freeze_tuning=True)["outcome"] == "C"
    assert _ok()["promotion_readiness"] != "promoted"


def _trace(step, commitment, hub, returning=False, active="outer"):
    return [
        {
            "kind": "step", "index": step, "commitment_left": commitment,
            "returning": returning, "active_branch": active,
            "src_sig": "parent-sig", "src_cluster": "parent-cluster",
            "src_url": "http://127.0.0.1/thread.html",
            "dst_sig": "child-sig", "dst_url": "http://127.0.0.1/leaf.html",
            "n_nodes": 3,
            "action": {"type": "click", "target_eid": "open_leaf"},
        },
        {"kind": "seq_after", "step": step, "is_hub": hub},
    ]


def test_detector_separates_continuation_and_handoff():
    rows = _trace(1, 2, True) + _trace(2, 1, True)
    opps = opportunities_from_trace(rows)
    assert [item["kind"] for item in opps] == ["continuation", "handoff"]
    events = [
        {"event": "nested_continuation", "step": 1, "commitment_before": 2},
        {
            "event": "horizon_handoff_started", "step": 2,
            "child_parent_sig": "parent-sig",
            "child_sequence_instance_id": "seq-0002",
        },
        {
            "event": "child_parent_witness", "step": 4,
            "child_sequence_instance_id": "seq-0002",
        },
        {"event": "parent_frame_resume_to_return", "step": 4},
    ]
    matched = match_candidate_events(events, rows)
    assert matched["ok"] is True
    assert matched["continuation_opportunities"] == 1
    assert matched["handoff_opportunities"] == 1


def test_unmatched_handoff_and_resume_fail():
    bad = match_candidate_events(
        [{"event": "horizon_handoff_started", "step": 9, "child_parent_sig": "x",
          "child_sequence_instance_id": "seq-1"}],
        _trace(1, 2, True))
    assert bad["ok"] is False
    resume = match_candidate_events(
        [{"event": "parent_frame_resume_to_return", "step": 3}], [])
    assert any("resume" in item for item in resume["failures"])
    unwind = match_candidate_events(
        [{"event": "horizon_handoff_unwind", "step": 5, "reason": "child_return_cycle_escape"}],
        [])
    assert any("unwind" in item for item in unwind["failures"])
    escaped = match_candidate_events(
        [
            {"event": "return_cycle_escape", "step": 5},
            {"event": "horizon_handoff_unwind", "step": 5},
        ],
        [])
    assert escaped["ok"] is True
