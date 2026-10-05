"""Generate GhostQA paragraph audio with Xiaomi MiMo TTS (OpenAI-compatible).

Contract (platform.xiaomimimo.com, 2026-10-05):
  POST https://api.xiaomimimo.com/v1/chat/completions
  model  : mimo-v2.5-tts            preset voices + natural-language style
           mimo-v2.5-tts-voicedesign  voice designed from a text description
  target text goes in ``role: assistant``; optional style direction goes in
  ``role: user``; output audio comes back as base64 in
  ``choices[0].message.audio.data``.

The API key is read from ``MIMO_API_KEY`` (loaded from the repo-root ``.env``,
which is gitignored). The helper keeps this call separate from the product
runtime and, like qwen_tts.py, never overwrites a good paragraph with a failure.

The instruction to use is per-scene or per-script; the script file may carry a
``speaker.instruct`` field that this helper reads.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
API_URL = "https://api.xiaomimimo.com/v1/chat/completions"
DEFAULT_MODEL = "mimo-v2.5-tts"
DEFAULT_VOICE = "Dean"
DEFAULT_INSTRUCT = ("用平静、克制的新闻播报语气朗读，普通话标准，语速平稳适中，"
                    "语调平直，不要情绪起伏，像电视台新闻联播播音员。")


def load_key() -> str:
    key = os.environ.get("MIMO_API_KEY")
    if key:
        return key.strip()
    env = ROOT / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line.startswith("MIMO_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise SystemExit(
        "Missing MIMO_API_KEY. Put it in the repo-root .env (gitignored), "
        "never in the repository.")


def synth(text: str, model: str, voice: str, instruct: str, timeout: int = 120) -> bytes:
    """One paragraph in, raw WAV bytes out. Raises on any failure."""
    messages = []
    if instruct:
        messages.append({"role": "user", "content": instruct})
    messages.append({"role": "assistant", "content": text})
    audio_params = {"format": "wav"}
    if voice:
        audio_params["voice"] = voice
    if model.endswith("voicedesign"):
        # Never let the API rewrite the narration: every number in the script
        # comes from the recorded run and must reach the model verbatim.
        audio_params["optimize_text_preview"] = False
    body = {
        "model": model,
        "messages": messages,
        "audio": audio_params,
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {load_key()}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    audio = payload.get("choices", [{}])[0].get("message", {}).get("audio")
    if not audio or not audio.get("data"):
        raise RuntimeError(f"MiMo returned no audio: {json.dumps(payload)[:300]}")
    return base64.b64decode(audio["data"])


def wav_seconds(data: bytes) -> float:
    import io
    import wave
    with wave.open(io.BytesIO(data), "rb") as w:
        return w.getnframes() / w.getframerate()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--voice", default=None, help="preset voice id; defaults to script.speaker.voice")
    parser.add_argument("--instruct", default=None, help="style direction; defaults to script.speaker.instruct")
    parser.add_argument("--retry", type=int, default=2)
    args = parser.parse_args()

    script = json.loads(args.script.read_text(encoding="utf-8-sig"))
    speaker = script.get("speaker", {})
    voice = args.voice or speaker.get("voice") or DEFAULT_VOICE
    instruct = args.instruct if args.instruct is not None else speaker.get("instruct", "")

    args.out.mkdir(parents=True, exist_ok=True)
    paragraph_dir = args.out / "paragraphs"
    paragraph_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "provider": "Xiaomi MiMo TTS (OpenAI-compatible)",
        "api_url": API_URL,
        "model": args.model,
        "voice": voice,
        "instruct": instruct,
        "script": str(args.script),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "paragraphs": [],
    }

    for scene_index, scene in enumerate(script["scenes"], 1):
        scene_instruct = instruct
        if isinstance(scene, dict) and scene.get("instruct"):
            scene_instruct = scene["instruct"]
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
                row.update({"status": "cached",
                            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()})
                manifest["paragraphs"].append(row)
                print(f"CACHED {stem}", flush=True)
                continue

            last_error = None
            for attempt in range(args.retry + 1):
                try:
                    data = synth(paragraph["tts"], args.model, voice, scene_instruct)
                    if len(data) < 4096:
                        raise RuntimeError(f"suspiciously small audio ({len(data)} bytes)")
                    destination.write_bytes(data)
                    row.update({
                        "status": "generated",
                        "attempts": attempt + 1,
                        "seconds": round(wav_seconds(data), 2),
                        "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                    })
                    print(f"GENERATED {stem}: {len(data)} bytes "
                          f"{row['seconds']}s", flush=True)
                    break
                except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError,
                        TimeoutError, json.JSONDecodeError) as exc:
                    detail = getattr(exc, "read", lambda: b"")()
                    last_error = f"{type(exc).__name__}: {exc} {detail[:200]!r}"
                    print(f"ERROR {stem} attempt {attempt + 1}: {last_error}",
                          file=sys.stderr, flush=True)
                    if attempt < args.retry:
                        time.sleep(2 * (attempt + 1))
            else:
                row.update({"status": "failed", "error": last_error})
            manifest["paragraphs"].append(row)
            (args.out / "manifest.partial.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    (args.out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    failed = [row for row in manifest["paragraphs"] if row["status"] == "failed"]
    if failed:
        raise SystemExit(f"MiMo generation incomplete: {len(failed)} paragraph(s) failed")
    print(f"COMPLETE {len(manifest['paragraphs'])} paragraphs", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
