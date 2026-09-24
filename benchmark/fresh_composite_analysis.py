"""Measurement and outcome gate for v0.3.20. Does not choose actions."""
from __future__ import annotations

import json
import os

from ghostqa.exploration.horizon_handoff_guard import terminal_violations

from benchmark.fresh_composite_qualify import qualify_path
from benchmark.fresh_composite_run import (
    APPS, CANDIDATE, CELLS, NEGATIVE, POLICY, POSITIVE, SEED, cell_dir, cell_stem,
)

OUTCOME_MEANING = {
    "A": "strong fresh composite transfer",
    "B": "safe mixed fresh transfer",
    "C": "fresh validation harmful, unsafe, or invalid",
    "D": "fresh suite insufficiently evaluable",
}


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _load_jsonl(path):
    rows = []
    if not os.path.isfile(path):
        return rows
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _row(metrics: dict, policy_name: str, budget: int) -> dict:
    for item in metrics.get("runs") or []:
        if item.get("policy") == policy_name and _int(item.get("budget")) == budget:
            return item
    return {}


def _events(run_root: str, app: str, policy_name: str, budget: int) -> list:
    path = os.path.join(
        cell_dir(run_root, app), cell_stem(policy_name, budget) + ".sequence_events.json")
    if not os.path.isfile(path):
        return []
    return _load_json(path)


def _trace(run_root: str, app: str, policy_name: str, budget: int) -> list:
    path = os.path.join(
        cell_dir(run_root, app), cell_stem(policy_name, budget) + ".events.jsonl")
    return _load_jsonl(path)


def product_default_changed() -> bool:
    import inspect
    from ghostqa.exploration.policy import GhostPolicy
    signature = inspect.signature(GhostPolicy.__init__)
    frontier = signature.parameters["use_frontier"].default
    mode = signature.parameters["sequence_mode"].default
    text = open(os.path.join("ghostqa", "__main__.py"), encoding="utf-8").read()
    cli_default = 'default="ghost"' in text or "default='ghost'" in text
    return not (frontier is False and mode == "off" and cli_default)


def _by_step(events: list) -> dict:
    grouped = {}
    for event in events:
        grouped.setdefault(_int(event.get("step")), []).append(event)
    return grouped


def trigger_audit(events: list) -> dict:
    grouped = _by_step(events)
    triggers = [event for event in events if event.get("event") == "finding_return_entry_trigger"]
    drains = [event for event in events if event.get("event") == "return_entry_drain_started"]
    mismatch = 0
    reused = 0
    wrong = 0
    seen = set()
    for trigger in triggers:
        step = _int(trigger.get("step"))
        branch = trigger.get("branch_key") or ""
        terminals = [
            event for event in grouped.get(step, [])
            if event.get("event") == "sequence_terminal"
            and event.get("outcome") == "finding"
            and (event.get("branch_key") or "") == branch
        ]
        if len(terminals) != 1 or trigger.get("terminal_outcome") not in (None, "finding"):
            mismatch += 1
        if trigger.get("terminal_outcome") not in (None, "", "finding"):
            wrong += 1
        key = (
            trigger.get("sequence_instance_id") or "",
            trigger.get("terminal_event_index"),
        )
        if key in seen:
            reused += 1
        seen.add(key)
        same = [
            event for event in drains
            if _int(event.get("step")) == step and (event.get("branch_key") or "") == branch
        ]
        if len(same) != 1:
            mismatch += 1
    for drain in drains:
        step = _int(drain.get("step"))
        branch = drain.get("branch_key") or ""
        same = [
            event for event in triggers
            if _int(event.get("step")) == step and (event.get("branch_key") or "") == branch
        ]
        if len(same) != 1:
            mismatch += 1
    if len(triggers) != len(drains):
        mismatch += abs(len(triggers) - len(drains))
    return {
        "trigger_mismatch_violations": mismatch,
        "reused_trigger_violations": reused,
        "wrong_instance_violations": wrong,
        "triggers": len(triggers),
        "drains": len(drains),
    }


