"""P1–P15 suspended-parent stack. Synthetic controller tests only."""
import os
import re

from ghostqa.exploration.nested_stack_guard import (
    LEGAL_TERMINALS, NestedStackReturnGuardGhostPolicy,
    SuspendedParentFrame, SuspendedParentSequenceController,
    terminal_violations,
)
from ghostqa.exploration.policy import GhostPolicy
from ghostqa.exploration.return_cycle_guard import ReturnCycleGuardSequenceController
from ghostqa.exploration.sequence import (
    BRANCH_HORIZON, MutationContext, W_BRANCH_NOVELTY, branch_key,
)
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState
from benchmark.algorithm_freeze import DEFAULT_FREEZE, verify_freeze
from benchmark.return_cycle_guard_reproduce import verify_candidate_identity

try:
    from helpers import make_hub_state, make_seq_el
except ImportError:
    from tests.helpers import make_hub_state, make_seq_el

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SOURCE = os.path.join(ROOT, "ghostqa", "exploration", "nested_stack_guard.py")


def _leaf(url="/leaf", title="Leaf", eid="x"):
    return GUIState(
        app="t", url=url, title=title,
        elements=(make_seq_el(eid, eid),), obs={})


def _hub(url, title, eids):
    return GUIState(
        app="t", url=url, title=title,
        elements=tuple(make_seq_el(eid, eid) for eid in eids), obs={})


def _graph():
    graph = StateGraph()
    graph.add_state("P", "/hub", "Hub", cluster_id="hub")
    graph.add_state("N", "/nested", "Nested", cluster_id="nested")
    graph.add_state("G", "/grand", "Grand", cluster_id="grand")
    graph.add_state("A", "/a", "A", cluster_id="a")
    graph.add_state("L", "/leaf", "Leaf", cluster_id="leaf")
    graph.add_state("Q", "/q", "Q", cluster_id="q")
    return graph


def _states():
    return {
        "hub": make_hub_state(),
        "nested": _hub("/nested", "Nested", ("n1", "n2", "n3")),
        "grand": _hub("/grand", "Grand", ("g1", "g2", "g3")),
        "leaf": _leaf(),
        "a": _leaf("/a", "A", "x"),
        "q": _leaf("/q", "Q", "q"),
    }


class _Finding:
    def fingerprint(self):
        return "fp-stack"


def _ctrl():
    return SuspendedParentSequenceController("structural")


def _go(ctrl, sig, action, state, new_state, new_sig, graph, step, **kw):
    ctrl.after(
        sig, action, state, new_state, kw.get("relation", "new"),
        kw.get("findings", []), new_sig, kw.get("crashed", False), graph, step)


def _world():
    return _graph(), _states()


def _open_outer(ctrl, graph, states, step=1):
    """Hub branch onto the nested hub. Commitment afterwards is 2."""
    _go(ctrl, "P", Action("click", "go_a"), states["hub"], states["nested"],
        "N", graph, step)
    return step


def _nest(ctrl, graph, states, step, dest="L", dest_state="leaf"):
    _go(ctrl, "N", Action("click", "n1"), states["nested"], states[dest_state],
        dest, graph, step)


def _burn_return(ctrl, graph, states, step, parent_sig, land="L"):
    """Spend a fresh child commitment of 2, then step onto parent_sig."""
    leaf = states["leaf"]
    _go(ctrl, land, Action("click", "x"), leaf, leaf, land, graph, step,
        relation="identical")
    _go(ctrl, land, Action("click", "x"), leaf, leaf, land, graph, step + 1,
        relation="identical")
    assert ctrl.ledger.returning is True
    _go(ctrl, land, Action("back"), leaf, states["hub"], parent_sig, graph,
        step + 2)
    return step + 3


def _terminals(ctrl, outcome=None, iid=None):
    rows = []
    for event in ctrl.events:
        if event.get("event") != "sequence_terminal":
            continue
        if outcome is not None and event.get("outcome") != outcome:
            continue
        if iid is not None and event.get("sequence_instance_id") != iid:
            continue
        rows.append(event)
    return rows


