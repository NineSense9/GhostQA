"""RD1–RD30, SCC gates, and source isolation for residual-frontier debt."""
import os

from ghostqa.exploration.policy import GhostPolicy
from ghostqa.exploration.return_waypoint_frontier_guard import (
    ReturnWaypointFrontierSequenceController,
)
from ghostqa.exploration.residual_frontier_debt_guard import (
    ResidualFrontierDebtGuardGhostPolicy,
    ResidualFrontierDebtSequenceController,
    component_pending,
    normalize_residual_tokens,
    observed_scc,
)
from ghostqa.state.graph import StateEdge
from ghostqa.state.models import Action
from tests.test_return_waypoint_frontier_guard import (
    _burn_return,
    _drive_until_outer_return,
    _el,
    _events,
    _go,
    _graph,
    _page,
    _states,
    _violation_free,
)
from benchmark.fresh_composite_analysis import product_default_changed
from benchmark.residual_frontier_debt_audit import (
    normalize_residual_tokens as audit_normalize,
)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SOURCE = os.path.join(ROOT, "ghostqa", "exploration", "residual_frontier_debt_guard.py")
EXPLORER = os.path.join(ROOT, "ghostqa", "exploration", "explorer.py")
NEEDLES = (
    "buggy-campus", "buggy-studio", "buggy-warehouse", "buggy-booking",
    "buggy-catalog", "buggy-kiosk", "help.html", "handbook.html",
    "settings.html", "BUG-", "btn_pin", "btn_cool", "open_side", "nav_prefs",
)


def _ctrl():
    return ResidualFrontierDebtSequenceController("structural")


def _arm(ctrl=None, graph=None, states=None):
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
    _chosen, step = _drive_until_outer_return(ctrl, "M", states["mid"], graph, step + 1)
    assert ctrl.ledger.returning is True
    assert ctrl.stack_depth == 0
    return ctrl, graph, states, step


def _policy(ctrl):
    policy = ResidualFrontierDebtGuardGhostPolicy()
    policy.sequence = ctrl
    return policy


def _escape(ctrl, graph, states, step, dest_sig="E", dest_state="entity"):
    ctrl.last_label = "return_hub"
    ctrl.after(
        "M", Action("back"), states["mid"], states[dest_state], "new", [],
        dest_sig, False, graph, step)
    return _events(ctrl, "residual_frontier_debt_created")


def _edge(graph, src, dst, eid, src_cluster="", dst_cluster=""):
    graph.add_transition(
        src, "/" + src, src, f"click:{eid}:", dst, "/" + dst, dst,
        action=Action("click", eid),
        src_cluster=src_cluster, dst_cluster=dst_cluster)


def _closed_sink(graph, pending=False, outside=False, include=()):
    graph.add_state("A", "/a", "A", cluster_id="sink")
    graph.add_state("B", "/b", "B", cluster_id="sink")
    _edge(graph, "A", "B", "ab", "sink", "sink")
    _edge(graph, "B", "A", "ba", "sink", "sink")
    previous = "B"
    for sig in include:
        _edge(graph, previous, sig, "in" + sig, "sink", graph.nodes[sig].cluster_id)
        _edge(graph, sig, "A", "back" + sig, graph.nodes[sig].cluster_id, "sink")
        previous = sig
    if outside:
        graph.add_state("Z", "/z", "Z", cluster_id="out")
        _edge(graph, "A", "Z", "leave", "sink", "out")
    if pending:
        node = graph.nodes["A"]
        node.observed_opps["click:left"] = {
            "kind": "click", "progress": False, "field_type": "unknown",
        }
        node.observed_actions.add("click:left:")


def _arm_debt(dest_sig="E", dest_state="entity"):
    ctrl, graph, states, step = _arm()
    created = _escape(ctrl, graph, states, step, dest_sig, dest_state)
    assert created, [event.get("event") for event in ctrl.events[-6:]]
    return ctrl, graph, states, step, created[-1]


def _relocate(ctrl, graph, sig="A", budget=40, step_index=0):
    policy = _policy(ctrl)
    return policy.maybe_relocate(graph, None, [], {
        "sig": sig, "step_index": step_index, "budget": budget,
    })


