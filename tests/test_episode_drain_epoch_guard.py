"""EE1–EE28 and source isolation for episode-scoped drain revalidation."""
import json
import os

from ghostqa.exploration.episode_drain_epoch_guard import (
    EpisodeDrainEpochGuardGhostPolicy,
    EpisodeDrainEpochSequenceController,
)
from ghostqa.exploration.policy import GhostPolicy
from ghostqa.exploration.residual_frontier_debt_guard import (
    ResidualFrontierDebtSequenceController,
)
from ghostqa.state.models import Action
from benchmark.algorithm_freeze import sha256_file
from benchmark.episode_drain_epoch_analysis import derive_v0324_outcome, passing_facts
from benchmark.episode_drain_epoch_audit import build_audit
from benchmark.fresh_composite_analysis import product_default_changed
from tests.test_local_action_drain_guard import (
    _Finding,
    _events as _drain_events,
    _go as _drain_go,
    _promote,
    _ready as _drain_ready,
)
from tests.test_residual_frontier_debt_guard import (
    _arm,
    _closed_sink,
    _edge,
    _el,
    _escape,
    _go,
    _page,
)
from tests.test_return_entry_drain_guard import (
    _enter,
    _events as _return_events,
    _go as _return_go,
)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SOURCE = os.path.join(ROOT, "ghostqa", "exploration", "episode_drain_epoch_guard.py")
PROTOCOL = os.path.join(ROOT, "experiments", "validation", "v0.3.24", "protocol.json")
AUDIT = os.path.join(ROOT, "experiments", "validation", "v0.3.24", "v0323-episode-drain-audit.json")
DEBT_FREEZE = os.path.join(
    ROOT, "experiments", "frozen", "ghost-residual-frontier-debt-v0.3.23", "freeze.json")
NEEDLES = (
    "buggy-campus", "buggy-studio", "buggy-warehouse", "buggy-booking",
    "deepbench", "BUG-", "btn_staff_note", "btn_variant", "open_mid_b",
    "lesson.html", "asset.html", "warehouse.html", "booking", "campus", "studio",
)


def _ctrl():
    return EpisodeDrainEpochSequenceController("structural")


def _events(ctrl, name):
    return [event for event in ctrl.events if event.get("event") == name]


def _ready():
    ctrl = _ctrl()
    ctrl, graph, states, step = _arm(ctrl)
    created = _escape(ctrl, graph, states, step, "E", "entity")
    assert created
    _closed_sink(graph)
    _edge(graph, "P", "E", "to_target", "list", graph.nodes["E"].cluster_id)
    return ctrl, graph, states, step, created[-1]


def _relocate(ctrl, graph, sig="A", budget=40, step_index=0):
    policy = EpisodeDrainEpochGuardGhostPolicy()
    policy.sequence = ctrl
    return policy.maybe_relocate(graph, None, [], {
        "sig": sig, "step_index": step_index, "budget": budget,
    })


def _ctx(sig, step=5, restore=False):
    ctx = {"sig": sig, "step_index": step}
    if restore:
        ctx["restore_step"] = True
    return ctx


def _stamp_same_hub(ctrl, graph, cluster="nested", eid="b1", step=5):
    key = f"{cluster}:button:{eid}"
    state = _page("/nested", "Nested", (_el(eid, "button"), _el("keep", "button")))
    graph.add_state("N", "/nested", "Nested", cluster_id=cluster)
    ctrl._drain = {
        "active": True,
        "paused": False,
        "hub_cluster": cluster,
        "hub_sig": "N",
        "epoch_keys": [],
        "current_sig": "N",
        "current_state": state,
        "step": step,
        "frame": None,
        "promoted_child_id": "",
        "seen_keys": [],
    }
    ctrl._pending_probe = None
    ctrl._complete_same_hub(
        {"key": key, "eid": eid, "role": "button", "hub_cluster": cluster},
        "N", Action("click", eid), state, state, "identical", [],
        "N", graph, step, cluster, cluster)
    ctrl._drain = None
    ctrl._pending_probe = None
    return key


