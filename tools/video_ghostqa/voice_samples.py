"""Generate and verify the isolated GhostQA voice A/B samples.

Uses the installed edge_tts, ffmpeg and ffprobe. No production narration is
changed. The report records acoustic verification, not a subjective listen.
"""

from __future__ import annotations

import argparse
import asyncio
from array import array
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import wave

import edge_tts


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "artifacts" / "competition_video_ghostqa" / "voice_samples"
TEXT = (
    "这是 Ghost Q A。我们给它一个页面和业务规格，接下来的动作由系统按当前状态选择。"
    "这里出现的是候选异常，还不能算确认缺陷。它要先回到干净起点，完整重放这段操作，匹配同一缺陷指纹，"
    "再留下能复现的路径。"
)
SPEAKERS = (
    {"sample": "A_xiaoyi", "voice": "zh-CN-XiaoyiNeural", "name": "晓伊", "gender": "Female"},
    {"sample": "B_xiaoxiao", "voice": "zh-CN-XiaoxiaoNeural", "name": "晓晓", "gender": "Female"},
    {"sample": "C_yunjian", "voice": "zh-CN-YunjianNeural", "name": "云健", "gender": "Male"},
    {"sample": "D_yunyang", "voice": "zh-CN-YunyangNeural", "name": "云扬", "gender": "Male"},
    {"sample": "E_yunxia", "voice": "zh-CN-YunxiaNeural", "name": "云夏", "gender": "Male"},
    {"sample": "F_yunjian_slow", "voice": "zh-CN-YunjianNeural", "name": "云健（稳重版）", "gender": "Male", "rate": "-2%", "pitch": "-2Hz"},
    {"sample": "G_yunyang_slow", "voice": "zh-CN-YunyangNeural", "name": "云扬（稳重版）", "gender": "Male", "rate": "-2%", "pitch": "-2Hz"},
)
RATE = "+4%"
PITCH = "+0Hz"


def command(args: list[str]) -> str:
    proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode:
        raise RuntimeError(f"Command failed: {args!r}\n{proc.stderr}")
    return proc.stdout


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def probe(path: Path) -> dict:
    return json.loads(command([
        "ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)
    ]))


def acoustics(path: Path) -> dict:
    with wave.open(str(path), "rb") as wav:
        frames = wav.getnframes()
        sample_rate = wav.getframerate()
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        assert (sample_rate, channels, sample_width) == (48000, 1, 2)
        samples = array("h", wav.readframes(frames))
    if sys.byteorder != "little":
        samples.byteswap()
    peak = max(abs(v) for v in samples)
    rms = math.sqrt(sum(v * v for v in samples) / len(samples))
    return {
        "frames": frames,
        "sample_rate_hz": sample_rate,
        "channels": channels,
        "sample_width_bits": sample_width * 8,
        "duration_seconds": frames / sample_rate,
        "peak_absolute_pcm16": peak,
        "peak_dbfs": 20 * math.log10(peak / 32768) if peak else None,
        "rms_dbfs": 20 * math.log10(rms / 32768) if rms else None,
        "clipped_samples": sum(v <= -32768 or v >= 32767 for v in samples),
        "nonzero_samples": sum(v != 0 for v in samples),
    }


async def generate(out: Path, speaker: dict, text: str) -> None:
    stem = speaker["sample"]
    mp3 = out / f"{stem}.mp3"
    wav = out / f"{stem}.wav"
    events = []
    rate=speaker.get("rate", RATE); pitch=speaker.get("pitch", PITCH)
    communicate = edge_tts.Communicate(text, speaker["voice"], rate=rate, pitch=pitch,
                                      boundary="WordBoundary")
    with mp3.open("wb") as audio:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio.write(chunk["data"])
            else:
                event = dict(chunk)
                if "offset" in event:
                    event["offset_seconds"] = event["offset"] / 10_000_000
                if "duration" in event:
                    event["duration_seconds"] = event["duration"] / 10_000_000
                events.append(event)
    write_json(out / f"{stem}.boundaries.json", {
        "speaker": speaker, "rate": rate, "pitch": pitch, "text": text,
        "timebase": "raw offset and duration use 100 ns ticks; seconds are also included",
        "events": events,
    })
    command(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(mp3),
             "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", str(wav)])


def verify(out: Path, enforce_duration: bool) -> dict:
    reports = []
    for speaker in SPEAKERS:
        stem = speaker["sample"]
        boundaries = json.loads((out / f"{stem}.boundaries.json").read_text(encoding="utf-8"))
        assert boundaries["speaker"]["voice"] == speaker["voice"]
        assert boundaries["rate"] == speaker.get("rate", RATE) and boundaries["pitch"] == speaker.get("pitch", PITCH)
        assert boundaries["events"], "Missing TTS boundaries"
        for suffix in ("mp3", "wav"):
            path = out / f"{stem}.{suffix}"
            command(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path), "-f", "null", "-"])
        mp3_probe = probe(out / f"{stem}.mp3")
        wav_probe = probe(out / f"{stem}.wav")
        stats = acoustics(out / f"{stem}.wav")
        assert wav_probe["streams"][0]["codec_name"] == "pcm_s16le"
        assert stats["nonzero_samples"] > 0
        assert stats["clipped_samples"] == 0
        in_range = 18 <= stats["duration_seconds"] <= 23
        if enforce_duration:
            assert in_range, f"{stem} duration out of range: {stats['duration_seconds']:.3f}s"
        reports.append({
            "speaker": speaker,
            "rate": RATE,
            "pitch": PITCH,
            "text": boundaries["text"],
            "boundary_event_count": len(boundaries["events"]),
            "duration_target_18_to_23_seconds_pass": in_range,
            "full_decode_pass": True,
            "acoustic_stats": stats,
            "ffprobe": {"mp3": mp3_probe, "wav": wav_probe},
            "files": {
                suffix: {"path": str(out / f"{stem}.{suffix}"),
                         "sha256": hashlib.sha256((out / f"{stem}.{suffix}").read_bytes()).hexdigest()}
                for suffix in ("mp3", "wav", "boundaries.json")
            },
        })
        print(f"{stem}: WAV {stats['duration_seconds']:.3f}s; MP3 {float(mp3_probe['format']['duration']):.3f}s; "
              f"peak {stats['peak_dbfs']:.2f} dBFS; clipped {stats['clipped_samples']}; boundaries {len(boundaries['events'])}",
              flush=True)
    assert all(report["text"] == reports[0]["text"] for report in reports[1:]), "voice sample text mismatch"
    manifest = {
        "generated_or_verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "GhostQA isolated A/B voice audition samples",
        "tts_provider": "Microsoft Edge TTS via edge_tts",
        "subjective_listen_performed": False,
        "verification_method": "ffprobe format and duration, complete ffmpeg decode, PCM16 peak/RMS/clipping audit",
        "samples": reports,
    }
    write_json(out / "manifest.json", manifest)
    (out / "shared_text.txt").write_text(reports[0]["text"] + "\n", encoding="utf-8")
    return manifest


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--text", default=TEXT)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--allow-duration-outside-target", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if not args.verify_only:
        await asyncio.gather(*(generate(args.out, speaker, args.text) for speaker in SPEAKERS))
    verify(args.out, not args.allow_duration_outside_target)


if __name__ == "__main__":
    asyncio.run(main())
