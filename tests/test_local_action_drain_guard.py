"""A1–A12, LA1–LA10, and I1–I10 for the v0.3.17 local action drain."""
import os

from ghostqa.exploration.horizon_handoff_guard import terminal_violations
from ghostqa.exploration.local_action_drain_guard import (
    LocalActionDrainGuardGhostPolicy, LocalActionDrainSequenceController,
)
from ghostqa.exploration.reentry_frontier_guard import ReentryFrontierSequenceController
from ghostqa.exploration.sequence import BRANCH_HORIZON, branch_key
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState, UIElement

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SOURCE = os.path.join(ROOT, "ghostqa", "exploration", "local_action_drain_guard.py")
NEEDLES = (
    "buggy-lab", "buggy-directory", "buggy-forum", "buggy-billing",
    "bug-", "btn_staff_note", "btn_cool", "btn_close", "btn_reopen",
    "open_result_from_run", "open_run_again", "samples.html",
    "manifest", "app.js", "topology",
)


def _el(eid, role="button", text=None, enabled=True, kind="click"):
    return UIElement(eid, role, text if text is not None else eid, kind=kind, enabled=enabled)


def _page(url, title, elements):
    return GUIState(app="t", url=url, title=title, elements=tuple(elements), obs={})


def _graph():
    graph = StateGraph()
    graph.add_state("P", "/hub", "Hub", cluster_id="hub")
    graph.add_state("N", "/nested", "Nested", cluster_id="nested")
    graph.add_state("N2", "/nested-v", "NestedV", cluster_id="nested")
    graph.add_state("L", "/leaf", "Leaf", cluster_id="leaf")
    graph.add_state("Q", "/q", "Q", cluster_id="q")
    graph.add_state("G", "/grand", "Grand", cluster_id="grand")
    graph.add_state("G2", "/grand2", "Grand2", cluster_id="grand2")
    return graph


def _links(url, title, eids):
    return _page(url, title, [_el(eid, "link") for eid in eids])


def _states():
    return {
        "hub": _links("/hub", "Hub", ("go_a", "go_b", "go_c")),
        "nested_links": _links("/nested", "Nested", ("l1", "l2", "l3")),
        "nested": _page("/nested", "Nested", (
            _el("b1"), _el("b2"), _el("l1", "link"), _el("l2", "link"),
        )),
        "nested_v": _page("/nested-v", "NestedV", (
            _el("b1"), _el("b2"), _el("l1", "link"), _el("l2", "link"),
        )),
        "nested_reveal": _page("/nested", "Nested", (
            _el("b1"), _el("b2"), _el("b3"), _el("l1", "link"), _el("l2", "link"),
        )),
        "leaf": _page("/leaf", "Leaf", (_el("x", "link"),)),
        "q": _page("/q", "Q", (_el("q", "link"),)),
        "grand": _links("/grand", "Grand", ("g1", "g2", "g3")),
        "grand2": _links("/grand2", "Grand2", ("h1", "h2", "h3")),
        "progress": _page("/nested", "Nested", (
            _el("save", "button", "保存"),
            _el("l1", "link"), _el("l2", "link"), _el("l3", "link"),
        )),
    }


class _Finding:
    def __init__(self, assert_id="assert-local"):
        self.evidence = {"assert_id": assert_id}

    def fingerprint(self):
        return "fp-" + self.evidence["assert_id"]


def _ctrl():
    return LocalActionDrainSequenceController("structural")


def _go(ctrl, sig, action, state, new_state, new_sig, graph, step, **kw):
    ctrl.after(
        sig, action, state, new_state, kw.get("relation", "new"),
        kw.get("findings", []), new_sig, kw.get("crashed", False), graph, step)


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


def _ctx(sig, step=1):
    return {"sig": sig, "step_index": step}


