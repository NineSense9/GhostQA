"""The v0.3.18 return-entry audit is recomputed from committed evidence."""
import os

from benchmark.application_shape_evidence import canonical_json_bytes, load_json, sha256_bytes
from benchmark.return_entry_drain_audit import build_return_entry_analysis

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PATH = os.path.join(
    ROOT, "experiments", "validation", "v0.3.18", "v0317-return-entry-analysis.json")


def test_return_entry_analysis_matches_committed_traces():
    report = build_return_entry_analysis()
    stored = load_json(PATH)
    assert stored == report
    assert sha256_bytes(canonical_json_bytes(report)) == sha256_bytes(
        open(PATH, "rb").read())

    step15 = report["step15_result_return"]
    assert step15["finding_terminal"] is True
    assert step15["finding_outcome"] == "finding"
    assert "sequence_terminal" in step15["same_step_events"]
    assert "horizon_handoff_started" in step15["same_step_events"]
    assert step15["next_is_return_attempt"] is True
    assert step15["next_step"] == 16
    assert step15["drain_started_on_terminal_or_next_step"] is False
    assert step15["drain_started_on_result_cluster"] is False
    assert step15["browser"]["target_eid"] == "open_result_from_run"
    assert step15["browser"]["dst_url"].endswith("/result.html?id=q1") or (
        "result.html" in step15["browser"]["dst_url"])
    assert step15["next_browser"]["src_url"].find("result.html") >= 0
    assert step15["next_browser"]["index"] == 16

    step21 = report["step21_result_return"]
    assert step21["finding_terminal"] is True
    assert "sequence_terminal" in step21["same_step_events"]
    assert "nested_continuation" in step21["same_step_events"]
    assert step21["next_is_return_attempt"] is True
    assert step21["next_step"] == 22
    assert step21["drain_started_on_terminal_or_next_step"] is False
    assert step21["drain_started_on_result_cluster"] is False
    assert step21["browser"]["target_eid"] == "open_result_q1"
    assert "result.html" in step21["browser"]["dst_url"]
    assert "result.html" in step21["next_browser"]["src_url"]

    assert report["result_drain_missing"] is True
    guard = report["guard_l9"]
    assert guard["first_hit"]["index"] == 74
    assert guard["first_hit"]["target_eid"] == "btn_reopen"
    assert "lab_reopen_clears" in guard["first_hit"]["finding_assert_ids"]
    assert guard["btn_close_before_btn_reopen"] is True
    assert report["v0317_only_guard_loss"] == ["BUG-L9"]
    assert report["v0317_lost_vs_guard_confirmed"] == ["BUG-L9"]
    assert report["v0317_lost_vs_guard_reference"] == ["BUG-L9"]
    assert "BUG-L9" not in report["v0317_lab_confirmed"]
    assert "BUG-L9" in report["guard_lab_confirmed"]