def _actions(ctrl, iid):
    return sum(
        1 for event in ctrl.events
        if event.get("event") == "sequence_action"
        and event.get("sequence_instance_id") == iid)


def test_p1_one_level_suspend_starts_a_real_child():
    ctrl = _ctrl()
    graph, states = _world()
    _open_outer(ctrl, graph, states)
    outer_id = ctrl._open_instance["id"]
    outer_branch = ctrl.ledger.active_branch
    _nest(ctrl, graph, states, 2)
    assert _terminals(ctrl, "lost_parent") == []
    assert ctrl.stack_depth == 1
    frame = ctrl._stack[0]
    assert frame.open_instance["id"] == outer_id
    assert frame.active_branch == outer_branch
    starts = [e for e in ctrl.events if e.get("event") == "branch_start"]
    assert len(starts) == 2
    child = starts[-1]
    assert child["sequence_instance_id"] != outer_id
    assert child["sequence_instance_id"] == ctrl._open_instance["id"]
    assert ctrl.ledger.parent_hub_sig == "N"
    assert ctrl.ledger.parent_hub_cluster == "nested"
    assert ctrl.ledger.commitment_left == BRANCH_HORIZON - 1
    assert any(e.get("event") == "parent_frame_suspended" for e in ctrl.events)
    assert any(e.get("event") == "nested_child_started" for e in ctrl.events)
    assert _actions(ctrl, outer_id) == 1
    assert _actions(ctrl, child["sequence_instance_id"]) == 1


def test_p2_outer_commitment_is_not_consumed_by_the_child_click():
    ctrl = _ctrl()
    graph, states = _world()
    _go(ctrl, "P", Action("click", "go_a"), states["hub"], states["a"],
        "A", graph, 1)
    _go(ctrl, "A", Action("click", "x"), states["a"], states["nested"],
        "N", graph, 2)
    assert ctrl.ledger.commitment_left == 1
    assert ctrl.stack_depth == 0
    outer_id = ctrl._open_instance["id"]
    _nest(ctrl, graph, states, 3)
    assert ctrl._stack[0].commitment_left == 1
    assert ctrl.ledger.commitment_left == BRANCH_HORIZON - 1
    assert ctrl.ledger.commitment_left != ctrl._stack[0].commitment_left
    assert _actions(ctrl, outer_id) == 2
    guard = ReturnCycleGuardSequenceController("structural")
    _go(guard, "P", Action("click", "go_a"), states["hub"], states["a"],
        "A", graph, 1)
    _go(guard, "A", Action("click", "x"), states["a"], states["nested"],
        "N", graph, 2)
    _nest(guard, graph, states, 3)
    assert guard.ledger.commitment_left == ctrl.ledger.commitment_left
    assert guard.ledger.parent_hub_sig == "N"
    assert _terminals(guard, "lost_parent")
    assert _terminals(ctrl, "lost_parent") == []


def test_p3_child_return_resumes_the_same_outer_instance():
    ctrl = _ctrl()
    graph, states = _world()
    _open_outer(ctrl, graph, states)
    outer_id = ctrl._open_instance["id"]
    outer_branch = ctrl.ledger.active_branch
    saved_commitment = ctrl.ledger.commitment_left
    _nest(ctrl, graph, states, 2)
    child_id = ctrl._open_instance["id"]
    _burn_return(ctrl, graph, states, 3, "N")
    assert _terminals(ctrl, "returned", child_id)
    assert len(_terminals(ctrl, "returned")) == 1
    assert ctrl.stack_depth == 0
    assert ctrl._open_instance["id"] == outer_id
    assert ctrl.ledger.active_branch == outer_branch
    assert ctrl.ledger.parent_hub_sig == "P"
    assert ctrl.ledger.commitment_left == saved_commitment
    assert ctrl.ledger.returning is False
    assert ctrl.ledger.return_success == 1
    assert _terminals(ctrl, "returned", outer_id) == []
    resumed = [e for e in ctrl.events if e.get("event") == "parent_frame_resumed"]
    assert len(resumed) == 1
    assert resumed[0]["resumed_sequence_instance_id"] == outer_id
    assert resumed[0]["remaining_commitment"] == saved_commitment
    assert resumed[0]["reason"] == "child_returned_to_parent"
    assert resumed[0]["child_parent_matched"] is True
    assert resumed[0]["stack_depth"] == 0


