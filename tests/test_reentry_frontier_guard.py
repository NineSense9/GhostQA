"""R1–R12 and F1–F20 for the v0.3.16 reentry frontier candidate."""
import os

from ghostqa.exploration.horizon_handoff_guard import (
    HorizonHandoffSequenceController, terminal_violations,
)
from ghostqa.exploration.reentry_frontier_guard import (
    ReentryFrontierGuardGhostPolicy, ReentryFrontierSequenceController,
)
from ghostqa.exploration.sequence import BRANCH_HORIZON, branch_key
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState
from benchmark.algorithm_freeze import verify_freeze

try:
    from helpers import make_hub_state, make_seq_el
except ImportError:
    from tests.helpers import make_hub_state, make_seq_el

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SOURCE = os.path.join(ROOT, "ghostqa", "exploration", "reentry_frontier_guard.py")
NEEDLES = (
    "buggy-directory", "buggy-lab", "buggy-forum", "buggy-billing",
    "buggy-crm", "buggy-ops", "buggy-desk", "buggy-wiki", "buggy-shop",
    "buggy-flow", "nav_people", "open_result_from_run", "nav_up_exp",
    "btn_cool", "btn_reopen", "nav_samples", "bug-", "manifest", ".html",
)


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
    graph.add_state("P2", "/hub-v", "HubV", cluster_id="hub")
    graph.add_state("N", "/nested", "Nested", cluster_id="nested")
    graph.add_state("N2", "/nested-v", "NestedV", cluster_id="nested")
    graph.add_state("N4", "/nested-new", "NestedNew", cluster_id="nested")
    graph.add_state("G", "/grand", "Grand", cluster_id="grand")
    graph.add_state("G2", "/grand2", "Grand2", cluster_id="grand2")
    graph.add_state("L", "/leaf", "Leaf", cluster_id="leaf")
    graph.add_state("Q", "/q", "Q", cluster_id="q")
    return graph


def _states():
    return {
        "hub": make_hub_state(),
        "nested": _hub("/nested", "Nested", ("n1", "n2", "n3")),
        "nested_new": _hub("/nested-new", "NestedNew", ("n1", "n2", "n3", "n4")),
        "grand": _hub("/grand", "Grand", ("g1", "g2", "g3")),
        "grand2": _hub("/grand2", "Grand2", ("h1", "h2", "h3")),
        "leaf": _leaf(),
        "q": _leaf("/q", "Q", "q"),
    }


class _Finding:
    def fingerprint(self):
        return "fp-reentry"


def _ctrl():
    return ReentryFrontierSequenceController("structural")


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


def _start(ctrl, graph, states, step=1):
    _go(ctrl, "P", Action("click", "go_a"), states["hub"], states["nested"],
        "N", graph, step)
    return step + 1


def _handoff(ctrl, graph, states):
    step = _start(ctrl, graph, states)
    _go(ctrl, "N", Action("fill", "x"), states["nested"], states["nested"],
        "N", graph, step, relation="identical")
    _go(ctrl, "N", Action("click", "n1"), states["nested"], states["leaf"],
        "L", graph, step + 1)
    return step + 2


def _seal(ctrl, cluster, sig, keep=""):
    rec = ctrl.ledger.hub(sig, cluster)
    for key in list(rec.discovered):
        if keep and key == keep:
            continue
        rec.started.add(key)
        ctrl.struct.branch(cluster, key).attempts += 1


def _ctx(sig, step=1):
    return {"sig": sig, "step_index": step}


def test_r1_exact_early_parent_reentry():
    ctrl = _ctrl()
    graph, states = _graph(), _states()
    _start(ctrl, graph, states)
    assert ctrl.ledger.commitment_left > 0
    assert ctrl.ledger.returning is False
    _go(ctrl, "N", Action("back"), states["nested"], states["hub"], "P", graph, 2)
    early = _events(ctrl, "early_parent_reentry")
    assert len(early) == 1
    assert early[0]["reentry_strength"] == "exact"
    assert len(_terminals(ctrl, "returned")) == 1
    assert ctrl.ledger.return_success == 1
    assert ctrl.ledger.active_branch == ""
    assert ctrl.ledger.commitment_left == 0
    assert ctrl.ledger.returning is False
    assert _events(ctrl, "sequence_horizon_reached") == []
    assert terminal_violations(ctrl.events) == []


