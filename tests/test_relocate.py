"""v0.3.3 relocation: utility scale, single restore cost, gates, shadow."""
from ghostqa.agent.gateway import NullLLM
from ghostqa.exploration.interaction import InteractionOpportunity
from ghostqa.exploration.policy import GhostPolicy
from ghostqa.exploration.relocate import restore_cost, opportunity_value, breadth_bonus
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState, UIElement


def _el(eid, role, text, kind="click"):
    return UIElement(eid, role, text, kind=kind)


def _leaf_graph():
    g = StateGraph()
    home, leaf = "home:none", "h4:none"
    g.add_state(home, "/home", "首页", brief="进入主流程",
                cluster_id="home", variant_key="none")
    a = Action("click", "nav_help")
    g.add_transition(home, "/home", "首页", a.key(), leaf,
                     "/h4", "帮助4", action=a)
    g.record_observed(home, [a.key(), "click:nav_main:", "back:"])
    g.record_observed(leaf, ["back:"])
    g.record_opportunities(home, [
        InteractionOpportunity("click", "nav_main", "进入主流程", progress=True)])
    return g, home, leaf


def test_r0_still_relocates_to_home_frontier():
    g, home, leaf = _leaf_graph()
    policy = GhostPolicy(NullLLM(), use_frontier=True, relocate_mode="opportunity")
    state = GUIState(app="t", url="/h4", title="帮助4",
                     elements=(_el("x", "link", "回"),), obs={})
    ctx = {"sig": leaf, "step_index": 12, "budget": 40, "state_brief": "帮助4"}
    assert policy.maybe_relocate(g, state, [Action("back")], ctx) == home
    rec = policy.relocation_ledger.decisions[-1]
    assert rec["decision"] == "relocate"
    assert rec["frontier"]["target_sig"] == home
    # start-node restore path is empty; still log both cost fields.
    assert "planner_restore_cost" in rec["frontier"]
    assert "policy_restore_cost" in rec["frontier"]


def test_shadow_records_recommendation_but_does_not_return_target():
    g, home, leaf = _leaf_graph()
    policy = GhostPolicy(NullLLM(), use_frontier=True, relocate_mode="shadow")
    state = GUIState(app="t", url="/h4", title="帮助4",
                     elements=(_el("x", "link", "回"),), obs={})
    ctx = {"sig": leaf, "step_index": 12, "budget": 40, "state_brief": "帮助4"}
    assert policy.maybe_relocate(g, state, [Action("back")], ctx) is None
    rec = policy.relocation_ledger.decisions[-1]
    assert rec["decision"] == "relocate"
    assert rec["reason"] == "shadow"
    assert rec["executed"] is False
    assert rec["frontier"]["target_sig"] == home


def test_five_clicks_do_not_outrank_local_progress_under_marginal():
    g = StateGraph()
    here, far = "here:none", "far:none"
    g.add_state(here, "/here", "Here", cluster_id="here", variant_key="none")
    a = Action("click", "to_far")
    g.add_transition(here, "/here", "Here", a.key(), far, "/far", "Far", action=a)
    g.record_observed(here, [a.key(), "click:next:", "back:"])
    g.record_opportunities(here, [
        InteractionOpportunity("click", "next", "下一步", progress=True)])
    g.record_observed(far, [f"click:c{i}:" for i in range(5)] + ["back:"])
    g.record_opportunities(far, [
        InteractionOpportunity("click", f"c{i}", f"item{i}") for i in range(5)])
    policy = GhostPolicy(NullLLM(), use_frontier=True, relocate_mode="marginal")
    state = GUIState(app="t", url="/here", title="Here",
                     elements=(_el("next", "button", "下一步"),), obs={})
    actions = [Action("click", "next", text="下一步"), Action("back")]
    ctx = {"sig": here, "step_index": 12, "budget": 80, "state_brief": "here"}
    assert policy.maybe_relocate(g, state, actions, ctx) is None
    rec = policy.relocation_ledger.decisions[-1]
    assert rec["decision"] == "stay"
    local = rec["local"]["best_opportunity"]
    remote_clicks = rec["frontier"]["clicks"]
    assert remote_clicks >= 5
    assert local >= opportunity_value("progress") - 1e-9