def test_historical_helpers_are_not_shadowed():
    parent = set(ReturnWaypointFrontierSequenceController.__dict__)
    ours = set(ResidualFrontierDebtSequenceController.__dict__)
    allowed = {
        "__init__", "__doc__", "__module__", "__firstlineno__",
        "__static_attributes__", "reset", "after", "metrics",
    }
    assert ours & parent <= allowed
    ctrl = ResidualFrontierDebtSequenceController("structural")
    snap = ctrl._snapshot()
    assert snap["active_branch"] == ""
    assert "parent_hub_sig" in snap


def test_source_isolation_and_product_default():
    text = open(SOURCE, encoding="utf-8").read()
    for needle in NEEDLES:
        assert needle not in text, needle
    assert "pick_override" not in ResidualFrontierDebtSequenceController.__dict__
    assert "select" not in ResidualFrontierDebtGuardGhostPolicy.__dict__
    policy = ResidualFrontierDebtGuardGhostPolicy()
    assert policy.name == "ghost-structural-residual-frontier-debt-guard"
    assert policy.use_frontier is False
    assert policy.sequence_mode == "structural"
    assert isinstance(policy.sequence, ResidualFrontierDebtSequenceController)
    bare = GhostPolicy(llm=None)
    assert bare.name == "ghost"
    assert bare.use_frontier is False
    assert bare.sequence_mode == "off"
    assert product_default_changed() is False
    explorer = open(EXPLORER, encoding="utf-8").read()
    assert "if seqc is not None and not restore_step:" in explorer
    relocate = explorer.split("if not pending_restore:", 1)[1].split("restore_step = False", 1)[0]
    assert "policy.reset(" not in relocate


def test_normalize_dedupes_button_and_click_without_hardcoded_eids():
    tokens = normalize_residual_tokens(
        ["hub:button:alpha", "hub:button:beta"],
        ["hub:click:alpha", "hub:click:gamma", "other:click:alpha"],
        "hub",
    )
    assert tokens == ["hub:click:alpha", "hub:click:beta", "hub:click:gamma"]
    assert audit_normalize(
        ["hub:button:alpha"], ["hub:click:alpha"], "hub") == tokens[:1]


def test_rd1_waypoint_escape_creates_debt():
    ctrl, graph, states, step, event = _arm_debt("E2", "entity_local")
    assert event["remaining_count"] >= 1
    assert event["waypoint_sig"] == "E2"
    assert event["waypoint_cluster"]
    assert event["source_sequence_instance_id"]
    assert ctrl._debts[0]["status"] == "unresolved"
    assert ctrl.metrics()["residual_frontier_debts_created"] == 1
    assert ctrl.metrics()["residual_frontier_tokens_created"] >= 1
    _violation_free(ctrl)


def test_rd2_empty_residual_escape_creates_no_debt():
    ctrl, graph, states, step = _arm()
    created = _escape(ctrl, graph, states, step, "E", "entity_empty")
    assert created == []
    assert _events(ctrl, "return_waypoint_frontier_escape") == []
    assert ctrl.metrics()["residual_frontier_debts_created"] == 0


def test_rd3_duplicate_local_and_structural_eid_dedupes():
    ctrl, _graph_obj, _states_obj, _step, event = _arm_debt("E", "entity")
    raw = event["raw_residual_keys"]["local"] + event["raw_residual_keys"]["structural"]
    tokens = event["normalized_residual_tokens"]
    assert len(tokens) < len(raw)
    eids = [token.split(":")[-1] for token in tokens]
    assert eids.count("pin") == 1
    assert any(item.endswith(":button:pin") for item in raw)
    assert any(item.endswith(":click:pin") for item in raw)


def test_rd4_arrival_does_not_clear_debt():
    ctrl, graph, states, step, event = _arm_debt()
    _closed_sink(graph)
    _edge(graph, "P", "E", "to_entity", "list", "entity")
    assert _relocate(ctrl, graph) == "E"
    assert _relocate(ctrl, graph, sig="E") is None
    debt = ctrl._debts[0]
    assert debt["status"] == "unresolved"
    assert debt["remaining_tokens"] == event["normalized_residual_tokens"]
    assert ctrl.metrics()["residual_frontier_debts_resolved"] == 0
    assert _events(ctrl, "residual_frontier_debt_relocation_failure") == []


def test_rd5_matching_normal_action_consumes_token():
    ctrl, graph, states, step, event = _arm_debt("E2", "entity_local")
    token = event["normalized_residual_tokens"][0]
    eid = token.split(":")[-1]
    before = ctrl.ledger.return_success
    page = _page("/entity-v", "EntityV", (_el(eid, "button"),))
    _go(ctrl, "E2", Action("click", eid), page, page, "E2", graph, step + 1)
    assert token in ctrl._debts[0]["consumed_tokens"]
    assert _events(ctrl, "residual_frontier_debt_consumed")
    assert ctrl.ledger.return_success == before


