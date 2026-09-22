"""H1–H20 horizon handoff. Synthetic controller tests only."""
import os

from ghostqa.exploration.horizon_handoff_guard import (
    LEGAL_TERMINALS, HorizonHandoffReturnGuardGhostPolicy,
    HorizonHandoffSequenceController, terminal_violations,
)
from ghostqa.exploration.policy import GhostPolicy
from ghostqa.exploration.return_cycle_guard import ReturnCycleGuardSequenceController
from ghostqa.exploration.sequence import BRANCH_HORIZON, branch_key
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState
from benchmark.algorithm_freeze import verify_freeze
from benchmark.nested_stack_analysis import APP_NEEDLES, app_specific_needles
from benchmark.return_cycle_guard_reproduce import verify_candidate_identity

try:
    from helpers import make_hub_state, make_seq_el
except ImportError:
    from tests.helpers import make_hub_state, make_seq_el

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SOURCE = os.path.join(ROOT, "ghostqa", "exploration", "horizon_handoff_guard.py")


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
    graph.add_state("N2", "/nested-v", "NestedV", cluster_id="nested")
    graph.add_state("G", "/grand", "Grand", cluster_id="grand")
    graph.add_state("G2", "/grand2", "Grand2", cluster_id="grand2")
    graph.add_state("L", "/leaf", "Leaf", cluster_id="leaf")
    graph.add_state("Q", "/q", "Q", cluster_id="q")
    for sig, cluster in (
        ("A", "a"), ("B", "b"), ("C", "c"), ("D", "d"), ("E", "e"), ("F", "f"),
    ):
        graph.add_state(sig, "/" + sig.lower(), sig, cluster_id=cluster)
    return graph


def _states():
    chain = {
        sig: _hub("/" + sig.lower(), sig, ("b1", "b2", "b3"))
        for sig in ("A", "B", "C", "D", "E", "F")
    }
    chain.update({
        "hub": make_hub_state(),
        "nested": _hub("/nested", "Nested", ("n1", "n2", "n3")),
        "grand": _hub("/grand", "Grand", ("g1", "g2", "g3")),
        "grand2": _hub("/grand2", "Grand2", ("h1", "h2", "h3")),
        "leaf": _leaf(),
        "q": _leaf("/q", "Q", "q"),
    })
    return chain


class _Finding:
    def fingerprint(self):
        return "fp-handoff"


def _ctrl():
    return HorizonHandoffSequenceController("structural")


def _go(ctrl, sig, action, state, new_state, new_sig, graph, step, **kw):
    ctrl.after(
        sig, action, state, new_state, kw.get("relation", "new"),
        kw.get("findings", []), new_sig, kw.get("crashed", False), graph, step)


def _world():
    return _graph(), _states()


def _open_on_nested(ctrl, graph, states, step=1):
    """Branch from the outer hub onto the nested hub. Commitment is 2."""
    _go(ctrl, "P", Action("click", "go_a"), states["hub"], states["nested"],
        "N", graph, step)
    return step + 1


def _burn_to_final_slot(ctrl, graph, states, step):
    """Non-branch action on the nested hub. Commitment 2 becomes 1."""
    _go(ctrl, "N", Action("fill", "x"), states["nested"], states["nested"],
        "N", graph, step, relation="identical")
    return step + 1


def _handoff_to_leaf(ctrl, graph, states, step):
    _go(ctrl, "N", Action("click", "n1"), states["nested"], states["leaf"],
        "L", graph, step)
    return step + 1


def _events(ctrl, name):
    return [event for event in ctrl.events if event.get("event") == name]


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


def test_h1_nested_continuation_at_commitment_2():
    ctrl = _ctrl()
    graph, states = _world()
    _open_on_nested(ctrl, graph, states)
    outer_id = ctrl._open_instance["id"]
    parent = ctrl.ledger.parent_hub_sig
    parent_cluster = ctrl.ledger.parent_hub_cluster
    assert ctrl.ledger.commitment_left == 2
    _go(ctrl, "N", Action("click", "n1"), states["nested"], states["leaf"],
        "L", graph, 2)
    assert ctrl._open_instance["id"] == outer_id
    assert ctrl.stack_depth == 0
    assert _events(ctrl, "nested_continuation")
    assert _events(ctrl, "horizon_handoff_started") == []
    assert ctrl.ledger.parent_hub_sig == parent
    assert ctrl.ledger.parent_hub_cluster == parent_cluster
    assert ctrl.ledger.commitment_left == 1
    event = _events(ctrl, "nested_continuation")[-1]
    assert event["commitment_before"] == 2
    assert event["commitment_after"] == 1
    assert event["outer_sequence_instance_id"] == outer_id
    assert event["nested_hub_sig"] == "N"


