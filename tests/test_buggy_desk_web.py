"""Known-path BuggyDesk correctness. Does not run C1/guard/BFS/DFS."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

from ghostqa.state.models import Action
from ghostqa.oracle.engine import OracleEngine
from ghostqa.oracle.spec import load_spec
from ghostqa.state.signature import state_signature

pytestmark = pytest.mark.integration

APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "apps", "buggy-desk")
SPEC_PATH = os.path.join(APP_DIR, "spec.json")
MANIFEST_PATH = os.path.join(APP_DIR, "bugs.manifest.json")
ROUTES = [
    "/index.html", "/tickets.html", "/ticket.html?id=1001",
    "/customers.html", "/customer.html?id=c1", "/activity.html?id=c1",
    "/kb.html", "/article.html?id=a1", "/reports.html", "/team.html",
    "/settings.html", "/profile.html", "/integrations.html",
    "/compose.html", "/help.html", "/handbook.html",
]


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="module")
def buggy_desk():
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, os.path.join(APP_DIR, "server.py"), str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            urllib.request.urlopen(base + "/index.html", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    else:
        proc.kill()
        raise RuntimeError("BuggyDesk server did not start")
    yield base
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


@pytest.fixture()
def web(buggy_desk):
    from ghostqa.executor.playwright_web import PlaywrightWebExecutor
    ex = PlaywrightWebExecutor(buggy_desk, headless=True)
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
        if new is not None:
            state = new
            sig = state_signature(state)
            hist.append(sig)
            sig_url[sig] = state.url
    return findings


def test_ordinary_routes_serve(buggy_desk):
    for path in ROUTES:
        with urllib.request.urlopen(buggy_desk + path, timeout=3) as resp:
            assert resp.status == 200, path
    with pytest.raises(Exception):
        urllib.request.urlopen(buggy_desk + "/bugs.manifest.json", timeout=3)
    with pytest.raises(Exception):
        urllib.request.urlopen(buggy_desk + "/topology.json", timeout=3)


def test_echo_ok_webhook_500(buggy_desk):
    req = urllib.request.Request(
        buggy_desk + "/api/echo", data=b"ping", method="POST")
    with urllib.request.urlopen(req, timeout=3) as resp:
        assert resp.status == 200
    req = urllib.request.Request(
        buggy_desk + "/api/webhook", data=b"{}", method="POST")
    try:
        urllib.request.urlopen(req, timeout=3)
        assert False, "webhook should 500"
    except urllib.error.HTTPError as e:
        assert e.code == 500


def test_observe_home_and_ground_truth(web):
    state = web.observe()
    assert "index.html" in state.url
    eids = [e.eid for e in state.elements]
    assert "nav_tickets" in eids
    assert "nav_customers" in eids
    assert "search_box" in eids
    assert web.ground_truth() == {}
    html = web.page.content()
    assert "BUG-K" not in html
    assert "data-bug-id" not in html
    assert "bugs.manifest" not in html


def test_reset_is_deterministic(web):
    a = web.reset()
    eids_a = [e.eid for e in a.elements]
    obs_a = dict(a.obs)
    b = web.reset()
    assert [e.eid for e in b.elements] == eids_a
    assert dict(b.obs) == obs_a
    assert "index.html" in b.url


def test_k1_js_error(web):
    fs = run_steps(web, [
        Action("click", "nav_integrations"),
        Action("click", "btn_test_conn"),
    ], OracleEngine())
    assert any(f.kind == "js_error" and "channel handshake" in f.evidence.get("error", "")
               for f in fs)


def test_k2_blank_reports(web):
    fs = run_steps(web, [Action("click", "nav_reports")], OracleEngine())
    assert any(f.kind == "blank" and "reports.html" in (f.evidence.get("url") or "")
               for f in fs)


def test_k3_dead_watch(web):
    fs = run_steps(web, [
        Action("click", "nav_tickets"),
        Action("click", "ticket_1001"),
        Action("click", "btn_watch"),
    ], OracleEngine())
    assert any(f.kind == "dead_action" and f.evidence.get("eid") == "btn_watch"
               for f in fs)


def test_k4_help_nav_loop(web):
    fs = run_steps(web, [
        Action("click", "nav_help"),
        Action("click", "btn_handbook"),
        Action("click", "btn_help"),
        Action("click", "btn_handbook"),
        Action("click", "btn_help"),
    ], OracleEngine())
    assert any(f.kind == "nav_loop" for f in fs)


def test_k5_empty_title_semantic(web):
    spec = load_spec(SPEC_PATH)
    fs = run_steps(web, [
        Action("click", "nav_compose"),
        Action("click", "btn_create"),
    ], OracleEngine(spec))
    assert any(f.kind == "semantic"
               and f.evidence.get("assert_id") == "ticket_title_required"
               for f in fs)


def test_k6_sla_after_pause(web):
    spec = load_spec(SPEC_PATH)
    fs = run_steps(web, [
        Action("click", "nav_tickets"),
        Action("click", "ticket_1001"),
        Action("click", "btn_pause_sla"),
    ], OracleEngine(spec))
    assert any(f.kind == "semantic"
               and f.evidence.get("assert_id") == "sla_display_matches_remaining"
               for f in fs)


def test_k7_long_search(web):
    fs = run_steps(web, [
        Action("input", "search_box", "x" * 25),
        Action("click", "search_btn"),
    ], OracleEngine())
    assert any(f.kind == "js_error" and "search query too long" in f.evidence.get("error", "")
               for f in fs)


def test_k8_webhook_http_error(web):
    fs = run_steps(web, [
        Action("click", "nav_integrations"),
        Action("click", "btn_webhook"),
    ], OracleEngine())
    assert any(f.kind == "http_error" and "/api/webhook" in (f.evidence.get("error") or "")
               for f in fs)


def test_k9_reopen_keeps_closed(web):
    spec = load_spec(SPEC_PATH)
    fs = run_steps(web, [
        Action("click", "nav_tickets"),
        Action("click", "ticket_1001"),
        Action("click", "btn_close"),
        Action("click", "btn_reopen"),
    ], OracleEngine(spec))
    assert any(f.kind == "semantic"
               and f.evidence.get("assert_id") == "reopen_clears_closed"
               for f in fs)


def test_k10_internal_note_on_activity(web):
    spec = load_spec(SPEC_PATH)
    fs = run_steps(web, [
        Action("click", "nav_tickets"),
        Action("click", "ticket_1001"),
        Action("click", "btn_internal_note"),
        Action("click", "nav_customer_c1"),
        Action("click", "nav_activity"),
    ], OracleEngine(spec))
    assert any(f.kind == "semantic"
               and f.evidence.get("assert_id") == "internal_note_not_customer_visible"
               for f in fs)


def test_legitimate_return_path(web):
    web.reset()
    web.execute(Action("click", "nav_tickets"))
    web.execute(Action("click", "ticket_1001"))
    r = web.execute(Action("click", "nav_back_tickets"))
    assert r.ok and r.state is not None
    assert "tickets.html" in r.state.url


def test_related_ticket_clique_reachable(web):
    web.reset()
    web.execute(Action("click", "nav_tickets"))
    web.execute(Action("click", "ticket_1001"))
    r = web.execute(Action("click", "related_1002"))
    assert r.ok and r.state is not None
    assert "id=1002" in r.state.url
    r = web.execute(Action("click", "related_1001"))
    assert "id=1001" in r.state.url


def test_semantic_obs_present_on_ticket(web):
    web.reset()
    web.execute(Action("click", "nav_tickets"))
    web.execute(Action("click", "ticket_1001"))
    st = web.observe()
    assert st.obs.get("ticket_status") == "处理中"
    assert st.obs.get("sla_display") == st.obs.get("sla_remaining")
    assert st.obs.get("reopen_state") == "否"
