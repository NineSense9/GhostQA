"""FG1–FG16 and horizon differential safety for finding-gated return entry."""
import os

from ghostqa.exploration.horizon_handoff_guard import terminal_violations
from ghostqa.exploration.local_action_drain_guard import LocalActionDrainSequenceController
from ghostqa.exploration.finding_return_entry_guard import (
    FindingReturnEntryDrainGuardGhostPolicy,
    FindingReturnEntryDrainSequenceController,
)
from ghostqa.exploration.return_entry_drain_guard import ReturnEntryDrainSequenceController
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState, UIElement

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SOURCE = os.path.join(ROOT, "ghostqa", "exploration", "finding_return_entry_guard.py")
NEEDLES = (
    "buggy-lab", "buggy-directory", "buggy-forum", "buggy-billing",
    "deepbench", "wiki", "crm", "bug-", "btn_close", "btn_reopen",
    "btn_login", "btn_demo_login", "result.html", "login.html",
    "lab_reopen_clears", "manifest", "topology", "app.js",
)
AUDIT_EVENTS = {
    "finding_return_entry_horizon_bypassed",
    "finding_return_entry_nonfinding_bypassed",
    "finding_return_entry_trigger",
}


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
    }


class _Finding:
    def __init__(self, assert_id="assert-local"):
        self.evidence = {"assert_id": assert_id}

    def fingerprint(self):
        return "fp-" + self.evidence["assert_id"]


def _ctrl():
    return FindingReturnEntryDrainSequenceController("structural")


def _go(ctrl, sig, action, state, new_state, new_sig, graph, step, **kw):
    ctrl.after(
        sig, action, state, new_state, kw.get("relation", "new"),
        kw.get("findings", []), new_sig, kw.get("crashed", False), graph, step)


def _events(ctrl, name):
    return [event for event in ctrl.events if event.get("event") == name]


def _terminals(ctrl, outcome=None):
    rows = []
    for event in ctrl.events:
        if event.get("event") != "sequence_terminal":
            continue
        if outcome is not None and event.get("outcome") != outcome:
            continue
        rows.append(event)
    return rows


def _ctx(sig, step=1):
    return {"sig": sig, "step_index": step}


def _strip(events):
    return [event for event in events if event.get("event") not in AUDIT_EVENTS]


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


def _pair(factory_steps):
    graph, states = _graph(), _states()
    historical = LocalActionDrainSequenceController("structural")
    candidate = _ctrl()
    factory_steps(historical, graph, states)
    factory_steps(candidate, graph, states)
    return historical, candidate, graph, states


def _signature(ctrl):
    return {
        "returning": bool(ctrl.ledger.returning),
        "active_branch": ctrl.ledger.active_branch or "",
        "parent_sig": ctrl.ledger.parent_hub_sig or "",
        "parent_cluster": ctrl.ledger.parent_hub_cluster or "",
        "return_attempts": int(ctrl.ledger.return_attempts),
        "return_success": int(ctrl.ledger.return_success),
        "history": tuple(sorted(ctrl._seen_failed_return_dests)),
        "drained": {
            key: tuple(sorted(value))
            for key, value in sorted(ctrl._drained_by_cluster.items())
        },
        "probes": len(_events(ctrl, "return_entry_probe_selected")),
        "drains": len(_events(ctrl, "return_entry_drain_started")),
    }


def _choose(ctrl, actions, state, graph, sig, step):
    chosen = ctrl.pick_override(actions, state, graph, _ctx(sig, step))
    if chosen is None:
        return None
    return (chosen.type, getattr(chosen, "target_eid", "") or "")