def test_p4_resumed_outer_reaches_its_own_horizon_and_parent():
    ctrl = _ctrl()
    graph, states = _world()
    _open_outer(ctrl, graph, states)
    outer_id = ctrl._open_instance["id"]
    _nest(ctrl, graph, states, 2)
    step = _burn_return(ctrl, graph, states, 3, "N")
    assert ctrl.ledger.parent_hub_sig == "P"
    assert ctrl.ledger.commitment_left == 2
    leaf = states["leaf"]
    _go(ctrl, "N", Action("click", "x"), leaf, leaf, "L", graph, step,
        relation="identical")
    assert ctrl.ledger.commitment_left == 1
    assert ctrl.ledger.returning is False
    _go(ctrl, "L", Action("click", "x"), leaf, leaf, "L", graph, step + 1,
        relation="identical")
    assert ctrl.ledger.returning is True
    assert ctrl.ledger.commitment_left == 0
    assert ctrl.ledger.parent_hub_sig == "P"
    assert len(_terminals(ctrl, "returned")) == 1
    _go(ctrl, "L", Action("back"), leaf, states["hub"], "P", graph, step + 2)
    assert len(_terminals(ctrl, "returned", outer_id)) == 1
    assert ctrl.ledger.return_success == 2
    assert ctrl.stack_depth == 0
    assert ctrl.ledger.active_branch == ""


def test_p5_two_levels_restore_lifo():
    ctrl = _ctrl()
    graph, states = _world()
    _open_outer(ctrl, graph, states)
    outer_id = ctrl._open_instance["id"]
    _nest(ctrl, graph, states, 2, dest="G", dest_state="grand")
    child_id = ctrl._open_instance["id"]
    assert ctrl.ledger.parent_hub_sig == "N"
    _go(ctrl, "G", Action("click", "g1"), states["grand"], states["leaf"],
        "L", graph, 3)
    grand_id = ctrl._open_instance["id"]
    assert ctrl.stack_depth == 2
    assert ctrl.ledger.parent_hub_sig == "G"
    assert [frame.open_instance["id"] for frame in ctrl._stack] == [outer_id, child_id]
    _burn_return(ctrl, graph, states, 4, "G")
    assert ctrl.stack_depth == 1
    assert ctrl._open_instance["id"] == child_id
    assert ctrl.ledger.parent_hub_sig == "N"
    assert ctrl.ledger.commitment_left == 2
    _burn_return(ctrl, graph, states, 7, "N")
    assert ctrl.stack_depth == 0
    assert ctrl._open_instance["id"] == outer_id
    assert ctrl.ledger.parent_hub_sig == "P"
    resumed = [e for e in ctrl.events if e.get("event") == "parent_frame_resumed"]
    assert [e["resumed_sequence_instance_id"] for e in resumed] == [child_id, outer_id]
    assert _terminals(ctrl, "returned", grand_id)
    assert _terminals(ctrl, "returned", child_id)
    assert _terminals(ctrl, "returned", outer_id) == []