def test_h2_continuation_structural_accounting_starts_no_instance():
    ctrl = _ctrl()
    graph, states = _world()
    _open_on_nested(ctrl, graph, states)
    before_started = ctrl.ledger.sequences_started
    before_ids = [
        event.get("sequence_instance_id")
        for event in _events(ctrl, "branch_start")
    ]
    _go(ctrl, "N", Action("click", "n1"), states["nested"], states["leaf"],
        "L", graph, 2)
    key = branch_key("nested", Action("click", "n1"))
    assert key in ctrl.ledger.hub("N", "nested").discovered
    assert ctrl.struct.branch("nested", key).attempts >= 1
    assert _events(ctrl, "nested_continuation")
    assert ctrl.ledger.sequences_started == before_started
    assert [event.get("sequence_instance_id") for event in _events(ctrl, "branch_start")] == before_ids
    assert key not in ctrl.ledger.hub("N", "nested").started
    assert _terminals(ctrl, "returned") == []


def test_h3_final_slot_handoff_consumes_outer_and_starts_child():
    ctrl = _ctrl()
    graph, states = _world()
    step = _burn_to_final_slot(ctrl, graph, states, _open_on_nested(ctrl, graph, states))
    assert ctrl.ledger.commitment_left == 1
    outer_id = ctrl._open_instance["id"]
    pre_actions = ctrl.ledger.branch_actions
    pre_len = ctrl.ledger._seq_len
    pre_findings = ctrl.ledger.branch_findings
    _handoff_to_leaf(ctrl, graph, states, step)
    assert ctrl.stack_depth == 1
    frame = ctrl._stack[0]
    assert frame.commitment_left == 0
    assert frame.returning is True
    assert frame.deferred_horizon is True
    assert frame.branch_actions == pre_actions + 1
    assert frame.seq_len == pre_len + 1
    assert frame.branch_findings == pre_findings
    assert frame.open_instance["id"] == outer_id
    assert frame.child_parent_sig == "N"
    assert frame.child_parent_cluster == "nested"
    assert frame.child_instance_id != outer_id
    assert ctrl.ledger.commitment_left == BRANCH_HORIZON - 1
    assert ctrl.ledger.parent_hub_sig == "N"
    assert ctrl._open_instance["id"] == frame.child_instance_id
    handoff = _events(ctrl, "horizon_handoff_started")[-1]
    assert handoff["outer_commitment_before"] == 1
    assert handoff["stored_commitment"] == 0
    assert handoff["child_commitment_assigned"] == BRANCH_HORIZON
    assert handoff["child_sequence_instance_id"] == frame.child_instance_id
    assert handoff["stack_depth"] == 1
    assert _terminals(ctrl, "lost_parent") == []
    step_actions = [
        event for event in _events(ctrl, "sequence_action")
        if event.get("step") == step
    ]
    assert len(step_actions) == 1
    assert step_actions[0]["sequence_instance_id"] == frame.child_instance_id
    assert len([event for event in _events(ctrl, "mutation") if event.get("step") == step]) == 1
    assert ctrl.ledger.branch_actions == 1
    assert _events(ctrl, "sequence_horizon_reached") == []


def test_h4_child_commitment_is_independent_of_stored_outer():
    ctrl = _ctrl()
    graph, states = _world()
    step = _handoff_to_leaf(
        ctrl, graph, states,
        _burn_to_final_slot(ctrl, graph, states, _open_on_nested(ctrl, graph, states)))
    frame = ctrl._stack[0]
    assert ctrl.ledger.commitment_left == BRANCH_HORIZON - 1
    assert frame.commitment_left == 0
    _go(ctrl, "L", Action("click", "x"), states["leaf"], states["leaf"],
        "L", graph, step, relation="identical")
    assert ctrl.ledger.commitment_left == BRANCH_HORIZON - 2
    assert frame.commitment_left == 0
    assert frame.deferred_horizon is True
    assert ctrl.stack_depth == 1


