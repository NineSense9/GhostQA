"""Synthetic A/B/C/D derivation for the frozen v0.3.21 gate."""
from benchmark.return_waypoint_frontier_analysis import (
    derive_v0321_outcome, passing_facts,
)


def test_outcome_a_when_every_preregistered_gate_passes():
    report = derive_v0321_outcome(**passing_facts())
    assert report["outcome"] == "A"
    assert report["fresh_validation"] is False
    assert report["product_default_changed"] is False
    assert report["mechanism_engaged_count"] == 4


def test_outcome_c_precedes_partial_repair():
    facts = passing_facts()
    facts["regression_vs_v0320_f"] = [{"app": "buggy-campus", "bugs": ["BUG-CP2"]}]
    facts["positives_fully_recovered"] = 3
    assert derive_v0321_outcome(**facts)["outcome"] == "C"

    facts = passing_facts()
    facts["escape_false_success"] = True
    assert derive_v0321_outcome(**facts)["outcome"] == "C"

    facts = passing_facts()
    facts["catalog_waypoint_escapes"] = 1
    assert derive_v0321_outcome(**facts)["outcome"] == "C"

    facts = passing_facts()
    facts["lab_retained"] = False
    assert derive_v0321_outcome(**facts)["outcome"] == "C"

    facts = passing_facts()
    facts["model_raw_traces"] = 100
    assert derive_v0321_outcome(**facts)["outcome"] == "C"


def test_outcome_d_when_the_waypoint_mechanism_misses_three_of_four():
    facts = passing_facts()
    facts["mechanism_engaged_count"] = 2
    facts["residual_escape_count"] = 2
    facts["positives_fully_recovered"] = 1
    facts["template_589_recovered"] = 1
    assert derive_v0321_outcome(**facts)["outcome"] == "D"


def test_outcome_b_when_escape_engages_but_template_repair_is_partial():
    facts = passing_facts()
    facts["positives_fully_recovered"] = 3
    facts["template_589_recovered"] = 3
    report = derive_v0321_outcome(**facts)
    assert report["outcome"] == "B"
    assert report["mechanism_engaged_count"] == 4


def test_outcome_b_when_transfer_is_incomplete_but_safe():
    facts = passing_facts()
    facts["nested_transfer_ok"] = False
    assert derive_v0321_outcome(**facts)["outcome"] == "B"
