"""Build the MiMo audition page with measured prosody and a feasibility check.

Same rules as audition_page_broadcast.py: each candidate is measured (F0 spread,
speaking rate, loudness swing) and projected onto the real narration character
count, so a calm-but-slow voice cannot be picked and blow the five-minute limit.

Usage:
  python tools/video_ghostqa/audition_page_mimo.py
"""
from __future__ import annotations

import json
import re
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts' / 'competition_video_ghostqa'
V6 = OUT / 'voice_samples' / 'v6_mimo'
sys.path.insert(0, str(ROOT / 'tools' / 'video_ghostqa' / '.tmp_kokoro'))
sys.path.insert(0, str(ROOT / 'tools' / 'video_ghostqa'))

import numpy as np  # noqa: E402
from audition_page_broadcast import project_total, scene_stats, solve_tempo, TARGET  # noqa: E402

PAUSE = 1.2


def measure(path: Path, spoken_chars: int):
    with wave.open(str(path), 'rb') as w:
        sr, n = w.getframerate(), w.getnframes()
        x = np.frombuffer(w.readframes(n), dtype='<i2').astype(np.float32) / 32768.0
        if w.getnchannels() == 2:
            x = x.reshape(-1, 2).mean(1)
    duration = n / sr

    frame, hop = int(0.040 * sr), int(0.010 * sr)
    lo, hi = int(sr / 300), int(sr / 70)
    f0, rms = [], []
    for s in range(0, len(x) - frame, hop):
        seg = x[s:s + frame]
        level = float(np.sqrt((seg ** 2).mean()))
        rms.append(level)
        if level < 0.02:
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
        f0.append(sr / k)
    f0 = np.array(f0)
    semi = 12 * np.log2(f0 / np.median(f0))
    rms = np.array(rms)
    loud = rms[rms > 0.02]
    return {
        'duration': duration,
        'median_f0': float(np.median(f0)),
        'std_semi': float(semi.std()),
        'p10_p90': float(np.percentile(semi, 90) - np.percentile(semi, 10)),
        'rate': spoken_chars / duration,
        'dyn_db': float(20 * np.log10(np.percentile(loud, 90) / np.percentile(loud, 10))) if len(loud) else 0.0,
    }


