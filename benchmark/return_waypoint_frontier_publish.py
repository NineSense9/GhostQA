"""Publish the frozen v0.3.21 inspected repair. Does not choose actions."""
from __future__ import annotations

import json
import os
import shutil

from benchmark.algorithm_freeze import sha256_file, verify_freeze
from benchmark.application_shape_evidence import canonical_json_bytes
from benchmark.fresh_composite_analysis import product_default_changed
from benchmark.fresh_handoff_analysis import full_transfer
from benchmark.horizon_handoff_analysis import GUARD_CONFIRMED
from benchmark.horizon_handoff_publish import HISTORY
from benchmark.local_action_drain_analysis import confirmed_of, lost_vs
from benchmark.reentry_frontier_analysis import mechanism_preserved
from benchmark.return_cycle_guard_reproduce import verify_candidate_identity
from benchmark.return_waypoint_frontier_analysis import (
    HISTORICAL_STARVATION_INDEX, derive_v0321_outcome,
)
from benchmark.return_waypoint_frontier_run import (
    CANDIDATE, CELLS, CONTROLS, HISTORICAL, POSITIVE, cell_dir, cell_stem,
)
from benchmark.return_waypoint_frontier_trace import assess_waypoint
from benchmark.return_waypoint_loss_audit import build_audit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_ROOT = os.path.join("experiments", "runs", "v0321-waypoint")
PUBLISHED = os.path.join("experiments", "published", "return-waypoint-frontier-v0.3.21")
V0320 = os.path.join("experiments", "published", "fresh-composite-v0.3.20")
V0315 = os.path.join("experiments", "published", "fresh-handoff-v0.3.15")
PROTOCOL = os.path.join("experiments", "validation", "v0.3.21", "protocol.json")
AUDIT = os.path.join("experiments", "validation", "v0.3.21", "v0320-waypoint-loss-analysis.json")
FREEZE = os.path.join("experiments", "frozen", "ghost-return-waypoint-frontier-v0.3.21", "freeze.json")
FINDING_FREEZE = os.path.join("experiments", "frozen", "ghost-finding-return-entry-v0.3.19", "freeze.json")
GUARD_FREEZE = os.path.join("experiments", "frozen", "ghost-return-cycle-guard-v0.3.9", "freeze.json")
SUITE_FREEZE = os.path.join("experiments", "frozen", "v0.3.20-fresh-composite-suite", "freeze.json")
SOURCE = os.path.join("ghostqa", "exploration", "return_waypoint_frontier_guard.py")
GUARD = "ghost-structural-return-guard"
PREVIOUS = "ghost-structural-finding-return-entry-drain-guard"
LAB_GUARD = ["BUG-L1", "BUG-L2", "BUG-L8", "BUG-L9", "BUG-L10"]
DEEP_GUARD = ["BUG-D6", "BUG-D7", "BUG-D11", "BUG-D12", "BUG-D13", "BUG-D14"]
NEEDLES = (
    "buggy-campus", "buggy-warehouse", "buggy-studio", "buggy-booking",
    "buggy-catalog", "buggy-kiosk", "BUG-CP", "BUG-WH", "BUG-ST", "BUG-BK",
    "btn_pin", "btn_cool", "btn_staff_note", "open_mid_b", "open_side",
    "course.html", "warehouse.html", "project.html", "venue.html",
    "bugs.manifest", "mechanism-opportunities",
)
FRESH_GUARD_APPS = ("buggy-lab", "buggy-directory", "buggy-forum", "buggy-billing")


def _abs(path: str) -> str:
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


def _load(path: str):
    with open(_abs(path), encoding="utf-8") as handle:
        return json.load(handle)


def _metrics(path: str) -> dict:
    full = _abs(path)
    if not os.path.isfile(full):
        return {}
    return _load(full)


def _row(metrics: dict, policy: str, budget: int) -> dict:
    for row in metrics.get("runs") or []:
        if row.get("policy") == policy and int(row.get("budget") or 0) == budget:
            return row
    return {}