def test_p6_finding_does_not_resume_until_parent_match():
    ctrl = _ctrl()
    graph, states = _world()
    _open_outer(ctrl, graph, states)
    outer_id = ctrl._open_instance["id"]
    _nest(ctrl, graph, states, 2)
    child_id = ctrl._open_instance["id"]
    _go(ctrl, "L", Action("click", "x"), states["leaf"], states["leaf"],
        "L", graph, 3, findings=[_Finding()])
    assert len(_terminals(ctrl, "finding", child_id)) == 1
    assert ctrl.stack_depth == 1
    assert ctrl._stack[0].open_instance["id"] == outer_id
    assert [e for e in ctrl.events if e.get("event") == "parent_frame_resumed"] == []
    assert ctrl.ledger.returning is True
    _go(ctrl, "L", Action("back"), states["leaf"], states["nested"], "N", graph, 4)
    assert len(_terminals(ctrl, "finding")) == 1
    assert _terminals(ctrl, "returned", child_id) == []
    assert ctrl.stack_depth == 0
    assert ctrl._open_instance["id"] == outer_id
    assert len([e for e in ctrl.events if e.get("event") == "parent_frame_resumed"]) == 1


def test_p7_finding_then_escape_unwinds_without_a_false_return():
    ctrl = _ctrl()
    graph, states = _world()
    _open_outer(ctrl, graph, states)
    outer_id = ctrl._open_instance["id"]
    _nest(ctrl, graph, states, 2)
    child_id = ctrl._open_instance["id"]
    before_success = ctrl.ledger.return_success
    _go(ctrl, "L", Action("click", "x"), states["leaf"], states["leaf"],
        "L", graph, 3, findings=[_Finding()])
    _go(ctrl, "L", Action("click", "x"), states["leaf"], states["leaf"],
        "L", graph, 4, relation="identical")
    assert ctrl.stack_depth == 0
    assert ctrl.ledger.active_branch == ""
    assert ctrl.ledger.return_success == before_success
    assert len(_terminals(ctrl, "finding", child_id)) == 1
    assert _terminals(ctrl, "returned") == []
    assert _terminals(ctrl, "return_cycle_abandoned", child_id) == []
    assert _terminals(ctrl, "nested_descendant_abandoned", outer_id)
    assert any(e.get("event") == "nested_stack_unwind" for e in ctrl.events)
    assert [e for e in ctrl.events if e.get("event") == "parent_frame_resumed"] == []
    assert terminal_violations(ctrl.events) == []


def test_p8_child_escape_unwinds_the_stack():
    ctrl = _ctrl()
    graph, states = _world()
    _open_outer(ctrl, graph, states)
    outer_id = ctrl._open_instance["id"]
    success_before = ctrl.ledger.return_success
    _nest(ctrl, graph, states, 2)
    child_id = ctrl._open_instance["id"]
    leaf = states["leaf"]
    _go(ctrl, "L", Action("click", "x"), leaf, leaf, "L", graph, 3,
        relation="identical")
    _go(ctrl, "L", Action("click", "x"), leaf, leaf, "L", graph, 4,
        relation="identical")
    assert ctrl.ledger.returning is True
    _go(ctrl, "L", Action("click", "x"), leaf, leaf, "L", graph, 5,
        relation="identical")
    assert ctrl.stack_depth == 0
    assert ctrl.ledger.return_success == success_before
    assert ctrl.ledger.active_branch == ""
    assert _terminals(ctrl, "return_cycle_abandoned", child_id)
    assert _terminals(ctrl, "nested_descendant_abandoned", outer_id)
    assert _terminals(ctrl, "returned") == []
    assert ctrl.metrics()["child_escape_unwind_events"] == 1
    assert ctrl.metrics()["suspended_frames_abandoned"] == 1
    assert ctrl.metrics()["outer_instances_resumed"] == 0
    assert terminal_violations(ctrl.events) == []


