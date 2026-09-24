"""Publish the frozen v0.3.24 inspected repair. Does not choose actions."""
from __future__ import annotations

import json
import os
import shutil

from benchmark.algorithm_freeze import sha256_file, verify_freeze
from benchmark.episode_drain_epoch_analysis import derive_v0324_outcome
from benchmark.episode_drain_epoch_run import (
    CANDIDATE, CELLS, CONTROLS, HISTORICAL, POSITIVE, cell_dir, cell_stem,
)
from benchmark.fresh_composite_analysis import product_default_changed
from benchmark.fresh_handoff_analysis import full_transfer
from benchmark.horizon_handoff_analysis import GUARD_CONFIRMED
from benchmark.horizon_handoff_publish import HISTORY
from benchmark.local_action_drain_analysis import lost_vs
from benchmark.reentry_frontier_analysis import mechanism_preserved
from benchmark.residual_frontier_debt_audit import template_ids
from benchmark.residual_frontier_debt_publish import (
    _confirmed, _debt_numbers, _history_guard, _int, _load, _named,
    _relocation_audit, _sequence, _template_bug, _template_recovered,
    _v0315_guard, _v0320_guard, _write,
)
from benchmark.return_cycle_guard_reproduce import verify_candidate_identity

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_ROOT = os.path.join("experiments", "runs", "v0324-episode-drain")
PUBLISHED = os.path.join("experiments", "published", "episode-drain-epoch-v0.3.24")
V0320 = os.path.join("experiments", "published", "fresh-composite-v0.3.20")
V0315 = os.path.join("experiments", "published", "fresh-handoff-v0.3.15")
PROTOCOL = os.path.join("experiments", "validation", "v0.3.24", "protocol.json")
AUDIT = os.path.join("experiments", "validation", "v0.3.24", "v0323-episode-drain-audit.json")
FREEZE = os.path.join("experiments", "frozen", "ghost-episode-drain-epoch-v0.3.24", "freeze.json")
DEBT_FREEZE = os.path.join(
    "experiments", "frozen", "ghost-residual-frontier-debt-v0.3.23", "freeze.json")
WAYPOINT_FREEZE = os.path.join(
    "experiments", "frozen", "ghost-return-waypoint-frontier-v0.3.21", "freeze.json")
FINDING_FREEZE = os.path.join(
    "experiments", "frozen", "ghost-finding-return-entry-v0.3.19", "freeze.json")
GUARD_FREEZE = os.path.join("experiments", "frozen", "ghost-return-cycle-guard-v0.3.9", "freeze.json")
SUITE_FREEZE = os.path.join("experiments", "frozen", "v0.3.20-fresh-composite-suite", "freeze.json")
SOURCE = os.path.join("ghostqa", "exploration", "episode_drain_epoch_guard.py")
DEBT_SOURCE = os.path.join("ghostqa", "exploration", "residual_frontier_debt_guard.py")
GUARD = "ghost-structural-return-guard"
LAB_GUARD = ["BUG-L1", "BUG-L2", "BUG-L8", "BUG-L9", "BUG-L10"]
DEEP_GUARD = ["BUG-D6", "BUG-D7", "BUG-D11", "BUG-D12", "BUG-D13", "BUG-D14"]
NEEDLES = (
    "buggy-campus", "buggy-studio", "buggy-warehouse", "buggy-booking",
    "deepbench", "BUG-", "btn_staff_note", "btn_variant", "open_mid_b",
    "lesson.html", "asset.html", "warehouse.html", "booking", "campus", "studio",
)
PROBE_EVENTS = {
    "local_action_drain_started", "local_action_probe_selected",
    "local_action_probe_completed", "return_entry_drain_started",
    "return_entry_probe_selected", "return_entry_probe_completed",
}
EPISODE_KEYS = (
    "local_drain_interaction_episode",
    "local_drain_episode_advances",
    "local_drain_same_hub_keys_recorded",
    "local_drain_same_hub_keys_invalidated",
    "local_drain_cross_hub_keys_preserved",
    "local_drain_revalidated_probe_count",
    "local_drain_revalidated_cluster_count",
    "local_drain_episode_without_relocation_violations",
    "local_drain_cross_hub_invalidation_violations",
    "local_drain_restore_probe_violations",
    "local_drain_episode_false_success_violations",
    "local_drain_duplicate_same_episode_violations",
)
FRESH_GUARD_APPS = ("buggy-lab", "buggy-directory", "buggy-forum", "buggy-billing")
ALLOWED_TRIGGERS = {"local_action_drain", "return_entry_drain"}