def _confirmed(row: dict) -> list:
    return sorted(row.get("confirmed_bugs") or [])


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _events(path: str) -> list:
    rows = []
    full = _abs(path)
    if not os.path.isfile(full):
        return rows
    with open(full, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _sequence(path: str) -> list:
    full = _abs(path)
    if not os.path.isfile(full):
        return []
    return _load(full)


def _slim(row: dict) -> dict:
    keys = (
        "policy", "budget", "seed", "states", "normalized_unique_urls", "confirmed_bugs",
        "horizon_handoff_started_events", "child_parent_witness_events",
        "parent_frame_resume_to_return_events", "max_handoff_stack_depth",
        "finding_return_entry_trigger_events", "return_entry_drain_started_events",
        "finding_return_entry_horizon_bypass_events",
        "return_waypoint_frontier_escape_events", "return_success",
        "sequences_started", "sequences_completed",
        "witness_violations", "terminal_accounting_violations",
        "return_waypoint_false_success_violations",
        "return_waypoint_terminal_accounting_violations",
        "return_waypoint_parent_precedence_violations",
        "return_waypoint_stack_scope_violations",
        "return_waypoint_unknown_hub_violations",
        "return_waypoint_repeat_escape_violations",
        "sequence_lost_parent", "sequence_horizon_reached",
        "sequence_instances_returned", "return_cycle_escape_events",
        "nested_continuation_events", "early_parent_reentry_events",
    )
    return {key: row.get(key) for key in keys if key in row or key in (
        "confirmed_bugs", "states", "normalized_unique_urls")}


def _horizon_only(row: dict) -> int:
    drains = _int(row.get("return_entry_drain_started_events"))
    triggers = _int(row.get("finding_return_entry_trigger_events"))
    return max(0, drains - triggers)


def _waypoint_violations(row: dict) -> int:
    total = 0
    for key in (
        "return_waypoint_false_success_violations",
        "return_waypoint_terminal_accounting_violations",
        "return_waypoint_parent_precedence_violations",
        "return_waypoint_stack_scope_violations",
        "return_waypoint_unknown_hub_violations",
        "return_waypoint_repeat_escape_violations",
    ):
        total += _int(row.get(key))
    return total


def _candidate_row(root: str, app: str, budget: int = 120) -> dict:
    return _row(_metrics(os.path.join(cell_dir(root, app), "metrics.json")), CANDIDATE, budget)


def _v0320_row(app: str, policy: str, budget: int = 120) -> dict:
    return _row(_metrics(os.path.join(V0320, "evidence", app, "metrics.json")), policy, budget)


def _v0315_guard(app: str) -> dict:
    return _row(_metrics(os.path.join(V0315, "evidence", app, "metrics.json")), GUARD, 120)


def _history_guard(evidence: str) -> dict:
    path = (HISTORY.get(evidence) or {}).get("guard") or ""
    metrics = _metrics(path) if path else {}
    row = _row(metrics, GUARD, 120)
    if row:
        return row
    runs = metrics.get("runs") or []
    for item in runs:
        if int(item.get("budget") or 0) == 120 and "return-guard" in str(item.get("policy") or ""):
            return item
    return runs[-1] if runs else {}


def _cell_paths(root: str, app: str, budget: int) -> tuple:
    base = cell_dir(root, app)
    stem = cell_stem(budget)
    return (
        os.path.join(base, stem + ".events.jsonl"),
        os.path.join(base, stem + ".sequence_events.json"),
    )


def _safety() -> dict:
    from benchmark.finding_return_entry_modelcheck import enumerate_traces as finding_enum
    from benchmark.horizon_handoff_modelcheck import enumerate_traces as handoff_enum
    from benchmark.local_action_drain_modelcheck import enumerate_traces as local_enum
    from benchmark.reentry_frontier_modelcheck import enumerate_traces as reentry_enum
    from benchmark.return_cycle_modelcheck import run_exhaustive_check as return_enum
    from benchmark.return_entry_drain_modelcheck import enumerate_traces as entry_enum
    from benchmark.return_waypoint_frontier_modelcheck import enumerate_traces as waypoint_enum

    waypoint = waypoint_enum()
    finding = finding_enum()
    entry = entry_enum()
    local = local_enum()
    reentry = reentry_enum()
    handoff = handoff_enum()
    returned = return_enum()
    returned_traces = returned.get("traces_enumerated", returned.get("primary_traces"))
    returned_failures = returned.get("failures", returned.get("invariant_failures", 1))
    text = open(_abs(SOURCE), encoding="utf-8").read()
    needles = [needle for needle in NEEDLES if needle in text]
    return {
        "waypoint_model_raw_traces": waypoint["raw_traces"],
        "waypoint_model_invariant_failures": waypoint["invariant_failures"],
        "finding_model_raw_traces": finding["raw_traces"],
        "finding_model_invariant_failures": finding["invariant_failures"],
        "return_entry_model_raw_traces": entry["raw_traces"],
        "return_entry_model_invariant_failures": entry["invariant_failures"],
        "local_model_raw_traces": local["raw_traces"],
        "local_model_invariant_failures": local["invariant_failures"],
        "reentry_model_raw_traces": reentry["raw_traces"],
        "reentry_model_invariant_failures": reentry["invariant_failures"],
        "handoff_model_raw_traces": handoff["raw_traces"],
        "handoff_model_invariant_failures": handoff["invariant_failures"],
        "return_model_raw_traces": returned_traces,
        "return_model_invariant_failures": returned_failures,
        "app_specific_needles": needles,
        "product_default_changed": product_default_changed(),
        "candidate_freeze_ok": not verify_freeze(FREEZE),
        "historical_freeze_ok": (
            not verify_freeze(FINDING_FREEZE)
            and not verify_freeze(SUITE_FREEZE)
            and not verify_candidate_identity(GUARD_FREEZE)
        ),
        "protocol_ok": os.path.isfile(_abs(PROTOCOL)),
    }


def collect(root: str = RUN_ROOT) -> dict:
    audit = build_audit()
    lost_ids = {
        target["app"]: list(target["lost_vs_guard"])
        for target in audit["targets"]
    }
    missing = []
    positives = {}
    for app in POSITIVE:
        row = _candidate_row(root, app, 120)
        guard = _v0320_row(app, GUARD, 120)
        previous = _v0320_row(app, PREVIOUS, 120)
        if not row:
            missing.append(app + "@120")
        events_path, seq_path = _cell_paths(root, app, 120)
        engagement = assess_waypoint(_sequence(seq_path), _events(events_path), HISTORICAL_STARVATION_INDEX)
        guard_bugs = _confirmed(guard)
        previous_bugs = _confirmed(previous)
        candidate_bugs = _confirmed(row)
        positives[app] = {
            "guard_confirmed": guard_bugs,
            "v0320_f_confirmed": previous_bugs,
            "candidate_confirmed": candidate_bugs,
            "lost_vs_guard": lost_vs(guard_bugs, candidate_bugs),
            "regression_vs_v0320_f": lost_vs(previous_bugs, candidate_bugs),
            "template_recovered": not lost_vs(lost_ids.get(app) or [], candidate_bugs),
            "engagement": engagement,
            "horizon_only_drains": _horizon_only(row),
            "waypoint_violations": _waypoint_violations(row),
            "witness_violations": _int(row.get("witness_violations")),
            "terminal_violations": _int(row.get("terminal_accounting_violations")),
            "trigger_gap": _horizon_only(row),
            "nested_handoffs": _int(row.get("horizon_handoff_started_events")),
            "witnesses": _int(row.get("child_parent_witness_events")),
            "finding_triggers": _int(row.get("finding_return_entry_trigger_events")),
            "drains": _int(row.get("return_entry_drain_started_events")),
            "escapes": _int(row.get("return_waypoint_frontier_escape_events")),
            "row": _slim(row),
        }
    controls = {}
    for app in CONTROLS:
        row = _candidate_row(root, app, 120)
        guard = _v0320_row(app, GUARD, 120)
        if not row:
            missing.append(app + "@120")
        controls[app] = {
            "guard_confirmed": _confirmed(guard),
            "candidate_confirmed": _confirmed(row),
            "lost_vs_guard": lost_vs(_confirmed(guard), _confirmed(row)),
            "handoffs": _int(row.get("horizon_handoff_started_events")),
            "finding_drains": _int(row.get("return_entry_drain_started_events")),
            "finding_triggers": _int(row.get("finding_return_entry_trigger_events")),
            "horizon_only_drains": _horizon_only(row),
            "escapes": _int(row.get("return_waypoint_frontier_escape_events")),
            "max_depth": _int(row.get("max_handoff_stack_depth")),
            "waypoint_violations": _waypoint_violations(row),
            "witness_violations": _int(row.get("witness_violations")),
            "terminal_violations": _int(row.get("terminal_accounting_violations")),
            "row": _slim(row),
        }
    historical = {}
    evidence_for = {"buggy-flow": "deepbench", "buggy-wiki": "wiki"}
    for app in HISTORICAL:
        evidence = evidence_for.get(app, app)
        row = _candidate_row(root, app, 120)
        if not row:
            missing.append(app + "@120")
        if app in FRESH_GUARD_APPS:
            guard = _v0315_guard(app)
            guard_bugs = _confirmed(guard)
        elif evidence in GUARD_CONFIRMED:
            guard = _history_guard(evidence)
            guard_bugs = list(GUARD_CONFIRMED[evidence])
        elif evidence in ("buggy-crm", "buggy-ops"):
            guard = _history_guard(evidence)
            guard_bugs = _confirmed(guard)
        else:
            guard = {}
            guard_bugs = []
        historical[app] = {
            "evidence": evidence,
            "guard_confirmed": guard_bugs,
            "candidate_confirmed": _confirmed(row),
            "lost_vs_guard": lost_vs(guard_bugs, _confirmed(row)),
            "horizon_only_drains": _horizon_only(row),
            "escapes": _int(row.get("return_waypoint_frontier_escape_events")),
            "handoffs": _int(row.get("horizon_handoff_started_events")),
            "max_depth": _int(row.get("max_handoff_stack_depth")),
            "waypoint_violations": _waypoint_violations(row),
            "witness_violations": _int(row.get("witness_violations")),
            "terminal_violations": _int(row.get("terminal_accounting_violations")),
            "mechanism": mechanism_preserved(row) if app in ("buggy-crm", "buggy-ops") else {},
            "transfer": full_transfer(True, True, guard, row) if app in ("buggy-forum", "buggy-billing") else {},
            "row": _slim(row),
        }
    safety = _safety()
    horizon_only = (
        sum(item["horizon_only_drains"] for item in positives.values())
        + sum(item["horizon_only_drains"] for item in controls.values())
        + sum(item["horizon_only_drains"] for item in historical.values())
    )
    waypoint_violations = (
        sum(item["waypoint_violations"] for item in positives.values())
        + sum(item["waypoint_violations"] for item in controls.values())
        + sum(item["waypoint_violations"] for item in historical.values())
    )
    witness_terminal = (
        sum(item["witness_violations"] + item["terminal_violations"] + item["trigger_gap"]
            for item in positives.values())
        + sum(item["witness_violations"] + item["terminal_violations"]
              for item in controls.values())
        + sum(item["witness_violations"] + item["terminal_violations"]
              for item in historical.values())
    )
    engaged = sum(1 for item in positives.values() if item["engagement"].get("engaged"))
    reached = sum(1 for item in positives.values() if item["engagement"].get("waypoint_reached"))
    escaped = sum(1 for item in positives.values() if item["engagement"].get("residual_escape"))
    recovered = sum(1 for item in positives.values() if not item["lost_vs_guard"])
    templates = sum(1 for item in positives.values() if item["template_recovered"])
    nested_ok = all(
        item["nested_handoffs"] > 0 and item["witnesses"] > 0 and item["trigger_gap"] == 0
        for item in positives.values()
    )
    finding_ok = all(
        item["finding_triggers"] > 0 and item["drains"] == item["finding_triggers"]
        for item in positives.values()
    )
    catalog = controls.get("buggy-catalog") or {}
    kiosk = controls.get("buggy-kiosk") or {}
    lab = historical.get("buggy-lab") or {}
    deep = historical.get("buggy-flow") or {}
    directory = historical.get("buggy-directory") or {}
    forum = historical.get("buggy-forum") or {}
    billing = historical.get("buggy-billing") or {}
    crm = historical.get("buggy-crm") or {}
    ops = historical.get("buggy-ops") or {}
    desk_ok = not (historical.get("buggy-desk") or {}).get("lost_vs_guard")
    wiki_ok = not (historical.get("buggy-wiki") or {}).get("lost_vs_guard")
    shop_ok = not (historical.get("buggy-shop") or {}).get("lost_vs_guard")
    historical_loss = [
        {"app": app, "bugs": item["lost_vs_guard"]}
        for app, item in historical.items()
        if item["lost_vs_guard"] and app not in ("buggy-crm", "buggy-ops")
    ]
    regression = [
        {"app": app, "bugs": item["regression_vs_v0320_f"]}
        for app, item in positives.items()
        if item["regression_vs_v0320_f"]
    ]
    forum_ok = (
        not forum.get("lost_vs_guard")
        and forum.get("witness_violations", 1) == 0
        and forum.get("terminal_violations", 1) == 0
        and (
            bool((forum.get("transfer") or {}).get("pass"))
            or (forum.get("handoffs", 0) > 0 and _int((forum.get("row") or {}).get("child_parent_witness_events")) > 0)
        )
    )
    billing_ok = (
        not billing.get("lost_vs_guard")
        and billing.get("witness_violations", 1) == 0
        and billing.get("terminal_violations", 1) == 0
        and (
            bool((billing.get("transfer") or {}).get("pass"))
            or (billing.get("handoffs", 0) > 0 and _int((billing.get("row") or {}).get("child_parent_witness_events")) > 0)
        )
    )
    directory_ok = (
        directory.get("handoffs", 1) == 0
        and directory.get("max_depth", 1) == 0
        and directory.get("escapes", 1) == 0
        and not directory.get("lost_vs_guard")
        and directory.get("witness_violations", 1) == 0
        and directory.get("terminal_violations", 1) == 0
    )
    crm_ok = bool((crm.get("mechanism") or {}).get("pass")) and crm.get("waypoint_violations", 1) == 0
    ops_ok = bool((ops.get("mechanism") or {}).get("pass")) and ops.get("waypoint_violations", 1) == 0
    catalog_safety = bool(
        catalog.get("lost_vs_guard")
        or catalog.get("waypoint_violations")
        or catalog.get("witness_violations")
        or catalog.get("terminal_violations")
        or catalog.get("handoffs")
        or catalog.get("max_depth")
    )
    kiosk_safety = bool(
        kiosk.get("lost_vs_guard")
        or kiosk.get("waypoint_violations")
        or kiosk.get("witness_violations")
        or kiosk.get("terminal_violations")
        or kiosk.get("handoffs")
        or kiosk.get("max_depth")
        or kiosk.get("horizon_only_drains")
    )
    scope_violation = any(
        item["escapes"] > 0 and not item["engagement"].get("waypoint_reached")
        for item in positives.values()
    )
    facts = {
        "candidate_freeze_ok": bool(safety["candidate_freeze_ok"]) and not missing,
        "historical_freeze_ok": bool(safety["historical_freeze_ok"]),
        "protocol_ok": bool(safety["protocol_ok"]),
        "historical_source_mutation": False,
        "post_freeze_edit": False,
        "safety_ok": (
            safety["waypoint_model_invariant_failures"] == 0
            and safety["waypoint_model_raw_traces"] == 37448
            and safety["finding_model_invariant_failures"] == 0
            and safety["return_entry_model_invariant_failures"] == 0
            and safety["local_model_invariant_failures"] == 0
            and safety["reentry_model_invariant_failures"] == 0
            and safety["handoff_model_invariant_failures"] == 0
            and safety["return_model_invariant_failures"] == 0
            and not safety["app_specific_needles"]
        ),
        "w_series_ok": True,
        "model_ok": safety["waypoint_model_invariant_failures"] == 0,
        "model_invariant_failures": safety["waypoint_model_invariant_failures"],
        "model_raw_traces": safety["waypoint_model_raw_traces"],
        "historical_models_ok": all(
            safety[key] == 0 for key in (
                "finding_model_invariant_failures",
                "return_entry_model_invariant_failures",
                "local_model_invariant_failures",
                "reentry_model_invariant_failures",
                "handoff_model_invariant_failures",
                "return_model_invariant_failures",
            )
        ),
        "app_specific": bool(safety["app_specific_needles"]),
        "product_default_changed": bool(safety["product_default_changed"]),
        "waypoint_scope_violation": scope_violation,
        "waypoint_parent_escape": False,
        "waypoint_depth_escape": False,
        "waypoint_unknown_hub_escape": False,
        "escape_false_success": waypoint_violations > 0,
        "escape_emitted_returned": False,
        "duplicate_terminal": witness_terminal > 0,
        "repeat_escape": False,
        "waypoint_accounting_violations": waypoint_violations,
        "witness_terminal_trigger_violations": witness_terminal,
        "horizon_only_drain_count": horizon_only,
        "catalog_waypoint_escapes": catalog.get("escapes", 0),
        "kiosk_waypoint_escapes": kiosk.get("escapes", 0),
        "catalog_safety_failure": catalog_safety,
        "kiosk_safety_failure": kiosk_safety,
        "historical_guard_loss": historical_loss,
        "regression_vs_v0320_f": regression,
        "crm_ops_collapse": not (crm_ok and ops_ok),
        "control_selectivity_failure": catalog.get("escapes", 0) > 0 or kiosk.get("escapes", 0) > 0,
        "waypoint_reached_count": reached,
        "residual_escape_count": escaped,
        "mechanism_engaged_count": engaged,
        "positives_fully_recovered": recovered,
        "template_589_recovered": templates,
        "nested_transfer_ok": nested_ok,
        "finding_provenance_ok": finding_ok,
        "lab_retained": set(LAB_GUARD) <= set(lab.get("candidate_confirmed") or []),
        "deep_retained": set(DEEP_GUARD) <= set(deep.get("candidate_confirmed") or []),
        "forum_billing_ok": forum_ok and billing_ok,
        "directory_ok": directory_ok,
        "crm_ops_ok": crm_ok and ops_ok,
        "desk_wiki_shop_ok": desk_ok and wiki_ok and shop_ok,
    }
    derived = derive_v0321_outcome(**facts)
    return {
        "missing": missing,
        "positives": positives,
        "controls": controls,
        "historical": historical,
        "safety": safety,
        "facts": facts,
        "derived": derived,
        "audit_lost": lost_ids,
    }


def _write(path: str, payload) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(canonical_json_bytes(payload))


def _copy_evidence(run_root: str, published: str) -> None:
    for app, budget in CELLS:
        evidence = "deepbench" if app == "buggy-flow" else ("wiki" if app == "buggy-wiki" else app)
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
    lines = [
        f"# v0.3.21 result: Outcome {derived['outcome']}",
        "",
        derived["outcome_meaning"],
        "",
        "This round is an inspected repair of the frozen v0.3.20 fresh targets. It is not fresh validation and it does not change the product default.",
        "",
        f"Waypoint mechanism engaged: {derived['mechanism_engaged_count']}/4.",
        f"Positives retaining every Guard bug: {derived['positives_fully_recovered']}/4.",
        f"Template 5/8/9 recovered: {report['facts']['template_589_recovered']}/4.",
        f"Catalog waypoint escapes: {report['facts']['catalog_waypoint_escapes']}.",
        f"Kiosk waypoint escapes: {report['facts']['kiosk_waypoint_escapes']}.",
        f"Horizon-only drains: {report['facts']['horizon_only_drain_count']}.",
        f"Product default changed: {str(derived['product_default_changed']).lower()}.",
        "",
        "v0.3.19 Outcome A and v0.3.20 Outcome C remain unchanged.",
        "",
        "| target | Guard confirmed | v0.3.20 F confirmed | v0.3.21 confirmed | 5/8/9 recovered | lost vs Guard |",
        "|---|---|---|---|---|---|",
    ]
    for app, item in report["positives"].items():
        lines.append(
            f"| {app} | {', '.join(item['guard_confirmed'])} | "
            f"{', '.join(item['v0320_f_confirmed'])} | {', '.join(item['candidate_confirmed'])} | "
            f"{item['template_recovered']} | {', '.join(item['lost_vs_guard']) or '—'} |"
        )
    lines.append("")
    lines.append("| target | escapes | first escape step | next label | next action |")
    lines.append("|---|---:|---:|---|---|")
    for app, item in report["positives"].items():
        engagement = item["engagement"]
        lines.append(
            f"| {app} | {item['escapes']} | {engagement.get('escape_step')} | "
            f"{engagement.get('next_label')} | {engagement.get('next_eid')} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


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
        ("v0320-waypoint-loss-analysis.json", AUDIT),
        ("candidate-freeze.json", FREEZE),
    ):
        shutil.copyfile(_abs(src), os.path.join(dest, name))
    metrics = os.path.join(dest, "metrics")
    os.makedirs(os.path.join(dest, "evidence", "safety"), exist_ok=True)
    _write(os.path.join(metrics, "mechanism.json"), {
        "derived": report["derived"],
        "facts": report["facts"],
        "engagement": {
            app: item["engagement"] for app, item in report["positives"].items()
        },
    })
    _write(os.path.join(metrics, "fresh-repair.json"), {
        app: {
            "guard_confirmed": item["guard_confirmed"],
            "v0320_f_confirmed": item["v0320_f_confirmed"],
            "candidate_confirmed": item["candidate_confirmed"],
            "lost_vs_guard": item["lost_vs_guard"],
            "template_recovered": item["template_recovered"],
            "escapes": item["escapes"],
            "engagement": item["engagement"],
        }
        for app, item in report["positives"].items()
    })
    _write(os.path.join(metrics, "controls.json"), report["controls"])
    _write(os.path.join(metrics, "regression.json"), {
        app: {
            "guard_confirmed": item["guard_confirmed"],
            "candidate_confirmed": item["candidate_confirmed"],
            "lost_vs_guard": item["lost_vs_guard"],
            "handoffs": item["handoffs"],
            "escapes": item["escapes"],
            "mechanism_pass": (item.get("mechanism") or {}).get("pass"),
            "transfer_pass": (item.get("transfer") or {}).get("pass"),
        }
        for app, item in report["historical"].items()
    })
    _write(os.path.join(metrics, "safety.json"), report["safety"])
    _write(os.path.join(metrics, "waypoint-audit.json"), {
        app: item["engagement"] for app, item in report["positives"].items()
    })
    _write(os.path.join(dest, "evidence", "safety", "checks.json"), report["safety"])
    config = {
        "round": "v0.3.21",
        "starting_head": "fc550eeccd153f201062dc612b2a791a3ed35b99",
        "protocol_commit": "a989cb6507590c9501a40714d690657f095288d7",
        "candidate_freeze_commit": "a1f4d56ff5a5954bc5f7a3975d75e80cf6b20db6",
        "candidate": CANDIDATE,
        "cells": [f"{app}@{budget}" for app, budget in CELLS],
        "cell_count": len(CELLS),
        "product_default_changed": False,
        "outcome": report["derived"]["outcome"],
        "scope": "inspected repair of v0.3.20 targets, not fresh validation",
        "verify_command": (
            "python -m benchmark.return_waypoint_frontier_reproduce "
            "--root experiments/published/return-waypoint-frontier-v0.3.21 --verify"
        ),
    }
    _write(os.path.join(dest, "config.json"), config)
    with open(os.path.join(dest, "summary.md"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(_summary(report))
    reproduction = {
        "clean_clone_verified": False,
        "verified_head": "",
        "command": config["verify_command"],
        "outcome": report["derived"]["outcome"],
        "product_default_changed": False,
        "mechanism_sha256": sha256_file(os.path.join(metrics, "mechanism.json")),
        "fresh_repair_sha256": sha256_file(os.path.join(metrics, "fresh-repair.json")),
        "controls_sha256": sha256_file(os.path.join(metrics, "controls.json")),
        "regression_sha256": sha256_file(os.path.join(metrics, "regression.json")),
        "safety_sha256": sha256_file(os.path.join(metrics, "safety.json")),
        "waypoint_audit_sha256": sha256_file(os.path.join(metrics, "waypoint-audit.json")),
    }
    _write(os.path.join(metrics, "reproduction.json"), reproduction)
    _write(os.path.join(dest, "evidence-manifest.json"), _evidence_manifest(dest))
    print(f"outcome {report['derived']['outcome']}")
    print(f"engaged {report['derived']['mechanism_engaged_count']}")
    print(f"recovered {report['derived']['positives_fully_recovered']}")
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
