"""Record one authentic multi-case GhostQA run and read-only views of the same run.

Difference from record.py: the run starts from the builtin case catalog with a
larger budget so a single run visits several cases. The continuous authenticity
unit ends when exploration hands over to replay, because replay/minimization can
take minutes and must not be trimmed into the exploration shot.

Outputs into artifacts/competition_video_ghostqa/multicase/:
  raw/            headed browser video (1920x1080)
  shots/          still screenshots of the same run
  run-identity.json, capture-marks.json, observations.json, run-status.json,
  events.json, graph.json, bugs.json, report.html, browser-qa.json
"""
from __future__ import annotations
import argparse, json, shutil, sys, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts' / 'competition_video_ghostqa'
SHA = '23739a72f3555f3c02e6c7bd0c559ae526689fbb'


def get(url):
    with urllib.request.urlopen(url, timeout=25) as r:
        return json.load(r)


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def remote_report(rid, dest):
    """Pull report.json from the deployed server. Best effort: never fatal."""
    try:
        sys.path.insert(0, r'C:\Users\57219\AgentDock\ghostqa-server-deploy')
        import ssh_run
        client, _ = ssh_run.connect()
        try:
            sftp = client.open_sftp()
            with sftp.open('/opt/ghostqa/app/dashboard_runs/' + rid + '/report.json', 'rb') as f:
                dest.write_bytes(f.read())
            sftp.close()
        finally:
            client.close()
        return True
    except Exception as exc:
        print('REMOTE_REPORT_SKIPPED', str(exc)[:200], flush=True)
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='http://39.106.200.173:8787')
    ap.add_argument('--case', default='catalog')
    ap.add_argument('--url', default=None, help='defaults to <base>/cases/index.html')
    ap.add_argument('--budget', type=int, default=30)
    ap.add_argument('--explore-timeout', type=float, default=150,
                    help='seconds to wait for exploration to hand over to replay')
    ap.add_argument('--wait-seconds', type=float, default=960,
                    help='total seconds to wait for a terminal run state')
    ap.add_argument('--cancel-after', type=float, default=840,
                    help='cancel the run after this many seconds so it finalizes')
    ap.add_argument('--kind', default='multicase')
    args = ap.parse_args()
    base = args.base.rstrip('/')
    url = args.url or base + '/cases/index.html'
    folder = OUT / args.kind
    folder.mkdir(parents=True, exist_ok=True)
    shots = folder / 'shots'; shots.mkdir(exist_ok=True)
    profile = folder / ('profile-' + str(int(time.time())))
    marks, observations, errors = [], [], []
    with sync_playwright() as pw:
        ctx = None
        channel = None
        for channel in ['msedge', 'chrome', None]:
            try:
                ctx = pw.chromium.launch_persistent_context(
                    str(profile), channel=channel, headless=False,
                    viewport={'width': 1920, 'height': 1080}, device_scale_factor=1,
                    record_video_dir=str(folder / 'raw'),
                    record_video_size={'width': 1920, 'height': 1080},
                    args=['--no-first-run', '--disable-infobars', '--window-size=1940,1200'],
                )
                print('RECORDING_CHANNEL', channel or 'chromium', flush=True)
                break
            except Exception as exc:
                errors.append({'channel': channel, 'launch_error': str(exc)[:240]})
        if ctx is None:
            raise RuntimeError('No recording browser available')
        page = ctx.pages[0]
        origin = time.monotonic()
        page.on('pageerror', lambda e: errors.append({'page_error': str(e)}))

        def mark(name):
            marks.append({'name': name, 'seconds': round(time.monotonic() - origin, 3), 'url': page.url})
            save(folder / 'capture-marks.json', marks)
            print('MARK', name, marks[-1]['seconds'], flush=True)

        def shot(name):
            page.screenshot(path=str(shots / (name + '.png')))
            mark(name)

        def hold(seconds):
            page.wait_for_timeout(int(seconds * 1000))

        def scroll_to(selector):
            page.locator(selector).scroll_into_view_if_needed()
            hold(1.2)

        try:
            page.goto(base + '/#live', wait_until='domcontentloaded', timeout=45000)
            page.wait_for_function('() => window.GhostQA !== undefined')
            page.locator('#f-case').select_option(args.case)
            page.locator('#f-url').fill(url)
            page.locator('#f-policy').select_option('ghost')
            page.locator('#f-budget').fill(str(args.budget))
            page.locator('#f-mock').uncheck()
            cfg = page.evaluate("""() => ({url:document.querySelector('#f-url').value,
              spec:document.querySelector('#f-spec').value,policy:document.querySelector('#f-policy').value,
              budget:Number(document.querySelector('#f-budget').value),mock_llm:document.querySelector('#f-mock').checked})""")
            assert cfg['policy'] == 'ghost' and cfg['budget'] == args.budget and not cfg['mock_llm'], cfg
            assert cfg['url'].endswith('/cases/index.html'), cfg
            shot('config')
            hold(30)
            with page.expect_response(lambda r: '/api/run' in r.url and r.request.method == 'POST') as resp:
                mark('start_click')
                page.locator('#btn-run').click()
            start = resp.value.json()
            rid = start['run_id']
            save(folder / 'run-identity.json', {'run_id': rid, 'source_sha': SHA, 'base_url': base,
                 'recording_browser': channel or 'chromium', 'executor_browser': 'Playwright Chromium',
                 'executor_location': 'server' if '39.106.200.173' in base else 'local', 'cfg': cfg})
            print('RUN_ID', rid, flush=True)

            # Phase 1: watch the continuous run until exploration hands over to replay.
            unit_end = None
            deadline = time.monotonic() + args.explore_timeout
            saved_first = False
            while time.monotonic() < deadline:
                st = get(base + '/api/runs/' + rid)
                observations.append({'video_seconds': round(time.monotonic() - origin, 3),
                                     'status': st['status'], 'phase': st.get('phase'),
                                     'event_count': st.get('events'), 'summary': st.get('summary')})
                if not saved_first and (st.get('events') or 0) > 0:
                    shot('exploring'); saved_first = True
                if st.get('phase') in ('replay', 'minimizing', 'report') or st['status'] in (
                        'done', 'partial', 'error', 'stopped'):
                    mark('authentic_unit_end'); unit_end = marks[-1]['seconds']
                    break
                hold(.35)
            if unit_end is None:
                mark('authentic_unit_end'); unit_end = marks[-1]['seconds']

            # Phase 2: let replay/minimization finish; cancel early enough to finalize.
            cancelled = False
            hard = time.monotonic() + args.wait_seconds
            while time.monotonic() < hard:
                st = get(base + '/api/runs/' + rid)
                if st['status'] in ('done', 'partial', 'error', 'stopped'):
                    break
                if args.cancel_after and (time.monotonic() - origin) > args.cancel_after and not cancelled:
                    try:
                        req = urllib.request.Request(base + '/api/runs/%s/cancel' % rid,
                                                     data=b'', method='POST')
                        urllib.request.urlopen(req, timeout=30).read()
                        cancelled = True
                        print('CANCEL_SENT', round(time.monotonic() - origin, 1), flush=True)
                    except Exception as exc:
                        print('CANCEL_ERR', str(exc)[:160], flush=True)
                hold(2.0)
            else:
                st = get(base + '/api/runs/' + rid)
            save(folder / 'observations.json', observations)
            save(folder / 'run-status.json', st)
            for route, name in [('events', 'events.json'), ('graph', 'graph.json'), ('bugs', 'bugs.json')]:
                save(folder / name, get(base + '/api/runs/' + rid + '/' + route))
            print('RUN_END', st['status'], st.get('phase'), flush=True)
            if '39.106.200.173' in base:
                remote_report(rid, folder / 'report.json')
            else:
                src = ROOT / 'dashboard_runs' / rid / 'report.json'
                if src.is_file():
                    shutil.copy2(src, folder / 'report.json')

            # Phase 3: read-only review of the same stored run.
            hold(3)
            rows = page.locator('#log .log-row')
            if rows.count():
                rows.first.click(); hold(1)
                page.evaluate('window.scrollTo(0,0)'); hold(1)
                shot('first_action'); hold(7)
            if page.locator('#ai-readout').is_visible():
                scroll_to('#ai-readout'); shot('ai_observation'); hold(7)
            scroll_to('#bugs'); shot('confirmed_card'); hold(7)
            body = page.locator('.bug-body').first
            if body.count():
                body.hover(); page.mouse.wheel(0, 280); hold(2)
                shot('confirmed_path'); hold(5)
            scroll_to('#phase-records')
            page.locator('#phase-records').hover(); page.mouse.wheel(0, 420); hold(2)
            shot('phase_records'); hold(9)
            page.evaluate('window.scrollTo(0,0)'); hold(1)
            shot('dashboard_review'); hold(5)
            shot('completed'); mark('run_review_end')

            with page.expect_popup() as popup:
                mark('open_report'); page.locator('#report-link').click()
            report_page = popup.value
            report_origin = time.monotonic() - origin
            report_page.wait_for_load_state('domcontentloaded')
            report_page.screenshot(path=str(shots / 'report_top.png'))
            marks.append({'name': 'report_top', 'seconds': round(time.monotonic() - origin, 3), 'url': report_page.url})
            save(folder / 'capture-marks.json', marks)
            hold(12)
            report_page.evaluate('window.scrollTo(0,470)'); hold(2)
            report_page.screenshot(path=str(shots / 'report_detail.png'))
            marks.append({'name': 'report_detail', 'seconds': round(time.monotonic() - origin, 3), 'url': report_page.url})
            hold(14)
            report_page.evaluate('window.scrollTo(0,document.body.scrollHeight)'); hold(1)
            report_page.screenshot(path=str(shots / 'report_bottom.png'))
            hold(10)
            (folder / 'report.html').write_text(report_page.content(), encoding='utf-8')
            report_video = report_page.video
            report_page.close()
            save(folder / 'report-video.json', {'path': str(report_video.path()),
                 'origin_seconds': report_origin, 'run_id': rid})
            page.bring_to_front()
            page.reload(wait_until='domcontentloaded'); hold(4)
            same = page.evaluate("sessionStorage.getItem('ghostqa-run')")
            save(folder / 'restore-check.json', {'expected': rid, 'restored': same,
                 'reserved_path_open': True})
            shot('restored_same_run'); hold(6)
            page.locator('[data-view="evidence"]').first.click(); hold(3)
            shot('research'); hold(10)
            page.locator('[data-view="live"]').first.click(); hold(2)
            scroll_to('#bugs'); shot('ending'); hold(7)
            save(folder / 'capture-marks.json', marks)
            save(folder / 'browser-qa.json', {'console_errors': errors, 'refresh_same_run': rid,
                 'restored_same_run': same, 'unit_end_seconds': unit_end,
                 'final_status': st['status'], 'cancelled': cancelled})
            mark('recording_end')
            video = page.video
            ctx.close()
            if video:
                save(folder / 'video.json', {'path': str(video.path()), 'marks': marks})
            print('CAPTURE_FINISHED', args.kind, rid, st['status'], flush=True)
        except Exception:
            save(folder / 'capture-marks.json', marks)
            save(folder / 'browser-errors.json', errors)
            if ctx:
                ctx.close()
            raise


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
