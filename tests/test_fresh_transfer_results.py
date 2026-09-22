"""Published v0.3.10 outcome is derived from committed evidence."""
import json
import os

from benchmark.algorithm_freeze import DEFAULT_FREEZE, verify_freeze
from benchmark.fresh_transfer_analysis import derive_bundle, derive_outcome, PUBLISHED_ROOT
from benchmark.fresh_transfer_reproduce import verify
from benchmark.return_cycle_guard_reproduce import verify_candidate_identity
from benchmark.target_freeze import DESK_FREEZE


def test_published_v0310_is_outcome_a():
    bundle = derive_bundle(PUBLISHED_ROOT)
    assert bundle["derived"]["outcome"] == "A"
    c1 = bundle["c1_120"]
    g = bundle["guard_120"]
    assert c1["c1_opportunity_count"] >= 1
    assert g["return_cycle_escape_events"] >= 1
    assert (g.get("post_escape_novel_state_count") or 0) >= 1 or (
        g.get("absent_from_c1_url_count") or 0) >= 1
    assert bundle["derived"]["lost_c1_confirmed"] == []
    assert bundle["safety"]["all_pass"] is True
    assert bundle["derived"]["product_default_changed"] is False
    assert bundle["derived"]["generalization_claim"] is False


def test_outcome_function_matches_published():
    bundle = derive_bundle(PUBLISHED_ROOT)
    recomputed = derive_outcome(
        opportunity_count=bundle["c1_120"]["c1_opportunity_count"],
        guard_escapes=bundle["guard_120"]["return_cycle_escape_events"],
        post_escape_novel_state_count=bundle["guard_120"]["post_escape_novel_state_count"],
        post_escape_novel_url_count=bundle["guard_120"]["post_escape_novel_url_count"],
        absent_from_c1_state_count=bundle["guard_120"].get("absent_from_c1_state_count") or 0,
        absent_from_c1_url_count=bundle["guard_120"].get("absent_from_c1_url_count") or 0,
        c1_confirmed=bundle["c1_120"]["confirmed_bugs"],
        guard_confirmed=bundle["guard_120"]["confirmed_bugs"],
        s1_escapes=bundle["safety"]["s1_escapes"],
        s2_escapes=bundle["safety"]["s2_escapes"],
        s3_escapes=bundle["safety"]["s3_escapes"],
        s4_escapes=bundle["safety"]["s4_escapes"],
        s4_returned_inflation=bundle["safety"]["s4_returned_inflation"],
        s5_escapes=bundle["safety"]["s5_escapes"],
        s5_returned_inflation=bundle["safety"]["s5_returned_inflation"],
        historical_ok=True, freeze_ok=True,
    )
    assert recomputed == bundle["derived"]["outcome"]


def test_v0310_reproduce_verify():
    assert verify(PUBLISHED_ROOT) == 0


def test_freezes_still_pass():
    assert verify_freeze(DEFAULT_FREEZE) == []
    assert verify_candidate_identity() == []
    assert verify_freeze(DESK_FREEZE) == []


def test_protocol_lock():
    proto = json.load(open(
        os.path.join("experiments", "validation", "v0.3.10", "protocol.json"),
        encoding="utf-8"))
    assert proto["executed"] is False
    assert proto["matrix"]["budgets"] == [40, 80, 120]
    assert proto["matrix"]["seeds"] == [1]
    assert proto["candidate"]["identity"] == "ghost-structural-return-guard"
    assert set(proto["outcome_gates"]) == {"A", "B", "C", "D"}


def test_guard_escapes_match_detector():
    """Every v0.3.10 guard escape maps to a detector opportunity by structured key."""
    from benchmark.fresh_transfer_analysis import GUARD, PRIMARY_BUDGET, load_cell_files
    from benchmark.fresh_transfer_analysis import detect_return_cycle_opportunities
    from benchmark.return_cycle_accounting import match_escapes_to_opportunities

    events, _graph, seq = load_cell_files(PUBLISHED_ROOT, GUARD, PRIMARY_BUDGET)
    escapes = [e for e in seq if e.get("event") == "return_cycle_escape"]
    opps = detect_return_cycle_opportunities(seq, events)
    result = match_escapes_to_opportunities(escapes, opps)
    assert result["ok"], result["unmatched_escapes"]
    assert result["matched"] == result["escape_count"]
    assert result["escape_count"] == result["opportunity_count"]
    assert result["escape_count"] == len(escapes)
    keys = result["escape_keys"]
    assert len(keys) == len(escapes)
    assert len({(k["step"], k["repeated_destination_sig"],
                 k["parent_hub_sig"], k["branch"]) for k in keys}) == len(keys)
    bundle = derive_bundle(PUBLISHED_ROOT)
    assert bundle["c1_120"]["c1_opportunity_count"] >= 1


def test_v0310_escape_count_fallback_removed():
    src = open(__file__, encoding="utf-8").read()
    body = src.split("def test_guard_escapes_match_detector", 1)[1]
    body = body.split("def test_", 1)[0]
    assert " == 7" not in body
    assert "or len(" not in body
    assert "match_escapes_to_opportunities" in body
