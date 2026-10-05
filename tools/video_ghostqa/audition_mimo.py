"""Audition MiMo TTS voices for the GhostQA broadcast-style narration.

Renders the same sentence through several preset voices (plus one designed
voice), saves the WAVs, and lets audition_page_broadcast.py measure them. The
style direction is the calm news-anchor instruction, so candidates are judged on
delivery, not on marketing copy.

Usage:
  python tools/video_ghostqa/audition_mimo.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mimo_tts import synth, wav_seconds  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts' / 'competition_video_ghostqa' / 'voice_samples' / 'v6_mimo'

TEXT = ('下面演示 Ghost Q A 的一次完整测试流程。它是一个自主探索式的 Web 测试系统，'
        '本次运行通过 11 个状态，确认 4 个缺陷。')

CALM = ('用平静、克制的新闻播报语气朗读，普通话标准，语速平稳适中，语调平直，'
        '不要情绪起伏，不要拖腔，像电视台新闻联播播音员。')

ANCHOR_DESIGN = ('三十五岁左右的男性新闻播音员，普通话标准，声音沉稳干净，中低音区，'
                 '吐字清晰，语速平稳，语调平直克制，无情绪起伏，适合电视新闻联播播报。')

# (key, label, model, voice, instruct)
CONFIGS = [
    ('01_dean', 'Dean（预置男声）+ 播报指令', 'mimo-v2.5-tts', 'Dean', CALM),
    ('02_milo', 'Milo（预置男声）+ 播报指令', 'mimo-v2.5-tts', 'Milo', CALM),
    ('03_baihua', '白桦（预置男声）+ 播报指令', 'mimo-v2.5-tts', '白桦', CALM),
    ('04_soda', '苏打（预置男声）+ 播报指令', 'mimo-v2.5-tts', '苏打', CALM),
    ('05_default', 'mimo_default + 播报指令', 'mimo-v2.5-tts', 'mimo_default', CALM),
    ('06_anchor_design', 'voicedesign · 描述生成播音员', 'mimo-v2.5-tts-voicedesign', '', ANCHOR_DESIGN),
    ('07_bingtang', '冰糖（预置女声）+ 播报指令', 'mimo-v2.5-tts', '冰糖', CALM),
    ('08_moli', '茉莉（预置女声）+ 播报指令', 'mimo-v2.5-tts', '茉莉', CALM),
    ('09_chloe', 'Chloe（预置女声）+ 播报指令', 'mimo-v2.5-tts', 'Chloe', CALM),
    ('10_mia', 'Mia（预置女声）+ 播报指令', 'mimo-v2.5-tts', 'Mia', CALM),
    ('11_baihua_slow', '白桦 + 更慢更沉的播报指令', 'mimo-v2.5-tts', '白桦',
     '用沉稳克制的新闻播报语气朗读，普通话标准，语速偏慢、字字清晰，语调平直，'
     '句间停顿从容，不要情绪起伏，不要拖腔，像电视台新闻联播播音员。'),
    ('12_soda_slow', '苏打 + 更慢更沉的播报指令', 'mimo-v2.5-tts', '苏打',
     '用沉稳克制的新闻播报语气朗读，普通话标准，语速偏慢、字字清晰，语调平直，'
     '句间停顿从容，不要情绪起伏，不要拖腔，像电视台新闻联播播音员。'),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for key, label, model, voice, instruct in CONFIGS:
        wav = OUT / f'{key}.wav'
        row = {'key': key, 'label': label, 'model': model, 'voice': voice,
               'instruct': instruct, 'file': str(wav)}
        if wav.is_file() and wav.stat().st_size > 4096:
            row['status'] = 'cached'
            rows.append(row)
            print('CACHED', key, flush=True)
            continue
        try:
            data = synth(TEXT, model, voice, instruct)
            if len(data) < 4096:
                raise RuntimeError(f'suspiciously small audio ({len(data)} bytes)')
            wav.write_bytes(data)
            row.update({'status': 'generated', 'bytes': len(data),
                        'seconds': round(wav_seconds(data), 2)})
            print(f'GENERATED {key}: {len(data)} bytes {row["seconds"]}s', flush=True)
        except Exception as exc:
            row.update({'status': 'failed', 'error': repr(exc)[:400]})
            print('ERROR', key, repr(exc)[:300], file=sys.stderr, flush=True)
        rows.append(row)
    (OUT / 'manifest.json').write_text(
        json.dumps({'text': TEXT, 'instruct': CALM, 'samples': rows},
                   ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    ok = [r for r in rows if r['status'] in ('generated', 'cached')]
    print(f'DONE {len(ok)}/{len(rows)}')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
