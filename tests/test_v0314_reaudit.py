"""Corrected v0.3.13 restore re-audit. Counts come from committed traces."""
import json
import os

from benchmark.application_shape_evidence import canonical_json_bytes, sha256_bytes
from benchmark.nested_stack_analysis import stack_audit
from benchmark.v0313_restore_reaudit import (
    PUBLISHED_ROOT, VALIDATION_JSON, audit_trace, build_report,
)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _report():
    return build_report(os.path.join(ROOT, PUBLISHED_ROOT))


def test_published_traces_match_the_measurement_erratum():
    report = _report()
    desk = report["apps"]["buggy-desk"]
    deep = report["apps"]["deepbench"]
    wiki = report["apps"]["wiki"]
    assert desk["resume_count"] == 28
    assert desk["old_bad_restore_count"] == 1
    assert desk["same_step_finding_witness_count"] == 1
    assert desk["same_step_crash_witness_count"] == 0
    assert desk["corrected_residual_bad_count"] == 0
    assert desk["corrected_bad_examples"] == []
    assert desk["browser_step_join_verified"] is True
    assert desk["v0313_reference_outcome"] == "C"
    assert deep["resume_count"] == 44
    assert deep["old_bad_restore_count"] == 33
    assert deep["same_step_finding_witness_count"] == 33
    assert deep["corrected_residual_bad_count"] == 0
    assert deep["browser_step_join_verified"] is True
    assert wiki["resume_count"] == 16
    assert wiki["old_bad_restore_count"] == 0
    assert wiki["same_step_returned_count"] == 16
    assert wiki["corrected_residual_bad_count"] == 0
    for app in ("buggy-crm", "buggy-ops", "buggy-shop"):
        row = report["apps"][app]
        assert row["resume_count"] == 0
        assert row["old_bad_restore_count"] == 0
        assert row["corrected_residual_bad_count"] == 0
        assert row["browser_step_join_verified"] is True
        assert row["v0313_reference_outcome"] == "C"


def test_clearing_the_old_restore_flag_leaves_outcome_c():
    report = _report()
    gate = report["counterfactual_gate"]
    assert report["v0313_published_outcome"] == "C"
    assert report["publication_rewritten"] is False
    assert gate["restore_without_child_return"] is False
    assert gate["counterfactual_outcome"] == "C"
    assert gate["crm_repair"] is False
    assert gate["ops_repair"] is False
    assert gate["promotable"] is False
    assert gate["lost_vs_guard"]["buggy-desk"] == ["BUG-K1", "BUG-K2"]
    assert gate["lost_vs_guard"]["deepbench"] == [
        "BUG-D11", "BUG-D13", "BUG-D14", "BUG-D7"]
    assert gate["lost_vs_guard"]["wiki"] == ["BUG-W2"]
    assert gate["additional_lost"]["buggy-desk"] == ["BUG-K1", "BUG-K2"]
    published = os.path.join(ROOT, "experiments", "published", "nested-stack-v0.3.13")
    summary = open(
        os.path.join(published, "summary.md"), encoding="utf-8").read()
    assert summary.startswith("# GhostQA v0.3.13 — Outcome C")


def test_committed_reaudit_matches_regenerated_report():
    path = os.path.join(ROOT, VALIDATION_JSON)
    committed = json.loads(open(path, encoding="utf-8").read())
    fresh = _report()
    assert committed == fresh
    assert sha256_bytes(canonical_json_bytes(fresh)) == sha256_bytes(
        canonical_json_bytes(committed))


def _resume_fixture(*, dst_sig, dst_cluster, outcome, escape=False):
    seq = [
        {
            "event": "branch_start",
            "step": 1,
            "sequence_instance_id": "seq-0002",
            "exact_sig": "parent:v1",
            "cluster_id": "parent-cluster",
            "branch_key": "parent-cluster:click:go",
        },
        {
            "event": "parent_frame_suspended",
            "step": 1,
            "stack_depth": 1,
            "suspended_sequence_instance_id": "seq-0001",
            "commitment_left": 1,
        },
        {
            "event": "sequence_terminal",
            "step": 2,
            "sequence_instance_id": "seq-0002",
            "outcome": outcome,
            "branch_key": "parent-cluster:click:go",
        },
        {
            "event": "parent_frame_resumed",
            "step": 2,
            "stack_depth": 0,
            "reason": "child_returned_to_parent",
            "child_parent_matched": True,
            "remaining_commitment": 1,
            "resumed_sequence_instance_id": "seq-0001",
            "suspended_sequence_instance_id": "seq-0001",
            "child_sequence_instance_id": "seq-0002",
            "child_branch": "parent-cluster:click:go",
        },
    ]
    if escape:
        seq.append({
            "event": "return_cycle_escape",
            "step": 2,
            "sequence_instance_id": "seq-0002",
        })
    browser = [{
        "kind": "step",
        "index": 2,
        "dst_sig": dst_sig,
        "dst_cluster": dst_cluster,
    }]
    return seq, browser


def test_same_step_finding_with_cluster_witness_is_not_a_false_restore():
    seq, browser = _resume_fixture(
        dst_sig="parent:v2", dst_cluster="parent-cluster", outcome="finding")
    old = stack_audit(seq)
    assert old["restore_without_child_return"] is True
    audit = audit_trace(seq, browser)
    assert audit["old_bad_restore_count"] == 1
    assert audit["same_step_finding_witness_count"] == 1
    assert audit["corrected_residual_bad_count"] == 0
    assert audit["resumes"][0]["witness_strength"] == "cluster"


def test_wrong_parent_and_escape_remain_residual():
    wrong_seq, wrong_browser = _resume_fixture(
        dst_sig="other:v", dst_cluster="other-cluster", outcome="finding")
    wrong = audit_trace(wrong_seq, wrong_browser)
    assert wrong["corrected_residual_bad_count"] == 1
    assert "parent_mismatch" in wrong["corrected_bad_examples"][0]["reasons"]
    esc_seq, esc_browser = _resume_fixture(
        dst_sig="parent:v1", dst_cluster="parent-cluster",
        outcome="returned", escape=True)
    escaped = audit_trace(esc_seq, esc_browser)
    assert escaped["corrected_residual_bad_count"] == 1
    assert "escape_same_step" in escaped["resumes"][0]["reasons"]


def test_resume_without_a_browser_step_is_not_accepted():
    seq, _browser = _resume_fixture(
        dst_sig="parent:v1", dst_cluster="parent-cluster", outcome="returned")
    audit = audit_trace(seq, [])
    assert audit["browser_step_join_verified"] is False
    assert audit["corrected_residual_bad_count"] == 1
    assert "missing_browser_step" in audit["corrected_bad_examples"][0]["reasons"]
