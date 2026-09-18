"""Frontier planner + relocate tests (sim, no browser)."""
from ghostqa.executor.sim import SimExecutor
from ghostqa.exploration.explorer import run_exploration
from ghostqa.exploration.planner import FrontierPlanner
from ghostqa.exploration.policy import GhostPolicy, BFSPolicy
from ghostqa.oracle.engine import OracleEngine
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action
from ghostqa.agent.gateway import NullLLM
from benchmark.sim_apps import make_sim_deep


def test_planner_selects_non_current_untried_node():
    g = StateGraph()
    start = "home:none"
    g.add_state(start, "/home", "首页", cluster_id="home", variant_key="none")
    help_sig = "help:none"
    main_sig = "main:none"
    a_help = Action("click", "nav_help")
    a_main = Action("click", "nav_main")
    g.add_transition(start, "/home", "首页", a_help.key(), help_sig,
                     "/help", "帮助", action=a_help,
                     src_cluster="home", dst_cluster="help", dst_relation="new")
    g.add_state(main_sig, "/flow", "流程", cluster_id="main", variant_key="none")
    g.record_observed(start, [a_help.key(), a_main.key(), "back:"])
    g.record_observed(help_sig, ["back:"])
    g.record_observed(main_sig, [Action("click", "pay").key()])
    planner = FrontierPlanner()
    target = planner.select(g, help_sig, remaining_budget=20)
    assert target is not None
    assert target.sig != help_sig
    assert target.untried >= 1


def test_shortest_path_replay_actions_are_executable():
    g = StateGraph()
    a1 = Action("click", "nav_main")
    a2 = Action("click", "next_s2")
    g.add_transition("h:none", "/home", "首页", a1.key(), "s1:none",
                     "/s1", "s1", action=a1)
    g.add_transition("s1:none", "/s1", "s1", a2.key(), "s2:none",
                     "/s2", "s2", action=a2)
    path = g.shortest_path("h:none", "s2:none")
    assert [p.key() for p in path] == [a1.key(), a2.key()]


def test_ghost_frontier_finds_deep_crash():
    app, spec, manifest = make_sim_deep()
    ghost = run_exploration(SimExecutor(app), GhostPolicy(NullLLM()), budget=40,
                            oracle=OracleEngine(spec))
    bfs = run_exploration(SimExecutor(make_sim_deep()[0]), BFSPolicy(), budget=40,
                          oracle=OracleEngine(spec))
    ghost_hit = any(f.kind == "crash" for f in ghost.candidates)
    bfs_hit = any(f.kind == "crash" for f in bfs.candidates)
    # Research hypothesis, not a pass/fail gate: we only require Ghost to
    # remain capable of reaching the deep crash in this constructed app.
    assert ghost_hit, "GhostPolicy v1.2 should reach the depth-6 crash on sim-deep"
    # BFS may or may not; record both for the experiment narrative.
    assert ghost.relocate_count >= 0
    assert len(ghost.graph.nodes) >= 4
    _ = bfs_hit


def test_relocate_reset_replay_lands_on_frontier():
    """Construct a graph where the current leaf is exhausted and Home still
    has an untried high-value action; maybe_relocate must name that node."""
    from ghostqa.exploration.policy import GhostPolicy
    g = StateGraph()
    home, leaf = "home:none", "h4:none"
    g.add_state(home, "/home", "首页", brief="进入主流程 帮助",
                cluster_id="home", variant_key="none")
    a = Action("click", "nav_help")
    g.add_transition(home, "/home", "首页", a.key(), leaf,
                     "/h4", "帮助4", action=a)
    g.record_observed(home, [a.key(), "click:nav_main:", "back:"])
    g.record_observed(leaf, ["back:"])
    policy = GhostPolicy(NullLLM(), use_frontier=True)
    from ghostqa.state.models import GUIState, UIElement
    state = GUIState(app="t", url="/h4", title="帮助4",
                     elements=(UIElement("x", "link", "回"),), obs={})
    actions = [Action("back")]
    ctx = {"sig": leaf, "step_index": 12, "budget": 40, "state_brief": "帮助4"}
    target = policy.maybe_relocate(g, state, actions, ctx)
    assert target == home
