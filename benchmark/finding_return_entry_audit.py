"""Code-derived v0.3.18 trigger-context audit for the v0.3.19 repair round.

Reads committed return-entry, local-action, guard, and fresh-handoff evidence.
Does not run a browser and does not choose exploration actions.
"""
from __future__ import annotations

import os

from benchmark.algorithm_freeze import sha256_file
from benchmark.application_shape_evidence import (
    canonical_json_bytes, load_json, load_jsonl, sha256_bytes, steps_only,
)
from benchmark.fresh_handoff_analysis import full_transfer
from benchmark.fresh_transfer_analysis import normalize_url
from benchmark.horizon_handoff_analysis import GUARD_CONFIRMED
from benchmark.local_action_drain_analysis import directory_preserved
from benchmark.reentry_frontier_analysis import mechanism_preserved

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CURRENT = os.path.join("experiments", "published", "return-entry-drain-v0.3.18")
PREVIOUS = os.path.join("experiments", "published", "local-action-drain-v0.3.17")
GUARD_PUB = os.path.join("experiments", "published", "return-cycle-guard-v0.3.9")
FRESH = os.path.join("experiments", "published", "fresh-handoff-v0.3.15")
CURRENT_POLICY = "ghost-structural-return-entry-drain-guard"
PREVIOUS_POLICY = "ghost-structural-local-action-drain-guard"
GUARD_POLICY = "ghost-structural-return-guard"
DEEP_GUARD = ["BUG-D6", "BUG-D7", "BUG-D11", "BUG-D12", "BUG-D13", "BUG-D14"]
LAB_GUARD = ["BUG-L1", "BUG-L2", "BUG-L8", "BUG-L9", "BUG-L10"]
APPS = (
    ("buggy-billing", "buggy-billing"),
    ("buggy-crm", "buggy-crm"),
    ("buggy-desk", "buggy-desk"),
    ("buggy-directory", "buggy-directory"),
    ("buggy-forum", "buggy-forum"),
    ("buggy-lab", "buggy-lab"),
    ("buggy-ops", "buggy-ops"),
    ("buggy-shop", "buggy-shop"),
    ("deepbench", "deepbench"),
    ("wiki", "wiki"),
)
FREEZES = {
    "v0.3.9": "experiments/frozen/ghost-return-cycle-guard-v0.3.9/freeze.json",
    "v0.3.14": "experiments/frozen/ghost-horizon-handoff-v0.3.14/freeze.json",
    "v0.3.15": "experiments/frozen/v0.3.15-fresh-handoff-suite/freeze.json",
    "v0.3.16": "experiments/frozen/ghost-reentry-frontier-v0.3.16/freeze.json",
    "v0.3.17": "experiments/frozen/ghost-local-action-drain-v0.3.17/freeze.json",
    "v0.3.18": "experiments/frozen/ghost-return-entry-drain-v0.3.18/freeze.json",
}


def _abs(rel: str) -> str:
    return os.path.join(ROOT, rel.replace("/", os.sep))


def _stem(policy: str, budget: int = 120, seed: int = 1) -> str:
    return f"{policy}_b{budget}_s{seed}"


def _seq_path(root: str, folder: str, policy: str, budget: int = 120) -> str:
    return os.path.join(root, "evidence", folder, _stem(policy, budget) + ".sequence_events.json")


def _events_path(root: str, folder: str, policy: str, budget: int = 120) -> str:
    return os.path.join(root, "evidence", folder, _stem(policy, budget) + ".events.jsonl")


def _metrics_path(root: str, folder: str) -> str:
    return os.path.join(root, "evidence", folder, "metrics.json")


def _row(root: str, folder: str, policy: str, budget: int = 120) -> dict:
    metrics = load_json(_abs(_metrics_path(root, folder)))
    for row in metrics.get("runs") or []:
        if row.get("policy") == policy and int(row.get("budget") or 0) == budget:
            return row
    return {}


def _load_seq(root: str, folder: str, policy: str) -> list:
    return load_json(_abs(_seq_path(root, folder, policy)))


def _load_steps(root: str, folder: str, policy: str) -> list:
    return steps_only(load_jsonl(_abs(_events_path(root, folder, policy))))


