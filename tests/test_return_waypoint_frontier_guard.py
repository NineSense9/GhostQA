"""W1–W18 and accounting safety for return-waypoint frontier escape."""
import json
import os

from ghostqa.exploration.horizon_handoff_guard import terminal_violations
from ghostqa.exploration.policy import GhostPolicy
from ghostqa.exploration.return_waypoint_frontier_guard import (
    ReturnWaypointFrontierGuardGhostPolicy,
    ReturnWaypointFrontierSequenceController,
)
from ghostqa.exploration.sequence import is_return_action
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState, UIElement

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SOURCE = os.path.join(ROOT, "ghostqa", "exploration", "return_waypoint_frontier_guard.py")
NEEDLES = (
    "buggy-campus", "buggy-warehouse", "buggy-studio", "buggy-booking",
    "buggy-catalog", "buggy-kiosk", "BUG-CP", "BUG-WH", "BUG-ST", "BUG-BK",
    "btn_pin", "btn_cool", "btn_staff_note", "open_mid_b", "open_side",
    "course.html", "warehouse.html", "project.html", "venue.html",
    "bugs.manifest", "mechanism-opportunities",
)


def _el(eid, role="link", text=None):
    return UIElement(eid, role, text if text is not None else eid, kind="click")


def _page(url, title, elements):
    return GUIState(app="t", url=url, title=title, elements=tuple(elements), obs={})


def _graph():
    graph = StateGraph()
    for sig, cluster, url, title in (
        ("P", "list", "/list", "List"),
        ("E", "entity", "/entity", "Entity"),
        ("E2", "entity", "/entity-v", "EntityV"),
        ("M", "mid", "/mid", "Mid"),
        ("H", "childhub", "/childhub", "ChildHub"),
        ("I", "inner", "/inner", "Inner"),
        ("C", "child", "/child", "Child"),
        ("L", "leaf", "/leaf", "Leaf"),
        ("N", "novel", "/novel", "Novel"),
    ):
        graph.add_state(sig, url, title, cluster_id=cluster)
    return graph


def _states():
    return {
        "list": _page("/list", "List", (
            _el("to_entity"), _el("lb"), _el("lc"),
        )),
        "entity": _page("/entity", "Entity", (
            _el("to_mid"), _el("side"), _el("extra"), _el("pin", "button", "pin"),
        )),
        "entity_local": _page("/entity-v", "EntityV", (
            _el("submit", "button", "提交"), _el("nav_up", "link", "返回"),
        )),
        "entity_struct": _page("/entity", "Entity", (
            _el("side"), _el("nav_up", "link", "返回"), _el("filler"),
        )),
        "entity_empty": _page("/entity", "Entity", (
            _el("nav_up", "link", "返回"), _el("help", "button", "帮助"),
        )),
        "mid": _page("/mid", "Mid", (
            _el("to_child", "button"), _el("m2", "button"), _el("m3", "button"),
            _el("nav_up", "link", "返回"),
        )),
        "child": _page("/child", "Child", (_el("x", "link"),)),
        "childhub": _page("/childhub", "ChildHub", (
            _el("to_inner"), _el("ch2"), _el("ch3"),
        )),
        "inner": _page("/inner", "Inner", (
            _el("to_leaf", "button"), _el("i2", "button"), _el("i3", "button"),
            _el("nav_up", "link", "返回"),
        )),
        "leaf": _page("/leaf", "Leaf", (_el("x", "link"),)),
        "novel": _page("/novel", "Novel", (
            _el("n1"), _el("n2"), _el("n3"), _el("pin", "button", "pin"),
        )),
    }


def _ctrl():
    return ReturnWaypointFrontierSequenceController("structural")


def _events(ctrl, name):
    return [event for event in ctrl.events if event.get("event") == name]


def _go(ctrl, sig, action, state, new_state, new_sig, graph, step, **kw):
    if kw.get("label") is not None:
        ctrl.last_label = kw["label"]
    elif ctrl.ledger.returning and is_return_action(action, state):
        ctrl.last_label = "return_hub"
    else:
        ctrl.last_label = "normal"
    ctrl.after(
        sig, action, state, new_state, kw.get("relation", "new"),
        kw.get("findings", []), new_sig, kw.get("crashed", False), graph, step)


