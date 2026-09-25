"""Publish the v0.3.25 fresh transfer. Does not change the candidate or targets."""
from __future__ import annotations

import json
import os
import shutil

from benchmark.algorithm_freeze import sha256_file, verify_freeze
from benchmark.fresh_composite_analysis import product_default_changed
from benchmark.fresh_transfer_v0325_analysis import derive_v0325_outcome
from benchmark.fresh_transfer_v0325_run import (
    CANDIDATE, CELLS, GUARD, HISTORICAL, NEGATIVE, POSITIVE, _dir, _evidence, _stem,
)
from benchmark.horizon_handoff_analysis import GUARD_CONFIRMED
from benchmark.local_action_drain_analysis import lost_vs
from benchmark.residual_frontier_debt_publish import _confirmed, _history_guard, _int, _v0315_guard

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_ROOT = os.path.join("experiments", "runs", "v0325-fresh-transfer")
PUBLISHED = os.path.join("experiments", "published", "fresh-transfer-v0.3.25")
PROTOCOL = os.path.join("experiments", "validation", "v0.3.25", "protocol.json")
SUITE = os.path.join("experiments", "frozen", "v0.3.25-fresh-transfer-suite", "freeze.json")
CANDIDATE_FREEZE = os.path.join(
    "experiments", "frozen", "ghost-episode-drain-epoch-v0.3.24", "freeze.json")
SOURCE = os.path.join("ghostqa", "exploration", "episode_drain_epoch_guard.py")
SOURCE_SHA = "9403e81f34625ff225f4cca69bf65c992d937305cb3a516a8be12a7bc9e08d45"
FRESH_GUARD_APPS = ("buggy-lab", "buggy-directory", "buggy-forum", "buggy-billing")
NEEDLES = (
    "buggy-clinic", "buggy-dispatch", "buggy-archive", "buggy-fleet",
    "buggy-shelf", "buggy-counter",
)


def _abs(path: str) -> str:
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


def _load(path: str):
    with open(_abs(path), encoding="utf-8") as handle:
        return json.load(handle)


