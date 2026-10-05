"""Freeze the recorded multi-case run into a single facts file.

Everything the script and the rendered slides display is read from the run API
and, when available, the run's report.json. Run it once the recorded run has
reached a terminal state.

  python tools/video_ghostqa/extract_multicase_facts.py --run-id <id>
"""
from __future__ import annotations
import argparse, json, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts' / 'competition_video_ghostqa'
MC = OUT / 'multicase'
SHA = '23739a72f3555f3c02e6c7bd0c559ae526689fbb'


def get(base, path):
    with urllib.request.urlopen(base + path, timeout=40) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='http://39.106.200.173:8787')
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--out', default=str(OUT / 'multicase-facts.json'))
    args = ap.parse_args()
    base = args.base.rstrip('/'); rid = args.run_id

    status = get(base, '/api/runs/' + rid)
    summary = status.get('summary') or {}
    bugs = get(base, '/api/runs/%s/bugs' % rid)
    graph = get(base, '/api/runs/%s/graph' % rid)
    candidates = []
    try:
        candidates = get(base, '/api/runs/%s/events?after=0' % rid)
    except Exception:
        candidates = []
    cand_list = status.get('candidates') or []
    if not cand_list:
        try:
            cand_list = get(base, '/api/runs/%s/candidates' % rid)
        except Exception:
            cand_list = []

    report = None
    rp = MC / 'report.json'
    if rp.is_file():
        report = json.loads(rp.read_text(encoding='utf-8'))

    unfinished = []
    if isinstance(report, dict):
        for row in report.get('unfinished', []) or []:
            unfinished.append(row)
    if not unfinished:
        unfinished = [c for c in cand_list if c.get('replay_status') == 'unfinished']
        # a run we stopped may leave candidates without a final replay verdict
        if status.get('status') == 'stopped':
            done = {b['finding']['description'] for b in bugs}
            unfinished += [c for c in cand_list
                           if c.get('replay_status') is None and c.get('description') not in done]
    failed = [c for c in cand_list if c.get('replay_status') == 'failed']

    facts = {
        'run_id': rid,
        'source_sha': SHA,
        'base_url': base,
        'final_status': status.get('status'),
        'cfg': (status.get('cfg') or {}),
        'action_count': summary.get('actions'),
        'state_count': summary.get('states'),
        'candidate_count': summary.get('candidates'),
        'confirmed_count': len(bugs),
        'llm_calls': summary.get('llm_calls'),
        'wall_seconds': summary.get('wall_seconds'),
        'edge_count': len(graph.get('edges') or []),
        'failed_count': len(failed),
        'unfinished_count': len(unfinished),
        'bugs': [{'finding': b['finding'], 'reproduction': b['reproduction'],
                  'original_length': b.get('original_length')} for b in bugs],
        'candidates': [{'kind': c.get('kind'), 'severity': c.get('severity'),
                        'description': c.get('description'), 'step_index': c.get('step_index'),
                        'replay_status': c.get('replay_status')} for c in cand_list],
        'notes': ['All numbers are read from the recorded multi-case run; nothing is reused from run 66026146.'],
    }
    Path(args.out).write_text(json.dumps(facts, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('WROTE', args.out)
    print(json.dumps({k: facts[k] for k in ('run_id', 'final_status', 'action_count', 'state_count',
                                            'candidate_count', 'confirmed_count', 'llm_calls',
                                            'edge_count', 'failed_count', 'unfinished_count')},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
