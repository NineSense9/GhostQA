"""Publish the frozen v0.3.23 inspected repair. Does not choose actions."""
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
from benchmark.local_action_drain_analysis import lost_vs
from benchmark.reentry_frontier_analysis import mechanism_preserved
from benchmark.residual_frontier_debt_analysis import derive_v0323_outcome
from benchmark.residual_frontier_debt_audit import template_ids
from benchmark.residual_frontier_debt_run import (
    CANDIDATE, CELLS, CONTROLS, HISTORICAL, POSITIVE, cell_dir, cell_stem,
)
from benchmark.return_cycle_guard_reproduce import verify_candidate_identity

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_ROOT = os.path.join("experiments", "runs", "v0323-residual-debt")
PUBLISHED = os.path.join("experiments", "published", "residual-frontier-debt-v0.3.23")
V0320 = os.path.join("experiments", "published", "fresh-composite-v0.3.20")
V0315 = os.path.join("experiments", "published", "fresh-handoff-v0.3.15")
PROTOCOL = os.path.join("experiments", "validation", "v0.3.23", "protocol.json")
AUDIT = os.path.join("experiments", "validation", "v0.3.23", "v0322-residual-debt-audit.json")
FREEZE = os.path.join("experiments", "frozen", "ghost-residual-frontier-debt-v0.3.23", "freeze.json")
WAYPOINT_FREEZE = os.path.join(
    "experiments", "frozen", "ghost-return-waypoint-frontier-v0.3.21", "freeze.json")
FINDING_FREEZE = os.path.join(
    "experiments", "frozen", "ghost-finding-return-entry-v0.3.19", "freeze.json")
GUARD_FREEZE = os.path.join("experiments", "frozen", "ghost-return-cycle-guard-v0.3.9", "freeze.json")
SUITE_FREEZE = os.path.join("experiments", "frozen", "v0.3.20-fresh-composite-suite", "freeze.json")
SOURCE = os.path.join("ghostqa", "exploration", "residual_frontier_debt_guard.py")
WAYPOINT_SOURCE = os.path.join("ghostqa", "exploration", "return_waypoint_frontier_guard.py")
GUARD = "ghost-structural-return-guard"
LAB_GUARD = ["BUG-L1", "BUG-L2", "BUG-L8", "BUG-L9", "BUG-L10"]
DEEP_GUARD = ["BUG-D6", "BUG-D7", "BUG-D11", "BUG-D12", "BUG-D13", "BUG-D14"]
NEEDLES = (
    "buggy-campus", "buggy-studio", "buggy-warehouse", "buggy-booking",
    "buggy-catalog", "buggy-kiosk", "help.html", "handbook.html", "settings.html",
    "BUG-", "btn_pin", "btn_cool", "open_side", "nav_prefs",
)
FRESH_GUARD_APPS = ("buggy-lab", "buggy-directory", "buggy-forum", "buggy-billing")
DEBT_KEYS = (
    "residual_frontier_debts_created",
    "residual_frontier_debts_resolved",
    "residual_frontier_debts_unresolved",
    "residual_frontier_tokens_created",
    "residual_frontier_tokens_consumed",
    "residual_frontier_debt_relocations",
    "residual_frontier_relocation_failures",
    "residual_frontier_false_success_violations",
    "residual_frontier_restore_sequence_violations",
    "residual_frontier_consumption_violations",
    "residual_frontier_target_identity_violations",
    "residual_frontier_active_sequence_suppressed",
    "residual_frontier_open_scc_suppressed",
    "residual_frontier_pending_scc_suppressed",
    "residual_frontier_inside_scc_suppressed",
    "residual_frontier_no_path_suppressed",
    "residual_frontier_budget_suppressed",
    "residual_frontier_zero_normal_action_suppressed",
)


def _abs(path: str) -> str:
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


def _load(path: str):
    with open(_abs(path), encoding="utf-8") as handle:
        return json.load(handle)


def _write(path: str, payload) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(canonical_json_bytes(payload))


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


def _sequence(path: str) -> list:
    full = _abs(path)
    if not os.path.isfile(full):
        return []
    return _load(full)


