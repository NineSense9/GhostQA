"""Normalize per-paragraph pitch for designed-voice TTS narration.

``mimo-v2.5-tts-voicedesign`` re-derives the voice from the description on every
call, so paragraph medians drift (measured: up to 2.5 semitones across a script).
Listeners hear that as "different takes" between scenes. This helper measures
each paragraph's median F0, then shifts it to a common anchor with
``asetrate`` (pitch) + ``atempo`` (restores duration) — a deterministic,
reversible post-process. Paragraphs already within tolerance are left untouched.

Writes ``pitch.json`` next to the audio for the provenance record.

Usage:
  python tools/video_ghostqa/normalize_pitch.py --dir <audio_dir> [--tolerance 0.5]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import wave
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'video_ghostqa' / '.tmp_kokoro'))

import numpy as np  # noqa: E402


def load_pcm(path: Path):
    with wave.open(str(path), 'rb') as w:
        sr, n = w.getframerate(), w.getnframes()
        x = np.frombuffer(w.readframes(n), dtype='<i2').astype(np.float32) / 32768.0
        if w.getnchannels() == 2:
            x = x.reshape(-1, 2).mean(1)
    return sr, x


def median_f0(x: np.ndarray, sr: int) -> float:
    frame = int(0.040 * sr)
    lo, hi = int(sr / 300), int(sr / 70)
    f0 = []
    for s in range(0, len(x) - frame, int(0.010 * sr)):
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
        f0.append(sr / k)
    if len(f0) == 0:
        raise RuntimeError(f'no voiced frames found in {path}')
    return float(np.median(np.array(f0)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', type=Path, required=True)
    parser.add_argument('--tolerance', type=float, default=0.5,
                        help='semitones; paragraphs closer than this stay untouched')
    args = parser.parse_args()

    paragraph_dir = args.dir / 'paragraphs'
    wavs = sorted(paragraph_dir.glob('*.wav'))
    if not wavs:
        raise SystemExit(f'no paragraphs under {paragraph_dir}')

    measured = {}
    for wav in wavs:
        sr, x = load_pcm(wav)
        measured[wav.name] = (sr, median_f0(x, sr))
    anchor = float(np.median([m for _, m in measured.values()]))

    report = {'created_at_utc': datetime.now(timezone.utc).isoformat(),
              'anchor_hz': anchor, 'tolerance_semitones': args.tolerance,
              'files': {}}
    shifted = 0
    for name, (sr, hz) in measured.items():
        drift = 12 * float(np.log2(hz / anchor))
        row = {'before_hz': round(hz, 2), 'drift_semitones': round(drift, 3)}
        if abs(drift) > args.tolerance:
            factor = anchor / hz
            factor = max(0.8, min(1.25, factor))
            source, target = paragraph_dir / name, paragraph_dir / (name + '.tmp.wav')
            subprocess.run(
                ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', str(source),
                 '-af', f'asetrate={sr * factor:.2f},aresample={sr},atempo={1 / factor:.5f}',
                 '-c:a', 'pcm_s16le', str(target)], check=True)
            target.replace(source)
            sr2, x2 = load_pcm(source)
            after = median_f0(x2, sr2)
            row.update({'after_hz': round(after, 2), 'factor': round(factor, 4),
                        'duration_s': round(len(x2) / sr2, 2)})
            shifted += 1
        report['files'][name] = row
        print(f"  {name}: {hz:6.1f} Hz  drift {drift:+5.2f} st"
              + (f"  -> {row.get('after_hz', hz):6.1f} Hz" if 'after_hz' in row else '  (kept)'),
              flush=True)

    (args.dir / 'pitch.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'ANCHOR {anchor:.1f} Hz; shifted {shifted}/{len(wavs)} paragraphs')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