def test_fg1_finding_terminal_with_button_starts_drain():
    ctrl, graph, states = _finding()
    started = _events(ctrl, "return_entry_drain_started")
    trigger = _events(ctrl, "finding_return_entry_trigger")
    assert len(started) == 1
    assert len(trigger) == 1
    assert trigger[0]["terminal_outcome"] == "finding"
    assert trigger[0]["step"] == started[0]["step"]
    assert trigger[0]["returning_before"] is False
    assert trigger[0]["returning_after"] is True
    assert trigger[0]["provenance_mode"] == "sequence_instance"
    assert trigger[0]["visible_eligible_keys"] == ["nested:button:b1", "nested:button:b2"]
    chosen = ctrl.pick_override(
        [Action("click", "b2"), Action("click", "b1"), Action("back")],
        states["buttons"], graph, _ctx("N", 2))
    assert chosen.target_eid == "b1"
    assert ctrl.metrics()["finding_return_entry_trigger_events"] == 1
    assert ctrl.metrics()["return_entry_drain_started_events"] == 1
    assert ctrl.metrics()["finding_return_entry_trigger_mismatch_violations"] == 0


def test_fg2_finding_terminal_without_button_does_not_drain():
    historical, candidate, graph, states = _pair(lambda ctrl, graph, states: _go(
        ctrl, "P", Action("click", "go_a"), states["hub"], states["links"], "N",
        graph, 1, findings=[_Finding()]))
    assert _events(candidate, "return_entry_drain_started") == []
    assert _events(candidate, "finding_return_entry_trigger") == []
    assert _terminals(candidate, "finding")
    assert candidate.ledger.returning is True
    assert _strip(candidate.events) == historical.events
    chosen = _choose(
        candidate, [Action("click", "l1"), Action("back")], states["links"], graph, "N", 2)
    assert chosen == _choose(
        historical, [Action("click", "l1"), Action("back")], states["links"], graph, "N", 2)
    assert chosen == ("back", "")


def test_fg3_horizon_with_button_does_not_drain():
    ctrl, graph, states = _horizon()
    assert _events(ctrl, "sequence_horizon_reached")
    assert _terminals(ctrl, "finding") == []
    assert _events(ctrl, "return_entry_drain_started") == []
    assert _events(ctrl, "finding_return_entry_horizon_bypassed")
    assert _events(ctrl, "finding_return_entry_horizon_bypassed")[-1]["behavior"] == "v0317_fallback"
    assert ctrl.ledger.returning is True
    assert ctrl._open_instance is not None
    chosen = ctrl.pick_override(
        [Action("click", "b1"), Action("click", "b2"), Action("back")],
        states["buttons"], graph, _ctx("N", 4))
    assert chosen.type == "back"
    assert ctrl.metrics()["finding_return_entry_horizon_bypass_events"] >= 1


def test_fg4_horizon_without_button_is_a_normal_return():
    historical, candidate, graph, states = _pair(_horizon_links)
    assert _events(candidate, "return_entry_drain_started") == []
    assert candidate.ledger.returning is True
    assert _strip(candidate.events) == historical.events
    assert _signature(candidate) == _signature(historical)
    assert _choose(
        candidate, [Action("click", "l1"), Action("back")], states["links"], graph, "N", 4,
    ) == ("back", "")


def _horizon_links(ctrl, graph, states):
    _go(ctrl, "P", Action("click", "go_a"), states["hub"], states["links"], "N", graph, 1)
    page = states["links"]
    _go(ctrl, "N", Action("fill", "x"), page, page, "N", graph, 2, relation="identical")
    _go(ctrl, "N", Action("fill", "y"), page, page, "N", graph, 3, relation="identical")


def test_fg5_crash_terminal_does_not_drain():
    historical, candidate, graph, states = _pair(lambda ctrl, graph, states: _go(
        ctrl, "P", Action("click", "go_a"), states["hub"], states["buttons"], "N",
        graph, 1, crashed=True))
    assert _terminals(candidate, "crash")
    assert _events(candidate, "return_entry_drain_started") == []
    assert _events(candidate, "finding_return_entry_nonfinding_bypassed")
    assert _events(candidate, "finding_return_entry_nonfinding_bypassed")[-1]["terminal_outcome"] == "crash"
    assert _strip(candidate.events) == historical.events
    assert _signature(candidate) == _signature(historical)


def test_fg6_returned_terminal_does_not_drain():
    ctrl, graph, states = _horizon(dest="links")
    _go(ctrl, "N", Action("back"), states["links"], states["hub"], "P", graph, 4)
    assert _terminals(ctrl, "returned")
    assert _events(ctrl, "return_entry_drain_started") == []
    assert ctrl._return_entry is None