def _ready(ctrl=None, nested="nested"):
    """Outer handoff whose child returns to a nested hub."""
    ctrl = ctrl or _ctrl()
    graph, states = _graph(), _states()
    _go(ctrl, "P", Action("click", "go_a"), states["hub"], states[nested], "N", graph, 1)
    _go(ctrl, "N", Action("fill", "x"), states[nested], states[nested], "N", graph, 2,
        relation="identical")
    _go(ctrl, "N", Action("click", "l1"), states[nested], states["leaf"], "L", graph, 3)
    _go(ctrl, "L", Action("back"), states["leaf"], states[nested], "N", graph, 4)
    return ctrl, graph, states


def _outer_id(ctrl):
    started = _events(ctrl, "local_action_drain_started")
    assert started
    return started[-1]["suspended_outer_id"]


def test_a1_drain_starts_only_after_a_valid_witness():
    ctrl = _ctrl()
    graph, states = _graph(), _states()
    _go(ctrl, "P", Action("click", "go_a"), states["hub"], states["nested"], "N", graph, 1)
    assert _events(ctrl, "local_action_drain_started") == []
    assert _events(ctrl, "child_parent_witness") == []


def test_a2_selects_enabled_button_and_ignores_link_and_keeps_progress():
    ctrl, graph, states = _ready(nested="progress")
    chosen = ctrl.pick_override(
        [Action("click", "l1"), Action("click", "save"), Action("back")],
        states["progress"], graph, _ctx("N", 5))
    assert chosen.target_eid == "save"
    assert ctrl.last_label == "local_action_drain"
    disabled = _page("/nested", "Nested", (
        _el("off", enabled=False), _el("l1", "link"), _el("l2", "link"), _el("l3", "link"),
    ))
    other = _ctrl()
    _ready(other, nested="nested_links")
    assert _events(other, "local_action_drain_started") == []
    assert _eligible_empty(disabled)


def _eligible_empty(state):
    ctrl = _ctrl()
    return ctrl._eligible_buttons(state, "nested") == []


def test_a3_uses_element_order_not_text():
    ctrl, graph, states = _ready()
    chosen = ctrl.pick_override(
        [Action("click", "l1"), Action("click", "b2"), Action("click", "b1")],
        states["nested"], graph, _ctx("N", 5))
    assert chosen.target_eid == "b1"
    selected = _events(ctrl, "local_action_probe_selected")[-1]
    assert selected["eid"] == "b1"
    assert selected["frontier_count"] == 2


def test_a4_same_hub_probe_is_not_a_sequence_and_drains_the_key():
    ctrl, graph, states = _ready()
    before = len(_events(ctrl, "branch_start"))
    terminals = len(_events(ctrl, "sequence_terminal"))
    action = ctrl.pick_override(
        [Action("click", "b1"), Action("click", "b2")], states["nested"], graph, _ctx("N", 5))
    _go(ctrl, "N", action, states["nested"], states["nested"], "N", graph, 5, relation="identical")
    assert len(_events(ctrl, "branch_start")) == before
    assert len(_events(ctrl, "sequence_terminal")) == terminals
    assert _events(ctrl, "local_action_probe_completed")
    assert ctrl._drained_by_cluster["nested"] == {"nested:button:b1"}
    assert ctrl.ledger.active_branch == ""
    assert ctrl._drain and ctrl._drain["active"] and not ctrl._drain["paused"]
    assert ctrl.metrics()["local_action_sequence_accounting_violations"] == 0
    assert ctrl.metrics()["same_hub_local_action_events"] == 1


def test_a5_finding_stays_on_the_probe_and_drain_continues():
    ctrl, graph, states = _ready()
    action = ctrl.pick_override(
        [Action("click", "b1")], states["nested"], graph, _ctx("N", 5))
    outer = _outer_id(ctrl)
    _go(ctrl, "N", action, states["nested"], states["nested"], "N", graph, 5,
        relation="identical", findings=[_Finding()])
    assert _events(ctrl, "local_action_probe_finding")
    assert _events(ctrl, "local_action_probe_finding")[-1]["assert_ids"] == ["assert-local"]
    assert _terminals(ctrl, iid=outer) == []
    assert ctrl._drain and ctrl._drain["active"]
    nxt = ctrl.pick_override(
        [Action("click", "b1"), Action("click", "b2")], states["nested"], graph, _ctx("N", 6))
    assert nxt.target_eid == "b2"
    assert _terminals(ctrl, iid=outer) == []
    ctrl.close_open(7, "N", "nested")
    assert len(_terminals(ctrl, "budget_end", outer)) == 1
    assert terminal_violations(ctrl.events) == []