def test_ee1_same_hub_local_probe_records_episode_key():
    ctrl, graph, states = _drain_ready(_ctrl())
    action = ctrl.pick_override(
        [Action("click", "b1"), Action("click", "b2")],
        states["nested"], graph, _ctx("N"))
    _drain_go(ctrl, "N", action, states["nested"], states["nested"], "N", graph, 5,
              relation="identical")
    assert ("nested", "nested:button:b1") in ctrl._episode_same_hub_keys
    assert _events(ctrl, "local_drain_same_hub_key_recorded")[-1]["trigger"] == "local_action"
    assert ctrl.metrics()["local_drain_same_hub_keys_recorded"] == 1
    assert ctrl.interaction_episode == 0


def test_ee2_same_hub_return_entry_records_episode_key():
    ctrl, graph, states = _enter(ctrl=_ctrl(), findings=[_Finding()])
    action = ctrl.pick_override(
        [Action("click", "b1"), Action("click", "b2")],
        states["buttons"], graph, _ctx("N", 2))
    _return_go(ctrl, "N", action, states["buttons"], states["buttons"], "N", graph, 2,
               relation="identical")
    assert ("nested", "nested:button:b1") in ctrl._episode_same_hub_keys
    recorded = _events(ctrl, "local_drain_same_hub_key_recorded")[-1]
    assert recorded["trigger"] == "return_entry"
    assert _return_events(ctrl, "return_entry_probe_completed")


def test_ee3_promoted_cross_hub_is_not_episode_invalidatable():
    ctrl, graph, states = _drain_ready(_ctrl())
    _promote(ctrl, graph, states)
    assert ("nested", "nested:button:b1") not in ctrl._episode_same_hub_keys
    _drain_go(ctrl, "L", Action("back"), states["leaf"], states["nested"], "N", graph, 6)
    identity = ("nested", "nested:button:b1")
    assert "nested:button:b1" in ctrl._drained_by_cluster["nested"]
    assert identity not in ctrl._episode_same_hub_keys
    assert identity in ctrl._cross_hub_keys
    assert ctrl.metrics()["local_drain_cross_hub_keys_preserved"] == 1


def test_ee4_return_entry_left_hub_is_not_episode_invalidatable():
    ctrl, graph, states = _enter(ctrl=_ctrl(), findings=[_Finding()])
    action = ctrl.pick_override(
        [Action("click", "b1")], states["buttons"], graph, _ctx("N", 2))
    _return_go(ctrl, "N", action, states["buttons"], states["leaf"], "L", graph, 2)
    identity = ("nested", "nested:button:b1")
    assert _return_events(ctrl, "return_entry_probe_left_hub")
    assert "nested:button:b1" in ctrl._drained_by_cluster["nested"]
    assert identity not in ctrl._episode_same_hub_keys
    assert identity in ctrl._cross_hub_keys


def test_ee5_suppressed_relocate_does_not_advance():
    ctrl, graph, _states, _step, _event = _ready()
    ctrl.ledger.returning = True
    assert _relocate(ctrl, graph) is None
    assert ctrl.interaction_episode == 0
    assert ctrl.metrics()["local_drain_episode_advances"] == 0
    assert _events(ctrl, "local_drain_episode_advanced") == []


def test_ee6_valid_relocate_advances_once():
    ctrl, graph, _states, _step, _event = _ready()
    assert _relocate(ctrl, graph) == "E"
    assert ctrl.interaction_episode == 1
    assert ctrl.metrics()["local_drain_episode_advances"] == 1
    assert ctrl.metrics()["residual_frontier_debt_relocations"] == 1
    advanced = _events(ctrl, "local_drain_episode_advanced")
    assert len(advanced) == 1
    assert advanced[0]["reason"] == "residual_frontier_debt_relocation"
    assert advanced[0]["old_episode"] == 0
    assert advanced[0]["new_episode"] == 1
    assert _relocate(ctrl, graph) is None
    assert ctrl.interaction_episode == 1


