"""Nested-hub preemption detector. Measurement only. Counts come from evidence."""
import os

from benchmark.application_shape_evidence import load_json, load_jsonl
from benchmark.nested_hub_detector import (
    detect_nested_hub_preemptions, summarize_preemptions,
)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
V0311 = os.path.join(
    ROOT, "experiments", "published", "multi-target-replication-v0.3.11")


def _cell(app: str, policy: str, budget: int = 120):
    base = os.path.join(V0311, "evidence", app)
    stem = f"{policy}_b{budget}_s1"
    seq = load_json(os.path.join(base, stem + ".sequence_events.json"))
    steps = load_jsonl(os.path.join(base, stem + ".events.jsonl"))
    return seq, steps


def _preempt_script():
    seq = [
        {"step": 0, "event": "hub_seen", "exact_sig": "P", "cluster_id": "pc",
         "branch_key": "", "sequence_instance_id": None},
        {"step": 0, "event": "branch_start", "exact_sig": "P", "cluster_id": "pc",
         "branch_key": "pc:click:a", "sequence_instance_id": "seq-0001"},
        {"step": 1, "event": "hub_seen", "exact_sig": "N", "cluster_id": "nc",
         "branch_key": "", "sequence_instance_id": "seq-0001"},
        {"step": 1, "event": "branch_discovered", "exact_sig": "N",
         "cluster_id": "nc", "branch_key": "nc:click:b",
         "sequence_instance_id": "seq-0001"},
        {"step": 1, "event": "sequence_terminal", "exact_sig": "N",
         "cluster_id": "nc", "branch_key": "pc:click:a",
         "sequence_instance_id": "seq-0001", "outcome": "lost_parent"},
        {"step": 1, "event": "branch_start", "exact_sig": "N", "cluster_id": "nc",
         "branch_key": "nc:click:b", "sequence_instance_id": "seq-0002"},
    ]
    steps = [{
        "kind": "step", "index": 1, "commitment_left": 2, "returning": False,
        "active_branch": "pc:click:a",
        "action": {"type": "click", "target_eid": "b"},
    }]
    return seq, steps


def test_synthetic_commitment_window_preemption_fields():
    seq, steps = _preempt_script()
    rows = detect_nested_hub_preemptions(seq, steps)
    assert len(rows) == 1
    row = rows[0]
    assert row["step"] == 1
    assert row["sequence_instance_id"] == "seq-0001"
    assert row["outer_branch"] == "pc:click:a"
    assert row["outer_parent_hub_sig"] == "P"
    assert row["outer_parent_hub_cluster"] == "pc"
    assert row["nested_hub_sig"] == "N"
    assert row["nested_hub_cluster"] == "nc"
    assert row["nested_branch_key"] == "nc:click:b"
    assert row["nested_action"]["target_eid"] == "b"
    assert row["commitment_left"] == 2
    assert row["returning_before"] is False
    assert row["commitment_window"] is True
    assert row["terminal_outcome"] == "lost_parent"
    assert row["horizon_before_terminal"] is False
    assert row["return_attempt_before_terminal"] is False


def test_horizon_before_terminal_is_not_preemption():
    seq, steps = _preempt_script()
    seq.insert(2, {
        "step": 0, "event": "sequence_horizon_reached", "exact_sig": "P",
        "cluster_id": "pc", "branch_key": "pc:click:a",
        "sequence_instance_id": "seq-0001",
    })
    assert detect_nested_hub_preemptions(seq, steps) == []


def test_return_attempt_before_terminal_is_not_preemption():
    seq, steps = _preempt_script()
    seq.insert(2, {
        "step": 0, "event": "return_attempt", "exact_sig": "P",
        "cluster_id": "pc", "branch_key": "pc:click:a",
        "sequence_instance_id": "seq-0001",
    })
    assert detect_nested_hub_preemptions(seq, steps) == []


def test_zero_commitment_is_not_commitment_window():
    seq, steps = _preempt_script()
    steps[0]["commitment_left"] = 0
    steps[0]["returning"] = True
    rows = detect_nested_hub_preemptions(seq, steps)
    assert len(rows) == 1
    assert rows[0]["commitment_window"] is False


def test_v0311_guard_crm_ops_preempt_wiki_reaches_return():
    guard = "ghost-structural-return-guard"
    crm_seq, crm_steps = _cell("buggy-crm", guard)
    ops_seq, ops_steps = _cell("buggy-ops", guard)
    wiki_seq, wiki_steps = _cell("buggy-wiki", guard)
    crm = summarize_preemptions(crm_seq, crm_steps)
    ops = summarize_preemptions(ops_seq, ops_steps)
    wiki = summarize_preemptions(wiki_seq, wiki_steps)
    assert crm["preemptions"] > 0
    assert crm["commitment_window_preemptions"] > 0
    assert crm["return_attempt_events"] == 0
    assert crm["sequence_horizon_reached"] == 0
    assert ops["preemptions"] > 0
    assert ops["commitment_window_preemptions"] > 0
    assert ops["return_attempt_events"] == 0
    assert ops["sequence_horizon_reached"] == 0
    assert wiki["return_attempt_events"] > 0
    assert wiki["sequence_horizon_reached"] > 0
    assert wiki["preemptions"] < crm["preemptions"]
    assert wiki["preemptions"] < ops["preemptions"]
    assert crm["examples"][0]["horizon_before_terminal"] is False
    assert crm["examples"][0]["return_attempt_before_terminal"] is False


def test_v0311_c1_crm_ops_same_preemption_class():
    c1 = "ghost-structural-memory"
    for app in ("buggy-crm", "buggy-ops"):
        seq, steps = _cell(app, c1)
        summary = summarize_preemptions(seq, steps)
        assert summary["commitment_window_preemptions"] > 0
        assert summary["return_attempt_events"] == 0
        assert summary["sequence_horizon_reached"] == 0
