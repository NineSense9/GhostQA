"""v0.3.12 nested-hub candidate. N1–N12, differential equivalence, isolation."""
import inspect
import os

from ghostqa.exploration.nested_hub_guard import (
    NestedHubPreservingSequenceController, NestedHubReturnGuardGhostPolicy,
)
from ghostqa.exploration.policy import GhostPolicy
from ghostqa.exploration.return_cycle_guard import (
    ReturnCycleGuardGhostPolicy, ReturnCycleGuardSequenceController,
)
from ghostqa.exploration.sequence import (
    BRANCH_HORIZON, SequenceController, is_branch_click, is_hub,
)
from ghostqa.exploration import sequence as sequence_mod
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState
from benchmark.algorithm_freeze import DEFAULT_FREEZE, verify_freeze
from benchmark.nested_hub_run import make_policy as nested_make_policy
from benchmark.return_cycle_accounting import classify_escape_lifecycle
from benchmark.return_cycle_guard_reproduce import verify_candidate_identity
from benchmark.web_runner import make_policy

try:
    from helpers import make_hub_state, make_seq_el
except ImportError:
    from tests.helpers import make_hub_state, make_seq_el

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _leaf(url="/a", title="A", eid="x"):
    return GUIState(
        app="t", url=url, title=title,
        elements=(make_seq_el(eid, "x"),), obs={})


def _nested_hub():
    return GUIState(
        app="t", url="/nested", title="Nested",
        elements=(
            make_seq_el("n1", "子支1"),
            make_seq_el("n2", "子支2"),
            make_seq_el("n3", "子支3"),
        ), obs={})


def _graph():
    graph = StateGraph()
    graph.add_state("P", "/hub", "Hub", cluster_id="hub")
    graph.add_state("N", "/nested", "Nested", cluster_id="nested")
    graph.add_state("A", "/a", "A", cluster_id="a")
    graph.add_state("B", "/b", "B", cluster_id="b")
    graph.add_state("C", "/c", "C", cluster_id="c")
    graph.add_state("L", "/l", "L", cluster_id="l")
    return graph


def _states():
    return {
        "hub": make_hub_state(),
        "nested": _nested_hub(),
        "A": _leaf("/a", "A"),
        "B": _leaf("/b", "B", "y"),
        "C": _leaf("/c", "C", "z"),
        "L": _leaf("/l", "L", "w"),
    }


class _Finding:
    def fingerprint(self):
        return "fp-nested"


def _terminals(ctrl, outcome=None):
    rows = [
        event for event in ctrl.events
        if event.get("event") == "sequence_terminal"
        and (outcome is None or event.get("outcome") == outcome)
    ]
    return rows


def _followups(ctrl):
    return [event for event in ctrl.events
            if event.get("event") == "nested_branch_followup"]


def _drive(ctrl, script):
    graph = _graph()
    states = _states()
    for step in script:
        sig, action, state_name, new_name, relation, findings, new_sig, crashed = step[:8]
        index = step[8]
        ctrl.after(
            sig, action, states[state_name], states[new_name] if new_name else None,
            relation, findings, new_sig, crashed, graph, index)
    return ctrl


def _start_outer(ctrl):
    """Open one sequence on P and land on the nested hub. Commitment is 2."""
    graph, states = _graph(), _states()
    ctrl.after(
        "P", Action("click", "go_a"), states["hub"], states["nested"],
        "new", [], "N", False, graph, 1)
    return graph, states


def test_fixture_is_a_real_nested_hub_branch_click():
    nested = _nested_hub()
    action = Action("click", "n1")
    assert is_hub(nested) is True
    assert is_branch_click(action, nested) is True
    assert is_hub(make_hub_state()) is True


def test_n1_nested_branch_does_not_kill_outer_instance():
    ctrl = NestedHubPreservingSequenceController("structural")
    graph, states = _start_outer(ctrl)
    outer_id = ctrl._open_instance["id"]
    outer_branch = ctrl.ledger.active_branch
    parent_sig = ctrl.ledger.parent_hub_sig
    parent_cluster = ctrl.ledger.parent_hub_cluster
    ctrl.after(
        "N", Action("click", "n1"), states["nested"], states["L"],
        "new", [], "L", False, graph, 2)
    assert _terminals(ctrl, "lost_parent") == []
    assert ctrl._open_instance is not None
    assert ctrl._open_instance["id"] == outer_id
    assert ctrl.ledger.active_branch == outer_branch
    assert ctrl.ledger.parent_hub_sig == parent_sig
    assert ctrl.ledger.parent_hub_cluster == parent_cluster
    follow = _followups(ctrl)
    assert len(follow) == 1
    event = follow[0]
    assert event["outer_branch"] == outer_branch
    assert event["outer_parent_hub_sig"] == "P"
    assert event["outer_parent_hub_cluster"] == "hub"
    assert event["nested_hub_sig"] == "N"
    assert event["nested_hub_cluster"] == "nested"
    assert event["nested_branch_key"] == "nested:click:n1"
    assert event["commitment_left_before"] == 2
    assert event["sequence_instance_id"] == outer_id
    assert sequence_mod.is_hub(states["nested"]) is True