def test_r2_cluster_variant_early_parent_reentry():
    ctrl = _ctrl()
    graph, states = _graph(), _states()
    _start(ctrl, graph, states)
    _go(ctrl, "N", Action("back"), states["nested"], states["hub"], "P2", graph, 2)
    early = _events(ctrl, "early_parent_reentry")
    assert len(early) == 1
    assert early[0]["reentry_strength"] == "cluster"
    assert len(_terminals(ctrl, "returned")) == 1
    assert ctrl.ledger.active_branch == ""
    assert terminal_violations(ctrl.events) == []


def test_r3_no_parent_match_does_not_complete():
    ctrl = _ctrl()
    graph, states = _graph(), _states()
    _start(ctrl, graph, states)
    _go(ctrl, "N", Action("click", "x"), states["nested"], states["leaf"],
        "L", graph, 2, relation="identical")
    assert _events(ctrl, "early_parent_reentry") == []
    assert ctrl.ledger.active_branch
    assert _terminals(ctrl, "returned") == []


def test_r4_already_returning_uses_historical_path():
    ctrl = _ctrl()
    graph, states = _graph(), _states()
    _start(ctrl, graph, states)
    _go(ctrl, "N", Action("click", "x"), states["nested"], states["leaf"],
        "L", graph, 2, relation="identical")
    _go(ctrl, "L", Action("click", "x"), states["leaf"], states["leaf"],
        "L", graph, 3, relation="identical")
    assert ctrl.ledger.returning is True
    _go(ctrl, "L", Action("back"), states["leaf"], states["hub"], "P", graph, 4)
    assert _events(ctrl, "early_parent_reentry") == []
    assert len(_terminals(ctrl, "returned")) == 1
    assert ctrl.ledger.active_branch == ""
    assert terminal_violations(ctrl.events) == []


def test_r5_finding_and_parent_has_one_terminal():
    ctrl = _ctrl()
    graph, states = _graph(), _states()
    _start(ctrl, graph, states)
    _go(ctrl, "N", Action("back"), states["nested"], states["hub"], "P", graph, 2,
        findings=[_Finding()])
    assert _events(ctrl, "early_parent_reentry") == []
    assert len(_terminals(ctrl, "finding")) == 1
    assert _terminals(ctrl, "returned") == []
    assert ctrl.ledger.active_branch == ""
    assert terminal_violations(ctrl.events) == []


def test_r6_crash_and_parent_has_one_terminal():
    ctrl = _ctrl()
    graph, states = _graph(), _states()
    _start(ctrl, graph, states)
    _go(ctrl, "N", Action("back"), states["nested"], states["hub"], "P", graph, 2,
        crashed=True)
    assert _events(ctrl, "early_parent_reentry") == []
    assert len(_terminals(ctrl, "crash")) == 1
    assert _terminals(ctrl, "returned") == []
    assert ctrl.ledger.active_branch == ""
    assert terminal_violations(ctrl.events) == []


def test_r7_child_early_reentry_resolves_witness():
    ctrl = _ctrl()
    graph, states = _graph(), _states()
    _handoff(ctrl, graph, states)
    child = ctrl._open_instance["id"]
    _seal(ctrl, "nested", "N", keep=branch_key("nested", Action("click", "n1")))
    _go(ctrl, "L", Action("back"), states["leaf"], states["nested"], "N", graph, 4)
    assert _events(ctrl, "early_parent_reentry")
    assert _events(ctrl, "child_parent_witness")
    assert _events(ctrl, "child_parent_witness")[-1]["child_sequence_instance_id"] == child
    assert ctrl.stack_depth == 0
    assert len(_terminals(ctrl, "returned", child)) == 1
    ctrl.close_open(5, "N", "nested")
    assert terminal_violations(ctrl.events) == []


def test_r8_sibling_after_reentry_is_not_a_handoff():
    ctrl = _ctrl()
    graph, states = _graph(), _states()
    _start(ctrl, graph, states)
    _go(ctrl, "N", Action("back"), states["nested"], states["hub"], "P", graph, 2)
    _go(ctrl, "P", Action("click", "go_b"), states["hub"], states["leaf"], "L", graph, 3)
    assert _events(ctrl, "horizon_handoff_started") == []
    assert _events(ctrl, "source_parent_reentry_repair") == []
    assert len(_events(ctrl, "branch_start")) == 2
    assert len(_terminals(ctrl, "returned")) == 1
    ctrl.close_open(4, "L", "leaf")
    assert terminal_violations(ctrl.events) == []


