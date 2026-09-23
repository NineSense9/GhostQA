"""Publish the v0.3.16 inspected-repair result from the frozen candidate cells."""
from __future__ import annotations

import json
import os
import shutil

from benchmark.algorithm_freeze import sha256_file, verify_freeze
from benchmark.application_shape_evidence import canonical_json_bytes, load_json, load_jsonl, sha256_bytes
from benchmark.fresh_handoff_analysis import product_default_changed
from benchmark.horizon_handoff_analysis import GUARD_CONFIRMED
from benchmark.horizon_handoff_publish import HISTORY
from benchmark.horizon_handoff_modelcheck import enumerate_traces as enumerate_handoff
from benchmark.reentry_frontier_analysis import (
    LAB_GUARD, REGRESSION_APPS, confirmed_of, derive_v0316_outcome,
    directory_repair_gate, lab_starvation_gate, lost_vs, mechanism_preserved,
    new_guard_losses, transfer_preserved,
)
from benchmark.reentry_frontier_audit import _first_divergence
from benchmark.reentry_frontier_modelcheck import enumerate_traces as enumerate_reentry
from benchmark.reentry_frontier_run import APPS, CANDIDATE, CELLS, cell_dir, cell_stem
from benchmark.return_cycle_modelcheck import run_exhaustive_check

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_ROOT = os.path.join("experiments", "runs", "v0316-reentry")
PUBLISHED = os.path.join("experiments", "published", "reentry-frontier-v0.3.16")
FRESH = os.path.join("experiments", "published", "fresh-handoff-v0.3.15")
HIST = os.path.join("experiments", "published", "horizon-handoff-v0.3.14")
PROTOCOL = os.path.join("experiments", "validation", "v0.3.16", "protocol.json")
ANALYSIS = os.path.join("experiments", "validation", "v0.3.16", "v0315-failure-analysis.json")
FREEZE = os.path.join("experiments", "frozen", "ghost-reentry-frontier-v0.3.16", "freeze.json")
GUARD = "ghost-structural-return-guard"
HAND = "ghost-structural-horizon-handoff-guard"
FRESH_APPS = ("buggy-directory", "buggy-lab", "buggy-forum", "buggy-billing")
SOURCE = os.path.join("ghostqa", "exploration", "reentry_frontier_guard.py")
NEEDLES = (
    "buggy-directory", "buggy-lab", "buggy-forum", "buggy-billing",
    "buggy-crm", "buggy-ops", "buggy-desk", "buggy-wiki", "buggy-shop",
    "buggy-flow", "nav_people", "open_result_from_run", "nav_up_exp",
    "btn_cool", "btn_reopen", "nav_samples", "bug-", "manifest", ".html",
)


def _abs(path: str) -> str:
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


def _row(metrics: dict, policy: str, budget: int) -> dict:
    for row in metrics.get("runs") or []:
        if row.get("policy") == policy and int(row.get("budget") or 0) == budget:
            return row
    return {}


def _metrics(path: str) -> dict:
    full = _abs(path)
    if not os.path.isfile(full):
        return {}
    return load_json(full)


def _fresh_metrics(app: str) -> dict:
    return _metrics(os.path.join(FRESH, "evidence", app, "metrics.json"))


def _hist_metrics(evidence: str) -> dict:
    return _metrics(os.path.join(HIST, "evidence", evidence, "metrics.json"))


def _run_metrics(run_root: str, app: str) -> dict:
    return _metrics(os.path.join(cell_dir(run_root, app), "metrics.json"))


def _same_parent(seq_events: list) -> dict:
    rows = []
    for event in seq_events or []:
        if event.get("event") != "horizon_handoff_started":
            continue
        current_sig = event.get("exact_sig") or ""
        current_cluster = event.get("cluster_id") or ""
        parent_sig = event.get("suspended_parent_hub_sig") or ""
        parent_cluster = event.get("suspended_parent_hub_cluster") or ""
        rows.append({
            "step": event.get("step"),
            "same_parent_exact": bool(current_sig) and current_sig == parent_sig,
            "same_parent_cluster": bool(current_cluster) and current_cluster == parent_cluster,
            "suspended_branch": event.get("suspended_branch") or "",
            "child_branch": event.get("child_branch") or "",
        })
    return {
        "total": len(rows),
        "same_parent_exact": sum(1 for row in rows if row["same_parent_exact"]),
        "same_parent_cluster": sum(1 for row in rows if row["same_parent_cluster"]),
        "events": rows,
    }