def main():
    manifest = json.loads((V6 / 'manifest.json').read_text(encoding='utf-8'))
    text = manifest['text']
    spoken_cs = len(re.sub(r'[^\u4e00-\u9fffA-Za-z0-9]', '', text))
    stats = scene_stats()
    chars = sum(c for _, c, _ in stats)
    paragraphs = sum(n for _, _, n in stats)

    rows = []
    for sample in manifest['samples']:
        if sample.get('status') not in ('generated', 'cached'):
            continue
        wav = Path(sample['file'])
        if not wav.is_file():
            continue
        m = measure(wav, spoken_cs)
        tempo = solve_tempo(m['rate'], stats)
        adjusted = project_total(m['rate'] * (tempo or 1.0), stats) if tempo else None
        rows.append({'key': sample['key'], 'voice': sample['label'],
                     'model': sample.get('model', ''),
                     'projected': project_total(m['rate'], stats),
                     'tempo': tempo, 'adjusted': adjusted, **m})
    # Feasible with (or without) tempo help first, flattest delivery first.
    rows.sort(key=lambda r: (r['tempo'] is None, r['std_semi']))

    cards = []
    for rank, r in enumerate(rows, 1):
        ok = r['tempo'] is not None
        if r['tempo'] is None:
            badge = f"不可用 · 直出 {r['projected']:.0f}s，±15% 变速也装不下"
        elif abs(r['tempo'] - 1.0) < 1e-6:
            badge = f"可选用 · 直出 {r['projected']:.0f}s"
        else:
            badge = (f"可选用 · 变速 ×{r['tempo']:.2f} 后 {r['adjusted']:.0f}s"
                     f"（直出 {r['projected']:.0f}s）")
        cls = 'ok' if ok else 'bad'
        cards.append(f"""<li class="{cls}">
  <div class="hd"><span class="rk">#{rank}</span><span class="t">{r['voice']}</span>
    <span class="tag {cls}">{badge}</span></div>
  <div class="m">F0 起伏 <b>{r['std_semi']:.2f}</b> 半音 ｜ 语速 <b>{r['rate']:.2f}</b> 字/秒 ｜
     中位音高 {r['median_f0']:.0f} Hz ｜ 音量摆幅 {r['dyn_db']:.1f} dB ｜ 样句 {r['duration']:.2f}s</div>
  <audio controls preload="none" src="{r['key']}.wav"></audio>
</li>""")

    page = f"""<!DOCTYPE html>
<meta charset="utf-8"><title>GhostQA MiMo 播报腔试听</title>
<style>
body{{font-family:"Microsoft YaHei",system-ui,sans-serif;background:#F2EFE8;color:#2D2B27;
margin:0;padding:30px 20px 60px}}
h1{{font-size:22px;color:#0D6B66;margin:0 0 8px}}
p.lead{{color:#6F6C64;font-size:14px;margin:0 0 6px;line-height:1.75;max-width:900px}}
p.rule{{background:#FBF9F4;border-left:3px solid #0D6B66;padding:10px 14px;border-radius:6px;
color:#4A473F;font-size:13px;line-height:1.8;max-width:900px;margin:14px 0 22px}}
ul{{list-style:none;margin:0;padding:0;display:grid;gap:12px;max-width:940px}}
li{{background:#FBF9F4;border:1px solid #D4D0C7;border-radius:12px;padding:14px 18px}}
li.bad{{border-color:#E0B4A8;background:#FBF3F0}}
.hd{{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}}
.rk{{color:#0D6B66;font-weight:700;font-size:15px}}
.t{{font-weight:600;font-size:16px}}
.tag{{margin-left:auto;border-radius:999px;padding:2px 10px;font-size:12px;
background:#EAF3F1;border:1px solid #C9DEDA;color:#0D6B66;font-variant-numeric:tabular-nums}}
.tag.bad{{background:#F7E4DE;border-color:#E3C0B5;color:#A2452C}}
.m{{color:#6F6C64;font-size:12.5px;margin:8px 0 10px;font-variant-numeric:tabular-nums}}
.m b{{color:#2D2B27}}
audio{{width:100%}}
</style>
<h1>MiMo TTS 播报腔试听 · 可手动变速，但上限仍然有效</h1>
<p class="lead">同一句文稿：{text}</p>
<p class="rule">所有样本都带同一条播报指令："平静克制、普通话标准、语调平直、不要情绪起伏、像新闻联播播音员"。
比赛硬上限 <b>300 秒</b>（内部安全线 {TARGET:.0f}s）。生成后可整体变速（atempo，<b>保音高</b>，语气起伏不变），
±15% 以内基本无感，所以"平但慢"的音色也在候选里 —— 每张卡片给出建议变速倍率与调速后时长。
排序：能装进上限的排前，同组内按 F0 起伏（越小越平）。</p>
<ul>{''.join(cards)}</ul>"""
    (V6 / 'index.html').write_text(page, encoding='utf-8')
    print('WROTE', V6 / 'index.html')
    print(f'narration chars={chars} paragraphs={paragraphs}')
    for r in rows:
        tempo = r['tempo']
        flag = 'OK ' if tempo is not None else 'BAD'
        if tempo is None:
            tail = '变速也不可救'
        elif abs(tempo - 1.0) < 1e-6:
            tail = '无需变速'
        else:
            tail = f"×{tempo:.2f} -> {r['adjusted']:.0f}s"
        print(f"  {flag} F0起伏 {r['std_semi']:5.2f}  {r['rate']:5.2f}字/s  "
              f"直出 {r['projected']:6.1f}s  {tail:16s} {r['voice']}")


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