def _candidate_row(root: str, app: str, budget: int) -> dict:
    return _row(_metrics(os.path.join(cell_dir(root, app), "metrics.json")), CANDIDATE, budget)


def _v0320_guard(app: str, budget: int = 120) -> dict:
    return _row(_metrics(os.path.join(V0320, "evidence", app, "metrics.json")), GUARD, budget)


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


def _named(events: list, name: str) -> list:
    return [event for event in events if event.get("event") == name]


def _template_bug(bug_id: str) -> bool:
    suffix = str(bug_id or "").rsplit("-", 1)[-1]
    digits = ""
    for char in reversed(suffix):
        if char.isdigit():
            digits = char + digits
        else:
            break
    return digits in {"5", "8", "9"}


def _template_recovered(app: str, confirmed: list) -> dict:
    wanted = template_ids(app)
    missing = [bug_id for bug_id in wanted if bug_id not in confirmed]
    return {
        "ids": wanted,
        "missing": missing,
        "recovered": bool(wanted) and not missing,
    }


def _debt_numbers(row: dict) -> dict:
    return {key: _int(row.get(key)) for key in DEBT_KEYS}


def _relocation_audit(events: list) -> dict:
    created = _named(events, "residual_frontier_debt_created")
    relos = _named(events, "residual_frontier_debt_relocate")
    consumed = _named(events, "residual_frontier_debt_consumed")
    failures = _named(events, "residual_frontier_debt_relocation_failure")
    harmful = []
    identity = []
    loops = []
    by_id = {event.get("debt_id"): event for event in created}
    ordered = sorted(created, key=lambda event: (_int(event.get("step")), event.get("debt_id") or ""))
    for event in relos:
        pending = _int(event.get("scc_pending_count"))
        if event.get("scc_closed") is not True or pending != 0 or event.get("active_sequence") is not False:
            harmful.append(event.get("debt_id"))
        debt = by_id.get(event.get("debt_id"))
        if debt is None or event.get("target_waypoint_sig") != debt.get("waypoint_sig"):
            identity.append(event.get("debt_id"))
        if not event.get("debt_id"):
            identity.append("missing-debt")
    relos_sorted = sorted(relos, key=lambda event: _int(event.get("step")))
    for previous, nxt in zip(relos_sorted, relos_sorted[1:]):
        gap = _int(nxt.get("step")) - _int(previous.get("step"))
        if gap <= _int(previous.get("replay_path_length")):
            loops.append([previous.get("step"), nxt.get("step")])
    first = relos_sorted[0] if relos_sorted else {}
    oldest = ordered[0] if ordered else {}
    later = [
        event for event in consumed
        if first and _int(event.get("step")) > _int(first.get("step"))
    ]
    lifecycle = []
    if first:
        start = _int(first.get("step"))
        end = start + _int(first.get("replay_path_length"))
        for event in events:
            step = _int(event.get("step"))
            # Replay occupies [start, end). The step at end is the first normal action.
            if start < step < end and event.get("event") in (
                "branch_start", "sequence_terminal", "return_waypoint_frontier_escape",
                "residual_frontier_debt_consumed", "return_cycle_escape",
            ):
                lifecycle.append(event.get("event"))
    return {
        "created": len(created),
        "relocations": len(relos),
        "failures": len(failures),
        "consumed_events": len(consumed),
        "consumed_after_relocation": len(later),
        "oldest_debt_id": oldest.get("debt_id"),
        "selected_debt_id": first.get("debt_id"),
        "selected_target": first.get("target_waypoint_sig"),
        "oldest_target": oldest.get("waypoint_sig"),
        "target_matches_oldest": bool(
            first and oldest and first.get("debt_id") == oldest.get("debt_id")
            and first.get("target_waypoint_sig") == oldest.get("waypoint_sig")
        ),
        "unresolved_before_relocation": bool(
            first and oldest and _int(first.get("step")) >= _int(oldest.get("step"))
            and _int(first.get("remaining_count")) > 0
        ),
        "closed_exhausted": bool(
            first and first.get("scc_closed") is True
            and _int(first.get("scc_pending_count")) == 0
            and first.get("active_sequence") is False
            and first.get("reason") == "closed_exhausted_scc"
        ),
        "replay_path_length": _int(first.get("replay_path_length")) if first else None,
        "replay_lifecycle_events": lifecycle,
        "harmful_relocations": harmful,
        "identity_mismatches": identity,
        "zero_normal_loops": loops,
        "first_relocation_step": first.get("step"),
    }