def test_rd6_restore_action_does_not_consume_token():
    ctrl, graph, states, step, event = _arm_debt("E2", "entity_local")
    token = event["normalized_residual_tokens"][0]
    eid = token.split(":")[-1]
    before_events = len(ctrl.events)
    before_success = ctrl.ledger.return_success
    ctrl.observe_restore_action("E2", Action("click", eid), graph, step + 1)
    assert ctrl._debts[0]["remaining_tokens"] == event["normalized_residual_tokens"]
    assert len(ctrl.events) == before_events
    assert ctrl.ledger.return_success == before_success
    assert ctrl.metrics()["residual_frontier_restore_sequence_violations"] == 0
    assert ctrl.metrics()["residual_frontier_tokens_consumed"] == 0


def test_rd7_all_tokens_consumed_resolves_debt():
    ctrl, graph, states, step, event = _arm_debt("E2", "entity_local")
    assert len(event["normalized_residual_tokens"]) == 1
    token = event["normalized_residual_tokens"][0]
    eid = token.split(":")[-1]
    page = _page("/entity-v", "EntityV", (_el(eid, "button"),))
    _go(ctrl, "E2", Action("click", eid), page, page, "E2", graph, step + 1)
    assert ctrl._debts[0]["status"] == "resolved"
    assert ctrl._debts[0]["remaining_tokens"] == []
    assert _events(ctrl, "residual_frontier_debt_resolved")
    assert ctrl.metrics()["residual_frontier_debts_resolved"] == 1
    assert ctrl.metrics()["residual_frontier_debts_unresolved"] == 0


def _ready(dest_sig="E", dest_state="entity"):
    ctrl, graph, states, step, event = _arm_debt(dest_sig, dest_state)
    _closed_sink(graph)
    _edge(graph, "P", dest_sig, "to_target", "list", graph.nodes[dest_sig].cluster_id)
    return ctrl, graph, states, step, event


def test_rd8_active_sequence_suppresses_relocation():
    ctrl, graph, _states_obj, _step, _event = _ready()
    ctrl._open_instance = {"id": "seq-open", "branch": "b", "len": 1}
    assert _relocate(ctrl, graph) is None
    assert ctrl.metrics()["residual_frontier_active_sequence_suppressed"] == 1
    assert ctrl.metrics()["residual_frontier_debt_relocations"] == 0


def test_rd9_returning_suppresses_relocation():
    ctrl, graph, _states_obj, _step, _event = _ready()
    ctrl.ledger.returning = True
    assert _relocate(ctrl, graph) is None
    assert ctrl.metrics()["residual_frontier_active_sequence_suppressed"] == 1


def test_rd10_stack_depth_suppresses_relocation():
    ctrl, graph, _states_obj, _step, _event = _ready()
    ctrl._stack.append(object())
    assert ctrl.stack_depth == 1
    assert _relocate(ctrl, graph) is None
    assert ctrl.metrics()["residual_frontier_active_sequence_suppressed"] == 1


def test_rd11_local_and_return_entry_lifecycle_suppresses_relocation():
    cases = (
        ("_drain", {"active": True}),
        ("_drain", {"paused": True, "promoted_child_id": "child-1"}),
        ("_return_entry", {"active": True}),
        ("_pending_return_probe", {"eid": "probe"}),
        ("_pending_probe", {"eid": "local"}),
        ("_lease", {"active": True}),
        ("_pending_lease_action", {"key": "lease"}),
    )
    for attr, value in cases:
        ctrl, graph, _states_obj, _step, _event = _ready()
        setattr(ctrl, attr, value)
        assert _relocate(ctrl, graph) is None, attr
        assert ctrl.metrics()["residual_frontier_active_sequence_suppressed"] == 1, attr
        assert ctrl.metrics()["residual_frontier_debt_relocations"] == 0, attr


def test_rd12_open_scc_suppresses_relocation():
    ctrl, graph, _states_obj, _step, _event = _arm_debt()
    _closed_sink(graph, outside=True)
    _edge(graph, "P", "E", "to_entity", "list", "entity")
    assert _relocate(ctrl, graph) is None
    assert ctrl.metrics()["residual_frontier_open_scc_suppressed"] == 1
    assert ctrl.metrics()["residual_frontier_debt_relocations"] == 0