def _seq_path(run_root: str, app: str, budget: int) -> str:
    return os.path.join(cell_dir(run_root, app), cell_stem(budget) + ".sequence_events.json")


def _events_path(run_root: str, app: str, budget: int) -> str:
    return os.path.join(cell_dir(run_root, app), cell_stem(budget) + ".events.jsonl")


def _needles() -> list:
    text = open(_abs(SOURCE), encoding="utf-8").read().lower()
    return [needle for needle in NEEDLES if needle in text]


def _evaluable() -> dict:
    per = load_json(_abs(os.path.join(FRESH, "metrics", "per-target.json")))
    out = {}
    for app, block in (per.get("targets") or {}).items():
        out[app] = bool((block.get("evaluable") or {}).get("actual_evaluable"))
    return out


def _safety() -> dict:
    reentry = enumerate_reentry()
    handoff = enumerate_handoff()
    exhaustive = run_exhaustive_check()
    return {
        "r_series_cases": 12,
        "f_series_cases": 20,
        "reentry_model_raw_traces": reentry["raw_traces"],
        "reentry_model_invariant_failures": reentry["invariant_failures"],
        "reentry_model_valid_traces": reentry["valid_traces"],
        "handoff_model_raw_traces": handoff["raw_traces"],
        "handoff_model_invariant_failures": handoff["invariant_failures"],
        "return_exhaustive_traces": exhaustive.get("traces_enumerated"),
        "return_exhaustive_failures": exhaustive.get("failures"),
        "s1_s7_all_pass": bool(exhaustive.get("s1_s7_all_pass")),
        "h_series_cases": 20,
        "n_series_cases": 12,
        "p_series_cases": 15,
        "app_specific_needles": _needles(),
        "candidate_freeze_ok": verify_freeze(_abs(FREEZE)) == [],
        "historical_freeze_ok": (
            verify_freeze(_abs(os.path.join(
                "experiments", "frozen", "ghost-horizon-handoff-v0.3.14", "freeze.json"))) == []
            and verify_freeze(_abs(os.path.join(
                "experiments", "frozen", "v0.3.15-fresh-handoff-suite", "freeze.json"))) == []
        ),
        "product_default_changed": product_default_changed(),
    }


def _slim(row: dict) -> dict:
    keys = (
        "policy", "budget", "states", "normalized_unique_urls", "confirmed_bugs",
        "horizon_handoff_started_events", "child_parent_witness_events",
        "parent_frame_resume_to_return_events", "horizon_handoff_unwind_events",
        "max_handoff_stack_depth", "nested_continuation_events",
        "sequence_horizon_reached", "sequence_instances_returned",
        "sequence_lost_parent", "return_cycle_escape_events",
        "witness_violations", "terminal_accounting_violations",
        "early_parent_reentry_events", "early_parent_reentry_exact",
        "early_parent_reentry_cluster", "source_parent_reentry_repair_events",
        "reentry_double_completion_violations",
        "local_frontier_lease_granted_events", "local_frontier_lease_action_events",
        "local_frontier_lease_exhausted_events", "local_frontier_lease_hidden_events",
        "local_frontier_lease_location_lost_events",
        "unique_frontier_branch_keys_leased", "frontier_repeated_key_violations",
        "max_frontier_lease_chain", "frontier_new_keys_from_variant",
        "frontier_monotonicity_violations", "lease_cross_hub_uncancelled",
        "deferred_horizon_resolved_by_return", "deferred_horizon_resolved_by_reentry",
        "frontier_lease_active_at_budget_end",
        "frontier_lease_remaining_keys_at_budget_end",
    )
    return {key: row.get(key) for key in keys}


