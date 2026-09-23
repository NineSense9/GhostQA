"""The v0.3.16 failure audit is recomputed from committed v0.3.15 evidence."""
import os

from benchmark.application_shape_evidence import canonical_json_bytes, load_json, sha256_bytes
from benchmark.reentry_frontier_audit import build_failure_analysis

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PATH = os.path.join(
    ROOT, "experiments", "validation", "v0.3.16", "v0315-failure-analysis.json")


def test_failure_analysis_matches_committed_traces():
    report = build_failure_analysis()
    stored = load_json(PATH)
    assert stored == report
    assert sha256_bytes(canonical_json_bytes(report)) == sha256_bytes(
        open(PATH, "rb").read())
    directory = report["directory"]
    assert directory["handoff_count"] == 2
    assert directory["same_parent_exact_handoff_count"] == 2
    assert directory["same_parent_cluster_handoff_count"] == 2
    assert [row["step"] for row in directory["events"]] == [13, 67]
    assert all(row["preceding_lands_on_suspended_parent_exact"] for row in directory["events"])
    census = report["same_parent_census"]
    assert census["buggy-forum"]["total_handoffs"] == 11
    assert census["buggy-forum"]["same_parent_cluster"] == 1
    assert census["buggy-billing"]["total_handoffs"] == 6
    assert census["buggy-billing"]["same_parent_cluster"] == 1
    assert census["buggy-lab"]["total_handoffs"] == 11
    assert census["buggy-lab"]["same_parent_cluster"] == 3
    assert census["buggy-directory"]["total_handoffs"] == 2
    assert census["buggy-directory"]["same_parent_cluster"] == 2
    split = report["lab_first_divergence"]
    assert split["first_divergent_step"] == 13
    assert split["guard"]["target_eid"] == "open_result_from_run"
    assert split["horizon"]["target_eid"] == "nav_up_exp"
    lost = report["lab_lost_bugs"]
    assert lost["BUG-L1"]["guard_first_hit"]["index"] == 99
    assert lost["BUG-L1"]["guard_first_hit"]["dst_url"] == "/samples.html"
    assert lost["BUG-L8"]["guard_first_hit"]["index"] == 29
    assert lost["BUG-L8"]["guard_first_hit"]["finding_assert_ids"] == ["lab_heat_matches"]
    assert lost["BUG-L9"]["guard_first_hit"]["index"] == 74
    assert "lab_reopen_clears" in lost["BUG-L9"]["guard_first_hit"]["finding_assert_ids"]
    assert lost["BUG-L10"]["guard_first_hit"]["index"] == 30
    assert lost["BUG-L10"]["guard_first_hit"]["finding_assert_ids"] == ["lab_note_visibility"]
    for bug_id in ("BUG-L1", "BUG-L8", "BUG-L9", "BUG-L10"):
        assert lost[bug_id]["horizon_never_hits"] is True
    assert "direct causal attribution is not established" in lost["BUG-L1"]["causality"]
    assert "direct causal attribution is not established" in lost["BUG-L9"]["causality"]
    assert report["confirmed_at_120"]["buggy-lab"]["lost_vs_guard"] == [
        "BUG-L1", "BUG-L10", "BUG-L8", "BUG-L9",
    ]