def test_rd13_closed_scc_with_pending_interaction_suppresses_relocation():
    ctrl, graph, _states_obj, _step, _event = _arm_debt()
    _closed_sink(graph, pending=True)
    _edge(graph, "P", "E", "to_entity", "list", "entity")
    assert component_pending(graph, ["A"]) > 0
    assert _relocate(ctrl, graph) is None
    assert ctrl.metrics()["residual_frontier_pending_scc_suppressed"] == 1


def test_rd14_debt_target_inside_scc_suppresses_relocation():
    ctrl, graph, _states_obj, _step, _event = _arm_debt()
    _closed_sink(graph, include=("E",))
    assert _relocate(ctrl, graph) is None
    assert ctrl.metrics()["residual_frontier_inside_scc_suppressed"] == 1
    assert ctrl._debts[0]["skips"][-1]["reason"] == "inside_scc"


def test_rd15_no_replay_path_suppresses_relocation():
    ctrl, graph, _states_obj, _step, _event = _arm_debt()
    _closed_sink(graph)
    assert graph.shortest_path(graph.start_sig, "E") is None
    assert _relocate(ctrl, graph) is None
    assert ctrl.metrics()["residual_frontier_no_path_suppressed"] == 1


def test_rd16_insufficient_budget_suppresses_relocation():
    ctrl, graph, _states_obj, _step, _event = _ready()
    path = graph.shortest_path(graph.start_sig, "E")
    assert path is not None and len(path) >= 1
    assert _relocate(ctrl, graph, budget=len(path), step_index=0) is None
    assert ctrl.metrics()["residual_frontier_budget_suppressed"] == 1


def test_rd17_valid_gate_relocates_oldest_debt():
    ctrl, graph, _states_obj, _step, event = _ready()
    target = _relocate(ctrl, graph)
    assert target == "E"
    assert target == event["waypoint_sig"]
    relocated = _events(ctrl, "residual_frontier_debt_relocate")[-1]
    assert relocated["debt_id"] == event["debt_id"]
    assert relocated["reason"] == "closed_exhausted_scc"
    assert relocated["scc_closed"] is True
    assert relocated["scc_pending_count"] == 0
    assert relocated["active_sequence"] is False
    assert relocated["current_scc_node_count"] == 2
    assert relocated["replay_path_length"] >= 1
    assert relocated["remaining_debt_tokens"]
    assert "app" not in relocated
    assert ctrl._debts[0]["status"] == "unresolved"
    assert ctrl._debts[0]["relocation_count"] == 1
    assert ctrl.metrics()["residual_frontier_debt_relocations"] == 1
    assert ctrl.metrics()["residual_frontier_false_success_violations"] == 0


def test_rd18_replay_creates_no_sequence_events_or_false_success():
    ctrl, graph, states, step, event = _ready()
    assert _relocate(ctrl, graph) == "E"
    before = list(ctrl.events)
    success = ctrl.ledger.return_success
    started = ctrl.ledger.sequences_started
    completed = ctrl.ledger.sequences_completed
    eid = event["normalized_residual_tokens"][0].split(":")[-1]
    ctrl.observe_restore_action("P", Action("click", eid), graph, step + 1)
    assert ctrl.events == before
    assert ctrl.ledger.return_success == success
    assert ctrl.ledger.sequences_started == started
    assert ctrl.ledger.sequences_completed == completed
    assert ctrl._debts[0]["status"] == "unresolved"
    names = {item.get("event") for item in ctrl.events}
    assert "branch_start" not in {
        item.get("event") for item in ctrl.events[len(before):]
    }
    assert ctrl.metrics()["residual_frontier_restore_sequence_violations"] == 0
    del names


def test_rd19_restore_failure_preserves_unresolved_debt():
    ctrl, graph, _states_obj, _step, _event = _ready()
    assert _relocate(ctrl, graph) == "E"
    assert _relocate(ctrl, graph, sig="A") is None
    assert ctrl._debts[0]["status"] == "unresolved"
    assert ctrl._debts[0]["consumed_tokens"] == []
    assert _events(ctrl, "residual_frontier_debt_relocation_failure")
    assert ctrl.metrics()["residual_frontier_relocation_failures"] == 1
    assert _relocate(ctrl, graph, sig="A") is None
    assert ctrl.metrics()["residual_frontier_relocation_failures"] == 1
    assert ctrl.metrics()["residual_frontier_debt_relocations"] == 1


