"""Publish the v0.3.17 inspected-repair result from the frozen candidate cells."""
from __future__ import annotations

import os
import shutil

from benchmark.algorithm_freeze import sha256_file, verify_freeze
from benchmark.application_shape_evidence import (
    canonical_json_bytes, load_json, load_jsonl, sha256_bytes, steps_only,
)
from benchmark.fresh_handoff_analysis import product_default_changed
from benchmark.horizon_handoff_analysis import GUARD_CONFIRMED
from benchmark.horizon_handoff_modelcheck import enumerate_traces as enumerate_handoff
from benchmark.horizon_handoff_publish import HISTORY
from benchmark.local_action_drain_analysis import (
    LAB_GUARD, REGRESSION_APPS, confirmed_of, derive_v0317_outcome,
    directory_preserved, lab_mechanism_gate, lost_vs, mechanism_preserved,
    transfer_preserved,
)
from benchmark.local_action_drain_audit import _first_hit
from benchmark.local_action_drain_audit import _manifest as _lab_manifest
from benchmark.local_action_drain_modelcheck import enumerate_traces as enumerate_local
from benchmark.local_action_drain_run import APPS, CANDIDATE, CELLS, cell_dir, cell_stem
from benchmark.local_action_drain_trace import diagnose_lab
from benchmark.reentry_frontier_modelcheck import enumerate_traces as enumerate_reentry
from benchmark.return_cycle_guard_reproduce import verify_candidate_identity
from benchmark.return_cycle_modelcheck import run_exhaustive_check

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_ROOT = os.path.join("experiments", "runs", "v0317-local-action")
PUBLISHED = os.path.join("experiments", "published", "local-action-drain-v0.3.17")
FRESH = os.path.join("experiments", "published", "fresh-handoff-v0.3.15")
REENTRY = os.path.join("experiments", "published", "reentry-frontier-v0.3.16")
PROTOCOL = os.path.join("experiments", "validation", "v0.3.17", "protocol.json")
ANALYSIS = os.path.join(
    "experiments", "validation", "v0.3.17", "v0316-local-frontier-analysis.json")
FREEZE = os.path.join(
    "experiments", "frozen", "ghost-local-action-drain-v0.3.17", "freeze.json")
GUARD = "ghost-structural-return-guard"
HAND = "ghost-structural-horizon-handoff-guard"
PREVIOUS = "ghost-structural-reentry-frontier-guard"
FRESH_APPS = ("buggy-directory", "buggy-lab", "buggy-forum", "buggy-billing")
SOURCE = os.path.join("ghostqa", "exploration", "local_action_drain_guard.py")
NEEDLES = (
    "buggy-lab", "buggy-directory", "buggy-forum", "buggy-billing",
    "bug-", "btn_staff_note", "btn_cool", "btn_close", "btn_reopen",
    "open_result_from_run", "open_run_again", "samples.html",
    "manifest", "app.js", "topology",
)


def _abs(path: str) -> str:
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


def _metrics(path: str) -> dict:
    full = _abs(path)
    if not os.path.isfile(full):
        return {}
    return load_json(full)


def _row(metrics: dict, policy: str, budget: int) -> dict:
    for row in metrics.get("runs") or []:
        if row.get("policy") == policy and int(row.get("budget") or 0) == budget:
            return row
    return {}


def _fresh_metrics(app: str) -> dict:
    return _metrics(os.path.join(FRESH, "evidence", app, "metrics.json"))


def _previous_metrics(evidence: str) -> dict:
    return _metrics(os.path.join(REENTRY, "evidence", evidence, "metrics.json"))


def _hist_metrics(evidence: str) -> dict:
    return _metrics(HISTORY[evidence]["guard"])


