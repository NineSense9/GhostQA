"""Metric semantics: TTF vs TTCB, replay pass/fail/invalid, episode stats."""
from ghostqa.executor.sim import SimApp, SimExecutor
from ghostqa.exploration.explorer import run_exploration
from ghostqa.exploration.metrics import (
    classify_validation, episode_stats, finding_artifact, latency_metrics,
)
from ghostqa.exploration.policy import Policy
from ghostqa.oracle.engine import OracleEngine
from ghostqa.replay.validator import INVALID, validate_candidate
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
    return SimApp("metrics-branch", "home", pages, {}, lambda i, p: {})


class RelocateOncePolicy(Policy):
    name = "relocate-once"

    def __init__(self):
        self.relocated = False

    def select(self, graph, state, actions, ctx):
        page = state.meta.get("page")
        by = {a.target_eid: a for a in actions if a.target_eid}
        if page == "home":
            return by["nav_a"] if not self.relocated else by["nav_b"]
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
    return SimApp("metrics-crash", "home", pages, {}, lambda i, p: {})


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


def test_episode_metrics_after_relocate():
    result = run_exploration(SimExecutor(_branch_app()), RelocateOncePolicy(),
                             budget=8, oracle=OracleEngine())
    stats = episode_stats(result)
    assert stats["relocate_episode_count"] >= 1
    assert stats["episode_count"] >= 2
    assert stats["reset_count"] >= 2  # initial + relocate
    assert stats["max_episode_length"] >= 1
    assert stats["mean_episode_length"] > 0
    assert stats["crash_recovery_episode_count"] == 0


def test_ttf_is_first_finding_not_confirmed_bug():
    oracle = OracleEngine()
    result = run_exploration(SimExecutor(_crash_then_bug_app()),
                             CrashThenOtherPolicy(), budget=6, oracle=oracle)
    crash = next(f for f in result.candidates if f.kind == "crash")
    js = next(f for f in result.candidates if f.kind == "js_error")
    assert crash.step_index < js.step_index

    factory = lambda: SimExecutor(_crash_then_bug_app())
    vr = validate_candidate(factory, result.reproduction_actions(js), js, oracle)
    assert vr.confirmed
    lat = latency_metrics(result, {"BUG-JS": js.step_index})
    assert lat["ttf"] == crash.step_index
    assert lat["ttcb"] == js.step_index
    assert lat["ttf"] != lat["ttcb"]
    assert lat["time_to_first_bug"] == lat["ttf"]  # deprecated alias


def test_replay_metrics_pass_fail_invalid():
    oracle = OracleEngine()
    result = run_exploration(SimExecutor(_branch_app()), RelocateOncePolicy(),
                             budget=8, oracle=oracle)
    finding = next(f for f in result.candidates if f.kind == "js_error")
    factory = lambda: SimExecutor(_branch_app())

    vr_ok = validate_candidate(
        factory, result.reproduction_actions(finding), finding, oracle)
    assert classify_validation(vr_ok) == "pass"

    flat = result.actions()[: finding.step_index + 1]
    vr_flat = validate_candidate(factory, flat, finding, oracle)
    assert not vr_flat.confirmed
    assert classify_validation(vr_flat) in ("fail", "invalid")

    vr_bad = validate_candidate(
        factory, [Action("click", "no-such-element")], finding, oracle)
    assert classify_validation(vr_bad) == "invalid"
    assert vr_bad.status == INVALID


def test_finding_artifact_has_episode_id():
    result = run_exploration(SimExecutor(_branch_app()), RelocateOncePolicy(),
                             budget=8, oracle=OracleEngine())
    finding = next(f for f in result.candidates if f.kind == "js_error")
    art = finding_artifact(result, finding)
    assert "episode_id" in art
    assert art["episode_id"] >= 1
    step = result.step_for_finding(finding)
    assert art["episode_id"] == step.episode_id
    assert "episode_id" not in finding.to_dict()


def test_confirmed_bug_provenance():
    oracle = OracleEngine()
    result = run_exploration(SimExecutor(_branch_app()), RelocateOncePolicy(),
                             budget=8, oracle=oracle)
    finding = next(f for f in result.candidates if f.kind == "js_error")
    repro = result.reproduction_actions(finding)
    bug = result.make_confirmed(finding, repro)
    d = bug.to_dict()
    assert d["source_episode_id"] == result.step_for_finding(finding).episode_id
    assert d["original_global_step"] == finding.step_index
    assert d["episode_local_reproduction_length"] == len(repro)
    assert d["episode_local_reproduction_length"] < finding.step_index + 1
    assert all(a["target_eid"] != "nav_a" for a in d["reproduction"])
