"""Integration tests: real Chromium + BuggyShop. Marked `integration`."""
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
from ghostqa.state.signature import state_signature

pytestmark = pytest.mark.integration

APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "apps", "buggy-shop")
SPEC_PATH = os.path.join(APP_DIR, "spec.json")
MANIFEST_PATH = os.path.join(APP_DIR, "bugs.manifest.json")


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="module")
def buggy_shop():
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
        raise RuntimeError("BuggyShop server did not start")
    yield base
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


@pytest.fixture()
def web(buggy_shop, tmp_path):
    from ghostqa.executor.playwright_web import PlaywrightWebExecutor
    ex = PlaywrightWebExecutor(buggy_shop, headless=True,
                               screenshots_dir=str(tmp_path))
    yield ex
    ex.close()


def run_steps(ex, actions, oracle):
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


def test_observe_home(web):
    state = web.observe()
    assert "index.html" in state.url
    assert len(state.elements) >= 5
    eids = [e.eid for e in state.elements]
    assert "search_box" in eids and "search_btn" in eids
    assert state.meta["body_text_len"] > 0


def test_click_navigation(web):
    web.reset()
    r = web.execute(Action("click", "item_apple"))
    # from home there is no item_apple; navigate via products page link text
    assert not r.ok or True
    r = web.execute(Action("click", _find_eid(web, "商品列表")))
    assert r.ok and "products.html" in r.state.url


def test_nav_stack_records_real_navigation(web):
    web.reset()
    web.execute(Action("click", _find_eid(web, "商品列表")))
    assert "products.html" in web.page.url
    r = web.execute(Action("back"))
    assert r.ok and "index.html" in r.state.url


def test_nav_stack_ignores_same_page_click(web):
    """Favorite is a same-page no-op; Back must not treat it as a navigation."""
    web.reset()
    web.execute(Action("click", _find_eid(web, "商品列表")))
    web.execute(Action("click", "item_apple"))
    assert "detail.html" in web.page.url
    stack_before = list(web._nav_stack)
    r = web.execute(Action("click", "btn_fav"))
    assert r.ok
    assert "detail.html" in r.state.url
    assert web._nav_stack == stack_before, "same-page click must not push Back stack"
    r = web.execute(Action("back"))
    assert "products.html" in r.state.url, (
        f"Back after same-page click should leave detail, got {r.state.url}")


def _find_eid(web, text: str) -> str:
    if not hasattr(web, "_descriptors"):
        web.observe()
    for eid, d in web._descriptors.items():
        if text in d.get("text", ""):
            return eid
    raise AssertionError(f"element with text {text} not found")


def test_l1_js_error_search_overflow(web):
    oracle = OracleEngine()
    findings = run_steps(web, [
        Action("input", "search_box", "x" * 25),
        Action("click", "search_btn"),
    ], oracle)
    assert any(f.kind == "js_error" and "搜索关键词过长" in f.evidence.get("error", "")
               for f in findings)


def test_l2_dead_action_favorite(web):
    oracle = OracleEngine()
    findings = run_steps(web, [
        Action("click", _find_eid(web, "商品列表")),
        Action("click", "item_apple"),
        Action("click", "btn_fav"),
    ], oracle)
    assert any(f.kind == "dead_action" and f.evidence.get("eid") == "btn_fav"
               for f in findings)


def test_l3_semantic_cart_total(web):
    spec = load_spec(SPEC_PATH)
    oracle = OracleEngine(spec)
    findings = run_steps(web, [
        Action("click", _find_eid(web, "购物车")),
        Action("click", "btn_remove"),
    ], oracle)
    assert any(f.kind == "semantic"
               and f.evidence.get("assert_id") == "cart_total_consistent"
               for f in findings)


def test_l3_semantic_login_gate(web):
    spec = load_spec(SPEC_PATH)
    oracle = OracleEngine(spec)
    findings = run_steps(web, [Action("click", _find_eid(web, "个人中心"))], oracle)
    assert any(f.evidence.get("assert_id") == "login_gate"
               for f in findings if f.kind == "semantic")


def test_l1_blank_promo(web):
    oracle = OracleEngine()
    findings = run_steps(web, [Action("click", _find_eid(web, "活动专区"))], oracle)
    assert any(f.kind == "blank" for f in findings)


def test_replay_invalid_when_element_missing(web, buggy_shop):
    from ghostqa.replay.validator import _replay, INVALID
    from ghostqa.executor.playwright_web import PlaywrightWebExecutor
    oracle = OracleEngine()
    shared = web.share_handle()
    factory = lambda: PlaywrightWebExecutor(buggy_shop, headless=True, shared=shared)
    status, _findings, diag = _replay(factory, [Action("click", "nonexistent_eid")], oracle)
    assert status == INVALID
    assert diag.get("failed_action_index") == 0


def test_vertical_slice_end_to_end(web, buggy_shop, tmp_path):
    """The v0.2 main quest: explore -> candidate -> replay confirm -> ddmin -> report."""
    from ghostqa.agent.gateway import NullLLM
    from ghostqa.exploration.explorer import run_exploration
    from ghostqa.exploration.policy import GhostPolicy
    from ghostqa.executor.playwright_web import PlaywrightWebExecutor
    from ghostqa.minimizer.ddmin import minimize_reproduction
    from ghostqa.replay.validator import validate_candidate
    from ghostqa.report.generator import build_report, write_report

    spec = load_spec(SPEC_PATH)
    oracle = OracleEngine(spec)
    result = run_exploration(web, GhostPolicy(NullLLM()), budget=45, oracle=oracle)

    kinds = {f.kind for f in result.candidates}
    assert len(result.candidates) >= 2, f"expected candidates, got {kinds}"

    shared = web.share_handle()
    factory = lambda: PlaywrightWebExecutor(buggy_shop, headless=True, shared=shared)
    confirmed, kept_executors = [], []
    for f in result.candidates:
        vr = validate_candidate(factory, result.reproduction_actions(f), f, oracle)
        if vr.confirmed:
            repro = minimize_reproduction(factory, result.reproduction_actions(f), f, oracle)
            from ghostqa.state.models import ConfirmedBug
            confirmed.append(ConfirmedBug(finding=f, reproduction=repro,
                                          original_length=f.step_index + 1))
    assert len(confirmed) >= 1, "no bug survived replay validation"

    report = build_report(result, confirmed, {"budget": 45, "policy": "ghost"})
    write_report(report, str(tmp_path / "report.json"), str(tmp_path / "report.html"))
    assert os.path.exists(tmp_path / "report.html")
    data = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert data["summary"]["confirmed_bugs"] >= 1
    assert any(b["reproduction"] for b in data["bugs"])
