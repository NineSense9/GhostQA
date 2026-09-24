"""v0.3.20 protocol is preregistered before target generation."""
import hashlib
import json
import os

from benchmark.algorithm_freeze import sha256_file

PROTOCOL = os.path.join("experiments", "validation", "v0.3.20", "protocol.json")
CANDIDATE = "ghostqa/exploration/finding_return_entry_guard.py"
CANDIDATE_SHA = "0bfec3c7bd2811f154daa83bc81fde632976b8ab6e1da9ee6a208cf81c4bb42c"
SEED_PREFIX = "ghostqa-v0.3.20:"
SEEDS = {
    "buggy-campus": (2388280117, "8e5a4335"),
    "buggy-warehouse": (2226848266, "84bb020a"),
    "buggy-studio": (2246306509, "85e3eacd"),
    "buggy-booking": (684480120, "28cc5678"),
    "buggy-catalog": (950621117, "38a953bd"),
    "buggy-kiosk": (655628102, "27141746"),
}
POSITIVE = ("buggy-campus", "buggy-warehouse", "buggy-studio", "buggy-booking")
NEGATIVE = ("buggy-catalog", "buggy-kiosk")


def _proto():
    with open(PROTOCOL, encoding="utf-8") as handle:
        return json.load(handle)


def test_protocol_is_unexecuted_fresh_validation():
    proto = _proto()
    assert proto["executed"] is False
    assert proto["version"] == "v0.3.20"
    assert proto["starting_head"] == "7e730565d043fd5e8744e1882e44686f566a7276"
    assert proto["question_kind"] == "strong-fresh-composite-transfer"
    frozen = proto["frozen_candidate"]
    assert frozen["identity"] == "ghost-structural-finding-return-entry-drain-guard"
    assert frozen["policy"] == "FindingReturnEntryDrainGuardGhostPolicy"
    assert frozen["controller"] == "FindingReturnEntryDrainSequenceController"
    assert frozen["source_sha256"] == CANDIDATE_SHA
    assert frozen["immutable_this_round"] is True
    assert frozen["product_default"] is False
    assert frozen["do_not_edit_source"] is True
    assert sha256_file(CANDIDATE) == CANDIDATE_SHA
    assert proto["matrix"]["cells_total"] == 42
    assert proto["matrix"]["positive_cells"] == 36
    assert proto["matrix"]["negative_cells"] == 6
    assert proto["matrix"]["seed"] == 1
    assert len(proto["matrix"]["cells"]) == 42
    preserved = proto["historical_outcomes_preserved"]
    assert preserved["v0.3.8"] == "structural application-shape diagnosis"
    assert preserved["v0.3.9"] == "A"
    assert preserved["v0.3.10"] == "A"
    assert preserved["v0.3.11"] == "D"
    assert preserved["v0.3.12"] == "C"
    assert preserved["v0.3.13"] == "C"
    assert preserved["v0.3.14"] == "A"
    assert preserved["v0.3.15"] == "C"
    assert preserved["v0.3.16"] == "B"
    assert preserved["v0.3.17"] == "B"
    assert preserved["v0.3.18"] == "C"
    assert preserved["v0.3.19"] == "A"
    assert proto["product_default"]["unchanged"] is True
    assert proto["product_default"]["sequence_mode"] == "off"
    assert proto["product_default"]["outcome_A_promotes"] is False
    assert proto["outcome_gates"]["priority"] == "C, then D, then B, else A"
    assert proto["promotion_readiness"]["outcome_A_only"] == (
        "evidence_supports_productization_study")
    assert "promoted" in proto["promotion_readiness"]["forbidden"]
    assert "production_ready" in proto["promotion_readiness"]["forbidden"]
    assert "default_ready" in proto["promotion_readiness"]["forbidden"]
    assert proto["no_seed_search"] is True
    assert proto["one_graph_per_identity"] is True
    assert proto["bug_census"]["total_judge_bugs"] == 64
    assert proto["qualification"]["branch_horizon"] == 3


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
    for name in POSITIVE:
        assert by_app[name]["class"] == "positive"
        assert by_app[name]["bug_count"] == 12
        assert len(by_app[name]["bug_ids"]) == 12
    for name in NEGATIVE:
        assert by_app[name]["class"] == "negative"
        assert by_app[name]["bug_count"] == 8
        assert len(by_app[name]["bug_ids"]) == 8
    assert by_app["buggy-catalog"]["expected_candidate_events"]["horizon_handoff_started_events"] == 0
    assert by_app["buggy-catalog"]["expected_candidate_events"]["finding_return_entry_trigger_events"] == 0
    assert by_app["buggy-kiosk"]["expected_candidate_events"]["horizon_handoff_started_events"] == 0
    assert by_app["buggy-kiosk"]["finding_drain_may_fire"] is True


def test_protocol_matrix_is_exact():
    proto = _proto()
    expected = []
    for app in POSITIVE:
        for policy in ("C1", "G", "F"):
            for budget in (40, 80, 120):
                expected.append({"app": app, "policy": policy, "budget": budget, "seed": 1})
    for app in NEGATIVE:
        for policy in ("C1", "G", "F"):
            expected.append({"app": app, "policy": policy, "budget": 120, "seed": 1})
    assert proto["matrix"]["cells"] == expected
    assert proto["policies"] == {
        "C1": "ghost-structural-memory",
        "G": "ghost-structural-return-guard",
        "F": "ghost-structural-finding-return-entry-drain-guard",
    }
    ports = proto["runner_ports"]
    assert [ports[name] for name in (*POSITIVE, *NEGATIVE)] == [3951, 3952, 3953, 3954, 3955, 3956]
    assert len({ports[name] for name in SEEDS}) == 6