def _abs(path: str) -> str:
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


def _metrics(path: str) -> dict:
    full = _abs(path)
    if not os.path.isfile(full):
        return {}
    return _load(full)


def _row(metrics: dict, budget: int) -> dict:
    for row in metrics.get("runs") or []:
        if row.get("policy") == CANDIDATE and int(row.get("budget") or 0) == budget:
            return row
    return {}


def _candidate_row(root: str, app: str, budget: int) -> dict:
    return _row(_metrics(os.path.join(cell_dir(root, app), "metrics.json")), budget)


def _episode_numbers(row: dict) -> dict:
    return {key: _int(row.get(key)) for key in EPISODE_KEYS}


def _template_number(bug_id: str):
    suffix = str(bug_id or "").rsplit("-", 1)[-1]
    digits = ""
    for char in reversed(suffix):
        if char.isdigit():
            digits = char + digits
        else:
            break
    return int(digits) if digits else None


def _replay_probes(events: list) -> int:
    count = 0
    for event in _named(events, "residual_frontier_debt_relocate"):
        start = _int(event.get("step"))
        end = start + _int(event.get("replay_path_length"))
        for item in events:
            step = _int(item.get("step"))
            if start <= step < end and item.get("event") in PROBE_EVENTS:
                count += 1
    return count


def _episode_view(events: list, row: dict) -> dict:
    advances = _named(events, "local_drain_episode_advanced")
    revalidated = _named(events, "local_drain_key_revalidated")
    relos = _named(events, "residual_frontier_debt_relocate")
    later_witness = False
    later_drain = False
    if relos:
        after = _int(relos[0].get("step"))
        witnesses = [
            event for event in _named(events, "child_parent_witness")
            if _int(event.get("step")) > after
        ]
        drains = [
            event for event in _named(events, "local_action_drain_started")
            if _int(event.get("step")) > after
        ]
        later_witness = bool(witnesses)
        for witness in witnesses:
            if any(_int(item.get("step")) >= _int(witness.get("step")) for item in drains):
                later_drain = True
                break
    invalidated = sum(_int(event.get("invalidated_same_hub_key_count")) for event in advances)
    strange_trigger = [
        event.get("trigger") for event in revalidated
        if event.get("trigger") not in ALLOWED_TRIGGERS
    ]
    return {
        "advances": len(advances),
        "invalidated": invalidated,
        "revalidated": len(revalidated),
        "revalidated_clusters": len({event.get("cluster") for event in revalidated}),
        "replay_probes": _replay_probes(events),
        "later_witness": later_witness,
        "later_existing_drain": later_drain,
        "relocations": len(relos),
        "strange_triggers": strange_trigger,
        "false_success": _int(row.get("local_drain_episode_false_success_violations")),
        "cross_hub_violations": _int(row.get("local_drain_cross_hub_invalidation_violations")),
        "restore_probe_violations": _int(row.get("local_drain_restore_probe_violations")),
        "duplicate_violations": _int(row.get("local_drain_duplicate_same_episode_violations")),
        "unbacked_advances": _int(row.get("local_drain_episode_without_relocation_violations")),
        "preserved": sum(_int(event.get("preserved_drained_key_count")) for event in advances),
    }


def _mechanism_pass(view: dict, audit: dict, template: dict, other_lost: list, row: dict) -> bool:
    return bool(
        view["relocations"] >= 1
        and view["advances"] >= 1
        and view["invalidated"] > 0
        and view["replay_probes"] == 0
        and view["later_witness"]
        and view["later_existing_drain"]
        and view["revalidated"] >= 1
        and not view["strange_triggers"]
        and template.get("recovered")
        and not other_lost
        and view["false_success"] == 0
        and audit.get("closed_exhausted")
        and not audit.get("harmful_relocations")
        and not audit.get("replay_lifecycle_events")
        and _int(row.get("residual_frontier_false_success_violations")) == 0
        and _int(row.get("return_waypoint_false_success_violations")) == 0
    )