def test_r9_source_parent_fallback_once():
    ctrl = _ctrl()
    graph, states = _graph(), _states()
    _start(ctrl, graph, states)
    assert ctrl.ledger.active_branch
    _go(ctrl, "P", Action("click", "go_b"), states["hub"], states["leaf"], "L", graph, 2)
    assert len(_events(ctrl, "source_parent_reentry_repair")) == 1
    assert _events(ctrl, "early_parent_reentry") == []
    assert _events(ctrl, "horizon_handoff_started") == []
    assert len(_terminals(ctrl, "returned")) == 1
    assert len(_events(ctrl, "branch_start")) == 2
    ctrl.close_open(3, "L", "leaf")
    assert terminal_violations(ctrl.events) == []


def test_r10_primary_reentry_does_not_also_repair():
    ctrl = _ctrl()
    graph, states = _graph(), _states()
    _start(ctrl, graph, states)
    _go(ctrl, "N", Action("back"), states["nested"], states["hub"], "P", graph, 2)
    assert len(_events(ctrl, "early_parent_reentry")) == 1
    assert _events(ctrl, "source_parent_reentry_repair") == []
    assert len(_terminals(ctrl, "returned")) == 1
    assert ctrl.metrics()["reentry_double_completion_violations"] == 0


def test_r11_reset_clears_reentry_state():
    ctrl = _ctrl()
    graph, states = _graph(), _states()
    _start(ctrl, graph, states)
    _go(ctrl, "N", Action("back"), states["nested"], states["hub"], "P", graph, 2)
    ctrl.reset()
    assert ctrl.events == []
    assert ctrl.ledger.active_branch == ""
    assert ctrl.metrics()["early_parent_reentry_events"] == 0
    assert ctrl.metrics()["source_parent_reentry_repair_events"] == 0
    assert ctrl._lease is None
    assert ctrl._deferred_unemitted == set()


def test_r12_every_instance_has_one_terminal():
    ctrl = _ctrl()
    graph, states = _graph(), _states()
    _start(ctrl, graph, states)
    _go(ctrl, "N", Action("back"), states["nested"], states["hub"], "P", graph, 2)
    _go(ctrl, "P", Action("click", "go_b"), states["hub"], states["leaf"], "L", graph, 3)
    ctrl.close_open(4, "L", "leaf")
    assert len(_events(ctrl, "branch_start")) == 2
    assert terminal_violations(ctrl.events) == []
    assert len(_terminals(ctrl)) == 2


def _lease_ready(ctrl=None):
    ctrl = ctrl or _ctrl()
    graph, states = _graph(), _states()
    _handoff(ctrl, graph, states)
    _go(ctrl, "L", Action("back"), states["leaf"], states["nested"], "N", graph, 4)
    return ctrl, graph, states


def test_f1_empty_frontier_matches_historical_resume():
    graph, states = _graph(), _states()
    historical = HorizonHandoffSequenceController("structural")
    candidate = _ctrl()
    for ctrl in (historical, candidate):
        _handoff(ctrl, graph, states)
    _seal(candidate, "nested", "N", keep=branch_key("nested", Action("click", "n1")))
    leaf = states["leaf"]
    for ctrl in (historical, candidate):
        _go(ctrl, "L", Action("click", "x"), leaf, leaf, "L", graph, 4, relation="identical")
        _go(ctrl, "L", Action("click", "x"), leaf, leaf, "L", graph, 5, relation="identical")
        _go(ctrl, "L", Action("back"), leaf, states["nested"], "N", graph, 6)
    assert candidate.events == historical.events
    assert candidate.ledger.returning is True
    assert candidate.ledger.commitment_left == 0
    assert candidate.stack_depth == 0


def test_f2_nonempty_frontier_grants_one_slot_without_horizon():
    ctrl, _graph_obj, _states_obj = _lease_ready()
    grant = _events(ctrl, "local_frontier_lease_granted")
    assert len(grant) == 1
    assert grant[0]["frontier_count"] >= 1
    assert ctrl.ledger.commitment_left == 1
    assert ctrl.ledger.returning is False
    assert _events(ctrl, "sequence_horizon_reached") == []
    assert ctrl._lease["active"] is True


def test_f3_lease_selects_first_allowed_branch():
    ctrl, graph, states = _lease_ready()
    chosen = ctrl.pick_override(
        [Action("click", "n2"), Action("click", "n3"), Action("back")],
        states["nested"], graph, _ctx("N", 5))
    assert chosen.target_eid == "n2"
    assert ctrl.last_label == "local_frontier_lease"