def test_ee7_and_ee8_advance_removes_only_same_hub_keys():
    ctrl, graph, _states, _step, _event = _ready()
    inherited = len(ctrl._episode_same_hub_keys)
    same = _stamp_same_hub(ctrl, graph)
    ctrl._drained_by_cluster.setdefault("other", set()).add("other:button:kept")
    ctrl._cross_hub_keys.add(("other", "other:button:kept"))
    assert _relocate(ctrl, graph) == "E"
    assert same not in ctrl._drained_by_cluster.get("nested", set())
    assert "other:button:kept" in ctrl._drained_by_cluster["other"]
    advanced = _events(ctrl, "local_drain_episode_advanced")[-1]
    assert advanced["invalidated_same_hub_key_count"] == inherited + 1
    assert advanced["preserved_drained_key_count"] == 1
    assert ctrl.metrics()["local_drain_cross_hub_invalidation_violations"] == 0


def test_ee9_ee10_ee11_structural_memory_survives_advance():
    ctrl, graph, _states, _step, _event = _ready()
    before = ctrl._structural_view()
    assert _relocate(ctrl, graph) == "E"
    after = ctrl._structural_view()
    assert after[0] == before[0]
    assert after[1] == before[1]
    assert after[2] == before[2]
    assert after[3] == before[3]
    assert after[4] == before[4]
    assert after[6][0][1] == before[6][0][1]
    assert after[6][0][2] == before[6][0][2]
    assert ctrl.metrics()["local_drain_episode_false_success_violations"] == 0
    assert ctrl.ledger.return_success == before[0]


def test_ee12_restore_context_creates_no_local_probe():
    ctrl, graph, states = _drain_ready(_ctrl())
    before = len(ctrl.events)
    chosen = ctrl._select_local(
        [Action("click", "b1")], states["nested"], graph, _ctx("N", 5, restore=True), "N")
    assert chosen is None
    assert _drain_events(ctrl, "local_action_probe_selected") == []
    assert len([event for event in ctrl.events[before:] if event.get("event") == "local_action_probe_selected"]) == 0
    assert ctrl.metrics()["local_drain_restore_probe_violations"] == 1
    ctrl.observe_restore_action("N", Action("click", "b1"), graph, 5)
    assert ctrl.metrics()["local_drain_episode_false_success_violations"] == 0


def test_ee13_arrival_alone_creates_no_local_probe():
    ctrl = _ctrl()
    graph_states = __import__(
        "tests.test_local_action_drain_guard", fromlist=["_graph", "_states"])
    graph, states = graph_states._graph(), graph_states._states()
    _drain_go(ctrl, "P", Action("click", "go_a"), states["hub"], states["nested"], "N", graph, 1)
    assert _events(ctrl, "local_action_drain_started") == []
    assert _events(ctrl, "local_action_probe_selected") == []
    assert ctrl.metrics()["local_drain_revalidated_probe_count"] == 0


def test_ee14_later_witness_can_reprobe_invalidated_key():
    ctrl, graph, states = _drain_ready(_ctrl())
    ctrl.interaction_episode = 1
    ctrl._invalidated[("nested", "nested:button:b1")] = {"original_episode": 0}
    action = ctrl.pick_override(
        [Action("click", "b1"), Action("click", "b2")],
        states["nested"], graph, _ctx("N", 5))
    assert action.target_eid == "b1"
    event = _events(ctrl, "local_drain_key_revalidated")[-1]
    assert event["original_episode"] == 0
    assert event["current_episode"] == 1
    assert event["trigger"] == "local_action_drain"
    assert event["key"] == "nested:button:b1"
    assert ctrl.metrics()["local_drain_revalidated_probe_count"] == 1


def test_ee15_same_episode_reprobe_is_suppressed():
    ctrl, graph, states = _drain_ready(_ctrl())
    action = ctrl.pick_override(
        [Action("click", "b1")], states["nested"], graph, _ctx("N", 5))
    _drain_go(ctrl, "N", action, states["nested"], states["nested"], "N", graph, 5,
              relation="identical")
    again = ctrl.pick_override(
        [Action("click", "b1"), Action("click", "b2")],
        states["nested"], graph, _ctx("N", 6))
    assert again is None or again.target_eid != "b1"
    selected = [event.get("eid") for event in _events(ctrl, "local_action_probe_selected")]
    assert selected.count("b1") == 1
    assert ctrl.metrics()["local_drain_duplicate_same_episode_violations"] == 0


