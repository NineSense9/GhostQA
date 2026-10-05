"""Record one authentic GhostQA run and read-only views of the same run."""
from __future__ import annotations
import argparse, hashlib, json, shutil, sys, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts' / 'competition_video_ghostqa'
SHA = '23739a72f3555f3c02e6c7bd0c559ae526689fbb'

def get(url):
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.load(r)

def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')

def remote_report(rid, dest):
    sys.path.insert(0, r'C:\Users\57219\AgentDock\ghostqa-server-deploy')
    import ssh_run
    client, _ = ssh_run.connect()
    try:
        sftp = client.open_sftp()
        with sftp.open('/opt/ghostqa/app/dashboard_runs/' + rid + '/report.json', 'rb') as f:
            data = f.read()
        dest.write_bytes(data)
        sftp.close()
    finally:
        client.close()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='http://39.106.200.173:8787')
    ap.add_argument('--kind', choices=['rehearsal','formal'], required=True)
    args = ap.parse_args()
    base = args.base.rstrip('/')
    folder = OUT / args.kind
    folder.mkdir(parents=True, exist_ok=True)
    shots = folder / 'shots'; shots.mkdir(exist_ok=True)
    profile = folder / ('profile-' + str(int(time.time())))
    marks, observations, errors = [], [], []
    with sync_playwright() as pw:
        ctx = None
        for channel in ['msedge','chrome',None]:
            try:
                ctx = pw.chromium.launch_persistent_context(
                    str(profile), channel=channel, headless=False,
                    viewport={'width':1920,'height':1080}, device_scale_factor=1,
                    record_video_dir=str(folder/'raw') if args.kind=='formal' else None,
                    record_video_size={'width':1920,'height':1080} if args.kind=='formal' else None,
                    args=['--no-first-run','--disable-infobars','--window-size=1940,1200'],
                )
                print('RECORDING_CHANNEL',channel or 'chromium',flush=True)
                break
            except Exception as exc:
                errors.append({'channel':channel,'launch_error':str(exc)[:240]})
        if ctx is None: raise RuntimeError('No recording browser available')
        # Persistent context creates a blank tab. Only the product tab is recorded.
        page = ctx.pages[0]
        origin = time.monotonic()
        page.on('pageerror',lambda e: errors.append({'page_error':str(e)}))
        def mark(name):
            marks.append({'name':name,'seconds':round(time.monotonic()-origin,3),'url':page.url})
            save(folder/'capture-marks.json', marks)
            print('MARK',name,marks[-1]['seconds'],flush=True)
        def shot(name):
            page.screenshot(path=str(shots/(name+'.png')))
            mark(name)
        def hold(seconds): page.wait_for_timeout(int(seconds*1000))
        def scroll_to(selector):
            page.locator(selector).scroll_into_view_if_needed()
            hold(1.2)
        try:
            page.goto(base+'/#live',wait_until='domcontentloaded',timeout=45000)
            page.wait_for_function('() => window.GhostQA !== undefined')
            page.locator('#f-case').select_option('cart')
            page.locator('#f-url').fill(base+'/cases/cart.html')
            page.locator('#f-policy').select_option('ghost')
            page.locator('#f-budget').fill('6')
            page.locator('#f-mock').uncheck()
            cfg = page.evaluate("""() => ({url:document.querySelector('#f-url').value,
              spec:document.querySelector('#f-spec').value,policy:document.querySelector('#f-policy').value,
              budget:Number(document.querySelector('#f-budget').value),mock_llm:document.querySelector('#f-mock').checked})""")
            assert cfg['policy']=='ghost' and cfg['budget']==6 and not cfg['mock_llm']
            shot('config')
            hold(28 if args.kind=='formal' else 1)
            # The sole start action for this take is the visible Dashboard button.
            with page.expect_response(lambda r:'/api/run' in r.url and r.request.method=='POST') as resp:
                mark('start_click')
                page.locator('#btn-run').click()
            start = resp.value.json()
            rid = start['run_id']
            save(folder/'run-identity.json', {'run_id':rid,'source_sha':SHA,'base_url':base,
                'recording_browser':channel or 'chromium','executor_browser':'Playwright Chromium',
                'executor_location':'server' if '39.106.200.173' in base else 'local', 'cfg':cfg})
            print('RUN_ID',rid,flush=True)
            deadline=time.monotonic()+180
            saved_first=False
            while time.monotonic()<deadline:
                st=get(base+'/api/runs/'+rid)
                observations.append({'video_seconds':round(time.monotonic()-origin,3),'status':st['status'],
                    'phase':st.get('phase'),'event_count':st.get('events'), 'summary':st.get('summary')})
                if not saved_first and (st.get('events') or 0)>0:
                    shot('exploring'); saved_first=True
                if st['status'] in ['done','partial','error','stopped']: break
                hold(.35)
            else: raise RuntimeError('Formal run did not finish within observation limit')
            save(folder/'observations.json', observations)
            save(folder/'run-status.json',st)
            for route,name in [('events','events.json'),('graph','graph.json'),('bugs','bugs.json')]:
                save(folder/name,get(base+'/api/runs/'+rid+'/'+route))
            if st['status']!='done': raise RuntimeError('Take ended '+st['status']+'; retain as unsuccessful take')
            if '39.106.200.173' in base: remote_report(rid,folder/'report.json')
            else: shutil.copy2(ROOT/'dashboard_runs'/rid/'report.json',folder/'report.json')
            hold(4)
            shot('completed'); mark('authentic_unit_end')
            # Everything below is UI review, showing the same stored run.
            if args.kind=='formal':
                hold(8)
                rows=page.locator('#log .log-row')
                if rows.count():
                    rows.first.click(); hold(1)
                    page.evaluate('window.scrollTo(0,0)'); hold(1)
                    shot('first_action'); hold(8)
                if page.locator('#ai-readout').is_visible():
                    scroll_to('#ai-readout'); shot('ai_observation'); hold(8)
                scroll_to('#bugs'); shot('confirmed_card'); hold(8)
                body=page.locator('.bug-body').first
                body.hover(); page.mouse.wheel(0,280); hold(2)
                shot('confirmed_path'); hold(5)
                scroll_to('#phase-records')
                page.locator('#phase-records').hover(); page.mouse.wheel(0,400); hold(2)
                shot('phase_records'); hold(10)
                page.evaluate('window.scrollTo(0,0)'); hold(1)
                shot('dashboard_review'); hold(6)
                with page.expect_popup() as popup:
                    mark('open_report'); page.locator('#report-link').click()
                report_page=popup.value
                report_origin=time.monotonic()-origin
                report_page.wait_for_load_state('domcontentloaded')
                report_page.screenshot(path=str(shots/'report_top.png'))
                marks.append({'name':'report_top','seconds':round(time.monotonic()-origin,3),'url':report_page.url})
                hold(12)
                report_page.evaluate('window.scrollTo(0,450)'); hold(2)
                report_page.screenshot(path=str(shots/'report_detail.png'))
                marks.append({'name':'report_detail','seconds':round(time.monotonic()-origin,3),'url':report_page.url})
                hold(14)
                report_page.evaluate('window.scrollTo(0,document.body.scrollHeight)'); hold(1)
                report_page.screenshot(path=str(shots/'report_bottom.png'))
                hold(10)
                report_html=report_page.content()
                (folder/'report.html').write_text(report_html,encoding='utf-8')
                report_video=report_page.video
                report_page.close()
                save(folder/'report-video.json',{'path':str(report_video.path()),'origin_seconds':report_origin,
                    'run_id':rid})
                page.bring_to_front()
                page.reload(wait_until='domcontentloaded'); hold(4)
                assert page.evaluate("sessionStorage.getItem('ghostqa-run')")==rid
                shot('restored_same_run'); hold(7)
                # Public research evidence, independently labeled, is not a product-run score.
                page.locator('[data-view="evidence"]').first.click(); hold(3)
                shot('research'); hold(12)
                page.locator('[data-view="live"]').first.click(); hold(2)
                scroll_to('#bugs'); shot('ending'); hold(8)
            save(folder/'capture-marks.json',marks)
            save(folder/'browser-qa.json',{'console_errors':errors,'refresh_same_run':rid})
            mark('recording_end')
            video=page.video
            ctx.close()
            if video: save(folder/'video.json',{'path':str(video.path()),'marks':marks})
            print('CAPTURE_FINISHED',args.kind,rid,flush=True)
        except Exception:
            save(folder/'capture-marks.json',marks); save(folder/'browser-errors.json',errors)
            if ctx: ctx.close()
            raise

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8'); main()