def test_n2_nested_branch_consumes_commitment():
    ctrl = NestedHubPreservingSequenceController("structural")
    graph, states = _start_outer(ctrl)
    before = ctrl.ledger.commitment_left
    assert before == BRANCH_HORIZON - 1
    ctrl.after(
        "N", Action("click", "n1"), states["nested"], states["L"],
        "new", [], "L", False, graph, 2)
    assert ctrl.ledger.commitment_left == before - 1
    assert ctrl.ledger.commitment_left != BRANCH_HORIZON
    guard = ReturnCycleGuardSequenceController("structural")
    g_graph, g_states = _start_outer(guard)
    guard.after(
        "N", Action("click", "n1"), g_states["nested"], g_states["L"],
        "new", [], "L", False, g_graph, 2)
    assert guard.ledger.commitment_left == BRANCH_HORIZON - 1
    assert ctrl.ledger.commitment_left < guard.ledger.commitment_left


def test_n3_nested_branch_reaches_horizon():
    ctrl = NestedHubPreservingSequenceController("structural")
    graph, states = _start_outer(ctrl)
    ctrl.after(
        "N", Action("click", "n1"), states["nested"], states["nested"],
        "new", [], "N", False, graph, 2)
    assert ctrl.ledger.returning is False
    ctrl.after(
        "N", Action("click", "n2"), states["nested"], states["L"],
        "new", [], "L", False, graph, 3)
    horizons = [
        event for event in ctrl.events
        if event.get("event") == "sequence_horizon_reached"
    ]
    assert len(horizons) == 1
    assert ctrl.ledger.returning is True
    assert ctrl.ledger.commitment_left == 0
    assert ctrl._open_instance is not None
    assert _terminals(ctrl, "lost_parent") == []


def test_n4_return_still_targets_outer_parent():
    ctrl = NestedHubPreservingSequenceController("structural")
    graph, states = _start_outer(ctrl)
    ctrl.after(
        "N", Action("click", "n1"), states["nested"], states["A"],
        "new", [], "A", False, graph, 2)
    ctrl.after(
        "A", Action("click", "x"), states["A"], states["A"],
        "identical", [], "A", False, graph, 3)
    assert ctrl.ledger.returning is True
    assert ctrl.ledger.parent_hub_sig == "P"
    assert ctrl.ledger.parent_hub_cluster == "hub"
    before_success = ctrl.ledger.return_success
    ctrl.after(
        "A", Action("back"), states["A"], states["hub"],
        "new", [], "P", False, graph, 4)
    assert len(_terminals(ctrl, "returned")) == 1
    assert ctrl.ledger.return_success == before_success + 1
    assert ctrl.metrics()["sequence_instances_returned"] == 1
    assert ctrl.metrics()["return_cycle_escape_events"] == 0


def test_n5_return_cycle_guard_still_exact():
    ctrl = NestedHubPreservingSequenceController("structural")
    graph, states = _start_outer(ctrl)
    success = ctrl.ledger.return_success
    completed = ctrl.ledger.completed_total
    ctrl.after(
        "N", Action("click", "n1"), states["nested"], states["A"],
        "new", [], "A", False, graph, 2)
    ctrl.after(
        "A", Action("click", "x"), states["A"], states["A"],
        "identical", [], "A", False, graph, 3)
    ctrl.after(
        "A", Action("click", "x"), states["A"], states["B"],
        "new", [], "B", False, graph, 4)
    ctrl.after(
        "B", Action("click", "y"), states["B"], states["A"],
        "new", [], "A", False, graph, 5)
    escapes = [
        event for event in ctrl.events if event.get("event") == "return_cycle_escape"
    ]
    assert len(escapes) == 1
    assert escapes[0]["repeated_destination_sig"] == "A"
    assert _terminals(ctrl, "returned") == []
    assert ctrl.ledger.return_success == success
    assert ctrl.ledger.completed_total == completed
    assert ctrl.ledger.active_branch == ""
    assert ctrl.metrics()["sequence_instances_returned"] == 0