def horizon_only_drain_count(events: list) -> int:
    count = 0
    for step, items in _by_step(events).items():
        del step
        horizons = [event for event in items if event.get("event") == "sequence_horizon_reached"]
        findings = [
            event for event in items
            if event.get("event") == "sequence_terminal" and event.get("outcome") == "finding"
        ]
        drains = [event for event in items if event.get("event") == "return_entry_drain_started"]
        if horizons and not findings and drains:
            count += len(drains)
    return count


def trace_opportunities(trace_rows: list) -> list:
    snaps = {
        _int(row.get("step")): row
        for row in trace_rows
        if row.get("kind") == "seq_after"
    }
    found = []
    for row in trace_rows:
        if row.get("kind") != "step":
            continue
        step = _int(row.get("index"))
        snap = snaps.get(step) or {}
        action = row.get("action") or {}
        if action.get("type") != "click":
            continue
        if not snap.get("is_hub"):
            continue
        if not row.get("active_branch"):
            continue
        if row.get("returning"):
            continue
        commitment = _int(row.get("commitment_left"))
        if commitment > 1:
            kind = "continuation"
        elif commitment == 1:
            kind = "handoff"
        else:
            continue
        found.append({
            "step": step,
            "kind": kind,
            "commitment_before": commitment,
            "src_url": row.get("src_url") or "",
            "action": action.get("target_eid") or "",
        })
    return found


def match_handoffs(events: list, trace_rows: list) -> dict:
    opps = trace_opportunities(trace_rows)
    by_step = {}
    for opp in opps:
        by_step.setdefault((opp["step"], opp["kind"]), []).append(opp)
    used = set()
    failures = []

    def take(step, kind):
        pool = by_step.get((step, kind)) or []
        for index, opp in enumerate(pool):
            key = (step, kind, index)
            if key in used:
                continue
            used.add(key)
            return opp
        return None

    stack = []
    witness_steps = set()
    names = {
        "nested_continuation", "horizon_handoff_started", "child_parent_witness",
        "parent_frame_resume_to_return", "horizon_handoff_unwind", "witness_rejection",
    }
    for event in events:
        name = event.get("event")
        if name not in names:
            continue
        step = _int(event.get("step"))
        if name == "nested_continuation":
            if take(step, "continuation") is None:
                failures.append(f"unmatched nested_continuation step {step}")
        elif name == "horizon_handoff_started":
            if take(step, "handoff") is None:
                failures.append(f"unmatched horizon_handoff_started step {step}")
            else:
                stack.append(event.get("child_sequence_instance_id") or "")
        elif name == "child_parent_witness":
            child = event.get("child_sequence_instance_id") or ""
            if not stack or (stack[-1] and child and stack[-1] != child):
                failures.append(f"witness without matching frame step {step}")
            else:
                stack.pop()
                witness_steps.add(step)
        elif name == "parent_frame_resume_to_return":
            if step not in witness_steps:
                failures.append(f"resume without witness step {step}")
        elif name == "horizon_handoff_unwind":
            escaped = any(
                item.get("event") == "return_cycle_escape" and _int(item.get("step")) == step
                for item in events
            )
            if not escaped:
                failures.append(f"unwind without escape step {step}")
            stack.clear()
        elif name == "witness_rejection":
            if not stack:
                failures.append(f"rejection without frame step {step}")
    return {
        "ok": not failures,
        "failures": failures,
        "handoff_opportunities": sum(1 for item in opps if item["kind"] == "handoff"),
        "continuation_opportunities": sum(1 for item in opps if item["kind"] == "continuation"),
    }


def _page(url: str) -> str:
    path = url or ""
    if "://" in path:
        path = path.split("://", 1)[1]
        path = path.split("/", 1)[1] if "/" in path else ""
        path = "/" + path
    return path.split("?", 1)[0].split("#", 1)[0]


def _returning_flip(trace_rows: list, step: int) -> bool:
    before = None
    after = None
    for row in trace_rows:
        if row.get("kind") == "step" and _int(row.get("index")) == step:
            before = bool(row.get("returning"))
        if row.get("kind") == "seq_after" and _int(row.get("step")) == step:
            after = bool(row.get("returning"))
    return before is False and after is True