def test_fg7_unrelated_finding_without_sequence_terminal_does_not_drain():
    ctrl, graph, states = _ctrl(), _graph(), _states()
    _go(
        ctrl, "P", Action("fill", "note"), states["hub"], states["hub"], "P",
        graph, 1, findings=[_Finding("noise")], relation="identical")
    assert _terminals(ctrl) == []
    assert _events(ctrl, "return_entry_drain_started") == []
    assert _events(ctrl, "finding_return_entry_trigger") == []
    assert ctrl.ledger.returning is False


def test_fg8_old_finding_terminal_does_not_drain_a_later_horizon():
    ctrl, graph, states = _enter(dest="links", findings=[_Finding()])
    assert _terminals(ctrl, "finding")
    assert _events(ctrl, "return_entry_drain_started") == []
    _go(ctrl, "N", Action("back"), states["links"], states["hub"], "P", graph, 2)
    page = states["buttons"]
    _go(ctrl, "P", Action("click", "go_b"), states["hub"], page, "N", graph, 3)
    _go(ctrl, "N", Action("fill", "x"), page, page, "N", graph, 4, relation="identical")
    _go(ctrl, "N", Action("fill", "y"), page, page, "N", graph, 5, relation="identical")
    assert len(_terminals(ctrl, "finding")) == 1
    assert _events(ctrl, "sequence_horizon_reached")
    assert _events(ctrl, "return_entry_drain_started") == []
    assert _events(ctrl, "finding_return_entry_horizon_bypassed")


def test_fg9_wrong_sequence_identity_does_not_drain():
    ctrl = _ctrl()
    graph, states = _graph(), _states()
    original = ctrl._maybe_start_return_entry

    def _tamper(*args, **kwargs):
        n_events = args[8]
        for event in ctrl.events[n_events:]:
            if event.get("event") == "sequence_terminal" and event.get("outcome") == "finding":
                event["sequence_instance_id"] = "seq-other"
        return original(*args, **kwargs)

    ctrl._maybe_start_return_entry = _tamper
    _go(
        ctrl, "P", Action("click", "go_a"), states["hub"], states["buttons"], "N",
        graph, 1, findings=[_Finding()])
    assert _terminals(ctrl, "finding")
    assert _terminals(ctrl, "finding")[-1]["sequence_instance_id"] == "seq-other"
    assert _events(ctrl, "return_entry_drain_started") == []
    assert ctrl.metrics()["finding_return_entry_wrong_instance_violations"] == 0


def test_fg10_matching_finding_records_exactly_one_provenance():
    ctrl, _graph_obj, _states_obj = _finding()
    triggers = _events(ctrl, "finding_return_entry_trigger")
    assert len(triggers) == 1
    assert len(ctrl._trigger_records) == 1
    assert len(ctrl._consumed_triggers) == 1
    terminal = _terminals(ctrl, "finding")[-1]
    assert triggers[0]["terminal_event_index"] == ctrl.events.index(terminal)
    assert triggers[0]["sequence_instance_id"] == terminal.get("sequence_instance_id")
    assert triggers[0]["branch_key"] == ctrl.ledger.active_branch


def test_fg11_already_returning_with_a_new_finding_does_not_start_another_epoch():
    ctrl, graph, states = _horizon()
    assert ctrl.ledger.returning is True
    before = len(_events(ctrl, "return_entry_drain_started"))
    _go(
        ctrl, "N", Action("fill", "z"), states["buttons"], states["buttons"], "N",
        graph, 4, findings=[_Finding("later")], relation="identical")
    assert len(_events(ctrl, "return_entry_drain_started")) == before == 0
    assert _terminals(ctrl, "finding") == []


def test_fg12_parent_match_completion_beats_drain():
    graph, states = _graph(), _states()
    landed = _page("/hub", "Hub", (_el("b1"), _el("b2"), _el("go_a", "link")))
    historical = LocalActionDrainSequenceController("structural")
    candidate = _ctrl()
    for ctrl in (historical, candidate):
        _go(ctrl, "P", Action("click", "go_a"), states["hub"], landed, "P", graph, 1,
            findings=[_Finding()])
    assert _events(candidate, "return_entry_drain_started") == []
    assert _strip(candidate.events) == historical.events
    assert candidate.ledger.return_success == historical.ledger.return_success == 1
    assert candidate.ledger.returning is False
    assert candidate._return_entry is None