def test_n6_no_open_instance_matches_historical_branch_start():
    script = [(
        "P", Action("click", "go_a"), "hub", "A", "new", [], "A", False, 1,
    )]
    guard = _drive(ReturnCycleGuardSequenceController("structural"), script)
    cand = _drive(NestedHubPreservingSequenceController("structural"), script)
    assert cand.events == guard.events
    assert _followups(cand) == []
    assert cand.ledger.active_branch == guard.ledger.active_branch
    assert cand.ledger.parent_hub_sig == guard.ledger.parent_hub_sig == "P"
    assert cand.ledger.parent_hub_cluster == guard.ledger.parent_hub_cluster
    assert cand.ledger.commitment_left == guard.ledger.commitment_left
    assert cand.ledger.returning == guard.ledger.returning
    assert cand._open_instance["id"] == guard._open_instance["id"]
    assert cand.metrics()["nested_branch_followup_events"] == 0


def test_n7_outside_window_matches_historical_controller():
    enter = [
        ("P", Action("click", "go_a"), "hub", "A", "new", [], "A", False, 1),
        ("A", Action("click", "x"), "A", "A", "identical", [], "A", False, 2),
        ("A", Action("click", "x"), "A", "A", "identical", [], "A", False, 3),
        ("A", Action("click", "x"), "A", "nested", "new", [], "N", False, 4),
        ("N", Action("click", "n1"), "nested", "L", "new", [], "L", False, 5),
    ]
    guard = _drive(ReturnCycleGuardSequenceController("structural"), enter)
    cand = _drive(NestedHubPreservingSequenceController("structural"), enter)
    assert cand.events == guard.events
    assert _followups(cand) == []
    assert cand.ledger.commitment_left == guard.ledger.commitment_left
    assert cand.ledger.parent_hub_sig == guard.ledger.parent_hub_sig == "N"
    assert cand.ledger.returning == guard.ledger.returning is False

    forced_guard = ReturnCycleGuardSequenceController("structural")
    forced = NestedHubPreservingSequenceController("structural")
    _start_outer(forced_guard)
    _start_outer(forced)
    forced_guard.ledger.commitment_left = 0
    forced.ledger.commitment_left = 0
    forced_guard.ledger.returning = False
    forced.ledger.returning = False
    graph, states = _graph(), _states()
    args = (
        "N", Action("click", "n1"), states["nested"], states["L"],
        "new", [], "L", False, graph, 9,
    )
    forced_guard.after(*args)
    forced.after(*args)
    assert forced.events[-6:] == forced_guard.events[-6:]
    assert _followups(forced) == []
    assert forced.ledger.commitment_left == forced_guard.ledger.commitment_left


def test_n8_finding_during_nested_traversal_is_l2_later():
    ctrl = NestedHubPreservingSequenceController("structural")
    graph, states = _start_outer(ctrl)
    ctrl.after(
        "N", Action("click", "n1"), states["nested"], states["A"],
        "new", [_Finding()], "A", False, graph, 2)
    assert len(_terminals(ctrl, "finding")) == 1
    assert ctrl._open_instance is None
    assert ctrl.ledger.returning is True
    assert ctrl.ledger.parent_hub_sig == "P"
    ctrl.after(
        "A", Action("click", "x"), states["A"], states["B"],
        "new", [], "B", False, graph, 3)
    ctrl.after(
        "B", Action("click", "y"), states["B"], states["A"],
        "new", [], "A", False, graph, 4)
    assert len(_terminals(ctrl)) == 1
    assert _terminals(ctrl, "returned") == []
    life = classify_escape_lifecycle(ctrl.events)
    assert life["escape_count"] == 1
    assert life["L2"] == 1
    assert life["L1"] == 0
    assert life["return_inflation_events"] == []
    assert ctrl.metrics()["return_cycle_escape_events"] == 1


def test_n9_crash_during_nested_traversal_is_one_terminal():
    ctrl = NestedHubPreservingSequenceController("structural")
    graph, states = _start_outer(ctrl)
    ctrl.after(
        "N", Action("click", "n1"), states["nested"], None,
        "new", [], "CRASHED", True, graph, 2)
    crashes = _terminals(ctrl, "crash")
    assert len(crashes) == 1
    assert len(_terminals(ctrl)) == 1
    assert len(_followups(ctrl)) == 1
    assert ctrl._open_instance is None
    assert crashes[0]["sequence_instance_id"] == "seq-0001"