def _browser(steps: list, index: int) -> dict:
    for step in steps:
        if step.get("index") != index:
            continue
        action = step.get("action") or {}
        findings = step.get("findings") or []
        return {
            "index": index,
            "target_eid": action.get("target_eid") or "",
            "type": action.get("type") or "",
            "src_url": normalize_url(step.get("src_url") or ""),
            "dst_url": normalize_url(step.get("dst_url") or ""),
            "src_cluster": step.get("src_cluster") or "",
            "dst_cluster": step.get("dst_cluster") or "",
            "finding_kinds": sorted({
                item.get("kind") for item in findings if item.get("kind")
            }),
            "finding_assert_ids": sorted({
                item.get("assert_id") for item in findings if item.get("assert_id")
            }),
        }
    return {"index": index}


def _names_at(seq: list, step: int) -> list:
    return sorted({
        event.get("event") or ""
        for event in seq
        if event.get("step") == step and event.get("event")
    })


def _classify_start(seq: list, start: dict) -> dict:
    step = start.get("step")
    same = [event for event in seq if event.get("step") == step]
    terminals = [
        event for event in same if event.get("event") == "sequence_terminal"
    ]
    outcomes = [event.get("outcome") or "" for event in terminals]
    horizon = any(event.get("event") == "sequence_horizon_reached" for event in same)
    if any(outcome == "finding" for outcome in outcomes):
        kind = "finding"
    elif horizon:
        kind = "horizon"
    elif any(outcome == "crash" for outcome in outcomes):
        kind = "crash"
    else:
        kind = "other"
    return {
        "step": step,
        "kind": kind,
        "terminal_outcomes": outcomes,
        "horizon_reached": horizon,
        "same_step_events": _names_at(seq, step),
        "branch": start.get("active_branch") or start.get("branch_key") or "",
        "hub_cluster": start.get("hub_cluster") or start.get("cluster_id") or "",
        "parent_hub_cluster": start.get("parent_hub_cluster") or "",
        "visible_eligible_keys": list(start.get("visible_eligible_keys") or []),
        "return_attempts": start.get("return_attempts"),
        "return_success": start.get("return_success"),
        "sequence_instance_id": start.get("sequence_instance_id"),
    }


def _census(seq: list) -> dict:
    rows = [
        _classify_start(seq, event)
        for event in seq
        if event.get("event") == "return_entry_drain_started"
    ]
    counts = {"finding": 0, "horizon": 0, "crash": 0, "other": 0}
    for row in rows:
        counts[row["kind"]] = counts.get(row["kind"], 0) + 1
    return {
        "return_entry_drain_started": len(rows),
        "finding_terminal_triggers": counts["finding"],
        "horizon_triggers": counts["horizon"],
        "crash_triggers": counts["crash"],
        "other_triggers": counts["other"],
        "triggers": rows,
    }


def _eid(key: str) -> str:
    text = str(key or "")
    marker = ":button:"
    if marker in text:
        return text.split(marker, 1)[1]
    return text


def _probe_rows(seq: list, steps: list, start_step: int, end_step: int) -> list:
    selected = [
        event for event in seq
        if event.get("event") == "return_entry_probe_selected"
        and isinstance(event.get("step"), int)
        and start_step < event["step"] < end_step
    ]
    finding_steps = {
        event.get("step")
        for event in seq
        if event.get("event") == "return_entry_probe_finding"
    }
    left_steps = {
        event.get("step")
        for event in seq
        if event.get("event") == "return_entry_probe_left_hub"
    }
    rows = []
    for event in selected:
        step = event.get("step")
        browser = _browser(steps, step)
        rows.append({
            "step": step,
            "eid": event.get("eid") or _eid(event.get("key") or ""),
            "same_hub": event.get("event") != "return_entry_probe_left_hub" and step not in left_steps,
            "left_hub": step in left_steps,
            "probe_finding": step in finding_steps,
            "return_attempts": event.get("return_attempts"),
            "browser": browser,
        })
    return rows


def _epoch_end(starts: list, index: int) -> int:
    later = [
        event.get("step")
        for event in starts[index + 1:]
        if isinstance(event.get("step"), int)
    ]
    return min(later) if later else 10 ** 9


