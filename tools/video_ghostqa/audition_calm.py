"""Calm male voice audition: same line, several neutral Mandarin voices.

Writes voice_samples/v4_calm/ with one mp3 per voice plus a single-file
listening page. The previous narration (Ethan) is included as a control.
"""
from __future__ import annotations
import html, json, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts' / 'competition_video_ghostqa' / 'voice_samples' / 'v4_calm'
SPACE = 'https://qwen-qwen3-tts-demo.hf.space'
API = '/tts_interface'

TEXT = ('下面演示 GhostQA 的一次完整测试流程。它是一个自主探索式的 Web 测试系统。'
        '本次 5 个候选，4 个已确认缺陷。')

VOICES = [
    ('01_wen', 'Neil / 精品百人-阿闻', '偏播报，语速平'),
    ('02_elias', 'Elias / 墨讲师', '讲师腔，句子稳'),
    ('03_kai', 'Kai / 凯', '常规男声'),
    ('04_tianshu', 'Vincent / 精品百人-田叔', '偏低沉，年长'),
    ('05_xudaye', 'Arthur / 精品百人-徐大爷', '最低沉，年长'),
    ('06_ethan', 'Ethan / 晨煦', '当前成片用声（对照）'),
]


def main():
    sys.path.insert(0, str(ROOT / 'tools' / 'video_ghostqa' / '.tmp_gradio'))
    from gradio_client import Client
    OUT.mkdir(parents=True, exist_ok=True)
    client = Client(SPACE)
    rows = []
    for key, voice, note in VOICES:
        wav = OUT / (key + '.wav')
        mp3 = OUT / (key + '.mp3')
        if not wav.is_file():
            result = client.predict(TEXT, voice, 'Chinese / 中文', api_name=API)
            src = result.get('path') if isinstance(result, dict) else result
            shutil.copyfile(src, wav)
        if not mp3.is_file():
            subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', str(wav),
                            '-codec:a', 'libmp3lame', '-b:a', '128k', str(mp3)], check=True)
        rows.append({'key': key, 'voice': voice, 'note': note, 'mp3': mp3.name})
        print('OK', key, voice, flush=True)

    items = '\n'.join(
        f'<li><div class="t">{html.escape(r["voice"])}</div>'
        f'<div class="n">{html.escape(r["note"])}</div>'
        f'<audio controls preload="none" src="{r["mp3"]}"></audio></li>' for r in rows)
    page = f"""<!DOCTYPE html>
<meta charset="utf-8"><title>GhostQA 平静男声试听</title>
<style>
body{{font-family:"Microsoft YaHei",system-ui,sans-serif;background:#F2EFE8;color:#2D2B27;
margin:0;padding:32px 20px 60px}}
h1{{font-size:22px;color:#0D6B66;margin:0 0 6px}}
p.lead{{color:#6F6C64;font-size:14px;margin:0 0 22px;line-height:1.7;max-width:760px}}
ul{{list-style:none;margin:0;padding:0;display:grid;gap:14px;max-width:820px}}
li{{background:#FBF9F4;border:1px solid #D4D0C7;border-radius:12px;padding:14px 18px}}
.t{{font-weight:600;font-size:16px}}
.n{{color:#6F6C64;font-size:13px;margin:2px 0 10px}}
audio{{width:100%}}
</style>
<h1>平静男声试听 · 同一句文稿</h1>
<p class="lead">文稿：{html.escape(TEXT)}<br>
六个音色都读同一句。目标是"像播报那样平"，不要有情绪起伏。</p>
<ul>{items}</ul>"""
    (OUT / 'index.html').write_text(page, encoding='utf-8')
    (OUT / 'manifest.json').write_text(json.dumps(
        {'text': TEXT, 'space': SPACE, 'voices': rows}, ensure_ascii=False, indent=2), encoding='utf-8')
    print('WROTE', OUT / 'index.html', flush=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