def finding_trace_hit(events: list, trace_rows: list, pages: set) -> bool:
    for event in events:
        if event.get("event") != "sequence_terminal" or event.get("outcome") != "finding":
            continue
        step = _int(event.get("step"))
        if not _returning_flip(trace_rows, step):
            continue
        for row in trace_rows:
            if row.get("kind") == "step" and _int(row.get("index")) == step:
                if _page(row.get("dst_url") or "") in pages:
                    return True
    return False


def horizon_trace_hit(events: list, trace_rows: list, pages: set) -> bool:
    for event in events:
        if event.get("event") != "sequence_horizon_reached":
            continue
        step = _int(event.get("step"))
        same = _by_step(events).get(step) or []
        if any(item.get("event") == "sequence_terminal" and item.get("outcome") == "finding" for item in same):
            continue
        if not _returning_flip(trace_rows, step):
            continue
        for row in trace_rows:
            if row.get("kind") == "step" and _int(row.get("index")) == step:
                if _page(row.get("dst_url") or "") in pages:
                    return True
    return False


def _confirmed(row: dict) -> set:
    return set(row.get("confirmed_bugs") or [])


def _target_view(run_root: str, app: str, budget: int, qualification: dict) -> dict:
    metrics = {}
    path = os.path.join(cell_dir(run_root, app), "metrics.json")
    if os.path.isfile(path):
        metrics = _load_json(path)
    cells = {}
    audits = {}
    for code, policy_name in POLICY.items():
        row = _row(metrics, policy_name, budget)
        events = _events(run_root, app, policy_name, budget)
        trace = _trace(run_root, app, policy_name, budget)
        handoff = match_handoffs(events, trace)
        triggers = trigger_audit(events)
        cells[code] = row
        audits[code] = {
            "handoff_match": handoff,
            "trigger_audit": triggers,
            "horizon_only_drains": horizon_only_drain_count(events),
            "terminal_violations": len(terminal_violations(events)) if events else 0,
            "witness_violations": _int(row.get("witness_violations")),
            "accounting_violations": _int(row.get("return_entry_accounting_violations")),
        }
    finding_pages = set()
    horizon_pages = set()
    chain_pages = set()
    nodes = {
        node["id"]: node
        for node in _load_json(os.path.join(APPS[app]["dir"], "topology.json")).get("nodes") or []
    }
    for item in qualification.get("finding_return_opportunities") or []:
        node = nodes.get(item.get("destination_node") or "") or {}
        if node.get("page"):
            finding_pages.add("/" + node["page"])
    for item in qualification.get("horizon_only_controls") or []:
        node = nodes.get(item.get("destination_node") or "") or {}
        if node.get("page"):
            horizon_pages.add("/" + node["page"])
    for chain in qualification.get("qualifying_chains") or []:
        for node_id in chain.get("nodes") or []:
            node = nodes.get(node_id) or {}
            if node.get("page"):
                chain_pages.add("/" + node["page"])
    f_events = _events(run_root, app, POLICY["F"], budget)
    f_trace = _trace(run_root, app, POLICY["F"], budget)
    g_events = _events(run_root, app, POLICY["G"], budget)
    g_trace = _trace(run_root, app, POLICY["G"], budget)
    f_row = cells["F"]
    g_row = cells["G"]
    f_match = audits["F"]["handoff_match"]
    handoffs = _int(f_row.get("horizon_handoff_started_events"))
    witnesses = _int(f_row.get("child_parent_witness_events"))
    unwinds = _int(f_row.get("horizon_handoff_unwind_events"))
    triggers_n = _int(f_row.get("finding_return_entry_trigger_events"))
    drains_n = _int(f_row.get("return_entry_drain_started_events"))
    horizon_reached = horizon_trace_hit(f_events, f_trace, horizon_pages)
    finding_hit = (
        triggers_n >= 1 and audits["F"]["trigger_audit"]["trigger_mismatch_violations"] == 0
    ) or finding_trace_hit(f_events, f_trace, finding_pages)
    nested_hit = (
        (handoffs >= 1 and f_match["ok"] and f_match["handoff_opportunities"] >= 1)
        or f_match["handoff_opportunities"] >= 1
        or match_handoffs(g_events, g_trace)["handoff_opportunities"] >= 1
        or _lost_on_pages(g_events, g_trace, chain_pages) > 0
    )
    lost = sorted(_confirmed(g_row) - _confirmed(f_row))
    violations = (
        audits["F"]["witness_violations"]
        + audits["F"]["terminal_violations"]
        + audits["F"]["trigger_audit"]["trigger_mismatch_violations"]
        + audits["F"]["trigger_audit"]["reused_trigger_violations"]
        + audits["F"]["trigger_audit"]["wrong_instance_violations"]
        + audits["F"]["accounting_violations"]
        + audits["F"]["horizon_only_drains"]
    )
    resolved = witnesses >= 1 or unwinds >= 1
    states_f = _int(f_row.get("states"))
    states_g = _int(g_row.get("states"))
    urls_f = _int(f_row.get("normalized_unique_urls"))
    urls_g = _int(g_row.get("normalized_unique_urls"))
    horizon_n = _int(f_row.get("horizon_events") or f_row.get("sequence_horizon_reached"))
    if not horizon_n:
        horizon_n = sum(1 for event in f_events if event.get("event") == "sequence_horizon_reached")
    returned = _int(f_row.get("sequence_instances_returned"))
    escapes = _int(f_row.get("return_cycle_escape_events"))
    runaway = bool(
        handoffs > 0 and witnesses == 0 and unwinds == 0
        and horizon_n == 0 and returned == 0 and escapes == 0
    )
    lifecycle = horizon_n > 0 or returned > 0 or escapes > 0
    expansion = states_f > states_g or urls_f > urls_g
    horizon_drains = audits["F"]["horizon_only_drains"]
    nested_transfer = bool(
        qualification.get("qualified") and handoffs >= 1 and resolved and audits["F"]["handoff_match"]["ok"]
        and audits["F"]["witness_violations"] == 0 and audits["F"]["terminal_violations"] == 0
    )
    finding_transfer = bool(
        triggers_n >= 1 and drains_n >= 1
        and audits["F"]["trigger_audit"]["trigger_mismatch_violations"] == 0
        and audits["F"]["trigger_audit"]["reused_trigger_violations"] == 0
        and audits["F"]["trigger_audit"]["wrong_instance_violations"] == 0
        and (horizon_drains == 0 if horizon_reached else True)
    )
    full = bool(
        qualification.get("qualified")
        and nested_hit and finding_hit
        and nested_transfer and finding_transfer
        and not lost and expansion and not runaway and lifecycle and violations == 0
    )
    return {
        "cells": {code: _slim(cells[code]) for code in cells},
        "audits": {
            code: {
                "horizon_only_drains": audits[code]["horizon_only_drains"],
                "terminal_violations": audits[code]["terminal_violations"],
                "witness_violations": audits[code]["witness_violations"],
                "accounting_violations": audits[code]["accounting_violations"],
                "trigger_audit": audits[code]["trigger_audit"],
                "handoff_ok": audits[code]["handoff_match"]["ok"],
                "handoff_opportunities": audits[code]["handoff_match"]["handoff_opportunities"],
                "handoff_failures": audits[code]["handoff_match"]["failures"],
            }
            for code in audits
        },
        "nested_evaluable": bool(nested_hit),
        "finding_evaluable": bool(finding_hit),
        "horizon_control_reached": bool(horizon_reached),
        "composite_evaluable": bool(nested_hit and finding_hit),
        "nested_transfer": nested_transfer,
        "finding_drain_transfer": finding_transfer,
        "full_transfer": full,
        "lost_vs_guard": lost,
        "expansion": expansion,
        "runaway": runaway,
        "lifecycle": lifecycle,
    }


