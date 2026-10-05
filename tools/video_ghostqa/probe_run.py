"""Probe one real Dashboard run and report how it ends.

Usage:
  python tools/video_ghostqa/probe_run.py --url http://.../cases/index.html --budget 15 \
      --out artifacts/competition_video_ghostqa/probe.json [--cancel-after 300]

Prints a progress line per poll and, at the end, a JSON block with the terminal
state plus candidates / confirmed bugs collected from the run API. Never edits
the run config; the only mutating call is an optional cancel of its own run.
"""
from __future__ import annotations
import argparse, json, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _post(base, path, obj=None):
    data = b'' if obj is None else json.dumps(obj).encode()
    req = urllib.request.Request(base + path, data=data,
                                 headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=40) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='http://39.106.200.173:8787')
    ap.add_argument('--url', default=None, help='page url; defaults to <base>/cases/index.html')
    ap.add_argument('--policy', default='ghost')
    ap.add_argument('--budget', type=int, default=15)
    ap.add_argument('--spec', default='apps/builtin-cases/spec.json')
    ap.add_argument('--mock', action='store_true')
    ap.add_argument('--max-seconds', type=float, default=600)
    ap.add_argument('--cancel-after', type=float, default=0,
                    help='if >0, cancel the run once it has run this long')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    base = args.base.rstrip('/')
    cfg = {'url': args.url or base + '/cases/index.html', 'policy': args.policy,
           'budget': args.budget, 'spec': args.spec, 'mock_llm': args.mock}
    start = _post(base, '/api/runs', cfg)
    rid = start.get('run_id') or start.get('id')
    print('RUN', rid, json.dumps(cfg, ensure_ascii=False), flush=True)

    t0 = time.monotonic()
    cancelled = False
    st = {}
    while True:
        elapsed = time.monotonic() - t0
        try:
            st = _get(base, '/api/runs/' + rid)
        except Exception as exc:  # keep probing through a transient hiccup
            print(round(elapsed, 1), 'poll-error', str(exc)[:120], flush=True)
            time.sleep(4)
            continue
        s = st.get('summary') or {}
        print(round(elapsed, 1), st['status'], st.get('phase'), 'ev', st.get('events'),
              'act', s.get('actions'), 'st', s.get('states'), 'cand', s.get('candidates'),
              'conf', s.get('confirmed'), flush=True)
        if st['status'] in ('done', 'partial', 'error', 'stopped'):
            break
        if args.cancel_after and elapsed > args.cancel_after and not cancelled:
            try:
                _post(base, '/api/runs/%s/cancel' % rid)
                cancelled = True
                print('CANCEL_SENT', round(elapsed, 1), flush=True)
            except Exception as exc:
                print('CANCEL_ERR', str(exc)[:120], flush=True)
        if elapsed > args.max_seconds:
            print('MAX_SECONDS_REACHED', round(elapsed, 1), flush=True)
            break
        time.sleep(4)

    out = {'run_id': rid, 'cfg': cfg, 'final_status': st.get('status'),
           'phase': st.get('phase'), 'events': st.get('events'),
           'summary': st.get('summary'), 'cancelled': cancelled,
           'wall_seconds': round(time.monotonic() - t0, 1)}
    for route, key in (('candidates', 'candidates'), ('bugs', 'bugs'), ('graph', 'graph')):
        try:
            out[key] = _get(base, '/api/runs/%s/%s' % (rid, route))
        except Exception as exc:
            out[key] = {'error': str(exc)[:160]}
    print('RESULT ' + json.dumps({k: out[k] for k in
          ('run_id', 'final_status', 'phase', 'events', 'summary', 'cancelled', 'wall_seconds')},
          ensure_ascii=False), flush=True)
    if isinstance(out.get('bugs'), list):
        print('BUGS', len(out['bugs']), flush=True)
        for b in out['bugs']:
            f = b.get('finding', {})
            print('  -', f.get('kind'), f.get('severity'), f.get('description', '')[:56], flush=True)
    g = out.get('graph')
    if isinstance(g, dict):
        print('GRAPH nodes', len(g.get('nodes') or []), 'edges', len(g.get('edges') or []), flush=True)
    if args.out:
        p = Path(args.out)
        if not p.is_absolute():
            p = ROOT / p
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
        print('WROTE', p, flush=True)


if __name__ == '__main__':
    main()
