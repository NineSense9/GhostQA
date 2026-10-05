"""Generate GhostQA paragraph audio with the official Qwen3-TTS demo.

This helper keeps the public Gradio call separate from the product runtime. It
reads the already reviewed script, requests one paragraph at a time, and saves
the returned WAV files plus a manifest. The public Space is rate limited, so a
failed paragraph is reported without replacing an earlier successful file.

Provider note (2026-10-05): the original endpoint
``qwen-qwen3-tts-demo`` was retired and now returns 404. The official
replacement is ``Qwen/Qwen3-TTS-Demo``, which keeps the identical
``/tts_interface(text, voice, language)`` signature and the same speaker list.
``Qwen/Qwen3-TTS`` is the newer Space and adds an ``instruct`` style field, but
its ZeroGPU backend refuses anonymous calls once the shared quota is spent, so
it is only usable with a Hugging Face token.

The local development machine needs ``gradio_client``. The production video
does not depend on this helper at runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone


SPACE = "Qwen/Qwen3-TTS-Demo"
API_NAME = "/tts_interface"
VOICE = "Ethan / 晨煦"
LANGUAGE = "Chinese / 中文"


def load_client():
    try:
        from gradio_client import Client
    except ImportError as exc:  # pragma: no cover - environment guidance
        raise SystemExit(
            "Missing gradio_client. Install it in a temporary environment; "
            "do not add it to GhostQA product dependencies."
        ) from exc
    return Client


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def result_path(result: object) -> str | None:
    """Qwen endpoints return either a bare path or ``(audio, status)``."""
    if isinstance(result, (list, tuple)):
        for item in result:
            found = result_path(item)
            if found:
                return found
        return None
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        return result.get("path") or result.get("value")
    return None


def call_kwargs(api_name: str, text: str, voice: str, language: str, instruct: str) -> dict:
    if api_name == "/generate_custom_voice":
        # speaker + instruct + model_size; language is the bare enum value here.
        return {"text": text, "language": language.split(" / ")[0],
                "speaker": voice.split(" / ")[0], "instruct": instruct or "自然朗读",
                "model_size": "1.7B"}
    return {"text": text, "voice_display": voice, "language_display": language}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--voice", default=None, help="defaults to script.speaker.voice")
    parser.add_argument("--language", default=None, help="defaults to script.speaker.language")
    parser.add_argument("--instruct", default=None, help="only used by /generate_custom_voice")
    parser.add_argument("--space", default=SPACE)
    parser.add_argument("--api-name", default=API_NAME)
    parser.add_argument("--retry", type=int, default=1)
    args = parser.parse_args()

    script = json.loads(args.script.read_text(encoding="utf-8-sig"))
    speaker = script.get("speaker", {})
    voice = args.voice or speaker.get("voice") or VOICE
    language = args.language or speaker.get("language") or LANGUAGE

    args.out.mkdir(parents=True, exist_ok=True)
    paragraph_dir = args.out / "paragraphs"
    paragraph_dir.mkdir(parents=True, exist_ok=True)
    Client = load_client()
    client = Client(args.space)
    manifest = {
        "provider": "Qwen3-TTS official Hugging Face Demo",
        "space": args.space,
        "api_name": args.api_name,
        "voice": voice,
        "language": language,
        "instruct": args.instruct,
        "script": str(args.script),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "paragraphs": [],
    }

    for scene_index, scene in enumerate(script["scenes"], 1):
        for paragraph_index, paragraph in enumerate(scene["paragraphs"], 1):
            stem = f"scene_{scene_index:02d}_paragraph_{paragraph_index:02d}"
            destination = paragraph_dir / f"{stem}.wav"
            row = {
                "scene_id": scene["id"],
                "scene_index": scene_index,
                "paragraph_index": paragraph_index,
                "display": paragraph["display"],
                "tts": paragraph["tts"],
                "file": str(destination),
            }
            if destination.is_file() and destination.stat().st_size > 1024:
                row.update({"status": "cached", "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()})
                manifest["paragraphs"].append(row)
                print(f"CACHED {stem}", flush=True)
                continue

            last_error = None
            for attempt in range(args.retry + 1):
                try:
                    result = client.predict(
                        api_name=args.api_name,
                        **call_kwargs(args.api_name, paragraph["tts"], voice, language, args.instruct or ""),
                    )
                    source = result_path(result)
                    if not source or not os.path.isfile(source):
                        raise RuntimeError(f"Qwen returned no local audio path: {result!r}")
                    shutil.copyfile(source, destination)
                    row.update({
                        "status": "generated",
                        "attempts": attempt + 1,
                        "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                    })
                    print(f"GENERATED {stem}: {destination.stat().st_size} bytes", flush=True)
                    break
                except Exception as exc:  # public Space errors need to remain visible in the manifest
                    last_error = repr(exc)
                    print(f"ERROR {stem} attempt {attempt + 1}: {last_error}", file=sys.stderr, flush=True)
            else:
                row.update({"status": "failed", "error": last_error})
            manifest["paragraphs"].append(row)
            write_json(args.out / "manifest.partial.json", manifest)

    write_json(args.out / "manifest.json", manifest)
    failed = [row for row in manifest["paragraphs"] if row["status"] == "failed"]
    if failed:
        raise SystemExit(f"Qwen generation incomplete: {len(failed)} paragraph(s) failed")
    print(f"COMPLETE {len(manifest['paragraphs'])} paragraphs", flush=True)


if __name__ == "__main__":
    main()