def _return_child_exact(ctrl, graph, states, step, dest="N", dest_state="nested"):
    leaf = states["leaf"]
    _go(ctrl, "L", Action("click", "x"), leaf, leaf, "L", graph, step,
        relation="identical")
    _go(ctrl, "L", Action("click", "x"), leaf, leaf, "L", graph, step + 1,
        relation="identical")
    assert ctrl.ledger.returning is True
    _go(ctrl, "L", Action("back"), leaf, states[dest_state], dest, graph, step + 2)
    return step + 3


def test_h5_exact_child_parent_witness_restores_outer_return_phase():
    ctrl = _ctrl()
    graph, states = _world()
    step = _handoff_to_leaf(
        ctrl, graph, states,
        _burn_to_final_slot(ctrl, graph, states, _open_on_nested(ctrl, graph, states)))
    outer_id = ctrl._stack[0].open_instance["id"]
    child_id = ctrl._stack[0].child_instance_id
    before_success = ctrl.ledger.return_success
    _return_child_exact(ctrl, graph, states, step)
    assert ctrl.ledger.return_success == before_success + 1
    assert ctrl.stack_depth == 0
    witness = _events(ctrl, "child_parent_witness")
    assert len(witness) == 1
    assert witness[0]["witness_strength"] == "exact"
    assert witness[0]["terminal_context"] == "returned"
    assert witness[0]["child_sequence_instance_id"] == child_id
    assert witness[0]["return_success_delta"] == 1
    resumed = _events(ctrl, "parent_frame_resume_to_return")
    assert len(resumed) == 1
    assert resumed[0]["resumed_sequence_instance_id"] == outer_id
    assert resumed[0]["returning"] is True
    assert resumed[0]["commitment_left"] == 0
    assert resumed[0]["stack_depth"] == 0
    horizons = [
        event for event in _events(ctrl, "sequence_horizon_reached")
        if event.get("reason") == "horizon_handoff_resolved"
    ]
    assert len(horizons) == 1
    assert horizons[0]["sequence_instance_id"] == outer_id
    assert ctrl.ledger.returning is True
    assert ctrl.ledger.commitment_left == 0
    assert _terminals(ctrl, "returned", child_id)
    assert _terminals(ctrl, "returned", outer_id) == []


def test_h6_cluster_variant_witness():
    ctrl = _ctrl()
    graph, states = _world()
    step = _handoff_to_leaf(
        ctrl, graph, states,
        _burn_to_final_slot(ctrl, graph, states, _open_on_nested(ctrl, graph, states)))
    leaf = states["leaf"]
    _go(ctrl, "L", Action("click", "x"), leaf, leaf, "L", graph, step,
        relation="identical")
    _go(ctrl, "L", Action("click", "x"), leaf, leaf, "L", graph, step + 1,
        relation="identical")
    _go(ctrl, "L", Action("back"), leaf, states["nested"], "N2", graph, step + 2)
    witness = _events(ctrl, "child_parent_witness")[-1]
    assert witness["witness_strength"] == "cluster"
    assert witness["observed_destination_sig"] == "N2"
    assert witness["expected_parent_sig"] == "N"
    assert ctrl.stack_depth == 0
    assert ctrl.ledger.returning is True


def test_h7_same_step_finding_and_cluster_witness_does_not_fake_returned():
    ctrl = _ctrl()
    graph, states = _world()
    step = _handoff_to_leaf(
        ctrl, graph, states,
        _burn_to_final_slot(ctrl, graph, states, _open_on_nested(ctrl, graph, states)))
    child_id = ctrl._open_instance["id"]
    _go(ctrl, "L", Action("click", "x"), states["leaf"], states["nested"],
        "N2", graph, step, findings=[_Finding()])
    witness = _events(ctrl, "child_parent_witness")[-1]
    assert witness["witness_strength"] == "cluster"
    assert witness["terminal_context"] == "finding_same_step"
    assert ctrl.stack_depth == 0
    assert ctrl.ledger.returning is True
    assert len(_terminals(ctrl, "finding", child_id)) == 1
    assert _terminals(ctrl, "returned", child_id) == []