def test_n10_nested_branch_accounting_is_not_a_new_sequence():
    ctrl = NestedHubPreservingSequenceController("structural")
    graph, states = _start_outer(ctrl)
    ctrl.after(
        "N", Action("click", "n1"), states["nested"], states["L"],
        "new", [], "L", False, graph, 2)
    metrics = ctrl.metrics()
    starts = [event for event in ctrl.events if event.get("event") == "branch_start"]
    assert metrics["nested_branch_followup_events"] == 1
    assert metrics["unique_nested_branches_followed"] == 1
    assert metrics["nested_preemption_avoided_events"] == 1
    assert metrics["sequence_instances_started"] == 1
    assert len(starts) == 1
    assert starts[0]["branch_key"] == "hub:click:go_a"
    assert "nested:click:n1" not in {event["branch_key"] for event in starts}
    assert "nested:click:n1" in ctrl.ledger.hubs["N"].discovered
    assert "nested:click:n1" not in ctrl.ledger.hubs["N"].started
    assert ctrl.struct.branch("nested", "nested:click:n1").attempts == 1


def test_n11_repeated_nested_hub_does_not_reset_parent_or_commitment():
    ctrl = NestedHubPreservingSequenceController("structural")
    graph, states = _start_outer(ctrl)
    assert ctrl.ledger.commitment_left == 2
    outer_id = ctrl._open_instance["id"]
    outer_branch = ctrl.ledger.active_branch
    ctrl.after(
        "N", Action("click", "n1"), states["nested"], states["nested"],
        "identical", [], "N", False, graph, 2)
    assert ctrl.ledger.commitment_left == 1
    assert ctrl.ledger.parent_hub_sig == "P"
    assert ctrl.ledger.active_branch == outer_branch
    assert ctrl._open_instance["id"] == outer_id
    ctrl.after(
        "N", Action("click", "n2"), states["nested"], states["L"],
        "new", [], "L", False, graph, 3)
    assert ctrl.ledger.commitment_left == 0
    assert ctrl.ledger.commitment_left != BRANCH_HORIZON
    assert ctrl.ledger.parent_hub_sig == "P"
    assert ctrl.ledger.parent_hub_cluster == "hub"
    assert ctrl.ledger.active_branch == outer_branch
    assert ctrl._open_instance["id"] == outer_id
    assert ctrl.ledger.returning is True
    assert len(_followups(ctrl)) == 2
    assert _terminals(ctrl, "lost_parent") == []
    assert ctrl.metrics()["unique_nested_branches_followed"] == 2


def test_n12_reset_clears_candidate_nested_state():
    ctrl = NestedHubPreservingSequenceController("structural")
    graph, states = _start_outer(ctrl)
    ctrl.after(
        "N", Action("click", "n1"), states["nested"], states["L"],
        "new", [], "L", False, graph, 2)
    assert ctrl._nested_followed
    assert ctrl.metrics()["nested_branch_followup_events"] == 1
    ctrl.reset()
    assert ctrl._nested_followed == set()
    assert ctrl._nested_followup_n == 0
    assert ctrl._seen_failed_return_dests == set()
    assert ctrl.events == []
    assert ctrl._open_instance is None
    assert ctrl.ledger.active_branch == ""
    assert ctrl.metrics()["nested_branch_followup_events"] == 0
    assert ctrl.metrics()["unique_nested_branches_followed"] == 0
    assert ctrl.metrics()["nested_preemption_avoided_events"] == 0
    assert ctrl.metrics()["return_cycle_escape_events"] == 0


def _replay_pair(script):
    guard = _drive(ReturnCycleGuardSequenceController("structural"), script)
    cand = _drive(NestedHubPreservingSequenceController("structural"), script)
    return guard, cand


def _assert_equivalent(guard, cand):
    assert cand.events == guard.events
    assert cand.ledger.active_branch == guard.ledger.active_branch
    assert cand.ledger.parent_hub_sig == guard.ledger.parent_hub_sig
    assert cand.ledger.parent_hub_cluster == guard.ledger.parent_hub_cluster
    assert cand.ledger.commitment_left == guard.ledger.commitment_left
    assert cand.ledger.returning == guard.ledger.returning
    assert cand.ledger.return_success == guard.ledger.return_success
    assert cand.ledger.completed_total == guard.ledger.completed_total
    assert cand.metrics()["return_cycle_escape_events"] == guard.metrics()[
        "return_cycle_escape_events"]
    assert _followups(cand) == []


