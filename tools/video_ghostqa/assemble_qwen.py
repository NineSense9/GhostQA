"""Assemble Qwen paragraph WAVs into the script-defined GhostQA timeline."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import wave
from datetime import datetime, timezone
from pathlib import Path

SAMPLE_RATE = 48_000


def ffmpeg_resample(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
         "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(destination)],
        check=True,
    )


def wav_frames(path: Path) -> int:
    with wave.open(str(path), "rb") as audio:
        if (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) != (SAMPLE_RATE, 1, 2):
            raise ValueError(f"Unexpected WAV format: {path}")
        return audio.getnframes()


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in re.findall(r"[^。！？!?；;]+[。！？!?；;]*", text) if part.strip()]


def text_weight(text: str) -> int:
    return max(1, sum(ch.isalnum() for ch in text))


def make_cues(text: str, start: int, end: int) -> list[dict]:
    sentences = split_sentences(text)
    weights = [text_weight(sentence) for sentence in sentences]
    total = sum(weights) or 1
    cues, cursor = [], start
    for index, (sentence, weight) in enumerate(zip(sentences, weights)):
        next_cursor = cursor + round((end - start) * weight / total)
        if index == len(sentences) - 1:
            next_cursor = end
        if next_cursor <= cursor:
            next_cursor = min(end, cursor + 1)
        cues.append({"text": sentence, "start_frame": cursor, "end_frame": next_cursor})
        cursor = next_cursor
    return cues


def srt_time(frame: int) -> str:
    millis = round(frame * 1000 / SAMPLE_RATE)
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def silence(audio: wave.Wave_write, frames: int) -> None:
    block = b"\x00" * (SAMPLE_RATE * 2)
    while frames:
        chunk = min(frames, SAMPLE_RATE)
        audio.writeframesraw(block[: chunk * 2])
        frames -= chunk


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--audio-dir", type=Path, required=True)
    args = parser.parse_args()
    script = json.loads(args.script.read_text(encoding="utf-8-sig"))
    total_seconds = int(script["duration"])
    paragraph_dir = args.audio_dir / "paragraphs"
    normalized = args.audio_dir / "normalized"
    normalized.mkdir(parents=True, exist_ok=True)

    assets = {}
    for scene_index, scene in enumerate(script["scenes"], 1):
        for paragraph_index, _paragraph in enumerate(scene["paragraphs"], 1):
            stem = f"scene_{scene_index:02d}_paragraph_{paragraph_index:02d}"
            source = paragraph_dir / f"{stem}.wav"
            if not source.is_file():
                raise FileNotFoundError(source)
            destination = normalized / f"{stem}.wav"
            if not destination.is_file():
                ffmpeg_resample(source, destination)
            assets[(scene_index, paragraph_index)] = destination

    layouts, cues = [], []
    cursor = 0
    with wave.open(str(args.audio_dir / "voiceover.wav.partial"), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        for scene_index, scene in enumerate(script["scenes"], 1):
            scene_start = round(scene["start"] * SAMPLE_RATE)
            scene_end = round(scene["end"] * SAMPLE_RATE)
            if scene_start > cursor:
                silence(output, scene_start - cursor)
                cursor = scene_start
            clips = []
            for paragraph_index, paragraph in enumerate(scene["paragraphs"], 1):
                path = assets[(scene_index, paragraph_index)]
                frames = wav_frames(path)
                clips.append((paragraph, path, frames))
            remaining = scene_end - scene_start - sum(frames for _, _, frames in clips)
            minimum_pause = round(0.35 * SAMPLE_RATE) * len(clips)
            if remaining < minimum_pause:
                raise ValueError(f"Scene {scene['id']} is too short for Qwen audio: {remaining / SAMPLE_RATE:.2f}s remaining")
            gap, extra = divmod(remaining, len(clips) + 1)
            scene_rows = []
            for index in range(len(clips) + 1):
                gap_frames = gap + (1 if index < extra else 0)
                silence(output, gap_frames)
                cursor += gap_frames
                if index >= len(clips):
                    continue
                paragraph, path, frames = clips[index]
                start = cursor
                with wave.open(str(path), "rb") as clip:
                    while chunk := clip.readframes(SAMPLE_RATE):
                        output.writeframesraw(chunk)
                cursor += frames
                paragraph_cues = make_cues(paragraph["display"], start, cursor)
                for cue in paragraph_cues:
                    cues.append({**cue, "scene_id": scene["id"], "paragraph_index": index + 1})
                scene_rows.append({
                    "index": index + 1,
                    "start": start / SAMPLE_RATE,
                    "end": cursor / SAMPLE_RATE,
                    "duration": frames / SAMPLE_RATE,
                    "audio": str(path),
                    "subtitles": paragraph_cues,
                })
            if cursor != scene_end:
                raise ValueError(f"Scene {scene['id']} ended at {cursor}, expected {scene_end}")
            layouts.append({"id": scene["id"], "start": scene["start"], "end": scene["end"], "paragraphs": scene_rows})
        if cursor < total_seconds * SAMPLE_RATE:
            silence(output, total_seconds * SAMPLE_RATE - cursor)
            cursor = total_seconds * SAMPLE_RATE
    voiceover = args.audio_dir / "voiceover.wav"
    (args.audio_dir / "voiceover.wav.partial").replace(voiceover)
    if wav_frames(voiceover) != total_seconds * SAMPLE_RATE:
        raise ValueError(f"Qwen voiceover is not exactly {total_seconds} seconds")

    srt = "\n\n".join(
        f"{i}\n{srt_time(cue['start_frame'])} --> {srt_time(cue['end_frame'])}\n{cue['text']}"
        for i, cue in enumerate(cues, 1)
    ) + "\n"
    (args.audio_dir / "subtitles.srt").write_text(srt, encoding="utf-8")
    timings = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "provider": script.get("speaker", {}).get("provider", "unknown"),
        "voice": script.get("speaker", {}).get("voice") or script.get("speaker", {}).get("model", ""),
        "instruct": script.get("speaker", {}).get("instruct", ""),
        "language": script.get("speaker", {}).get("language", ""),
        "total_seconds": total_seconds,
        "sample_rate": SAMPLE_RATE,
        "channels": 1,
        "sample_width_bits": 16,
        "subjective_listen_performed": False,
        "asr_verified": False,
        "subtitle_status": "proportional paragraph timing; final listen required",
        "scenes": layouts,
        "subtitles": cues,
    }
    (args.audio_dir / "timings.json").write_text(json.dumps(timings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"COMPLETE {voiceover} / {len(cues)} subtitle cues", flush=True)


if __name__ == "__main__":
    main()