def test_a6_same_hub_crash_aborts_without_a_fake_outer_return():
    ctrl, graph, states = _ready()
    outer = _outer_id(ctrl)
    action = ctrl.pick_override(
        [Action("click", "b1")], states["nested"], graph, _ctx("N", 5))
    _go(ctrl, "N", action, states["nested"], states["nested"], "N", graph, 5, crashed=True)
    assert _events(ctrl, "local_action_probe_crash")
    assert _events(ctrl, "local_action_drain_abort")[-1]["reason"] == "crash"
    assert _terminals(ctrl, "returned", outer) == []
    assert _terminals(ctrl, "horizon_handoff_abandoned", outer)
    assert ctrl._drain is None
    assert _events(ctrl, "parent_frame_resume_to_return") == []
    assert terminal_violations(ctrl.events) == []


def test_a7_second_distinct_button_is_selected_next():
    ctrl, graph, states = _ready()
    first = ctrl.pick_override(
        [Action("click", "b1"), Action("click", "b2")], states["nested"], graph, _ctx("N", 5))
    _go(ctrl, "N", first, states["nested"], states["nested"], "N", graph, 5, relation="identical")
    second = ctrl.pick_override(
        [Action("click", "b1"), Action("click", "b2")], states["nested"], graph, _ctx("N", 6))
    assert first.target_eid == "b1"
    assert second.target_eid == "b2"


def test_a8_same_cluster_eid_is_not_selected_twice():
    ctrl, graph, states = _ready()
    action = ctrl.pick_override(
        [Action("click", "b1")], states["nested"], graph, _ctx("N", 5))
    _go(ctrl, "N", action, states["nested"], states["nested"], "N", graph, 5, relation="identical")
    only = _page("/nested", "Nested", (
        _el("b1"), _el("l1", "link"), _el("l2", "link"), _el("l3", "link"),
    ))
    again = ctrl.pick_override(
        [Action("click", "b1"), Action("click", "l2")], only, graph, _ctx("N", 6))
    assert again is None or again.target_eid != "b1"
    selected = [event["eid"] for event in _events(ctrl, "local_action_probe_selected")]
    assert selected.count("b1") == 1
    assert ctrl.metrics()["repeated_local_action_key_violations"] == 0


def test_a9_exact_variant_keeps_the_same_eid_drained():
    ctrl, graph, states = _ready()
    action = ctrl.pick_override(
        [Action("click", "b1")], states["nested"], graph, _ctx("N", 5))
    _go(ctrl, "N", action, states["nested"], states["nested_v"], "N2", graph, 5,
        relation="similar")
    assert ctrl.metrics()["local_action_variant_revisits"] == 1
    again = ctrl.pick_override(
        [Action("click", "b1"), Action("click", "b2")], states["nested_v"], graph, _ctx("N2", 6))
    assert again.target_eid == "b2"


def test_a10_a_new_button_eid_can_be_drained_once():
    ctrl, graph, states = _ready()
    action = ctrl.pick_override(
        [Action("click", "b1")], states["nested"], graph, _ctx("N", 5))
    _go(ctrl, "N", action, states["nested"], states["nested_reveal"], "N", graph, 5,
        relation="similar")
    revealed = _events(ctrl, "local_action_new_key_revealed")
    assert [event["eid"] for event in revealed] == ["b3"]
    nxt = ctrl.pick_override(
        [Action("click", "b2"), Action("click", "b3")],
        states["nested_reveal"], graph, _ctx("N", 6))
    assert nxt.target_eid == "b2"
    assert ctrl.metrics()["newly_revealed_local_action_keys"] == 1


