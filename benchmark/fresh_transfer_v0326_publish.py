"""Publish the v0.3.26 fresh transfer. Does not change the candidate or targets."""
from __future__ import annotations

import json
import os
import shutil

from benchmark.algorithm_freeze import sha256_file, verify_freeze
from benchmark.fresh_composite_analysis import product_default_changed
from benchmark.fresh_transfer_v0326_analysis import derive_v0326_outcome
from benchmark.fresh_transfer_v0326_run import (
    CANDIDATE, CELLS, GUARD, HISTORICAL, INSPECTED, NEGATIVE, POSITIVE, _dir,
    _evidence, _stem,
)
from benchmark.horizon_handoff_analysis import GUARD_CONFIRMED
from benchmark.local_action_drain_analysis import lost_vs
from benchmark.residual_frontier_debt_publish import _confirmed, _history_guard, _int, _v0315_guard

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_ROOT = os.path.join("experiments", "runs", "v0326-fresh-transfer")
PUBLISHED = os.path.join("experiments", "published", "fresh-transfer-v0.3.26")
PROTOCOL = os.path.join("experiments", "validation", "v0.3.26", "protocol.json")
SUITE = os.path.join("experiments", "frozen", "v0.3.26-fresh-transfer-suite", "freeze.json")
CANDIDATE_FREEZE = os.path.join(
    "experiments", "frozen", "ghost-untried-sibling-v0.3.26", "freeze.json")
SOURCE = os.path.join("ghostqa", "exploration", "untried_sibling_guard.py")
SOURCE_SHA = "0a425a46df8884bc8260bf2c9fa1ac3c85da6a7931b7dec2899a94b9daac35dd"
PARENT = os.path.join("ghostqa", "exploration", "episode_drain_epoch_guard.py")
PARENT_SHA = "9403e81f34625ff225f4cca69bf65c992d937305cb3a516a8be12a7bc9e08d45"
INSPECTED_REF = os.path.join(
    "experiments", "published", "fresh-transfer-v0.3.25", "metrics", "mechanism.json")