def test_rd20_reset_clears_debt_between_runs():
    ctrl, graph, _states_obj, _step, _event = _ready()
    assert _relocate(ctrl, graph) == "E"
    assert ctrl._debts
    policy = _policy(ctrl)
    assert ctrl._debts
    policy.reset()
    assert policy.sequence._debts == []
    assert policy.sequence._hold is None
    metrics = policy.sequence.metrics()
    assert metrics["residual_frontier_debts_created"] == 0
    assert metrics["residual_frontier_debt_relocations"] == 0
    assert metrics["residual_frontier_gate_checks"] == 0


def test_rd21_partial_debt_permits_later_relocation():
    ctrl, graph, _states_obj, step, event = _arm_debt()
    tokens = list(event["normalized_residual_tokens"])
    assert len(tokens) >= 2
    eid = tokens[0].split(":")[-1]
    page = _page("/entity", "Entity", (_el(eid, "button"),))
    _go(ctrl, "E", Action("click", eid), page, page, "E", graph, step + 1)
    assert ctrl._debts[0]["status"] == "unresolved"
    assert tokens[0] in ctrl._debts[0]["consumed_tokens"]
    assert ctrl._debts[0]["remaining_tokens"]
    _closed_sink(graph)
    _edge(graph, "P", "E", "to_entity", "list", "entity")
    assert _relocate(ctrl, graph) == "E"


def test_rd22_zero_normal_action_prevents_immediate_relocate():
    ctrl, graph, _states_obj, _step, _event = _ready()
    assert _relocate(ctrl, graph) == "E"
    assert _relocate(ctrl, graph, sig="E") is None
    assert ctrl.metrics()["residual_frontier_zero_normal_action_suppressed"] >= 1
    assert ctrl.metrics()["residual_frontier_debt_relocations"] == 1
    assert _events(ctrl, "residual_frontier_debt_relocation_failure") == []


def test_rd23_one_normal_action_releases_repeat_eligibility():
    ctrl, graph, _states_obj, step, _event = _ready()
    assert _relocate(ctrl, graph) == "E"
    assert _relocate(ctrl, graph, sig="E") is None
    page = _page("/a", "A", (_el("note", "button", "note"),))
    _go(ctrl, "A", Action("input", "note", "x"), page, page, "A", graph, step + 2)
    assert ctrl._hold is None
    assert _relocate(ctrl, graph) == "E"
    assert ctrl.metrics()["residual_frontier_debt_relocations"] == 2


def _second_debt(ctrl, graph, states, step):
    """A second real escape at a visited hub whose buttons were not drained."""
    graph.add_state("G", "/gate", "Gate", cluster_id="gate")
    graph.add_state("F", "/fresh", "Fresh", cluster_id="fresh")
    graph.add_state("C2", "/c2", "C2", cluster_id="child2")
    gate = _page("/gate", "Gate", (
        _el("g1", "button"), _el("g2", "button"), _el("g3", "button"),
        _el("nav_up", "link", "返回"),
    ))
    fresh = _page("/fresh", "Fresh", (
        _el("f1", "button"), _el("f2", "button"), _el("f3", "button"),
        _el("nav_up", "link", "返回"),
    ))
    child = _page("/c2", "C2", (_el("x", "link"),))
    _go(ctrl, "P", Action("click", "lb"), states["list"], gate,
        "G", graph, step + 1, label="branch")
    _go(ctrl, "G", Action("click", "g1"), gate, fresh, "F", graph, step + 2)
    _go(ctrl, "F", Action("click", "f1"), fresh, child, "C2", graph, step + 3)
    nxt = _burn_return(ctrl, "C2", child, graph, step + 4)
    _go(ctrl, "C2", Action("back"), child, fresh, "F", graph, nxt)
    _chosen, nxt = _drive_until_outer_return(ctrl, "F", fresh, graph, nxt + 1)
    before = len(ctrl._debts)
    ctrl.last_label = "return_hub"
    ctrl.after(
        "F", Action("back"), fresh, gate, "new", [], "G", False, graph, nxt)
    assert len(ctrl._debts) == before + 1
    return nxt


def test_rd24_multiple_debts_choose_oldest_usable():
    ctrl, graph, states, step, _event = _arm_debt()
    _second_debt(ctrl, graph, states, step)
    assert [debt["waypoint_sig"] for debt in ctrl._debts] == ["E", "G"]
    _closed_sink(graph)
    _edge(graph, "P", "E", "to_entity", "list", "entity")
    _edge(graph, "P", "G", "to_gate", "list", "gate")
    assert _relocate(ctrl, graph) == "E"


