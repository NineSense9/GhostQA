"""The v0.3.13 regression analysis is regenerated from committed traces."""
import json
import os

from benchmark.application_shape_evidence import canonical_json_bytes
from benchmark.nested_stack_regression import (
    ANCHOR_CANDIDATE_EID, ANCHOR_REFERENCE_EID, ANCHOR_SRC, ANCHOR_STEP,
    anchor_problems, build_regression_analysis,
)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ARTIFACT = os.path.join(
    ROOT, "experiments", "validation", "v0.3.13", "regression-analysis.json")


def test_regression_analysis_matches_committed_artifact():
    built = build_regression_analysis()
    committed = json.loads(open(ARTIFACT, encoding="utf-8").read())
    assert canonical_json_bytes(built) == canonical_json_bytes(committed)


def test_buggy_desk_divergence_anchor():
    desk = build_regression_analysis()["buggy_desk"]
    assert anchor_problems(desk) == []
    assert desk["first_identical_prefix_length"] == ANCHOR_STEP
    assert desk["first_divergence_step"] == ANCHOR_STEP
    assert desk["reference_action"]["target_eid"] == ANCHOR_REFERENCE_EID
    assert desk["v0_3_12_action"]["target_eid"] == ANCHOR_CANDIDATE_EID
    assert desk["reference_action"]["src_url"] == ANCHOR_SRC
    assert desk["v0_3_12_action"]["src_url"] == ANCHOR_SRC
    assert desk["reference_action"]["dst_url"] == "/activity.html?id=c1"
    assert desk["v0_3_12_action"]["dst_url"] == "/customers.html"
    mech = desk["child_commitment_reset_vs_outer_consumption"]
    assert mech["reference_commitment_before"] == 1
    assert mech["reference_commitment_after"] == mech["branch_horizon"] - 1
    assert mech["v0_3_12_commitment_before"] == 1
    assert mech["v0_3_12_commitment_after"] == 0
    assert desk["commitment_state_at_divergence"]["reference"]["returning"] is False
    assert desk["commitment_state_at_divergence"]["v0_3_12"]["returning"] is True
    only = set(desk["reference_only_urls"])
    assert {
        "/activity.html?id=c2",
        "/customer.html?id=c2",
        "/ticket.html?id=1002",
        "/ticket.html?id=1003",
        "/article.html?id=a2",
        "/article.html?id=a3",
    } <= only
    assert set(desk["candidate_only_urls"]) >= {
        "/settings.html", "/help.html", "/handbook.html",
    }
    lost = {row["id"]: row for row in desk["lost_bug_first_steps"]}
    for bug_id in ("BUG-K3", "BUG-K6", "BUG-K9", "BUG-K10"):
        assert lost[bug_id]["reference_first_match"]["index"] is not None
        assert lost[bug_id]["v0_3_12_first_match"] is None


def test_deepbench_d12_is_consistency_not_proof():
    deep = build_regression_analysis()["deepbench"]
    bug = deep["bug_d12"]
    assert bug["prerequisites"] == ["login", "project", "add-member", "remove"]
    assert bug["match"]["assert_id"] == "member_count_consistent"
    assert bug["reference_confirmed"] is True
    assert bug["v0_3_12_confirmed"] is False
    assert deep["members_nested_followup_count"] >= 1
    assert deep["btn_add_alice_branch_start_count"] == 0
    assert deep["mechanism_consistency"]["causal_proof"] is False
    assert deep["mechanism_consistency"]["consistent_with_buggy_desk_flattening"] is True
    assert any(
        row["nested_branch_key"].endswith("btn_add_alice")
        and "btn_members" in row["outer_branch"]
        for row in deep["members_nested_followups"])