def test_p9_crash_terminal_does_not_restore_the_outer():
    ctrl = _ctrl()
    graph, states = _world()
    _open_outer(ctrl, graph, states)
    outer_id = ctrl._open_instance["id"]
    _go(ctrl, "N", Action("click", "n1"), states["nested"], states["leaf"],
        "L", graph, 2, crashed=True)
    assert len(_terminals(ctrl, "crash")) == 1
    assert ctrl.stack_depth == 1
    assert ctrl._stack[0].open_instance["id"] == outer_id
    assert ctrl._open_instance is None
    assert [e for e in ctrl.events if e.get("event") == "parent_frame_resumed"] == []
    assert ctrl.ledger.return_success == 0
    assert _terminals(ctrl, "returned") == []


def test_p10_budget_end_accounts_for_active_and_suspended_instances():
    ctrl = _ctrl()
    graph, states = _world()
    _open_outer(ctrl, graph, states)
    outer_id = ctrl._open_instance["id"]
    _nest(ctrl, graph, states, 2)
    child_id = ctrl._open_instance["id"]
    ctrl.close_open(step=9, sig="L", cluster="leaf")
    assert ctrl.metrics()["active_frame_budget_end_count"] == 1
    assert ctrl.metrics()["suspended_frame_budget_end_count"] == 1
    assert ctrl.metrics()["stack_depth_at_budget_end"] == 1
    assert ctrl.stack_depth == 0
    assert len(_terminals(ctrl, "budget_end", child_id)) == 1
    assert len(_terminals(ctrl, "budget_end", outer_id)) == 1
    assert _terminals(ctrl, "returned") == []
    assert terminal_violations(ctrl.events) == []
    ctrl.close_open(step=10)
    assert len(_terminals(ctrl, "budget_end")) == 2


def test_p11_reset_clears_stack_and_return_history():
    ctrl = _ctrl()
    graph, states = _world()
    _open_outer(ctrl, graph, states)
    _nest(ctrl, graph, states, 2)
    ctrl._seen_failed_return_dests.add("OLD-DEST")
    assert ctrl.stack_depth == 1
    ctrl.reset()
    assert ctrl.stack_depth == 0
    assert ctrl._seen_failed_return_dests == set()
    assert ctrl._max_depth == 0
    assert ctrl._open_instance is None
    assert ctrl.events == []
    assert ctrl.ledger.active_branch == ""
    _open_outer(ctrl, graph, states)
    assert ctrl._open_instance["id"] == "seq-0001"
    assert ctrl.stack_depth == 0
    leaf = states["leaf"]
    _go(ctrl, "N", Action("click", "x"), leaf, leaf, "L", graph, 2,
        relation="identical")
    _go(ctrl, "L", Action("click", "x"), leaf, leaf, "OLD-DEST", graph, 3,
        relation="identical")
    assert ctrl.ledger.returning is True
    assert ctrl.metrics()["return_cycle_escape_events"] == 0
    assert "OLD-DEST" in ctrl._seen_failed_return_dests


def test_p12_child_branch_start_is_a_real_structural_attempt():
    ctrl = _ctrl()
    guard = ReturnCycleGuardSequenceController("structural")
    graph, states = _world()
    _open_outer(ctrl, graph, states)
    _open_outer(guard, graph, states)
    _nest(ctrl, graph, states, 2)
    _nest(guard, graph, states, 2)
    key = branch_key("nested", Action("click", "n1"))
    assert key in ctrl.ledger.hubs["N"].started
    assert ctrl.struct.hub("nested").branches[key].attempts == 1
    assert guard.struct.hub("nested").branches[key].attempts == 1
    ctx = {"sig": "N"}
    tried = ctrl.score_bonus(Action("click", "n1"), states["nested"], graph, ctx)
    fresh = ctrl.score_bonus(Action("click", "n2"), states["nested"], graph, ctx)
    assert fresh - tried == W_BRANCH_NOVELTY
    assert any(
        event.get("event") == "branch_start" and event.get("branch_key") == key
        for event in ctrl.events)


