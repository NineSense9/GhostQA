"""Exercise actual Dashboard cases and keep submission audit evidence.

No fixture results are used: each case starts through the real UI and saves
its own run ID, status, events, graph, bugs and HTML report.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CASES = ['cart', 'stock', 'register', 'profile', 'dead', 'script', 'blank', 'loop', 'catalog']
TERMINAL = {'done', 'partial', 'error', 'stopped'}


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def audit_layout(page):
    return page.evaluate("""() => {
        const b = s => document.querySelector(s).getBoundingClientRect().toJSON();
        return {
          width: innerWidth, height: innerHeight,
          horizontalOverflow: document.documentElement.scrollWidth > innerWidth + 2,
          viewport: b('.viewport-panel'), graph: b('.graph-panel'),
          legend: b('.graph-legend'), log: b('.log-panel'),
          cards: [...document.querySelectorAll('.bug')].map(el => ({
            height: el.clientHeight, content: el.scrollHeight,
            expanded: el.querySelector('.bug-head').getAttribute('aria-expanded')
          }))
        };
    }""")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--cases', default=','.join(CASES))
    parser.add_argument('--mock', action='store_true')
    parser.add_argument('--cart-repeats', type=int, default=1)
    parser.add_argument('--run-timeout', type=int, default=1800,
                        help='Whole-run wait limit; long ddmin runs can exceed four minutes.')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    rows, errors, console = [], [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={'width': 1280, 'height': 720})
        # External fonts aren't part of the application or layout evidence.
        context.route('**/fonts.googleapis.com/**', lambda route: route.fulfill(body=''))
        context.route('**/fonts.gstatic.com/**', lambda route: route.fulfill(body=''))
        page = context.new_page()
        page.on('pageerror', lambda exc: console.append(str(exc)))
        page.goto(args.url + '/#live', wait_until='domcontentloaded')
        for case in args.cases.split(','):
            for repeat in range(args.cart_repeats if case == 'cart' else 1):
                label = f'{case}-{repeat+1}'
                page.set_viewport_size({'width': 1280, 'height': 720})
                if page.locator('#run-form-card').evaluate("el => el.classList.contains('is-collapsed')"):
                    page.locator('#config-toggle').click()
                page.locator('#f-case').select_option(case)
                if args.mock:
                    page.locator('#f-mock').check()
                else:
                    page.locator('#f-mock').uncheck()
                with page.expect_response(lambda r: r.request.method == 'POST' and r.url.endswith('/api/runs')) as response:
                    page.locator('#btn-run').click()
                started = response.value.json()
                rid = started['run_id']
                dst = args.out / f'{label}-{rid}'
                dst.mkdir(exist_ok=True)
                print('START', label, rid, flush=True)
                deadline = time.monotonic() + args.run_timeout
                while time.monotonic() < deadline:
                    st = context.request.get(args.url + f'/api/runs/{rid}').json()
                    if st['status'] in TERMINAL:
                        break
                    page.wait_for_timeout(700)
                else:
                    errors.append(f'{label}: timed out, left running {rid}')
                    break
                page.wait_for_function("() => ['已完成','部分完成','出错','已停止'].includes(document.getElementById('r-status').textContent)", timeout=20000)
                page.wait_for_function("() => !document.getElementById('report-link').hidden", timeout=15000)
                write_json(dst / 'status.json', st)
                for endpoint in ('events', 'graph', 'bugs'):
                    write_json(dst / f'{endpoint}.json', context.request.get(args.url + f'/api/runs/{rid}/{endpoint}').json())
                report = context.request.get(args.url + f'/api/runs/{rid}/report.html')
                (dst / 'report.html').write_text(report.text(), encoding='utf-8')
                if report.status != 200:
                    errors.append(f'{label}: report HTTP {report.status}')
                if st['status'] not in ('done', 'partial'):
                    errors.append(f'{label}: status {st["status"]} {st.get("error")}')
                page.screenshot(path=str(dst / 'completed-1280.png'))
                layouts = []
                for width, height in ((1280,720), (1920,1080), (1366,768), (1024,768), (390,844)):
                    page.set_viewport_size({'width': width, 'height': height})
                    page.wait_for_timeout(550)
                    layout = audit_layout(page)
                    layouts.append(layout)
                    if layout['horizontalOverflow']:
                        errors.append(f'{label}: horizontal overflow {width}x{height}')
                    for card in layout['cards']:
                        if card['content'] > card['height'] + 2:
                            errors.append(f'{label}: clipped defect card {width}x{height}')
                    if width > 1180 and (layout['legend']['bottom'] > layout['graph']['bottom']+2 or layout['log']['bottom'] > height+2):
                        errors.append(f'{label}: clipped live panels {width}x{height}')
                    if case in ('cart','catalog'):
                        page.screenshot(path=str(dst / f'completed-{width}x{height}.png'))
                write_json(dst / 'layout.json', layouts)
                page.set_viewport_size({'width':1280,'height':720})
                page.reload(wait_until='domcontentloaded')
                page.wait_for_function("() => !document.getElementById('report-link').hidden", timeout=20000)
                restored = page.locator('#report-link').get_attribute('href') == f'/api/runs/{rid}/report.html'
                if not restored:
                    errors.append(f'{label}: refresh restored a different run')
                row = {'case':case,'run_id':rid,'status':st['status'],'cfg':st['cfg'],
                       'summary':st['summary'],'unfinished':st.get('unfinished'),
                       'report_http':report.status,'refresh_restored':restored}
                rows.append(row)
                write_json(args.out / 'summary.json', {'url':args.url,'runs':rows,'errors':errors,'page_errors':console})
                print('DONE', json.dumps(row, ensure_ascii=False), flush=True)
        browser.close()
    write_json(args.out / 'summary.json', {'url':args.url,'runs':rows,'errors':errors,'page_errors':console})
    if errors or console:
        raise SystemExit('\n'.join(errors+console))
    print('QA_OK', len(rows), 'actual runs', flush=True)


if __name__ == '__main__':
    main()