def test_rd25_unusable_oldest_skips_to_next_debt():
    ctrl, graph, states, step, _event = _arm_debt()
    _second_debt(ctrl, graph, states, step)
    _closed_sink(graph, include=("E",))
    _edge(graph, "P", "G", "to_gate", "list", "gate")
    assert _relocate(ctrl, graph) == "G"
    assert ctrl._debts[0]["skips"][-1]["reason"] == "inside_scc"
    assert ctrl._debts[1]["relocation_count"] == 1
    assert ctrl._debts[0]["relocation_count"] == 0


def test_rd26_same_cluster_variant_can_consume():
    ctrl, graph, _states_obj, step, event = _arm_debt()
    token = next(item for item in event["normalized_residual_tokens"] if item.endswith(":pin"))
    eid = token.split(":")[-1]
    page = _page("/entity-v", "EntityV", (_el(eid, "button"),))
    _go(ctrl, "E2", Action("click", eid), page, page, "E2", graph, step + 1)
    assert token in ctrl._debts[0]["consumed_tokens"]


def test_rd27_wrong_cluster_cannot_consume():
    ctrl, graph, states, step, event = _arm_debt()
    token = event["normalized_residual_tokens"][0]
    eid = token.split(":")[-1]
    before = list(ctrl._debts[0]["remaining_tokens"])
    page = _page("/mid", "Mid", (_el(eid, "button"),))
    _go(ctrl, "M", Action("click", eid), page, page, "M", graph, step + 1)
    assert ctrl._debts[0]["remaining_tokens"] == before
    assert ctrl._debts[0]["consumed_tokens"] == []


def test_rd28_wrong_eid_cannot_consume():
    ctrl, graph, _states_obj, step, event = _arm_debt()
    before = list(event["normalized_residual_tokens"])
    page = _page("/entity", "Entity", (_el("unrelated", "button"),))
    _go(ctrl, "E", Action("click", "unrelated"), page, page, "E", graph, step + 1)
    assert ctrl._debts[0]["remaining_tokens"] == before


def test_rd29_resolution_does_not_increment_return_success():
    ctrl, graph, _states_obj, step, event = _arm_debt("E2", "entity_local")
    success = ctrl.ledger.return_success
    completed = ctrl.ledger.sequences_completed
    started = ctrl.ledger.sequences_started
    eid = event["normalized_residual_tokens"][0].split(":")[-1]
    page = _page("/entity-v", "EntityV", (_el(eid, "button"),))
    _go(ctrl, "E2", Action("click", eid), page, page, "E2", graph, step + 1)
    assert ctrl._debts[0]["status"] == "resolved"
    assert ctrl.ledger.return_success == success
    assert ctrl.ledger.sequences_completed == completed
    assert ctrl.ledger.sequences_started == started
    assert ctrl.metrics()["residual_frontier_false_success_violations"] == 0


def test_rd30_product_default_remains_unchanged():
    text = open(os.path.join(ROOT, "ghostqa", "__main__.py"), encoding="utf-8").read()
    assert 'default="ghost"' in text or "default='ghost'" in text
    assert product_default_changed() is False
    policy = ResidualFrontierDebtGuardGhostPolicy()
    assert policy.name != GhostPolicy.name
    assert policy.use_frontier is False


def test_scc_closure_ignores_crashed_and_back_is_not_pending():
    graph = _graph()
    _closed_sink(graph)
    graph.edges[("A", "click:boom:")] = StateEdge(
        src="A", action_key="click:boom:", dst="CRASHED", count=1,
        action={"type": "click", "target_eid": "boom", "text": None})
    component = observed_scc(graph, "A")
    assert component["closed"] is True
    assert component["size"] == 2
    assert "E" not in component["members"]
    graph.nodes["A"].observed_opps["back"] = {
        "kind": "back", "progress": False, "field_type": "unknown",
    }
    assert component_pending(graph, component["sigs"]) == 0
    assert observed_scc(graph, "missing") is None


def test_actionless_edge_does_not_close_or_open_the_component():
    graph = _graph()
    _closed_sink(graph)
    graph.edges[("A", "click:bare:")] = StateEdge(
        src="A", action_key="click:bare:", dst="Z", count=1, action=None)
    component = observed_scc(graph, "A")
    assert component["closed"] is True
    assert component["outgoing"] == 0
