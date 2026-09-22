"""Published v0.3.11 outcome is derived from committed evidence."""
import json
import os

import pytest

from benchmark.algorithm_freeze import DEFAULT_FREEZE, verify_freeze
from benchmark.multi_target_analysis import (
    APP_NAMES, PUBLISHED_ROOT, derive_suite, derive_v0311_outcome,
)
from benchmark.multi_target_reproduce import verify
from benchmark.return_cycle_guard_reproduce import verify_candidate_identity
from benchmark.return_cycle_accounting import match_escapes_to_opportunities
from benchmark.fresh_transfer_analysis import detect_return_cycle_opportunities, GUARD, PRIMARY_BUDGET
from benchmark.multi_target_analysis import load_cell
from benchmark.target_freeze import V0311_SUITE_FREEZE, V0311_TARGET_FREEZES
from benchmark.algorithm_freeze import verify_freeze as vf

pytestmark = pytest.mark.skipif(
    not os.path.isfile(os.path.join(PUBLISHED_ROOT, "metrics", "metrics.json")),
    reason="v0.3.11 publication not present",
)


def test_published_v0311_recomputes():
    safety = json.load(open(
        os.path.join(PUBLISHED_ROOT, "evidence", "safety", "safety.json"),
        encoding="utf-8"))
    suite = derive_suite(PUBLISHED_ROOT, safety=safety, historical_ok=True, freeze_ok=True)
    metrics = json.load(open(
        os.path.join(PUBLISHED_ROOT, "metrics", "metrics.json"), encoding="utf-8"))
    assert suite["derived"]["outcome"] == metrics["derived"]["outcome"]
    assert suite["derived"]["outcome"] == "D"
    assert suite["derived"]["outcome_meaning"] == "inconclusive suite"
    assert suite["derived"]["evaluable_targets"] == 1
    assert suite["derived"]["transfer_targets"] == 1
    assert suite["derived"]["product_default_changed"] is False
    assert suite["derived"]["generalization_claim"] is False
    assert suite["derived"]["promotion_readiness"] == "not_ready"
    assert suite["derived"]["targets_with_lost_c1_bugs"] == []
    repl = {r["target"]: r for r in metrics["replication"]}
    assert repl["buggy-wiki"]["transfer_demonstrated"] is True
    assert repl["buggy-crm"]["transfer_demonstrated"] is False
    assert repl["buggy-ops"]["transfer_demonstrated"] is False


def test_v0311_reproduce_verify():
    assert verify(PUBLISHED_ROOT) == 0


def test_v0311_freezes_still_pass():
    assert verify_freeze(DEFAULT_FREEZE) == []
    assert verify_candidate_identity() == []
    assert vf(V0311_SUITE_FREEZE) == []
    for path in V0311_TARGET_FREEZES.values():
        assert vf(path) == []


def test_protocol_lock():
    proto = json.load(open(
        os.path.join("experiments", "validation", "v0.3.11", "protocol.json"),
        encoding="utf-8"))
    assert proto["executed"] is False
    assert proto["matrix"]["primary_budgets"] == [40, 80, 120]
    assert proto["matrix"]["seeds"] == [1]
    assert proto["matrix"]["apps"] == list(APP_NAMES)
    assert proto["candidate"]["identity"] == "ghost-structural-return-guard"
    assert set(proto["outcome_gates"]) == {"A", "B", "C", "D"}
    assert proto["product_default"]["unchanged"] is True


def test_per_target_escape_opportunity_and_lifecycle():
    for app in APP_NAMES:
        events, _g, seq = load_cell(PUBLISHED_ROOT, app, GUARD, PRIMARY_BUDGET)
        escapes = [e for e in seq if e.get("event") == "return_cycle_escape"]
        opps = detect_return_cycle_opportunities(seq, events)
        result = match_escapes_to_opportunities(escapes, opps)
        assert result["ok"], (app, result["unmatched_escapes"])
        assert result["matched"] == result["escape_count"]


def test_outcome_function_matches_published():
    safety = json.load(open(
        os.path.join(PUBLISHED_ROOT, "evidence", "safety", "safety.json"),
        encoding="utf-8"))
    suite = derive_suite(PUBLISHED_ROOT, safety=safety, historical_ok=True, freeze_ok=True)
    per = []
    for app, t in suite["targets"].items():
        per.append({
            "name": app,
            "evaluable_opportunity": t.get("evaluable_opportunity"),
            "guard_escapes": t.get("guard_escapes"),
            "post_escape_novelty": t.get("post_escape_novelty"),
            "lost_c1_bugs": t.get("lost_c1_bugs"),
            "lost_meaningful_return_keys": t.get("lost_meaningful_return_keys"),
            "escape_opportunity_ok": t.get("escape_opportunity_ok"),
            "unclassified_escapes": t.get("unclassified_escapes"),
            "return_inflation": t.get("return_inflation"),
        })
    recomputed = derive_v0311_outcome(
        exhaustive_failures=int(safety.get("exhaustive_failures") or 0),
        s1_s7_pass=bool(safety.get("s1_s7_all_pass")),
        per_target=per,
        historical_ok=True, freeze_ok=True)
    assert recomputed["outcome"] == suite["derived"]["outcome"]