def test_a11_no_buttons_falls_back_to_v0316_lease():
    graph, states = _graph(), _states()
    historical = ReentryFrontierSequenceController("structural")
    candidate = _ctrl()
    for ctrl, nested in ((historical, "nested_links"), (candidate, "nested_links")):
        _go(ctrl, "P", Action("click", "go_a"), states["hub"], states[nested], "N", graph, 1)
        _go(ctrl, "N", Action("fill", "x"), states[nested], states[nested], "N", graph, 2,
            relation="identical")
        _go(ctrl, "N", Action("click", "l1"), states[nested], states["leaf"], "L", graph, 3)
        _go(ctrl, "L", Action("back"), states["leaf"], states[nested], "N", graph, 4)
    assert candidate.events == historical.events
    assert _events(candidate, "local_action_drain_started") == []
    assert _events(candidate, "local_frontier_lease_granted")
    assert candidate.ledger.commitment_left == 1


def test_a12_reset_clears_drain_state():
    ctrl, graph, states = _ready()
    ctrl.pick_override([Action("click", "b1")], states["nested"], graph, _ctx("N", 5))
    ctrl.reset()
    assert ctrl.events == []
    assert ctrl._drain is None
    assert ctrl._drained_by_cluster == {}
    assert ctrl.metrics()["local_action_drain_started_events"] == 0
    assert ctrl.metrics()["local_action_keys_drained"] == 0


def _promote(ctrl, graph, states, step=5, dest="L", new_state=None):
    action = ctrl.pick_override(
        [Action("click", "b1"), Action("click", "b2"), Action("click", "l2")],
        states["nested"], graph, _ctx("N", step))
    _go(ctrl, "N", action, states["nested"], new_state or states["leaf"], dest, graph, step)
    return action


def test_la1_navigation_promotes_a_real_child():
    ctrl, graph, states = _ready()
    before = len(_events(ctrl, "branch_start"))
    _promote(ctrl, graph, states)
    assert len(_events(ctrl, "branch_start")) == before + 1
    promoted = _events(ctrl, "local_action_promoted_to_child")[-1]
    assert promoted["button_key"] == "nested:button:b1"
    assert promoted["promoted_child_branch"] == "nested:local-button:b1"
    assert promoted["destination_hub_cluster"] == "leaf"
    assert promoted["child_parent_cluster"] == "nested"
    assert ctrl._drain["paused"] is True
    assert ctrl.ledger.active_branch


def test_la2_promoted_click_is_counted_once_at_historical_commitment():
    ctrl, graph, states = _ready()
    _promote(ctrl, graph, states)
    promoted = _events(ctrl, "local_action_promoted_to_child")[-1]
    child = promoted["promoted_child_id"]
    actions = [
        event for event in _events(ctrl, "sequence_action")
        if event.get("sequence_instance_id") == child
    ]
    assert len(actions) == 1
    assert promoted["child_commitment_after_first_action"] == BRANCH_HORIZON - 1
    assert ctrl.ledger.commitment_left == BRANCH_HORIZON - 1
    reference = ReentryFrontierSequenceController("structural")
    _go(reference, "N", Action("click", "b1"), states["nested"], states["leaf"], "L", graph, 1)
    assert reference.ledger.commitment_left == BRANCH_HORIZON - 1


def test_la3_exact_child_return_resumes_the_same_drain():
    ctrl, graph, states = _ready()
    _promote(ctrl, graph, states)
    _go(ctrl, "L", Action("back"), states["leaf"], states["nested"], "N", graph, 6)
    assert _events(ctrl, "local_action_promoted_child_witness")
    assert _events(ctrl, "local_action_promoted_child_witness")[-1]["witness_strength"] == "exact"
    assert "nested:button:b1" in ctrl._drained_by_cluster["nested"]
    assert ctrl._drain and ctrl._drain["active"] and not ctrl._drain["paused"]
    nxt = ctrl.pick_override(
        [Action("click", "b1"), Action("click", "b2")], states["nested"], graph, _ctx("N", 7))
    assert nxt.target_eid == "b2"