def _world():
    return _ctrl(), _graph(), _states()


def _burn_return(ctrl, sig, state, graph, step, count=2):
    for offset in range(count):
        _go(ctrl, sig, Action("fill", "x"), state, state, sig, graph,
            step + offset, relation="identical", label="normal")
    return step + count


def _drive_until_outer_return(ctrl, sig, state, graph, step):
    actions = [Action("click", element.eid) for element in state.elements]
    actions.append(Action("back"))
    for _ in range(12):
        resumes = len(_events(ctrl, "parent_frame_resume_to_return"))
        chosen = ctrl.pick_override(
            actions, state, graph, {"sig": sig, "step_index": step})
        if (
            resumes and ctrl.ledger.returning and chosen is not None
            and is_return_action(chosen, state)
        ):
            return chosen, step
        if len(_events(ctrl, "parent_frame_resume_to_return")) > resumes and (
            chosen is not None and is_return_action(chosen, state)
        ):
            return chosen, step
        if chosen is None:
            break
        ctrl.after(
            sig, chosen, state, state, "identical", [], sig, False, graph, step)
        step += 1
    raise AssertionError("outer return was not armed, events=%s returning=%s depth=%s" % (
        [event.get("event") for event in ctrl.events],
        ctrl.ledger.returning,
        ctrl.stack_depth,
    ))


def _arm_resume(ctrl=None, graph=None, states=None):
    ctrl = ctrl or _ctrl()
    graph = graph or _graph()
    states = states or _states()
    _go(ctrl, "P", Action("click", "to_entity"), states["list"], states["entity"],
        "E", graph, 1, label="branch")
    _go(ctrl, "E", Action("click", "to_mid"), states["entity"], states["mid"],
        "M", graph, 2, label="normal")
    _go(ctrl, "M", Action("click", "to_child"), states["mid"], states["child"],
        "C", graph, 3, label="normal")
    assert ctrl.stack_depth == 1
    step = _burn_return(ctrl, "C", states["child"], graph, 4)
    _go(ctrl, "C", Action("back"), states["child"], states["mid"], "M", graph, step)
    chosen, step = _drive_until_outer_return(ctrl, "M", states["mid"], graph, step + 1)
    assert _events(ctrl, "parent_frame_resume_to_return")
    assert ctrl.ledger.returning is True
    assert ctrl.stack_depth == 0
    return ctrl, graph, states, chosen, step


def _return_to(ctrl, graph, states, step, dest_sig, dest_state, source="M"):
    action = Action("back")
    before = {
        "success": ctrl.ledger.return_success,
        "started": ctrl.ledger.sequences_started,
        "completed": ctrl.ledger.sequences_completed,
    }
    ctrl.last_label = "return_hub"
    ctrl.after(
        source, action, states["mid"], states[dest_state], "new", [],
        dest_sig, False, graph, step)
    return before


def _violation_free(ctrl):
    metrics = ctrl.metrics()
    for key in (
        "return_waypoint_false_success_violations",
        "return_waypoint_terminal_accounting_violations",
        "return_waypoint_parent_precedence_violations",
        "return_waypoint_stack_scope_violations",
        "return_waypoint_unknown_hub_violations",
        "return_waypoint_repeat_escape_violations",
    ):
        assert metrics[key] == 0, key


def test_source_has_no_target_needles_and_does_not_rank():
    text = open(SOURCE, encoding="utf-8").read()
    for needle in NEEDLES:
        assert needle not in text
    assert "pick_override" not in ReturnWaypointFrontierSequenceController.__dict__
    policy = ReturnWaypointFrontierGuardGhostPolicy()
    assert policy.name == "ghost-structural-return-waypoint-frontier-guard"
    assert policy.sequence_mode == "structural"
    bare = GhostPolicy(llm=None)
    assert bare.use_frontier is False
    assert bare.sequence_mode == "off"


def test_w1_without_resume_a_true_return_does_not_escape():
    ctrl, graph, states = _world()
    _go(ctrl, "P", Action("click", "to_entity"), states["list"], states["entity"],
        "E", graph, 1, label="branch")
    _go(ctrl, "E", Action("click", "to_mid"), states["entity"], states["mid"],
        "M", graph, 2, label="normal")
    step = _burn_return(ctrl, "M", states["mid"], graph, 3, count=1)
    assert ctrl.ledger.returning is True
    assert _events(ctrl, "parent_frame_resume_to_return") == []
    _go(ctrl, "M", Action("back"), states["mid"], states["entity"], "E", graph, step)
    assert _events(ctrl, "return_waypoint_frontier_escape") == []
    assert ctrl.ledger.returning is True
    _violation_free(ctrl)