def test_marginal_restore_cost_is_charged_once():
    g = StateGraph()
    home, a, b, far, leaf = "home:none", "a:none", "b:none", "far:none", "leaf:none"
    g.add_state(home, "/home", "Home", cluster_id="home", variant_key="none")
    e1, e2, e3, el = (Action("click", x) for x in ("to_a", "to_b", "to_far", "to_leaf"))
    g.add_transition(home, "/h", "H", e1.key(), a, "/a", "A", action=e1)
    g.add_transition(a, "/a", "A", e2.key(), b, "/b", "B", action=e2)
    g.add_transition(b, "/b", "B", e3.key(), far, "/far", "Far", action=e3)
    g.add_transition(home, "/h", "H", el.key(), leaf, "/leaf", "Leaf", action=el)
    g.record_observed(leaf, ["back:"])
    g.record_observed(far, [f"click:c{i}:" for i in range(3)] + ["back:"])
    g.record_opportunities(far, [
        InteractionOpportunity("click", "pay", "支付", progress=True)])
    policy = GhostPolicy(NullLLM(), use_frontier=True, relocate_mode="marginal")
    state = GUIState(app="t", url="/leaf", title="Leaf",
                     elements=(_el("x", "link", "回"),), obs={})
    ctx = {"sig": leaf, "step_index": 12, "budget": 80, "state_brief": "leaf"}
    policy.maybe_relocate(g, state, [Action("back")], ctx)
    rec = policy.relocation_ledger.decisions[-1]
    fr = rec["frontier"]
    assert fr["path_len"] >= 2
    once = restore_cost(fr["path_len"])
    assert abs(fr["restore_cost"] - once) < 1e-9
    double = fr["planner_restore_cost"] + fr["policy_restore_cost"]
    assert abs(fr["restore_cost"] - double) > 1e-9


def test_budget_reserve_blocks_long_restore():
    g, home, leaf = _leaf_graph()
    policy = GhostPolicy(NullLLM(), use_frontier=True, relocate_mode="marginal")
    state = GUIState(app="t", url="/h4", title="帮助4",
                     elements=(_el("x", "link", "回"),), obs={})
    # remaining = 12 - 10 = 2; path_len is 1; reserve 5 → blocked
    ctx = {"sig": leaf, "step_index": 10, "budget": 12, "state_brief": "帮助4"}
    assert policy.maybe_relocate(g, state, [Action("back")], ctx) is None
    rec = policy.relocation_ledger.decisions[-1]
    assert rec["reason"] == "reserve"


def test_momentum_blocks_ordinary_frontier():
    g, home, leaf = _leaf_graph()
    policy = GhostPolicy(NullLLM(), use_frontier=True, relocate_mode="momentum")
    policy.relocation_ledger.recent_new_states = [True, True, True]
    state = GUIState(app="t", url="/h4", title="帮助4",
                     elements=(_el("x", "link", "回"),), obs={})
    # Give a local progress-like action so the raised threshold can bite.
    actions = [Action("click", "stay_here", text="下一步"), Action("back")]
    ctx = {"sig": leaf, "step_index": 12, "budget": 80, "state_brief": "帮助4"}
    policy.maybe_relocate(g, state, actions, ctx)
    rec = policy.relocation_ledger.decisions[-1]
    assert rec["threshold"] >= 0.35 + 0.29


def test_lease_blocks_immediate_chain():
    g, home, leaf = _leaf_graph()
    policy = GhostPolicy(NullLLM(), use_frontier=True, relocate_mode="lease")
    policy.relocation_ledger.grant_lease(k=3)
    state = GUIState(app="t", url="/h4", title="帮助4",
                     elements=(_el("x", "link", "回"),), obs={})
    ctx = {"sig": leaf, "step_index": 12, "budget": 40, "state_brief": "帮助4"}
    assert policy.maybe_relocate(g, state, [Action("back")], ctx) is None
    rec = policy.relocation_ledger.decisions[-1]
    assert rec["reason"] == "lease"


def test_breadth_bonus_is_sublinear():
    assert breadth_bonus(10) < 10 * opportunity_value("nav_click")
    assert breadth_bonus(10) < 2.0