def test_p13_no_suspension_matches_the_return_guard():
    def plain(ctrl, graph, states):
        leaf = states["leaf"]
        _go(ctrl, "P", Action("click", "go_a"), states["hub"], leaf, "L", graph, 1)
        _go(ctrl, "L", Action("click", "x"), leaf, leaf, "L", graph, 2,
            relation="identical")
        _go(ctrl, "L", Action("click", "x"), leaf, leaf, "L", graph, 3,
            relation="identical")
        _go(ctrl, "L", Action("back"), leaf, states["hub"], "P", graph, 4)

    def late(ctrl, graph, states):
        """Return phase, then a hub branch click. Suspension does not apply."""
        leaf = states["leaf"]
        _go(ctrl, "P", Action("click", "go_a"), states["hub"], leaf, "L", graph, 1)
        _go(ctrl, "L", Action("click", "x"), leaf, leaf, "L", graph, 2,
            relation="identical")
        _go(ctrl, "L", Action("click", "x"), leaf, leaf, "L", graph, 3,
            relation="identical")
        assert ctrl.ledger.returning is True
        _go(ctrl, "N", Action("click", "n1"), states["nested"], leaf, "Q", graph, 4)

    for drive in (plain, late):
        guard = ReturnCycleGuardSequenceController("structural")
        stack = _ctrl()
        graph, states = _world()
        drive(guard, graph, states)
        drive(stack, graph, states)
        assert stack.events == guard.events
        assert stack.stack_depth == 0
        assert stack.metrics()["suspended_frame_push_events"] == 0


def test_p14_return_destinations_stay_on_their_own_frame():
    ctrl = _ctrl()
    graph, states = _world()
    _open_outer(ctrl, graph, states)
    ctrl._seen_failed_return_dests.add("OUTER")
    _nest(ctrl, graph, states, 2, dest="G", dest_state="grand")
    assert ctrl._stack[0].seen_failed_return_dests == {"OUTER"}
    assert "OUTER" not in ctrl._seen_failed_return_dests
    ctrl._seen_failed_return_dests.add("CHILD")
    _go(ctrl, "G", Action("click", "g1"), states["grand"], states["leaf"],
        "L", graph, 3)
    assert ctrl._stack[1].seen_failed_return_dests == {"CHILD"}
    assert ctrl._stack[0].seen_failed_return_dests == {"OUTER"}
    assert "CHILD" not in ctrl._seen_failed_return_dests
    leaf = states["leaf"]
    _go(ctrl, "L", Action("click", "x"), leaf, states["q"], "Q", graph, 4)
    _go(ctrl, "Q", Action("click", "q"), states["q"], states["q"], "Q", graph, 5,
        relation="identical")
    assert ctrl.ledger.returning is True
    assert "Q" in ctrl._seen_failed_return_dests
    assert ctrl._stack[1].seen_failed_return_dests == {"CHILD"}
    _go(ctrl, "Q", Action("back"), states["q"], states["grand"], "G", graph, 6)
    assert ctrl._seen_failed_return_dests == {"CHILD"}
    assert "Q" not in ctrl._seen_failed_return_dests
    assert "OUTER" not in ctrl._seen_failed_return_dests
    _burn_return(ctrl, graph, states, 7, "N")
    assert ctrl._seen_failed_return_dests == {"OUTER"}
    assert ctrl.stack_depth == 0


