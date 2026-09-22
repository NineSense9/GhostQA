"""v0.3.11 derived metrics and Outcome A/B/C/D. Measurement only."""
from __future__ import annotations

import os

from benchmark.fresh_transfer_analysis import (
    detect_return_cycle_opportunities, novelty_absent_from_c1,
    post_escape_novelty, seq_event_counts, unique_urls_from_graph,
    first_escape_record, PRIMARY, GUARD, PRIMARY_BUDGET,
)
from benchmark.application_shape_evidence import load_json, load_jsonl
from benchmark.return_cycle_accounting import (
    classify_escape_lifecycle, match_escapes_to_opportunities, branch_of,
)
from benchmark.multitarget_vocab import APP_NAMES

PUBLISHED_ROOT = os.path.join(
    "experiments", "published", "multi-target-replication-v0.3.11")
MATRIX_PRIMARY = (PRIMARY, GUARD)
CONTEXT = ("ghost-nollm", "bfs", "dfs")
PRIMARY_BUDGETS = (40, 80, 120)

OUTCOME_MEANING = {
    "A": "multi-target replication with safety",
    "B": "safe but mixed replication",
    "C": "harmful/regression",
    "D": "inconclusive suite",
}

PROMOTION_NOT_READY = "not_ready"
PROMOTION_STUDY = "evidence_supports_productization_study"


def meaningful_lost_return_keys(c1_seq: list, guard_seq: list,
                                c1_opportunities: list) -> list:
    """C1 returned keys that the guard also started, excluding cycle branches."""
    c1_ret = {e.get("branch_key") for e in c1_seq or []
              if e.get("event") == "sequence_terminal"
              and e.get("outcome") == "returned" and e.get("branch_key")}
    g_ret = {e.get("branch_key") for e in guard_seq or []
             if e.get("event") == "sequence_terminal"
             and e.get("outcome") == "returned" and e.get("branch_key")}
    g_started = {e.get("branch_key") for e in guard_seq or []
                 if e.get("event") == "branch_start" and e.get("branch_key")}
    cycle_branches = {o.get("branch") for o in c1_opportunities or [] if o.get("branch")}
    return sorted((c1_ret & g_started) - g_ret - cycle_branches)


def derive_v0311_outcome(
    *,
    exhaustive_failures: int,
    s1_s7_pass: bool,
    per_target: list,
    historical_ok: bool = True,
    freeze_ok: bool = True,
    v0310_outcome_a: bool = True,
    deepbench_regression_safe: bool = True,
) -> dict:
    """Preregistered v0.3.11 Outcome A/B/C/D plus promotion_readiness."""
    n = len(per_target or [])
    unmatched = any(not t.get("escape_opportunity_ok", True) for t in per_target)
    unclassified = any(int(t.get("unclassified_escapes") or 0) > 0 for t in per_target)
    inflation = any(bool(t.get("return_inflation")) for t in per_target)
    lost_bugs = [t["name"] for t in per_target if t.get("lost_c1_bugs")]
    lost_returns = [t["name"] for t in per_target if t.get("lost_meaningful_return_keys")]
    evaluable = sum(1 for t in per_target if int(t.get("evaluable_opportunity") or 0) >= 1)
    transfer = sum(
        1 for t in per_target
        if int(t.get("guard_escapes") or 0) >= 1 and bool(t.get("post_escape_novelty"))
    )
    safety_fail = (
        int(exhaustive_failures or 0) > 0
        or not s1_s7_pass
        or unmatched
        or unclassified
        or inflation
        or not historical_ok
        or not freeze_ok
        or bool(lost_bugs)
        or bool(lost_returns)
    )
    if safety_fail:
        outcome = "C"
    elif evaluable < 2:
        outcome = "D"
    elif transfer >= 2 and not lost_bugs and not lost_returns:
        outcome = "A"
    else:
        outcome = "B"

    promotion = PROMOTION_NOT_READY
    if (outcome == "A" and v0310_outcome_a and transfer >= 2
            and not lost_bugs and int(exhaustive_failures or 0) == 0
            and s1_s7_pass and deepbench_regression_safe):
        promotion = PROMOTION_STUDY

    return {
        "outcome": outcome,
        "outcome_meaning": OUTCOME_MEANING[outcome],
        "promotion_readiness": promotion,
        "product_default_changed": False,
        "generalization_claim": False,
        "n_targets": n,
        "evaluable_targets": evaluable,
        "transfer_targets": transfer,
        "targets_with_lost_c1_bugs": lost_bugs,
        "targets_with_return_regression": lost_returns,
    }


