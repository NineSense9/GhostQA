"""Generate GhostQA narration, timing metadata and bounded display subtitles.

Input: {speaker, scenes:[{id,start,end,paragraphs:[{display,tts}]}]}.
Speaker may be a voice string or {voice,rate,pitch}. CLI values override it.
The output is exactly 260 seconds, PCM16 mono at 48 kHz. Scene padding never
speeds up speech. --dry-run is offline; --assemble-only requires cached audio.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import wave

import aiohttp
import edge_tts
from edge_tts.exceptions import EdgeTTSException


SAMPLE_RATE = 48000
TOTAL_SECONDS = 260
TOTAL_FRAMES = SAMPLE_RATE * TOTAL_SECONDS
DEFAULT_VOICE = "zh-CN-XiaoyiNeural"
DEFAULT_RATE = "+4%"
DEFAULT_PITCH = "+0Hz"


def frames(seconds: float) -> int:
    return round(seconds * SAMPLE_RATE)


def seconds(frame: int) -> float:
    return frame / SAMPLE_RATE


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(args: list[str]) -> str:
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {args!r}\n{result.stderr}")
    return result.stdout


def validate_script(data: dict) -> dict:
    if not isinstance(data, dict) or not isinstance(data.get("scenes"), list) or not data["scenes"]:
        raise ValueError("script.json must contain a nonempty scenes list")
    previous_end = 0
    identifiers = set()
    for scene in data["scenes"]:
        if not isinstance(scene, dict) or not all(k in scene for k in ("id", "start", "end", "paragraphs")):
            raise ValueError("Each scene needs id, start, end and paragraphs")
        identifier = str(scene["id"])
        if not identifier or identifier in identifiers:
            raise ValueError(f"Duplicate or empty scene id: {identifier!r}")
        identifiers.add(identifier)
        start, end = scene["start"], scene["end"]
        if (isinstance(start, bool) or isinstance(end, bool) or
                not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or
                not math.isfinite(start) or not math.isfinite(end) or not 0 <= start < end <= TOTAL_SECONDS):
            raise ValueError(f"Scene {identifier}: require 0 <= start < end <= {TOTAL_SECONDS}")
        if frames(start) < previous_end:
            raise ValueError(f"Scene {identifier}: overlap or scenes are not in chronological order")
        if frames(end) <= frames(start):
            raise ValueError(f"Scene {identifier}: duration is below one sample")
        previous_end = frames(end)
        if not isinstance(scene["paragraphs"], list):
            raise ValueError(f"Scene {identifier}: paragraphs must be a list")
        for index, paragraph in enumerate(scene["paragraphs"]):
            if not isinstance(paragraph, dict) or any(
                not isinstance(paragraph.get(key), str) or not paragraph[key].strip() for key in ("display", "tts")
            ):
                raise ValueError(f"Scene {identifier}, paragraph {index + 1}: need nonempty display and tts")
    return data


def resolve_speaker(data: dict, voice: str | None = None, rate: str | None = None,
                    pitch: str | None = None) -> dict:
    supplied = data.get("speaker") or {}
    if isinstance(supplied, str):
        supplied = {"voice": supplied}
    if not isinstance(supplied, dict):
        raise ValueError("speaker must be a voice string or an object with voice, rate and pitch")
    result = {"voice": voice or supplied.get("voice") or DEFAULT_VOICE,
              "rate": rate or supplied.get("rate") or DEFAULT_RATE,
              "pitch": pitch or supplied.get("pitch") or DEFAULT_PITCH}
    if not isinstance(result["voice"], str) or not result["voice"].strip():
        raise ValueError("speaker.voice must be a nonempty string")
    if not isinstance(result["rate"], str) or not re.fullmatch(r"[+-]\d+%", result["rate"]):
        raise ValueError("rate must look like +4%")
    if not isinstance(result["pitch"], str) or not re.fullmatch(r"[+-]\d+Hz", result["pitch"]):
        raise ValueError("pitch must look like +0Hz")
    return result


def wav_frames(path: Path) -> int:
    with wave.open(str(path), "rb") as audio:
        if (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) != (SAMPLE_RATE, 1, 2):
            raise ValueError(f"Expected PCM16 mono 48kHz WAV: {path}")
        if audio.getcomptype() != "NONE" or audio.getnframes() <= 0:
            raise ValueError(f"Empty or compressed WAV: {path}")
        return audio.getnframes()


def cache_paths(out: Path, scene_index: int, paragraph_index: int) -> dict:
    stem = out / "paragraphs" / f"scene_{scene_index + 1:02d}_paragraph_{paragraph_index + 1:02d}"
    return {"mp3": stem.with_suffix(".mp3"), "wav": stem.with_suffix(".wav"),
            "boundary_json": stem.with_suffix(".boundaries.json")}


def cache_key(text: str, speaker: dict, boundary: str) -> str:
    payload = json.dumps({"text": text, "speaker": speaker, "boundary": boundary},
                         ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_cached(paths: dict, key: str) -> dict | None:
    if not all(path.is_file() for path in paths.values()):
        return None
    try:
        metadata = json.loads(paths["boundary_json"].read_text(encoding="utf-8"))
        if metadata.get("cache_key") != key or not metadata.get("events"):
            return None
        for name in ("mp3", "wav"):
            if hashlib.sha256(paths[name].read_bytes()).hexdigest() != metadata["sha256"][name]:
                return None
        count = wav_frames(paths["wav"])
        return {**{name: str(path) for name, path in paths.items()}, "frames": count,
                "events": metadata["events"], "cache_key": key, "cached": True,
                "network_attempts": metadata.get("network_attempts"), "boundary_type": metadata["boundary_type"]}
    except (ValueError, KeyError, OSError, wave.Error):
        return None


async def synthesize(paragraph: dict, paths: dict, speaker: dict, boundary: str,
                     retries: int, semaphore: asyncio.Semaphore, cached_only: bool = False) -> dict:
    key = cache_key(paragraph["tts"], speaker, boundary)
    cached = load_cached(paths, key)
    if cached:
        return cached
    if cached_only:
        raise ValueError(f"Valid cached audio is missing: {paths['wav']}")
    async with semaphore:
        paths["mp3"].parent.mkdir(parents=True, exist_ok=True)
        temporary = paths["mp3"].with_suffix(".mp3.partial")
        events = []
        for attempt in range(retries + 1):
            try:
                events = []
                communicate = edge_tts.Communicate(paragraph["tts"], speaker["voice"],
                    rate=speaker["rate"], pitch=speaker["pitch"], boundary=boundary)
                with temporary.open("wb") as audio:
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
                if not events or temporary.stat().st_size == 0:
                    raise edge_tts.exceptions.NoAudioReceived("Empty audio or boundaries")
                temporary.replace(paths["mp3"])
                break
            except (aiohttp.ClientError, TimeoutError, EdgeTTSException) as error:
                if attempt == retries:
                    raise RuntimeError(f"TTS failed after {attempt + 1} attempts: {paths['mp3'].name}: {error}") from error
                print(f"Retry {attempt + 1}/{retries}: {paths['mp3'].name}: {type(error).__name__}", file=sys.stderr, flush=True)
                await asyncio.sleep(2 ** attempt)
        await asyncio.to_thread(run, ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(paths["mp3"]), "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(paths["wav"])])
        count = wav_frames(paths["wav"])
        metadata = {"cache_key": key, "speaker": speaker, "tts": paragraph["tts"],
                    "display": paragraph["display"], "boundary_type": boundary,
                    "timebase": "offset/duration are 100ns ticks; *_seconds are relative to paragraph audio",
                    "network_attempts": attempt + 1, "events": events,
                    "sha256": {name: hashlib.sha256(paths[name].read_bytes()).hexdigest() for name in ("mp3", "wav")}}
        write_json(paths["boundary_json"], metadata)
        print(f"Generated {paths['wav'].name}: {seconds(count):.3f}s", flush=True)
        return {**{name: str(path) for name, path in paths.items()}, "frames": count,
                "events": events, "cache_key": key, "cached": False, "network_attempts": attempt + 1,
                "boundary_type": boundary}


def layout_scene(scene: dict, assets: list[dict], min_pause: float) -> dict:
    start, end = frames(scene["start"]), frames(scene["end"])
    if len(assets) != len(scene["paragraphs"]):
        raise ValueError(f"Scene {scene['id']}: paragraph/audio count mismatch")
    used = sum(asset["frames"] for asset in assets)
    budget = frames(min_pause * len(assets))
    remaining = end - start - used
    if remaining < budget:
        shortage = seconds(budget - remaining)
        raise ValueError(f"Scene {scene['id']}: speech {seconds(used):.3f}s + natural pause budget "
                         f"{seconds(budget):.3f}s exceeds scene {seconds(end - start):.3f}s by {shortage:.3f}s")
    slots = len(assets) + 1
    quotient, remainder = divmod(remaining, slots)
    gap_lengths = [quotient + (index < remainder) for index in range(slots)]
    silences, paragraphs = [], []
    cursor = start
    for index, gap in enumerate(gap_lengths):
        silence = {"kind": "head" if index == 0 else "tail" if index == slots - 1 else "between_paragraphs",
                   "start_frame": cursor, "end_frame": cursor + gap, "frames": gap,
                   "start": seconds(cursor), "end": seconds(cursor + gap), "duration": seconds(gap)}
        if not assets:
            silence["kind"] = "silent_scene"
        silences.append(silence)
        cursor += gap
        if index < len(assets):
            finish = cursor + assets[index]["frames"]
            paragraphs.append({"index": index + 1, "display": scene["paragraphs"][index]["display"],
                               "tts": scene["paragraphs"][index]["tts"], "start_frame": cursor,
                               "end_frame": finish, "start": seconds(cursor), "end": seconds(finish),
                               "duration": seconds(finish - cursor), "audio": {
                                   k: v for k, v in assets[index].items() if k != "events"}})
            cursor = finish
    if cursor != end:
        raise RuntimeError("Internal timing error: scene does not end on its requested sample")
    return {"id": scene["id"], "start": seconds(start), "end": seconds(end),
            "start_frame": start, "end_frame": end, "duration": seconds(end - start),
            "speech_duration": seconds(used), "minimum_natural_pause_per_paragraph": min_pause,
            "minimum_natural_pause_total": seconds(budget), "total_silence": seconds(remaining),
            "pause_distribution": "all remaining samples divided equally across head, between-paragraph, tail slots",
            "silences": silences, "paragraphs": paragraphs}


def text_weight(text: str) -> int:
    return max(1, sum(char.isalnum() for char in text))


def sentences(text: str) -> list[str]:
    return [part.strip() for part in re.findall(r"[^。！？!?；;]+[。！？!?；;]*", text) if part.strip()]


def subtitle_parts(text: str) -> list[str]:
    if text_weight(text) <= 32:
        return [text]
    pieces = [part.strip() for part in re.findall(r"[^，,：:]+[，,：:]*", text) if part.strip()]
    return pieces or [text]


def build_cues(display: str, tts: str, events: list[dict], start_frame: int, end_frame: int) -> list[dict]:
    """Map display sentences onto boundary-weighted TTS progress within one paragraph.

    Matching sentence counts use TTS sentence weights (so phonetic names do not
    shift subsequent captions). Otherwise use paragraph-wide proportional
    mapping. These are initial timings, requiring final listen/ASR verification.
    """
    duration = end_frame - start_frame
    boundary_events = sorted((event for event in events if "offset" in event and "duration" in event),
                             key=lambda event: event["offset"])
    if not boundary_events:
        raise ValueError("Paragraph has no timed TTS boundaries")
    timed = []
    for event in boundary_events:
        begin = max(0, min(duration, frames(event["offset"] / 10_000_000)))
        finish = max(begin, min(duration, frames((event["offset"] + event["duration"]) / 10_000_000)))
        if finish > begin:
            timed.append((begin, finish, text_weight(event.get("text", ""))))
    if not timed:
        raise ValueError("TTS boundary times fall outside paragraph audio")
    total_weight = sum(item[2] for item in timed)

    def position(fraction: float) -> int:
        target, consumed = fraction * total_weight, 0
        if fraction <= 0:
            return timed[0][0]
        if fraction >= 1:
            return timed[-1][1]
        for begin, finish, weight in timed:
            if target <= consumed + weight:
                return round(begin + (finish - begin) * (target - consumed) / weight)
            consumed += weight
        return timed[-1][1]

    display_sentences, tts_sentences = sentences(display), sentences(tts)
    matched = len(display_sentences) == len(tts_sentences)
    weights = [text_weight(text) for text in (tts_sentences if matched else display_sentences)]
    total = sum(weights)
    cues, cumulative = [], 0
    previous_finish = start_frame
    for sentence, weight in zip(display_sentences, weights):
        pieces = subtitle_parts(sentence)
        piece_total = sum(text_weight(piece) for piece in pieces)
        within = 0
        for piece in pieces:
            piece_weight = text_weight(piece)
            begin_fraction = (cumulative + weight * within / piece_total) / total
            end_fraction = (cumulative + weight * (within + piece_weight) / piece_total) / total
            begin = max(previous_finish, start_frame + position(begin_fraction))
            finish = min(end_frame, start_frame + position(end_fraction))
            if finish <= begin:
                raise ValueError(f"Insufficient boundary time for caption {piece!r}")
            cues.append({"text": piece, "start_frame": begin, "end_frame": finish,
                         "start": seconds(begin), "end": seconds(finish),
                         "mapping": "tts_sentence_character_ratio_to_service_boundaries" if matched
                                    else "display_paragraph_character_ratio_to_service_boundaries"})
            previous_finish = finish
            within += piece_weight
        cumulative += weight
    return cues


def srt_time(frame: int, edge: str = "round") -> str:
    # Round inward at caption edges, so millisecond SRT precision cannot move
    # a subtitle outside its sample-accurate paragraph interval.
    if edge == "start":
        milliseconds = (frame * 1000 + SAMPLE_RATE - 1) // SAMPLE_RATE
    elif edge == "end":
        milliseconds = frame * 1000 // SAMPLE_RATE
    else:
        milliseconds = round(frame * 1000 / SAMPLE_RATE)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def write_silence(audio: wave.Wave_write, count: int) -> None:
    block = b"\x00" * (SAMPLE_RATE * 2)
    while count:
        chunk = min(count, SAMPLE_RATE)
        audio.writeframesraw(block[:chunk * 2])
        count -= chunk


def assemble(data: dict, all_assets: list[list[dict]], out: Path, speaker: dict, min_pause: float) -> dict:
    if len(all_assets) != len(data["scenes"]):
        raise ValueError("Scene/audio count mismatch")
    layouts = [layout_scene(scene, assets, min_pause) for scene, assets in zip(data["scenes"], all_assets)]
    cues = []
    for layout, assets in zip(layouts, all_assets):
        for paragraph, asset in zip(layout["paragraphs"], assets):
            paragraph_cues = build_cues(paragraph["display"], paragraph["tts"], asset["events"],
                                       paragraph["start_frame"], paragraph["end_frame"])
            paragraph["subtitles"] = paragraph_cues
            cues.extend({**cue, "scene_id": layout["id"], "paragraph_index": paragraph["index"]}
                        for cue in paragraph_cues)
    out.mkdir(parents=True, exist_ok=True)
    temporary = out / "voiceover.partial.wav"
    cursor, global_silences = 0, []
    with wave.open(str(temporary), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(SAMPLE_RATE)
        for layout in layouts:
            if layout["start_frame"] > cursor:
                gap = layout["start_frame"] - cursor
                global_silences.append({"kind": "outside_scenes", "start_frame": cursor,
                    "end_frame": cursor + gap, "start": seconds(cursor), "end": seconds(cursor + gap),
                    "duration": seconds(gap), "frames": gap})
                write_silence(audio, gap)
                cursor += gap
            for index, silence in enumerate(layout["silences"]):
                write_silence(audio, silence["frames"])
                cursor += silence["frames"]
                if index < len(layout["paragraphs"]):
                    paragraph = layout["paragraphs"][index]
                    source = Path(paragraph["audio"]["wav"])
                    if wav_frames(source) != paragraph["end_frame"] - paragraph["start_frame"]:
                        raise ValueError(f"Audio changed since layout: {source}")
                    with wave.open(str(source), "rb") as clip:
                        while chunk := clip.readframes(SAMPLE_RATE):
                            audio.writeframesraw(chunk)
                    cursor = paragraph["end_frame"]
        if cursor < TOTAL_FRAMES:
            gap = TOTAL_FRAMES - cursor
            global_silences.append({"kind": "outside_scenes", "start_frame": cursor,
                "end_frame": TOTAL_FRAMES, "start": seconds(cursor), "end": TOTAL_SECONDS,
                "duration": seconds(gap), "frames": gap})
            write_silence(audio, gap)
    if wav_frames(temporary) != TOTAL_FRAMES:
        raise RuntimeError("Final narration is not exactly 260 seconds")
    temporary.replace(out / "voiceover.wav")
    for cue in cues:
        if ((cue["start_frame"] * 1000 + SAMPLE_RATE - 1) // SAMPLE_RATE >=
                cue["end_frame"] * 1000 // SAMPLE_RATE):
            raise ValueError(f"Subtitle duration is too short for SRT millisecond precision: {cue['text']!r}")
    srt = "\n\n".join(f"{index}\n{srt_time(cue['start_frame'], 'start')} --> {srt_time(cue['end_frame'], 'end')}\n{cue['text']}"
                        for index, cue in enumerate(cues, 1))
    (out / "subtitles.srt").write_text(srt + ("\n" if srt else ""), encoding="utf-8")
    result = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "speaker": speaker,
              "total_seconds": TOTAL_SECONDS, "sample_rate": SAMPLE_RATE, "channels": 1,
              "sample_width_bits": 16, "total_frames": TOTAL_FRAMES,
              "subjective_listen_performed": False, "asr_verified": False,
              "subtitle_status": "initial sentence mapping from TTS boundaries; final listen/ASR required",
              "global_silences": global_silences, "scenes": layouts, "subtitles": cues}
    write_json(out / "timings.json", result)
    return result


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--out", type=Path, help="Default: script.json parent / audio")
    parser.add_argument("--voice", help="Override script speaker voice")
    parser.add_argument("--rate", help="Override rate, e.g. +4%%")
    parser.add_argument("--pitch", help="Override pitch, e.g. +0Hz")
    parser.add_argument("--boundary", choices=("WordBoundary", "SentenceBoundary"), default="WordBoundary")
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    parser.add_argument("--retries", type=int, choices=range(4), default=3,
                        help="Network retries after initial attempt (maximum 3)")
    parser.add_argument("--min-pause", type=float, default=0.35, help="Minimum pause budget seconds per paragraph")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs and CLI settings offline")
    parser.add_argument("--assemble-only", action="store_true", help="Use valid paragraph cache; do not call TTS")
    args = parser.parse_args()
    if not math.isfinite(args.min_pause) or args.min_pause < 0:
        raise ValueError("--min-pause must be a nonnegative finite number")
    data = validate_script(json.loads(args.script.read_text(encoding="utf-8-sig")))
    speaker = resolve_speaker(data, args.voice, args.rate, args.pitch)
    out = (args.out or args.script.parent / "audio").resolve()
    for executable in ("ffmpeg", "ffprobe"):
        if not shutil.which(executable):
            raise RuntimeError(f"Required installed executable missing: {executable}")
    print(f"Speaker: {speaker}; scenes: {len(data['scenes'])}; paragraphs: "
          f"{sum(len(scene['paragraphs']) for scene in data['scenes'])}; output: {out}", flush=True)
    if args.dry_run:
        print("Input valid. No network request or audio output was made.")
        return
    out.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(args.workers)
    jobs = [synthesize(paragraph, cache_paths(out, scene_index, paragraph_index), speaker,
                       args.boundary, args.retries, semaphore, args.assemble_only)
            for scene_index, scene in enumerate(data["scenes"])
            for paragraph_index, paragraph in enumerate(scene["paragraphs"])]
    generated = await asyncio.gather(*jobs)
    all_assets, cursor = [], 0
    for scene in data["scenes"]:
        count = len(scene["paragraphs"])
        all_assets.append(generated[cursor:cursor + count])
        cursor += count
    try:
        result = assemble(data, all_assets, out, speaker, args.min_pause)
    except ValueError as error:
        write_json(out / "assembly_error.json", {"error": str(error), "script": str(args.script.resolve()),
                                                "speaker": speaker})
        raise
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(out / "voiceover.wav"), "-f", "null", "-"])
    result["ffprobe"] = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format",
                                      "-of", "json", str(out / "voiceover.wav")]))
    result["script_path"] = str(args.script.resolve())
    result["script_sha256"] = hashlib.sha256(args.script.read_bytes()).hexdigest()
    result["full_decode_pass"] = True
    write_json(out / "timings.json", result)
    print(f"Complete: {out / 'voiceover.wav'} (260.000s); {len(result['subtitles'])} subtitle cues", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (ValueError, RuntimeError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