def test_w2_final_parent_completes_without_escape():
    ctrl, graph, states, _chosen, step = _arm_resume()
    success = ctrl.ledger.return_success
    ctrl.last_label = "return_hub"
    ctrl.after(
        "M", Action("back"), states["mid"], states["list"], "new", [],
        "P", False, graph, step)
    assert _events(ctrl, "return_waypoint_frontier_escape") == []
    assert ctrl.ledger.return_success == success + 1
    assert ctrl.ledger.returning is False
    _violation_free(ctrl)
    assert terminal_violations(ctrl.events) == []


def test_w3_unknown_hub_does_not_escape():
    ctrl, graph, states, _chosen, step = _arm_resume()
    success = ctrl.ledger.return_success
    _return_to(ctrl, graph, states, step, "N", "novel")
    assert _events(ctrl, "return_waypoint_frontier_escape") == []
    assert ctrl.ledger.returning is True
    assert ctrl.ledger.return_success == success
    _violation_free(ctrl)


def test_w4_known_waypoint_without_residual_does_not_escape():
    ctrl, graph, states, _chosen, step = _arm_resume()
    _return_to(ctrl, graph, states, step, "E", "entity_empty")
    assert _events(ctrl, "return_waypoint_frontier_escape") == []
    assert ctrl.ledger.returning is True
    _violation_free(ctrl)


def test_w5_residual_local_button_escapes_without_success():
    ctrl, graph, states, _chosen, step = _arm_resume()
    before = _return_to(ctrl, graph, states, step, "E2", "entity_local")
    event = _events(ctrl, "return_waypoint_frontier_escape")[-1]
    assert event["local_residual_count"] >= 1
    assert event["structural_residual_count"] == 0
    assert event["reason"] == "residual_frontier"
    assert event["waypoint_match_strength"] == "cluster"
    assert ctrl.ledger.return_success == before["success"]
    assert ctrl.ledger.sequences_started == before["started"]
    assert ctrl.ledger.sequences_completed == before["completed"]
    assert ctrl.ledger.returning is False
    assert ctrl.metrics()["return_waypoint_escape_cluster_matches"] == 1
    _violation_free(ctrl)


def test_w6_residual_structural_branch_escapes():
    ctrl, graph, states, _chosen, step = _arm_resume()
    _return_to(ctrl, graph, states, step, "E", "entity_struct")
    event = _events(ctrl, "return_waypoint_frontier_escape")[-1]
    assert event["structural_residual_count"] >= 1
    assert event["local_residual_count"] == 0
    assert event["waypoint_match_strength"] == "exact"
    assert ctrl.metrics()["return_waypoint_escape_exact_matches"] == 1
    _violation_free(ctrl)


def test_w7_only_return_back_and_distractor_do_not_escape():
    ctrl, graph, states, _chosen, step = _arm_resume()
    _return_to(ctrl, graph, states, step, "E", "entity_empty")
    assert _events(ctrl, "return_waypoint_frontier_escape") == []
    assert ctrl.ledger.returning is True


def test_w8_stack_depth_above_zero_does_not_escape():
    ctrl, graph, states = _world()
    _go(ctrl, "P", Action("click", "to_entity"), states["list"], states["entity"],
        "E", graph, 1, label="branch")
    _go(ctrl, "E", Action("click", "to_mid"), states["entity"], states["mid"],
        "M", graph, 2)
    _go(ctrl, "M", Action("click", "to_child"), states["mid"], states["childhub"],
        "H", graph, 3)
    assert ctrl.stack_depth == 1
    _go(ctrl, "H", Action("click", "to_inner"), states["childhub"], states["inner"],
        "I", graph, 4)
    _go(ctrl, "I", Action("click", "to_leaf"), states["inner"], states["leaf"],
        "L", graph, 5)
    assert ctrl.stack_depth == 2
    step = _burn_return(ctrl, "L", states["leaf"], graph, 6)
    _go(ctrl, "L", Action("back"), states["leaf"], states["inner"], "I", graph, step)
    _chosen, step = _drive_until_outer_return(ctrl, "I", states["inner"], graph, step + 1)
    assert ctrl.stack_depth == 1
    assert ctrl.ledger.returning is True
    success = ctrl.ledger.return_success
    ctrl.last_label = "return_hub"
    ctrl.after(
        "I", Action("back"), states["inner"], states["childhub"], "new", [],
        "H", False, graph, step)
    assert _events(ctrl, "return_waypoint_frontier_escape") == []
    assert ctrl.stack_depth == 1
    assert ctrl.ledger.return_success == success
    assert ctrl.metrics()["return_waypoint_stack_scope_violations"] == 0