def load_cell(root: str, app: str, policy: str, budget: int, seed: int = 1):
    base = os.path.join(root, "evidence", app)
    stem = f"{policy}_b{budget}_s{seed}"
    ev = os.path.join(base, stem + ".events.jsonl")
    gp = os.path.join(base, stem + ".graph.json")
    sp = os.path.join(base, stem + ".sequence_events.json")
    events = load_jsonl(ev) if os.path.isfile(ev) else []
    graph = load_json(gp) if os.path.isfile(gp) else {"nodes": [], "edges": []}
    seq = load_json(sp) if os.path.isfile(sp) else []
    return events, graph, seq


def metrics_row(root: str, app: str, policy: str, budget: int) -> dict:
    path = os.path.join(root, "evidence", app, "metrics.json")
    if not os.path.isfile(path):
        path = os.path.join(root, "metrics", "per-target.json")
    data = load_json(path) if os.path.isfile(path) else {}
    runs = data.get("runs") or data.get(app, {}).get("runs") or []
    if isinstance(data.get(app), dict) and "runs" not in data:
        runs = []
    for r in runs:
        if r.get("policy") == policy and r.get("budget") == budget:
            return r
    # published per-target.json may be {app: {policy@budget: row}}
    cell = (data.get(app) or {}).get(f"{policy}@{budget}")
    if isinstance(cell, dict):
        return cell
    return {}


def derive_target_cell(root: str, app: str, policy: str, budget: int) -> dict:
    events, graph, seq = load_cell(root, app, policy, budget)
    counts = seq_event_counts(seq)
    row = metrics_row(root, app, policy, budget)
    urls = unique_urls_from_graph(graph) or list(row.get("unique_urls") or [])
    esc = first_escape_record(seq)
    novelty = post_escape_novelty(graph, events, esc.get("first_escape_step"))
    opps = detect_return_cycle_opportunities(seq, events)
    life = classify_escape_lifecycle(seq) if policy == GUARD else {
        "escape_count": 0, "L1": 0, "L2": 0, "unclassified": 0, "ok": True,
        "return_inflation_events": [], "escapes": [],
    }
    escapes = [e for e in seq if e.get("event") == "return_cycle_escape"]
    matched = match_escapes_to_opportunities(escapes, opps) if policy == GUARD else {
        "ok": True, "escape_count": 0, "opportunity_count": len(opps), "matched": 0,
        "unmatched_escapes": [],
    }
    return {
        "app": app, "policy": policy, "budget": budget,
        "actions": row.get("actions"),
        "states": len(graph.get("nodes") or []) or row.get("states"),
        "clusters": row.get("clusters"),
        "variants": row.get("variants"),
        "normalized_unique_urls": len(urls) or row.get("normalized_unique_urls"),
        "unique_urls": urls,
        "candidates": row.get("candidates") or row.get("candidate_count"),
        "confirmed_bug_count": row.get("confirmed_bug_count"),
        "confirmed_bugs": row.get("confirmed_bugs") or [],
        "bug_discovery_rate": row.get("bug_discovery_rate"),
        "deep_bug_discovery_rate": row.get("deep_bug_discovery_rate"),
        "discovery_auc": row.get("discovery_auc"),
        "ttcb": row.get("ttcb"),
        "ttdcb": row.get("ttdcb"),
        "replay_pass": row.get("replay_pass"),
        "replay_fail": row.get("replay_fail"),
        "replay_invalid": row.get("replay_invalid"),
        "repeat_rate": row.get("repeat_rate"),
        **counts, **esc, **novelty,
        "c1_opportunities": opps,
        "c1_opportunity_count": len(opps),
        "lifecycle": {
            "escapes": life.get("escape_count"),
            "L1": life.get("L1"),
            "L2": life.get("L2"),
            "unclassified": life.get("unclassified"),
        },
        "escape_opportunity_match": matched,
        "return_inflation": bool(life.get("return_inflation_events")),
    }