def test_fg13_same_step_finding_and_parent_completion_leaves_no_stale_drain():
    graph, states = _graph(), _states()
    landed = _page("/hub", "Hub", (_el("b1"), _el("b2"), _el("go_a", "link")))
    historical = LocalActionDrainSequenceController("structural")
    candidate = _ctrl()
    for ctrl in (historical, candidate):
        _go(ctrl, "P", Action("click", "go_a"), states["hub"], landed, "P", graph, 1,
            findings=[_Finding()])
    assert candidate._return_entry is None
    assert candidate._pending_return_probe is None
    assert _events(candidate, "return_entry_drain_started") == []
    chosen = _choose(
        candidate, [Action("click", "b1"), Action("click", "b2"), Action("back")],
        landed, graph, "P", 2)
    assert chosen == _choose(
        historical, [Action("click", "b1"), Action("click", "b2"), Action("back")],
        landed, graph, "P", 2)
    assert candidate.ledger.sequences_completed == historical.ledger.sequences_completed
    assert candidate.ledger.return_success == historical.ledger.return_success


def test_fg14_trigger_provenance_cannot_be_reused():
    ctrl, graph, states = _finding()
    assert len(_events(ctrl, "return_entry_drain_started")) == 1
    ctrl._return_entry = None
    ctrl._maybe_start_return_entry(
        False, states["buttons"], "N", False, graph, 1,
        ctrl.ledger.return_success, ctrl.ledger.sequences_completed, 0)
    assert len(_events(ctrl, "return_entry_drain_started")) == 1
    assert len(_events(ctrl, "finding_return_entry_trigger")) == 1
    assert ctrl.metrics()["finding_return_entry_reused_trigger_violations"] == 1


def test_fg15_reset_clears_trigger_state():
    ctrl, graph, states = _finding()
    ctrl.pick_override([Action("click", "b1")], states["buttons"], graph, _ctx("N", 2))
    ctrl.reset()
    assert ctrl.events == []
    assert ctrl._return_entry is None
    assert ctrl._consumed_triggers == set()
    assert ctrl._trigger_records == []
    assert ctrl.metrics()["finding_return_entry_trigger_events"] == 0
    assert ctrl.metrics()["return_entry_drain_started_events"] == 0
    assert ctrl.metrics()["finding_return_entry_reused_trigger_violations"] == 0


def test_fg16_horizon_boundary_matches_v0317_lifecycle():
    historical, candidate, graph, states = _pair(_horizon_buttons)
    assert _events(candidate, "return_entry_drain_started") == []
    assert _strip(candidate.events) == historical.events
    assert _signature(candidate) == _signature(historical)
    actions = [Action("click", "b2"), Action("click", "b1"), Action("back")]
    assert _choose(candidate, actions, states["buttons_back"], graph, "N", 4) == _choose(
        historical, actions, states["buttons_back"], graph, "N", 4)
    assert candidate._drained_by_cluster == historical._drained_by_cluster


def _horizon_buttons(ctrl, graph, states):
    page = states["buttons_back"]
    _go(ctrl, "P", Action("click", "go_a"), states["hub"], page, "N", graph, 1)
    _go(ctrl, "N", Action("fill", "x"), page, page, "N", graph, 2, relation="identical")
    _go(ctrl, "N", Action("fill", "y"), page, page, "N", graph, 3, relation="identical")


def _cycles(ctrl, graph, states, count):
    page = states["buttons_back"]
    eids = ("go_a", "go_b", "go_c")
    step = 1
    choices = []
    actions = [Action("click", "b1"), Action("click", "b2"), Action("back")]
    for eid in eids[:count]:
        _go(ctrl, "P", Action("click", eid), states["hub"], page, "N", graph, step)
        step += 1
        _go(ctrl, "N", Action("fill", "x"), page, page, "N", graph, step, relation="identical")
        step += 1
        _go(ctrl, "N", Action("fill", "y"), page, page, "N", graph, step, relation="identical")
        step += 1
        choices.append(_choose(ctrl, actions, page, graph, "N", step))
        _go(ctrl, "N", Action("back"), page, states["hub"], "P", graph, step)
        step += 1
    return choices


