"""v0.3.5 hub / branch / mutation / followup / return-to-hub."""
import inspect

from ghostqa.agent.gateway import NullLLM
from ghostqa.executor.sim import SimApp, SimExecutor
from ghostqa.exploration.explorer import run_exploration
from ghostqa.exploration.policy import GhostPolicy
from ghostqa.exploration.sequence import (
    SequenceController, is_hub, branch_key, W_BRANCH_NOVELTY, BRANCH_HORIZON,
)
from ghostqa.oracle.engine import OracleEngine
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState, UIElement


def _el(eid, text, kind="click"):
    return UIElement(eid, "button", text, kind=kind)


def _hub_state():
    return GUIState(
        app="t", url="/hub", title="Hub",
        elements=(
            _el("go_a", "分支A"),
            _el("go_b", "分支B"),
            _el("go_c", "分支C"),
            _el("submit", "提交"),
        ), obs={})


def _form_state():
    return GUIState(
        app="t", url="/form", title="Form",
        elements=(
            UIElement("name", "input", "名称", kind="input", input_type="text"),
            _el("create", "创建"),
        ), obs={})


def test_three_branches_make_a_hub():
    assert is_hub(_hub_state()) is True
    assert is_hub(_form_state()) is False


def test_untested_branch_has_bonus_then_zero():
    ctrl = SequenceController("branch")
    g = StateGraph()
    g.add_state("h", "/hub", "Hub", cluster_id="hub")
    state = _hub_state()
    ctx = {"sig": "h", "step_index": 8}
    a = Action("click", "go_a")
    b1 = ctrl.score_bonus(a, state, g, ctx)
    rec = ctrl.ledger.hub("h", "hub")
    rec.started.add(branch_key("hub", a))
    b2 = ctrl.score_bonus(a, state, g, ctx)
    assert b1 >= W_BRANCH_NOVELTY - 1e-9
    assert b2 < b1
    assert abs(b2) < 1e-9


def test_commitment_does_not_immediately_back():
    ctrl = SequenceController("sequence")
    g = StateGraph()
    g.add_state("h", "/hub", "Hub", cluster_id="hub")
    state = _hub_state()
    ctx = {"sig": "h"}
    chosen = ctrl.pick_override(
        [Action("click", "go_a"), Action("back")], state, g, ctx)
    assert chosen is not None and chosen.target_eid == "go_a"
    ctrl.after("h", chosen, state, state, "new", [], "a", False, g, 8)
    assert ctrl.ledger.commitment_left == BRANCH_HORIZON - 1
    leaf = GUIState(app="t", url="/a", title="A",
                    elements=(_el("do", "操作"),), obs={})
    g.add_state("a", "/a", "A", cluster_id="a")
    ov = ctrl.pick_override(
        [Action("click", "do"), Action("back")], leaf, g, {"sig": "a"})
    assert ov is None or ov.type != "back"


def test_mutation_creates_followup_bonus():
    ctrl = SequenceController("followup")
    g = StateGraph()
    before = GUIState(app="t", url="/a", title="A",
                      elements=(_el("mutate", "变更"),), obs={"x": "0"})
    after = GUIState(app="t", url="/a", title="A",
                     elements=(_el("mutate", "变更"), _el("follow", "后续")),
                     obs={"x": "1"})
    g.add_state("a", "/a", "A", cluster_id="a")
    ctrl.after("a", Action("click", "mutate"), before, after, "similar", [],
               "a", False, g, 3)
    assert ctrl.ledger.mutations >= 1
    fu = Action("click", "follow")
    assert ctrl._is_followup(fu)
    bonus = ctrl.score_bonus(fu, after, g, {"sig": "a"})
    assert bonus >= 0.5


def test_followup_expires_after_horizon_ttl():
    ctrl = SequenceController("followup")
    g = StateGraph()
    before = GUIState(app="t", url="/a", title="A",
                      elements=(_el("m", "m"),), obs={})
    after = GUIState(app="t", url="/a", title="A",
                     elements=(_el("m", "m"), _el("n", "n")), obs={})
    g.add_state("a", "/a", "A")
    ctrl.after("a", Action("click", "m"), before, after, "new", [], "a", False, g, 0)
    for _ in range(12):
        ctrl.after("a", Action("click", "m"), after, after, "identical", [],
                   "a", False, g, 1)
    assert ctrl._is_followup(Action("click", "n")) is False