def _finding_then_next(seq: list, steps: list) -> list:
    starts = [event for event in seq if event.get("event") == "return_entry_drain_started"]
    found = []
    for index, start in enumerate(starts):
        start_step = start.get("step")
        if not isinstance(start_step, int):
            continue
        end = _epoch_end(starts, index)
        probes = _probe_rows(seq, steps, start_step, end)
        for cursor, probe in enumerate(probes[:-1]):
            browser = probe.get("browser") or {}
            has_finding = bool(probe.get("probe_finding")) or bool(
                browser.get("finding_kinds") or browser.get("finding_assert_ids"))
            if not has_finding:
                continue
            nxt = probes[cursor + 1]
            found.append({
                "drain_start_step": start_step,
                "trigger_kind": _classify_start(seq, start)["kind"],
                "probe_step": probe.get("step"),
                "probe_eid": probe.get("eid"),
                "probe_finding_kinds": list(browser.get("finding_kinds") or []),
                "probe_assert_ids": list(browser.get("finding_assert_ids") or []),
                "next_probe_step": nxt.get("step"),
                "next_probe_eid": nxt.get("eid"),
                "next_assert_ids": list((nxt.get("browser") or {}).get("finding_assert_ids") or []),
            })
    return found


def _slim_row(row: dict) -> dict:
    keys = (
        "states", "normalized_unique_urls", "confirmed_bugs", "return_success",
        "return_attempts", "return_cycle_escape_events",
        "horizon_handoff_started_events", "max_handoff_stack_depth",
        "witness_violations", "terminal_accounting_violations",
        "sequence_horizon_reached", "sequence_instances_returned",
        "sequence_lost_parent", "early_parent_reentry_events",
        "child_parent_witness_events",
    )
    slim = {key: row.get(key) for key in keys}
    slim["confirmed_bugs"] = sorted(row.get("confirmed_bugs") or [])
    return slim


def _evaluable() -> dict:
    per = load_json(_abs(os.path.join(FRESH, "metrics", "per-target.json")))
    out = {}
    for app, block in (per.get("targets") or {}).items():
        out[app] = bool((block.get("evaluable") or {}).get("actual_evaluable"))
    return out


def _transfer(app: str, candidate_root: str, candidate_policy: str) -> dict:
    guard = _row(FRESH, app, GUARD_POLICY)
    candidate = _row(candidate_root, app, candidate_policy)
    evaluable = _evaluable().get(app, False)
    report = full_transfer(True, evaluable, guard, candidate)
    return {
        "evaluable": evaluable,
        "full_transfer": bool(report.get("pass")),
        "lost_vs_guard": list(report.get("lost_vs_guard") or []),
        "guard_confirmed": sorted(guard.get("confirmed_bugs") or []),
        "candidate_confirmed": sorted(candidate.get("confirmed_bugs") or []),
    }


def _preservation() -> dict:
    deep_prev = _row(PREVIOUS, "deepbench", PREVIOUS_POLICY)
    deep_guard = _row(GUARD_PUB, "deepbench", GUARD_POLICY)
    directory = _row(PREVIOUS, "buggy-directory", PREVIOUS_POLICY)
    wiki = _row(PREVIOUS, "wiki", PREVIOUS_POLICY)
    desk = _row(PREVIOUS, "buggy-desk", PREVIOUS_POLICY)
    shop = _row(PREVIOUS, "buggy-shop", PREVIOUS_POLICY)
    crm = _row(PREVIOUS, "buggy-crm", PREVIOUS_POLICY)
    ops = _row(PREVIOUS, "buggy-ops", PREVIOUS_POLICY)
    directory_guard = _row(FRESH, "buggy-directory", GUARD_POLICY)
    return {
        "note": (
            "Committed v0.3.17 rows already preserved these inspected sets "
            "without Return-Entry Drain. This is historical support for a "
            "horizon fallback, not a guarantee."
        ),
        "deepbench": {
            **_slim_row(deep_prev),
            "guard_confirmed": list(DEEP_GUARD),
            "lost_vs_guard": sorted(set(DEEP_GUARD) - set(deep_prev.get("confirmed_bugs") or [])),
            "guard_states": deep_guard.get("states"),
            "guard_urls_recorded": deep_guard.get("normalized_unique_urls"),
        },
        "wiki": {
            "confirmed_bugs": sorted(wiki.get("confirmed_bugs") or []),
            "contains_w2": "BUG-W2" in set(wiki.get("confirmed_bugs") or []),
        },
        "buggy-desk": {
            "confirmed_bugs": sorted(desk.get("confirmed_bugs") or []),
            "lost_vs_guard": sorted(
                set(GUARD_CONFIRMED["buggy-desk"]) - set(desk.get("confirmed_bugs") or [])),
        },
        "buggy-shop": {
            "confirmed_bugs": sorted(shop.get("confirmed_bugs") or []),
            "lost_vs_guard": sorted(
                set(GUARD_CONFIRMED["buggy-shop"]) - set(shop.get("confirmed_bugs") or [])),
        },
        "buggy-directory": {
            "horizon_handoff_started_events": directory.get("horizon_handoff_started_events"),
            "max_handoff_stack_depth": directory.get("max_handoff_stack_depth"),
            "preserved": directory_preserved(
                directory,
                sorted(directory_guard.get("confirmed_bugs") or []),
                sorted(directory.get("confirmed_bugs") or []),
            ),
        },
        "buggy-forum": _transfer("buggy-forum", PREVIOUS, PREVIOUS_POLICY),
        "buggy-billing": _transfer("buggy-billing", PREVIOUS, PREVIOUS_POLICY),
        "buggy-crm": mechanism_preserved(crm),
        "buggy-ops": mechanism_preserved(ops),
    }


