"""Rewrite the calm-voice audition page with measured prosody metrics.

For each sample it reports median F0, F0 standard deviation in semitones (lower
= flatter delivery), the p10-p90 spread, and characters per second. These are
proxies for "reads like a broadcast" versus "reads with emotion", so the choice
does not depend on guessing from a voice name.
"""
from __future__ import annotations
import glob
import html
import json
import os
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts' / 'competition_video_ghostqa' / 'voice_samples' / 'v4_calm'
TEXT = ('下面演示 GhostQA 的一次完整测试流程。它是一个自主探索式的 Web 测试系统。'
        '本次 5 个候选，4 个已确认缺陷。')
sys.path.insert(0, str(ROOT / 'tools' / 'video_ghostqa' / '.tmp_kokoro'))
import numpy as np  # noqa: E402

NOTES = {
    '01_wen': ('Neil / 精品百人-阿闻', '偏播报，语速平'),
    '02_elias': ('Elias / 墨讲师', '讲师腔，句子稳'),
    '03_kai': ('Kai / 凯', '常规男声'),
    '04_tianshu': ('Vincent / 精品百人-田叔', '偏低沉，年长'),
    '05_xudaye': ('Arthur / 精品百人-徐大爷', '最低沉，年长'),
    '06_ethan': ('Ethan / 晨煦', '当前成片用声（对照）'),
}


def f0_track(path: Path):
    w = wave.open(str(path), 'rb')
    sr, n = w.getframerate(), w.getnframes()
    x = np.frombuffer(w.readframes(n), dtype='<i2').astype(np.float32) / 32768.0
    if w.getnchannels() == 2:
        x = x.reshape(-1, 2).mean(1)
    fl, hop = int(0.040 * sr), int(0.010 * sr)
    lo, hi = int(sr / 300), int(sr / 70)
    f0 = []
    for s in range(0, len(x) - fl, hop):
        fr = x[s:s + fl]
        if float(np.sqrt((fr ** 2).mean())) < 0.02:
            continue
        fr = fr - fr.mean()
        spec = np.fft.rfft(fr, 2 * fl)
        ac = np.fft.irfft(spec * np.conj(spec))[:fl]
        if ac[0] <= 0:
            continue
        seg = ac[lo:hi]
        if len(seg) == 0:
            continue
        k = int(np.argmax(seg)) + lo
        if ac[k] / ac[0] < 0.35:
            continue
        f0.append(sr / k)
    f0 = np.array(f0)
    semi = 12 * np.log2(f0 / np.median(f0))
    return {'duration': n / sr, 'median_f0': float(np.median(f0)),
            'std_semi': float(semi.std()),
            'p10_p90': float(np.percentile(semi, 90) - np.percentile(semi, 10)),
            'rate': len(TEXT) / (n / sr)}


def main():
    rows = []
    for key in sorted(NOTES):
        wav = OUT / (key + '.wav')
        if not wav.is_file():
            continue
        m = f0_track(wav)
        name, note = NOTES[key]
        rows.append({'key': key, 'voice': name, 'note': note, 'mp3': key + '.mp3', **m})
    rows.sort(key=lambda r: r['std_semi'])

    cards = []
    for rank, r in enumerate(rows, 1):
        cards.append(f"""<li>
  <div class="hd"><span class="rk">#{rank}</span><span class="t">{html.escape(r['voice'])}</span>
    <span class="tag">F0 起伏 {r['std_semi']:.2f} 半音</span></div>
  <div class="n">{html.escape(r['note'])}</div>
  <div class="m">中位音高 {r['median_f0']:.0f} Hz ｜ 语速 {r['rate']:.2f} 字/秒 ｜ 时长 {r['duration']:.2f} s ｜ 10–90% 跨度 {r['p10_p90']:.2f} 半音</div>
  <audio controls preload="none" src="{r['mp3']}"></audio>
</li>""")
    page = f"""<!DOCTYPE html>
<meta charset="utf-8"><title>GhostQA 平静男声试听</title>
<style>
body{{font-family:"Microsoft YaHei",system-ui,sans-serif;background:#F2EFE8;color:#2D2B27;
margin:0;padding:30px 20px 60px}}
h1{{font-size:22px;color:#0D6B66;margin:0 0 6px}}
p.lead{{color:#6F6C64;font-size:14px;margin:0 0 8px;line-height:1.7;max-width:860px}}
p.hint{{color:#0D6B66;font-size:13px;margin:0 0 22px}}
ul{{list-style:none;margin:0;padding:0;display:grid;gap:12px;max-width:900px}}
li{{background:#FBF9F4;border:1px solid #D4D0C7;border-radius:12px;padding:14px 18px}}
.hd{{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}}
.rk{{color:#0D6B66;font-weight:700;font-size:15px}}
.t{{font-weight:600;font-size:16px}}
.tag{{margin-left:auto;background:#EAF3F1;border:1px solid #C9DEDA;color:#0D6B66;
border-radius:999px;padding:2px 10px;font-size:12px}}
.n{{color:#6F6C64;font-size:13px;margin:2px 0 6px}}
.m{{color:#8A867D;font-size:12px;margin-bottom:10px;font-variant-numeric:tabular-nums}}
audio{{width:100%}}
</style>
<h1>平静男声试听 · 同一句文稿</h1>
<p class="lead">文稿：{html.escape(TEXT)}</p>
<p class="hint">按"F0 起伏"从低到高排序 —— 数字越小，语气越平，越接近播报；
语速越慢，越不显得急。</p>
<ul>{''.join(cards)}</ul>"""
    (OUT / 'index.html').write_text(page, encoding='utf-8')
    print('WROTE', OUT / 'index.html')
    for r in rows:
        print(f"  {r['std_semi']:.2f}  {r['voice']:22s} {r['median_f0']:6.1f}Hz  {r['rate']:.2f}字/s")


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