def test_h8_same_step_crash_and_parent_witness():
    ctrl = _ctrl()
    graph, states = _world()
    step = _handoff_to_leaf(
        ctrl, graph, states,
        _burn_to_final_slot(ctrl, graph, states, _open_on_nested(ctrl, graph, states)))
    child_id = ctrl._open_instance["id"]
    _go(ctrl, "L", Action("click", "x"), states["leaf"], states["nested"],
        "N", graph, step, crashed=True)
    witness = _events(ctrl, "child_parent_witness")[-1]
    assert witness["witness_strength"] == "exact"
    assert witness["terminal_context"] == "crash_same_step"
    assert ctrl.ledger.returning is True
    assert ctrl.stack_depth == 0
    assert len(_terminals(ctrl, "crash", child_id)) == 1
    assert _terminals(ctrl, "returned", child_id) == []


def test_h9_finding_without_parent_witness_stays_suspended():
    ctrl = _ctrl()
    graph, states = _world()
    step = _handoff_to_leaf(
        ctrl, graph, states,
        _burn_to_final_slot(ctrl, graph, states, _open_on_nested(ctrl, graph, states)))
    _go(ctrl, "L", Action("click", "x"), states["leaf"], states["q"],
        "Q", graph, step, findings=[_Finding()])
    assert ctrl.stack_depth == 1
    assert _events(ctrl, "child_parent_witness") == []
    assert _events(ctrl, "parent_frame_resume_to_return") == []
    assert ctrl.ledger.returning is True
    assert ctrl.ledger.return_success == 0
    _go(ctrl, "Q", Action("back"), states["q"], states["nested"], "N", graph, step + 1)
    witness = _events(ctrl, "child_parent_witness")[-1]
    assert witness["terminal_context"] == "finding_prior"
    assert ctrl.stack_depth == 0
    assert ctrl.ledger.returning is True
    assert _terminals(ctrl, "returned") == []


def test_h10_wrong_parent_does_not_pop():
    ctrl = _ctrl()
    graph, states = _world()
    _handoff_to_leaf(
        ctrl, graph, states,
        _burn_to_final_slot(ctrl, graph, states, _open_on_nested(ctrl, graph, states)))
    before = ctrl._markers()
    ctrl.ledger.return_success += 1
    ctrl.ledger.active_branch = ""
    ctrl.ledger.returning = False
    ctrl._open_instance = None
    ctrl._resolve_stack(before, "L", "WRONG", graph, 9)
    assert ctrl.stack_depth == 1
    assert _events(ctrl, "child_parent_witness") == []
    assert _events(ctrl, "witness_rejection")[-1]["reason"] == "wrong_parent"


def test_h11_wrong_child_identity_does_not_pop():
    ctrl = _ctrl()
    graph, states = _world()
    step = _handoff_to_leaf(
        ctrl, graph, states,
        _burn_to_final_slot(ctrl, graph, states, _open_on_nested(ctrl, graph, states)))
    frame = ctrl._stack[0]
    frame.child_instance_id = "seq-other"
    frame.child_branch = "other:click:nope"
    _return_child_exact(ctrl, graph, states, step)
    assert ctrl.stack_depth == 1
    assert _events(ctrl, "child_parent_witness") == []
    assert _events(ctrl, "witness_rejection")[-1]["reason"] == "wrong_child"


def test_h12_global_return_success_delta_alone_does_not_pop():
    ctrl = _ctrl()
    graph, states = _world()
    _handoff_to_leaf(
        ctrl, graph, states,
        _burn_to_final_slot(ctrl, graph, states, _open_on_nested(ctrl, graph, states)))
    frame = ctrl._stack[0]
    before = ctrl._markers()
    before["open_id"] = "seq-unrelated"
    before["active_branch"] = "unrelated:click:nope"
    ctrl.ledger.return_success += 1
    ctrl.ledger.active_branch = ""
    ctrl.ledger.returning = False
    ctrl._open_instance = None
    ctrl._resolve_stack(before, "L", frame.child_parent_sig, graph, 9)
    assert ctrl.stack_depth == 1
    assert _events(ctrl, "child_parent_witness") == []
    assert _events(ctrl, "parent_frame_resume_to_return") == []
    assert _events(ctrl, "witness_rejection")[-1]["reason"] == "wrong_child"


