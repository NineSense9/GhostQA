"""Audition candidate voices on REAL narration paragraphs.

The client rejected Ethan as "too playful, like reading a novel". Generic
audition sentences proved unreliable for judging delivery style, so this helper
renders two actual script paragraphs -- one explanatory, one carrying the
hard Latin brand names -- through the flattest measured candidates, then scores
each on F0 flatness, zh-CN CER, and projected full-video length.

Usage:
  python tools/video_ghostqa/audition_real.py          # generate + measure + page
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import wave
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'video_ghostqa'))
sys.path.insert(0, str(ROOT / 'tools' / 'video_ghostqa' / '.tmp_kokoro'))
sys.path.insert(0, str(ROOT / 'tools' / 'video_ghostqa' / '.tmp_gradio'))
sys.path.insert(0, str(ROOT / 'tools' / 'video_ghostqa' / '.tmp_asr'))

import numpy as np  # noqa: E402
import speech_recognition as sr  # noqa: E402
from audition_page_broadcast import project_total, scene_stats, solve_tempo, TARGET  # noqa: E402

OUT = ROOT / 'artifacts' / 'competition_video_ghostqa' / 'voice_samples' / 'v9_real'

P_A = ('回看这次运行，实际执行了 30 个动作，形成 11 个状态，跨过注册、结算和库存几个页面。'
       '每执行一步，都重新读取页面元素和业务观测，用结构簇和语义变体记录状态身份。')
P_B = ('我们用 Edge 展示面板，真正执行测试的，是服务器侧的 Playwright Chromium。'
       '探索从案例目录页出发，自己决定先进入哪个页面。')

CALM = ('用平静、克制的新闻播报语气朗读，普通话标准，语速平稳适中，语调平直，'
        '不要情绪起伏，不要拖腔，像电视台新闻联播播音员。')

# (key, label, provider, voice)
CANDIDATES = [
    ('kai', 'Kai / 凯（Qwen，实测最平）', 'qwen', 'Kai / 凯'),
    ('ryan', 'Ryan / 甜茶（Qwen）', 'qwen', 'Ryan / 甜茶'),
    ('aiden', 'Aiden / 艾登（Qwen）', 'qwen', 'Aiden / 艾登'),
    ('baihua', '白桦（MiMo + 播报指令）', 'mimo', '白桦'),
    ('soda', '苏打（MiMo + 播报指令）', 'mimo', '苏打'),
    ('bingtang', '冰糖（MiMo 女声 + 播报指令）', 'mimo', '冰糖'),
    ('ethan', 'Ethan / 晨煦（当前版，对照）', 'qwen', 'Ethan / 晨煦'),
]


def synth_qwen(text: str, voice: str) -> bytes:
    from gradio_client import Client
    client = Client('Qwen/Qwen3-TTS-Demo', verbose=False)
    result = client.predict(text=text, voice_display=voice,
                            language_display='Chinese / 中文', api_name='/tts_interface')
    src = result if isinstance(result, str) else result[0]
    return Path(src).read_bytes()


def synth_mimo(text: str, voice: str) -> bytes:
    from mimo_tts import synth
    return synth(text, 'mimo-v2.5-tts', voice, CALM)


def f0_stats(path: Path):
    with wave.open(str(path), 'rb') as w:
        sr_, n = w.getframerate(), w.getnframes()
        x = np.frombuffer(w.readframes(n), dtype='<i2').astype(np.float32) / 32768.0
        if w.getnchannels() == 2:
            x = x.reshape(-1, 2).mean(1)
    frame, lo, hi = int(0.040 * sr_), int(sr_ / 300), int(sr_ / 70)
    f0 = []
    for s in range(0, len(x) - frame, int(0.010 * sr_)):
        seg = x[s:s + frame]
        if float(np.sqrt((seg ** 2).mean())) < 0.02:
            continue
        seg = seg - seg.mean()
        spec = np.fft.rfft(seg, 2 * frame)
        ac = np.fft.irfft(spec * np.conj(spec))[:frame]
        if ac[0] <= 0:
            continue
        window = ac[lo:hi]
        if len(window) == 0:
            continue
        k = int(np.argmax(window)) + lo
        if ac[k] / ac[0] < 0.35:
            continue
        f0.append(sr_ / k)
    f0 = np.array(f0)
    semi = 12 * np.log2(f0 / np.median(f0))
    return {'duration': n / sr_, 'median_f0': float(np.median(f0)),
            'std_semi': float(semi.std())}


def norm(s: str) -> str:
    return re.sub(r'[^\u4e00-\u9fff0-9a-z]', '', s.lower())


def cer(ref: str, hyp: str) -> float:
    a, b = norm(ref), norm(hyp)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] / len(a)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stats = scene_stats()
    chars = sum(c for _, c, _ in stats)
    recognizer = sr.Recognizer()

    rows = []
    for key, label, provider, voice in CANDIDATES:
        row = {'key': key, 'voice': label}
        for tag, text in (('a', P_A), ('b', P_B)):
            wav = OUT / f'{key}_{tag}.wav'
            if not wav.is_file() or wav.stat().st_size < 4096:
                data = (synth_qwen if provider == 'qwen' else synth_mimo)(text, voice)
                wav.write_bytes(data)
            m = f0_stats(wav)
            row[f'dur_{tag}'] = m['duration']
            row[f'f0_{tag}'] = m['std_semi']
            with wave.open(str(wav), 'rb') as w:
                rate, raw = w.getframerate(), w.readframes(w.getnframes())
            try:
                hyp = recognizer.recognize_google(sr.AudioData(raw, rate, 2), language='zh-CN')
                row[f'cer_{tag}'] = cer(text, hyp)
            except Exception as exc:
                row[f'cer_{tag}'] = None
                row[f'asr_error_{tag}'] = repr(exc)[:120]
        # speaking rate on the explanatory paragraph, projected onto the script
        rate = len(norm(P_A)) / row['dur_a']
        tempo = solve_tempo(rate, stats)
        row.update({'rate': rate, 'tempo': tempo,
                    'adjusted': project_total(rate * (tempo or 1.0), stats),
                    'direct': project_total(rate, stats)})
        rows.append(row)
        (OUT / 'measure.json').write_text(
            json.dumps({'created_at_utc': datetime.now(timezone.utc).isoformat(),
                        'paragraphs': {'a': P_A, 'b': P_B}, 'rows': rows},
                       ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('MEASURED', key, flush=True)

    rows.sort(key=lambda r: (r['tempo'] is None,
                             min(r['f0_a'], r['f0_b'])))
    cards = []
    for rank, r in enumerate(rows, 1):
        f0 = min(r['f0_a'], r['f0_b'])
        if r['tempo'] is None:
            badge, cls = f"不可用 · 变速也装不下（直出 {r['direct']:.0f}s）", 'bad'
        elif abs(r['tempo'] - 1.0) < 1e-6:
            badge, cls = f"可选用 · 直出 {r['direct']:.0f}s", 'ok'
        else:
            badge, cls = (f"可选用 · 变速 ×{r['tempo']:.2f} 后 {r['adjusted']:.0f}s"
                          f"（直出 {r['direct']:.0f}s）"), 'ok'
        cera = '—' if r['cer_a'] is None else f"{r['cer_a'] * 100:.0f}%"
        cerb = '—' if r['cer_b'] is None else f"{r['cer_b'] * 100:.0f}%"
        cards.append(f"""<li class="{cls}">
  <div class="hd"><span class="rk">#{rank}</span><span class="t">{r['voice']}</span>
    <span class="tag {cls}">{badge}</span></div>
  <div class="m">平直度 <b>{f0:.2f}</b>（讲解段 {r['f0_a']:.2f} / 品牌段 {r['f0_b']:.2f}，越小越不像“读小说”）｜
     语速 {r['rate']:.2f} 字/秒 ｜ 中位音高 {r.get('median_f0', 0):.0f} Hz ｜
     ASR 中文 CER：讲解段 <b>{cera}</b> / 品牌段 <b>{cerb}</b></div>
  <div class="cap">A · 讲解段</div><audio controls preload="none" src="{r['key']}_a.wav"></audio>
  <div class="cap">B · 品牌段（Edge / Playwright）</div><audio controls preload="none" src="{r['key']}_b.wav"></audio>