def test_la4_cluster_variant_return_resumes_drain():
    ctrl, graph, states = _ready()
    _promote(ctrl, graph, states)
    _go(ctrl, "L", Action("back"), states["leaf"], states["nested_v"], "N2", graph, 6)
    witness = _events(ctrl, "local_action_promoted_child_witness")[-1]
    assert witness["witness_strength"] == "cluster"
    assert ctrl._drain and not ctrl._drain["paused"]
    assert ctrl.metrics()["cross_hub_drain_violations"] == 0


def test_la5_finding_then_witness_does_not_duplicate_the_terminal():
    ctrl, graph, states = _ready()
    _promote(ctrl, graph, states)
    child = _events(ctrl, "local_action_promoted_to_child")[-1]["promoted_child_id"]
    _go(ctrl, "L", Action("back"), states["leaf"], states["nested"], "N", graph, 6,
        findings=[_Finding()])
    assert len(_terminals(ctrl, "finding", child)) == 1
    assert _terminals(ctrl, "returned", child) == []
    assert _events(ctrl, "local_action_promoted_child_witness")
    ctrl.close_open(7, "N", "nested")
    assert terminal_violations(ctrl.events) == []


def test_la6_promoted_child_crash_does_not_resume_or_fake_return():
    ctrl, graph, states = _ready()
    _promote(ctrl, graph, states)
    outer = _outer_id(ctrl)
    child = _events(ctrl, "local_action_promoted_to_child")[-1]["promoted_child_id"]
    _go(ctrl, "L", Action("click", "x"), states["leaf"], states["q"], "Q", graph, 6, crashed=True)
    assert _terminals(ctrl, "crash", child)
    assert _terminals(ctrl, "returned", outer) == []
    assert _events(ctrl, "local_action_promoted_child_witness") == []
    assert ctrl._drain is None
    assert _events(ctrl, "local_action_drain_abort")[-1]["reason"] == "crash"
    assert terminal_violations(ctrl.events) == []


def test_la7_promoted_child_escape_unwinds_without_resume():
    ctrl, graph, states = _ready()
    _promote(ctrl, graph, states)
    outer = _outer_id(ctrl)
    leaf = states["leaf"]
    _go(ctrl, "L", Action("click", "x"), leaf, leaf, "L", graph, 6, relation="identical")
    _go(ctrl, "L", Action("click", "x"), leaf, states["q"], "Q", graph, 7)
    _go(ctrl, "Q", Action("click", "q"), states["q"], states["q"], "Q", graph, 8,
        relation="identical")
    assert _events(ctrl, "return_cycle_escape")
    assert _events(ctrl, "local_action_promoted_child_unwind")
    assert _events(ctrl, "local_action_promoted_child_witness") == []
    assert _terminals(ctrl, "returned", outer) == []
    assert _terminals(ctrl, "horizon_handoff_abandoned", outer)
    assert ctrl._drain is None
    assert terminal_violations(ctrl.events) == []


def test_la8_recursive_handoff_inside_the_promoted_child_stays_lifo():
    ctrl, graph, states = _ready()
    _promote(ctrl, graph, states, dest="G", new_state=states["grand"])
    outer = _outer_id(ctrl)
    promoted = ctrl._open_instance["id"]
    _go(ctrl, "G", Action("fill", "x"), states["grand"], states["grand"], "G", graph, 6,
        relation="identical")
    _go(ctrl, "G", Action("click", "g1"), states["grand"], states["leaf"], "L", graph, 7)
    assert ctrl.stack_depth == 1
    grandchild = ctrl._open_instance["id"]
    _go(ctrl, "L", Action("back"), states["leaf"], states["grand"], "G", graph, 8)
    assert ctrl.stack_depth == 0
    assert _events(ctrl, "child_parent_witness")[-1]["child_sequence_instance_id"] == grandchild
    assert ctrl._drain and ctrl._drain["paused"]
    assert ctrl._drain["frame"].open_instance["id"] == outer
    _go(ctrl, "G", Action("fill", "y"), states["grand"], states["grand"], "G", graph, 9,
        relation="identical")
    assert ctrl.ledger.returning is True
    _go(ctrl, "G", Action("back"), states["grand"], states["nested"], "N", graph, 10)
    assert _events(ctrl, "local_action_promoted_child_witness")
    assert _events(ctrl, "local_action_promoted_child_witness")[-1]["promoted_child_id"] == promoted
    assert ctrl._drain and not ctrl._drain["paused"]
    ctrl.close_open(11, "N", "nested")
    assert terminal_violations(ctrl.events) == []