def _deep_epoch(seq: list, steps: list, row: dict) -> dict:
    starts = [event for event in seq if event.get("event") == "return_entry_drain_started"]
    start = None if not starts else starts[0]
    if start is None:
        return {"present": False}
    classified = _classify_start(seq, start)
    end = _epoch_end(starts, 0)
    probes = _probe_rows(seq, steps, classified["step"], end)
    confirmed = sorted(row.get("confirmed_bugs") or [])
    return {
        "present": True,
        "trigger": classified,
        "probes": probes,
        "states": row.get("states"),
        "urls": row.get("normalized_unique_urls"),
        "return_success": row.get("return_success"),
        "return_cycle_escape_events": row.get("return_cycle_escape_events"),
        "confirmed_bugs": confirmed,
        "lost_vs_guard": sorted(set(DEEP_GUARD) - set(confirmed)),
    }


def _lab_epoch(seq: list, steps: list, row: dict) -> dict:
    classified_rows = [
        _classify_start(seq, event)
        for event in seq
        if event.get("event") == "return_entry_drain_started"
    ]
    result = None
    for item in classified_rows:
        keys = [_eid(key) for key in item["visible_eligible_keys"]]
        if "btn_close" in keys and "btn_reopen" in keys and item["kind"] == "finding":
            result = item
            break
    if result is None:
        return {"present": False}
    starts = [event for event in seq if event.get("event") == "return_entry_drain_started"]
    index = next(
        cursor for cursor, event in enumerate(starts)
        if event.get("step") == result["step"]
    )
    probes = _probe_rows(seq, steps, result["step"], _epoch_end(starts, index))
    attempts = [probe.get("return_attempts") for probe in probes]
    stable_attempts = bool(attempts) and all(value == result.get("return_attempts") for value in attempts)
    return {
        "present": True,
        "trigger": result,
        "probes": probes,
        "return_attempts_unchanged_across_recorded_probes": stable_attempts,
        "confirmed_bugs": sorted(row.get("confirmed_bugs") or []),
        "lost_vs_lab_guard": sorted(set(LAB_GUARD) - set(row.get("confirmed_bugs") or [])),
    }


def _finding_stop(seq: list, steps: list) -> dict:
    epochs = _finding_then_next(seq, steps)
    lab = [
        epoch for epoch in epochs
        if epoch.get("probe_eid") == "btn_close" and epoch.get("next_probe_eid") == "btn_reopen"
        and "lab_reopen_clears" in set(epoch.get("next_assert_ids") or [])
    ]
    return {
        "rule": "if any local probe produces a finding, stop the drain immediately",
        "rejected_before_candidate_design": True,
        "trace_support_only": True,
        "lab_epochs_where_later_probe_carries_l9": lab,
        "finding_stop_would_skip_the_later_probe": bool(lab),
        "other_epochs": [
            epoch for epoch in epochs
            if epoch not in lab
        ],
    }


def _read_files() -> list:
    rels = []
    for _app, folder in APPS:
        rels.append(_seq_path(CURRENT, folder, CURRENT_POLICY))
        rels.append(_events_path(CURRENT, folder, CURRENT_POLICY))
        rels.append(_metrics_path(CURRENT, folder))
        rels.append(_metrics_path(PREVIOUS, folder))
    rels.extend((
        _metrics_path(GUARD_PUB, "deepbench"),
        _metrics_path(FRESH, "buggy-forum"),
        _metrics_path(FRESH, "buggy-billing"),
        _metrics_path(FRESH, "buggy-directory"),
        os.path.join(FRESH, "metrics", "per-target.json"),
    ))
    return [
        {"path": rel.replace("\\", "/"), "sha256": sha256_file(_abs(rel))}
        for rel in rels
    ]