def test_f4_started_branch_is_not_granted():
    ctrl = _ctrl()
    graph, states = _graph(), _states()
    _handoff(ctrl, graph, states)
    key = branch_key("nested", Action("click", "n2"))
    ctrl.ledger.hub("N", "nested").started.add(key)
    ctrl.struct.branch("nested", key).attempts += 1
    _go(ctrl, "L", Action("back"), states["leaf"], states["nested"], "N", graph, 4)
    granted = set(_events(ctrl, "local_frontier_lease_granted")[-1]["frontier_keys"])
    assert key not in granted
    assert branch_key("nested", Action("click", "n3")) in granted


def test_f5_completed_branch_is_not_granted():
    ctrl = _ctrl()
    graph, states = _graph(), _states()
    _handoff(ctrl, graph, states)
    key = branch_key("nested", Action("click", "n2"))
    ctrl.ledger.hub("N", "nested").completed.add(key)
    _go(ctrl, "L", Action("back"), states["leaf"], states["nested"], "N", graph, 4)
    granted = set(_events(ctrl, "local_frontier_lease_granted")[-1]["frontier_keys"])
    assert key not in granted


def test_f6_lease_action_starts_a_normal_child():
    ctrl, graph, states = _lease_ready()
    action = ctrl.pick_override(
        [Action("click", "n2"), Action("back")], states["nested"], graph, _ctx("N", 5))
    _go(ctrl, "N", action, states["nested"], states["leaf"], "L", graph, 5)
    assert ctrl.stack_depth == 1
    assert _events(ctrl, "horizon_handoff_started")
    assert ctrl.ledger.commitment_left == BRANCH_HORIZON - 1
    assert ctrl._lease["active"] is False
    assert _events(ctrl, "local_frontier_lease_action")[-1]["chosen_branch_key"].endswith("n2")


def test_f7_second_witness_leases_a_different_key():
    ctrl, graph, states = _lease_ready()
    action = ctrl.pick_override(
        [Action("click", "n2"), Action("click", "n3"), Action("back")],
        states["nested"], graph, _ctx("N", 5))
    _go(ctrl, "N", action, states["nested"], states["leaf"], "L", graph, 5)
    _go(ctrl, "L", Action("back"), states["leaf"], states["nested"], "N", graph, 6)
    grants = _events(ctrl, "local_frontier_lease_granted")
    assert len(grants) == 2
    first = set(grants[0]["frontier_keys"])
    second = set(grants[1]["frontier_keys"])
    assert branch_key("nested", Action("click", "n2")) in first
    assert branch_key("nested", Action("click", "n2")) not in second
    assert branch_key("nested", Action("click", "n3")) in second
    assert ctrl.metrics()["frontier_repeated_key_violations"] == 0
    assert ctrl.metrics()["max_frontier_lease_chain"] >= 2


def test_f8_exhausted_lease_resumes_return_once():
    ctrl, graph, states = _lease_ready()
    _seal(ctrl, "nested", "N")
    chosen = ctrl.pick_override(
        [Action("click", "n2"), Action("back")], states["nested"], graph, _ctx("N", 5))
    assert chosen.type == "back"
    assert len(_events(ctrl, "local_frontier_lease_exhausted")) == 1
    horizons = [
        event for event in _events(ctrl, "sequence_horizon_reached")
        if event.get("reason") == "horizon_handoff_resolved"
    ]
    assert len(horizons) == 1
    assert ctrl.ledger.returning is True
    assert ctrl.ledger.commitment_left == 0
    assert ctrl._lease["active"] is False


def test_f9_hidden_frontier_does_not_pick_unrelated_action():
    ctrl, graph, states = _lease_ready()
    chosen = ctrl.pick_override(
        [Action("click", "n9"), Action("back")], states["nested"], graph, _ctx("N", 5))
    assert chosen.type == "back"
    assert _events(ctrl, "local_frontier_lease_action") == []
    assert _events(ctrl, "local_frontier_lease_exhausted_or_hidden")
    assert len(_events(ctrl, "sequence_horizon_reached")) == 1
    assert ctrl.ledger.returning is True