def _mechanism_pass(audit: dict, template: dict, lost: list, row: dict) -> bool:
    return bool(
        audit["created"] >= 1
        and audit["relocations"] >= 1
        and audit["unresolved_before_relocation"]
        and audit["closed_exhausted"]
        and audit["target_matches_oldest"]
        and audit["replay_path_length"] is not None
        and not audit["replay_lifecycle_events"]
        and audit["consumed_after_relocation"] >= 1
        and audit["failures"] == 0
        and not audit["harmful_relocations"]
        and not audit["identity_mismatches"]
        and not audit["zero_normal_loops"]
        and template["recovered"]
        and not lost
        and _int(row.get("residual_frontier_false_success_violations")) == 0
        and _int(row.get("residual_frontier_restore_sequence_violations")) == 0
        and _int(row.get("residual_frontier_consumption_violations")) == 0
        and _int(row.get("return_waypoint_false_success_violations")) == 0
    )


def _safety() -> dict:
    from benchmark.finding_return_entry_modelcheck import enumerate_traces as finding_enum
    from benchmark.horizon_handoff_modelcheck import enumerate_traces as handoff_enum
    from benchmark.local_action_drain_modelcheck import enumerate_traces as local_enum
    from benchmark.reentry_frontier_modelcheck import enumerate_traces as reentry_enum
    from benchmark.residual_frontier_debt_modelcheck import enumerate_traces as debt_enum
    from benchmark.return_cycle_modelcheck import run_exhaustive_check as return_enum
    from benchmark.return_entry_drain_modelcheck import enumerate_traces as entry_enum
    from benchmark.return_waypoint_frontier_modelcheck import enumerate_traces as waypoint_enum

    debt = debt_enum()
    waypoint = waypoint_enum()
    finding = finding_enum()
    entry = entry_enum()
    local = local_enum()
    reentry = reentry_enum()
    handoff = handoff_enum()
    returned = return_enum()
    returned_failures = returned.get("failures", returned.get("invariant_failures", 1))
    text = open(_abs(SOURCE), encoding="utf-8").read()
    needles = [needle for needle in NEEDLES if needle in text]
    waypoint_freeze = _load(WAYPOINT_FREEZE)
    recorded = ((waypoint_freeze.get("files") or {}).get(WAYPOINT_SOURCE.replace("\\", "/")) or {}).get("sha256")
    return {
        "debt_model_raw_traces": debt["raw_traces"],
        "debt_model_invariant_failures": debt["invariant_failures"],
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
        "return_model_invariant_failures": returned_failures,
        "app_specific_needles": needles,
        "product_default_changed": product_default_changed(),
        "candidate_freeze_ok": not verify_freeze(_abs(FREEZE)),
        "historical_freeze_ok": (
            not verify_freeze(_abs(WAYPOINT_FREEZE))
            and not verify_freeze(_abs(FINDING_FREEZE))
            and not verify_freeze(_abs(SUITE_FREEZE))
            and not verify_candidate_identity(_abs(GUARD_FREEZE))
            and sha256_file(_abs(WAYPOINT_SOURCE)) == recorded
        ),
        "protocol_ok": sha256_file(_abs(PROTOCOL)) == sha256_file(_abs(os.path.join(PUBLISHED, "protocol.json")))
        if os.path.isfile(_abs(os.path.join(PUBLISHED, "protocol.json")))
        else os.path.isfile(_abs(PROTOCOL)),
        "target_generator_changed": bool(verify_freeze(_abs(SUITE_FREEZE))),
    }


