"""Episode-aware replay regressions (v0.3.2)."""
from ghostqa.executor.sim import SimApp, SimExecutor
from ghostqa.exploration.explorer import run_exploration
from ghostqa.exploration.policy import Policy
from ghostqa.minimizer.ddmin import minimize_reproduction
from ghostqa.oracle.engine import OracleEngine
from ghostqa.replay.validator import validate_candidate, validate_reproduction
from ghostqa.state.models import Action


def _branch_app():
    pages = {
        "home": {"url": "/home", "title": "首页",
                 "elements": [
                     {"eid": "nav_a", "role": "link", "text": "分支A",
                      "effect": {"op": "goto", "to": "a"}},
                     {"eid": "nav_b", "role": "link", "text": "分支B",
                      "effect": {"op": "goto", "to": "b"}},
                 ]},
        "a": {"url": "/a", "title": "A",
              "elements": [
                  {"eid": "btn_noop", "role": "button", "text": "空操作",
                   "effect": {"op": "noop"}},
              ]},
        "b": {"url": "/b", "title": "B",
              "elements": [
                  {"eid": "btn_bug", "role": "button", "text": "触发缺陷",
                   "effect": {"op": "js_error", "message": "branch-b-only-error"}},
              ]},
    }
    return SimApp("ep-branch", "home", pages, {}, lambda i, p: {})


class RelocateOncePolicy(Policy):
    """Explore A, then reset-relocate to start and take B."""
    name = "relocate-once"

    def __init__(self):
        self.relocated = False

    def select(self, graph, state, actions, ctx):
        page = state.meta.get("page")
        by = {a.target_eid: a for a in actions if a.target_eid}
        if page == "home":
            if not self.relocated:
                return by["nav_a"]
            return by["nav_b"]
        if page == "a":
            return by.get("btn_noop") or actions[0]
        if page == "b":
            return by["btn_bug"]
        return actions[0]

    def maybe_relocate(self, graph, state, actions, ctx):
        if self.relocated:
            return None
        if state.meta.get("page") == "a" and ctx.get("step_index", 0) >= 1:
            self.relocated = True
            return graph.start_sig
        return None


def _crash_then_bug_app():
    pages = {
        "home": {"url": "/home", "title": "首页",
                 "elements": [
                     {"eid": "boom", "role": "button", "text": "崩溃",
                      "effect": {"op": "crash"}},
                     {"eid": "other", "role": "button", "text": "另一缺陷",
                      "effect": {"op": "js_error", "message": "post-crash-only"}},
                 ]},
    }
    return SimApp("ep-crash", "home", pages, {}, lambda i, p: {})


class CrashThenOtherPolicy(Policy):
    name = "crash-then-other"

    def __init__(self):
        self.hit_crash = False

    def select(self, graph, state, actions, ctx):
        by = {a.target_eid: a for a in actions if a.target_eid}
        if not self.hit_crash and "boom" in by:
            self.hit_crash = True
            return by["boom"]
        return by.get("other") or actions[0]


def test_relocated_episode_finding_replays_from_correct_reset_boundary():
    app = _branch_app()
    oracle = OracleEngine()
    result = run_exploration(SimExecutor(app), RelocateOncePolicy(),
                             budget=8, oracle=oracle)
    assert result.relocate_count >= 1
    assert len({s.episode_id for s in result.steps}) >= 2
    bugs = [f for f in result.candidates if f.kind == "js_error"]
    assert bugs, f"expected js_error, got {[f.kind for f in result.candidates]}"
    finding = bugs[0]
    repro = result.reproduction_actions(finding)
    assert all(a.target_eid != "nav_a" for a in repro), (
        "episode-local repro must not include pre-reset branch A: "
        f"{[a.key() for a in repro]}")
    assert any(a.target_eid == "nav_b" for a in repro)
    assert any(a.target_eid == "btn_bug" for a in repro)

    factory = lambda: SimExecutor(_branch_app())
    vr = validate_candidate(factory, repro, finding, oracle)
    assert vr.confirmed, vr.detail
    # Old flattened prefix would go to A first and fail to click nav_b.
    flat = result.actions()[: finding.step_index + 1]
    if any(a.target_eid == "nav_a" for a in flat):
        vr_flat = validate_candidate(factory, flat, finding, oracle)
        assert not vr_flat.confirmed


def test_post_crash_episode_finding_does_not_include_pre_crash_actions():
    oracle = OracleEngine()
    result = run_exploration(SimExecutor(_crash_then_bug_app()),
                             CrashThenOtherPolicy(), budget=6, oracle=oracle)
    post = [f for f in result.candidates if f.kind == "js_error"]
    assert post
    finding = post[0]
    repro = result.reproduction_actions(finding)
    assert all(a.target_eid != "boom" for a in repro)
    assert any(a.target_eid == "other" for a in repro)
    vr = validate_candidate(lambda: SimExecutor(_crash_then_bug_app()),
                            repro, finding, oracle)
    assert vr.confirmed


def test_ddmin_stays_inside_relocation_episode():
    oracle = OracleEngine()
    result = run_exploration(SimExecutor(_branch_app()), RelocateOncePolicy(),
                             budget=8, oracle=oracle)
    finding = next(f for f in result.candidates if f.kind == "js_error")
    repro = result.reproduction_actions(finding)
    factory = lambda: SimExecutor(_branch_app())
    mini = minimize_reproduction(factory, repro, finding, oracle)
    assert mini
    assert all(a.target_eid != "nav_a" for a in mini)
    vr = validate_reproduction(factory, mini, finding.fingerprint(), oracle)
    assert vr.confirmed
    # executable from a clean reset
    vr2 = validate_candidate(factory, mini, finding, oracle)
    assert vr2.confirmed