def test_h13_child_escape_unwinds_without_return_inflation():
    ctrl = _ctrl()
    graph, states = _world()
    step = _handoff_to_leaf(
        ctrl, graph, states,
        _burn_to_final_slot(ctrl, graph, states, _open_on_nested(ctrl, graph, states)))
    outer_id = ctrl._stack[0].open_instance["id"]
    child_id = ctrl._stack[0].child_instance_id
    leaf = states["leaf"]
    _go(ctrl, "L", Action("click", "x"), leaf, leaf, "L", graph, step,
        relation="identical")
    _go(ctrl, "L", Action("click", "x"), leaf, leaf, "L", graph, step + 1,
        relation="identical")
    assert ctrl.ledger.returning is True
    _go(ctrl, "L", Action("click", "x"), leaf, states["q"], "Q", graph, step + 2)
    _go(ctrl, "Q", Action("click", "q"), states["q"], states["q"], "Q", graph, step + 3,
        relation="identical")
    assert ctrl.stack_depth == 0
    assert _events(ctrl, "child_parent_witness") == []
    assert _events(ctrl, "parent_frame_resume_to_return") == []
    assert _events(ctrl, "horizon_handoff_unwind")
    assert _terminals(ctrl, "return_cycle_abandoned", child_id)
    assert _terminals(ctrl, "horizon_handoff_abandoned", outer_id)
    assert _terminals(ctrl, "returned") == []
    assert ctrl.ledger.return_success == 0
    assert ctrl.ledger.sequences_completed == 0
    assert ctrl.metrics()["witness_violations"] == 0
    assert terminal_violations(ctrl.events) == []


def test_h14_recursive_handoff_restores_lifo():
    ctrl = _ctrl()
    graph, states = _world()
    step = _burn_to_final_slot(ctrl, graph, states, _open_on_nested(ctrl, graph, states))
    _go(ctrl, "N", Action("click", "n1"), states["nested"], states["grand"],
        "G", graph, step)
    outer_id = ctrl._stack[0].open_instance["id"]
    child_id = ctrl._open_instance["id"]
    assert ctrl.ledger.commitment_left == 2
    _go(ctrl, "G", Action("click", "g1"), states["grand"], states["grand2"],
        "G2", graph, step + 1)
    assert ctrl._open_instance["id"] == child_id
    assert ctrl.stack_depth == 1
    assert ctrl.ledger.commitment_left == 1
    assert _events(ctrl, "nested_continuation")
    _go(ctrl, "G2", Action("click", "h1"), states["grand2"], states["leaf"],
        "L", graph, step + 2)
    assert ctrl.stack_depth == 2
    grandchild = ctrl._open_instance["id"]
    assert grandchild not in (outer_id, child_id)
    _return_child_exact(ctrl, graph, states, step + 3, dest="G2", dest_state="grand2")
    assert ctrl.stack_depth == 1
    assert ctrl.ledger.returning is True
    assert ctrl.ledger.commitment_left == 0
    assert ctrl.ledger.parent_hub_sig == "N"
    assert ctrl._open_instance["id"] == child_id
    _go(ctrl, "G2", Action("back"), states["grand2"], states["nested"],
        "N", graph, step + 6)
    assert ctrl.stack_depth == 0
    assert ctrl.ledger.returning is True
    assert ctrl.ledger.parent_hub_sig == "P"
    assert ctrl._open_instance["id"] == outer_id
    resumes = _events(ctrl, "parent_frame_resume_to_return")
    assert [event["resumed_sequence_instance_id"] for event in resumes] == [
        child_id, outer_id]
    assert len(_events(ctrl, "child_parent_witness")) == 2
    assert ctrl.ledger.parent_hub_sig == "P"
    assert _terminals(ctrl, "returned", outer_id) == []


def test_h15_resumed_outer_targets_its_original_parent():
    ctrl = _ctrl()
    graph, states = _world()
    step = _return_child_exact(
        ctrl, graph, states,
        _handoff_to_leaf(
            ctrl, graph, states,
            _burn_to_final_slot(
                ctrl, graph, states, _open_on_nested(ctrl, graph, states))))
    assert ctrl.ledger.parent_hub_sig == "P"
    assert ctrl.ledger.parent_hub_cluster == "hub"
    assert ctrl.ledger.parent_hub_sig != "N"
    success = ctrl.ledger.return_success
    _go(ctrl, "N", Action("back"), states["nested"], states["hub"], "P", graph, step)
    assert ctrl.ledger.return_success == success + 1
    assert ctrl.ledger.active_branch == ""
    assert _terminals(ctrl, "returned")
    assert terminal_violations(ctrl.events) == []