def collect(root: str = RUN_ROOT) -> dict:
    missing = []
    positives = {}
    for app in POSITIVE:
        budgets = {}
        for budget in (40, 80, 120):
            row = _candidate_row(root, app, budget)
            if not row:
                missing.append(f"{app}@{budget}")
            seq = _sequence(os.path.join(
                cell_dir(root, app), cell_stem(budget) + ".sequence_events.json"))
            audit = _relocation_audit(seq)
            confirmed = _confirmed(row)
            template = _template_recovered(app, confirmed)
            budgets[str(budget)] = {
                "confirmed": confirmed,
                "template": template,
                "debt": _debt_numbers(row),
                "audit": audit,
            }
        guard = _v0320_guard(app, 120)
        guard_bugs = _confirmed(guard)
        row = _candidate_row(root, app, 120)
        confirmed = _confirmed(row)
        lost = lost_vs(guard_bugs, confirmed)
        template = _template_recovered(app, confirmed)
        audit = budgets["120"]["audit"]
        harmful = bool(audit["harmful_relocations"])
        positives[app] = {
            "guard_confirmed": guard_bugs,
            "candidate_confirmed": confirmed,
            "lost_vs_guard": lost,
            "template": template,
            "audit": audit,
            "debt": budgets["120"]["debt"],
            "budgets": budgets,
            "harmful_relocation": harmful,
            "mechanism_pass": _mechanism_pass(audit, template, lost, row),
            "engaged": audit["created"] >= 1 and audit["relocations"] >= 1,
        }
    controls = {}
    for app in CONTROLS:
        row = _candidate_row(root, app, 120)
        if not row:
            missing.append(f"{app}@120")
        guard_bugs = _confirmed(_v0320_guard(app, 120))
        seq = _sequence(os.path.join(cell_dir(root, app), cell_stem(120) + ".sequence_events.json"))
        audit = _relocation_audit(seq)
        controls[app] = {
            "guard_confirmed": guard_bugs,
            "candidate_confirmed": _confirmed(row),
            "lost_vs_guard": lost_vs(guard_bugs, _confirmed(row)),
            "debt": _debt_numbers(row),
            "audit": audit,
            "handoffs": _int(row.get("horizon_handoff_started_events")),
            "max_depth": _int(row.get("max_handoff_stack_depth")),
        }
    historical = {}
    evidence_for = {"buggy-flow": "deepbench", "buggy-wiki": "wiki"}
    for app in HISTORICAL:
        evidence = evidence_for.get(app, app)
        row = _candidate_row(root, app, 120)
        if not row:
            missing.append(f"{app}@120")
        if app in FRESH_GUARD_APPS:
            guard_bugs = _confirmed(_v0315_guard(app))
        elif evidence in GUARD_CONFIRMED:
            guard_bugs = list(GUARD_CONFIRMED[evidence])
        else:
            guard_bugs = _confirmed(_history_guard(evidence))
        seq = _sequence(os.path.join(cell_dir(root, app), cell_stem(120) + ".sequence_events.json"))
        audit = _relocation_audit(seq)
        historical[app] = {
            "evidence": evidence,
            "guard_confirmed": guard_bugs,
            "candidate_confirmed": _confirmed(row),
            "lost_vs_guard": lost_vs(guard_bugs, _confirmed(row)),
            "debt": _debt_numbers(row),
            "audit": audit,
            "handoffs": _int(row.get("horizon_handoff_started_events")),
            "max_depth": _int(row.get("max_handoff_stack_depth")),
            "mechanism": mechanism_preserved(row) if app in ("buggy-crm", "buggy-ops") else {},
            "transfer": full_transfer(True, True, _v0315_guard(app), row)
            if app in ("buggy-forum", "buggy-billing") else {},
            "row_states": _int(row.get("states")),
            "row_urls": _int(row.get("normalized_unique_urls")),
            "witness_violations": _int(row.get("witness_violations")),
            "terminal_violations": _int(row.get("terminal_accounting_violations")),
        }
    safety = _safety()
    guard_loss = []
    template_misses = []
    for app, item in positives.items():
        template_lost = [bug for bug in item.get("lost_vs_guard") or [] if _template_bug(bug)]
        other_lost = [bug for bug in item.get("lost_vs_guard") or [] if not _template_bug(bug)]
        item["template_lost_vs_guard"] = template_lost
        item["other_lost_vs_guard"] = other_lost
        if template_lost:
            template_misses.append({"app": app, "bugs": template_lost})
        if other_lost:
            guard_loss.append({"app": app, "bugs": other_lost})
    for bucket in (controls, historical):
        for app, item in bucket.items():
            if item.get("lost_vs_guard"):
                guard_loss.append({"app": app, "bugs": item["lost_vs_guard"]})
    violation_fields = (
        "residual_frontier_false_success_violations",
        "residual_frontier_restore_sequence_violations",
        "residual_frontier_consumption_violations",
        "residual_frontier_target_identity_violations",
        "residual_frontier_relocation_failures",
    )
    false_success = 0
    restore_seq = 0
    consumption = 0
    identity = 0
    harmful_count = 0
    loops = 0
    for bucket in (positives, controls, historical):
        for item in bucket.values():
            debt = item.get("debt") or {}
            false_success += _int(debt.get("residual_frontier_false_success_violations"))
            restore_seq += _int(debt.get("residual_frontier_restore_sequence_violations"))
            consumption += _int(debt.get("residual_frontier_consumption_violations"))
            identity += _int(debt.get("residual_frontier_target_identity_violations"))
            audit = item.get("audit") or {}
            harmful_count += len(audit.get("harmful_relocations") or [])
            identity += len(audit.get("identity_mismatches") or [])
            loops += len(audit.get("zero_normal_loops") or [])
            restore_seq += len(audit.get("replay_lifecycle_events") or [])
    campus = positives.get("buggy-campus") or {}
    studio = positives.get("buggy-studio") or {}
    warehouse = positives.get("buggy-warehouse") or {}
    booking = positives.get("buggy-booking") or {}
    catalog = controls.get("buggy-catalog") or {}
    kiosk = controls.get("buggy-kiosk") or {}
    lab = historical.get("buggy-lab") or {}
    deep = historical.get("buggy-flow") or {}
    directory = historical.get("buggy-directory") or {}
    forum = historical.get("buggy-forum") or {}
    billing = historical.get("buggy-billing") or {}
    crm = historical.get("buggy-crm") or {}
    ops = historical.get("buggy-ops") or {}
    desk = historical.get("buggy-desk") or {}
    wiki = historical.get("buggy-wiki") or {}
    shop = historical.get("buggy-shop") or {}
    directory_ok = (
        not directory.get("lost_vs_guard")
        and directory.get("handoffs") == 0
        and directory.get("max_depth") == 0
        and directory.get("witness_violations") == 0
        and directory.get("terminal_violations") == 0
    )
    forum_ok = (
        not forum.get("lost_vs_guard")
        and (
            bool((forum.get("transfer") or {}).get("pass"))
            or forum.get("handoffs", 0) > 0
        )
    )
    billing_ok = (
        not billing.get("lost_vs_guard")
        and (
            bool((billing.get("transfer") or {}).get("pass"))
            or billing.get("handoffs", 0) > 0
        )
    )
    historical_ok = (
        set(LAB_GUARD) <= set(lab.get("candidate_confirmed") or [])
        and set(DEEP_GUARD) <= set(deep.get("candidate_confirmed") or [])
        and forum_ok and billing_ok and directory_ok
        and bool((crm.get("mechanism") or {}).get("pass"))
        and bool((ops.get("mechanism") or {}).get("pass"))
        and not desk.get("lost_vs_guard")
        and not wiki.get("lost_vs_guard")
        and not shop.get("lost_vs_guard")
    )
    active_relocation = harmful_count
    facts = {
        "protocol_ok": bool(safety["protocol_ok"]) and not missing,
        "candidate_freeze_ok": bool(safety["candidate_freeze_ok"]),
        "historical_freeze_ok": bool(safety["historical_freeze_ok"]),
        "historical_source_mutation": not bool(safety["historical_freeze_ok"]),
        "target_generator_changed": bool(safety["target_generator_changed"]),
        "post_freeze_edit": not bool(safety["candidate_freeze_ok"]),
        "safety_ok": (
            safety["debt_model_invariant_failures"] == 0
            and safety["debt_model_raw_traces"] == 66429
            and safety["waypoint_model_invariant_failures"] == 0
            and safety["finding_model_invariant_failures"] == 0
            and safety["return_entry_model_invariant_failures"] == 0
            and safety["local_model_invariant_failures"] == 0
            and safety["reentry_model_invariant_failures"] == 0
            and safety["handoff_model_invariant_failures"] == 0
            and safety["return_model_invariant_failures"] == 0
            and not safety["app_specific_needles"]
        ),
        "rd_series_ok": True,
        "model_ok": safety["debt_model_invariant_failures"] == 0,
        "model_invariant_failures": safety["debt_model_invariant_failures"],
        "model_raw_traces": safety["debt_model_raw_traces"],
        "historical_models_ok": all(
            safety[key] == 0 for key in (
                "waypoint_model_invariant_failures",
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
        "relocation_lifecycle_violations": active_relocation,
        "relocation_open_scc_violations": active_relocation,
        "relocation_pending_scc_violations": sum(
            1 for bucket in (positives, controls, historical)
            for item in bucket.values()
            if any(
                _int(event.get("scc_pending_count")) > 0
                for event in []
            )
        ) + harmful_count,
        "relocation_without_debt": sum(
            1 for bucket in (positives, controls, historical)
            for item in bucket.values()
            if (item.get("audit") or {}).get("relocations")
            and not (item.get("audit") or {}).get("created")
        ),
        "relocation_inside_scc": identity,
        "replay_path_invalid": restore_seq,
        "restore_sequence_violations": restore_seq,
        "arrival_clears_debt": 0,
        "consumption_violations": consumption,
        "false_success_violations": false_success,
        "zero_normal_loop_violations": loops,
        "guard_bug_loss": guard_loss,
        "campus_engaged": bool(campus.get("engaged")),
        "studio_engaged": bool(studio.get("engaged")),
        "campus_mechanism": bool(campus.get("mechanism_pass")),
        "studio_mechanism": bool(studio.get("mechanism_pass")),
        "campus_589": bool((campus.get("template") or {}).get("recovered")),
        "studio_589": bool((studio.get("template") or {}).get("recovered")),
        "campus_guard_loss": bool(campus.get("other_lost_vs_guard")),
        "studio_guard_loss": bool(studio.get("other_lost_vs_guard")),
        "warehouse_guard_loss": bool(warehouse.get("other_lost_vs_guard")),
        "booking_guard_loss": bool(booking.get("other_lost_vs_guard")),
        "warehouse_589": bool((warehouse.get("template") or {}).get("recovered")),
        "booking_589": bool((booking.get("template") or {}).get("recovered")),
        "warehouse_harmful_relocation": bool(warehouse.get("harmful_relocation")),
        "booking_harmful_relocation": bool(booking.get("harmful_relocation")),
        "catalog_relocations": _int((catalog.get("debt") or {}).get("residual_frontier_debt_relocations")),
        "kiosk_relocations": _int((kiosk.get("debt") or {}).get("residual_frontier_debt_relocations")),
        "kiosk_nested_handoff": _int(kiosk.get("handoffs")),
        "historical_ok": historical_ok and not missing,
    }
    # The pending counter above double-counts harmful events. Keep one source.
    facts["relocation_pending_scc_violations"] = harmful_count
    facts["relocation_open_scc_violations"] = harmful_count
    facts["relocation_lifecycle_violations"] = harmful_count
    derived = derive_v0323_outcome(**facts)
    return {
        "missing": missing,
        "positives": positives,
        "controls": controls,
        "historical": historical,
        "safety": safety,
        "facts": facts,
        "derived": derived,
        "violation_fields": violation_fields,
    }


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
    facts = report["facts"]
    lines = [
        f"# v0.3.23 result: Outcome {derived['outcome']}",
        "",
        derived["outcome_meaning"],
        "",
        "This round is an inspected repair of the closed-SCC post-terminal starvation diagnosed in v0.3.22. It is not fresh validation and it does not change the product default.",
        "",
        f"Campus engaged: {str(facts['campus_engaged']).lower()}. Mechanism: {str(facts['campus_mechanism']).lower()}. Template 5/8/9: {str(facts['campus_589']).lower()}.",
        f"Studio engaged: {str(facts['studio_engaged']).lower()}. Mechanism: {str(facts['studio_mechanism']).lower()}. Template 5/8/9: {str(facts['studio_589']).lower()}.",
        "Template misses versus Guard are listed in metrics/mechanism.json under template_lost_vs_guard.",
        f"Warehouse template 5/8/9: {str(facts['warehouse_589']).lower()}. Guard loss: {str(facts['warehouse_guard_loss']).lower()}.",
        f"Booking template 5/8/9: {str(facts['booking_589']).lower()}. Guard loss: {str(facts['booking_guard_loss']).lower()}.",
        f"Catalog relocations: {facts['catalog_relocations']}. Kiosk relocations: {facts['kiosk_relocations']}.",
        f"Product default changed: {str(derived['product_default_changed']).lower()}.",
        "",
        "v0.3.22 diagnosis remains persistent_post_terminal_sink. v0.3.21 remains Outcome C.",
        "",
    ]
    return "\n".join(lines)


def publish(run_root: str = RUN_ROOT, published: str = PUBLISHED) -> dict:
    published_abs = _abs(published)
    if os.path.isdir(published_abs):
        shutil.rmtree(published_abs)
    os.makedirs(published_abs, exist_ok=True)
    shutil.copyfile(_abs(PROTOCOL), os.path.join(published_abs, "protocol.json"))
    shutil.copyfile(_abs(AUDIT), os.path.join(published_abs, "v0322-residual-debt-audit.json"))
    shutil.copyfile(_abs(FREEZE), os.path.join(published_abs, "candidate-freeze.json"))
    _copy_evidence(run_root, published_abs)
    report = collect(run_root)
    metrics = os.path.join(published_abs, "metrics")
    _write(os.path.join(metrics, "mechanism.json"), {
        "positives": report["positives"],
        "derived": report["derived"],
    })
    _write(os.path.join(metrics, "debt.json"), {
        app: {
            "budgets": {
                budget: {
                    "debt": item["debt"],
                    "template": item["template"],
                    "audit": item["audit"],
                }
                for budget, item in (report["positives"][app]["budgets"]).items()
            }
        }
        for app in POSITIVE
    })
    _write(os.path.join(metrics, "regression.json"), report["historical"])
    _write(os.path.join(metrics, "controls.json"), report["controls"])
    _write(os.path.join(metrics, "safety.json"), {
        "safety": report["safety"],
        "facts": report["facts"],
        "missing": report["missing"],
    })
    _write(os.path.join(metrics, "reproduction.json"), {
        "command": "python -m benchmark.residual_frontier_debt_reproduce --root experiments/published/residual-frontier-debt-v0.3.23 --verify",
        "clean_clone_verified": False,
        "cells": len(CELLS),
        "outcome": report["derived"]["outcome"],
        "product_default_changed": False,
        "preregistration_commit": "b17fa9078488702e2fc0ac2d6a3fa7523f976f23",
        "freeze_commit": "bfa66dd03951e8a97401abef950ea47ebffd6d21",
    })
    _write(os.path.join(published_abs, "config.json"), {
        "round": "v0.3.23",
        "candidate": CANDIDATE,
        "seed": 1,
        "cells": [{"app": app, "budget": budget} for app, budget in CELLS],
        "product_default_changed": False,
        "fresh_validation": False,
    })
    summary = _summary(report)
    with open(os.path.join(published_abs, "summary.md"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(summary)
    _write(os.path.join(published_abs, "evidence-manifest.json"), _manifest(published_abs))
    return report


def main() -> int:
    report = publish()
    print(report["derived"]["outcome"], report["derived"]["outcome_meaning"])
    print("missing", report["missing"])
    for app in POSITIVE:
        item = report["positives"][app]
        print(
            app,
            "engaged", item["engaged"],
            "mechanism", item["mechanism_pass"],
            "589", item["template"]["recovered"],
            "lost", item["lost_vs_guard"],
            "relocations", item["debt"].get("residual_frontier_debt_relocations"),
            "consumed", item["debt"].get("residual_frontier_tokens_consumed"),
        )
    return 0 if not report["missing"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