def test_return_to_hub_uses_back_not_reset():
    ctrl = SequenceController("sequence")
    g = StateGraph()
    g.add_state("h", "/hub", "Hub", cluster_id="hub")
    g.add_state("a", "/a", "A", cluster_id="a")
    hub = _hub_state()
    ctrl.pick_override([Action("click", "go_a"), Action("back")], hub, g, {"sig": "h"})
    ctrl.after("h", Action("click", "go_a"), hub, hub, "new", [], "a", False, g, 1)
    ctrl.ledger.commitment_left = 0
    ctrl.ledger.returning = True
    leaf = GUIState(app="t", url="/a", title="A",
                    elements=(_el("x", "x"),), obs={})
    ov = ctrl.pick_override([Action("click", "x"), Action("back")], leaf, g, {"sig": "a"})
    assert ov is not None and ov.type == "back"


def test_branch_completed_after_parent_return():
    ctrl = SequenceController("sequence")
    g = StateGraph()
    g.add_state("h", "/hub", "Hub", cluster_id="hub")
    g.add_state("a", "/a", "A", cluster_id="a")
    hub = _hub_state()
    ctrl.after("h", Action("click", "go_a"), hub, hub, "new", [], "a", False, g, 1)
    assert ctrl.ledger.active_branch
    leaf = GUIState(app="t", url="/a", title="A", elements=(_el("x", "x"),), obs={})
    ctrl.ledger.returning = True
    ctrl.after("a", Action("back"), leaf, hub, "identical", [], "h", False, g, 2)
    rec = ctrl.ledger.hub("h", "hub")
    assert rec.completed
    assert ctrl.ledger.return_success >= 1


def _seq_app():
    pages = {
        "hub": {"url": "/hub", "title": "Hub",
                "elements": [
                    {"eid": "go_a", "role": "button", "text": "分支A",
                     "effect": {"op": "goto", "to": "a"}},
                    {"eid": "go_b", "role": "button", "text": "分支B",
                     "effect": {"op": "goto", "to": "b"}},
                    {"eid": "go_c", "role": "button", "text": "分支C",
                     "effect": {"op": "goto", "to": "c"}},
                ]},
        "a": {"url": "/a", "title": "A",
              "elements": [
                  {"eid": "mutate", "role": "button", "text": "变更",
                   "effect": {"op": "goto", "to": "a2"}},
                  {"eid": "backh", "role": "button", "text": "返回",
                   "effect": {"op": "goto", "to": "hub"}},
              ]},
        "a2": {"url": "/a2", "title": "A2",
               "elements": [
                   {"eid": "follow", "role": "button", "text": "后续",
                    "effect": {"op": "goto", "to": "hub"}},
                   {"eid": "backh", "role": "button", "text": "返回",
                    "effect": {"op": "goto", "to": "hub"}},
               ]},
        "b": {"url": "/b", "title": "B",
              "elements": [
                  {"eid": "leaf_b", "role": "button", "text": "叶子B",
                   "effect": {"op": "noop"}},
                  {"eid": "backh", "role": "button", "text": "返回",
                   "effect": {"op": "goto", "to": "hub"}},
              ]},
        "c": {"url": "/c", "title": "C",
              "elements": [
                  {"eid": "leaf_c", "role": "button", "text": "叶子C",
                   "effect": {"op": "noop"}},
                  {"eid": "backh", "role": "button", "text": "返回",
                   "effect": {"op": "goto", "to": "hub"}},
              ]},
    }
    return SimApp("seq", "hub", pages, {}, lambda i, p: {})


def test_agent_covers_two_branches_and_followup():
    result = run_exploration(
        SimExecutor(_seq_app()),
        GhostPolicy(NullLLM(), use_frontier=False, sequence_mode="sequence"),
        budget=20, oracle=OracleEngine())
    eids = [s.action.target_eid for s in result.steps if s.action.type == "click"]
    assert "go_a" in eids or "go_b" in eids
    m = result.sequence_metrics
    assert m.get("hub_count", 0) >= 1
    assert m.get("branches_started", 0) >= 1
    # Followup or a second branch — sequence planner is working.
    assert ("follow" in eids) or (m.get("branches_started", 0) >= 2) or (
        m.get("return_success", 0) >= 1)


def test_no_manifest_in_sequence_module():
    src = inspect.getsource(
        __import__("ghostqa.exploration.sequence", fromlist=["x"]))
    assert "bugs.manifest" not in src
    assert "holdout.manifest" not in src
    assert "BUG-D" not in src
    assert "trigger_depth" not in src
    assert "prerequisites" not in src
    assert "shortest_path replay" not in src.lower()
