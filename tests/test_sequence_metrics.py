"""v0.3.5.1 canonical sequence metrics. Must not change action traces."""
from ghostqa.agent.gateway import NullLLM
from ghostqa.executor.sim import SimExecutor
from ghostqa.exploration.explorer import run_exploration
from ghostqa.exploration.policy import GhostPolicy
from ghostqa.exploration.sequence import (
    SequenceController, canonical_sequence_metrics,
)
from ghostqa.oracle.engine import OracleEngine
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState
try:
    from helpers import make_hub_state, make_seq_app, make_seq_el
except ImportError:  # python -m pytest adds repo root, not tests/
    from tests.helpers import make_hub_state, make_seq_app, make_seq_el


def test_two_variants_one_canonical_hub():
    ctrl = SequenceController("sequence")
    g = StateGraph()
    g.add_state("h:a", "/hub", "Hub", cluster_id="hub", variant_key="a")
    g.add_state("h:b", "/hub", "Hub", cluster_id="hub", variant_key="b")
    hub = make_hub_state()
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
    hub = make_hub_state()
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
    hub = make_hub_state()
    leaf = GUIState(app="t", url="/a", title="A",
                    elements=(make_seq_el("x", "x"),), obs={})
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
    hub = make_hub_state()
    ctrl.after("h", Action("click", "go_a"), hub, hub, "new", [], "a", False, g, 1)
    ctrl.close_open(step=40, sig="a", cluster="a")
    m = canonical_sequence_metrics(ctrl.events)
    assert m["sequence_budget_ended"] == 1
    assert m["sequence_instances_returned"] == 0


def test_canonical_metrics_do_not_change_action_trace():
    def _keys():
        r = run_exploration(
            SimExecutor(make_seq_app()),
            GhostPolicy(NullLLM(), use_frontier=False, sequence_mode="sequence"),
            budget=16, oracle=OracleEngine())
        return [s.action.key() for s in r.steps], r.sequence_metrics

    k1, m1 = _keys()
    k2, m2 = _keys()
    assert k1 == k2
    assert m1.get("canonical_hub_count") is not None
    assert m1.get("hub_variant_count") is not None


def test_sequence_length_counts_concrete_actions():
    """Branch-start click is action #1; later actions increment length."""
    ctrl = SequenceController("sequence")
    g = StateGraph()
    g.add_state("h", "/hub", "Hub", cluster_id="hub")
    g.add_state("a", "/a", "A", cluster_id="a")
    hub = make_hub_state()
    leaf = GUIState(app="t", url="/a", title="A",
                    elements=(make_seq_el("x", "x"),), obs={})
    ctrl.after("h", Action("click", "go_a"), hub, leaf, "new", [], "a", False, g, 1)
    ctrl.after("a", Action("click", "x"), leaf, leaf, "similar", [], "a", False, g, 2)
    ctrl.after("a", Action("click", "x"), leaf, leaf, "similar", [], "a", False, g, 3)
    actions = [e for e in ctrl.events if e["event"] == "sequence_action"]
    assert len(actions) == 3
    assert actions[0]["action_key"] == Action("click", "go_a").key()
    m = canonical_sequence_metrics(ctrl.events)
    assert m["mean_sequence_len"] == 3
    assert m["max_sequence_len"] == 3
    assert m["sequence_instances_started"] == 1


def test_horizon_is_lifecycle_not_terminal():
    ctrl = SequenceController("sequence")
    g = StateGraph()
    g.add_state("h", "/hub", "Hub", cluster_id="hub")
    g.add_state("a", "/a", "A", cluster_id="a")
    hub = make_hub_state()
    leaf = GUIState(app="t", url="/a", title="A",
                    elements=(make_seq_el("x", "x"),), obs={})
    ctrl.after("h", Action("click", "go_a"), hub, leaf, "new", [], "a", False, g, 1)
    ctrl.after("a", Action("click", "x"), leaf, leaf, "identical", [], "a", False, g, 2)
    ctrl.after("a", Action("click", "x"), leaf, leaf, "identical", [], "a", False, g, 3)
    terminals = [e for e in ctrl.events if e["event"] == "sequence_terminal"]
    assert all(e.get("outcome") != "horizon" for e in terminals)
    assert any(e["event"] == "sequence_horizon_reached" for e in ctrl.events)
    m = canonical_sequence_metrics(ctrl.events)
    assert m["sequence_horizon_reached"] >= 1
    assert m.get("sequence_horizon_expired", 0) >= 1  # lifecycle alias, not a terminal
    assert m["sequence_instances_returned"] == 0
    assert m["sequence_budget_ended"] == 0
    assert m["sequence_instances_ended_on_finding"] == 0


def test_finding_is_instance_outcome_not_bug_count():
    class _Cand:
        def fingerprint(self):
            return "cand-1"

    ctrl = SequenceController("sequence")
    g = StateGraph()
    g.add_state("h", "/hub", "Hub", cluster_id="hub")
    g.add_state("a", "/a", "A", cluster_id="a")
    hub = make_hub_state()
    leaf = GUIState(app="t", url="/a", title="A",
                    elements=(make_seq_el("x", "x"),), obs={})
    ctrl.after("h", Action("click", "go_a"), hub, leaf, "new", [], "a", False, g, 1)
    ctrl.after("a", Action("click", "x"), leaf, leaf, "new", [_Cand()], "a", False, g, 2)
    m = canonical_sequence_metrics(ctrl.events)
    assert m["sequence_instances_ended_on_finding"] == 1
    assert m["sequence_found_finding"] == 1  # deprecated alias
    assert m["unique_branches_with_finding"] == 1
    assert m["unique_branches_returned"] == 0
    assert m["unique_branches_terminally_tested"] == 1
    assert m["unique_candidate_fingerprints_during_sequence"] == 1
    terminals = [e for e in ctrl.events if e["event"] == "sequence_terminal"]
    assert len(terminals) == 1
    assert terminals[0]["outcome"] == "finding"


def test_terminals_are_mutually_exclusive():
    ctrl = SequenceController("sequence")
    g = StateGraph()
    g.add_state("h", "/hub", "Hub", cluster_id="hub")
    hub = make_hub_state()
    ctrl.after("h", Action("click", "go_a"), hub, hub, "new", [], "a", False, g, 1)
    ctrl.close_open(step=40, sig="a", cluster="a")
    m = canonical_sequence_metrics(ctrl.events)
    buckets = (
        m["sequence_instances_returned"]
        + m["sequence_instances_ended_on_finding"]
        + m["sequence_crashed"]
        + m["sequence_lost_parent"]
        + m["sequence_budget_ended"]
    )
    assert buckets == m["sequence_instances_started"] == 1


def test_sim_sequences_are_longer_than_one_action():
    r = run_exploration(
        SimExecutor(make_seq_app()),
        GhostPolicy(NullLLM(), use_frontier=False, sequence_mode="sequence"),
        budget=16, oracle=OracleEngine())
    m = r.sequence_metrics
    assert m["max_sequence_len"] > 1
    assert m["mean_sequence_len"] > 1


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