def _lost_on_pages(events, trace_rows, pages: set) -> int:
    steps = {
        _int(row.get("index")): row
        for row in trace_rows if row.get("kind") == "step"
    }
    count = 0
    for event in events:
        if event.get("event") != "sequence_terminal" or event.get("outcome") != "lost_parent":
            continue
        row = steps.get(_int(event.get("step"))) or {}
        if _page(row.get("src_url") or "") in pages:
            count += 1
    return count


def _slim(row: dict) -> dict:
    keys = (
        "states", "clusters", "variants", "normalized_unique_urls", "confirmed_bugs",
        "bug_discovery_rate", "deep_bug_discovery_rate", "discovery_auc",
        "branch_start_events", "sequence_lost_parent", "sequence_instances_returned",
        "return_attempt_events", "return_cycle_escape_events",
        "nested_continuation_events", "horizon_handoff_started_events",
        "child_parent_witness_events", "horizon_handoff_unwind_events",
        "max_handoff_stack_depth", "local_action_drain_started_events",
        "finding_return_entry_trigger_events", "return_entry_drain_started_events",
        "finding_return_entry_horizon_bypass_events",
        "finding_return_entry_trigger_mismatch_violations",
        "finding_return_entry_reused_trigger_violations",
        "finding_return_entry_wrong_instance_violations",
        "witness_violations", "terminal_accounting_violations",
        "return_entry_accounting_violations",
    )
    out = {key: row.get(key) for key in keys}
    out["confirmed_bugs"] = list(row.get("confirmed_bugs") or [])
    return out


