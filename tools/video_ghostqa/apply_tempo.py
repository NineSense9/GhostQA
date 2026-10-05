"""Apply one global tempo factor to a paragraph directory (pitch preserved).

TTS output cannot be re-prompted for speed, and the competition caps the video
at five minutes. After the real narration is generated, --fit computes the true
total; if it overshoots, this helper speeds every paragraph by the same factor
with ffmpeg ``atempo`` (time-scale without pitch change) so pacing stays
consistent across scenes.

Idempotent: refuses to run twice on the same directory unless --force, and
records the factor in ``tempo.json``.

Usage:
  python tools/video_ghostqa/apply_tempo.py --dir <audio_dir> --tempo 1.03
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import wave
from datetime import datetime, timezone
from pathlib import Path


def wav_seconds(path: Path) -> float:
    with wave.open(str(path), 'rb') as w:
        return w.getnframes() / w.getframerate()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', type=Path, required=True)
    parser.add_argument('--tempo', type=float, required=True,
                        help='playback speedup factor, e.g. 1.03 = 3% faster')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    if not 0.8 <= args.tempo <= 1.2:
        raise SystemExit('tempo outside 0.8-1.2 would be audible; adjust the script instead')

    tempo_file = args.dir / 'tempo.json'
    if tempo_file.is_file() and not args.force:
        raise SystemExit(f'{tempo_file} already exists; pass --force to reapply')

    paragraph_dir = args.dir / 'paragraphs'
    wavs = sorted(paragraph_dir.glob('*.wav'))
    if not wavs:
        raise SystemExit(f'no paragraphs under {paragraph_dir}')

    before = {w.name: round(wav_seconds(w), 2) for w in wavs}
    for wav in wavs:
        target = paragraph_dir / (wav.name + '.tmp.wav')
        subprocess.run(
            ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', str(wav),
             '-af', f'atempo={args.tempo:.5f}', '-c:a', 'pcm_s16le', str(target)],
            check=True)
        target.replace(wav)
        print(f'  {wav.name}: {before[wav.name]:.2f}s -> {wav_seconds(wav):.2f}s', flush=True)

    after = {w.name: round(wav_seconds(w), 2) for w in wavs}
    tempo_file.write_text(json.dumps({
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'tempo': args.tempo, 'before_seconds': before, 'after_seconds': after,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    total_before, total_after = sum(before.values()), sum(after.values())
    print(f'APPLIED tempo {args.tempo}: narration {total_before:.1f}s -> {total_after:.1f}s')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