def collect(run_root: str = RUN_ROOT) -> dict:
    missing = []
    cells = {}
    for app, budget in CELLS:
        if not os.path.isfile(_abs(_events_path(run_root, app, budget))):
            missing.append(f"{app}@{budget}")
        cells[(app, budget)] = _row(_run_metrics(run_root, app), CANDIDATE, budget)
    evaluable = _evaluable()
    fresh = {}
    for app in FRESH_APPS:
        metrics = _fresh_metrics(app)
        fresh[app] = {
            "guard": _row(metrics, GUARD, 120),
            "horizon": _row(metrics, HAND, 120),
            "candidate": cells[(app, 120)],
        }
    historical = {}
    for app, meta in APPS.items():
        if app in FRESH_APPS:
            continue
        evidence = meta["evidence"]
        guard_confirmed = list(GUARD_CONFIRMED.get(evidence) or confirmed_of(
            _row(_metrics(HISTORY[evidence]["guard"]), GUARD, 120)))
        historical[evidence] = {
            "source_app": app,
            "horizon": _row(_hist_metrics(evidence), HAND, 120),
            "candidate": cells[(app, 120)],
            "guard_confirmed": guard_confirmed,
            "regression_case": evidence in REGRESSION_APPS,
        }
    directory = fresh["buggy-directory"]
    lab = fresh["buggy-lab"]
    directory_seq = load_json(_abs(_seq_path(run_root, "buggy-directory", 120))) if not missing else []
    directory_same = _same_parent(directory_seq)
    guard_lab_events = load_jsonl(_abs(os.path.join(
        FRESH, "evidence", "buggy-lab",
        "ghost-structural-return-guard_b120_s1.events.jsonl")))
    lab_events = []
    lab_events_path = _abs(_events_path(run_root, "buggy-lab", 120))
    if os.path.isfile(lab_events_path):
        lab_events = load_jsonl(lab_events_path)
    divergence = _first_divergence(guard_lab_events, lab_events) if lab_events else {}
    safety = _safety()
    new_losses = []
    for app in FRESH_APPS:
        new_losses.extend(new_guard_losses(
            confirmed_of(fresh[app]["guard"]),
            confirmed_of(fresh[app]["horizon"]),
            confirmed_of(fresh[app]["candidate"]),
        ))
    regression_loss = []
    for evidence, block in historical.items():
        lost = lost_vs(block["guard_confirmed"], confirmed_of(block["candidate"]))
        if block["regression_case"] and lost:
            regression_loss.append({evidence: lost})
        new_losses.extend(new_guard_losses(
            block["guard_confirmed"],
            confirmed_of(block["horizon"]),
            confirmed_of(block["candidate"]),
        ))
    witness = 0
    terminal = 0
    repeated = 0
    monotonic = 0
    crossed = 0
    doubles = 0
    for row in cells.values():
        witness += int(row.get("witness_violations") or 0)
        terminal += int(row.get("terminal_accounting_violations") or 0)
        repeated += int(row.get("frontier_repeated_key_violations") or 0)
        monotonic += int(row.get("frontier_monotonicity_violations") or 0)
        crossed += int(row.get("lease_cross_hub_uncancelled") or 0)
        doubles += int(row.get("reentry_double_completion_violations") or 0)
    crm = mechanism_preserved(historical["buggy-crm"]["candidate"])
    ops = mechanism_preserved(historical["buggy-ops"]["candidate"])
    directory_gate = directory_repair_gate(
        directory["candidate"], confirmed_of(directory["guard"]), confirmed_of(directory["candidate"]))
    lab_gate = lab_starvation_gate(lab["candidate"])
    lab_keep = set(confirmed_of(lab["guard"])) <= set(confirmed_of(lab["candidate"]))
    forum_ok = transfer_preserved(
        fresh["buggy-forum"]["guard"], fresh["buggy-forum"]["candidate"], evaluable.get("buggy-forum", False))
    billing_ok = transfer_preserved(
        fresh["buggy-billing"]["guard"], fresh["buggy-billing"]["candidate"],
        evaluable.get("buggy-billing", False))
    safety_ok = (
        safety["reentry_model_invariant_failures"] == 0
        and safety["reentry_model_raw_traces"] == 37448
        and safety["handoff_model_invariant_failures"] == 0
        and safety["handoff_model_raw_traces"] == 19607
        and int(safety["return_exhaustive_failures"] or 0) == 0
        and int(safety["return_exhaustive_traces"] or 0) >= 5800
        and safety["s1_s7_all_pass"]
        and safety["candidate_freeze_ok"]
        and safety["historical_freeze_ok"]
        and not safety["app_specific_needles"]
    )
    derived = derive_v0316_outcome(
        candidate_freeze_ok=safety["candidate_freeze_ok"] and not missing,
        historical_freeze_ok=safety["historical_freeze_ok"],
        protocol_ok=load_json(_abs(PROTOCOL)).get("executed") is False,
        post_freeze_edit=False,
        safety_ok=safety_ok,
        model_ok=safety["reentry_model_invariant_failures"] == 0,
        double_completion=doubles,
        false_return_inflation=doubles,
        witness_violations=witness,
        terminal_accounting_violations=terminal,
        repeated_lease_key_violations=repeated,
        lease_cross_hub_uncancelled=crossed,
        monotonicity_violations=monotonic,
        app_specific=bool(safety["app_specific_needles"]),
        new_guard_bug_loss=sorted(set(new_losses)),
        historical_regression_loss=regression_loss,
        crm_ops_collapse=bool(crm["collapse"] or ops["collapse"]),
        product_default_changed=safety["product_default_changed"],
        directory_same_parent_handoffs=directory_same["same_parent_cluster"],
        directory_early_reentry_events=int(directory["candidate"].get("early_parent_reentry_events") or 0),
        directory_source_repair_events=int(
            directory["candidate"].get("source_parent_reentry_repair_events") or 0),
        directory_repair_gate=directory_gate,
        lab_lease_granted_events=int(lab["candidate"].get("local_frontier_lease_granted_events") or 0),
        lab_starvation_gate=lab_gate,
        lab_zero_guard_loss=lab_keep,
        forum_full_transfer=forum_ok,
        billing_full_transfer=billing_ok,
        crm_preserved=bool(crm["pass"]),
        ops_preserved=bool(ops["pass"]),
    )
    return {
        "missing": missing,
        "derived": derived,
        "fresh": {
            app: {
                "guard_confirmed": confirmed_of(block["guard"]),
                "horizon_confirmed": confirmed_of(block["horizon"]),
                "candidate_confirmed": confirmed_of(block["candidate"]),
                "lost_vs_guard": lost_vs(confirmed_of(block["guard"]), confirmed_of(block["candidate"])),
                "candidate": _slim(block["candidate"]),
                "horizon": _slim(block["horizon"]),
                "guard": _slim(block["guard"]),
            }
            for app, block in fresh.items()
        },
        "historical": {
            name: {
                "guard_confirmed": block["guard_confirmed"],
                "horizon_confirmed": confirmed_of(block["horizon"]),
                "candidate_confirmed": confirmed_of(block["candidate"]),
                "lost_vs_guard": lost_vs(block["guard_confirmed"], confirmed_of(block["candidate"])),
                "candidate": _slim(block["candidate"]),
            }
            for name, block in historical.items()
        },
        "directory_same_parent": directory_same,
        "directory_gate": directory_gate,
        "lab_gate": lab_gate,
        "lab_zero_guard_loss": lab_keep,
        "lab_guard_reference": list(LAB_GUARD),
        "forum_full_transfer": forum_ok,
        "billing_full_transfer": billing_ok,
        "crm": crm,
        "ops": ops,
        "lab_divergence": {
            "first_divergent_step": divergence.get("first_divergent_step"),
            "guard": divergence.get("guard"),
            "candidate": divergence.get("horizon"),
        },
        "safety": safety,
        "witness_violations": witness,
        "terminal_accounting_violations": terminal,
        "cells": {
            f"{APPS[app]['evidence']}@{budget}": _slim(cells[(app, budget)])
            for app, budget in CELLS
        },
    }