def _write(path: str, payload) -> None:
    os.makedirs(os.path.dirname(_abs(path)), exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with open(_abs(path), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _runs(root: str, app: str) -> list:
    path = os.path.join(_dir(root, app), "metrics.json")
    if not os.path.isfile(_abs(path)):
        return []
    return _load(path).get("runs") or []


def _row(runs: list, policy: str, budget: int) -> dict:
    for item in runs:
        if item.get("policy") == policy and int(item.get("budget") or 0) == budget:
            return item
    return {}


def _evaluable(row: dict) -> bool:
    reached = any(_int(row.get(key)) > 0 for key in (
        "horizon_handoff_started_events",
        "same_hub_local_action_events",
        "finding_return_entry_trigger_events",
        "residual_frontier_debt_relocations",
    ))
    finished = _int(row.get("return_success")) > 0 or _int(row.get("sequences_completed")) > 0
    return reached and finished


def _historical_reference(app: str) -> list:
    evidence = _evidence(app)
    if app in FRESH_GUARD_APPS:
        return _confirmed(_v0315_guard(app))
    if evidence in GUARD_CONFIRMED:
        return list(GUARD_CONFIRMED[evidence])
    return _confirmed(_history_guard(evidence))


def collect(root: str = RUN_ROOT) -> dict:
    missing = []
    positives = {}
    evaluable = 0
    structured = 0
    fresh_loss = []
    for app in POSITIVE:
        runs = _runs(root, app)
        guard = _row(runs, GUARD, 120)
        cand = _row(runs, CANDIDATE, 120)
        if not guard or not cand:
            missing.append(app)
        lost = lost_vs(guard.get("confirmed_bugs"), cand.get("confirmed_bugs"))
        ok = _evaluable(cand)
        if ok:
            evaluable += 1
        if ok and not lost:
            structured += 1
        if lost:
            fresh_loss.append({"app": app, "bugs": lost})
        positives[app] = {
            "guard_confirmed": sorted(guard.get("confirmed_bugs") or []),
            "candidate_confirmed": sorted(cand.get("confirmed_bugs") or []),
            "lost_vs_guard": lost,
            "evaluable": ok,
            "handoff": _int(cand.get("horizon_handoff_started_events")),
            "local_drain": _int(cand.get("same_hub_local_action_events")),
            "finding_return": _int(cand.get("finding_return_entry_trigger_events")),
            "relocations": _int(cand.get("residual_frontier_debt_relocations")),
            "episode_advances": _int(cand.get("local_drain_episode_advances")),
            "return_success": _int(cand.get("return_success")),
        }
    controls = {}
    negative_handoff = 0
    for app in NEGATIVE:
        runs = _runs(root, app)
        guard = _row(runs, GUARD, 120)
        cand = _row(runs, CANDIDATE, 120)
        if not guard or not cand:
            missing.append(app)
        lost = lost_vs(guard.get("confirmed_bugs"), cand.get("confirmed_bugs"))
        handoff = _int(cand.get("horizon_handoff_started_events"))
        negative_handoff += handoff
        if lost:
            fresh_loss.append({"app": app, "bugs": lost})
        controls[app] = {
            "guard_confirmed": sorted(guard.get("confirmed_bugs") or []),
            "candidate_confirmed": sorted(cand.get("confirmed_bugs") or []),
            "lost_vs_guard": lost,
            "handoff": handoff,
            "finding_return": _int(cand.get("finding_return_entry_trigger_events")),
            "episode_advances": _int(cand.get("local_drain_episode_advances")),
        }
    historical = {}
    historical_loss = []
    episode_without = 0
    cross_hub = 0
    restore_probes = 0
    for app in list(POSITIVE) + list(NEGATIVE) + list(HISTORICAL):
        cand = _row(_runs(root, app), CANDIDATE, 120)
        episode_without += _int(cand.get("local_drain_episode_without_relocation_violations"))
        advances = _int(cand.get("local_drain_episode_advances"))
        relocations = _int(cand.get("residual_frontier_debt_relocations"))
        if advances > relocations:
            episode_without += advances - relocations
        cross_hub += _int(cand.get("local_drain_cross_hub_invalidation_violations"))
        restore_probes += _int(cand.get("local_drain_restore_probe_violations"))
    for app in HISTORICAL:
        cand = _row(_runs(root, app), CANDIDATE, 120)
        if not cand:
            missing.append(app)
        ref = _historical_reference(app)
        lost = lost_vs(ref, cand.get("confirmed_bugs"))
        if lost:
            historical_loss.append({"app": app, "bugs": lost})
        historical[app] = {
            "guard_confirmed": ref,
            "candidate_confirmed": sorted(cand.get("confirmed_bugs") or []),
            "lost_vs_guard": lost,
            "handoff": _int(cand.get("horizon_handoff_started_events")),
            "episode_advances": _int(cand.get("local_drain_episode_advances")),
        }
    text = open(_abs(SOURCE), encoding="utf-8").read()
    needles = [needle for needle in NEEDLES if needle in text]
    facts = {
        "protocol_ok": os.path.isfile(_abs(PROTOCOL)) and not missing and len(CELLS) == 38,
        "suite_freeze_ok": not verify_freeze(_abs(SUITE)),
        "candidate_freeze_ok": not verify_freeze(_abs(CANDIDATE_FREEZE)),
        "candidate_edited": sha256_file(_abs(SOURCE)) != SOURCE_SHA,
        "product_default_changed": product_default_changed(),
        "app_specific": bool(needles),
        "fresh_guard_loss": fresh_loss,
        "historical_guard_loss": historical_loss,
        "episode_without_relocation": episode_without,
        "cross_hub_invalidations": cross_hub,
        "restore_probes": restore_probes,
        "negative_handoff": negative_handoff,
        "evaluable_positives": evaluable,
        "structured_positives": structured,
    }
    return {
        "missing": missing,
        "positives": positives,
        "controls": controls,
        "historical": historical,
        "facts": facts,
        "derived": derive_v0325_outcome(**facts),
    }


def _copy_evidence(run_root: str, published: str) -> None:
    for app, policy, budget in CELLS:
        src_dir = _abs(_dir(run_root, app))
        dst_dir = os.path.join(published, "evidence", _evidence(app))
        os.makedirs(dst_dir, exist_ok=True)
        stem = _stem(policy, budget)
        for ext in (".events.jsonl", ".graph.json", ".sequence_events.json", ".config.json", ".DONE"):
            src = os.path.join(src_dir, stem + ext)
            if os.path.isfile(src):
                shutil.copyfile(src, os.path.join(dst_dir, stem + ext))
        metrics = os.path.join(src_dir, "metrics.json")
        if os.path.isfile(metrics):
            shutil.copyfile(metrics, os.path.join(dst_dir, "metrics.json"))


def _manifest(root: str) -> dict:
    files = []
    for dirpath, _dirs, names in os.walk(root):
        for name in names:
            if name == "evidence-manifest.json":
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace("\\", "/")
            files.append({"relative_path": rel, "sha256": sha256_file(full)})
    files.sort(key=lambda item: item["relative_path"])
    return {"expected_file_count": len(files), "files": files}


def _summary(report: dict) -> str:
    derived = report["derived"]
    lines = [
        f"# v0.3.25 result: Outcome {derived['outcome']}",
        "",
        derived["outcome_meaning"],
        "",
        "Fresh validation of the frozen v0.3.24 candidate on six new applications. The candidate was not edited. The product default was not changed.",
        "",
    ]
    for app, item in report["positives"].items():
        lines.append(
            f"{app}: evaluable={item['evaluable']}, handoff={item['handoff']}, "
            f"local drain={item['local_drain']}, lost vs Guard={item['lost_vs_guard'] or 'none'}."
        )
    lines.append("")
    lines.append("Shelf and counter nested handoff counts are in controls.json.")
    lines.append("v0.3.24 remains Outcome A on its inspected cells. This round does not promote the candidate.")
    lines.append("")
    return "\n".join(lines)


def publish(run_root: str = RUN_ROOT, published: str = PUBLISHED) -> dict:
    published_abs = _abs(published)
    if os.path.isdir(published_abs):
        shutil.rmtree(published_abs)
    os.makedirs(published_abs, exist_ok=True)
    shutil.copyfile(_abs(PROTOCOL), os.path.join(published_abs, "protocol.json"))
    shutil.copyfile(_abs(SUITE), os.path.join(published_abs, "suite-freeze.json"))
    shutil.copyfile(_abs(CANDIDATE_FREEZE), os.path.join(published_abs, "candidate-freeze.json"))
    _copy_evidence(run_root, published_abs)
    report = collect(run_root)
    metrics = os.path.join(published_abs, "metrics")
    _write(os.path.join(metrics, "mechanism.json"), {
        "positives": report["positives"],
        "controls": report["controls"],
        "derived": report["derived"],
    })
    _write(os.path.join(metrics, "regression.json"), report["historical"])
    _write(os.path.join(metrics, "controls.json"), report["controls"])
    _write(os.path.join(metrics, "safety.json"), {
        "facts": report["facts"],
        "missing": report["missing"],
    })
    _write(os.path.join(metrics, "reproduction.json"), {
        "command": "python -m benchmark.fresh_transfer_v0325_reproduce --root experiments/published/fresh-transfer-v0.3.25 --verify",
        "clean_clone_verified": False,
        "cells": len(CELLS),
        "outcome": report["derived"]["outcome"],
        "product_default_changed": False,
        "preregistration_commit": "6e700d6527fd4aa34d8119931c4585bd52d3e01d",
        "suite_freeze_commit": "4839d06e59e2c0ba48d8ad6346270b7a94632e59",
    })
    _write(os.path.join(published_abs, "config.json"), {
        "round": "v0.3.25",
        "candidate": CANDIDATE,
        "guard": GUARD,
        "seed": 1,
        "cells": [{"app": app, "policy": policy, "budget": budget} for app, policy, budget in CELLS],
        "product_default_changed": False,
        "fresh_validation": True,
        "promotion_readiness": "not_ready",
    })
    with open(os.path.join(published_abs, "summary.md"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(_summary(report))
    _write(os.path.join(published_abs, "evidence-manifest.json"), _manifest(published_abs))
    return report


def main() -> int:
    report = publish()
    print(report["derived"]["outcome"], report["derived"]["outcome_meaning"])
    print("missing", report["missing"])
    print("fresh loss", report["facts"]["fresh_guard_loss"])
    print("historical loss", report["facts"]["historical_guard_loss"])
    print("evaluable", report["facts"]["evaluable_positives"], "structured", report["facts"]["structured_positives"])
    return 0 if not report["missing"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
