"""v0.3.15 protocol is preregistered before target generation."""
import hashlib
import json
import os

from benchmark.algorithm_freeze import sha256_file

PROTOCOL = os.path.join("experiments", "validation", "v0.3.15", "protocol.json")
CANDIDATE = "ghostqa/exploration/horizon_handoff_guard.py"
CANDIDATE_SHA = "827b8e64f953012ceec06fe3e0302c343a016463b5b1f88191e7a0a486c2467e"
SEED_PREFIX = "ghostqa-v0.3.15:"
SEEDS = {
    "buggy-forum": (2471055070, "93494ede"),
    "buggy-billing": (1583186088, "5e5d80a8"),
    "buggy-lab": (1585316649, "5e7e0329"),
    "buggy-directory": (2239331232, "85797ba0"),
}


def _proto():
    with open(PROTOCOL, encoding="utf-8") as handle:
        return json.load(handle)


def test_protocol_is_unexecuted_fresh_validation():
    proto = _proto()
    assert proto["executed"] is False
    assert proto["version"] == "v0.3.15"
    assert proto["starting_head"] == "6a8f51d86fced3bdb87b8d1851035a202394500a"
    assert proto["question_kind"] == "fresh-multi-target-mechanism-transfer"
    assert proto["frozen_candidate"]["identity"] == "ghost-structural-horizon-handoff-guard"
    assert proto["frozen_candidate"]["immutable_this_round"] is True
    assert proto["frozen_candidate"]["product_default"] is False
    assert proto["frozen_candidate"]["source_sha256"] == CANDIDATE_SHA
    assert sha256_file(CANDIDATE) == CANDIDATE_SHA
    assert proto["frozen_candidate"]["branch_horizon"] == 3
    assert proto["frozen_candidate"]["no_threshold_N"] is True
    assert proto["frozen_candidate"]["no_max_stack_depth"] is True
    assert proto["frozen_candidate"]["no_app_specific_rules"] is True
    assert proto["matrix"]["cells_total"] == 30
    assert proto["matrix"]["positive_cells"] == 27
    assert proto["matrix"]["negative_cells"] == 3
    assert proto["matrix"]["seed"] == 1
    assert len(proto["matrix"]["cells"]) == 30
    assert proto["historical_outcomes_preserved"]["v0.3.11"] == "D"
    assert proto["historical_outcomes_preserved"]["v0.3.12"] == "C"
    assert proto["historical_outcomes_preserved"]["v0.3.13"] == "C"
    assert proto["historical_outcomes_preserved"]["v0.3.14"] == "A"
    assert proto["product_default"]["unchanged"] is True
    assert proto["product_default"]["sequence_mode"] == "off"
    assert proto["product_default"]["outcome_A_promotes"] is False
    assert proto["outcome_gates"]["priority"] == "C, then D, then B, else A"
    assert proto["promotion_readiness"]["outcome_A_only"] == (
        "evidence_supports_productization_study")
    assert "promoted" in proto["promotion_readiness"]["forbidden"]
    assert proto["no_seed_search"] is True
    assert proto["one_graph_per_identity"] is True


def test_protocol_seeds_match_frozen_rule():
    proto = _proto()
    assert proto["seed_prefix"] == SEED_PREFIX
    by_app = {item["app"]: item for item in proto["targets"]}
    assert set(by_app) == set(SEEDS)
    for name, (seed, hex8) in SEEDS.items():
        digest = hashlib.sha256((SEED_PREFIX + name).encode("utf-8")).hexdigest()
        assert digest[:8] == hex8
        assert int(digest[:8], 16) == seed
        assert by_app[name]["seed"] == seed
        assert by_app[name]["seed_hex"] == hex8
    assert by_app["buggy-directory"]["class"] == "negative"
    assert by_app["buggy-directory"]["expected_horizon_handoff_started_events"] == 0
    for name in ("buggy-forum", "buggy-billing", "buggy-lab"):
        assert by_app[name]["class"] == "positive"
        assert by_app[name]["bug_count"] == 10
    assert by_app["buggy-directory"]["bug_count"] == 8


def test_protocol_matrix_is_exact():
    proto = _proto()
    cells = proto["matrix"]["cells"]
    positive = ["buggy-forum", "buggy-billing", "buggy-lab"]
    expected = []
    for app in positive:
        for policy in ("C1", "G", "H"):
            for budget in (40, 80, 120):
                expected.append({"app": app, "policy": policy, "budget": budget, "seed": 1})
    for policy in ("C1", "G", "H"):
        expected.append({"app": "buggy-directory", "policy": policy, "budget": 120, "seed": 1})
    assert cells == expected
    assert proto["policies"] == {
        "C1": "ghost-structural-memory",
        "G": "ghost-structural-return-guard",
        "H": "ghost-structural-horizon-handoff-guard",
    }
    assert proto["runner_ports"]["buggy-forum"] == 3945
    assert proto["runner_ports"]["buggy-directory"] == 3948
    assert len(set(proto["runner_ports"][name] for name in SEEDS)) == 4