def test_horizon_differential_shapes_match_v0317():
    graph, states = _graph(), _states()
    broad = ReturnEntryDrainSequenceController("structural")
    _horizon_buttons(broad, graph, states)
    assert _events(broad, "return_entry_drain_started")
    for cycles in (1, 2, 3):
        historical = LocalActionDrainSequenceController("structural")
        candidate = _ctrl()
        old_choices = _cycles(historical, graph, states, cycles)
        new_choices = _cycles(candidate, graph, states, cycles)
        assert new_choices == old_choices
        assert all(choice == ("back", "") for choice in new_choices)
        assert _events(candidate, "return_entry_probe_selected") == []
        assert _events(candidate, "return_entry_drain_started") == []
        assert _signature(candidate) == _signature(historical)
        assert _strip(candidate.events) == historical.events
        assert len(_events(candidate, "finding_return_entry_horizon_bypassed")) >= 1


def test_post_trigger_finding_drain_matches_v0318_probe_accounting():
    graph, states = _graph(), _states()
    previous = ReturnEntryDrainSequenceController("structural")
    candidate = _ctrl()
    for ctrl in (previous, candidate):
        _go(
            ctrl, "P", Action("click", "go_a"), states["hub"], states["buttons"], "N",
            graph, 1, findings=[_Finding()])
        action = ctrl.pick_override(
            [Action("click", "b2"), Action("click", "b1")], states["buttons"], graph, _ctx("N", 2))
        assert action.target_eid == "b1"
        before_attempts = ctrl.ledger.return_attempts
        _go(ctrl, "N", action, states["buttons"], states["buttons"], "N", graph, 2,
            relation="identical", findings=[_Finding("probe")])
        assert ctrl.ledger.return_attempts == before_attempts
    assert _strip(candidate.events) == previous.events
    assert _events(candidate, "return_entry_probe_finding")
    assert len(_terminals(candidate, "finding")) == len(_terminals(previous, "finding")) == 1
    assert terminal_violations(candidate.events) == []
    assert candidate.metrics()["return_entry_accounting_violations"] == 0
    assert _signature(candidate) == _signature(previous)


def test_cross_hub_probe_keeps_the_original_return_obligation():
    ctrl, graph, states = _finding()
    branch = ctrl.ledger.active_branch
    parent = (ctrl.ledger.parent_hub_sig, ctrl.ledger.parent_hub_cluster)
    attempts = ctrl.ledger.return_attempts
    seen = set(ctrl._seen_failed_return_dests)
    action = ctrl.pick_override([Action("click", "b1")], states["buttons"], graph, _ctx("N", 2))
    _go(ctrl, "N", action, states["buttons"], states["leaf"], "L", graph, 2)
    assert _events(ctrl, "return_entry_probe_left_hub")
    assert _events(ctrl, "local_action_promoted_to_child") == []
    assert ctrl.ledger.returning is True
    assert ctrl.ledger.active_branch == branch
    assert (ctrl.ledger.parent_hub_sig, ctrl.ledger.parent_hub_cluster) == parent
    assert ctrl.ledger.return_attempts == attempts
    assert set(ctrl._seen_failed_return_dests) == seen
    assert len(_events(ctrl, "finding_return_entry_trigger")) == 1


def test_policy_identity_and_source_isolation():
    policy = FindingReturnEntryDrainGuardGhostPolicy(llm=None)
    assert policy.name == "ghost-structural-finding-return-entry-drain-guard"
    assert policy.sequence_mode == "structural"
    assert isinstance(policy.sequence, FindingReturnEntryDrainSequenceController)
    text = open(SOURCE, encoding="utf-8").read().lower()
    assert [needle for needle in NEEDLES if needle in text] == []
    from benchmark.fresh_handoff_analysis import product_default_changed
    assert product_default_changed() is False