def test_differential_equivalence_without_nested_preemption():
    leaf_return = [
        ("P", Action("click", "go_a"), "hub", "A", "new", [], "A", False, 1),
        ("A", Action("click", "x"), "A", "A", "identical", [], "A", False, 2),
        ("A", Action("click", "x"), "A", "A", "identical", [], "A", False, 3),
        ("A", Action("click", "backh"), "A", "hub", "new", [], "P", False, 4),
    ]
    cycle = [
        ("P", Action("click", "go_a"), "hub", "A", "new", [], "A", False, 1),
        ("A", Action("click", "x"), "A", "A", "identical", [], "A", False, 2),
        ("A", Action("click", "x"), "A", "A", "identical", [], "A", False, 3),
        ("A", Action("click", "x"), "A", "B", "new", [], "B", False, 4),
        ("B", Action("click", "y"), "B", "A", "new", [], "A", False, 5),
    ]
    finding_cycle = [
        ("P", Action("click", "go_a"), "hub", "A", "new", [], "A", False, 1),
        ("A", Action("click", "x"), "A", "A", "new", [_Finding()], "A", False, 2),
        ("A", Action("click", "x"), "A", "B", "new", [], "B", False, 3),
        ("B", Action("click", "y"), "B", "A", "new", [], "A", False, 4),
    ]
    multistep_return = [
        ("P", Action("click", "go_a"), "hub", "A", "new", [], "A", False, 1),
        ("A", Action("click", "x"), "A", "A", "identical", [], "A", False, 2),
        ("A", Action("click", "x"), "A", "A", "identical", [], "A", False, 3),
        ("A", Action("click", "x"), "A", "C", "new", [], "C", False, 4),
        ("C", Action("click", "z"), "C", "B", "new", [], "B", False, 5),
        ("B", Action("click", "y"), "B", "hub", "new", [], "P", False, 6),
    ]
    for script in (leaf_return, cycle, finding_cycle, multistep_return):
        guard, cand = _replay_pair(script)
        _assert_equivalent(guard, cand)


def test_same_trace_historical_guard_still_loses_parent():
    script = [
        ("P", Action("click", "go_a"), "hub", "nested", "new", [], "N", False, 1),
        ("N", Action("click", "n1"), "nested", "L", "new", [], "L", False, 2),
    ]
    guard, cand = _replay_pair(script)
    assert len(_terminals(guard, "lost_parent")) == 1
    assert _terminals(cand, "lost_parent") == []
    assert guard.ledger.parent_hub_sig == "N"
    assert cand.ledger.parent_hub_sig == "P"
    assert guard.ledger.active_branch != cand.ledger.active_branch


def test_select_matches_guard_before_any_nested_click():
    graph = _graph()
    hub = make_hub_state()
    actions = [Action("click", "go_a"), Action("click", "go_b"), Action("back")]
    guard = ReturnCycleGuardGhostPolicy(llm=None)
    cand = NestedHubReturnGuardGhostPolicy(llm=None)
    ctx = {"sig": "P", "step_index": 0, "budget": 20, "candidate_actions": actions,
           "state_brief": "", "spec_brief": ""}
    assert guard.select(graph, hub, actions, dict(ctx)).key() == cand.select(
        graph, hub, actions, dict(ctx)).key()
    g_bonus = {
        action.key(): guard.sequence.score_bonus(action, hub, graph, dict(ctx))
        for action in actions
    }
    c_bonus = {
        action.key(): cand.sequence.score_bonus(action, hub, graph, dict(ctx))
        for action in actions
    }
    assert g_bonus == c_bonus


