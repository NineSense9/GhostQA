"""Published v0.3.9 outcome is derived from committed evidence."""
import json
import os

from benchmark.algorithm_freeze import DEFAULT_FREEZE, verify_freeze
from benchmark.return_cycle_guard_analysis import (
    HISTORICAL_C1_120, PUBLISHED_ROOT, compute_outcome, derive_bundle,
)
from benchmark.return_cycle_guard_reproduce import (
    CANDIDATE_FREEZE, verify, verify_candidate_identity,
)


def test_outcome_gates_synthetic():
    base = {"n_urls": 4, "return_cycle_escape_events": 0}
    cand_ok = {"return_cycle_escape_events": 1, "post_escape_new_state_count": 5,
               "n_urls": 8, "successful_return_to_parent_events": 0}
    deep = {"confirmed_bugs": ["BUG-D6", "BUG-D7", "BUG-D11", "BUG-D12",
                               "BUG-D13", "BUG-D14"],
            "max_workflow_depth": 4}
    assert compute_outcome(base, cand_ok, deep, deep) == "A"
    cand_none = dict(cand_ok, return_cycle_escape_events=0)
    assert compute_outcome(base, cand_none, deep, deep) == "C"
    deep_lost = dict(deep, confirmed_bugs=["BUG-D6", "BUG-D12"])
    assert compute_outcome(base, cand_ok, deep, deep_lost) == "B"


def test_published_v039_is_outcome_a():
    bundle = derive_bundle(PUBLISHED_ROOT)
    assert bundle["derived"]["outcome"] == "A"
    shop_b = bundle["observed"]["shop"]["baseline"]
    shop_c = bundle["observed"]["shop"]["candidate"]
    assert shop_b["states"] == 6
    assert shop_b["n_urls"] == 4
    assert shop_b["return_attempt_events"] == 116
    assert shop_b["successful_return_to_parent_events"] == 0
    assert shop_c["return_cycle_escape_events"] >= 1
    assert shop_c["post_escape_new_state_count"] >= 1
    assert shop_c["successful_return_to_parent_events"] == 0
    assert shop_c["states"] > 6
    deep_g = [r for r in bundle["observed"]["deepbench"]
              if r["policy"] == "ghost-structural-return-guard" and r["budget"] == 120][0]
    ids = {x.replace("BUG-", "") for x in deep_g["confirmed_bugs"]}
    assert set(HISTORICAL_C1_120) <= ids
    assert deep_g["max_workflow_depth"] >= 4
    assert (deep_g.get("return_cycle_escape_events") or 0) == 0
    assert bundle["derived"]["lost_from_baseline_120"] == []


def test_v039_reproduce_verify():
    assert verify(PUBLISHED_ROOT) == 0


def test_both_freezes_still_pass():
    assert verify_freeze(DEFAULT_FREEZE) == []
    assert verify_candidate_identity(CANDIDATE_FREEZE) == []


def test_protocol_unchanged_rules():
    proto = json.load(open(
        os.path.join("experiments", "validation", "v0.3.9", "protocol.json"),
        encoding="utf-8"))
    assert proto["candidate"] == "ghost-structural-return-guard"
    assert proto["deepbench"]["budgets"] == [40, 80, 120]
    assert proto["shop"]["budgets"] == [120]
    assert set(proto["outcomes"]) == {"A", "B", "C"}