def _run_metrics(run_root: str, app: str) -> dict:
    return _metrics(os.path.join(cell_dir(run_root, app), "metrics.json"))


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
    local = enumerate_local()
    reentry = enumerate_reentry()
    handoff = enumerate_handoff()
    exhaustive = run_exhaustive_check()
    return {
        "a_series_cases": 12,
        "la_series_cases": 10,
        "integration_cases": 10,
        "local_model_raw_traces": local["raw_traces"],
        "local_model_invariant_failures": local["invariant_failures"],
        "local_model_valid_traces": local["valid_traces"],
        "reentry_model_raw_traces": reentry["raw_traces"],
        "reentry_model_invariant_failures": reentry["invariant_failures"],
        "handoff_model_raw_traces": handoff["raw_traces"],
        "handoff_model_invariant_failures": handoff["invariant_failures"],
        "return_exhaustive_traces": exhaustive.get("traces_enumerated"),
        "return_exhaustive_failures": exhaustive.get("failures"),
        "s1_s7_all_pass": bool(exhaustive.get("s1_s7_all_pass")),
        "h_series_cases": 20,
        "n_series_cases": 12,
        "p_series_cases": 15,
        "r_series_cases": 12,
        "f_series_cases": 20,
        "app_specific_needles": _needles(),
        "candidate_freeze_ok": verify_freeze(_abs(FREEZE)) == [],
        "historical_freeze_ok": (
            verify_candidate_identity() == []
            and verify_freeze(_abs(os.path.join(
                "experiments", "frozen", "ghost-horizon-handoff-v0.3.14", "freeze.json"))) == []
            and verify_freeze(_abs(os.path.join(
                "experiments", "frozen", "v0.3.15-fresh-handoff-suite", "freeze.json"))) == []
            and verify_freeze(_abs(os.path.join(
                "experiments", "frozen", "ghost-reentry-frontier-v0.3.16", "freeze.json"))) == []
        ),
        "protocol_executed_false": load_json(_abs(PROTOCOL)).get("executed") is False,
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
        "early_parent_reentry_events", "source_parent_reentry_repair_events",
        "reentry_double_completion_violations",
        "local_frontier_lease_granted_events", "local_frontier_lease_action_events",
        "frontier_repeated_key_violations", "frontier_monotonicity_violations",
        "local_action_drain_started_events", "local_action_drain_exhausted_events",
        "local_action_drain_abort_events", "local_action_drain_epochs",
        "max_local_actions_per_drain", "local_action_keys_drained",
        "local_action_probe_selected_events", "local_action_probe_completed_events",
        "local_action_probe_finding_events", "local_action_probe_crash_events",
        "same_hub_local_action_events", "local_action_new_key_revealed_events",
        "newly_revealed_local_action_keys", "local_action_variant_revisits",
        "local_action_promoted_to_child_events",
        "local_action_promoted_child_witness_events",
        "local_action_promoted_child_unwind_events",
        "repeated_local_action_key_violations", "cross_hub_drain_violations",
        "local_action_sequence_accounting_violations",
    )
    return {key: row.get(key) for key in keys}