def test_f10_location_lost_cancels_lease():
    ctrl, graph, states = _lease_ready()
    chosen = ctrl.pick_override(
        [Action("click", "go_a"), Action("back")], states["hub"], graph, _ctx("P", 5))
    assert chosen.type == "back"
    assert _events(ctrl, "local_frontier_lease_location_lost")
    assert _events(ctrl, "local_frontier_lease_action") == []
    assert ctrl.ledger.returning is True
    assert ctrl.metrics()["lease_cross_hub_uncancelled"] == 0
    assert len(_events(ctrl, "sequence_horizon_reached")) == 1


def test_f11_same_key_on_a_variant_is_not_released():
    ctrl, graph, states = _lease_ready()
    for eid in ("n3",):
        key = branch_key("nested", Action("click", eid))
        ctrl.ledger.hub("N", "nested").started.add(key)
    action = ctrl.pick_override(
        [Action("click", "n2"), Action("back")], states["nested"], graph, _ctx("N", 5))
    _go(ctrl, "N", action, states["nested"], states["leaf"], "L", graph, 5)
    _go(ctrl, "L", Action("back"), states["leaf"], states["nested"], "N2", graph, 6)
    grants = _events(ctrl, "local_frontier_lease_granted")
    assert len(grants) == 1
    assert ctrl.metrics()["frontier_repeated_key_violations"] == 0
    assert ctrl.ledger.returning is True


def test_f12_new_variant_key_can_enter_frontier_once():
    ctrl = _ctrl()
    graph, states = _graph(), _states()
    _handoff(ctrl, graph, states)
    _go(ctrl, "L", Action("back"), states["leaf"], states["nested_new"], "N4", graph, 4)
    assert ctrl.metrics()["frontier_new_keys_from_variant"] >= 1
    granted = set(_events(ctrl, "local_frontier_lease_granted")[-1]["frontier_keys"])
    assert branch_key("nested", Action("click", "n4")) in granted
    assert ctrl.metrics()["frontier_monotonicity_violations"] == 0


def test_f13_child_escape_does_not_renew_lease():
    ctrl, graph, states = _lease_ready()
    action = ctrl.pick_override(
        [Action("click", "n2"), Action("back")], states["nested"], graph, _ctx("N", 5))
    _go(ctrl, "N", action, states["nested"], states["leaf"], "L", graph, 5)
    leaf = states["leaf"]
    _go(ctrl, "L", Action("click", "x"), leaf, leaf, "L", graph, 6, relation="identical")
    _go(ctrl, "L", Action("click", "x"), leaf, states["q"], "Q", graph, 7, relation="new")
    _go(ctrl, "Q", Action("click", "q"), states["q"], states["q"], "Q", graph, 8,
        relation="identical")
    assert len(_events(ctrl, "local_frontier_lease_granted")) == 1
    assert _events(ctrl, "horizon_handoff_unwind")
    assert ctrl._lease["active"] is False
    assert ctrl.stack_depth == 0
    escaped = ctrl._stack
    assert escaped == []
    assert _terminals(ctrl, "returned")
    assert any(event.get("outcome") == "return_cycle_abandoned" for event in _terminals(ctrl))
    assert ctrl.metrics()["frontier_repeated_key_violations"] == 0
    assert terminal_violations(ctrl.events) == []


def test_f14_recursive_handoff_stays_lifo():
    ctrl = _ctrl()
    graph, states = _graph(), _states()
    _go(ctrl, "P", Action("click", "go_a"), states["hub"], states["nested"], "N", graph, 1)
    _go(ctrl, "N", Action("fill", "x"), states["nested"], states["nested"],
        "N", graph, 2, relation="identical")
    _go(ctrl, "N", Action("click", "n1"), states["nested"], states["grand"], "G", graph, 3)
    outer = ctrl._stack[0].open_instance["id"]
    _go(ctrl, "G", Action("click", "g1"), states["grand"], states["grand2"], "G2", graph, 4)
    _go(ctrl, "G2", Action("click", "h1"), states["grand2"], states["leaf"], "L", graph, 5)
    assert ctrl.stack_depth == 2
    grandchild = ctrl._open_instance["id"]
    _go(ctrl, "L", Action("back"), states["leaf"], states["grand2"], "G2", graph, 6)
    assert ctrl.stack_depth == 1
    assert ctrl._stack[0].open_instance["id"] == outer
    assert ctrl._lease["active"] is True
    assert ctrl._lease["hub_cluster"] == "grand2"
    assert _events(ctrl, "child_parent_witness")[-1]["child_sequence_instance_id"] == grandchild
    assert _events(ctrl, "parent_frame_resume_to_return") == []
    assert len(_terminals(ctrl, "returned", grandchild)) == 1