def test_w9_w12_escape_accounting_and_cleared_obligation():
    ctrl, graph, states, _chosen, step = _arm_resume()
    outer = ctrl._open_id()
    branch = ctrl.ledger.active_branch
    parent = ctrl.ledger.parent_hub_sig
    before = _return_to(ctrl, graph, states, step, "E", "entity")
    assert ctrl.ledger.return_success == before["success"]
    assert ctrl.ledger.sequences_started == before["started"]
    assert ctrl.ledger.sequences_completed == before["completed"]
    assert ctrl.ledger.returning is False
    assert ctrl.ledger.active_branch == ""
    assert ctrl.ledger.commitment_left == 0
    assert ctrl.ledger.parent_hub_sig == ""
    assert ctrl._open_instance is None
    assert ctrl.stack_depth == 0
    terminals = [
        event for event in ctrl.events
        if event.get("event") == "sequence_terminal"
        and event.get("sequence_instance_id") == outer
    ]
    assert len(terminals) == 1
    assert terminals[0]["outcome"] == "return_cycle_abandoned"
    assert terminals[0]["reason"] == "return_waypoint_escape"
    assert not any(event.get("outcome") == "returned" and event.get("sequence_instance_id") == outer
                   for event in ctrl.events)
    record = ctrl.ledger.hubs[parent]
    assert branch not in record.completed
    assert branch not in record.returned
    assert ctrl.metrics()["return_waypoint_frontier_escape_events"] == 1
    _violation_free(ctrl)
    assert terminal_violations(ctrl.events) == []


def test_w13_next_action_follows_normal_policy_order():
    ctrl, graph, states, _chosen, step = _arm_resume()
    _return_to(ctrl, graph, states, step, "E", "entity")
    assert ctrl.last_label == "normal"
    escape = _events(ctrl, "return_waypoint_frontier_escape")[-1]
    assert "chosen" not in escape
    first = ctrl.pick_override(
        [Action("click", "side"), Action("click", "extra"), Action("click", "pin")],
        states["entity"], graph, {"sig": "E", "step_index": step + 1})
    assert first.target_eid == "side"
    second_ctrl, graph2, states2, _chosen2, step2 = _arm_resume()
    _return_to(second_ctrl, graph2, states2, step2, "E", "entity")
    second = second_ctrl.pick_override(
        [Action("click", "pin"), Action("click", "side")],
        states2["entity"], graph2, {"sig": "E", "step_index": step2 + 1})
    assert second.target_eid == "pin"


def test_w14_same_branch_and_waypoint_is_suppressed():
    ctrl, graph, states, _chosen, step = _arm_resume()
    _return_to(ctrl, graph, states, step, "E", "entity")
    assert ctrl.metrics()["return_waypoint_frontier_escape_events"] == 1
    _go(ctrl, "P", Action("click", "to_entity"), states["list"], states["entity"],
        "E", graph, step + 1, label="branch")
    _go(ctrl, "E", Action("click", "to_mid"), states["entity"], states["mid"],
        "M", graph, step + 2)
    _go(ctrl, "M", Action("click", "to_child"), states["mid"], states["child"],
        "C", graph, step + 3)
    nxt = _burn_return(ctrl, "C", states["child"], graph, step + 4)
    _go(ctrl, "C", Action("back"), states["child"], states["mid"], "M", graph, nxt)
    _chosen, nxt = _drive_until_outer_return(ctrl, "M", states["mid"], graph, nxt + 1)
    success = ctrl.ledger.return_success
    _return_to(ctrl, graph, states, nxt, "E", "entity")
    assert ctrl.metrics()["return_waypoint_frontier_escape_events"] == 1
    assert ctrl.metrics()["return_waypoint_escape_repeat_suppressed"] >= 1
    assert ctrl.ledger.return_success == success
    assert ctrl.ledger.returning is True
    assert ctrl.metrics()["return_waypoint_repeat_escape_violations"] == 0