def test_ee16_and_ee17_second_relocation_invalidates_only_current_keys():
    ctrl, graph, _states, step, _event = _ready()
    inherited = len(ctrl._episode_same_hub_keys)
    first = _stamp_same_hub(ctrl, graph, eid="b1")
    assert _relocate(ctrl, graph) == "E"
    assert ctrl.metrics()["local_drain_same_hub_keys_invalidated"] == inherited + 1
    page = _page("/a", "A", (_el("note", "button", "note"),))
    _go(ctrl, "A", Action("input", "note"), page, page, "A", graph, step + 2)
    assert ctrl._hold is None
    second = _stamp_same_hub(ctrl, graph, eid="b2", step=step + 3)
    assert first not in ctrl._drained_by_cluster.get("nested", set())
    before_second = ctrl.metrics()["local_drain_same_hub_keys_invalidated"]
    assert _relocate(ctrl, graph) == "E"
    assert ctrl.interaction_episode == 2
    assert second not in ctrl._drained_by_cluster.get("nested", set())
    assert ctrl.metrics()["local_drain_same_hub_keys_invalidated"] == before_second + 1
    assert ctrl.metrics()["local_drain_episode_advances"] == 2


def test_ee18_restore_failure_does_not_fake_success():
    ctrl, graph, _states, _step, _event = _ready()
    key = _stamp_same_hub(ctrl, graph)
    success = ctrl.ledger.return_success
    assert _relocate(ctrl, graph) == "E"
    assert _relocate(ctrl, graph, sig="A") is None
    assert ctrl.interaction_episode == 1
    assert key not in ctrl._drained_by_cluster.get("nested", set())
    assert ctrl.ledger.return_success == success
    assert ctrl._debts[0]["status"] == "unresolved"
    assert _events(ctrl, "residual_frontier_debt_relocation_failure")
    assert ctrl.metrics()["local_drain_episode_false_success_violations"] == 0
    assert ctrl.metrics()["local_drain_episode_advances"] == 1


def test_ee19_new_run_reset_clears_epoch_state():
    ctrl, graph, _states, _step, _event = _ready()
    _stamp_same_hub(ctrl, graph)
    policy = EpisodeDrainEpochGuardGhostPolicy()
    policy.sequence = ctrl
    assert _relocate(ctrl, graph) == "E"
    policy.reset()
    assert policy.sequence.interaction_episode == 0
    assert policy.sequence._episode_same_hub_keys == set()
    assert policy.sequence._invalidated == {}
    assert policy.sequence._cross_hub_keys == set()
    assert policy.sequence._drained_by_cluster == {}
    assert policy.sequence._debts == []
    assert policy.sequence.metrics()["local_drain_episode_advances"] == 0


def test_ee20_without_relocation_dedupe_matches_v0323():
    episode, graph, states = _drain_ready(_ctrl())
    historical = ResidualFrontierDebtSequenceController("structural")
    historical, _graph, _states = _drain_ready(historical)
    for ctrl, step in ((episode, 5), (historical, 5)):
        action = ctrl.pick_override(
            [Action("click", "b1"), Action("click", "b2")],
            states["nested"], graph, _ctx("N", step))
        ctrl.after(
            "N", action, states["nested"], states["nested"], "identical", [],
            "N", False, graph, step)
    assert episode._drained_by_cluster == historical._drained_by_cluster
    assert episode.interaction_episode == 0
    assert episode.metrics()["local_drain_episode_advances"] == 0
    assert episode.metrics()["local_drain_revalidated_probe_count"] == 0


def test_ee21_active_lifecycle_cannot_advance_episode():
    ctrl, graph, _states, _step, _event = _ready()
    ctrl._open_instance = {"id": "seq-open", "branch": "b", "len": 1}
    assert _relocate(ctrl, graph) is None
    assert ctrl.interaction_episode == 0
    ctrl._open_instance = None
    ctrl.ledger.returning = True
    assert _relocate(ctrl, graph) is None
    assert ctrl.metrics()["local_drain_episode_advances"] == 0