def test_p15_every_started_instance_has_one_legal_terminal():
    scenarios = []
    graph, states = _world()

    returned = _ctrl()
    _open_outer(returned, graph, states)
    _nest(returned, graph, states, 2)
    _burn_return(returned, graph, states, 3, "N")
    returned.close_open(step=20, sig="N", cluster="nested")
    scenarios.append(returned)

    escaped = _ctrl()
    _open_outer(escaped, graph, states)
    _nest(escaped, graph, states, 2)
    leaf = states["leaf"]
    _go(escaped, "L", Action("click", "x"), leaf, leaf, "L", graph, 3,
        relation="identical")
    _go(escaped, "L", Action("click", "x"), leaf, leaf, "L", graph, 4,
        relation="identical")
    _go(escaped, "L", Action("click", "x"), leaf, leaf, "L", graph, 5,
        relation="identical")
    scenarios.append(escaped)

    for ctrl in scenarios:
        assert terminal_violations(ctrl.events) == []
        assert ctrl.metrics()["terminal_accounting_violations"] == 0
        seen = {}
        for event in ctrl.events:
            if event.get("event") != "sequence_terminal":
                continue
            iid = event["sequence_instance_id"]
            seen.setdefault(iid, []).append(event["outcome"])
        assert seen
        for outcomes in seen.values():
            assert len(outcomes) == 1
            assert outcomes[0] in LEGAL_TERMINALS

    duplicate = [{
        "event": "branch_start",
        "sequence_instance_id": "seq-0001",
    }, {
        "event": "sequence_terminal",
        "sequence_instance_id": "seq-0001",
        "outcome": "returned",
    }, {
        "event": "sequence_terminal",
        "sequence_instance_id": "seq-0001",
        "outcome": "returned",
    }]
    assert terminal_violations(duplicate)


def test_mutations_remain_global_and_are_not_rewound():
    assert "mutations" not in SuspendedParentFrame.__dataclass_fields__
    ctrl = _ctrl()
    guard = ReturnCycleGuardSequenceController("structural")
    graph, states = _world()
    for candidate in (ctrl, guard):
        _open_outer(candidate, graph, states)
        candidate.mutations.append(MutationContext(
            step=1, source_sig="P", action_key="click:go_a:",
            new_eids=("follow_me",), branch_id=candidate.ledger.active_branch,
            ttl=10))
    assert ctrl._is_followup(Action("click", "follow_me")) is True
    assert guard._is_followup(Action("click", "follow_me")) is True
    _nest(ctrl, graph, states, 2)
    _nest(guard, graph, states, 2)
    assert ctrl._is_followup(Action("click", "follow_me")) is True
    assert guard._is_followup(Action("click", "follow_me")) is True
    ctrl.mutations.append(MutationContext(
        step=3, source_sig="N", action_key="click:n1:",
        new_eids=("child_only",), branch_id=ctrl.ledger.active_branch, ttl=10))
    _burn_return(ctrl, graph, states, 3, "N")
    kept = set()
    for item in ctrl.mutations:
        kept.update(item.new_eids)
    assert "child_only" in kept


def test_controller_has_no_app_specific_rule_or_hub_monkeypatch():
    text = open(SOURCE, encoding="utf-8").read()
    lowered = text.lower()
    for needle in (
        "customer", "members", "bug-", "buggy-", "crm", "desk", "wiki",
        "shop", "deepbench", "settings.html", "handbook", "ticket",
        "article", "nav_activity",
    ):
        assert needle not in lowered
    assert re.search(r"is_hub\s*=", text) is None
    assert re.search(r"\bsequence_mod\b", text) is None


def test_product_default_and_research_identity_stay_separate():
    from ghostqa.__main__ import _make_policy
    default = _make_policy("ghost", None, 1)
    assert isinstance(default, GhostPolicy)
    assert default.name == "ghost"
    assert default.use_frontier is False
    assert default.sequence_mode == "off"
    stack = _make_policy("ghost-structural-nested-stack-guard", None, 1)
    assert isinstance(stack, NestedStackReturnGuardGhostPolicy)
    assert isinstance(stack.sequence, SuspendedParentSequenceController)
    assert stack.use_frontier is False
    assert stack.sequence_mode == "structural"
    flat = _make_policy("ghost-structural-nested-return-guard", None, 1)
    assert flat.name == "ghost-structural-nested-return-guard"


def test_historical_freezes_remain_intact():
    assert verify_freeze(DEFAULT_FREEZE) == []
    assert verify_candidate_identity() == []
    assert verify_freeze(os.path.join(
        ROOT, "experiments", "frozen", "ghost-nested-hub-guard-v0.3.12",
        "freeze.json")) == []