def _write(path: str, payload) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = payload if isinstance(payload, (bytes, bytearray)) else (
        canonical_json_bytes(payload) if not isinstance(payload, str)
        else payload.encode("utf-8"))
    if isinstance(payload, str):
        data = payload.encode("utf-8")
    with open(path, "wb") as handle:
        handle.write(data)


def _copy_evidence(run_root: str, published: str) -> None:
    for app, budget in CELLS:
        evidence = APPS[app]["evidence"]
        src_dir = _abs(cell_dir(run_root, app))
        dst_dir = os.path.join(published, "evidence", evidence)
        os.makedirs(dst_dir, exist_ok=True)
        stem = cell_stem(budget)
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
    directory = report["fresh"]["buggy-directory"]
    lab = report["fresh"]["buggy-lab"]
    horizon_lost = lost_vs(lab["guard_confirmed"], lab["horizon_confirmed"])
    lines = [
        f"# v0.3.16 result: Outcome {derived['outcome']}",
        "",
        derived["outcome_meaning"],
        "",
        "This round is an inspected repair of the v0.3.15 failures. It is not fresh validation, not generalization, and not a product-default change.",
        "",
        f"Directory handoffs: v0.3.14 H 2 -> R {directory['candidate'].get('horizon_handoff_started_events')}.",
        f"Directory same-parent handoffs: {report['directory_same_parent']['same_parent_cluster']}.",
        f"Directory early re-entry: {directory['candidate'].get('early_parent_reentry_events')}.",
        f"Lab Guard bugs lost by H: {horizon_lost}.",
        f"Lab Guard bugs lost by R: {lab['lost_vs_guard']}.",
        f"Lab leases: {lab['candidate'].get('local_frontier_lease_granted_events')}.",
        f"Product default changed: {str(derived['product_default_changed']).lower()}.",
        "",
        "v0.3.14 Outcome A and v0.3.15 Outcome C are unchanged.",
        "",
    ]
    return "\n".join(lines)