def derive_target_bundle(root: str, app: str, *, safety: dict | None = None) -> dict:
    c1 = derive_target_cell(root, app, PRIMARY, PRIMARY_BUDGET)
    guard = derive_target_cell(root, app, GUARD, PRIMARY_BUDGET)
    ev_g, g_g, seq_g = load_cell(root, app, GUARD, PRIMARY_BUDGET)
    ev_c, g_c, seq_c = load_cell(root, app, PRIMARY, PRIMARY_BUDGET)
    abs_c1 = novelty_absent_from_c1(
        g_g, ev_g, g_c, ev_c, guard.get("first_escape_step"))
    lost = sorted(set(c1.get("confirmed_bugs") or []) - set(guard.get("confirmed_bugs") or []))
    lost_keys = meaningful_lost_return_keys(
        seq_c, seq_g, c1.get("c1_opportunities") or [])
    evaluable = int(c1.get("c1_opportunity_count") or 0) >= 1 or int(
        guard.get("return_cycle_escape_events") or 0) >= 1
    novelty = (
        int(guard.get("post_escape_novel_state_count") or 0) >= 1
        or int(guard.get("post_escape_novel_url_count") or 0) >= 1
        or int(abs_c1.get("absent_from_c1_state_count") or 0) >= 1
        or int(abs_c1.get("absent_from_c1_url_count") or 0) >= 1
    )
    table = []
    cells = {}
    for pol in MATRIX_PRIMARY:
        for bud in PRIMARY_BUDGETS:
            cells[f"{pol}@{bud}"] = derive_target_cell(root, app, pol, bud)
    for pol in CONTEXT:
        cells[f"{pol}@120"] = derive_target_cell(root, app, pol, 120)
    for pol in list(MATRIX_PRIMARY) + list(CONTEXT):
        c = cells[f"{pol}@120"]
        table.append({
            "policy": pol,
            "states": c.get("states"),
            "urls": c.get("normalized_unique_urls"),
            "BDR": c.get("bug_discovery_rate"),
            "Deep-BDR": c.get("deep_bug_discovery_rate"),
            "return_attempts": c.get("return_attempt_events"),
            "returned": c.get("successful_return_to_parent_events"),
            "escapes": c.get("return_cycle_escape_events"),
            "confirmed": c.get("confirmed_bugs"),
        })
    return {
        "app": app,
        "c1_120": c1,
        "guard_120": {**guard, **abs_c1},
        "cells": cells,
        "table_120": table,
        "lost_c1_bugs": lost,
        "lost_meaningful_return_keys": lost_keys,
        "evaluable_opportunity": 1 if evaluable else 0,
        "guard_escapes": guard.get("return_cycle_escape_events") or 0,
        "post_escape_novelty": novelty,
        "escape_opportunity_ok": bool((guard.get("escape_opportunity_match") or {}).get("ok", True)),
        "unclassified_escapes": (guard.get("lifecycle") or {}).get("unclassified") or 0,
        "return_inflation": bool(guard.get("return_inflation")),
        "lifecycle": guard.get("lifecycle"),
        "name": app,
    }


def derive_suite(root: str, *, safety: dict, historical_ok: bool,
                 freeze_ok: bool, v0310_outcome_a: bool = True,
                 deepbench_regression_safe: bool = True) -> dict:
    targets = []
    for app in APP_NAMES:
        if os.path.isdir(os.path.join(root, "evidence", app)):
            targets.append(derive_target_bundle(root, app, safety=safety))
    outcome = derive_v0311_outcome(
        exhaustive_failures=int((safety or {}).get("exhaustive_failures") or 0),
        s1_s7_pass=bool((safety or {}).get("s1_s7_all_pass", (safety or {}).get("all_pass"))),
        per_target=targets,
        historical_ok=historical_ok,
        freeze_ok=freeze_ok,
        v0310_outcome_a=v0310_outcome_a,
        deepbench_regression_safe=deepbench_regression_safe,
    )
    return {
        "targets": {t["app"]: t for t in targets},
        "derived": outcome,
        "safety": safety,
        "interpretation": {
            "outcome_meaning": outcome["outcome_meaning"],
            "generalization_claim": False,
            "product_default_changed": False,
            "scope": "preregistered multi-target replication of the return-cycle mechanism",
        },
    }