def test_s1_s7_expectations_hold_on_candidate_scripts():
    direct = [
        ("P", Action("click", "go_a"), "hub", "A", "new", [], "A", False, 1),
        ("A", Action("click", "x"), "A", "A", "identical", [], "A", False, 2),
        ("A", Action("click", "x"), "A", "A", "identical", [], "A", False, 3),
        ("A", Action("click", "backh"), "A", "hub", "new", [], "P", False, 4),
    ]
    self_loop = [
        ("P", Action("click", "go_a"), "hub", "A", "new", [], "A", False, 1),
        ("A", Action("click", "x"), "A", "A", "identical", [], "A", False, 2),
        ("A", Action("click", "x"), "A", "A", "identical", [], "A", False, 3),
        ("A", Action("click", "x"), "A", "A", "identical", [], "A", False, 4),
    ]
    aba = [
        ("P", Action("click", "go_a"), "hub", "A", "new", [], "A", False, 1),
        ("A", Action("click", "x"), "A", "A", "identical", [], "A", False, 2),
        ("A", Action("click", "x"), "A", "A", "identical", [], "A", False, 3),
        ("A", Action("click", "x"), "A", "B", "new", [], "B", False, 4),
        ("B", Action("click", "y"), "B", "A", "new", [], "A", False, 5),
    ]
    cand = _drive(NestedHubPreservingSequenceController("structural"), direct)
    assert cand.metrics()["return_cycle_escape_events"] == 0
    assert len(_terminals(cand, "returned")) == 1
    cand = _drive(NestedHubPreservingSequenceController("structural"), self_loop)
    assert cand.metrics()["return_cycle_escape_events"] == 1
    assert _terminals(cand, "returned") == []
    cand = _drive(NestedHubPreservingSequenceController("structural"), aba)
    assert cand.metrics()["return_cycle_escape_events"] == 1
    assert _terminals(cand, "returned") == []


def test_exhaustive_model_check_still_passes_for_guard_and_candidate():
    import benchmark.return_cycle_modelcheck as modelcheck
    guard = modelcheck.run_exhaustive_check()
    assert guard["traces_enumerated"] >= 5800
    assert guard["failures"] == 0
    assert guard["s1_s7_all_pass"] is True
    original = modelcheck.ReturnCycleGuardSequenceController
    modelcheck.ReturnCycleGuardSequenceController = NestedHubPreservingSequenceController
    try:
        cand = modelcheck.run_exhaustive_check()
    finally:
        modelcheck.ReturnCycleGuardSequenceController = original
    assert cand["traces_enumerated"] >= 5800
    assert cand["traces_enumerated"] >= guard["traces_enumerated"]
    assert cand["failures"] == 0
    assert cand["all_pass"] is True
    assert sequence_mod.is_hub(make_hub_state()) is True


def test_product_default_and_frozen_sources_unchanged():
    product = GhostPolicy()
    assert product.name == "ghost"
    assert product.use_frontier is False
    assert product.sequence_mode == "off"
    assert product.sequence is None
    assert verify_freeze(DEFAULT_FREEZE) == []
    assert verify_candidate_identity() == []
    # v0.3.9 reproduce skips web_runner.py (additive app registry). This round
    # still must not edit it: the worktree blob matches HEAD.
    import subprocess
    blob = subprocess.check_output(
        ["git", "hash-object", os.path.join(ROOT, "benchmark", "web_runner.py")],
        text=True).strip()
    head_blob = subprocess.check_output(
        ["git", "rev-parse", "HEAD:benchmark/web_runner.py"],
        text=True).strip()
    assert blob == head_blob
    c1 = make_policy("ghost-structural-memory", 1)
    guard = make_policy("ghost-structural-return-guard", 1)
    assert type(c1.sequence) is SequenceController
    assert type(guard.sequence) is ReturnCycleGuardSequenceController
    try:
        make_policy("ghost-structural-nested-return-guard", 1)
        raised = False
    except ValueError:
        raised = True
    assert raised
    cand = nested_make_policy("ghost-structural-nested-return-guard", 1)
    assert isinstance(cand, NestedHubReturnGuardGhostPolicy)
    assert cand.name == "ghost-structural-nested-return-guard"
    assert cand.use_frontier is False
    assert isinstance(cand.sequence, NestedHubPreservingSequenceController)
    plain = nested_make_policy("ghost-structural-memory", 1)
    assert type(plain.sequence) is SequenceController


def test_candidate_source_reads_no_manifest_or_app_rules():
    path = os.path.join(ROOT, "ghostqa", "exploration", "nested_hub_guard.py")
    src = open(path, encoding="utf-8").read()
    for needle in (
        "bugs.manifest", "topology.manifest", "topology.json",
        "buggy-crm", "buggy-ops", "buggy-wiki", "buggy-desk", "buggy-shop",
        "buggy-flow", "BUG-", "BuggyShop", "BuggyDesk", "DeepBench",
        "cart.html", "RETURN_CYCLE_LIMIT", "accounts.html",
    ):
        assert needle not in src, needle
    assert "lost_parent" in src
    assert "nested_branch_followup" in src
    body = inspect.getsource(NestedHubPreservingSequenceController.after)
    assert "super().after" in body
