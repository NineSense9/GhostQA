"""Episode / replay / latency measurement (v0.3.2).

These helpers do not change exploration policy. They only describe a finished
RunResult and ValidationResult in audit-friendly fields.
"""
from __future__ import annotations

from collections import Counter

from ..replay.validator import INVALID


def episode_stats(result) -> dict:
    """Reset / episode counters derived from Step.episode_id and reset_events."""
    lengths = Counter(s.episode_id for s in result.steps)
    ids = set(lengths)
    ids.update(e.get("episode_id") for e in result.reset_events
               if e.get("episode_id") is not None)
    lens = list(lengths.values())
    reloc = sum(1 for e in result.reset_events if e.get("reason") == "relocate")
    crash = sum(1 for e in result.reset_events
                if e.get("reason") == "crash_recovery")
    return {
        "episode_count": len(ids),
        "reset_count": len(result.reset_events),
        "relocate_episode_count": reloc,
        "crash_recovery_episode_count": crash,
        "max_episode_length": max(lens) if lens else 0,
        "mean_episode_length": round(sum(lens) / len(lens), 3) if lens else 0.0,
    }


def classify_validation(vr) -> str:
    """Map ValidationResult to replay_pass / replay_fail / replay_invalid."""
    if vr.confirmed:
        return "pass"
    if getattr(vr, "status", "") == INVALID:
        return "invalid"
    return "fail"


def latency_metrics(result, confirmed_step_by_bug: dict,
                    deep_ids: set = None) -> dict:
    """TTF / TTCB / TTDCB. Old time_to_first_bug is a deprecated TTF alias."""
    ttf = next((s.index for s in result.steps if s.findings), None)
    ttcb = min(confirmed_step_by_bug.values()) if confirmed_step_by_bug else None
    deep_ids = deep_ids or set()
    deep_steps = [confirmed_step_by_bug[i] for i in deep_ids
                  if i in confirmed_step_by_bug]
    ttdcb = min(deep_steps) if deep_steps else None
    return {
        "time_to_first_finding": ttf,
        "time_to_first_confirmed_bug": ttcb,
        "time_to_first_deep_confirmed_bug": ttdcb,
        "ttf": ttf,
        "ttcb": ttcb,
        "ttdcb": ttdcb,
        "time_to_first_bug": ttf,       # deprecated alias of TTF
        "time_to_first_deep_bug": ttdcb,
    }


def finding_artifact(result, finding) -> dict:
    """Finding dict plus derived episode_id. Finding dataclass is unchanged."""
    d = finding.to_dict()
    step = result.step_for_finding(finding)
    d["episode_id"] = step.episode_id if step is not None else None
    return d