def test_ee22_zero_same_hub_keys_advances_with_zero_invalidation():
    ctrl, graph, _states, _step, _event = _ready()
    ctrl._episode_same_hub_keys.clear()
    ctrl._episode_completed.clear()
    ctrl._same_hub_origin.clear()
    ctrl._drained_by_cluster.clear()
    assert _relocate(ctrl, graph) == "E"
    event = _events(ctrl, "local_drain_episode_advanced")[-1]
    assert event["invalidated_same_hub_key_count"] == 0
    assert ctrl.metrics()["local_drain_same_hub_keys_invalidated"] == 0
    assert ctrl.interaction_episode == 1


def test_ee23_absent_key_is_not_double_counted():
    ctrl, graph, _states, _step, _event = _ready()
    present = set(ctrl._episode_same_hub_keys)
    absent = ("missing", "missing:button:gone")
    ctrl._episode_same_hub_keys.add(absent)
    ctrl._same_hub_origin[absent] = 0
    assert _relocate(ctrl, graph) == "E"
    event = _events(ctrl, "local_drain_episode_advanced")[-1]
    invalidated = {(item["cluster"], item["key"]) for item in event["invalidated_keys"]}
    assert absent not in invalidated
    assert invalidated == present
    assert event["invalidated_same_hub_key_count"] == len(present)


def test_ee24_distinct_revealed_eid_is_a_separate_key():
    ctrl, graph, states = _drain_ready(_ctrl())
    first = ctrl.pick_override(
        [Action("click", "b1")], states["nested"], graph, _ctx("N", 5))
    _drain_go(ctrl, "N", first, states["nested"], states["nested_reveal"], "N", graph, 5,
              relation="similar")
    third_ready = ctrl.pick_override(
        [Action("click", "b1"), Action("click", "b2"), Action("click", "b3")],
        states["nested_reveal"], graph, _ctx("N", 6))
    assert third_ready.target_eid == "b2"
    _drain_go(ctrl, "N", third_ready, states["nested_reveal"], states["nested_reveal"],
              "N", graph, 6, relation="identical")
    revealed = ctrl.pick_override(
        [Action("click", "b3"), Action("click", "b1")],
        states["nested_reveal"], graph, _ctx("N", 7))
    assert revealed.target_eid == "b3"
    _drain_go(ctrl, "N", revealed, states["nested_reveal"], states["nested_reveal"],
              "N", graph, 7, relation="identical")
    assert ("nested", "nested:button:b1") in ctrl._episode_same_hub_keys
    assert ("nested", "nested:button:b3") in ctrl._episode_same_hub_keys
    assert ctrl.metrics()["local_drain_duplicate_same_episode_violations"] == 0


def test_ee25_cluster_variant_shares_the_episode_key():
    ctrl, graph, states = _drain_ready(_ctrl())
    action = ctrl.pick_override(
        [Action("click", "b1")], states["nested"], graph, _ctx("N", 5))
    _drain_go(ctrl, "N", action, states["nested"], states["nested_v"], "N2", graph, 5,
              relation="similar")
    assert ("nested", "nested:button:b1") in ctrl._episode_same_hub_keys
    nxt = ctrl.pick_override(
        [Action("click", "b1"), Action("click", "b2")],
        states["nested_v"], graph, _ctx("N2", 6))
    assert nxt.target_eid == "b2"
    assert ctrl.metrics()["local_drain_same_hub_keys_recorded"] == 1


def test_ee26_finding_on_revalidated_probe_does_not_duplicate_terminal():
    ctrl, graph, states = _drain_ready(_ctrl())
    ctrl.interaction_episode = 1
    ctrl._invalidated[("nested", "nested:button:b1")] = {"original_episode": 0}
    action = ctrl.pick_override(
        [Action("click", "b1")], states["nested"], graph, _ctx("N", 5))
    terminals = len(_events(ctrl, "sequence_terminal"))
    _drain_go(
        ctrl, "N", action, states["nested"], states["nested"], "N", graph, 5,
        relation="identical", findings=[_Finding()])
    assert _events(ctrl, "local_action_probe_finding")
    assert len(_events(ctrl, "sequence_terminal")) == terminals
    assert ctrl.metrics()["local_drain_revalidated_probe_count"] == 1


