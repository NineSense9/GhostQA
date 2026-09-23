"""The v0.3.17 local-frontier audit is recomputed from committed evidence."""
import os

from benchmark.application_shape_evidence import canonical_json_bytes, load_json, sha256_bytes
from benchmark.local_action_drain_audit import build_local_frontier_analysis

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PATH = os.path.join(
    ROOT, "experiments", "validation", "v0.3.17", "v0316-local-frontier-analysis.json")


def test_local_frontier_analysis_matches_committed_traces():
    report = build_local_frontier_analysis()
    stored = load_json(PATH)
    assert stored == report
    assert sha256_bytes(canonical_json_bytes(report)) == sha256_bytes(
        open(PATH, "rb").read())
    run = report["run_hub"]
    assert run["witness_step"] == 12
    assert run["frontier_count"] == 4
    assert run["frontier_eids"] == [
        "btn_cool", "btn_staff_note", "open_result_from_run", "open_sample_s2",
    ]
    assert run["lease_actions_before_escape"] == [{
        "step": 13,
        "chosen_branch_key": run["lease_actions_before_escape"][0]["chosen_branch_key"],
        "eid": "open_result_from_run",
        "frontier_keys": run["frontier_keys"],
    }]
    assert run["lease_actions_before_escape"][0]["chosen_branch_key"].endswith(
        "open_result_from_run")
    assert run["escape_step"] == 20
    assert run["outer_abandon_outcome"] == "horizon_handoff_abandoned"
    assert run["outer_abandon_reason"] == "child_return_cycle_escape"
    assert run["remaining_frontier_eids"] == [
        "btn_cool", "btn_staff_note", "open_sample_s2",
    ]
    assert report["run_child_does_not_return_to_run_before_escape"]["returns_to_run_html"] is False

    result = report["result_hub"]
    assert result["witness_step"] == 25
    assert result["frontier_eids"] == [
        "btn_close", "btn_reopen", "open_notebook", "open_run_again",
    ]
    assert [row["step"] for row in result["lease_actions_before_escape"]] == [26, 30]
    assert [row["eid"] for row in result["lease_actions_before_escape"]] == [
        "open_notebook", "open_run_again",
    ]
    assert result["escape_step"] == 38
    assert result["outer_abandoned"] is True
    assert result["remaining_frontier_eids"] == ["btn_close", "btn_reopen"]

    guard = report["guard_bugs"]
    assert guard["BUG-L10"]["first_hit"]["index"] == 30
    assert guard["BUG-L10"]["first_hit"]["target_eid"] == "open_result_from_run"
    assert guard["BUG-L10"]["first_hit"]["finding_assert_ids"] == ["lab_note_visibility"]
    l10 = guard["BUG-L10"]["window_eids"]
    assert l10.index("btn_staff_note") < l10.index("open_result_from_run")
    assert guard["BUG-L9"]["first_hit"]["index"] == 74
    assert guard["BUG-L9"]["first_hit"]["target_eid"] == "btn_reopen"
    assert "lab_reopen_clears" in guard["BUG-L9"]["first_hit"]["finding_assert_ids"]
    l9 = guard["BUG-L9"]["window_eids"]
    assert l9.index("btn_close") < l9.index("btn_reopen")
    assert guard["BUG-L8"]["first_hit"]["index"] == 29
    assert guard["BUG-L8"]["first_hit"]["target_eid"] == "btn_cool"
    assert guard["BUG-L8"]["first_hit"]["finding_assert_ids"] == ["lab_heat_matches"]
    assert "BUG-L8" in report["v0316_recovered_vs_guard"]
    assert guard["BUG-L1"]["first_hit"]["index"] == 99
    assert guard["BUG-L1"]["first_hit"]["dst_url"] == "/samples.html"
    assert guard["BUG-L1"]["first_hit"]["target_eid"] == "nav_samples"
    assert report["l1_causal_claim"] is False
    assert "downstream" in guard["BUG-L1"]["causality"]
    assert report["v0316_still_lost_vs_guard"] == ["BUG-L1", "BUG-L10", "BUG-L9"]
