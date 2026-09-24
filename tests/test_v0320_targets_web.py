"""Known-path checks for v0.3.20 apps. Does not run C1, G, or F."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

from ghostqa.exploration.sequence import branch_clicks, is_hub
from ghostqa.oracle.engine import OracleEngine
from ghostqa.oracle.spec import load_spec
from ghostqa.state.models import Action
from ghostqa.state.signature import state_signature
from benchmark.fresh_composite_generator import APP_NAMES, ROOT
from benchmark.fresh_composite_vocab import FAMILIES
from benchmark.runner import evidence_matches

pytestmark = pytest.mark.integration


def _free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
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


def _parse_step(step):
    _page, action = step.split(": ", 1)
    action = action.strip()
    if "=" in action and action.endswith("chars"):
        testid, rest = action.split("=", 1)
        count = int(rest.split()[0])
        return Action("input", testid.strip(), "x" * count)
    return Action("click", action)


def _run(ex, steps, oracle):
    state = ex.reset()
    hist = [state_signature(state)]
    sig_url = {hist[0]: state.url}
    findings = []
    for index, step in enumerate(steps):
        action = _parse_step(step)
        result = ex.execute(action)
        new = result.state if not result.crashed else None
        findings.extend(oracle.inspect(state, action, result, new, {
            "step_index": index,
            "history_sigs": hist,
            "ground_truth": {},
            "sig_url_map": sig_url,
            "effective_clicks": set(),
        }))
        if result.crashed or new is None:
            break
        sig = state_signature(new)
        hist.append(sig)
        sig_url[sig] = new.url
        state = new
    return findings


@pytest.fixture(params=list(APP_NAMES))
def app_server(request):
    proc, base, app_dir = _start(request.param)
    yield request.param, base, app_dir
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


def test_routes_and_judge_files_hidden(app_server):
    name, base, app_dir = app_server
    topo = json.load(open(os.path.join(app_dir, "topology.json"), encoding="utf-8"))
    pages = sorted({node["page"] for node in topo["nodes"]})
    for fname in pages:
        with urllib.request.urlopen(base + "/" + fname, timeout=3) as resp:
            assert resp.status == 200, fname
    for hidden in (
        "/bugs.manifest.json", "/topology.json", "/generation.json",
        "/spec.json", "/mechanism-opportunities.json",
    ):
        with pytest.raises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(base + hidden, timeout=3)
        assert caught.value.code == 404
    req = urllib.request.Request(base + "/api/export", data=b"{}", method="POST")
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(req, timeout=3)
    assert caught.value.code == 500


def test_declared_hubs_match_live_branch_clicks(app_server):
    name, base, app_dir = app_server
    from ghostqa.executor.playwright_web import PlaywrightWebExecutor
    topo = json.load(open(os.path.join(app_dir, "topology.json"), encoding="utf-8"))
    web = PlaywrightWebExecutor(base, headless=True)
    try:
        for node in topo["nodes"]:
            if node.get("blank"):
                continue
            url = "/" + node["page"]
            if node.get("entity"):
                url += "?id=" + node["entity"]
            web._goto(base + url)
            state = web.observe()
            assert is_hub(state) is bool(node["hub"]), (name, node["id"], is_hub(state), node["hub"])
            clicks = branch_clicks(state)
            if node.get("first_branch_action"):
                assert clicks, node["id"]
                assert clicks[0].target_eid == node["first_branch_action"], (
                    name, node["id"], clicks[0].target_eid, node["first_branch_action"])
        home = web.reset()
        text = web.page.content()
        assert FAMILIES[name]["prefix"] not in text
        assert "BUG-" not in text
        assert "finding_return" not in text
        assert home.elements
    finally:
        web.close()


def test_manifest_minimum_paths_confirm(app_server):
    name, _base, app_dir = app_server
    from ghostqa.executor.playwright_web import PlaywrightWebExecutor
    spec = load_spec(os.path.join(app_dir, "spec.json"))
    bugs = json.load(open(os.path.join(app_dir, "bugs.manifest.json"), encoding="utf-8"))["bugs"]
    oracle = OracleEngine(spec)
    web = PlaywrightWebExecutor(_base, headless=True)
    try:
        for bug in bugs:
            findings = _run(web, bug["min_reproduction"], oracle)
            ok = any(
                finding.kind == bug["kind"] and evidence_matches(finding.evidence, bug["match"])
                for finding in findings
            )
            assert ok, (name, bug["id"], [(f.kind, f.evidence) for f in findings])
    finally:
        web.close()
