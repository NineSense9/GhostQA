"""Synthetic Outcome A/B/C/D gates for v0.3.10. No target-policy runs."""
from benchmark.fresh_transfer_analysis import (
    derive_outcome, detect_return_cycle_opportunities, OUTCOME_MEANING,
)
from benchmark.return_cycle_safety import collect_safety_suite


def _ok_safety():
    return dict(
        s1_escapes=0, s2_escapes=0, s3_escapes=0,
        s4_escapes=1, s4_returned_inflation=0,
        s5_escapes=1, s5_returned_inflation=0,
        escape_counted_returned=False,
        safety_regression=False,
        historical_ok=True, freeze_ok=True,
        c1_confirmed=["BUG-K2"], guard_confirmed=["BUG-K2", "BUG-K5"],
    )


def test_outcome_a():
    o = derive_outcome(
        opportunity_count=2, guard_escapes=1,
        post_escape_novel_state_count=4,
        absent_from_c1_url_count=2,
        **_ok_safety())
    assert o == "A"
    assert OUTCOME_MEANING[o]


def test_outcome_b_no_escape():
    o = derive_outcome(
        opportunity_count=3, guard_escapes=0,
        post_escape_novel_state_count=0,
        **_ok_safety())
    assert o == "B"


def test_outcome_b_escape_no_novelty():
    o = derive_outcome(
        opportunity_count=2, guard_escapes=2,
        post_escape_novel_state_count=0,
        post_escape_novel_url_count=0,
        absent_from_c1_state_count=0,
        absent_from_c1_url_count=0,
        **_ok_safety())
    assert o == "B"


def test_outcome_c_false_escape():
    kw = _ok_safety()
    kw["s1_escapes"] = 1
    o = derive_outcome(opportunity_count=2, guard_escapes=1,
                       post_escape_novel_state_count=3, **kw)
    assert o == "C"


def test_outcome_c_lost_c1_bug():
    kw = _ok_safety()
    kw["guard_confirmed"] = []
    o = derive_outcome(opportunity_count=2, guard_escapes=1,
                       post_escape_novel_state_count=3, **kw)
    assert o == "C"


def test_outcome_c_s4_return_inflation():
    kw = _ok_safety()
    kw["s4_returned_inflation"] = 1
    o = derive_outcome(opportunity_count=2, guard_escapes=1,
                       post_escape_novel_state_count=3, **kw)
    assert o == "C"


def test_outcome_d_no_opportunity():
    o = derive_outcome(
        opportunity_count=0, guard_escapes=0,
        **_ok_safety())
    assert o == "D"


def test_detector_flags_repeat_before_parent():
    seq = [
        {"step": 0, "event": "branch_start", "exact_sig": "P",
         "cluster_id": "p", "branch_key": "p:click:a"},
        {"step": 2, "event": "sequence_horizon_reached", "exact_sig": "A",
         "cluster_id": "a", "branch_key": "p:click:a"},
        {"step": 3, "event": "sequence_action", "exact_sig": "A",
         "cluster_id": "a", "branch_key": "p:click:a"},
        {"step": 4, "event": "sequence_action", "exact_sig": "B",
         "cluster_id": "b", "branch_key": "p:click:a"},
    ]
    steps = [
        {"kind": "step", "index": 3, "dst_sig": "B", "dst_cluster": "b"},
        {"kind": "step", "index": 4, "dst_sig": "B", "dst_cluster": "b"},
    ]
    opps = detect_return_cycle_opportunities(seq, steps)
    assert len(opps) == 1
    assert opps[0]["repeated_destination_sig"] == "B"
    assert opps[0]["return_later_succeeded"] is False


def test_safety_suite_all_pass():
    suite = collect_safety_suite()
    assert suite["all_pass"] is True
    assert suite["s1_escapes"] == 0
    assert suite["s2_escapes"] == 0
    assert suite["s3_escapes"] == 0
    assert suite["s4_escapes"] == 1
    assert suite["s5_escapes"] == 1


def test_detector_parent_match_is_not_opportunity():
    seq = [
        {"step": 0, "event": "branch_start", "exact_sig": "P",
         "cluster_id": "p", "branch_key": "p:click:a"},
        {"step": 2, "event": "sequence_horizon_reached", "exact_sig": "A",
         "cluster_id": "a", "branch_key": "p:click:a"},
        {"step": 3, "event": "sequence_terminal", "outcome": "returned",
         "exact_sig": "P", "cluster_id": "p", "branch_key": "p:click:a"},
    ]
    steps = [
        {"kind": "step", "index": 3, "dst_sig": "P", "dst_cluster": "p"},
    ]
    assert detect_return_cycle_opportunities(seq, steps) == []