def _freeze_identities() -> dict:
    out = {}
    for label, rel in FREEZES.items():
        payload = load_json(_abs(rel))
        out[label] = {
            "path": rel,
            "sha256": sha256_file(_abs(rel)),
            "algorithm_name": payload.get("algorithm_name"),
        }
    return out


def build_trigger_context_analysis() -> dict:
    census = {}
    sequences = {}
    browser = {}
    current_rows = {}
    for app, folder in APPS:
        sequences[app] = _load_seq(CURRENT, folder, CURRENT_POLICY)
        browser[app] = _load_steps(CURRENT, folder, CURRENT_POLICY)
        census[app] = _census(sequences[app])
        current_rows[app] = _row(CURRENT, folder, CURRENT_POLICY)
    crash_triggers = sum(block["crash_triggers"] for block in census.values())
    lab_stop = _finding_stop(sequences["buggy-lab"], browser["buggy-lab"])
    named = {
        "billing_close_reopen": any(
            epoch.get("probe_eid") == "btn_close" and epoch.get("next_probe_eid") == "btn_reopen"
            for epoch in _finding_then_next(sequences["buggy-billing"], browser["buggy-billing"])
        ),
        "desk_test_conn_webhook": any(
            epoch.get("probe_eid") == "btn_test_conn" and epoch.get("next_probe_eid") == "btn_webhook"
            for epoch in _finding_then_next(sequences["buggy-desk"], browser["buggy-desk"])
        ),
        "wiki_watch_unpublish": any(
            epoch.get("probe_eid") == "btn_watch" and epoch.get("next_probe_eid") == "btn_unpublish"
            for epoch in _finding_then_next(sequences["wiki"], browser["wiki"])
        ),
    }
    deep_row = current_rows["deepbench"]
    lab_row = current_rows["buggy-lab"]
    return {
        "round": "v0.3.19",
        "source_round": "v0.3.18",
        "source_publication": CURRENT.replace("\\", "/"),
        "previous_publication": PREVIOUS.replace("\\", "/"),
        "guard_publication": GUARD_PUB.replace("\\", "/"),
        "budget": 120,
        "seed": 1,
        "derived_from_committed_evidence": True,
        "hand_typed_counts": False,
        "browser_rerun": False,
        "causal_claim": False,
        "limitation": (
            "Counts and epochs are read from committed sequence events and "
            "browser steps. They support the preregistered hypothesis. They "
            "do not by themselves establish that the hypothesis will succeed."
        ),
        "rejected_finding_stop": lab_stop,
        "named_finding_then_next_epochs_present": named,
        "trigger_census": {
            app: {
                "finding_terminal_triggers": block["finding_terminal_triggers"],
                "horizon_triggers": block["horizon_triggers"],
                "crash_triggers": block["crash_triggers"],
                "other_triggers": block["other_triggers"],
                "return_entry_drain_started": block["return_entry_drain_started"],
            }
            for app, block in census.items()
        },
        "trigger_details": {
            app: block["triggers"] for app, block in census.items()
        },
        "crash_terminal_triggers": crash_triggers,
        "deep_harmful_epoch": _deep_epoch(sequences["deepbench"], browser["deepbench"], deep_row),
        "lab_l9_epoch": _lab_epoch(sequences["buggy-lab"], browser["buggy-lab"], lab_row),
        "v0318_deep_metrics": _slim_row(deep_row),
        "v0318_lab_metrics": _slim_row(lab_row),
        "v0317_historical_preservation": _preservation(),
        "freeze_identities": _freeze_identities(),
        "evidence_files": _read_files(),
    }


def analysis_bytes(report: dict | None = None) -> bytes:
    return canonical_json_bytes(
        report if report is not None else build_trigger_context_analysis())


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        default=os.path.join(
            "experiments", "validation", "v0.3.19",
            "v0318-trigger-context-analysis.json"),
    )
    args = parser.parse_args(argv)
    payload = analysis_bytes()
    path = _abs(args.write) if not os.path.isabs(args.write) else args.write
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(payload)
    print(sha256_bytes(payload))
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
