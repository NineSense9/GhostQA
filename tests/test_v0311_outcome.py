"""Synthetic Outcome A/B/C/D gates for v0.3.11. No target-policy runs."""
from benchmark.multi_target_analysis import (
    OUTCOME_MEANING, PROMOTION_NOT_READY, PROMOTION_STUDY, derive_v0311_outcome,
)


def _target(name, *, opp=2, esc=2, novelty=True, lost=None, lost_ret=None,
            unmatched=False, unclassified=0, inflation=False):
    return {
        "name": name,
        "evaluable_opportunity": opp,
        "guard_escapes": esc,
        "post_escape_novelty": novelty,
        "lost_c1_bugs": lost or [],
        "lost_meaningful_return_keys": lost_ret or [],
        "escape_opportunity_ok": not unmatched,
        "unclassified_escapes": unclassified,
        "return_inflation": inflation,
    }


def _ok_three(novelty=(True, True, False)):
    names = ("buggy-crm", "buggy-wiki", "buggy-ops")
    return [_target(n, novelty=novelty[i]) for i, n in enumerate(names)]


def test_outcome_a():
    r = derive_v0311_outcome(
        exhaustive_failures=0, s1_s7_pass=True,
        per_target=_ok_three((True, True, True)))
    assert r["outcome"] == "A"
    assert r["promotion_readiness"] == PROMOTION_STUDY
    assert r["product_default_changed"] is False
    assert OUTCOME_MEANING["A"]


def test_outcome_b_one_transfer():
    r = derive_v0311_outcome(
        exhaustive_failures=0, s1_s7_pass=True,
        per_target=_ok_three((True, False, False)))
    assert r["outcome"] == "B"
    assert r["promotion_readiness"] == PROMOTION_NOT_READY


def test_outcome_c_lost_bug_not_averaged():
    targets = _ok_three((True, True, True))
    targets[2]["lost_c1_bugs"] = ["BUG-O1"]
    r = derive_v0311_outcome(
        exhaustive_failures=0, s1_s7_pass=True, per_target=targets)
    assert r["outcome"] == "C"
    assert r["targets_with_lost_c1_bugs"] == ["buggy-ops"]


def test_outcome_c_exhaustive_failure():
    r = derive_v0311_outcome(
        exhaustive_failures=1, s1_s7_pass=True, per_target=_ok_three())
    assert r["outcome"] == "C"


def test_outcome_c_unclassified_lifecycle():
    targets = _ok_three((True, True, True))
    targets[0]["unclassified_escapes"] = 1
    r = derive_v0311_outcome(
        exhaustive_failures=0, s1_s7_pass=True, per_target=targets)
    assert r["outcome"] == "C"


def test_outcome_c_detector_mismatch():
    targets = _ok_three((True, True, True))
    targets[1]["escape_opportunity_ok"] = False
    r = derive_v0311_outcome(
        exhaustive_failures=0, s1_s7_pass=True, per_target=targets)
    assert r["outcome"] == "C"


def test_outcome_d_too_few_opportunities():
    targets = [
        _target("buggy-crm", opp=0, esc=0, novelty=False),
        _target("buggy-wiki", opp=0, esc=0, novelty=False),
        _target("buggy-ops", opp=1, esc=1, novelty=True),
    ]
    r = derive_v0311_outcome(
        exhaustive_failures=0, s1_s7_pass=True, per_target=targets)
    assert r["outcome"] == "D"


def test_promotion_requires_outcome_a_and_v0310():
    r = derive_v0311_outcome(
        exhaustive_failures=0, s1_s7_pass=True,
        per_target=_ok_three((True, True, True)),
        v0310_outcome_a=False)
    assert r["outcome"] == "A"
    assert r["promotion_readiness"] == PROMOTION_NOT_READY