def test_la9_wrong_parent_does_not_resume_drain():
    ctrl, graph, states = _ready()
    _promote(ctrl, graph, states)
    _go(ctrl, "L", Action("back"), states["leaf"], states["q"], "Q", graph, 6)
    assert _events(ctrl, "local_action_promoted_child_witness") == []
    assert ctrl._drain and ctrl._drain["paused"]


def test_la10_wrong_child_identity_does_not_resume_drain():
    ctrl, graph, states = _ready()
    _promote(ctrl, graph, states)
    ctrl._drain["promoted_child_id"] = "seq-other"
    _go(ctrl, "L", Action("back"), states["leaf"], states["nested"], "N", graph, 6)
    assert _events(ctrl, "local_action_promoted_child_witness") == []
    assert ctrl._drain and ctrl._drain["paused"]


def test_i1_exhausted_buttons_grant_the_structural_lease():
    ctrl, graph, states = _ready()
    for step, eid in ((5, "b1"), (6, "b2")):
        action = ctrl.pick_override(
            [Action("click", "b1"), Action("click", "b2"), Action("click", "l2")],
            states["nested"], graph, _ctx("N", step))
        assert action.target_eid == eid
        _go(ctrl, "N", action, states["nested"], states["nested"], "N", graph, step,
            relation="identical")
    exhausted = _events(ctrl, "local_action_drain_exhausted")[-1]
    assert exhausted["next_phase"] == "structural_lease"
    assert exhausted["remaining_structural_frontier_count"] >= 1
    assert _events(ctrl, "local_frontier_lease_granted")
    assert ctrl.ledger.commitment_left == 1
    assert ctrl.ledger.returning is False


def test_i2_drained_buttons_are_not_the_structural_selection():
    ctrl, graph, states = _ready()
    for step in (5, 6):
        action = ctrl.pick_override(
            [Action("click", "b1"), Action("click", "b2"), Action("click", "l2")],
            states["nested"], graph, _ctx("N", step))
        _go(ctrl, "N", action, states["nested"], states["nested"], "N", graph, step,
            relation="identical")
    granted = set(_events(ctrl, "local_frontier_lease_granted")[-1]["frontier_keys"])
    assert branch_key("nested", Action("click", "b1")) not in granted
    assert branch_key("nested", Action("click", "b2")) not in granted
    assert branch_key("nested", Action("click", "l2")) in granted
    chosen = ctrl.pick_override(
        [Action("click", "b1"), Action("click", "l2")],
        states["nested"], graph, _ctx("N", 7))
    assert chosen.target_eid == "l2"


def test_i3_early_reentry_trace_stays_free_of_handoff_and_drain():
    graph, states = _graph(), _states()
    historical = ReentryFrontierSequenceController("structural")
    candidate = _ctrl()
    for ctrl in (historical, candidate):
        _go(ctrl, "P", Action("click", "go_a"), states["hub"], states["nested"], "N", graph, 1)
        _go(ctrl, "N", Action("back"), states["nested"], states["hub"], "P", graph, 2)
        _go(ctrl, "P", Action("click", "go_b"), states["hub"], states["leaf"], "L", graph, 3)
    assert candidate.events == historical.events
    assert _events(candidate, "horizon_handoff_started") == []
    assert _events(candidate, "local_action_drain_started") == []
    assert _events(candidate, "early_parent_reentry")


def test_i4_no_button_trace_matches_v0316_events():
    test_a11_no_buttons_falls_back_to_v0316_lease()


def test_i5_local_probes_do_not_add_terminals():
    ctrl, graph, states = _ready()
    before = len(_events(ctrl, "sequence_terminal"))
    action = ctrl.pick_override(
        [Action("click", "b1")], states["nested"], graph, _ctx("N", 5))
    _go(ctrl, "N", action, states["nested"], states["nested"], "N", graph, 5,
        relation="identical", findings=[_Finding()])
    assert len(_events(ctrl, "sequence_terminal")) == before
    ctrl.close_open(6, "N", "nested")
    assert terminal_violations(ctrl.events) == []


