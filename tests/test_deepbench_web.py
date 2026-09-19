"""Integration tests: real Chromium + BuggyFlow (DeepBench)."""
import json
import os
import socket
import subprocess
import sys
import time

import pytest

from ghostqa.state.models import Action
from ghostqa.oracle.engine import OracleEngine
from ghostqa.oracle.spec import load_spec
from ghostqa.state.signature import state_id, cluster_id, variant_key

pytestmark = pytest.mark.integration

APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "apps", "buggy-flow")
SPEC_PATH = os.path.join(APP_DIR, "spec.json")
MANIFEST_PATH = os.path.join(APP_DIR, "bugs.manifest.json")


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="module")
def buggy_flow():
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, os.path.join(APP_DIR, "server.py"), str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            import urllib.request
            urllib.request.urlopen(base + "/index.html", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    else:
        proc.kill()
        raise RuntimeError("BuggyFlow server did not start")
    yield base
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


@pytest.fixture()
def web(buggy_flow):
    from ghostqa.executor.playwright_web import PlaywrightWebExecutor
    ex = PlaywrightWebExecutor(buggy_flow, headless=True)
    yield ex
    ex.close()


def run_steps(ex, actions, oracle):
    from ghostqa.state.signature import state_signature
    state = ex.reset()
    hist = [state_signature(state)]
    sig_url = {hist[0]: state.url}
    findings = []
    for i, a in enumerate(actions):
        r = ex.execute(a)
        new = r.state if not r.crashed else None
        findings.extend(oracle.inspect(state, a, r, new, {
            "step_index": i, "history_sigs": hist,
            "ground_truth": {}, "sig_url_map": sig_url}))
        if r.crashed:
            break
        state = new
        sig = state_signature(state)
        hist.append(sig)
        sig_url[sig] = state.url
    return findings


def _create_project(web, name="测试输入"):
    web.reset()
    web.execute(Action("click", "nav_login"))
    web.execute(Action("click", "btn_demo_login"))
    web.execute(Action("click", "btn_new_project"))
    if name:
        web.execute(Action("input", "proj_name", name))
    web.execute(Action("click", "btn_wiz_next"))
    web.execute(Action("click", "btn_wiz_next"))
    return web.execute(Action("click", "btn_wiz_confirm"))


def test_observe_home(web):
    state = web.observe()
    assert "index.html" in state.url
    eids = [e.eid for e in state.elements]
    assert "nav_login" in eids and "nav_help" in eids


def test_semantic_variants_same_cluster_on_project(web):
    _create_project(web, "测试输入")
    a = web.observe()
    web.execute(Action("click", "btn_archive"))
    b = web.observe()
    assert cluster_id(a) == cluster_id(b)
    assert variant_key(a) != variant_key(b)
    assert state_id(a) != state_id(b)


def test_clock_text_does_not_split_settings_cluster(web):
    web.reset()
    web.execute(Action("click", "nav_settings"))
    a = web.observe()
    web.execute(Action("click", "btn_toggle_notify"))
    b = web.observe()
    # toggle changes notify but notify is not data-obs; cluster stays
    assert cluster_id(a) == cluster_id(b)


def test_shallow_about_js_error(web):
    oracle = OracleEngine()
    fs = run_steps(web, [
        Action("click", "nav_about"),
        Action("click", "btn_version"),
    ], oracle)
    assert any(f.kind == "js_error" and "version info" in f.evidence.get("error", "")
               for f in fs)


def test_deep_empty_project_name(web):
    spec = load_spec(SPEC_PATH)
    oracle = OracleEngine(spec)
    web.reset()
    actions = [
        Action("click", "nav_login"),
        Action("click", "btn_demo_login"),
        Action("click", "btn_new_project"),
        Action("click", "btn_wiz_next"),
        Action("click", "btn_wiz_next"),
        Action("click", "btn_wiz_confirm"),
    ]
    fs = run_steps(web, actions, oracle)
    assert any(f.kind == "semantic"
               and f.evidence.get("assert_id") == "project_name_required"
               for f in fs)


def test_deep_guest_edit_after_archive(web):
    spec = load_spec(SPEC_PATH)
    oracle = OracleEngine(spec)
    _create_project(web, "测试输入")
    actions = [
        Action("click", "btn_members"),
        Action("click", "btn_add_alice"),
        Action("click", "btn_set_guest"),
        Action("click", "nav_project"),
        Action("click", "btn_archive"),
        Action("click", "btn_guest_edit"),
    ]
    # run_steps resets; use execute on current session instead
    findings = []
    state = web.observe()
    hist = []
    for i, a in enumerate(actions):
        r = web.execute(a)
        new = r.state
        findings.extend(oracle.inspect(state, a, r, new, {
            "step_index": i, "history_sigs": hist,
            "ground_truth": {}, "sig_url_map": {}}))
        state = new
    assert any(f.evidence.get("assert_id") == "archived_guest_cannot_edit"
               for f in findings if f.kind == "semantic")


def test_manifest_not_in_page_source(web):
    html = web.page.content()
    assert "BUG-D9" not in html
    assert "data-bug-id" not in html
    assert "bugs.manifest" not in html


def test_workflow_bfs_reaches_dashboard_or_wizard(web):
    """Reachability, not bug-discovery. No manifest is consulted."""
    from ghostqa.exploration.explorer import run_exploration
    from ghostqa.exploration.policy import WorkflowBFSPolicy
    result = run_exploration(web, WorkflowBFSPolicy(), budget=30)
    urls = " ".join(n.url for n in result.graph.nodes.values())
    assert result.max_workflow_depth >= 2 or "dashboard" in urls or "wizard" in urls, (
        f"WorkflowBFS did not leave the lobby; depth={result.max_workflow_depth} urls={urls}"
    )


def test_postreach_progress_exploit_progress_loop(web):
    """Behaviour, not D5: reach a post-login state, probe, continue."""
    from ghostqa.exploration.explorer import run_exploration
    from ghostqa.exploration.policy import GhostPolicy
    from ghostqa.agent.gateway import NullLLM
    result = run_exploration(
        web, GhostPolicy(NullLLM(), use_frontier=False, postreach_mode="postreach"),
        budget=40)
    urls = " ".join(n.url for n in result.graph.nodes.values())
    modes = [s.decision_mode for s in result.steps]
    assert result.max_workflow_depth >= 2 or "dashboard" in urls or "login" in urls
    assert any(m == "exploit" or m == "probe_commit" for m in modes) or (
        result.postreach_metrics.get("exploit_actions", 0) >= 1
        or result.postreach_metrics.get("deferred_payloads_executed", 0) >= 1
    ), f"no post-reach probe; modes={set(modes)} metrics={result.postreach_metrics}"
    assert result.actions_executed > 5
    assert any(m == "progress" for m in modes) or result.progress_actions >= 1