def test_ee27_revalidated_probe_promotes_only_under_historical_semantics():
    ctrl, graph, states = _drain_ready(_ctrl())
    historical, _graph, _states = _drain_ready(ResidualFrontierDebtSequenceController("structural"))
    ctrl.interaction_episode = 1
    ctrl._invalidated[("nested", "nested:button:b1")] = {"original_episode": 0}
    for candidate in (ctrl, historical):
        action = candidate.pick_override(
            [Action("click", "b1"), Action("click", "l1")],
            states["nested"], graph, _ctx("N", 5))
        candidate.after(
            "N", action, states["nested"], states["leaf"], "new", [],
            "L", False, graph, 5)
    assert _events(ctrl, "local_action_promoted_to_child")
    assert _events(historical, "local_action_promoted_to_child")
    assert ("nested", "nested:button:b1") not in ctrl._episode_same_hub_keys
    assert ctrl.metrics()["local_drain_revalidated_probe_count"] == 1


def test_ee28_episode_advance_does_not_change_product_default():
    ctrl, graph, _states, _step, _event = _ready()
    assert _relocate(ctrl, graph) == "E"
    policy = EpisodeDrainEpochGuardGhostPolicy()
    bare = GhostPolicy(llm=None)
    assert policy.name != bare.name
    assert bare.sequence_mode == "off"
    assert bare.use_frontier is False
    assert product_default_changed() is False
    assert "select" not in EpisodeDrainEpochGuardGhostPolicy.__dict__


def test_source_isolation_and_audit_hash():
    text = open(SOURCE, encoding="utf-8").read()
    for needle in NEEDLES:
        assert needle not in text, needle
    protocol = json.load(open(PROTOCOL, encoding="utf-8"))
    assert protocol["executed"] is False
    assert protocol["product_default_changed"] is False
    assert sha256_file(AUDIT) == protocol["v0_3_23_audit"]["sha256"]
    assert build_audit() == json.load(open(AUDIT, encoding="utf-8"))
    freeze = json.load(open(DEBT_FREEZE, encoding="utf-8"))
    recorded = freeze["files"]["ghostqa/exploration/residual_frontier_debt_guard.py"]["sha256"]
    assert sha256_file(os.path.join(
        ROOT, "ghostqa", "exploration", "residual_frontier_debt_guard.py")) == recorded
    assert recorded == "20b9a2f775e32fd70b3959ce3202ce8110783c6e3f5ddceb535badf31a6c2bff"


def test_outcome_order_is_c_then_d_then_b_then_a():
    assert derive_v0324_outcome()["outcome"] == "A"
    assert derive_v0324_outcome(product_default_changed=True)["outcome"] == "C"
    assert derive_v0324_outcome(episode_without_relocation=1)["outcome"] == "C"
    assert derive_v0324_outcome(cross_hub_invalidations=1)["outcome"] == "C"
    assert derive_v0324_outcome(guard_bug_loss=["BUG-X"])["outcome"] == "C"
    assert derive_v0324_outcome(catalog_episode_advances=1)["outcome"] == "C"
    assert derive_v0324_outcome(model_invariant_failures=1)["outcome"] == "C"
    assert derive_v0324_outcome(new_drain_trigger=True)["outcome"] == "C"
    quiet = passing_facts()
    quiet.update({
        "campus_engaged": False,
        "studio_engaged": False,
        "campus_mechanism": False,
        "studio_mechanism": False,
        "campus_589": False,
        "studio_589": False,
    })
    assert derive_v0324_outcome(**quiet)["outcome"] == "D"
    partial = passing_facts()
    partial.update({"studio_mechanism": False, "studio_589": False, "studio_engaged": True})
    assert derive_v0324_outcome(**partial)["outcome"] == "B"
    one_side = passing_facts()
    one_side.update({
        "studio_engaged": False,
        "studio_mechanism": False,
        "studio_589": False,
    })
    assert derive_v0324_outcome(**one_side)["outcome"] == "B"
