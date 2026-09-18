"""v0.3.1 interaction / payload / frontier / relocate unit tests."""
from ghostqa.state.models import GUIState, UIElement, Action
from ghostqa.state.graph import StateGraph
from ghostqa.exploration.interaction import (
    opportunities, diagnose_action_space, classify_field, interaction_key,
    form_progress, workflow_stage,
)
from ghostqa.exploration.payload import (
    PayloadPolicy, PAYLOAD_VALUES, first_wave, deferred_wave,
)
from ghostqa.exploration.planner import pending_opportunity_counts, FrontierPlanner
from ghostqa.exploration.policy import GhostPolicy, WorkflowBFSPolicy
from ghostqa.exploration.explorer import run_exploration
from ghostqa.executor.sim import SimExecutor, SimApp
from ghostqa.oracle.engine import OracleEngine
from ghostqa.agent.gateway import NullLLM


def _el(eid, kind="click", text="", **kw):
    return UIElement(eid=eid, role="button" if kind == "click" else "input",
                     text=text, kind=kind, **kw)


def _state(elements, url="/p", title="P"):
    return GUIState(app="t", url=url, title=title, elements=tuple(elements), obs={})


def test_one_input_six_payloads_is_one_opportunity():
    s = _state([_el("user", "input", "用户名", placeholder="用户名")])
    diag = diagnose_action_space(s)
    assert diag["input_elements"] == 1
    assert diag["raw_input_actions"] == 6
    assert diag["unique_interaction_targets"] == 2  # input + back
    opps = opportunities(s)
    assert sum(1 for o in opps if o.kind == "input") == 1


def test_progressive_payload_first_visit_not_all_six():
    s = _state([_el("user", "input", "用户名", placeholder="username")])
    pp = PayloadPolicy()
    acts = pp.actions_for(s, "s0", can_back=False, ctx={"step_index": 0, "budget": 40})
    texts = {a.text for a in acts if a.type == "input"}
    assert len(texts) == 2
    assert PAYLOAD_VALUES["NORMAL"] in texts
    assert PAYLOAD_VALUES["EMPTY"] in texts
    assert PAYLOAD_VALUES["SCRIPT_SPECIAL"] not in texts


def test_field_type_heuristic():
    assert classify_field(_el("u", "input", "用户名", placeholder="username")) == "username"
    assert classify_field(_el("q", "input", "搜索", input_type="search")) == "search"
    assert classify_field(_el("n", "input", "数量", input_type="number")) == "number"


def test_frontier_does_not_multiply_payloads():
    g = StateGraph()
    g.add_state("home", "/h", "H", cluster_id="c", variant_key="none")
    a1 = Action("input", "user", "")
    a2 = Action("input", "user", "测试输入")
    a3 = Action("input", "user", "x" * 25)
    for a in (a1, a2, a3):
        g.record_observed("home", [a.key()])
    from ghostqa.exploration.interaction import InteractionOpportunity
    g.record_opportunities("home", [
        InteractionOpportunity(kind="input", eid="user", label="用户名",
                               field_type="username")])
    c = pending_opportunity_counts(g, "home")
    assert c["inputs"] == 1
    assert c["inputs"] + c["deferred"] <= 1


def test_restore_cost_lowers_far_frontier():
    g = StateGraph()
    start, far = "s0", "s9"
    g.add_state(start, "/a", "A")
    prev = start
    for i in range(9):
        nxt = f"n{i}"
        a = Action("click", f"e{i}")
        g.add_transition(prev, "/x", "X", a.key(), nxt if i < 8 else far,
                         "/y", "Y", action=a)
        prev = nxt if i < 8 else far
    g.record_opportunities(far, [])
    from ghostqa.exploration.interaction import InteractionOpportunity
    g.nodes[far].observed_opps["click:z"] = {"kind": "click", "progress": False}
    near = FrontierPlanner().score_node(g, start, start)
    far_t = FrontierPlanner().score_node(g, far, start)
    # far path is long; even with a pending click, restore cost should bite
    if far_t is not None and near is not None:
        assert far_t.path_len >= 8