def test_h16_hub_chain_hands_off_only_on_the_final_slot():
    ctrl = _ctrl()
    graph, states = _world()
    order = [("A", "B"), ("B", "C"), ("C", "D"), ("D", "E"), ("E", "F")]
    depths = []
    for index, (src, dst) in enumerate(order, start=1):
        _go(ctrl, src, Action("click", "b1"), states[src], states[dst],
            dst, graph, index)
        depths.append(ctrl.stack_depth)
    assert depths == [0, 0, 1, 1, 2]
    assert len(_events(ctrl, "nested_continuation")) == 2
    assert len(_events(ctrl, "horizon_handoff_started")) == 2
    assert ctrl.metrics()["max_handoff_stack_depth"] == 2
    leaf = states["leaf"]
    _go(ctrl, "F", Action("fill", "x"), states["F"], leaf, "L", graph, 6,
        relation="identical")
    _go(ctrl, "L", Action("click", "x"), leaf, leaf, "L", graph, 7,
        relation="identical")
    assert ctrl.ledger.returning is True
    _go(ctrl, "L", Action("back"), leaf, states["E"], "E", graph, 8)
    assert _events(ctrl, "child_parent_witness")
    assert _events(ctrl, "sequence_horizon_reached")
    assert any(
        event.get("reason") == "horizon_handoff_resolved"
        for event in _events(ctrl, "sequence_horizon_reached"))
    assert ctrl.ledger.returning is True
    assert ctrl.stack_depth == 1


def test_h17_budget_end_accounts_for_every_open_instance_once():
    ctrl = _ctrl()
    graph, states = _world()
    _handoff_to_leaf(
        ctrl, graph, states,
        _burn_to_final_slot(ctrl, graph, states, _open_on_nested(ctrl, graph, states)))
    assert ctrl.stack_depth == 1
    child_id = ctrl._open_instance["id"]
    outer_id = ctrl._stack[0].open_instance["id"]
    ctrl.close_open(step=20, sig="L", cluster="leaf")
    assert ctrl.metrics()["handoff_stack_depth_at_budget_end"] == 1
    assert ctrl.metrics()["active_budget_end_count"] == 1
    assert ctrl.metrics()["suspended_budget_end_count"] == 1
    assert len(_terminals(ctrl, "budget_end", child_id)) == 1
    assert len(_terminals(ctrl, "budget_end", outer_id)) == 1
    assert _terminals(ctrl, "returned") == []
    assert terminal_violations(ctrl.events) == []
    ctrl.close_open(step=21, sig="L", cluster="leaf")
    assert len(_terminals(ctrl, "budget_end")) == 2


def test_h18_reset_clears_frames_and_witness_state():
    ctrl = _ctrl()
    graph, states = _world()
    _handoff_to_leaf(
        ctrl, graph, states,
        _burn_to_final_slot(ctrl, graph, states, _open_on_nested(ctrl, graph, states)))
    ctrl.ledger.return_success = 4
    ctrl.reset()
    assert ctrl.stack_depth == 0
    assert ctrl.events == []
    assert ctrl.ledger.return_success == 0
    assert ctrl.ledger.active_branch == ""
    assert ctrl._seen_failed_return_dests == set()
    assert ctrl._open_instance is None
    metrics = ctrl.metrics()
    assert metrics["horizon_handoff_started_events"] == 0
    assert metrics["nested_continuation_events"] == 0
    assert metrics["max_handoff_stack_depth"] == 0
    assert metrics["witness_violations"] == 0
    _open_on_nested(ctrl, graph, states)
    assert ctrl.stack_depth == 0
    assert ctrl.ledger.commitment_left == 2