FRESH_GUARD_APPS = ("buggy-lab", "buggy-directory", "buggy-forum", "buggy-billing")
NEEDLES = (
    "buggy-ward", "buggy-harbor", "buggy-gallery", "buggy-signal",
    "buggy-rack", "buggy-window", "buggy-clinic", "open_finding", "BUG-WD",
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


def _reached(row: dict) -> bool:
    return any(_int(row.get(key)) > 0 for key in (
        "horizon_handoff_started_events",
        "same_hub_local_action_events",
        "finding_return_entry_trigger_events",
        "residual_frontier_debt_relocations",
        "untried_sibling_before_return_selections",
    ))


def _evaluable(row: dict) -> bool:
    finished = _int(row.get("return_success")) > 0 or _int(row.get("sequences_completed")) > 0
    return _reached(row) and finished


def _historical_reference(app: str) -> list:
    evidence = _evidence(app)
    if app in FRESH_GUARD_APPS:
        return _confirmed(_v0315_guard(app))
    if evidence in GUARD_CONFIRMED:
        return list(GUARD_CONFIRMED[evidence])
    return _confirmed(_history_guard(evidence))


def _safety(cand: dict) -> tuple:
    episode_without = _int(cand.get("local_drain_episode_without_relocation_violations"))
    advances = _int(cand.get("local_drain_episode_advances"))
    relocations = _int(cand.get("residual_frontier_debt_relocations"))
    if advances > relocations:
        episode_without += advances - relocations
    return (
        episode_without,
        _int(cand.get("local_drain_cross_hub_invalidation_violations")),
        _int(cand.get("local_drain_restore_probe_violations")),
    )


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
        selections = _int(cand.get("untried_sibling_before_return_selections"))
        ok = _evaluable(cand)
        if ok:
            evaluable += 1
        if ok and not lost and selections > 0:
            structured += 1
        if lost:
            fresh_loss.append({"app": app, "bugs": lost})
        positives[app] = {
            "guard_confirmed": sorted(guard.get("confirmed_bugs") or []),
            "candidate_confirmed": sorted(cand.get("confirmed_bugs") or []),
            "lost_vs_guard": lost,
            "evaluable": ok,
            "sibling_selections": selections,
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
            "sibling_selections": _int(cand.get("untried_sibling_before_return_selections")),
            "finding_return": _int(cand.get("finding_return_entry_trigger_events")),
            "episode_advances": _int(cand.get("local_drain_episode_advances")),
        }
    historical = {}
    historical_loss = []
    episode_without = 0
    cross_hub = 0
    restore_probes = 0
    for app in list(POSITIVE) + list(NEGATIVE) + list(HISTORICAL) + list(INSPECTED):
        cand = _row(_runs(root, app), CANDIDATE, 120)
        extra, cross, restore = _safety(cand)
        episode_without += extra
        cross_hub += cross
        restore_probes += restore
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
            "sibling_selections": _int(cand.get("untried_sibling_before_return_selections")),
            "episode_advances": _int(cand.get("local_drain_episode_advances")),
        }
    inspected = {}
    prior = _load(INSPECTED_REF).get("positives") or {}
    for app in INSPECTED:
        cand = _row(_runs(root, app), CANDIDATE, 120)
        if not cand:
            missing.append(app)
        ref = (prior.get(app) or {}).get("guard_confirmed") or []
        lost = lost_vs(ref, cand.get("confirmed_bugs"))
        confirmed = set(cand.get("confirmed_bugs") or [])
        inspected[app] = {
            "guard_confirmed": list(ref),
            "candidate_confirmed": sorted(confirmed),
            "lost_vs_guard": lost,
            "score_bugs_confirmed": [bug for bug in ref if str(bug).endswith("12") and bug in confirmed],
            "sibling_selections": _int(cand.get("untried_sibling_before_return_selections")),
        }
    text = open(_abs(SOURCE), encoding="utf-8").read()
    needles = [needle for needle in NEEDLES if needle in text]
    facts = {
        "protocol_ok": os.path.isfile(_abs(PROTOCOL)) and not missing and len(CELLS) == 42,
        "suite_freeze_ok": not verify_freeze(_abs(SUITE)),
        "candidate_freeze_ok": not verify_freeze(_abs(CANDIDATE_FREEZE)),
        "candidate_edited": sha256_file(_abs(SOURCE)) != SOURCE_SHA or sha256_file(_abs(PARENT)) != PARENT_SHA,
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
        "inspected": inspected,
        "facts": facts,
        "derived": derive_v0326_outcome(**facts),
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
        f"# v0.3.26 result: Outcome {derived['outcome']}",
        "",
        derived["outcome_meaning"],
        "",
        "Fresh validation of the untried-sibling repair. The v0.3.24 candidate was not edited. The product default was not changed.",
        "",
    ]
    for app, item in report["positives"].items():
        lines.append(
            f"{app}: evaluable={item['evaluable']}, sibling={item['sibling_selections']}, "
            f"lost vs Guard={item['lost_vs_guard'] or 'none'}."
        )
    lines.append("")
    lines.append("The four v0.3.25 positives are inspected context. They do not change the outcome letter.")
    for app, item in report["inspected"].items():
        lines.append(
            f"{app}: sibling={item['sibling_selections']}, "
            f"score bugs confirmed={item['score_bugs_confirmed'] or 'none'}, "
            f"lost vs the published Guard={item['lost_vs_guard'] or 'none'}."
        )
    lines.append("")
    lines.append("v0.3.25 remains Outcome C. v0.3.24 remains Outcome A. This round does not promote the candidate.")
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
        "inspected": report["inspected"],
        "derived": report["derived"],
    })
    _write(os.path.join(metrics, "regression.json"), report["historical"])
    _write(os.path.join(metrics, "controls.json"), report["controls"])
    _write(os.path.join(metrics, "safety.json"), {
        "facts": report["facts"],
        "missing": report["missing"],
    })
    _write(os.path.join(metrics, "reproduction.json"), {
        "command": "python -m benchmark.fresh_transfer_v0326_reproduce --root experiments/published/fresh-transfer-v0.3.26 --verify",
        "clean_clone_verified": False,
        "verified_head": "",
        "cells": len(CELLS),
        "outcome": report["derived"]["outcome"],
        "product_default_changed": False,
        "preregistration_commit": "67989f5a3350d7461c77d10b2cca4f82fae8fe0d",
        "suite_freeze_commit": "613e5fa12154f148ebc1922ed53dff5c8733ad0d",
    })
    _write(os.path.join(published_abs, "config.json"), {
        "round": "v0.3.26",
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
