"""Build the broadcast-voice audition page with a hard feasibility check.

Beyond prosody, this page answers the only question that actually decides the
voice: at this speaking rate, does the full narration still fit the competition's
five-minute ceiling? Rates are measured, then projected onto the real character
count of ``build_multicase_script.narration`` so a slow, calm voice cannot be
chosen by accident and blow the deadline.

Usage:
  python tools/video_ghostqa/audition_page_broadcast.py
"""
from __future__ import annotations

import html
import json
import re
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts' / 'competition_video_ghostqa'
V5 = OUT / 'voice_samples' / 'v5_broadcast'
sys.path.insert(0, str(ROOT / 'tools' / 'video_ghostqa' / '.tmp_kokoro'))

import numpy as np  # noqa: E402

PAUSE = 1.2
CEILING = 300.0        # competition hard limit, seconds
TARGET = 297.0         # our own safety cap used by build_multicase_script

LABELS = {
    '01_demo_ethan': 'Ethan / 晨煦',
    '02_demo_elias': 'Elias / 墨讲师',
    '07_demo_kai': 'Kai / 凯',
    '08_demo_vincent': 'Vincent / 田叔',
    '09_demo_ryan': 'Ryan / 甜茶',
    '10_demo_aiden': 'Aiden / 艾登',
    '11_demo_eldric': 'Eldric Sage / 沧明子',
    '12_demo_neil': 'Neil / 阿闻',
}


# Mirror of build_multicase_script.py: scenes whose picture is a continuous
# capture are floored at this length, which adds padding the naive narration
# estimate would miss.
MIN_SECONDS = {'live': 37.0}
TAIL = 2.0            # build_multicase_script adds a 2s tail after fitting


def scene_stats():
    """[(scene_id, chars, paragraph_count)] for the narration actually recorded."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'bms', ROOT / 'tools' / 'video_ghostqa' / 'build_multicase_script.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    facts = json.loads((OUT / 'multicase-facts.json').read_text(encoding='utf-8'))
    stats = []
    for scene in mod.narration(facts):
        chars = sum(len(re.sub(r'[^\u4e00-\u9fffA-Za-z0-9]', '', para['tts']))
                    for para in scene['paragraphs'])
        stats.append((scene['id'], chars, len(scene['paragraphs'])))
    return stats


def project_total(rate: float, stats) -> float:
    """Whole-video seconds at this speaking rate, incl. pauses and floors."""
    total = 0.0
    for scene_id, chars, paragraphs in stats:
        natural = chars / rate + PAUSE * paragraphs
        total += max(natural, MIN_SECONDS.get(scene_id, 0.0))
    return total + TAIL


TEMPO_CAP = 0.15      # beyond ±15% the processing starts to be audible


def solve_tempo(rate: float, stats) -> float | None:
    """Post-generation atempo factor (pitch-preserving) that fits the ceiling.

    Returns the factor closest to 1.0 among feasible ones, or None when even
    the allowed speed change cannot fit. The user explicitly asked for manual
    tempo control after generation, so slow-but-flat voices stay in the pool.
    """
    best = None
    step = 0.005
    k = 1.0 - TEMPO_CAP
    while k <= 1.0 + TEMPO_CAP + 1e-9:
        if project_total(rate * k, stats) <= TARGET:
            if best is None or abs(k - 1.0) < abs(best - 1.0):
                best = round(k, 3)
        k += step
    return best


def measure(path: Path, spoken_chars: int):
    with wave.open(str(path), 'rb') as w:
        sr, n = w.getframerate(), w.getnframes()
        x = np.frombuffer(w.readframes(n), dtype='<i2').astype(np.float32) / 32768.0
        if w.getnchannels() == 2:
            x = x.reshape(-1, 2).mean(1)
    duration = n / sr

    # F0 via autocorrelation on voiced, sufficiently loud frames.
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
        # loudness swing: emotional delivery also pushes and drops volume
        'dyn_db': float(20 * np.log10(np.percentile(loud, 90) / np.percentile(loud, 10))) if len(loud) else 0.0,
    }


def main():
    text = json.loads((V5 / 'manifest.json').read_text(encoding='utf-8'))['text']
    spoken_cs = len(re.sub(r'[^\u4e00-\u9fffA-Za-z0-9]', '', text))
    stats = scene_stats()
    chars = sum(c for _, c, _ in stats)
    paragraphs = sum(n for _, _, n in stats)

    rows = []
    for key, label in LABELS.items():
        wav = V5 / f'{key}.wav'
        if not wav.is_file():
            continue
        m = measure(wav, spoken_cs)
        tempo = solve_tempo(m['rate'], stats)
        adjusted = project_total(m['rate'] * (tempo or 1.0), stats) if tempo else None
        rows.append({'key': key, 'voice': label,
                     'projected': project_total(m['rate'], stats),
                     'tempo': tempo, 'adjusted': adjusted, **m})
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
  <div class="hd"><span class="rk">#{rank}</span><span class="t">{html.escape(r['voice'])}</span>
    <span class="tag {cls}">{badge}</span></div>
  <div class="m">F0 起伏 <b>{r['std_semi']:.2f}</b> 半音 ｜ 语速 <b>{r['rate']:.2f}</b> 字/秒 ｜
     中位音高 {r['median_f0']:.0f} Hz ｜ 音量摆幅 {r['dyn_db']:.1f} dB ｜ 样句 {r['duration']:.2f}s</div>
  <audio controls preload="none" src="{r['key']}.wav"></audio>
</li>""")

    page = f"""<!DOCTYPE html>
<meta charset="utf-8"><title>GhostQA 播报腔音色 · 可行性试听</title>
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
<h1>播报腔音色试听 · 含"能不能装进 5 分钟"的硬核算</h1>
<p class="lead">同一句文稿：{html.escape(text)}</p>
<p class="rule">比赛硬上限 <b>300 秒</b>（内部安全线 {TARGET:.0f}s）。按各音色实测语速换算到本次文稿
<b>{chars}</b> 字 / {paragraphs} 段，得到"全片预估时长"。<b>偏平但语速慢的音色会直接超时，
不可选</b>，所以它排不进候选 —— 这一项不是主观偏好，是规则约束。</p>
<ul>{''.join(cards)}</ul>"""
    (V5 / 'index.html').write_text(page, encoding='utf-8')
    print('WROTE', V5 / 'index.html')
    print(f'narration chars={chars} paragraphs={paragraphs}')
    for r in rows:
        t=r['tempo']
        flag = 'OK ' if t is not None else 'BAD'
        tail = '变速也不可救' if t is None else ('无需变速' if abs(t-1.0)<1e-6 else f'×{t:.2f} -> {r["adjusted"]:.0f}s')
        print(f"  {flag} F0起伏 {r['std_semi']:5.2f}  {r['rate']:5.2f}字/s  "
              f"直出 {r['projected']:6.1f}s  {tail:16s} {r['voice']}")


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
