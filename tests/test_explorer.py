"""Explorer loop + policies tests (deterministic, sim-based)."""
from ghostqa.agent.gateway import MockLLM, NullLLM
from ghostqa.executor.sim import SimExecutor
from ghostqa.exploration.explorer import run_exploration
from ghostqa.exploration.policy import (RandomPolicy, DFSPolicy, GhostPolicy)
from ghostqa.oracle.engine import OracleEngine
from benchmark.sim_apps import make_sim_shop


def _make_mini_crash_app():
    """Tiny app with an easily reachable crash for loop-level tests."""
    from ghostqa.executor.sim import SimApp
    pages = {
        "home": {"url": "/home", "title": "首页",
                 "elements": [
                     {"eid": "nav_a", "role": "link", "text": "页面A",
                      "effect": {"op": "goto", "to": "a"}},
                 ]},
        "a": {"url": "/a", "title": "页面A",
              "elements": [
                  {"eid": "btn_boom", "role": "button", "text": "危险操作",
                   "effect": {"op": "crash"}},
              ]},
    }
    return SimApp("mini-crash", "home", pages, {}, lambda i, p: {})


def test_explorer_ghost_finds_crash():
    ex = SimExecutor(_make_mini_crash_app())
    result = run_exploration(ex, GhostPolicy(MockLLM()), budget=30,
                             oracle=OracleEngine())
    assert any(f.kind == "crash" for f in result.candidates)


def test_explorer_ghost_finds_multiple_bug_kinds_on_shop():
    app, spec, manifest = make_sim_shop()
    ex = SimExecutor(app)
    result = run_exploration(ex, GhostPolicy(MockLLM()), budget=80,
                             oracle=OracleEngine(spec))
    kinds = {f.kind for f in result.candidates}
    assert len(kinds) >= 3, f"expected >=3 kinds, got {kinds}"
    assert result.actions_executed > 0
    assert len(result.graph.nodes) >= 4           # discovered multiple states


def test_explorer_deterministic_with_seed():
    app, spec, _ = make_sim_shop()
    r1 = run_exploration(SimExecutor(app), RandomPolicy(seed=7), budget=40,
                         oracle=OracleEngine(spec))
    app2, spec2, _ = make_sim_shop()
    r2 = run_exploration(SimExecutor(app2), RandomPolicy(seed=7), budget=40,
                         oracle=OracleEngine(spec2))
    assert [s.action.key() for s in r1.steps] == [s.action.key() for s in r2.steps]


def test_explorer_recovers_after_crash():
    app, spec, _ = make_sim_shop()
    ex = SimExecutor(app)
    result = run_exploration(ex, DFSPolicy(), budget=50, oracle=OracleEngine(spec))
    # DFS will eventually hit pay->crash; exploration must continue afterwards
    if any(f.kind == "crash" for f in result.candidates):
        assert result.steps[-1].state_sig_after != "CRASHED" or \
               result.actions_executed == 50


def test_ghost_policy_uses_llm_only_on_slow_path():
    llm = MockLLM()
    app, spec, _ = make_sim_shop()
    ex = SimExecutor(app)
    run_exploration(ex, GhostPolicy(llm), budget=30, oracle=OracleEngine(spec))
    naive_calls = 30                                # every step would be 30
    assert llm.calls < naive_calls                  # slow path only
    assert llm.calls > 0                            # but it does consult the LLM


def test_ghost_vs_random_coverage():
    app, spec, _ = make_sim_shop()
    r_ghost = run_exploration(SimExecutor(app), GhostPolicy(NullLLM()), budget=80,
                              oracle=OracleEngine(spec))
    app2, spec2, _ = make_sim_shop()
    r_rand = run_exploration(SimExecutor(app2), RandomPolicy(seed=1), budget=80,
                             oracle=OracleEngine(spec2))
    assert len(r_ghost.graph.edges) >= len(r_rand.graph.edges)