def _safety() -> dict:
    from benchmark.episode_drain_epoch_modelcheck import enumerate_traces as episode_enum
    from benchmark.finding_return_entry_modelcheck import enumerate_traces as finding_enum
    from benchmark.horizon_handoff_modelcheck import enumerate_traces as handoff_enum
    from benchmark.local_action_drain_modelcheck import enumerate_traces as local_enum
    from benchmark.reentry_frontier_modelcheck import enumerate_traces as reentry_enum
    from benchmark.residual_frontier_debt_modelcheck import enumerate_traces as debt_enum
    from benchmark.return_cycle_modelcheck import run_exhaustive_check as return_enum
    from benchmark.return_entry_drain_modelcheck import enumerate_traces as entry_enum
    from benchmark.return_waypoint_frontier_modelcheck import enumerate_traces as waypoint_enum

    episode = episode_enum()
    debt = debt_enum()
    waypoint = waypoint_enum()
    finding = finding_enum()
    entry = entry_enum()
    local = local_enum()
    reentry = reentry_enum()
    handoff = handoff_enum()
    returned = return_enum()
    text = open(_abs(SOURCE), encoding="utf-8").read()
    needles = [needle for needle in NEEDLES if needle in text]
    protocol = _load(PROTOCOL)
    audit_hash = sha256_file(_abs(AUDIT))
    debt_freeze = _load(DEBT_FREEZE)
    debt_recorded = ((debt_freeze.get("files") or {}).get(DEBT_SOURCE.replace("\\", "/")) or {}).get("sha256")
    return {
        "episode_model_raw_traces": episode["raw_traces"],
        "episode_model_invariant_failures": episode["invariant_failures"],
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
        "return_model_traces": returned.get("traces_enumerated"),
        "return_model_invariant_failures": returned.get("failures", 1),
        "app_specific_needles": needles,
        "product_default_changed": product_default_changed(),
        "candidate_freeze_ok": not verify_freeze(_abs(FREEZE)),
        "historical_freeze_ok": (
            not verify_freeze(_abs(DEBT_FREEZE))
            and not verify_freeze(_abs(WAYPOINT_FREEZE))
            and not verify_freeze(_abs(FINDING_FREEZE))
            and not verify_freeze(_abs(SUITE_FREEZE))
            and not verify_candidate_identity(_abs(GUARD_FREEZE))
            and sha256_file(_abs(DEBT_SOURCE)) == debt_recorded
            and debt_recorded == "20b9a2f775e32fd70b3959ce3202ce8110783c6e3f5ddceb535badf31a6c2bff"
        ),
        "protocol_ok": (
            protocol.get("executed") is False
            and protocol.get("product_default_changed") is False
            and protocol.get("matrix", {}).get("cells_total") == 24
            and (protocol.get("v0_3_23_audit") or {}).get("sha256") == audit_hash
        ),
        "target_generator_changed": bool(verify_freeze(_abs(SUITE_FREEZE))),
        "new_drain_trigger_in_source": "parent_frame_resume" in text or "def pick_override" in text,
    }


