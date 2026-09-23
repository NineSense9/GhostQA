"""RE1–RE16 and X1–X10 for the v0.3.18 return-phase entry drain."""
import os

from ghostqa.exploration.horizon_handoff_guard import terminal_violations
from ghostqa.exploration.local_action_drain_guard import LocalActionDrainSequenceController
from ghostqa.exploration.return_entry_drain_guard import (
    ReturnEntryDrainGuardGhostPolicy, ReturnEntryDrainSequenceController,
)
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState, UIElement

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SOURCE = os.path.join(ROOT, "ghostqa", "exploration", "return_entry_drain_guard.py")
NEEDLES = (
    "buggy-lab", "buggy-directory", "buggy-forum", "buggy-billing",
    "bug-", "btn_close", "btn_reopen", "open_result", "result.html",
    "lab_reopen_clears", "manifest", "topology", "app.js",
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
    return graph


def _links(url, title, eids):
    return _page(url, title, [_el(eid, "link") for eid in eids])


def _buttons(*eids):
    return _page("/nested", "Nested", [_el(eid) for eid in eids])


def _states():
    return {
        "hub": _links("/hub", "Hub", ("go_a", "go_b", "go_c")),
        "buttons": _buttons("b1", "b2"),
        "buttons_back": _page("/nested", "Nested", (
            _el("b1"), _el("b2"), _el("up", "link", "返回"),
        )),
        "one": _buttons("b1"),
        "reveal": _buttons("b1", "b2", "b3"),
        "links": _links("/nested", "Nested", ("l1", "l2", "l3")),
        "leaf": _page("/leaf", "Leaf", (_el("x", "link"),)),
        "nested": _page("/nested", "Nested", (
            _el("b1"), _el("b2"), _el("l1", "link"), _el("l2", "link"),
        )),
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
    return ReturnEntryDrainSequenceController("structural")


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


def _enter(ctrl=None, dest="buttons", findings=None, crashed=False, step_dest="N"):
    ctrl = ctrl or _ctrl()
    graph, states = _graph(), _states()
    _go(
        ctrl, "P", Action("click", "go_a"), states["hub"], states[dest], step_dest,
        graph, 1, findings=findings or [], crashed=crashed)
    return ctrl, graph, states


def _finding(dest="buttons"):
    return _enter(findings=[_Finding()], dest=dest)


def _horizon(dest="buttons"):
    ctrl, graph, states = _enter(dest=dest, findings=[])
    page = states[dest]
    _go(ctrl, "N", Action("fill", "x"), page, page, "N", graph, 2, relation="identical")
    _go(ctrl, "N", Action("fill", "y"), page, page, "N", graph, 3, relation="identical")
    return ctrl, graph, states


def _ready_post_witness(ctrl=None, nested="nested"):
    ctrl = ctrl or _ctrl()
    graph, states = _graph(), _states()
    _go(ctrl, "P", Action("click", "go_a"), states["hub"], states[nested], "N", graph, 1)
    _go(ctrl, "N", Action("fill", "x"), states[nested], states[nested], "N", graph, 2,
        relation="identical")
    _go(ctrl, "N", Action("click", "l1"), states[nested], states["leaf"], "L", graph, 3)
    _go(ctrl, "L", Action("back"), states["leaf"], states[nested], "N", graph, 4)
    return ctrl, graph, states


def test_re1_finding_false_to_true_starts_drain():
    ctrl, graph, states = _finding()
    started = _events(ctrl, "return_entry_drain_started")
    assert len(started) == 1
    assert started[0]["visible_eligible_keys"] == ["nested:button:b1", "nested:button:b2"]
    assert ctrl.ledger.returning is True
    assert ctrl.ledger.active_branch
    chosen = ctrl.pick_override(
        [Action("click", "b2"), Action("click", "b1"), Action("back")],
        states["buttons"], graph, _ctx("N", 2))
    assert chosen.target_eid == "b1"
    assert ctrl.last_label == "return_entry_drain"


def test_re2_horizon_false_to_true_starts_drain():
    ctrl, _graph_obj, _states_obj = _horizon()
    assert _events(ctrl, "sequence_horizon_reached")
    assert _events(ctrl, "sequence_terminal") == [] or all(
        event.get("outcome") != "finding" for event in _events(ctrl, "sequence_terminal"))
    assert len(_events(ctrl, "return_entry_drain_started")) == 1
    assert ctrl.ledger.returning is True
    assert ctrl._open_instance is not None


def test_re3_true_to_true_does_not_restart():
    ctrl, graph, states = _enter(dest="links", findings=[_Finding()])
    assert ctrl.ledger.returning is True
    assert _events(ctrl, "return_entry_drain_started") == []
    graph.add_state("B", "/later", "Later", cluster_id="later")
    later = _buttons("b1", "b2")
    _go(ctrl, "N", Action("back"), states["links"], later, "B", graph, 2)
    assert ctrl.ledger.returning is True
    assert _events(ctrl, "return_entry_drain_started") == []
    again, again_graph, again_states = _finding()
    before = len(_events(again, "return_entry_drain_started"))
    action = again.pick_override(
        [Action("click", "b1"), Action("click", "b2")],
        again_states["buttons"], again_graph, _ctx("N", 2))
    _go(again, "N", action, again_states["buttons"], again_states["buttons"], "N",
        again_graph, 2, relation="identical")
    assert len(_events(again, "return_entry_drain_started")) == before == 1


def test_re4_no_buttons_matches_historical_return():
    graph, states = _graph(), _states()
    historical = LocalActionDrainSequenceController("structural")
    candidate = _ctrl()
    for ctrl in (historical, candidate):
        _go(ctrl, "P", Action("click", "go_a"), states["hub"], states["links"], "N",
            graph, 1, findings=[_Finding()])
    assert candidate.events == historical.events
    assert _events(candidate, "return_entry_drain_started") == []
    assert candidate.ledger.returning is True
    chosen = candidate.pick_override(
        [Action("click", "l1"), Action("back")], states["links"], graph, _ctx("N", 2))
    assert chosen.type == "back"
    assert candidate.last_label == "return_hub"


def test_re5_crash_transition_does_not_drain():
    graph, states = _graph(), _states()
    historical = LocalActionDrainSequenceController("structural")
    candidate = _ctrl()
    for ctrl in (historical, candidate):
        _go(ctrl, "P", Action("click", "go_a"), states["hub"], states["buttons"], "N",
            graph, 1, crashed=True)
    assert candidate.events == historical.events
    assert _events(candidate, "return_entry_drain_started") == []
    assert _terminals(candidate, "crash")
    assert _terminals(candidate, "returned") == []


def test_re6_same_hub_button_does_not_increment_return_attempts():
    ctrl, graph, states = _finding()
    attempts = ctrl.ledger.return_attempts
    seen = set(ctrl._seen_failed_return_dests)
    attempt_events = len(_events(ctrl, "return_attempt"))
    branch = ctrl.ledger.active_branch
    parent = ctrl.ledger.parent_hub_sig
    action = ctrl.pick_override(
        [Action("click", "b1")], states["buttons"], graph, _ctx("N", 2))
    _go(ctrl, "N", action, states["buttons"], states["buttons"], "N", graph, 2,
        relation="identical")
    assert _events(ctrl, "return_entry_probe_completed")
    assert ctrl.ledger.return_attempts == attempts
    assert set(ctrl._seen_failed_return_dests) == seen
    assert len(_events(ctrl, "return_attempt")) == attempt_events
    assert ctrl.ledger.active_branch == branch
    assert ctrl.ledger.parent_hub_sig == parent
    assert ctrl.ledger.returning is True
    assert ctrl.metrics()["return_entry_accounting_violations"] == 0


def test_re7_same_hub_finding_does_not_duplicate_the_terminal():
    ctrl, graph, states = _finding()
    terminals = len(_events(ctrl, "sequence_terminal"))
    action = ctrl.pick_override(
        [Action("click", "b1")], states["buttons"], graph, _ctx("N", 2))
    _go(ctrl, "N", action, states["buttons"], states["buttons"], "N", graph, 2,
        relation="identical", findings=[_Finding("probe")])
    assert _events(ctrl, "return_entry_probe_finding")
    assert _events(ctrl, "return_entry_probe_finding")[-1]["assert_ids"] == ["probe"]
    assert len(_events(ctrl, "sequence_terminal")) == terminals
    assert len(_terminals(ctrl, "finding")) == 1
    assert terminal_violations(ctrl.events) == []


def test_re8_second_button_follows_stable_element_order():
    ctrl, graph, states = _finding()
    first = ctrl.pick_override(
        [Action("click", "b2"), Action("click", "b1")],
        states["buttons"], graph, _ctx("N", 2))
    _go(ctrl, "N", first, states["buttons"], states["buttons"], "N", graph, 2,
        relation="identical")
    second = ctrl.pick_override(
        [Action("click", "b2"), Action("click", "b1")],
        states["buttons"], graph, _ctx("N", 3))
    assert first.target_eid == "b1"
    assert second.target_eid == "b2"


def test_re9_dynamic_reveal_drains_the_new_eid_once():
    ctrl, graph, states = _finding()
    first = ctrl.pick_override(
        [Action("click", "b1")], states["buttons"], graph, _ctx("N", 2))
    _go(ctrl, "N", first, states["buttons"], states["reveal"], "N", graph, 2,
        relation="similar")
    second = ctrl.pick_override(
        [Action("click", "b3"), Action("click", "b2"), Action("click", "b1")],
        states["reveal"], graph, _ctx("N", 3))
    assert second.target_eid == "b2"
    _go(ctrl, "N", second, states["reveal"], states["reveal"], "N", graph, 3,
        relation="identical")
    third = ctrl.pick_override(
        [Action("click", "b1"), Action("click", "b3")],
        states["reveal"], graph, _ctx("N", 4))
    assert third.target_eid == "b3"


def test_re10_a_key_is_drained_once():
    ctrl, graph, states = _finding(dest="one")
    action = ctrl.pick_override(
        [Action("click", "b1"), Action("back")], states["one"], graph, _ctx("N", 2))
    _go(ctrl, "N", action, states["one"], states["one"], "N", graph, 2, relation="identical")
    again = ctrl.pick_override(
        [Action("click", "b1"), Action("back")], states["one"], graph, _ctx("N", 3))
    selected = [event["eid"] for event in _events(ctrl, "return_entry_probe_selected")]
    assert selected.count("b1") == 1
    assert again is None or getattr(again, "target_eid", "") != "b1"
    assert ctrl.metrics()["repeated_local_action_key_violations"] == 0


def test_re11_exact_variant_does_not_reset_the_key():
    ctrl, graph, states = _finding()
    action = ctrl.pick_override(
        [Action("click", "b1")], states["buttons"], graph, _ctx("N", 2))
    _go(ctrl, "N", action, states["buttons"], states["buttons"], "N2", graph, 2,
        relation="similar")
    assert "nested:button:b1" in ctrl._drained_by_cluster["nested"]
    nxt = ctrl.pick_override(
        [Action("click", "b1"), Action("click", "b2")],
        states["buttons"], graph, _ctx("N2", 3))
    assert nxt.target_eid == "b2"


def test_re12_and_re13_cross_hub_keeps_the_return_obligation():
    ctrl, graph, states = _finding()
    branch = ctrl.ledger.active_branch
    parent = (ctrl.ledger.parent_hub_sig, ctrl.ledger.parent_hub_cluster)
    attempts = ctrl.ledger.return_attempts
    success = ctrl.ledger.return_success
    seen = set(ctrl._seen_failed_return_dests)
    starts = len(_events(ctrl, "branch_start"))
    action = ctrl.pick_override(
        [Action("click", "b1")], states["buttons"], graph, _ctx("N", 2))
    _go(ctrl, "N", action, states["buttons"], states["leaf"], "L", graph, 2)
    assert _events(ctrl, "return_entry_probe_left_hub")
    assert _events(ctrl, "local_action_promoted_to_child") == []
    assert len(_events(ctrl, "branch_start")) == starts
    assert ctrl._return_entry is None
    assert ctrl.ledger.returning is True
    assert ctrl.ledger.active_branch == branch
    assert (ctrl.ledger.parent_hub_sig, ctrl.ledger.parent_hub_cluster) == parent
    assert ctrl.ledger.return_attempts == attempts
    assert ctrl.ledger.return_success == success
    assert set(ctrl._seen_failed_return_dests) == seen
    assert "nested:button:b1" in ctrl._drained_by_cluster["nested"]
    assert ctrl.metrics()["return_entry_accounting_violations"] == 0
    nxt = ctrl.pick_override(
        [Action("click", "x"), Action("back")], states["leaf"], graph, _ctx("L", 3))
    assert nxt.type == "back"


def test_re14_exhaustion_resumes_historical_return():
    ctrl, graph, states = _finding(dest="buttons_back")
    branch = ctrl.ledger.active_branch
    parent = ctrl.ledger.parent_hub_sig
    attempts = ctrl.ledger.return_attempts
    success = ctrl.ledger.return_success
    for step, eid in ((2, "b1"), (3, "b2")):
        action = ctrl.pick_override(
            [Action("click", "b2"), Action("click", "b1"), Action("back")],
            states["buttons_back"], graph, _ctx("N", step))
        assert action.target_eid == eid
        _go(ctrl, "N", action, states["buttons_back"], states["buttons_back"], "N",
            graph, step, relation="identical")
    assert _events(ctrl, "return_entry_drain_exhausted")
    assert ctrl._return_entry is None
    assert ctrl.ledger.returning is True
    assert ctrl.ledger.active_branch == branch
    assert ctrl.ledger.parent_hub_sig == parent
    assert ctrl.ledger.return_attempts == attempts
    assert ctrl.ledger.return_success == success
    nxt = ctrl.pick_override(
        [Action("click", "b1"), Action("back"), Action("click", "up")],
        states["buttons_back"], graph, _ctx("N", 4))
    assert nxt.type == "back"
    assert ctrl.last_label == "return_hub"


def test_re15_parent_completion_wins():
    graph, states = _graph(), _states()
    landed = _page("/hub", "Hub", (_el("b1"), _el("b2"), _el("go_a", "link")))
    graph.add_state("P", "/hub", "Hub", cluster_id="hub")
    historical = LocalActionDrainSequenceController("structural")
    candidate = _ctrl()
    for ctrl in (historical, candidate):
        _go(ctrl, "P", Action("click", "go_a"), states["hub"], landed, "P", graph, 1,
            findings=[_Finding()])
    assert candidate.events == historical.events
    assert _events(candidate, "return_entry_drain_started") == []
    assert candidate.ledger.return_success == 1
    assert candidate.ledger.returning is False
    assert candidate.ledger.active_branch == ""


def test_re16_reset_clears_return_entry_context():
    ctrl, graph, states = _finding()
    ctrl.pick_override([Action("click", "b1")], states["buttons"], graph, _ctx("N", 2))
    assert ctrl._return_entry is not None
    ctrl.reset()
    assert ctrl.events == []
    assert ctrl._return_entry is None
    assert ctrl._pending_return_probe is None
    assert ctrl._drained_by_cluster == {}
    assert ctrl.metrics()["return_entry_drain_started_events"] == 0


def test_probe_crash_aborts_without_false_completion():
    ctrl, graph, states = _horizon()
    instance = ctrl._open_instance["id"]
    success = ctrl.ledger.return_success
    completed = ctrl.ledger.sequences_completed
    action = ctrl.pick_override(
        [Action("click", "b1")], states["buttons"], graph, _ctx("N", 4))
    _go(ctrl, "N", action, states["buttons"], states["buttons"], "N", graph, 4, crashed=True)
    assert _events(ctrl, "return_entry_drain_abort")[-1]["reason"] == "crash"
    assert ctrl._return_entry is None
    assert ctrl.ledger.return_success == success
    assert ctrl.ledger.sequences_completed == completed
    assert _terminals(ctrl, "returned") == []
    assert _terminals(ctrl, "return_cycle_abandoned", instance)
    assert terminal_violations(ctrl.events) == []
    assert ctrl.metrics()["return_entry_accounting_violations"] == 0


def test_x1_post_witness_key_is_excluded_from_return_entry():
    seeded = _ctrl()
    seeded._drained_by_cluster["nested"] = {"nested:button:b1"}
    graph, states = _graph(), _states()
    _go(seeded, "P", Action("click", "go_a"), states["hub"], states["buttons"], "N",
        graph, 1, findings=[_Finding()])
    visible = _events(seeded, "return_entry_drain_started")[-1]["visible_eligible_keys"]
    assert "nested:button:b1" not in visible
    chosen = seeded.pick_override(
        [Action("click", "b1"), Action("click", "b2")],
        states["buttons"], graph, _ctx("N", 2))
    assert chosen.target_eid == "b2"


def test_x2_return_entry_key_is_excluded_from_post_witness_drain():
    ctrl, graph, states = _finding(dest="one")
    action = ctrl.pick_override(
        [Action("click", "b1")], states["one"], graph, _ctx("N", 2))
    _go(ctrl, "N", action, states["one"], states["one"], "N", graph, 2, relation="identical")
    assert "nested:button:b1" in ctrl._drained_by_cluster["nested"]
    other = _ctrl()
    other._drained_by_cluster["nested"] = set(ctrl._drained_by_cluster["nested"])
    other, graph, states = _ready_post_witness(other)
    chosen = other.pick_override(
        [Action("click", "b1"), Action("click", "b2"), Action("click", "l2")],
        states["nested"], graph, _ctx("N", 5))
    assert chosen.target_eid == "b2"
    assert other.last_label == "local_action_drain"


def test_x3_post_witness_drain_has_priority():
    ctrl, graph, states = _ready_post_witness()
    ctrl._return_entry = {"active": True, "hub_cluster": "nested", "epoch_keys": []}
    chosen = ctrl.pick_override(
        [Action("click", "b1"), Action("click", "b2")],
        states["nested"], graph, _ctx("N", 5))
    assert chosen.target_eid == "b1"
    assert ctrl.last_label == "local_action_drain"
    assert _events(ctrl, "return_entry_probe_selected") == []


def test_x4_promoted_child_behavior_is_unchanged():
    ctrl, graph, states = _ready_post_witness()
    before = len(_events(ctrl, "branch_start"))
    action = ctrl.pick_override(
        [Action("click", "b1"), Action("click", "b2")],
        states["nested"], graph, _ctx("N", 5))
    _go(ctrl, "N", action, states["nested"], states["leaf"], "L", graph, 5)
    assert len(_events(ctrl, "branch_start")) == before + 1
    assert _events(ctrl, "local_action_promoted_to_child")
    assert _events(ctrl, "return_entry_probe_left_hub") == []
    assert _events(ctrl, "return_entry_drain_started") == []
    assert ctrl._drain["paused"] is True


def test_x5_structural_frontier_still_follows_post_witness_exhaustion():
    ctrl, graph, states = _ready_post_witness()
    for step, eid in ((5, "b1"), (6, "b2")):
        action = ctrl.pick_override(
            [Action("click", "b1"), Action("click", "b2"), Action("click", "l2")],
            states["nested"], graph, _ctx("N", step))
        assert action.target_eid == eid
        _go(ctrl, "N", action, states["nested"], states["nested"], "N", graph, step,
            relation="identical")
    assert _events(ctrl, "local_action_drain_exhausted")
    assert _events(ctrl, "local_frontier_lease_granted")
    assert _events(ctrl, "return_entry_drain_started") == []
    assert ctrl.ledger.commitment_left == 1
    assert ctrl.ledger.returning is False


def test_x6_early_reentry_matches_v0317():
    graph, states = _graph(), _states()
    historical = LocalActionDrainSequenceController("structural")
    candidate = _ctrl()
    for ctrl in (historical, candidate):
        _go(ctrl, "P", Action("click", "go_a"), states["hub"], states["nested"], "N", graph, 1)
        _go(ctrl, "N", Action("back"), states["nested"], states["hub"], "P", graph, 2)
        _go(ctrl, "P", Action("click", "go_b"), states["hub"], states["leaf"], "L", graph, 3)
    assert candidate.events == historical.events
    assert _events(candidate, "early_parent_reentry")
    assert _events(candidate, "return_entry_drain_started") == []
    assert _events(candidate, "horizon_handoff_started") == []


def test_x7_return_cycle_history_excludes_probes():
    ctrl, graph, states = _finding(dest="one")
    assert "N" in ctrl._seen_failed_return_dests
    seen = set(ctrl._seen_failed_return_dests)
    action = ctrl.pick_override(
        [Action("click", "b1")], states["one"], graph, _ctx("N", 2))
    _go(ctrl, "N", action, states["one"], states["one"], "N", graph, 2, relation="identical")
    assert _events(ctrl, "return_cycle_escape") == []
    assert set(ctrl._seen_failed_return_dests) == seen
    _go(ctrl, "N", Action("back"), states["one"], states["one"], "N", graph, 3,
        relation="identical")
    assert _events(ctrl, "return_cycle_escape")
    assert _events(ctrl, "return_cycle_escape")[-1]["step"] == 3


def test_x8_budget_end_during_return_entry_is_conservative():
    ctrl, _graph_obj, _states_obj = _horizon()
    instance = ctrl._open_instance["id"]
    success = ctrl.ledger.return_success
    ctrl.close_open(9, "N", "nested")
    assert len(_terminals(ctrl, "budget_end", instance)) == 1
    assert _terminals(ctrl, "returned", instance) == []
    assert ctrl.ledger.return_success == success
    assert ctrl._return_entry is None
    assert terminal_violations(ctrl.events) == []


def test_x9_prior_finding_terminal_is_not_duplicated():
    test_re7_same_hub_finding_does_not_duplicate_the_terminal()


def test_x10_no_trigger_matches_v0317():
    graph, states = _graph(), _states()
    historical = LocalActionDrainSequenceController("structural")
    candidate = _ctrl()
    script = (
        ("P", Action("click", "go_a"), "hub", "links", "N", {}),
        ("N", Action("fill", "x"), "links", "links", "N", {"relation": "identical"}),
        ("N", Action("click", "l1"), "links", "leaf", "L", {}),
        ("L", Action("back"), "leaf", "links", "N", {}),
        ("N", Action("click", "l2"), "links", "leaf", "L", {"findings": [_Finding()]}),
    )
    for ctrl in (historical, candidate):
        for step, (sig, action, src, dst, new_sig, kw) in enumerate(script, start=1):
            _go(ctrl, sig, action, states[src], states[dst], new_sig, graph, step, **kw)
    assert candidate.events == historical.events
    assert candidate.metrics()["return_entry_drain_started_events"] == 0
    historical_metrics = historical.metrics()
    candidate_metrics = candidate.metrics()
    for key, value in historical_metrics.items():
        assert candidate_metrics.get(key) == value


def test_policy_identity_and_source_isolation():
    policy = ReturnEntryDrainGuardGhostPolicy(llm=None)
    assert policy.name == "ghost-structural-return-entry-drain-guard"
    assert policy.sequence_mode == "structural"
    assert isinstance(policy.sequence, ReturnEntryDrainSequenceController)
    text = open(SOURCE, encoding="utf-8").read().lower()
    assert [needle for needle in NEEDLES if needle in text] == []
    from benchmark.fresh_handoff_analysis import product_default_changed
    assert product_default_changed() is False