def test_w15_same_cluster_variant_still_escapes():
    ctrl, graph, states, _chosen, step = _arm_resume()
    _return_to(ctrl, graph, states, step, "E2", "entity_local")
    event = _events(ctrl, "return_waypoint_frontier_escape")[-1]
    assert event["waypoint_sig"] == "E2"
    assert event["waypoint_match_strength"] == "cluster"
    assert event["waypoint_cluster"] != event["original_final_parent_cluster"]


def test_w16_return_cycle_escape_precludes_waypoint_escape():
    ctrl, graph, states, _chosen, step = _arm_resume()
    _return_to(ctrl, graph, states, step, "E", "entity_empty")
    assert _events(ctrl, "return_waypoint_frontier_escape") == []
    assert ctrl.ledger.returning is True
    ctrl.last_label = "return_hub"
    ctrl.after(
        "M", Action("back"), states["mid"], states["entity"], "new", [],
        "E", False, graph, step + 1)
    assert _events(ctrl, "return_cycle_escape")
    assert _events(ctrl, "return_waypoint_frontier_escape") == []
    outer_terminals = [
        event for event in ctrl.events
        if event.get("event") == "sequence_terminal"
        and event.get("sequence_instance_id") == "seq-0001"
    ]
    assert len(outer_terminals) == 1
    assert outer_terminals[0]["outcome"] == "return_cycle_abandoned"
    assert outer_terminals[0].get("reason") != "return_waypoint_escape"
    _violation_free(ctrl)
    assert terminal_violations(ctrl.events) == []


def test_w17_crash_does_not_escape():
    ctrl, graph, states, _chosen, step = _arm_resume()
    ctrl.last_label = "return_hub"
    ctrl.after(
        "M", Action("back"), states["mid"], None, "new", [],
        "CRASHED", True, graph, step)
    assert _events(ctrl, "return_waypoint_frontier_escape") == []
    _violation_free(ctrl)


def test_w18_reset_clears_resumed_context_and_suppression():
    ctrl, graph, states, _chosen, step = _arm_resume()
    _return_to(ctrl, graph, states, step, "E", "entity")
    assert ctrl._resumed
    assert ctrl._escape_keys
    assert ctrl._outbound
    ctrl.reset()
    assert ctrl._resumed == {}
    assert ctrl._escape_keys == set()
    assert ctrl._outbound == {}
    assert ctrl.metrics()["return_waypoint_frontier_escape_events"] == 0
    ctrl, graph, states, _chosen, step = _arm_resume(ctrl, graph, states)
    _return_to(ctrl, graph, states, step, "E", "entity")
    assert ctrl.metrics()["return_waypoint_frontier_escape_events"] == 1
    assert ctrl.metrics()["return_waypoint_escape_repeat_suppressed"] == 0


def test_accounting_budget_end_is_serializable_and_does_not_orphan():
    ctrl, graph, states, _chosen, step = _arm_resume()
    _return_to(ctrl, graph, states, step, "E", "entity_empty")
    assert ctrl.ledger.active_branch
    assert ctrl._open_instance is not None
    ctrl.close_open(step + 1, "E", "entity")
    encoded = json.dumps(ctrl.metrics(), ensure_ascii=False, default=str)
    assert encoded
    assert ctrl.stack_depth == 0
    assert ctrl._open_instance is None
    assert ctrl.stack_depth >= 0


def test_early_parent_reentry_is_not_a_waypoint_escape():
    ctrl, graph, states = _world()
    _go(ctrl, "P", Action("click", "to_entity"), states["list"], states["entity"],
        "E", graph, 1, label="branch")
    assert ctrl.ledger.returning is False
    _go(ctrl, "E", Action("fill", "x"), states["entity"], states["list"],
        "P", graph, 2, relation="identical", label="normal")
    assert _events(ctrl, "return_waypoint_frontier_escape") == []
    assert ctrl.ledger.return_success == 1