</li>""")

    page = f"""<!DOCTYPE html>
<meta charset="utf-8"><title>GhostQA 真实段落换音色试听</title>
<style>
body{{font-family:"Microsoft YaHei",system-ui,sans-serif;background:#F2EFE8;color:#2D2B27;
margin:0;padding:30px 20px 60px}}
h1{{font-size:22px;color:#0D6B66;margin:0 0 8px}}
p.lead,p.rule{{color:#6F6C64;font-size:13.5px;margin:0 0 6px;line-height:1.75;max-width:920px}}
p.rule{{background:#FBF9F4;border-left:3px solid #0D6B66;padding:10px 14px;border-radius:6px;
color:#4A473F;margin:14px 0 22px}}
ul{{list-style:none;margin:0;padding:0;display:grid;gap:12px;max-width:940px}}
li{{background:#FBF9F4;border:1px solid #D4D0C7;border-radius:12px;padding:14px 18px}}
li.bad{{border-color:#E0B4A8;background:#FBF3F0}}
.hd{{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}}
.rk{{color:#0D6B66;font-weight:700;font-size:15px}}
.t{{font-weight:600;font-size:16px}}
.tag{{margin-left:auto;border-radius:999px;padding:2px 10px;font-size:12px;
background:#EAF3F1;border:1px solid #C9DEDA;color:#0D6B66;font-variant-numeric:tabular-nums}}
.tag.bad{{background:#F7E4DE;border-color:#E3C0B5;color:#A2452C}}
.m{{color:#6F6C64;font-size:12.5px;margin:8px 0 6px;font-variant-numeric:tabular-nums}}
.m b{{color:#2D2B27}}
.cap{{color:#8A867D;font-size:11.5px;margin-top:6px}}
audio{{width:100%}}
</style>
<h1>换音色试听 · 用正片真实段落，不用泛泛样句</h1>
<p class="lead">候选 = 此前实测最平的音色。A 段是纯讲解（state_ai 开头），B 段是带 Edge / Playwright 的硬骨头。</p>
<p class="rule">“戏谑感/读小说”对应的是韵律起伏：平直度按<b>这两段真实旁白</b>实测，越小越像讲解。
每个候选按真实语速换算全片时长（硬上限 300s，内部线 {TARGET:.0f}s），需要变速的标注倍率。
ASR 中文 CER 单独列出——<b>音译回退（Edge→挨着）不算读音错</b>，红字级别的才要担心。</p>
<ul>{''.join(cards)}</ul>"""
    (OUT / 'index.html').write_text(page, encoding='utf-8')
    print('WROTE', OUT / 'index.html')
    for r in rows:
        f0 = min(r['f0_a'], r['f0_b'])
        flag = 'OK ' if r['tempo'] is not None else 'BAD'
        t = r['tempo']
        tail = '变速不可救' if t is None else ('直出' if abs(t - 1.0) < 1e-6 else f"×{t:.2f}->{r['adjusted']:.0f}s")
        ca = '—' if r['cer_a'] is None else f"{r['cer_a']*100:.0f}%"
        cb = '—' if r['cer_b'] is None else f"{r['cer_b']*100:.0f}%"
        print(f"  {flag} 平直 {f0:5.2f}  {r['rate']:5.2f}字/s  CER {ca:>4}/{cb:<4}  {tail:14s} {r['voice']}")


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
