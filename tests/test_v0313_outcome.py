"""Synthetic A/B/C/D for the preregistered v0.3.13 outcome function."""
import json
import os

from benchmark.nested_stack_analysis import (
    MIN_EXHAUSTIVE_TRACES, V0312_LOST, app_specific_needles,
    derive_v0313_outcome, stack_audit, structural_repair_gate,
)
from ghostqa.exploration.nested_stack_guard import SuspendedParentSequenceController
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState

try:
    from helpers import make_hub_state, make_seq_el
except ImportError:
    from tests.helpers import make_hub_state, make_seq_el


def _repair_cell():
    return {
        "nested_child_stack_events": 3,
        "commitment_window_preemptions": 0,
        "reached_horizon_or_safe_terminal": True,
        "reached_return_or_child_resume": True,
        "expanded_beyond_guard": True,
    }


def _base(**overrides):
    payload = dict(
        candidate_freeze_ok=True,
        historical_freezes_ok=True,
        p_series_failures=0,
        s1_s7_pass=True,
        exhaustive_failures=0,
        exhaustive_traces=MIN_EXHAUSTIVE_TRACES,
        terminal_accounting_violations=0,
        return_inflation=False,
        stack_frame_corruption=False,
        restore_without_child_return=False,
        app_specific_logic=False,
        product_default_changed=False,
        crm_repair=True,
        ops_repair=True,
        lost_vs_guard={
            "buggy-desk": [],
            "deepbench": [],
            "wiki": [],
            "buggy-shop": [],
        },
    )
    payload.update(overrides)
    return payload


def _outcome(**overrides):
    return derive_v0313_outcome(**_base(**overrides))["outcome"]


def test_outcome_a_when_stack_repairs_and_nothing_is_lost():
    got = derive_v0313_outcome(**_base())
    assert got["outcome"] == "A"
    assert got["outcome_meaning"].startswith("stack repair succeeds")
    assert got["generalization_claim"] is False
    assert got["product_default_changed"] is False
    assert got["promotion_prohibited"] is True
    assert got["v0_3_12_outcome_preserved"] == "C"
    assert got["v0_3_11_outcome_preserved"] == "D"


def test_outcome_b_when_only_v0312_regressions_remain():
    assert _outcome(lost_vs_guard={
        "buggy-desk": ["BUG-K3"],
        "deepbench": [],
        "wiki": [],
        "buggy-shop": [],
    }) == "B"
    assert _outcome(lost_vs_guard={
        "buggy-desk": [],
        "deepbench": ["BUG-D12"],
        "wiki": [],
        "buggy-shop": [],
    }) == "B"


def test_outcome_c_when_a_new_bug_is_lost():
    assert _outcome(lost_vs_guard={
        "buggy-desk": ["BUG-K1", "BUG-K3"],
        "deepbench": [],
        "wiki": [],
        "buggy-shop": [],
    }) == "C"
    assert _outcome(lost_vs_guard={
        "wiki": ["BUG-W2"],
        "buggy-shop": [],
        "buggy-desk": [],
        "deepbench": [],
    }) == "C"
    got = derive_v0313_outcome(**_base(lost_vs_guard={
        "buggy-shop": ["BUG-W5"],
    }))
    assert got["outcome"] == "C"
    assert "buggy-shop" in got["additional_lost"]


def test_outcome_c_dominates_failed_repair():
    assert _outcome(crm_repair=False, ops_repair=False, p_series_failures=1) == "C"
    assert _outcome(
        crm_repair=False, terminal_accounting_violations=2) == "C"
    assert _outcome(return_inflation=True, ops_repair=False) == "C"
    assert _outcome(stack_frame_corruption=True) == "C"
    assert _outcome(restore_without_child_return=True) == "C"
    assert _outcome(app_specific_logic=True) == "C"
    assert _outcome(product_default_changed=True) == "C"
    assert _outcome(candidate_freeze_ok=False) == "C"
    assert _outcome(historical_freezes_ok=False) == "C"
    assert _outcome(s1_s7_pass=False) == "C"
    assert _outcome(exhaustive_failures=1) == "C"
    assert _outcome(exhaustive_traces=MIN_EXHAUSTIVE_TRACES - 1) == "C"


def test_outcome_d_when_preemption_is_not_repaired():
    assert _outcome(crm_repair=False) == "D"
    assert _outcome(ops_repair=False) == "D"
    assert _outcome(crm_repair=False, ops_repair=False) == "D"
    got = derive_v0313_outcome(**_base(
        crm_repair=False,
        lost_vs_guard={"buggy-desk": ["BUG-K3"], "deepbench": ["BUG-D12"]},
    ))
    assert got["outcome"] == "D"


def test_structural_gate_requires_every_preregistered_clause():
    assert structural_repair_gate(_repair_cell()) is True
    for key, bad in (
        ("nested_child_stack_events", 0),
        ("commitment_window_preemptions", 1),
        ("reached_horizon_or_safe_terminal", False),
        ("reached_return_or_child_resume", False),
        ("expanded_beyond_guard", False),
    ):
        cell = _repair_cell()
        cell[key] = bad
        assert structural_repair_gate(cell) is False


def test_v0312_lost_set_matches_the_protocol():
    proto = json.load(open(os.path.join(
        "experiments", "validation", "v0.3.13", "protocol.json"), encoding="utf-8"))
    assert proto["v0_3_12_regression_lost"] == V0312_LOST
    assert app_specific_needles() == []


def _leaf():
    return GUIState(app="t", url="/leaf", title="Leaf",
                    elements=(make_seq_el("x", "x"),), obs={})


def _nested():
    return GUIState(
        app="t", url="/nested", title="Nested",
        elements=tuple(make_seq_el(eid, eid) for eid in ("n1", "n2", "n3")),
        obs={})


def _drive_resume():
    graph = StateGraph()
    graph.add_state("P", "/hub", "Hub", cluster_id="hub")
    graph.add_state("N", "/nested", "Nested", cluster_id="nested")
    graph.add_state("L", "/leaf", "Leaf", cluster_id="leaf")
    hub, nested, leaf = make_hub_state(), _nested(), _leaf()
    ctrl = SuspendedParentSequenceController("structural")
    ctrl.after("P", Action("click", "go_a"), hub, nested, "new", [], "N", False, graph, 1)
    ctrl.after("N", Action("click", "n1"), nested, leaf, "new", [], "L", False, graph, 2)
    ctrl.after("L", Action("click", "x"), leaf, leaf, "identical", [], "L", False, graph, 3)
    ctrl.after("L", Action("click", "x"), leaf, leaf, "identical", [], "L", False, graph, 4)
    ctrl.after("L", Action("back"), leaf, hub, "new", [], "N", False, graph, 5)
    return ctrl


def test_stack_audit_accepts_a_real_child_return():
    ctrl = _drive_resume()
    audit = stack_audit(ctrl.events)
    assert audit["terminal_accounting_violations"] == 1 or audit["return_inflation"] is False
    assert audit["stack_frame_corruption"] is False
    assert audit["restore_without_child_return"] is False
    assert audit["return_inflation"] is False
    # The outer instance is still open, so terminal accounting is not closed.
    assert any(item["reason"] == "count" for item in audit["terminal_violations"])
    ctrl.close_open(step=6, sig="N", cluster="nested")
    closed = stack_audit(ctrl.events)
    assert closed["terminal_accounting_violations"] == 0
    assert closed["stack_frame_corruption"] is False
    assert closed["restore_without_child_return"] is False
    assert closed["return_inflation"] is False
