"""Known-path correctness for v0.3.11 apps. Does not run C1/guard/BFS/DFS."""
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
from benchmark.multitarget_generator import FAMILIES, ROOT, APP_NAMES

pytestmark = pytest.mark.integration


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _start(app_name):
    app_dir = os.path.join(ROOT, "apps", app_name)
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, os.path.join(app_dir, "server.py"), str(port)],
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
        raise RuntimeError(app_name + " did not start")
    return proc, base, app_dir


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


@pytest.fixture(scope="module", params=list(APP_NAMES))
def app_server(request):
    proc, base, app_dir = _start(request.param)
    yield request.param, base, app_dir
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


@pytest.fixture()
def web(app_server):
    from ghostqa.executor.playwright_web import PlaywrightWebExecutor
    _name, base, _app_dir = app_server
    ex = PlaywrightWebExecutor(base, headless=True)
    yield ex
    ex.close()


def test_routes_serve_and_judge_hidden(app_server):
    name, base, app_dir = app_server
    pages = [p[0] for p in FAMILIES[name]["pages"]]
    for fname in pages:
        with urllib.request.urlopen(base + "/" + fname, timeout=3) as resp:
            assert resp.status == 200, fname
    for hidden in ("/bugs.manifest.json", "/topology.manifest.json"):
        with pytest.raises(Exception):
            urllib.request.urlopen(base + hidden, timeout=3)
    req = urllib.request.Request(base + "/api/echo", data=b"ping", method="POST")
    with urllib.request.urlopen(req, timeout=3) as resp:
        assert resp.status == 200
    fail = FAMILIES[name]["fail_path"]
    req = urllib.request.Request(base + fail, data=b"{}", method="POST")
    try:
        urllib.request.urlopen(req, timeout=3)
        assert False, fail
    except urllib.error.HTTPError as e:
        assert e.code == 500


def test_observe_home_reset_and_no_bug_ids(web, app_server):
    name, _base, _app_dir = app_server
    state = web.observe()
    assert "index.html" in state.url
    assert web.ground_truth() == {}
    html = web.page.content()
    assert FAMILIES[name]["prefix"] not in html
    assert "data-bug-id" not in html
    assert "bugs.manifest" not in html
    a = web.reset()
    b = web.reset()
    assert [e.eid for e in a.elements] == [e.eid for e in b.elements]
    assert dict(a.obs) == dict(b.obs)


