"""The v0.3.26 letter is fixed before any policy result."""
from benchmark.fresh_transfer_v0326_analysis import derive_v0326_outcome, passing_facts


def test_passing_facts_are_outcome_a():
    derived = derive_v0326_outcome(**passing_facts())
    assert derived["outcome"] == "A"
    assert derived["promotion_readiness"] == "not_ready"
    assert derived["product_default_changed"] is False


def test_guard_loss_is_outcome_c_before_structure():
    facts = passing_facts()
    facts["fresh_guard_loss"] = [{"app": "buggy-ward", "bugs": ["BUG-WD12"]}]
    facts["structured_positives"] = 0
    assert derive_v0326_outcome(**facts)["outcome"] == "C"


def test_unevaluable_is_outcome_d_when_safety_holds():
    facts = passing_facts()
    facts["evaluable_positives"] = 2
    facts["structured_positives"] = 0
    assert derive_v0326_outcome(**facts)["outcome"] == "D"


def test_preserved_but_unstructured_is_outcome_b():
    facts = passing_facts()
    facts["evaluable_positives"] = 4
    facts["structured_positives"] = 2
    assert derive_v0326_outcome(**facts)["outcome"] == "B"
