"""Synthetic v0.3.20 outcome gates. No browser and no fresh policy run."""
from benchmark.fresh_composite_analysis import (
    derive_v0320_outcome, horizon_only_drain_count, trigger_audit,
)


def _cell():
    return {
        "states": 10, "normalized_unique_urls": 8, "confirmed_bugs": ["BUG-1"],
        "horizon_handoff_started_events": 0, "finding_return_entry_trigger_events": 0,
        "return_entry_drain_started_events": 0, "max_handoff_stack_depth": 0,
    }


def _positive(full=True):
    view = {
        "cells": {"C1": _cell(), "G": _cell(), "F": _cell()},
        "audits": {"F": {
            "horizon_only_drains": 0, "terminal_violations": 0, "witness_violations": 0,
            "accounting_violations": 0,
            "trigger_audit": {
                "trigger_mismatch_violations": 0,
                "reused_trigger_violations": 0,
                "wrong_instance_violations": 0,
            },
        }},
        "nested_evaluable": True,
        "finding_evaluable": True,
        "composite_evaluable": True,
        "nested_transfer": full,
        "finding_drain_transfer": full,
        "full_transfer": full,
        "lost_vs_guard": [],
        "horizon_control_reached": True,
    }
    return {
        "qualification": {"qualified": True, "class": "positive"},
        "at_120": view,
    }


def _controls():
    catalog = _positive(False)
    catalog["qualification"] = {"qualified": True, "class": "negative"}
    catalog["at_120"]["composite_evaluable"] = False
    catalog["at_120"]["nested_evaluable"] = False
    catalog["at_120"]["finding_evaluable"] = False
    catalog["at_120"]["nested_transfer"] = False
    catalog["at_120"]["finding_drain_transfer"] = False
    catalog["at_120"]["full_transfer"] = False
    kiosk = _positive(False)
    kiosk["qualification"] = {"qualified": True, "class": "negative"}
    kiosk["at_120"]["nested_evaluable"] = False
    kiosk["at_120"]["nested_transfer"] = False
    kiosk["at_120"]["full_transfer"] = False
    kiosk["at_120"]["finding_evaluable"] = True
    kiosk["at_120"]["finding_drain_transfer"] = True
    return catalog, kiosk


def _report(full=True, **flags):
    catalog, kiosk = _controls()
    base_flags = {
        "candidate_freeze_ok": True,
        "suite_freeze_ok": True,
        "protocol_ok": True,
        "source_isolation_ok": True,
        "historical_safety_ok": True,
        "judge_leak": False,
        "post_freeze_tuning": False,
        "app_specific_logic": False,
        "product_default_changed": False,
        "clean_clone_mismatch": False,
    }
    base_flags.update(flags)
    return {
        "flags": base_flags,
        "targets": {
            "buggy-campus": _positive(full),
            "buggy-warehouse": _positive(full),
            "buggy-studio": _positive(full),
            "buggy-booking": _positive(False),
            "buggy-catalog": catalog,
            "buggy-kiosk": kiosk,
        },
    }


def test_outcome_a_when_three_transfer():
    got = derive_v0320_outcome(_report(True))
    assert got["outcome"] == "A"
    assert got["promotion_readiness"] == "evidence_supports_productization_study"
    assert got["full_transfer_positive_targets"] == 3
    assert got["product_default_changed"] is False
    assert got["generalization_claim"] is False


def test_outcome_b_when_transfer_is_short():
    got = derive_v0320_outcome(_report(False))
    assert got["outcome"] == "B"
    assert got["promotion_readiness"] == "not_ready"


def test_outcome_d_when_kiosk_is_not_finding_evaluable():
    report = _report(True)
    report["targets"]["buggy-kiosk"]["at_120"]["finding_evaluable"] = False
    got = derive_v0320_outcome(report)
    assert got["outcome"] == "D"


def test_outcome_d_when_fewer_than_three_composite():
    report = _report(True)
    report["targets"]["buggy-campus"]["at_120"]["composite_evaluable"] = False
    report["targets"]["buggy-warehouse"]["at_120"]["composite_evaluable"] = False
    got = derive_v0320_outcome(report)
    assert got["outcome"] == "D"


def test_outcome_c_on_guard_loss_or_catalog_event():
    report = _report(True)
    report["targets"]["buggy-booking"]["at_120"]["lost_vs_guard"] = ["BUG-BK1"]
    assert derive_v0320_outcome(report)["outcome"] == "C"
    report = _report(True)
    report["targets"]["buggy-catalog"]["at_120"]["cells"]["F"]["horizon_handoff_started_events"] = 1
    assert derive_v0320_outcome(report)["outcome"] == "C"
    report = _report(True)
    report["flags"]["product_default_changed"] = True
    got = derive_v0320_outcome(report)
    assert got["outcome"] == "C"
    assert got["promotion_readiness"] == "not_ready"


def test_trigger_and_horizon_audits():
    events = [
        {"event": "sequence_terminal", "step": 4, "outcome": "finding", "branch_key": "b"},
        {"event": "finding_return_entry_trigger", "step": 4, "branch_key": "b",
         "terminal_outcome": "finding", "sequence_instance_id": "seq-1", "terminal_event_index": 3},
        {"event": "return_entry_drain_started", "step": 4, "branch_key": "b"},
        {"event": "sequence_horizon_reached", "step": 9, "branch_key": "h"},
    ]
    audit = trigger_audit(events)
    assert audit["trigger_mismatch_violations"] == 0
    assert audit["reused_trigger_violations"] == 0
    assert horizon_only_drain_count(events) == 0
    events.append({"event": "return_entry_drain_started", "step": 9, "branch_key": "h"})
    assert horizon_only_drain_count(events) == 1
    assert trigger_audit(events)["trigger_mismatch_violations"] > 0