def collect(run_root: str) -> dict:
    targets = {}
    for app in (*POSITIVE, *NEGATIVE):
        qual = qualify_path(os.path.join(APPS[app]["dir"], "topology.json"))
        targets[app] = {
            "qualification": {
                "qualified": qual["qualified"],
                "class": qual["class"],
                "nested_handoff_opportunity_count": qual["nested_handoff_opportunity_count"],
                "finding_return_entry_opportunity_count": qual["finding_return_entry_opportunity_count"],
                "horizon_only_return_entry_control_count": qual["horizon_only_return_entry_control_count"],
                "max_nested_branch_depth": qual["max_nested_branch_depth"],
            },
            "at_120": _target_view(run_root, app, 120, qual),
        }
        if app in POSITIVE:
            targets[app]["budgets"] = {}
            for budget in (40, 80, 120):
                targets[app]["budgets"][str(budget)] = {
                    code: _slim(_row(
                        _load_json(os.path.join(cell_dir(run_root, app), "metrics.json"))
                        if os.path.isfile(os.path.join(cell_dir(run_root, app), "metrics.json"))
                        else {"runs": []},
                        POLICY[code], budget,
                    ))
                    for code in POLICY
                }
    return {"targets": targets, "cells_expected": len(CELLS)}


def _sum_audit(targets: dict, key: str) -> int:
    total = 0
    for app in targets.values():
        audit = ((app.get("at_120") or {}).get("audits") or {}).get("F") or {}
        if key == "trigger":
            trig = audit.get("trigger_audit") or {}
            total += _int(trig.get("trigger_mismatch_violations"))
            total += _int(trig.get("reused_trigger_violations"))
            total += _int(trig.get("wrong_instance_violations"))
        else:
            total += _int(audit.get(key))
    return total


