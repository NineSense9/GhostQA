"""BugFingerprint + manifest identity tests."""
from ghostqa.oracle.fingerprint import (fingerprint_of, normalize_url,
                                        normalize_error)
from ghostqa.state.models import Action, Finding
from ghostqa.executor.sim import SimExecutor, SimApp
from ghostqa.exploration.explorer import run_exploration
from ghostqa.exploration.policy import DFSPolicy
from ghostqa.oracle.engine import OracleEngine
from benchmark.runner import match_manifest


def test_url_and_error_normalization():
    assert normalize_url("http://localhost:3000/cart?ts=123#x") == "/cart"
    assert normalize_url("sim://sim-shop/cart") == "/cart"
    assert normalize_error("Error at line 42:  x > 3\nstack...") == "error at line #: x > #"


def test_two_crashes_have_distinct_fingerprints():
    f1 = Finding("crash", "high", "crash A", 1,
                 {"action": "click[pay]", "page": "checkout", "page_url": "sim://a/checkout"})
    f2 = Finding("crash", "high", "crash B", 2,
                 {"action": "click[boom]", "page": "other", "page_url": "sim://a/other"})
    assert f1.fingerprint() != f2.fingerprint()
    same = Finding("crash", "high", "crash A again", 9,
                   {"action": "click[pay]", "page": "checkout", "page_url": "sim://a/checkout"})
    assert f1.fingerprint() == same.fingerprint()


def test_semantic_fingerprint_uses_assert_id():
    f1 = Finding("semantic", "high", "x", 1, {"assert_id": "a1", "url": "sim://a/cart"})
    f2 = Finding("semantic", "high", "y", 2, {"assert_id": "a2", "url": "sim://a/cart"})
    assert f1.fingerprint() != f2.fingerprint()


# ---- an app with TWO different crash bugs ----
def make_two_crash_app():
    pages = {
        "home": {"url": "/home", "title": "首页",
                 "elements": [
                     {"eid": "nav_a", "role": "link", "text": "去A",
                      "effect": {"op": "goto", "to": "a"}},
                     {"eid": "nav_b", "role": "link", "text": "去B",
                      "effect": {"op": "goto", "to": "b"}},
                 ]},
        "a": {"url": "/a", "title": "页面A",
              "elements": [{"eid": "btn_boom_a", "role": "button", "text": "A崩溃",
                            "effect": {"op": "crash"}}]},
        "b": {"url": "/b", "title": "页面B",
              "elements": [{"eid": "btn_boom_b", "role": "button", "text": "B崩溃",
                            "effect": {"op": "crash"}}]},
    }
    manifest = [
        {"id": "BUG-A", "kind": "crash", "desc": "A页崩溃", "match": {"page": "a"}},
        {"id": "BUG-B", "kind": "crash", "desc": "B页崩溃", "match": {"page": "b"}},
    ]
    return SimApp("two-crash", "home", pages, {}, lambda i, p: {}), manifest


def test_manifest_matches_only_the_crash_actually_found():
    app, manifest = make_two_crash_app()
    # trigger only the A crash
    ex = SimExecutor(app)
    oracle = OracleEngine()
    from ghostqa.state.signature import state_signature
    state = ex.observe()
    hist = [state_signature(state)]
    findings = []
    for i, a in enumerate([Action("click", "nav_a"), Action("click", "btn_boom_a")]):
        r = ex.execute(a)
        new = r.state if not r.crashed else None
        findings.extend(oracle.inspect(state, a, r, new, {
            "step_index": i, "history_sigs": hist, "ground_truth": {}}))
        if not r.crashed:
            state = new
            hist.append(state_signature(state))
    found = match_manifest(findings, manifest)
    assert found == {"BUG-A"}          # NOT both


def test_manifest_rejects_indistinguishable_entries():
    import pytest
    bad = [{"id": "X", "kind": "crash", "match": {"page": "a"}},
           {"id": "Y", "kind": "crash", "match": {"page": "a"}}]
    with pytest.raises(ValueError):
        match_manifest([], bad)


# ---- slow-path regression: entering an unknown state triggers LLM ----
class SpyLLM:
    def __init__(self):
        self.calls = 0
        self.pseudo_tokens = 0

    def score_actions(self, s, briefs, spec=""):
        self.calls += 1
        return {i: 0.5 for i in range(len(briefs))}

    def choose_action(self, s, briefs):
        return 0


def test_entering_unknown_state_triggers_slow_path():
    """Regression for the is_new_state bug: destination novelty must be
    recorded before add_transition, so the FIRST decision on a newly
    discovered page consults the LLM."""
    from ghostqa.exploration.policy import GhostPolicy
    try:
        from helpers import make_mini_crash_app
    except ImportError:  # importlib mode
        from tests.helpers import make_mini_crash_app
    llm = SpyLLM()
    ex = SimExecutor(make_mini_crash_app())
    run_exploration(ex, GhostPolicy(llm), budget=5, oracle=OracleEngine())
    # step 0 (novel initial state) and step 1 (just arrived at page A)
    # must have triggered slow path at least twice
    assert llm.calls >= 2
