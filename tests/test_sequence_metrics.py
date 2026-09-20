"""v0.3.5.1 canonical sequence metrics. Must not change action traces."""
from ghostqa.agent.gateway import NullLLM
from ghostqa.executor.sim import SimExecutor
from ghostqa.exploration.explorer import run_exploration
from ghostqa.exploration.policy import GhostPolicy
from ghostqa.exploration.sequence import (
    SequenceController, canonical_sequence_metrics, is_hub, branch_key,
)
from ghostqa.oracle.engine import OracleEngine
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState, UIElement
from tests.test_sequence import _seq_app, _hub_state, _el


def test_two_variants_one_canonical_hub():
    ctrl = SequenceController("sequence")
    g = StateGraph()
    g.add_state("h:a", "/hub", "Hub", cluster_id="hub", variant_key="a")
    g.add_state("h:b", "/hub", "Hub", cluster_id="hub", variant_key="b")
    hub = _hub_state()
    ctrl.after("h:a", Action("click", "go_a"), hub, hub, "new", [], "x", False, g, 1)
    ctrl.after("h:b", Action("click", "go_b"), hub, hub, "new", [], "y", False, g, 2)
    m = canonical_sequence_metrics(ctrl.events)
    assert m["hub_variant_count"] == 2
    assert m["canonical_hub_count"] == 1


def test_same_branch_across_variants_is_one_unique():
    ctrl = SequenceController("sequence")
    g = StateGraph()
    g.add_state("h:a", "/hub", "Hub", cluster_id="hub")
    g.add_state("h:b", "/hub", "Hub", cluster_id="hub")
    hub = _hub_state()
    a = Action("click", "go_a")
    ctrl.after("h:a", a, hub, hub, "new", [], "x", False, g, 1)
    ctrl.after("h:b", a, hub, hub, "new", [], "y", False, g, 2)
    m = canonical_sequence_metrics(ctrl.events)
    assert m["unique_branches_started"] == 1
    assert m["branch_start_events"] == 2
    assert m["sequence_instances_started"] == 2


def test_return_completes_one_instance_once():
    ctrl = SequenceController("sequence")
    g = StateGraph()
    g.add_state("h", "/hub", "Hub", cluster_id="hub")
    g.add_state("a", "/a", "A", cluster_id="a")
    hub = _hub_state()
    leaf = GUIState(app="t", url="/a", title="A",
                    elements=(_el("x", "x"),), obs={})
    ctrl.after("h", Action("click", "go_a"), hub, leaf, "new", [], "a", False, g, 1)
    ctrl.ledger.returning = True
    ctrl.last_label = "return_hub"
    ctrl.after("a", Action("back"), leaf, hub, "identical", [], "h", False, g, 2)
    m = canonical_sequence_metrics(ctrl.events)
    assert m["sequence_instances_returned"] == 1
    assert m["sequence_instances_started"] == 1
    terminals = [e for e in ctrl.events if e["event"] == "sequence_terminal"]
    assert len(terminals) == 1
    assert terminals[0]["outcome"] == "returned"


def test_budget_end_is_open_not_completed():
    ctrl = SequenceController("sequence")
    g = StateGraph()
    g.add_state("h", "/hub", "Hub", cluster_id="hub")
    hub = _hub_state()
    ctrl.after("h", Action("click", "go_a"), hub, hub, "new", [], "a", False, g, 1)
    ctrl.close_open(step=40, sig="a", cluster="a")
    m = canonical_sequence_metrics(ctrl.events)
    assert m["sequence_budget_ended"] == 1
    assert m["sequence_instances_returned"] == 0


def test_canonical_metrics_do_not_change_action_trace():
    def _keys():
        r = run_exploration(
            SimExecutor(_seq_app()),
            GhostPolicy(NullLLM(), use_frontier=False, sequence_mode="sequence"),
            budget=16, oracle=OracleEngine())
        return [s.action.key() for s in r.steps], r.sequence_metrics

    k1, m1 = _keys()
    k2, m2 = _keys()
    assert k1 == k2
    assert m1.get("canonical_hub_count") is not None
    assert m1.get("hub_variant_count") is not None


def test_policy_does_not_read_events():
    src = open(__import__("ghostqa.exploration.sequence", fromlist=["x"]).__file__,
               encoding="utf-8").read()
    # score_bonus / pick_override must not mention self.events
    bonus = src.split("def score_bonus")[1].split("def pick_override")[0]
    pick = src.split("def pick_override")[1].split("def after")[0]
    assert "self.events" not in bonus
    assert "self.events" not in pick
    assert "canonical_sequence_metrics" not in bonus
    assert "canonical_sequence_metrics" not in pick
