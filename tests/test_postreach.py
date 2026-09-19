"""v0.3.4 post-reach: deferred resume, bounded exploit, probe+commit, escape."""
import inspect

from ghostqa.agent.gateway import NullLLM
from ghostqa.executor.sim import SimApp, SimExecutor
from ghostqa.exploration.explorer import run_exploration
from ghostqa.exploration.payload import PAYLOAD_VALUES, first_wave, deferred_wave
from ghostqa.exploration.policy import GhostPolicy
from ghostqa.exploration.postreach import (
    PostReachController, EXPLOIT_BUDGET, DEFERRED_PER_VISIT,
)
from ghostqa.oracle.engine import OracleEngine
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState, UIElement


def _form_app():
    pages = {
        "home": {"url": "/home", "title": "首页",
                 "elements": [
                     {"eid": "go_form", "role": "link", "text": "下一步",
                      "effect": {"op": "goto", "to": "form"}},
                 ]},
        "form": {"url": "/project", "title": "项目",
                 "elements": [
                     {"eid": "name", "role": "input", "text": "名称",
                      "kind": "input", "input_type": "text",
                      "effect": {"op": "set", "key": "name"}},
                     {"eid": "create", "role": "button", "text": "创建",
                      "effect": {"op": "goto", "to": "done"}},
                     {"eid": "archive", "role": "button", "text": "归档",
                      "effect": {"op": "noop"}},
                 ]},
        "done": {"url": "/done", "title": "完成",
                 "elements": [
                     {"eid": "home", "role": "link", "text": "返回",
                      "effect": {"op": "goto", "to": "home"}},
                 ]},
    }
    return SimApp("postreach", "home", pages, {}, lambda i, p: {})


def test_deferred_resume_after_progress():
    result = run_exploration(
        SimExecutor(_form_app()),
        GhostPolicy(NullLLM(), use_frontier=False, postreach_mode="deferred"),
        budget=12, oracle=OracleEngine())
    inputs = [s.action for s in result.steps if s.action.type == "input"]
    first = {PAYLOAD_VALUES[c] for c in first_wave("text")}
    deferred_vals = {PAYLOAD_VALUES[c] for c in deferred_wave("text")}
    first_used = [a for a in inputs if (a.text or "") in first]
    deferred_used = [a for a in inputs if (a.text or "") in deferred_vals]
    assert first_used, "first-wave should run on first visit"
    assert deferred_used, "post-reach should resume one deferred class"
    assert result.postreach_metrics.get("deferred_payloads_executed", 0) >= 1


def test_exploit_budget_is_bounded():
    ctrl = PostReachController("exploit")
    g = StateGraph()
    g.add_state("s", "/p", "P", cluster_id="p")
    rec = ctrl.ledger.rec("s")
    rec.arrived_via_progress = True
    rec.graph_depth = 3
    rec.exploit_this_visit = EXPLOIT_BUDGET
    assert ctrl.ledger.should_exploit("s", g, "exploit") is False


def test_one_deferred_class_per_visit():
    assert DEFERRED_PER_VISIT == 1
    leftover = deferred_wave("text")
    assert leftover[0] == "BOUNDARY_LONG"
    assert "SCRIPT_SPECIAL" in leftover
    # widening order is generic field-type, not a D-number.


def test_probe_transaction_prefers_commit():
    ctrl = PostReachController("postreach")
    state = GUIState(
        app="t", url="/project", title="项目",
        elements=(
            UIElement("name", "input", "名称", kind="input", input_type="text"),
            UIElement("create", "button", "创建", kind="click"),
        ), obs={})
    g = StateGraph()
    g.add_state("s", "/project", "项目", cluster_id="p")
    g.record_observed("s", ["input:name:x", "click:create:"])
    ctrl.pending_commit = Action("click", "create")
    ctrl.pending_from_sig = "s"
    actions = [Action("input", "name", "x"), Action("click", "create"), Action("back")]
    chosen, label = ctrl.pick(actions, state, g, {"sig": "s"})
    assert label == "probe_commit"
    assert chosen.type == "click" and chosen.target_eid == "create"


def test_probe_cancelled_on_state_change():
    ctrl = PostReachController("postreach")
    ctrl.pending_commit = Action("click", "create")
    ctrl.pending_from_sig = "form"
    ctrl.after("form", Action("input", "name", "x"), "new", [], "other", False)
    assert ctrl.pending_commit is None


def test_saturation_after_exploit_budget():
    ctrl = PostReachController("postreach")
    ctrl.last_label = "exploit"
    rec = ctrl.ledger.rec("s")
    rec.exploit_this_visit = EXPLOIT_BUDGET - 1
    ctrl.after("s", Action("click", "archive"), "identical", [], "s", False)
    assert rec.exploit_this_visit >= EXPLOIT_BUDGET
    assert rec.saturated is True
    assert ctrl.ledger.local_saturation_count >= 1


def test_saturated_state_prefers_back():
    ctrl = PostReachController("postreach")
    g = StateGraph()
    g.add_state("s", "/p", "P")
    ctrl.ledger.rec("s").saturated = True
    state = GUIState(app="t", url="/p", title="P",
                     elements=(UIElement("a", "button", "再点", kind="click"),),
                     obs={})
    actions = [Action("click", "a"), Action("back")]
    chosen, label = ctrl.pick(actions, state, g, {"sig": "s"})
    assert label == "escape"
    assert chosen.type == "back"


def test_no_manifest_in_postreach_payload_policy():
    import ghostqa.exploration.postreach as pr
    import ghostqa.exploration.payload as pay
    import ghostqa.exploration.policy as pol
    src = inspect.getsource(pr) + inspect.getsource(pay) + inspect.getsource(pol)
    assert "bugs.manifest" not in src
    assert "holdout.manifest" not in src
    assert "BUG-D" not in src
    assert "trigger_depth" not in src
