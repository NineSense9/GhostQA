"""The v0.3.19 trigger-context audit is recomputed from committed evidence."""
import os

from benchmark.application_shape_evidence import canonical_json_bytes, load_json, sha256_bytes
from benchmark.finding_return_entry_audit import build_trigger_context_analysis

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PATH = os.path.join(
    ROOT, "experiments", "validation", "v0.3.19", "v0318-trigger-context-analysis.json")
PROTOCOL = os.path.join(ROOT, "experiments", "validation", "v0.3.19", "protocol.json")
EXPECTED = {
    "buggy-billing": (7, 1),
    "buggy-crm": (0, 4),
    "buggy-desk": (1, 5),
    "buggy-directory": (1, 0),
    "buggy-forum": (3, 1),
    "buggy-lab": (3, 1),
    "buggy-ops": (0, 0),
    "buggy-shop": (1, 0),
    "deepbench": (0, 1),
    "wiki": (0, 6),
}


def test_trigger_context_analysis_matches_committed_traces():
    report = build_trigger_context_analysis()
    stored = load_json(PATH)
    assert stored == report
    assert sha256_bytes(canonical_json_bytes(report)) == sha256_bytes(open(PATH, "rb").read())
    protocol = load_json(PROTOCOL)
    assert protocol["executed"] is False
    assert protocol["trigger_context_audit"]["sha256"] == sha256_bytes(
        open(PATH, "rb").read())
    assert protocol["starting_head"] == "0acb51103cfe466db1d3b2227e587535f39d8958"
    assert protocol["matrix"]["cells_total"] == 12

    for app, (finding, horizon) in EXPECTED.items():
        block = report["trigger_census"][app]
        assert block["finding_terminal_triggers"] == finding
        assert block["horizon_triggers"] == horizon
        assert block["crash_triggers"] == 0
    assert report["crash_terminal_triggers"] == 0

    stop = report["rejected_finding_stop"]
    assert stop["rejected_before_candidate_design"] is True
    assert stop["finding_stop_would_skip_the_later_probe"] is True
    lab = stop["lab_epochs_where_later_probe_carries_l9"][0]
    assert lab["probe_step"] == 17
    assert lab["probe_eid"] == "btn_close"
    assert lab["probe_assert_ids"] == ["lab_note_visibility"]
    assert lab["next_probe_step"] == 18
    assert lab["next_probe_eid"] == "btn_reopen"
    assert "lab_reopen_clears" in lab["next_assert_ids"]
    named = report["named_finding_then_next_epochs_present"]
    assert named["billing_close_reopen"] is True
    assert named["desk_test_conn_webhook"] is True
    assert named["wiki_watch_unpublish"] is True

    deep = report["deep_harmful_epoch"]
    assert deep["trigger"]["step"] == 7
    assert deep["trigger"]["kind"] == "horizon"
    assert deep["trigger"]["horizon_reached"] is True
    assert deep["trigger"]["terminal_outcomes"] == []
    assert [probe["eid"] for probe in deep["probes"][:2]] == ["btn_login", "btn_demo_login"]
    assert "dead_action" in deep["probes"][0]["browser"]["finding_kinds"]
    assert deep["probes"][0]["left_hub"] is False
    assert deep["probes"][1]["left_hub"] is True
    assert deep["states"] == 8
    assert deep["urls"] == 6
    assert deep["return_success"] == 0
    assert deep["lost_vs_guard"] == [
        "BUG-D11", "BUG-D12", "BUG-D13", "BUG-D14", "BUG-D6", "BUG-D7",
    ]

    useful = report["lab_l9_epoch"]
    assert useful["trigger"]["kind"] == "finding"
    assert useful["trigger"]["step"] == 16
    assert "sequence_terminal" in useful["trigger"]["same_step_events"]
    assert [probe["eid"] for probe in useful["probes"][:2]] == ["btn_close", "btn_reopen"]
    assert useful["return_attempts_unchanged_across_recorded_probes"] is True
    assert useful["lost_vs_lab_guard"] == []
    assert "BUG-L9" in useful["confirmed_bugs"]

    previous = report["v0317_historical_preservation"]
    assert previous["deepbench"]["states"] == 24
    assert previous["deepbench"]["normalized_unique_urls"] == 8
    assert previous["deepbench"]["return_success"] == 40
    assert previous["deepbench"]["lost_vs_guard"] == []
    assert previous["deepbench"]["guard_urls_recorded"] is None
    assert previous["wiki"]["contains_w2"] is True
    assert previous["buggy-directory"]["preserved"] is True
    assert previous["buggy-directory"]["horizon_handoff_started_events"] == 0
    assert previous["buggy-forum"]["full_transfer"] is True
    assert previous["buggy-billing"]["full_transfer"] is True
    assert previous["buggy-crm"]["pass"] is True
    assert previous["buggy-ops"]["pass"] is True
    assert previous["buggy-desk"]["lost_vs_guard"] == []
    assert previous["buggy-shop"]["lost_vs_guard"] == []
    assert report["causal_claim"] is False