def test_f15_finding_witness_can_lease_without_a_second_terminal():
    ctrl = _ctrl()
    graph, states = _graph(), _states()
    _handoff(ctrl, graph, states)
    child = ctrl._open_instance["id"]
    _go(ctrl, "L", Action("back"), states["leaf"], states["nested"], "N", graph, 4,
        findings=[_Finding()])
    assert len(_terminals(ctrl, "finding", child)) == 1
    assert _terminals(ctrl, "returned", child) == []
    assert _events(ctrl, "local_frontier_lease_granted")
    ctrl.close_open(5, "N", "nested")
    assert terminal_violations(ctrl.events) == []


def test_f16_crash_witness_can_lease_without_a_second_terminal():
    ctrl = _ctrl()
    graph, states = _graph(), _states()
    _handoff(ctrl, graph, states)
    child = ctrl._open_instance["id"]
    _go(ctrl, "L", Action("back"), states["leaf"], states["nested"], "N", graph, 4,
        crashed=True)
    assert len(_terminals(ctrl, "crash", child)) == 1
    assert _terminals(ctrl, "returned", child) == []
    assert _events(ctrl, "local_frontier_lease_granted")
    ctrl.close_open(5, "N", "nested")
    assert terminal_violations(ctrl.events) == []


def test_f17_budget_end_accounts_for_lease_without_a_fake_terminal():
    ctrl = _ctrl()
    graph, states = _graph(), _states()
    _go(ctrl, "P", Action("click", "go_a"), states["hub"], states["nested"], "N", graph, 1)
    _go(ctrl, "N", Action("fill", "x"), states["nested"], states["nested"],
        "N", graph, 2, relation="identical")
    _go(ctrl, "N", Action("click", "n1"), states["nested"], states["grand"], "G", graph, 3)
    _go(ctrl, "G", Action("click", "g1"), states["grand"], states["grand2"], "G2", graph, 4)
    _go(ctrl, "G2", Action("click", "h1"), states["grand2"], states["leaf"], "L", graph, 5)
    _go(ctrl, "L", Action("back"), states["leaf"], states["grand2"], "G2", graph, 6)
    assert ctrl._lease["active"] is True
    before = len(_events(ctrl, "branch_start"))
    ctrl.close_open(7, "G2", "grand2")
    metrics = ctrl.metrics()
    assert metrics["frontier_lease_active_at_budget_end"] is True
    assert metrics["frontier_lease_remaining_keys_at_budget_end"] >= 1
    assert len(_events(ctrl, "branch_start")) == before
    assert terminal_violations(ctrl.events) == []


def test_f18_reset_clears_lease():
    ctrl, _graph_obj, _states_obj = _lease_ready()
    assert ctrl._lease["active"] is True
    ctrl.reset()
    assert ctrl._lease is None
    assert ctrl.events == []
    assert ctrl.metrics()["local_frontier_lease_granted_events"] == 0
    assert ctrl.metrics()["frontier_lease_active_at_budget_end"] is False


def test_f19_no_frontier_matches_historical_events():
    test_f1_empty_frontier_matches_historical_resume()


def test_f20_lease_starts_do_not_increase_known_frontier():
    ctrl, graph, states = _lease_ready()
    first = _events(ctrl, "local_frontier_lease_granted")[-1]["frontier_count"]
    action = ctrl.pick_override(
        [Action("click", "n2"), Action("click", "n3"), Action("back")],
        states["nested"], graph, _ctx("N", 5))
    _go(ctrl, "N", action, states["nested"], states["leaf"], "L", graph, 5)
    _go(ctrl, "L", Action("back"), states["leaf"], states["nested"], "N", graph, 6)
    second = _events(ctrl, "local_frontier_lease_granted")[-1]["frontier_count"]
    assert second < first
    assert ctrl.metrics()["frontier_monotonicity_violations"] == 0


def test_policy_identity_and_source_isolation():
    policy = ReentryFrontierGuardGhostPolicy(llm=None)
    assert policy.name == "ghost-structural-reentry-frontier-guard"
    assert policy.sequence_mode == "structural"
    text = open(SOURCE, encoding="utf-8").read().lower()
    assert [needle for needle in NEEDLES if needle in text] == []
    assert verify_freeze(os.path.join(
        ROOT, "experiments", "frozen", "ghost-horizon-handoff-v0.3.14", "freeze.json")) == []