def _play_non_nested(ctrl, graph, states):
    hub = states["hub"]
    leaf = states["leaf"]
    _go(ctrl, "P", Action("click", "go_a"), hub, leaf, "L", graph, 1)
    _go(ctrl, "L", Action("click", "x"), leaf, leaf, "L", graph, 2,
        relation="identical")
    _go(ctrl, "L", Action("click", "x"), leaf, leaf, "L", graph, 3,
        relation="identical")
    _go(ctrl, "L", Action("back"), leaf, hub, "P", graph, 4)
    _go(ctrl, "P", Action("click", "go_a"), hub, leaf, "L", graph, 5)
    _go(ctrl, "L", Action("click", "x"), leaf, leaf, "L", graph, 6,
        relation="identical")
    _go(ctrl, "L", Action("click", "x"), leaf, leaf, "L", graph, 7,
        relation="identical")
    _go(ctrl, "L", Action("click", "x"), leaf, states["q"], "Q", graph, 8)
    _go(ctrl, "Q", Action("click", "q"), states["q"], states["q"], "Q", graph, 9,
        relation="identical")


def test_h19_no_nesting_matches_v09_guard():
    graph, states = _world()
    guard = ReturnCycleGuardSequenceController("structural")
    cand = _ctrl()
    _play_non_nested(guard, graph, states)
    _play_non_nested(cand, graph, states)
    assert cand.events == guard.events
    assert cand.ledger.return_success == guard.ledger.return_success
    assert cand.ledger.active_branch == guard.ledger.active_branch
    assert cand._escape_n == guard._escape_n
    assert cand.stack_depth == 0
    metrics = cand.metrics()
    assert metrics["nested_continuation_events"] == 0
    assert metrics["horizon_handoff_started_events"] == 0
    assert metrics["max_handoff_stack_depth"] == 0


def test_h20_every_started_instance_has_one_legal_terminal():
    graph, states = _world()
    returned = _ctrl()
    step = _return_child_exact(
        returned, graph, states,
        _handoff_to_leaf(
            returned, graph, states,
            _burn_to_final_slot(
                returned, graph, states, _open_on_nested(returned, graph, states))))
    _go(returned, "N", Action("back"), states["nested"], states["hub"],
        "P", graph, step)
    assert terminal_violations(returned.events) == []
    assert returned.metrics()["terminal_accounting_violations"] == 0

    escaped = _ctrl()
    step = _handoff_to_leaf(
        escaped, graph, states,
        _burn_to_final_slot(escaped, graph, states, _open_on_nested(escaped, graph, states)))
    leaf = states["leaf"]
    _go(escaped, "L", Action("click", "x"), leaf, leaf, "L", graph, step,
        relation="identical")
    _go(escaped, "L", Action("click", "x"), leaf, leaf, "L", graph, step + 1,
        relation="identical")
    _go(escaped, "L", Action("click", "x"), leaf, states["q"], "Q", graph, step + 2)
    _go(escaped, "Q", Action("click", "q"), states["q"], states["q"], "Q", graph,
        step + 3, relation="identical")
    assert terminal_violations(escaped.events) == []

    budget = _ctrl()
    _handoff_to_leaf(
        budget, graph, states,
        _burn_to_final_slot(budget, graph, states, _open_on_nested(budget, graph, states)))
    budget.close_open(step=30, sig="L", cluster="leaf")
    assert terminal_violations(budget.events) == []
    outcomes = [event.get("outcome") for event in _terminals(budget)]
    assert outcomes
    assert set(outcomes) <= LEGAL_TERMINALS
    assert "returned" not in outcomes


def test_source_isolation_product_default_and_historical_freezes():
    text = open(SOURCE, encoding="utf-8").read().lower()
    assert "sequence_mod.is_hub" not in text
    assert "is_hub =" not in text
    for needle in APP_NEEDLES:
        assert needle not in text
    assert app_specific_needles(SOURCE) == []
    policy = HorizonHandoffReturnGuardGhostPolicy(llm=None)
    assert policy.name == "ghost-structural-horizon-handoff-guard"
    assert policy.sequence_mode == "structural"
    assert policy.use_frontier is False
    default = GhostPolicy(llm=None, use_frontier=False)
    assert default.name == "ghost"
    assert default.sequence_mode == "off"
    assert default.use_frontier is False
    assert verify_candidate_identity() == []
    assert verify_freeze(os.path.join(
        ROOT, "experiments", "frozen", "ghost-nested-hub-guard-v0.3.12", "freeze.json")) == []
    assert verify_freeze(os.path.join(
        ROOT, "experiments", "frozen", "ghost-nested-stack-guard-v0.3.13", "freeze.json")) == []