def test_i6_budget_end_during_drain_accounts_the_outer_once():
    ctrl, _graph_obj, _states_obj = _ready()
    outer = _outer_id(ctrl)
    ctrl.close_open(5, "N", "nested")
    assert len(_terminals(ctrl, "budget_end", outer)) == 1
    assert ctrl.metrics()["suspended_budget_end_count"] == 1
    assert terminal_violations(ctrl.events) == []


def test_i7_budget_end_during_promoted_child_accounts_both():
    ctrl, graph, states = _ready()
    _promote(ctrl, graph, states)
    outer = _outer_id(ctrl)
    child = _events(ctrl, "local_action_promoted_to_child")[-1]["promoted_child_id"]
    ctrl.close_open(6, "L", "leaf")
    assert len(_terminals(ctrl, "budget_end", child)) == 1
    assert len(_terminals(ctrl, "budget_end", outer)) == 1
    assert terminal_violations(ctrl.events) == []


def test_i8_return_cycle_escape_matches_historical_semantics():
    graph, states = _graph(), _states()
    historical = ReentryFrontierSequenceController("structural")
    candidate = _ctrl()
    for ctrl in (historical, candidate):
        _go(ctrl, "P", Action("click", "go_a"), states["hub"], states["leaf"], "L", graph, 1)
        leaf = states["leaf"]
        _go(ctrl, "L", Action("click", "x"), leaf, leaf, "L", graph, 2, relation="identical")
        _go(ctrl, "L", Action("click", "x"), leaf, states["q"], "Q", graph, 3)
        _go(ctrl, "Q", Action("click", "q"), states["q"], states["q"], "Q", graph, 4,
            relation="identical")
    assert candidate.events == historical.events
    assert _events(candidate, "return_cycle_escape")
    assert _terminals(candidate, "return_cycle_abandoned")


def test_i9_source_parent_fallback_is_unchanged():
    graph, states = _graph(), _states()
    historical = ReentryFrontierSequenceController("structural")
    candidate = _ctrl()
    for ctrl in (historical, candidate):
        _go(ctrl, "P", Action("click", "go_a"), states["hub"], states["nested"], "N", graph, 1)
        _go(ctrl, "P", Action("click", "go_b"), states["hub"], states["leaf"], "L", graph, 2)
    assert candidate.events == historical.events
    assert len(_events(candidate, "source_parent_reentry_repair")) == 1
    assert _events(candidate, "local_action_drain_started") == []


def test_i10_candidate_matches_v0316_when_drain_never_fires():
    graph, states = _graph(), _states()
    historical = ReentryFrontierSequenceController("structural")
    candidate = _ctrl()
    script = (
        ("P", Action("click", "go_a"), "hub", "nested_links", "N", {}),
        ("N", Action("fill", "x"), "nested_links", "nested_links", "N", {"relation": "identical"}),
        ("N", Action("click", "l1"), "nested_links", "leaf", "L", {}),
        ("L", Action("back"), "leaf", "nested_links", "N", {}),
        ("N", Action("click", "l2"), "nested_links", "leaf", "L", {}),
        ("L", Action("back"), "leaf", "nested_links", "N", {}),
    )
    for ctrl in (historical, candidate):
        for step, (sig, action, src, dst, new_sig, kw) in enumerate(script, start=1):
            _go(ctrl, sig, action, states[src], states[dst], new_sig, graph, step, **kw)
    assert candidate.events == historical.events
    assert candidate.metrics()["local_action_drain_started_events"] == 0


def test_policy_identity_and_source_isolation():
    policy = LocalActionDrainGuardGhostPolicy(llm=None)
    assert policy.name == "ghost-structural-local-action-drain-guard"
    assert policy.sequence_mode == "structural"
    text = open(SOURCE, encoding="utf-8").read().lower()
    assert [needle for needle in NEEDLES if needle in text] == []