def derive_v0320_outcome(report: dict) -> dict:
    """C, then D, then B, else A. Mechanical."""
    targets = report.get("targets") or {}
    positives = [targets[name] for name in POSITIVE if name in targets]
    catalog = (targets.get("buggy-catalog") or {}).get("at_120") or {}
    kiosk = (targets.get("buggy-kiosk") or {}).get("at_120") or {}
    catalog_f = ((catalog.get("cells") or {}).get("F") or {})
    kiosk_f = ((kiosk.get("cells") or {}).get("F") or {})
    catalog_events = (
        _int(catalog_f.get("horizon_handoff_started_events"))
        + _int(catalog_f.get("finding_return_entry_trigger_events"))
        + _int(catalog_f.get("return_entry_drain_started_events"))
        + _int(catalog_f.get("max_handoff_stack_depth"))
    )
    losses = []
    for name, target in targets.items():
        lost = (target.get("at_120") or {}).get("lost_vs_guard") or []
        if lost:
            losses.append({"app": name, "bugs": list(lost)})
    horizon_drains = _sum_audit(targets, "horizon_only_drains")
    witness = _sum_audit(targets, "witness_violations")
    terminal = _sum_audit(targets, "terminal_violations")
    accounting = _sum_audit(targets, "accounting_violations")
    trigger = _sum_audit(targets, "trigger")
    composite = sum(1 for item in positives if (item.get("at_120") or {}).get("composite_evaluable"))
    nested = sum(1 for item in positives if (item.get("at_120") or {}).get("nested_transfer"))
    finding = sum(1 for item in positives if (item.get("at_120") or {}).get("finding_drain_transfer"))
    full = sum(1 for item in positives if (item.get("at_120") or {}).get("full_transfer"))
    kiosk_eval = bool(kiosk.get("finding_evaluable"))
    kiosk_handoff = _int(kiosk_f.get("horizon_handoff_started_events")) + _int(kiosk_f.get("max_handoff_stack_depth"))
    flags = report.get("flags") or {}
    reasons = []
    if flags.get("candidate_freeze_ok") is False:
        reasons.append("candidate freeze mismatch")
    if flags.get("suite_freeze_ok") is False:
        reasons.append("suite freeze mismatch")
    if flags.get("protocol_ok") is False:
        reasons.append("protocol identity mismatch")
    if flags.get("source_isolation_ok") is False:
        reasons.append("source isolation failure")
    if flags.get("judge_leak") is True:
        reasons.append("judge leakage")
    if flags.get("historical_safety_ok") is False:
        reasons.append("historical safety failure")
    if flags.get("post_freeze_tuning") is True:
        reasons.append("post-freeze tuning")
    if flags.get("app_specific_logic") is True:
        reasons.append("app-specific candidate logic")
    if flags.get("product_default_changed") is True or report.get("product_default_changed") is True:
        reasons.append("product default changed")
    if flags.get("clean_clone_mismatch") is True:
        reasons.append("clean-clone freeze mismatch")
    if losses:
        reasons.append("guard-confirmed bug loss")
    if horizon_drains:
        reasons.append("horizon-only return-entry drain")
    if trigger or witness or terminal or accounting:
        reasons.append("trigger, witness, terminal, or accounting violation")
    if kiosk_handoff:
        reasons.append("kiosk nested handoff")
    if catalog_events:
        reasons.append("catalog candidate-specific event")
    if (kiosk.get("audits") or {}).get("F", {}).get("horizon_only_drains"):
        reasons.append("kiosk horizon-only drain")
    kiosk_trigger = ((kiosk.get("audits") or {}).get("F") or {}).get("trigger_audit") or {}
    if any(_int(kiosk_trigger.get(key)) for key in (
        "trigger_mismatch_violations", "reused_trigger_violations", "wrong_instance_violations",
    )):
        reasons.append("kiosk trigger provenance violation")
    static_bad = any(
        not ((target.get("qualification") or {}).get("qualified"))
        for target in targets.values()
    )
    if static_bad:
        reasons.append("static qualification invalid")
    if reasons:
        outcome = "C"
    elif composite < 3 or not kiosk_eval:
        outcome = "D"
    elif full < 3 or nested < 3 or finding < 3:
        outcome = "B"
    else:
        outcome = "A"
    readiness = (
        "evidence_supports_productization_study" if outcome == "A" else "not_ready"
    )
    return {
        "outcome": outcome,
        "outcome_meaning": OUTCOME_MEANING[outcome],
        "reasons": reasons,
        "promotion_readiness": readiness,
        "product_default_changed": bool(
            flags.get("product_default_changed") or report.get("product_default_changed")),
        "generalization_claim": False,
        "composite_evaluable_positive_targets": composite,
        "nested_transfer_positive_targets": nested,
        "finding_drain_positive_targets": finding,
        "full_transfer_positive_targets": full,
        "guard_bug_losses": losses,
        "horizon_only_drain_count": horizon_drains,
        "catalog_candidate_event_count": catalog_events,
        "kiosk_nested_handoff_count": kiosk_handoff,
        "kiosk_finding_control_evaluable": kiosk_eval,
        "trigger_violations": trigger,
        "witness_violations": witness,
        "terminal_violations": terminal,
        "accounting_violations": accounting,
    }
