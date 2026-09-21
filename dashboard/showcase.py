"""Presentation-safe research payload for the dashboard.

Reads committed published artifacts only. Never invents numbers.
Does not import exploration runtime.
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLISHED = os.path.join(ROOT, "experiments", "published")
V039 = os.path.join(PUBLISHED, "return-cycle-guard-v0.3.9")
V038 = os.path.join(PUBLISHED, "application-shape-v0.3.8")


def _load(path, default=None):
    if not os.path.isfile(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def _short_hash(h: str, head: int = 8, tail: int = 4) -> str:
    if not h:
        return ""
    if len(h) <= head + tail + 1:
        return h
    return f"{h[:head]}…{h[-tail:]}"


def _v039(root: str | None = None) -> dict:
    base = root or V039
    metrics = _load(os.path.join(base, "metrics", "metrics.json"))
    repro = _load(os.path.join(base, "metrics", "reproduction.json"))
    config = _load(os.path.join(base, "config.json"))
    man = _load(os.path.join(base, "evidence-manifest.json"))
    if not metrics:
        return {"available": False}
    shop = (metrics.get("observed") or {}).get("shop") or {}
    base_s = shop.get("baseline") or {}
    cand = shop.get("candidate") or {}
    derived = metrics.get("derived") or {}
    interp = metrics.get("interpretation") or {}
    deep = (metrics.get("observed") or {}).get("deepbench") or []
    deep120 = next(
        (r for r in deep
         if r.get("policy") == "ghost-structural-return-guard" and r.get("budget") == 120),
        {},
    )
    deep_c1 = next(
        (r for r in deep
         if r.get("policy") == "ghost-structural-memory" and r.get("budget") == 120),
        {},
    )
    n_files = len((man or {}).get("files") or [])
    return {
        "available": True,
        "round": "v0.3.9",
        "title": "Return-Cycle Guard",
        "outcome": derived.get("outcome"),
        "outcome_meaning": interp.get("outcome_meaning"),
        "product_default_changed": bool(interp.get("product_default_changed")),
        "generalization_claim": bool(interp.get("generalization_claim")),
        "inspected_case": True,
        "baseline": {
            "states": base_s.get("states"),
            "urls": base_s.get("n_urls"),
            "return_attempts": base_s.get("return_attempt_events"),
            "successful_return": base_s.get("successful_return_to_parent_events"),
            "confirmed": base_s.get("confirmed_bugs") or [],
        },
        "candidate": {
            "states": cand.get("states"),
            "urls": cand.get("n_urls"),
            "return_attempts": cand.get("return_attempt_events"),
            "successful_return": cand.get("successful_return_to_parent_events"),
            "cycle_escapes": cand.get("return_cycle_escape_events"),
            "post_escape_new_states": cand.get("post_escape_new_state_count"),
            "post_escape_new_urls": cand.get("post_escape_new_urls") or [],
            "escape_step": cand.get("escape_step"),
            "confirmed": cand.get("confirmed_bugs") or [],
        },
        "deepbench120": {
            "c1_confirmed": deep_c1.get("confirmed_bugs") or [],
            "guard_confirmed": deep120.get("confirmed_bugs") or [],
            "lost_from_baseline": derived.get("lost_from_baseline_120") or [],
            "guard_escapes": deep120.get("return_cycle_escape_events"),
            "depth": deep120.get("max_workflow_depth"),
        },
        "reproduction": {
            "clean_clone_verified": bool((repro or {}).get("clean_clone_verified")),
            "match": bool((repro or {}).get("match")),
            "command": (repro or {}).get("command") or (config or {}).get("verify_command"),
            "metrics_sha256": (repro or {}).get("expected_metrics_sha256"),
            "metrics_sha256_short": _short_hash((repro or {}).get("expected_metrics_sha256") or ""),
            "evidence_files": n_files,
            "candidate_freeze_verified": bool((repro or {}).get("candidate_freeze_verified")),
            "historical_c1_freeze_verified": bool(
                (repro or {}).get("historical_c1_freeze_verified")),
            "evidence_manifest_verified": bool(
                (repro or {}).get("evidence_manifest_verified")),
        },
        "product_default": (config or {}).get("product_default"),
        "command": (config or {}).get("verify_command") or (
            (repro or {}).get("command")),
    }


def _v038(root: str | None = None) -> dict:
    base = root or V038
    collapse = _load(os.path.join(base, "metrics", "shop-collapse.json"))
    repro = _load(os.path.join(base, "metrics", "reproduction.json"))
    config = _load(os.path.join(base, "config.json"))
    man = _load(os.path.join(base, "evidence-manifest.json"))
    if not collapse:
        return {"available": False}
    obs = collapse.get("observed") or {}
    c1 = obs.get("ghost-structural-memory") or {}
    interp = collapse.get("interpretation") or {}
    n_files = len((man or {}).get("files") or [])
    cmd = (repro or {}).get("command") or (config or {}).get("verify_command")
    return {
        "available": True,
        "round": "v0.3.8",
        "title": "Application-shape analysis",
        "root_cause": interp.get("primary_failure_class"),
        "c1": {
            "states": c1.get("n_states") or c1.get("states"),
            "urls": c1.get("n_urls"),
            "return_attempts": c1.get("return_attempt_events"),
            "successful_return": c1.get("successful_return_to_parent_events"),
        },
        "reproduction": {
            "clean_clone_verified": bool((repro or {}).get("clean_clone_verified")),
            "match": bool((repro or {}).get("match")),
            "command": cmd,
            "analysis_sha256": (repro or {}).get("expected_analysis_sha256"),
            "analysis_sha256_short": _short_hash(
                (repro or {}).get("expected_analysis_sha256") or ""),
            "evidence_files": n_files,
            "evidence_manifest_verified": bool(
                (repro or {}).get("evidence_manifest_verified")),
        },
        "command": cmd,
    }


def build_showcase(*, v039_root: str | None = None, v038_root: str | None = None) -> dict:
    v039 = _v039(v039_root)
    v038 = _v038(v038_root)
    latest = {
        "round": "v0.3.9",
        "title": "Return-Cycle Guard",
        "available": bool(v039.get("available")),
        "outcome": v039.get("outcome") if v039.get("available") else None,
        "product_default_changed": (
            v039.get("product_default_changed") if v039.get("available") else None),
    }
    return {
        "project": {
            "name": "GhostQA",
            "product_preview": "v0.4 preview",
            "latest_research": "v0.3.9",
        },
        "latest": latest,
        "return_cycle": v039,
        "application_shape": v038,
        "timeline": [
            {"round": "v0.3.6", "title": "Structural Memory",
             "kind": "development benchmark"},
            {"round": "v0.3.7", "title": "Frozen Transfer Check",
             "kind": "one-shot generalization"},
            {"round": "v0.3.8", "title": "Root Cause",
             "kind": "application-shape analysis"},
            {"round": "v0.3.9", "title": "Return-Cycle Guard",
             "kind": "mechanism repair"},
        ],
    }
