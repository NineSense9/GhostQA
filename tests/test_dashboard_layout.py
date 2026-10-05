"""Browser regressions for evidence that must remain readable in the live UI.

Rendering fixtures exercise the real HTML/CSS/controller without a model call.
They are layout inputs, not results from an exploration run.
"""
import base64
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

import pytest
from playwright.sync_api import sync_playwright

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def dashboard_url(tmp_path_factory):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    runs = str(tmp_path_factory.mktemp("layout-runs"))
    code = (
        "import sys,uvicorn; from dashboard import server; "
        "server.RUNS_DIR=sys.argv[1]; "
        "uvicorn.run(server.app,host='127.0.0.1',port=int(sys.argv[2]),log_level='error')"
    )
    proc = subprocess.Popen([sys.executable, "-c", code, runs, str(port)], cwd=ROOT,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(60):
            try:
                urlopen(base, timeout=1).close()
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("layout dashboard did not start")
        yield base
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def live_page(browser, dashboard_url):
    page = browser.new_page(viewport={"width": 1280, "height": 720})
    page.route("**/fonts.googleapis.com/**", lambda route: route.fulfill(body=""))
    page.route("**/fonts.gstatic.com/**", lambda route: route.abort())
    page.goto(dashboard_url + "/cases/cart.html")
    screenshot = "data:image/png;base64," + base64.b64encode(page.screenshot()).decode()
    page.goto(dashboard_url + "/#live")
    page.wait_for_function("typeof renderBugs === 'function'")
    bug = {
        "finding": {
            "kind": "semantic", "description": "购物车总价与商品金额不一致",
            "evidence": {"url": dashboard_url + "/cases/cart.html",
                         "assert_id": "case_cart_total_consistent",
                         "obs": {"cart_item_price": "5", "cart_total": "12",
                                 "cart_note": "已刷新"}},
        },
        "original_length": 1,
        "reproduction": [{"type": "click", "target_eid": "btn_refresh", "label": "刷新合计"}],
    }
    page.evaluate("""({bug, screenshot}) => {
        S.runId = 'layout-fixture'; S.status = 'done';
        setBarStatus('done');
        showComplete({status: 'done', summary: {actions: 6, states: 2, confirmed: 1}});
        renderBugs([bug], [], 'done');
        showShot(screenshot, '布局检查用案例截图');
    }""", {"bug": bug, "screenshot": screenshot})
    page.wait_for_function("document.getElementById('shot').naturalWidth > 0")
    yield page
    page.close()


@pytest.mark.parametrize("width,height", [(1280, 720), (1920, 1080), (1024, 768), (390, 844)])
def test_expanded_bug_keeps_all_evidence_and_path(live_page, width, height):
    page = live_page
    page.set_viewport_size({"width": width, "height": height})
    evidence = page.locator(".bug.is-open")
    sizes = evidence.evaluate("el => ({client: el.clientHeight, scroll: el.scrollHeight})")
    assert sizes["scroll"] <= sizes["client"] + 2, "expanded defect evidence is clipped"
    path = evidence.locator(".repro-steps li").last
    path.scroll_into_view_if_needed()
    bounds = path.bounding_box()
    assert bounds and bounds["y"] >= 0 and bounds["y"] + bounds["height"] <= height + 2


def test_expanded_bug_reports_correct_accessibility_state(live_page):
    head = live_page.locator(".bug-head").first
    assert head.get_attribute("aria-expanded") == "true"
    head.click()
    assert head.get_attribute("aria-expanded") == "false"
    head.press("Enter")
    assert head.get_attribute("aria-expanded") == "true"


@pytest.mark.parametrize("width,height", [(1280, 720), (1920, 1080), (1024, 768)])
def test_live_panels_do_not_overlap_or_leave_screen(live_page, width, height):
    page = live_page
    page.set_viewport_size({"width": width, "height": height})
    bounds = page.evaluate("""() => {
        const box = s => document.querySelector(s).getBoundingClientRect().toJSON();
        return {viewport: box('.viewport-panel'), action: box('.action-result'),
            graph: box('.graph-panel'), legend: box('.graph-legend'), log: box('.log-panel')};
    }""")
    assert bounds["viewport"]["bottom"] <= bounds["action"]["top"] + 2
    assert bounds["legend"]["bottom"] <= bounds["graph"]["bottom"] + 2
    assert bounds["graph"]["bottom"] <= bounds["log"]["top"] + 2
    if width > 1180:
        assert bounds["log"]["bottom"] <= height + 2


def test_default_screenshot_is_complete_and_zoom_can_scroll(live_page):
    page = live_page
    assert "is-zoomed" not in page.locator("#viewport").get_attribute("class")
    info = page.locator("#shot").evaluate("""el => ({fit: getComputedStyle(el).objectFit,
        image: el.getBoundingClientRect().toJSON(),
        viewport: el.parentElement.getBoundingClientRect().toJSON()})""")
    assert info["fit"] == "contain"
    assert info["image"]["height"] <= info["viewport"]["height"] + 2
    page.locator("#shot-zoom").click()
    assert page.locator("#viewport").evaluate("el => getComputedStyle(el).overflowY") == "auto"
    page.locator("#shot-zoom").click()
    assert "is-zoomed" not in page.locator("#viewport").get_attribute("class")


@pytest.mark.parametrize("phase,status,expected", [
    ("candidate", "ready", "待验证"),
    ("replay", "running", "重放中"),
    ("minimizing", "running", "最小化中"),
])
def test_phase_record_describes_its_own_stage(live_page, phase, status, expected):
    live_page.evaluate("ev => appendPhaseRecord(ev)",
                       {"type": "phase", "phase": phase, "status": status})
    assert expected in live_page.locator("#phase-records").inner_text()


def test_completed_result_focuses_the_card_in_its_own_scroll_area(live_page):
    page = live_page
    page.evaluate("document.querySelector('.col-right').scrollTop = 10000")
    page.evaluate("focusConfirmedBugs()")
    top = page.evaluate("""() => ({
        rail: document.querySelector('.col-right').getBoundingClientRect().top,
        card: document.getElementById('bug-card').getBoundingClientRect().top
    })""")
    assert abs(top['rail'] - top['card']) <= 2


def test_large_graph_fits_all_nodes_after_layout_and_resize(live_page):
    page = live_page
    page.evaluate("""() => {
        const nodes = Array.from({length: 12}, (_, i) => ({
            sig: 'layout-node-' + i, title: '案例页面 ' + i,
            relation: 'NEW', visits: 1, flags: []
        }));
        const edges = nodes.slice(1).map((n, i) => ({
            src: nodes[i].sig, dst: n.sig, action_key: 'layout-click-' + i
        }));
        syncGraph({nodes, edges});
    }""")
    for width, height in [(1280, 720), (1920, 1080), (390, 844), (1280, 720)]:
        page.set_viewport_size({'width': width, 'height': height})
        page.wait_for_timeout(550)
        bounds = page.evaluate("""() => ({
            nodes: S.cy.nodes().renderedBoundingBox(),
            width: S.cy.width(), height: S.cy.height()
        })""")
        assert bounds['nodes']['x1'] >= -1, bounds
        assert bounds['nodes']['y1'] >= -1, bounds
        assert bounds['nodes']['x2'] <= bounds['width'] + 1, bounds
        assert bounds['nodes']['y2'] <= bounds['height'] + 1, bounds


@pytest.mark.parametrize('width,height', [(1280, 720), (390, 844)])
def test_report_keeps_evidence_and_table_inside_page(browser, width, height):
    from ghostqa.report.generator import render_html

    report = {
        'app': 'web:127.0.0.1:8787/cases/index.html', 'policy': 'ghost',
        'summary': dict(actions_executed=40, states_discovered=12, candidate_findings=1,
                        confirmed_bugs=1, llm_calls=2, pseudo_tokens=0, wall_seconds=10),
        'bugs': [{'finding': {'kind': 'semantic', 'severity': 'high',
                  'description': '购物车总价与商品金额不一致',
                  'evidence': {'url': 'http://127.0.0.1:8787/cases/cart.html',
                               'assert_id': 'case_cart_total_consistent',
                               'obs': {'cart_item_price': '5', 'cart_total': '12'}}},
                  'original_length': 1,
                  'reproduction': [{'type': 'click', 'target_eid': 'btn_refresh', 'label': '刷新合计'}]}],
    }
    page = browser.new_page(viewport={'width': width, 'height': height})
    try:
        page.set_content(render_html(report))
        bounds = page.evaluate('''() => ({width: innerWidth,
            documentWidth: document.documentElement.scrollWidth,
            viewportMeta: !!document.querySelector('meta[name=viewport]'),
            clipped: [...document.querySelectorAll('.card')].some(e => e.scrollWidth > e.clientWidth + 2)
        })''')
        assert bounds['viewportMeta'], bounds
        assert bounds['documentWidth'] <= width + 2, bounds
        assert not bounds['clipped'], bounds
        assert '已重放确认' in page.locator('body').inner_text()
    finally:
        page.close()
