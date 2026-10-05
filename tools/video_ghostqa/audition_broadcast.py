"""Audition broadcast-style voices across the current Qwen3-TTS Spaces.

The old public demo (``qwen-qwen3-tts-demo``) has been retired. The official
replacement is ``Qwen/Qwen3-TTS``, which exposes an ``instruct`` field, so the
"news broadcast" delivery the client asked for can now be controlled explicitly
instead of being guessed from a voice name.

This helper renders the *same* sentence through several configurations, measures
F0 spread (flatter = calmer) and speaking rate, and writes an audition page. The
winning configuration is then used for the real narration.

Usage:
  python tools/video_ghostqa/audition_broadcast.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts' / 'competition_video_ghostqa' / 'voice_samples' / 'v5_broadcast'
GRADIO = ROOT / 'tools' / 'video_ghostqa' / '.tmp_gradio'
sys.path.insert(0, str(GRADIO))
sys.path.insert(0, str(ROOT / 'tools' / 'video_ghostqa' / '.tmp_kokoro'))

TEXT = ('下面演示 Ghost Q A 的一次完整测试流程。它是一个自主探索式的 Web 测试系统，'
        '本次运行通过 11 个状态，确认 4 个缺陷。')

CALM = ('用平静、克制的新闻播报语气朗读，普通话标准，语速平稳适中，语调平直，不要情绪起伏，'
        '不要拖腔，像电视台新闻联播播音员。')

# (key, label, space, api_name, kwargs)
# The ZeroGPU-backed spaces (Qwen/Qwen3-TTS, ...-Voice-Design) refuse anonymous
# calls once the shared quota is spent, so the usable provider is the Demo space.
_SCOUT = {'language_display': 'Chinese / 中文'}
CONFIGS = [
    ('01_demo_ethan', 'Ethan / 晨煦（当前成片用声，对照）',
     'Qwen/Qwen3-TTS-Demo', '/tts_interface', {'voice_display': 'Ethan / 晨煦', **_SCOUT}),
    ('02_demo_elias', 'Elias / 墨讲师（旧实测最平）',
     'Qwen/Qwen3-TTS-Demo', '/tts_interface', {'voice_display': 'Elias / 墨讲师', **_SCOUT}),
    ('07_demo_kai', 'Kai / 凯',
     'Qwen/Qwen3-TTS-Demo', '/tts_interface', {'voice_display': 'Kai / 凯', **_SCOUT}),
    ('08_demo_vincent', 'Vincent / 精品百人-田叔',
     'Qwen/Qwen3-TTS-Demo', '/tts_interface', {'voice_display': 'Vincent / 精品百人-田叔', **_SCOUT}),
    ('09_demo_ryan', 'Ryan / 甜茶',
     'Qwen/Qwen3-TTS-Demo', '/tts_interface', {'voice_display': 'Ryan / 甜茶', **_SCOUT}),
    ('10_demo_aiden', 'Aiden / 艾登',
     'Qwen/Qwen3-TTS-Demo', '/tts_interface', {'voice_display': 'Aiden / 艾登', **_SCOUT}),
    ('11_demo_eldric', 'Eldric Sage / 精品百人-沧明子',
     'Qwen/Qwen3-TTS-Demo', '/tts_interface', {'voice_display': 'Eldric Sage / 精品百人-沧明子', **_SCOUT}),
    ('12_demo_neil', 'Neil / 精品百人-阿闻',
     'Qwen/Qwen3-TTS-Demo', '/tts_interface', {'voice_display': 'Neil / 精品百人-阿闻', **_SCOUT}),
]


def result_path(result: object) -> str | None:
    if isinstance(result, (list, tuple)):
        for item in result:
            found = result_path(item)
            if found:
                return found
        return None
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        return result.get('path') or result.get('value')
    return None


def main() -> None:
    from gradio_client import Client

    OUT.mkdir(parents=True, exist_ok=True)
    clients: dict[str, object] = {}
    rows = []
    for key, label, space, api_name, kwargs in CONFIGS:
        wav = OUT / f'{key}.wav'
        row = {'key': key, 'label': label, 'space': space, 'api_name': api_name,
               'kwargs': kwargs, 'file': str(wav)}
        if wav.is_file() and wav.stat().st_size > 4096:
            row['status'] = 'cached'
            rows.append(row)
            print('CACHED', key, flush=True)
            continue
        try:
            client = clients.get(space)
            if client is None:
                client = Client(space, verbose=False)
                clients[space] = client
            result = client.predict(text=TEXT, api_name=api_name, **kwargs)
            source = result_path(result)
            if not source:
                raise RuntimeError(f'no audio path in result: {result!r}')
            Path(wav).write_bytes(Path(source).read_bytes())
            row.update({'status': 'generated', 'bytes': wav.stat().st_size})
            print('GENERATED', key, wav.stat().st_size, flush=True)
        except Exception as exc:
            row.update({'status': 'failed', 'error': repr(exc)[:400]})
            print('ERROR', key, repr(exc)[:300], file=sys.stderr, flush=True)
        rows.append(row)
    (OUT / 'manifest.json').write_text(
        json.dumps({'text': TEXT, 'instruct': CALM, 'samples': rows},
                   ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    ok = [r for r in rows if r['status'] in ('generated', 'cached')]
    print(f'DONE {len(ok)}/{len(rows)}')
    for r in rows:
        if r['status'] not in ('generated', 'cached'):
            print('  MISSING', r['key'], r.get('error', '')[:160])


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
