"""v0.3.28 measurement. Reads published traces. Does not change a candidate."""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVIDENCE = os.path.join(
    ROOT, "experiments", "published", "episode-drain-epoch-v0.3.24", "evidence")
APPS = ("buggy-campus", "buggy-studio")
STEM = "ghost-structural-episode-drain-epoch-guard_b120_s1"


def _rows(path: str) -> list:
    out = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _eid(step_text: str) -> str:
    if ":" not in step_text:
        return step_text.strip()
    return step_text.split(":", 1)[1].strip().split("=")[0].strip()


def measure_app(app: str) -> dict:
    events = _rows(os.path.join(EVIDENCE, app, STEM + ".events.jsonl"))
    metrics = json.load(open(os.path.join(EVIDENCE, app, "metrics.json"), encoding="utf-8"))
    run = [
        item for item in metrics.get("runs") or []
        if int(item.get("budget") or 0) == 120
        and "episode-drain" in (item.get("policy") or "")
    ][0]
    confirmed = set(run.get("confirmed_bugs") or [])
    resets = [item for item in (run.get("reset_events") or []) if item.get("reason") == "relocate"]
    reset_at = None if not resets else int(resets[0]["before_step"])
    manifest = json.load(open(os.path.join(ROOT, "apps", app, "bugs.manifest.json"), encoding="utf-8"))
    before = {}
    after = {}
    for step in events:
        if step.get("kind") != "step":
            continue
        idx = int(step.get("index"))
        action = step.get("action") or {}
        eid = action.get("target_eid") or ""
        sig = step.get("src_sig") or ""
        if not eid or reset_at is None:
            continue
        bucket = before if idx < reset_at else after
        bucket.setdefault(sig, set()).add(eid)
    misses = []
    if reset_at is not None:
        for bug in manifest["bugs"]:
            if bug["id"] in confirmed:
                continue
            controls = [_eid(item) for item in bug.get("min_reproduction") or []]
            for sig, eids in before.items():
                shared = [item for item in controls if item in eids]
                if not shared:
                    continue
                later = after.get(sig, set())
                stuck = [item for item in shared if item not in later]
                if stuck:
                    misses.append({"bug": bug["id"], "sig": sig, "controls": stuck})
    return {
        "app": app,
        "reset_before_step": reset_at,
        "confirmed_count": len(confirmed),
        "unconfirmed": [bug["id"] for bug in manifest["bugs"] if bug["id"] not in confirmed],
        "measured_misses": misses,
    }


def main() -> int:
    apps = [measure_app(app) for app in APPS]
    outcome = "no_measured_miss" if all(not item["measured_misses"] for item in apps) else "measured_miss"
    print(outcome)
    for item in apps:
        print(item["app"], "reset", item["reset_before_step"], "misses", len(item["measured_misses"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