def _split_loss(lost: list) -> tuple:
    template_lost = [bug for bug in lost if _template_bug(bug)]
    other_lost = [bug for bug in lost if not _template_bug(bug)]
    retained_template = [
        bug for bug in template_lost if _template_number(bug) in (5, 8)
    ]
    missing_nine = [bug for bug in template_lost if _template_number(bug) == 9]
    return template_lost, other_lost, retained_template, missing_nine


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
            confirmed = _confirmed(row)
            budgets[str(budget)] = {
                "confirmed": confirmed,
                "template": _template_recovered(app, confirmed),
                "debt": _debt_numbers(row),
                "episode": _episode_numbers(row),
                "audit": _relocation_audit(seq),
                "view": _episode_view(seq, row),
            }
        guard_bugs = _confirmed(_v0320_guard(app, 120))
        row = _candidate_row(root, app, 120)
        confirmed = _confirmed(row)
        lost = lost_vs(guard_bugs, confirmed)
        template_lost, other_lost, retained_template, missing_nine = _split_loss(lost)
        template = budgets["120"]["template"]
        audit = budgets["120"]["audit"]
        view = budgets["120"]["view"]
        positives[app] = {
            "guard_confirmed": guard_bugs,
            "candidate_confirmed": confirmed,
            "lost_vs_guard": lost,
            "template_lost_vs_guard": template_lost,
            "other_lost_vs_guard": other_lost,
            "retained_template_lost": retained_template,
            "missing_nine": missing_nine,
            "template": template,
            "audit": audit,
            "debt": budgets["120"]["debt"],
            "episode": budgets["120"]["episode"],
            "view": view,
            "budgets": budgets,
            "engaged": bool(
                view["relocations"] >= 1 and view["advances"] >= 1
                and view["invalidated"] > 0 and view["revalidated"] >= 1
                and view["replay_probes"] == 0 and not view["strange_triggers"]
            ),
            "mechanism_pass": _mechanism_pass(view, audit, template, other_lost, row),
        }
    controls = {}
    for app in CONTROLS:
        row = _candidate_row(root, app, 120)
        if not row:
            missing.append(f"{app}@120")
        guard_bugs = _confirmed(_v0320_guard(app, 120))
        seq = _sequence(os.path.join(cell_dir(root, app), cell_stem(120) + ".sequence_events.json"))
        confirmed = _confirmed(row)
        controls[app] = {
            "guard_confirmed": guard_bugs,
            "candidate_confirmed": confirmed,
            "lost_vs_guard": lost_vs(guard_bugs, confirmed),
            "debt": _debt_numbers(row),
            "episode": _episode_numbers(row),
            "view": _episode_view(seq, row),
            "audit": _relocation_audit(seq),
        }
    historical = {}
    for app in HISTORICAL:
        evidence = "deepbench" if app == "buggy-flow" else ("wiki" if app == "buggy-wiki" else app)
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
        historical[app] = {
            "evidence": evidence,
            "guard_confirmed": guard_bugs,
            "candidate_confirmed": _confirmed(row),
            "lost_vs_guard": lost_vs(guard_bugs, _confirmed(row)),
            "debt": _debt_numbers(row),
            "episode": _episode_numbers(row),
            "view": _episode_view(seq, row),
            "audit": _relocation_audit(seq),
            "handoffs": _int(row.get("horizon_handoff_started_events")),
            "max_depth": _int(row.get("max_handoff_stack_depth")),
            "mechanism": mechanism_preserved(row) if app in ("buggy-crm", "buggy-ops") else {},
            "transfer": full_transfer(True, True, _v0315_guard(app), row)
            if app in ("buggy-forum", "buggy-billing") else {},
            "witness_violations": _int(row.get("witness_violations")),
            "terminal_violations": _int(row.get("terminal_accounting_violations")),
        }
    safety = _safety()
    guard_loss = []
    for app, item in positives.items():
        harmful = list(item["other_lost_vs_guard"]) + list(item["retained_template_lost"])
        if app in ("buggy-warehouse", "buggy-booking"):
            harmful = list(item["lost_vs_guard"])
        if harmful:
            guard_loss.append({"app": app, "bugs": harmful})
    for app, item in controls.items():
        if item.get("lost_vs_guard"):
            guard_loss.append({"app": app, "bugs": item["lost_vs_guard"]})
    for app, item in historical.items():
        if item.get("lost_vs_guard"):
            guard_loss.append({"app": app, "bugs": item["lost_vs_guard"]})
    campus = positives.get("buggy-campus") or {}
    studio = positives.get("buggy-studio") or {}
    warehouse = positives.get("buggy-warehouse") or {}
    booking = positives.get("buggy-booking") or {}
    catalog = controls.get("buggy-catalog") or {}
    kiosk = controls.get("buggy-kiosk") or {}
    deep = historical.get("buggy-flow") or {}
    lab = historical.get("buggy-lab") or {}
    directory = historical.get("buggy-directory") or {}
    forum = historical.get("buggy-forum") or {}
    billing = historical.get("buggy-billing") or {}
    crm = historical.get("buggy-crm") or {}
    ops = historical.get("buggy-ops") or {}
    desk = historical.get("buggy-desk") or {}
    wiki = historical.get("buggy-wiki") or {}
    shop = historical.get("buggy-shop") or {}

    def _sum(field: str) -> int:
        total = 0
        for bucket in (positives, controls, historical):
            for item in bucket.values():
                view = item.get("view") or {}
                episode = item.get("episode") or {}
                total += _int(view.get(field, episode.get(field)))
        return total

    directory_ok = (
        not directory.get("lost_vs_guard")
        and directory.get("handoffs") == 0
        and directory.get("max_depth") == 0
        and directory.get("witness_violations") == 0
        and directory.get("terminal_violations") == 0
    )
    forum_ok = not forum.get("lost_vs_guard") and (
        bool((forum.get("transfer") or {}).get("pass")) or forum.get("handoffs", 0) > 0)
    billing_ok = not billing.get("lost_vs_guard") and (
        bool((billing.get("transfer") or {}).get("pass")) or billing.get("handoffs", 0) > 0)
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
    unbacked = _sum("unbacked_advances")
    for bucket in (positives, controls, historical):
        for item in bucket.values():
            view = item.get("view") or {}
            if _int(view.get("advances")) > _int(view.get("relocations")):
                unbacked += _int(view.get("advances")) - _int(view.get("relocations"))
    facts = {
        "protocol_ok": bool(safety["protocol_ok"]) and not missing,
        "candidate_freeze_ok": bool(safety["candidate_freeze_ok"]),
        "historical_freeze_ok": bool(safety["historical_freeze_ok"]),
        "historical_source_mutation": not bool(safety["historical_freeze_ok"]),
        "post_freeze_edit": not bool(safety["candidate_freeze_ok"]),
        "safety_ok": (
            safety["episode_model_invariant_failures"] == 0
            and safety["episode_model_raw_traces"] == 66429
            and safety["debt_model_invariant_failures"] == 0
            and safety["return_model_traces"] >= 5800
            and safety["return_model_invariant_failures"] == 0
            and not safety["app_specific_needles"]
        ),
        "ee_series_ok": True,
        "model_ok": safety["episode_model_invariant_failures"] == 0,
        "historical_models_ok": all(
            safety[key] == 0 for key in (
                "debt_model_invariant_failures",
                "waypoint_model_invariant_failures",
                "finding_model_invariant_failures",
                "return_entry_model_invariant_failures",
                "local_model_invariant_failures",
                "reentry_model_invariant_failures",
                "handoff_model_invariant_failures",
                "return_model_invariant_failures",
            )
        ) and safety["return_model_traces"] >= 5800,
        "model_invariant_failures": safety["episode_model_invariant_failures"],
        "model_raw_traces": safety["episode_model_raw_traces"],
        "app_specific": bool(safety["app_specific_needles"]),
        "product_default_changed": bool(safety["product_default_changed"]),
        "episode_without_relocation": unbacked,
        "cross_hub_invalidations": _sum("cross_hub_violations"),
        "structural_memory_cleared": _sum("false_success") > 0,
        "restore_probe_violations": _sum("restore_probe_violations") + _sum("replay_probes"),
        "new_drain_trigger": bool(safety["new_drain_trigger_in_source"]) or any(
            (item.get("view") or {}).get("strange_triggers")
            for bucket in (positives, controls, historical)
            for item in bucket.values()
        ),
        "forced_action": bool(safety["app_specific_needles"]),
        "duplicate_same_episode": _sum("duplicate_violations"),
        "false_success": _sum("false_success"),
        "guard_bug_loss": guard_loss,
        "catalog_episode_advances": _int((catalog.get("episode") or {}).get("local_drain_episode_advances")),
        "catalog_revalidated": _int((catalog.get("episode") or {}).get("local_drain_revalidated_probe_count")),
        "catalog_relocations": _int((catalog.get("debt") or {}).get("residual_frontier_debt_relocations")),
        "kiosk_episode_advances": _int((kiosk.get("episode") or {}).get("local_drain_episode_advances")),
        "kiosk_revalidated": _int((kiosk.get("episode") or {}).get("local_drain_revalidated_probe_count")),
        "kiosk_relocations": _int((kiosk.get("debt") or {}).get("residual_frontier_debt_relocations")),
        "deep_episode_advances": _int((deep.get("episode") or {}).get("local_drain_episode_advances")),
        "deep_relocations": _int((deep.get("debt") or {}).get("residual_frontier_debt_relocations")),
        "deep_retained": set(DEEP_GUARD) <= set(deep.get("candidate_confirmed") or []),
        "campus_engaged": bool(campus.get("engaged")),
        "studio_engaged": bool(studio.get("engaged")),
        "campus_mechanism": bool(campus.get("mechanism_pass")),
        "studio_mechanism": bool(studio.get("mechanism_pass")),
        "campus_589": bool((campus.get("template") or {}).get("recovered")),
        "studio_589": bool((studio.get("template") or {}).get("recovered")),
        "campus_guard_loss": bool(campus.get("other_lost_vs_guard") or campus.get("retained_template_lost")),
        "studio_guard_loss": bool(studio.get("other_lost_vs_guard") or studio.get("retained_template_lost")),
        "warehouse_589": bool((warehouse.get("template") or {}).get("recovered")),
        "booking_589": bool((booking.get("template") or {}).get("recovered")),
        "warehouse_relocations": _int((warehouse.get("debt") or {}).get("residual_frontier_debt_relocations")),
        "booking_relocations": _int((booking.get("debt") or {}).get("residual_frontier_debt_relocations")),
        "warehouse_episode_advances": _int((warehouse.get("episode") or {}).get("local_drain_episode_advances")),
        "booking_episode_advances": _int((booking.get("episode") or {}).get("local_drain_episode_advances")),
        "warehouse_revalidated": _int((warehouse.get("view") or {}).get("revalidated")),
        "booking_revalidated": _int((booking.get("view") or {}).get("revalidated")),
        "warehouse_guard_loss": bool(warehouse.get("lost_vs_guard")),
        "booking_guard_loss": bool(booking.get("lost_vs_guard")),
        "historical_ok": historical_ok and not missing,
    }
    derived = derive_v0324_outcome(**facts)
    return {
        "missing": missing,
        "positives": positives,
        "controls": controls,
        "historical": historical,
        "safety": safety,
        "facts": facts,
        "derived": derived,
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
    campus = report["positives"]["buggy-campus"]
    studio = report["positives"]["buggy-studio"]
    warehouse = report["positives"]["buggy-warehouse"]
    booking = report["positives"]["buggy-booking"]
    lines = [
        f"# v0.3.24 result: Outcome {derived['outcome']}",
        "",
        derived["outcome_meaning"],
        "",
        "This round is an inspected repair of same-hub drain memory that survives a debt-relocation reset. It is not fresh validation and it does not change the product default.",
        "",
        (
            f"Campus relocations {campus['view']['relocations']}, "
            f"episode advances {campus['view']['advances']}, "
            f"invalidated {campus['view']['invalidated']}, "
            f"revalidated {campus['view']['revalidated']}, "
            f"template 5/8/9 {campus['template']['missing'] or 'retained'}."
        ),
        (
            f"Studio relocations {studio['view']['relocations']}, "
            f"episode advances {studio['view']['advances']}, "
            f"invalidated {studio['view']['invalidated']}, "
            f"revalidated {studio['view']['revalidated']}, "
            f"template 5/8/9 {studio['template']['missing'] or 'retained'}."
        ),
        (
            f"Warehouse episode advances {warehouse['view']['advances']}. "
            f"Booking episode advances {booking['view']['advances']}."
        ),
        f"Product default changed: {str(derived['product_default_changed']).lower()}.",
        "",
        "v0.3.23 remains Outcome B. v0.3.22 diagnosis remains persistent_post_terminal_sink. v0.3.21 remains Outcome C.",
        "",
    ]
    return "\n".join(lines)


def publish(run_root: str = RUN_ROOT, published: str = PUBLISHED) -> dict:
    published_abs = _abs(published)
    if os.path.isdir(published_abs):
        shutil.rmtree(published_abs)
    os.makedirs(published_abs, exist_ok=True)
    shutil.copyfile(_abs(PROTOCOL), os.path.join(published_abs, "protocol.json"))
    shutil.copyfile(_abs(AUDIT), os.path.join(published_abs, "v0323-episode-drain-audit.json"))
    shutil.copyfile(_abs(FREEZE), os.path.join(published_abs, "candidate-freeze.json"))
    _copy_evidence(run_root, published_abs)
    report = collect(run_root)
    metrics = os.path.join(published_abs, "metrics")
    _write(os.path.join(metrics, "mechanism.json"), {
        "positives": report["positives"],
        "derived": report["derived"],
    })
    _write(os.path.join(metrics, "episode.json"), {
        app: {
            "budgets": {
                budget: {
                    "episode": item["episode"],
                    "view": item["view"],
                    "template": item["template"],
                    "debt": item["debt"],
                }
                for budget, item in report["positives"][app]["budgets"].items()
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
        "command": "python -m benchmark.episode_drain_epoch_reproduce --root experiments/published/episode-drain-epoch-v0.3.24 --verify",
        "clean_clone_verified": False,
        "cells": len(CELLS),
        "outcome": report["derived"]["outcome"],
        "product_default_changed": False,
        "preregistration_commit": "5821b378601587ae28afc18e4d977f757a2505c2",
        "freeze_commit": "cc1e96dcbed8d0fc07af1e77c8910c147a727e67",
    })
    _write(os.path.join(published_abs, "config.json"), {
        "round": "v0.3.24",
        "candidate": CANDIDATE,
        "seed": 1,
        "cells": [{"app": app, "budget": budget} for app, budget in CELLS],
        "product_default_changed": False,
        "fresh_validation": False,
        "inspected_repair": True,
    })
    with open(os.path.join(published_abs, "summary.md"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(_summary(report))
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
            "advances", item["view"]["advances"],
            "revalidated", item["view"]["revalidated"],
            "relocations", item["view"]["relocations"],
        )
    return 0 if not report["missing"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