def _bug_notes(run_root: str, facts: dict) -> dict:
    path = _abs(_events_path(run_root, "buggy-lab", 120))
    steps = steps_only(load_jsonl(path)) if os.path.isfile(path) else []
    bugs = _lab_manifest()
    notes = {}
    for bug_id in ("BUG-L1", "BUG-L8", "BUG-L9", "BUG-L10"):
        hit = _first_hit(steps, bugs[bug_id]) if steps else None
        notes[bug_id] = {"first_hit": hit}
    notes["run_order"] = facts.get("run")
    notes["result_order"] = facts.get("result")
    run_selected = (facts.get("run") or {}).get("selected_eids") or []
    result_selected = (facts.get("result") or {}).get("selected_eids") or []
    result_cluster = (facts.get("result") or {}).get("hub_cluster") or ""
    revealed = 0
    seq_path = _abs(_seq_path(run_root, "buggy-lab", 120))
    if os.path.isfile(seq_path) and result_cluster:
        for event in load_json(seq_path):
            if event.get("event") != "local_action_new_key_revealed":
                continue
            if (event.get("hub_cluster") or event.get("cluster_id") or "") == result_cluster:
                revealed += 1
    notes["l10_staff_note_before_open_result"] = (
        "btn_staff_note" in run_selected
        and (facts.get("run") or {}).get("structural_eid") == "open_result_from_run"
        and (facts.get("run") or {}).get("probe_before_structural") is True
    )
    notes["l10_navigation_kind"] = (facts.get("run") or {}).get("structural_event") or ""
    notes["l9_close_before_reopen"] = (
        "btn_close" in result_selected and "btn_reopen" in result_selected
        and result_selected.index("btn_close") < result_selected.index("btn_reopen")
    )
    notes["l9_dynamic_reveal_events"] = revealed
    notes["l1_recovered"] = bool(notes["BUG-L1"]["first_hit"])
    notes["l8_recovered"] = bool(notes["BUG-L8"]["first_hit"])
    notes["l9_recovered"] = bool(notes["BUG-L9"]["first_hit"])
    notes["l10_recovered"] = bool(notes["BUG-L10"]["first_hit"])
    return notes


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
        evidence = APPS[app]["evidence"]
        fresh[app] = {
            "guard": _row(metrics, GUARD, 120),
            "horizon": _row(metrics, HAND, 120),
            "previous": _row(_previous_metrics(evidence), PREVIOUS, 120),
            "candidate": cells[(app, 120)],
        }
    historical = {}
    for app, meta in APPS.items():
        if app in FRESH_APPS:
            continue
        evidence = meta["evidence"]
        guard_confirmed = list(GUARD_CONFIRMED.get(evidence) or confirmed_of(
            _row(_hist_metrics(evidence), GUARD, 120)))
        historical[evidence] = {
            "source_app": app,
            "previous": _row(_previous_metrics(evidence), PREVIOUS, 120),
            "candidate": cells[(app, 120)],
            "guard_confirmed": guard_confirmed,
            "regression_case": evidence in REGRESSION_APPS,
        }
    lab_events = []
    seq_path = _abs(_seq_path(run_root, "buggy-lab", 120))
    if os.path.isfile(seq_path):
        lab_events = load_json(seq_path)
    diagnosis = diagnose_lab(lab_events, cells.get(("buggy-lab", 120)) or {})
    directory = fresh["buggy-directory"]["candidate"]
    lab = fresh["buggy-lab"]["candidate"]
    safety = _safety()
    regression_loss = []
    for evidence, block in historical.items():
        lost = lost_vs(block["guard_confirmed"], confirmed_of(block["candidate"]))
        if block["regression_case"] and lost:
            regression_loss.append({evidence: lost})
    witness = terminal = repeated = cross = accounting = 0
    for row in cells.values():
        witness += int(row.get("witness_violations") or 0)
        terminal += int(row.get("terminal_accounting_violations") or 0)
        repeated += int(row.get("repeated_local_action_key_violations") or 0)
        cross += int(row.get("cross_hub_drain_violations") or 0)
        accounting += int(row.get("local_action_sequence_accounting_violations") or 0)
    crm = mechanism_preserved(historical["buggy-crm"]["candidate"])
    ops = mechanism_preserved(historical["buggy-ops"]["candidate"])
    directory_ok = directory_preserved(
        directory, confirmed_of(fresh["buggy-directory"]["guard"]),
        confirmed_of(directory))
    lab_keep = set(LAB_GUARD) <= set(confirmed_of(lab))
    forum_ok = transfer_preserved(
        fresh["buggy-forum"]["guard"], fresh["buggy-forum"]["candidate"],
        evaluable.get("buggy-forum", False))
    billing_ok = transfer_preserved(
        fresh["buggy-billing"]["guard"], fresh["buggy-billing"]["candidate"],
        evaluable.get("buggy-billing", False))
    mechanism_facts = {
        "sample_child_witness": diagnosis["sample_child_witness"],
        "drain_started_at_run": diagnosis["drain_started_at_run"],
        "same_hub_probe_before_structural_navigation": diagnosis[
            "same_hub_probe_before_structural_navigation"],
        "result_drain_started": diagnosis["result_drain_started"],
        "close_reopen_before_structural_navigation": diagnosis[
            "close_reopen_before_structural_navigation"],
        "repeated_local_key_violations": repeated,
        "local_action_sequence_accounting_violations": accounting,
        "witness_violations": witness,
        "terminal_accounting_violations": terminal,
    }
    safety_ok = (
        safety["local_model_invariant_failures"] == 0
        and safety["local_model_raw_traces"] == 66429
        and safety["reentry_model_invariant_failures"] == 0
        and safety["reentry_model_raw_traces"] == 37448
        and safety["handoff_model_invariant_failures"] == 0
        and safety["handoff_model_raw_traces"] == 19607
        and int(safety["return_exhaustive_failures"] or 0) == 0
        and int(safety["return_exhaustive_traces"] or 0) >= 5800
        and safety["s1_s7_all_pass"]
        and safety["candidate_freeze_ok"]
        and safety["historical_freeze_ok"]
        and safety["protocol_executed_false"]
        and not safety["app_specific_needles"]
    )
    derived = derive_v0317_outcome(
        candidate_freeze_ok=safety["candidate_freeze_ok"] and not missing,
        historical_freeze_ok=safety["historical_freeze_ok"],
        protocol_ok=safety["protocol_executed_false"],
        post_freeze_edit=False,
        safety_ok=safety_ok,
        model_ok=safety["local_model_invariant_failures"] == 0,
        model_invariant_failures=safety["local_model_invariant_failures"],
        model_raw_traces=safety["local_model_raw_traces"],
        cross_hub_drain_violations=cross,
        app_specific=bool(safety["app_specific_needles"]),
        hidden_metadata=bool(safety["app_specific_needles"]),
        historical_regression_loss=regression_loss,
        crm_ops_collapse=bool(crm["collapse"] or ops["collapse"]),
        directory_false_handoff=int(directory.get("horizon_handoff_started_events") or 0) > 0,
        product_default_changed=safety["product_default_changed"],
        lab_drain_engaged=diagnosis["lab_drain_engaged"],
        lab_mechanism_gate=lab_mechanism_gate(mechanism_facts),
        lab_zero_guard_loss=lab_keep,
        directory_preserved=directory_ok,
        forum_full_transfer=forum_ok,
        billing_full_transfer=billing_ok,
        crm_preserved=bool(crm["pass"]),
        ops_preserved=bool(ops["pass"]),
        **mechanism_facts,
    )
    bug_notes = _bug_notes(run_root, diagnosis) if not missing else {}
    return {
        "missing": missing,
        "derived": derived,
        "diagnosis": diagnosis,
        "bug_notes": bug_notes,
        "fresh": {
            app: {
                "guard_confirmed": confirmed_of(block["guard"]),
                "horizon_confirmed": confirmed_of(block["horizon"]),
                "v0316_confirmed": confirmed_of(block["previous"]),
                "candidate_confirmed": confirmed_of(block["candidate"]),
                "lost_vs_guard": lost_vs(
                    confirmed_of(block["guard"]), confirmed_of(block["candidate"])),
                "candidate": _slim(block["candidate"]),
                "previous": _slim(block["previous"]),
                "guard": _slim(block["guard"]),
            }
            for app, block in fresh.items()
        },
        "historical": {
            name: {
                "guard_confirmed": block["guard_confirmed"],
                "v0316_confirmed": confirmed_of(block["previous"]),
                "candidate_confirmed": confirmed_of(block["candidate"]),
                "lost_vs_guard": lost_vs(
                    block["guard_confirmed"], confirmed_of(block["candidate"])),
                "candidate": _slim(block["candidate"]),
                "previous": _slim(block["previous"]),
            }
            for name, block in historical.items()
        },
        "lab_budgets": {
            str(budget): _slim(cells[("buggy-lab", budget)])
            for budget in (40, 80, 120)
            if ("buggy-lab", budget) in cells
        },
        "directory_preserved": directory_ok,
        "lab_zero_guard_loss": lab_keep,
        "forum_full_transfer": forum_ok,
        "billing_full_transfer": billing_ok,
        "crm": crm,
        "ops": ops,
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
    if isinstance(payload, str):
        data = payload.encode("utf-8")
    else:
        data = canonical_json_bytes(payload)
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


def _evidence_manifest(root: str) -> dict:
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
    lab = report["fresh"]["buggy-lab"]
    directory = report["fresh"]["buggy-directory"]["candidate"]
    run = (report.get("diagnosis") or {}).get("run") or {}
    result = (report.get("diagnosis") or {}).get("result") or {}
    lines = [
        f"# v0.3.17 result: Outcome {derived['outcome']}",
        "",
        derived["outcome_meaning"],
        "",
        "This round is an inspected repair of the remaining v0.3.16 lab local-action starvation. It is not fresh validation, not generalization, and not a product-default change.",
        "",
        f"Run drain selected: {run.get('selected_eids')}.",
        f"Run structural next: {run.get('structural_event')} {run.get('structural_eid')}.",
        f"Result drain selected: {result.get('selected_eids')}.",
        f"Lab Guard bugs lost: {lab['lost_vs_guard']}.",
        f"Lab buttons drained @120: {lab['candidate'].get('local_action_keys_drained')}.",
        f"Promoted button children @120: {lab['candidate'].get('local_action_promoted_to_child_events')}.",
        f"Directory handoffs: {directory.get('horizon_handoff_started_events')}.",
        f"Product default changed: {str(derived['product_default_changed']).lower()}.",
        "",
        "v0.3.14 Outcome A, v0.3.15 Outcome C, and v0.3.16 Outcome B are unchanged.",
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
        ("v0316-local-frontier-analysis.json", ANALYSIS),
        ("candidate-freeze.json", FREEZE),
    ):
        shutil.copyfile(_abs(src), os.path.join(dest, name))
    metrics = os.path.join(dest, "metrics")
    os.makedirs(os.path.join(dest, "evidence", "safety"), exist_ok=True)
    mechanism = {
        "derived": report["derived"],
        "diagnosis": report["diagnosis"],
        "bug_notes": report["bug_notes"],
        "lab_budgets": report["lab_budgets"],
        "directory_preserved": report["directory_preserved"],
        "lab_zero_guard_loss": report["lab_zero_guard_loss"],
        "forum_full_transfer": report["forum_full_transfer"],
        "billing_full_transfer": report["billing_full_transfer"],
        "crm": report["crm"],
        "ops": report["ops"],
        "fresh": report["fresh"],
        "cells": report["cells"],
    }
    regression = {"historical": report["historical"], "fresh": {
        app: {
            "guard_confirmed": block["guard_confirmed"],
            "v0316_confirmed": block["v0316_confirmed"],
            "candidate_confirmed": block["candidate_confirmed"],
            "lost_vs_guard": block["lost_vs_guard"],
        }
        for app, block in report["fresh"].items()
    }}
    safety = report["safety"]
    local_audit = {
        "diagnosis": report["diagnosis"],
        "bug_notes": report["bug_notes"],
        "lab_zero_guard_loss": report["lab_zero_guard_loss"],
        "lost_vs_guard": report["fresh"]["buggy-lab"]["lost_vs_guard"],
        "guard_confirmed": report["fresh"]["buggy-lab"]["guard_confirmed"],
        "v0316_confirmed": report["fresh"]["buggy-lab"]["v0316_confirmed"],
        "candidate_confirmed": report["fresh"]["buggy-lab"]["candidate_confirmed"],
    }
    _write(os.path.join(metrics, "mechanism.json"), mechanism)
    _write(os.path.join(metrics, "regression.json"), regression)
    _write(os.path.join(metrics, "safety.json"), safety)
    _write(os.path.join(metrics, "local-action-audit.json"), local_audit)
    _write(os.path.join(dest, "evidence", "safety", "checks.json"), {
        "local_model_raw_traces": safety["local_model_raw_traces"],
        "local_model_invariant_failures": safety["local_model_invariant_failures"],
        "reentry_model_raw_traces": safety["reentry_model_raw_traces"],
        "reentry_model_invariant_failures": safety["reentry_model_invariant_failures"],
        "handoff_model_raw_traces": safety["handoff_model_raw_traces"],
        "handoff_model_invariant_failures": safety["handoff_model_invariant_failures"],
        "return_exhaustive_traces": safety["return_exhaustive_traces"],
        "return_exhaustive_failures": safety["return_exhaustive_failures"],
        "app_specific_needles": safety["app_specific_needles"],
        "product_default_changed": safety["product_default_changed"],
    })
    config = {
        "round": "v0.3.17",
        "starting_head": "d66fb7303cb18ef341161c77ae8f4689ac067f8e",
        "protocol_commit": "de348adc61fedbffc5b341edea9e432195ae6c86",
        "candidate_freeze_commit": "5a46bbab67ba6c3cc56afa807ce2c62de7347ae0",
        "candidate": CANDIDATE,
        "cells": [f"{app}@{budget}" for app, budget in CELLS],
        "product_default_changed": False,
        "outcome": report["derived"]["outcome"],
        "scope": "inspected repair, not fresh validation",
        "verify_command": (
            "python -m benchmark.local_action_drain_reproduce "
            "--root experiments/published/local-action-drain-v0.3.17 --verify"
        ),
    }
    _write(os.path.join(dest, "config.json"), config)
    with open(os.path.join(dest, "summary.md"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(_summary(report))
    reproduction = {
        "clean_clone_verified": False,
        "command": config["verify_command"],
        "outcome": report["derived"]["outcome"],
        "mechanism_sha256": sha256_file(os.path.join(metrics, "mechanism.json")),
        "regression_sha256": sha256_file(os.path.join(metrics, "regression.json")),
        "safety_sha256": sha256_file(os.path.join(metrics, "safety.json")),
        "local_action_audit_sha256": sha256_file(os.path.join(metrics, "local-action-audit.json")),
    }
    _write(os.path.join(metrics, "reproduction.json"), reproduction)
    _write(os.path.join(dest, "evidence-manifest.json"), _evidence_manifest(dest))
    print(f"outcome {report['derived']['outcome']}")
    print(sha256_bytes(canonical_json_bytes(report["derived"])))
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