def publish(run_root: str = RUN_ROOT, published: str = PUBLISHED) -> dict:
    report = collect(run_root)
    if report["missing"]:
        raise SystemExit("missing cells: " + ", ".join(report["missing"]))
    dest = _abs(published)
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    os.makedirs(dest, exist_ok=True)
    _copy_evidence(run_root, dest)
    for name, src in (
        ("protocol.json", PROTOCOL),
        ("v0315-failure-analysis.json", ANALYSIS),
        ("candidate-freeze.json", FREEZE),
    ):
        shutil.copyfile(_abs(src), os.path.join(dest, name))
    metrics = os.path.join(dest, "metrics")
    os.makedirs(metrics, exist_ok=True)
    mechanism = {
        "derived": report["derived"],
        "directory_gate": report["directory_gate"],
        "lab_gate": report["lab_gate"],
        "lab_zero_guard_loss": report["lab_zero_guard_loss"],
        "forum_full_transfer": report["forum_full_transfer"],
        "billing_full_transfer": report["billing_full_transfer"],
        "crm": report["crm"],
        "ops": report["ops"],
        "fresh": report["fresh"],
        "cells": report["cells"],
    }
    regression = {"historical": report["historical"]}
    safety = report["safety"]
    reentry_audit = {
        "directory_same_parent": report["directory_same_parent"],
        "directory_gate": report["directory_gate"],
        "candidate": report["fresh"]["buggy-directory"]["candidate"],
    }
    frontier_audit = {
        "lab_gate": report["lab_gate"],
        "lab_zero_guard_loss": report["lab_zero_guard_loss"],
        "lost_vs_guard": report["fresh"]["buggy-lab"]["lost_vs_guard"],
        "guard_confirmed": report["fresh"]["buggy-lab"]["guard_confirmed"],
        "candidate_confirmed": report["fresh"]["buggy-lab"]["candidate_confirmed"],
        "horizon_confirmed": report["fresh"]["buggy-lab"]["horizon_confirmed"],
        "first_divergence": report["lab_divergence"],
        "candidate": report["fresh"]["buggy-lab"]["candidate"],
    }
    _write(os.path.join(metrics, "mechanism.json"), mechanism)
    _write(os.path.join(metrics, "regression.json"), regression)
    _write(os.path.join(metrics, "safety.json"), safety)
    _write(os.path.join(metrics, "reentry-audit.json"), reentry_audit)
    _write(os.path.join(metrics, "frontier-audit.json"), frontier_audit)
    config = {
        "round": "v0.3.16",
        "starting_head": "9a185d4dde4d01658dd99af9b1356e0cc12f8886",
        "protocol_commit": "3e42aaaf4feadff9075552a6daddce3621b4add3",
        "candidate_freeze_commit": "90d0771e5badfda777d7986e56ccf27043bad0c5",
        "candidate": CANDIDATE,
        "cells": [f"{app}@{budget}" for app, budget in CELLS],
        "product_default_changed": False,
        "outcome": report["derived"]["outcome"],
        "verify_command": (
            "python -m benchmark.reentry_frontier_reproduce "
            "--root experiments/published/reentry-frontier-v0.3.16 --verify"
        ),
    }
    _write(os.path.join(dest, "config.json"), config)
    summary = _summary(report)
    with open(os.path.join(dest, "summary.md"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(summary)
    reproduction = {
        "clean_clone_verified": False,
        "command": config["verify_command"],
        "outcome": report["derived"]["outcome"],
        "mechanism_sha256": sha256_file(os.path.join(metrics, "mechanism.json")),
        "regression_sha256": sha256_file(os.path.join(metrics, "regression.json")),
        "safety_sha256": sha256_file(os.path.join(metrics, "safety.json")),
        "reentry_audit_sha256": sha256_file(os.path.join(metrics, "reentry-audit.json")),
        "frontier_audit_sha256": sha256_file(os.path.join(metrics, "frontier-audit.json")),
    }
    _write(os.path.join(metrics, "reproduction.json"), reproduction)
    _write(os.path.join(dest, "evidence-manifest.json"), _manifest(dest))
    print(f"outcome {report['derived']['outcome']}")
    print(f"published {published}")
    return report


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", default=RUN_ROOT)
    parser.add_argument("--published", default=PUBLISHED)
    args = parser.parse_args(argv)
    publish(args.run_root, args.published)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