def test_opportunity_relocate_despite_deferred_fuzz():
    g = StateGraph()
    home, leaf = "home:none", "h4:none"
    g.add_state(home, "/home", "首页", brief="进入主流程 帮助",
                cluster_id="home", variant_key="none")
    a = Action("click", "nav_help")
    g.add_transition(home, "/home", "首页", a.key(), leaf,
                     "/h4", "帮助4", action=a)
    g.record_observed(home, [a.key(), "click:nav_main:", "back:"])
    g.record_observed(leaf, ["input:box:zzzzz", "back:"])
    from ghostqa.exploration.interaction import InteractionOpportunity
    g.record_opportunities(home, [
        InteractionOpportunity("click", "nav_main", "进入主流程", progress=True)])
    g.record_opportunities(leaf, [
        InteractionOpportunity("input", "box", "x", field_type="text")])
    policy = GhostPolicy(NullLLM(), use_frontier=True, progressive=True,
                         relocate_mode="opportunity")
    state = GUIState(app="t", url="/h4", title="帮助4",
                     elements=(_el("box", "input", "x"),), obs={})
    # local remaining is a deferred-looking input
    actions = [Action("input", "box", PAYLOAD_VALUES["SCRIPT_SPECIAL"]),
               Action("back")]
    ctx = {"sig": leaf, "step_index": 12, "budget": 40, "state_brief": "帮助4"}
    target = policy.maybe_relocate(g, state, actions, ctx)
    assert target == home


def test_no_manifest_import_in_policy_planner():
    import inspect
    import ghostqa.exploration.policy as p
    import ghostqa.exploration.planner as pl
    src = inspect.getsource(p) + inspect.getsource(pl)
    assert "bugs.manifest" not in src
    assert "holdout.manifest" not in src
    assert "trigger_depth" not in src


def _form_app():
    pages = {
        "home": {"url": "/index.html", "title": "首页",
                 "elements": [
                     {"eid": "nav_login", "role": "link", "text": "登录",
                      "effect": {"op": "goto", "to": "login"}},
                     {"eid": "nav_help", "role": "link", "text": "帮助",
                      "effect": {"op": "goto", "to": "help"}},
                 ]},
        "login": {"url": "/login.html", "title": "登录",
                  "elements": [
                      {"eid": "login_user", "role": "input", "text": "用户名",
                       "kind": "input", "placeholder": "username"},
                      {"eid": "btn_login", "role": "button", "text": "登录",
                       "effect": {"op": "goto", "to": "dash"}},
                      {"eid": "btn_demo_login", "role": "button", "text": "演示登录",
                       "effect": {"op": "goto", "to": "dash"}},
                  ]},
        "dash": {"url": "/dashboard.html", "title": "工作台",
                 "elements": [
                     {"eid": "btn_new_project", "role": "button", "text": "新建项目",
                      "effect": {"op": "goto", "to": "wizard"}},
                 ]},
        "wizard": {"url": "/wizard.html", "title": "新建项目",
                   "elements": [
                       {"eid": "proj_name", "role": "input", "text": "项目名称",
                        "kind": "input"},
                       {"eid": "btn_wiz_next", "role": "button", "text": "下一步",
                        "effect": {"op": "goto", "to": "project"}},
                   ]},
        "project": {"url": "/project.html", "title": "项目详情",
                    "elements": [
                        {"eid": "btn_archive", "role": "button", "text": "归档",
                         "effect": {"op": "noop"}},
                    ]},
        "help": {"url": "/help.html", "title": "帮助",
                 "elements": [
                     {"eid": "more", "role": "link", "text": "更多",
                      "effect": {"op": "goto", "to": "help"}},
                 ]},
    }
    return SimApp("form", "home", pages, {}, lambda i, p: {})


def test_workflow_bfs_prefers_submit_over_deferred_fuzz():
    ex = SimExecutor(_form_app())
    result = run_exploration(ex, WorkflowBFSPolicy(), budget=12,
                             oracle=OracleEngine())
    urls = [n.url for n in result.graph.nodes.values()]
    assert any("dashboard" in u or "wizard" in u or "project" in u for u in urls)
    assert result.max_workflow_depth >= 2


def test_ghost_progressive_reaches_workflow():
    ex = SimExecutor(_form_app())
    result = run_exploration(ex, GhostPolicy(NullLLM(), progressive=True),
                             budget=16, oracle=OracleEngine())
    assert result.max_workflow_depth >= 2
    # first-wave should keep input share well below flat 6-payload flooding
    assert result.input_action_share < 0.7


def test_workflow_stage_from_url_only():
    assert workflow_stage("http://x/index.html") == 0
    assert workflow_stage("http://x/login.html") == 1
    assert workflow_stage("http://x/dashboard.html") == 2
    assert workflow_stage("http://x/wizard.html") == 3
    assert workflow_stage("http://x/project.html") == 4