def test_known_path_bugs(web, app_server):
    name, _base, app_dir = app_server
    spec = load_spec(os.path.join(app_dir, "spec.json"))
    oracle = OracleEngine(spec)
    if name == "buggy-crm":
        cases = [
            ([Action("click", "nav_settings"), Action("click", "btn_test_sync")],
             lambda fs: any(f.kind == "js_error" and "crm sync handshake" in f.evidence.get("error", "") for f in fs)),
            ([Action("click", "nav_pipeline")],
             lambda fs: any(f.kind == "blank" and "pipeline.html" in (f.evidence.get("url") or "") for f in fs)),
            ([Action("click", "nav_accounts"), Action("click", "account_a1"), Action("click", "btn_watch")],
             lambda fs: any(f.kind == "dead_action" and f.evidence.get("eid") == "btn_watch" for f in fs)),
            ([Action("click", "nav_help"), Action("click", "btn_handbook"), Action("click", "btn_help"),
              Action("click", "btn_handbook"), Action("click", "btn_help")],
             lambda fs: any(f.kind == "nav_loop" for f in fs)),
            ([Action("click", "nav_compose"), Action("click", "btn_create")],
             lambda fs: any(f.kind == "semantic" and f.evidence.get("assert_id") == "opp_title_required" for f in fs)),
            ([Action("click", "nav_accounts"), Action("click", "account_a1"), Action("click", "btn_pause_forecast")],
             lambda fs: any(f.kind == "semantic" and f.evidence.get("assert_id") == "forecast_display_matches_remaining" for f in fs)),
            ([Action("input", "search_box", "x" * 25), Action("click", "search_btn")],
             lambda fs: any(f.kind == "js_error" and "crm search query too long" in f.evidence.get("error", "") for f in fs)),
            ([Action("click", "nav_settings"), Action("click", "btn_export")],
             lambda fs: any(f.kind == "http_error" and "/api/export" in (f.evidence.get("error") or "") for f in fs)),
            ([Action("click", "nav_accounts"), Action("click", "account_a1"),
              Action("click", "btn_close"), Action("click", "btn_reopen")],
             lambda fs: any(f.kind == "semantic" and f.evidence.get("assert_id") == "reopen_clears_closed" for f in fs)),
            ([Action("click", "nav_accounts"), Action("click", "account_a1"),
              Action("click", "btn_internal_note"), Action("click", "nav_activity")],
             lambda fs: any(f.kind == "semantic" and f.evidence.get("assert_id") == "internal_note_not_customer_visible" for f in fs)),
        ]
        web.reset()
        web.execute(Action("click", "nav_accounts"))
        web.execute(Action("click", "account_a1"))
        r = web.execute(Action("click", "nav_back_accounts"))
        assert r.ok and r.state is not None and "accounts.html" in r.state.url
        web.reset()
        web.execute(Action("click", "nav_accounts"))
        web.execute(Action("click", "account_a1"))
        r = web.execute(Action("click", "related_a2"))
        assert r.ok and "id=a2" in r.state.url
    elif name == "buggy-wiki":
        cases = [
            ([Action("click", "nav_settings"), Action("click", "btn_test_plugin")],
             lambda fs: any(f.kind == "js_error" and "wiki plugin handshake" in f.evidence.get("error", "") for f in fs)),
            ([Action("click", "nav_search")],
             lambda fs: any(f.kind == "blank" and "search.html" in (f.evidence.get("url") or "") for f in fs)),
            ([Action("click", "nav_pages"), Action("click", "wiki_page_p1"), Action("click", "btn_watch")],
             lambda fs: any(f.kind == "dead_action" and f.evidence.get("eid") == "btn_watch" for f in fs)),
            ([Action("click", "nav_help"), Action("click", "btn_shortcuts"), Action("click", "btn_help"),
              Action("click", "btn_shortcuts"), Action("click", "btn_help")],
             lambda fs: any(f.kind == "nav_loop" for f in fs)),
            ([Action("click", "nav_editor"), Action("click", "btn_publish")],
             lambda fs: any(f.kind == "semantic" and f.evidence.get("assert_id") == "page_title_required" for f in fs)),
            ([Action("click", "nav_pages"), Action("click", "wiki_page_p1"), Action("click", "nav_history"),
              Action("click", "rev_r1"), Action("click", "btn_restore_rev")],
             lambda fs: any(f.kind == "semantic" and f.evidence.get("assert_id") == "display_rev_matches_restored" for f in fs)),
            ([Action("input", "search_box", "x" * 25), Action("click", "search_btn")],
             lambda fs: any(f.kind == "js_error" and "wiki search query too long" in f.evidence.get("error", "") for f in fs)),
            ([Action("click", "nav_settings"), Action("click", "btn_api_preview")],
             lambda fs: any(f.kind == "http_error" and "/api/preview" in (f.evidence.get("error") or "") for f in fs)),
            ([Action("click", "nav_pages"), Action("click", "wiki_page_p1"), Action("click", "btn_unpublish")],
             lambda fs: any(f.kind == "semantic" and f.evidence.get("assert_id") == "unpublish_clears_published" for f in fs)),
        ]
        web.reset()
        web.execute(Action("click", "nav_pages"))
        web.execute(Action("click", "wiki_page_p1"))
        web.execute(Action("click", "nav_history"))
        r = web.execute(Action("click", "rev_r1"))
        assert r.ok and "revision.html" in r.state.url
        r = web.execute(Action("click", "nav_back_history"))
        assert "history.html" in r.state.url
        r = web.execute(Action("click", "nav_back_page"))
        assert "page.html" in r.state.url
        web.reset()
        web.execute(Action("click", "nav_editor"))
        s1 = web.observe()
        web.execute(Action("click", "btn_preview"))
        s2 = web.observe()
        assert s1.url.split("?")[0] == s2.url.split("?")[0]
        assert s1.obs.get("preview_count") != s2.obs.get("preview_count")
        web.reset()
        web.execute(Action("click", "nav_pages"))
        web.execute(Action("click", "wiki_page_p1"))
        r = web.execute(Action("click", "backlink_p2"))
        assert r.ok and "id=p2" in r.state.url
    else:
        cases = [
            ([Action("click", "nav_settings"), Action("click", "btn_test_pager")],
             lambda fs: any(f.kind == "js_error" and "ops pager handshake" in f.evidence.get("error", "") for f in fs)),
            ([Action("click", "nav_teams")],
             lambda fs: any(f.kind == "blank" and "teams.html" in (f.evidence.get("url") or "") for f in fs)),
            ([Action("click", "nav_services"), Action("click", "service_svc1"),
              Action("click", "nav_service_incidents"), Action("click", "incident_i1"),
              Action("click", "btn_pin")],
             lambda fs: any(f.kind == "dead_action" and f.evidence.get("eid") == "btn_pin" for f in fs)),
            ([Action("click", "nav_help"), Action("click", "btn_playbook"), Action("click", "btn_help"),
              Action("click", "btn_playbook"), Action("click", "btn_help")],
             lambda fs: any(f.kind == "nav_loop" for f in fs)),
            ([Action("click", "nav_compose"), Action("click", "btn_create")],
             lambda fs: any(f.kind == "semantic" and f.evidence.get("assert_id") == "inc_title_required" for f in fs)),
            ([Action("click", "nav_alerts"), Action("click", "alert_al1"), Action("click", "btn_silence")],
             lambda fs: any(f.kind == "semantic" and f.evidence.get("assert_id") == "silence_display_matches_remaining" for f in fs)),
            ([Action("input", "search_box", "x" * 25), Action("click", "search_btn")],
             lambda fs: any(f.kind == "js_error" and "ops search query too long" in f.evidence.get("error", "") for f in fs)),
            ([Action("click", "nav_settings"), Action("click", "btn_page")],
             lambda fs: any(f.kind == "http_error" and "/api/page" in (f.evidence.get("error") or "") for f in fs)),
            ([Action("click", "nav_incidents"), Action("click", "incident_i1"),
              Action("click", "btn_ack"), Action("click", "btn_reopen")],
             lambda fs: any(f.kind == "semantic" and f.evidence.get("assert_id") == "reopen_clears_closed" for f in fs)),
        ]
        web.reset()
        web.execute(Action("click", "nav_services"))
        web.execute(Action("click", "service_svc1"))
        web.execute(Action("click", "nav_service_incidents"))
        web.execute(Action("click", "incident_i1"))
        r = web.execute(Action("click", "nav_back_incidents"))
        assert r.ok and "incidents.html" in r.state.url
        r = web.execute(Action("click", "nav_back_service"))
        assert "service.html" in r.state.url
        web.reset()
        web.execute(Action("click", "nav_incidents"))
        web.execute(Action("click", "incident_i1"))
        r = web.execute(Action("click", "related_i2"))
        assert r.ok and "id=i2" in r.state.url

    for actions, pred in cases:
        fs = run_steps(web, actions, oracle)
        assert pred(fs), (name, [a.target_eid for a in actions],
                          [(f.kind, f.evidence) for f in fs])
