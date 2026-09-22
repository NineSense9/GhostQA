"""Bounded exhaustive safety checker. Independent of fresh targets."""
from benchmark.return_cycle_modelcheck import (
    ALPHABET, TRACE_LENGTHS, compare_trace, run_exhaustive_check,
)
from benchmark.return_cycle_safety import collect_safety_suite


def test_named_rules_r1_r10():
    rec = run_exhaustive_check()
    assert rec["named_failures"] == []
    cases = [
        (("P",), None, 0),
        (("A", "A"), 1, None),
        (("A", "B", "A"), 2, None),
        (("A", "B", "C", "B"), 3, None),
        (("A", "B", "C", "P"), None, 3),
        (("A", "B", "A", "P"), 2, None),
        (("A", "B", "P", "A"), None, 2),
        (("A1", "A2"), None, None),
        (("A1", "A1"), 1, None),
    ]
    for dests, esc, ret in cases:
        got = compare_trace(dests)
        assert got["ok"], dests
        assert got["expected"]["escape_index"] == esc, dests
        assert got["expected"]["return_index"] == ret, dests


def test_exhaustive_enumeration_zero_failures():
    rec = run_exhaustive_check()
    assert rec["traces_enumerated"] >= 4 * (4 ** 6 - 1) // 3  # 5460
    assert rec["failures"] == 0
    assert rec["passed"] == rec["named_plus_enumerated"]
    assert rec["all_pass"] is True
    assert rec["s1_s7_all_pass"] is True
    assert rec["alphabet"] == list(ALPHABET)
    assert rec["trace_lengths"] == list(TRACE_LENGTHS)


def test_s1_s7_still_pass():
    suite = collect_safety_suite()
    assert suite["all_pass"] is True
    assert suite["s1_escapes"] == 0
    assert suite["s2_escapes"] == 0
    assert suite["s3_escapes"] == 0
    assert suite["s4_escapes"] == 1
    assert suite["s5_escapes"] == 1
