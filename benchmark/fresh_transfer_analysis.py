"""v0.3.10 derived metrics, C1 measurement-only cycle detector, Outcome A/B/C/D."""
from __future__ import annotations

import os
from collections import Counter

from benchmark.application_shape_evidence import load_json, load_jsonl, steps_only


def normalize_url(url: str) -> str:
    if not url:
        return ""
    path = url
    if "://" in path:
        path = path.split("://", 1)[1]
        path = path.split("/", 1)[1] if "/" in path else ""
        path = "/" + path
    path = path.split("#", 1)[0]
    return path or "/"


def seq_event_counts(seq_events: list) -> dict:
    outcomes = Counter()
    types = Counter()
    for e in seq_events or []:
        types[e.get("event") or ""] += 1
        if e.get("event") == "sequence_terminal":
            outcomes[e.get("outcome") or "unknown"] += 1
        if e.get("event") == "return_cycle_escape":
            outcomes["return_cycle_escape"] += 1
    return {
        "branch_start_events": types.get("branch_start", 0),
        "return_attempt_events": types.get("return_attempt", 0),
        "successful_return_to_parent_events": outcomes.get("returned", 0),
        "sequence_instances_returned": outcomes.get("returned", 0),
        "sequence_lost_parent": outcomes.get("lost_parent", 0),
        "return_cycle_escape_events": types.get("return_cycle_escape", 0),
        "return_cycle_abandoned": outcomes.get("return_cycle_abandoned", 0),
        "finding": outcomes.get("finding", 0),
        "returned": outcomes.get("returned", 0),
        "event_types": dict(types),
    }


def detect_return_cycle_opportunities(seq_events: list, step_events: list | None = None) -> list:
    """Measurement-only detector. Does not affect C1 decisions.

    An evaluable opportunity exists when an unresolved return phase revisits
    the same exact destination signature before matching the recorded parent.
    """
    dest_by_step = {}
    cluster_by_step = {}
    for s in steps_only(step_events or []):
        idx = s.get("index")
        if idx is None:
            continue
        dest_by_step[idx] = s.get("dst_sig") or ""
        cluster_by_step[idx] = s.get("dst_cluster") or ""

    by_step: dict[int, list] = {}
    for e in seq_events or []:
        st = e.get("step")
        if st is None:
            continue
        by_step.setdefault(int(st), []).append(e)

    returning = False
    was_returning = False
    seen: set = set()
    parent_sig = ""
    parent_cluster = ""
    branch = ""
    opportunities = []

    def _close_open(*, succeeded: bool):
        for opp in opportunities:
            if opp.get("open"):
                if succeeded and opp.get("return_later_succeeded") is False:
                    opp["return_later_succeeded"] = True
                opp["open"] = False

    steps = sorted(set(by_step) | set(dest_by_step))
    for step in steps:
        for e in by_step.get(step, []):
            ev = e.get("event")
            if ev == "branch_start":
                parent_sig = e.get("exact_sig") or ""
                parent_cluster = e.get("cluster_id") or ""
                branch = e.get("branch_key") or ""
                returning = False
                seen = set()
            elif ev == "sequence_horizon_reached":
                returning = True
            elif ev == "sequence_terminal":
                outcome = e.get("outcome")
                if outcome in ("finding", "crash"):
                    returning = True
                elif outcome == "returned":
                    returning = False
                    seen = set()
                    _close_open(succeeded=True)
                elif outcome in ("lost_parent", "budget_end"):
                    returning = False
                    seen = set()
                    _close_open(succeeded=False)

        dest = dest_by_step.get(step) or ""
        dst_cluster = cluster_by_step.get(step) or ""
        recorded = False
        if returning and dest:
            if not was_returning:
                seen = set()
            parent_hit = dest == parent_sig or (
                dst_cluster and dst_cluster == parent_cluster)
            if parent_hit:
                returning = False
                seen = set()
            elif dest in seen:
                opportunities.append({
                    "step": step,
                    "branch": branch,
                    "repeated_destination_sig": dest,
                    "parent_hub_sig": parent_sig,
                    "return_later_succeeded": False,
                    "open": True,
                })
                recorded = True
                returning = False
                seen = set()
            else:
                seen.add(dest)

        for e in by_step.get(step, []):
            if e.get("event") != "return_cycle_escape":
                continue
            if not recorded:
                opportunities.append({
                    "step": step,
                    "branch": e.get("active_branch") or e.get("branch_key") or branch,
                    "repeated_destination_sig": e.get("repeated_destination_sig") or dest,
                    "parent_hub_sig": e.get("parent_hub_sig") or parent_sig,
                    "return_later_succeeded": False,
                    "open": False,
                })
            returning = False
            seen = set()
        was_returning = returning

    for opp in opportunities:
        opp.pop("open", None)
    return opportunities


def first_escape_record(seq_events: list) -> dict:
    esc = next((e for e in seq_events or []
                if e.get("event") == "return_cycle_escape"), None)
    if esc is None:
        return {}
    return {
        "first_escape_step": esc.get("step"),
        "repeated_destination_sig": esc.get("repeated_destination_sig"),
        "parent": esc.get("parent_hub_sig") or esc.get("parent_hub_cluster"),
        "parent_hub_sig": esc.get("parent_hub_sig"),
        "parent_hub_cluster": esc.get("parent_hub_cluster"),
        "branch_key": esc.get("active_branch") or esc.get("branch_key"),
    }


def post_escape_novelty(graph: dict, events: list, escape_step) -> dict:
    if escape_step is None:
        return {
            "post_escape_novel_state_count": 0,
            "post_escape_novel_url_count": 0,
            "post_escape_novel_urls": [],
            "first_post_escape_novel_state_step": None,
            "first_post_escape_novel_url_step": None,
        }
    before_nodes = [n for n in graph.get("nodes") or []
                    if (n.get("first_seen_step") or 0) <= (escape_step + 1)]
    after_nodes = [n for n in graph.get("nodes") or []
                   if (n.get("first_seen_step") or 0) > (escape_step + 1)]
    before_urls = {normalize_url(s.get("dst_url") or "")
                   for s in steps_only(events)
                   if (s.get("index") or 0) <= escape_step}
    after_urls = []
    first_url_step = None
    for s in steps_only(events):
        idx = s.get("index")
        if idx is None or idx <= escape_step:
            continue
        u = normalize_url(s.get("dst_url") or "")
        if u and u not in before_urls and u not in after_urls:
            after_urls.append(u)
            if first_url_step is None:
                first_url_step = idx
    first_state = None
    if after_nodes:
        first_state = min(n.get("first_seen_step") for n in after_nodes)
    return {
        "post_escape_novel_state_count": len(after_nodes),
        "post_escape_novel_url_count": len(after_urls),
        "post_escape_novel_urls": after_urls,
        "first_post_escape_novel_state_step": first_state,
        "first_post_escape_novel_url_step": first_url_step,
        "states_before_escape": len(before_nodes),
    }


def novelty_absent_from_c1(guard_graph: dict, guard_events: list,
                           c1_graph: dict, c1_events: list, escape_step) -> dict:
    if escape_step is None:
        return {"absent_from_c1_state_count": 0, "absent_from_c1_url_count": 0,
                "absent_from_c1_urls": []}
    c1_sigs = {n.get("id") or n.get("sig") for n in c1_graph.get("nodes") or []}
    c1_urls = {normalize_url(n.get("url") or "") for n in c1_graph.get("nodes") or []}
    c1_urls |= {normalize_url(s.get("dst_url") or "") for s in steps_only(c1_events)}
    c1_urls.discard("")
    new_states = 0
    new_urls = []
    for n in guard_graph.get("nodes") or []:
        if (n.get("first_seen_step") or 0) <= (escape_step + 1):
            continue
        sig = n.get("id") or n.get("sig")
        if sig and sig not in c1_sigs:
            new_states += 1
        u = normalize_url(n.get("url") or "")
        if u and u not in c1_urls and u not in new_urls:
            new_urls.append(u)
    for s in steps_only(guard_events):
        idx = s.get("index")
        if idx is None or idx <= escape_step:
            continue
        u = normalize_url(s.get("dst_url") or "")
        if u and u not in c1_urls and u not in new_urls:
            new_urls.append(u)
    return {
        "absent_from_c1_state_count": new_states,
        "absent_from_c1_url_count": len(new_urls),
        "absent_from_c1_urls": new_urls,
    }


def unique_urls_from_graph(graph: dict) -> list:
    urls = []
    seen = set()
    for n in graph.get("nodes") or []:
        u = normalize_url(n.get("url") or "")
        if u and u not in seen:
            seen.add(u)
            urls.append(u)
    return urls


def derive_outcome(
    *,
    opportunity_count: int,
    guard_escapes: int,
    post_escape_novel_state_count: int = 0,
    post_escape_novel_url_count: int = 0,
    absent_from_c1_state_count: int = 0,
    absent_from_c1_url_count: int = 0,
    c1_confirmed: list | None = None,
    guard_confirmed: list | None = None,
    s1_escapes: int = 0,
    s2_escapes: int = 0,
    s3_escapes: int = 0,
    s4_escapes: int = 1,
    s4_returned_inflation: int = 0,
    s5_escapes: int = 1,
    s5_returned_inflation: int = 0,
    escape_counted_returned: bool = False,
    safety_regression: bool = False,
    historical_ok: bool = True,
    freeze_ok: bool = True,
) -> str:
    """Preregistered v0.3.10 Outcome A/B/C/D."""
    c1_set = {str(x) for x in (c1_confirmed or [])}
    g_set = {str(x) for x in (guard_confirmed or [])}
    lost = sorted(c1_set - g_set)
    s123_false = (s1_escapes > 0) or (s2_escapes > 0) or (s3_escapes > 0)
    s45_bad = (
        s4_escapes != 1 or s4_returned_inflation > 0
        or s5_escapes != 1 or s5_returned_inflation > 0
    )
    if (s123_false or escape_counted_returned or lost or safety_regression
            or not historical_ok or not freeze_ok or s45_bad):
        return "C"
    if int(opportunity_count or 0) < 1:
        return "D"
    novel = (
        int(post_escape_novel_state_count or 0) >= 1
        or int(post_escape_novel_url_count or 0) >= 1
        or int(absent_from_c1_state_count or 0) >= 1
        or int(absent_from_c1_url_count or 0) >= 1
    )
    if int(guard_escapes or 0) >= 1 and novel and not lost:
        return "A"
    return "B"


OUTCOME_MEANING = {
    "A": "fresh transfer with safety",
    "B": "safe but no demonstrated transfer benefit",
    "C": "harmful/regression",
    "D": "inconclusive target",
}

PRIMARY = "ghost-structural-memory"
GUARD = "ghost-structural-return-guard"
MATRIX_POLICIES = (
    "ghost-structural-memory",
    "ghost-structural-return-guard",
    "ghost-nollm",
    "bfs",
    "dfs",
)
PRIMARY_BUDGET = 120
PUBLISHED_ROOT = os.path.join(
    "experiments", "published", "fresh-transfer-v0.3.10")


def _stem(policy: str, budget: int = PRIMARY_BUDGET, seed: int = 1) -> str:
    return f"{policy}_b{budget}_s{seed}"


def load_cell_files(root: str, policy: str, budget: int = PRIMARY_BUDGET, seed: int = 1):
    base = os.path.join(root, "evidence", "buggy-desk")
    stem = _stem(policy, budget, seed)
    ev_path = os.path.join(base, stem + ".events.jsonl")
    g_path = os.path.join(base, stem + ".graph.json")
    s_path = os.path.join(base, stem + ".sequence_events.json")
    events = load_jsonl(ev_path) if os.path.isfile(ev_path) else []
    graph = load_json(g_path) if os.path.isfile(g_path) else {"nodes": [], "edges": []}
    seq = load_json(s_path) if os.path.isfile(s_path) else []
    return events, graph, seq


def metrics_row(root: str, policy: str, budget: int) -> dict:
    path = os.path.join(root, "evidence", "buggy-desk", "metrics.json")
    if not os.path.isfile(path):
        path = os.path.join(root, "metrics", "raw-runs.json")
    data = load_json(path) if os.path.isfile(path) else {}
    for r in data.get("runs") or []:
        if r.get("policy") == policy and r.get("budget") == budget:
            return r
    return {}


def derive_policy_cell(root: str, policy: str, budget: int = PRIMARY_BUDGET) -> dict:
    events, graph, seq = load_cell_files(root, policy, budget)
    counts = seq_event_counts(seq)
    row = metrics_row(root, policy, budget)
    urls = unique_urls_from_graph(graph) or list(row.get("unique_urls") or [])
    esc = first_escape_record(seq)
    novelty = post_escape_novelty(graph, events, esc.get("first_escape_step"))
    opps = []
    if policy == PRIMARY:
        opps = detect_return_cycle_opportunities(seq, events)
    escaped_returned = 0
    if policy == GUARD:
        for e in seq:
            if e.get("event") == "return_cycle_escape":
                pass
        for e in seq:
            if (e.get("event") == "sequence_terminal"
                    and e.get("outcome") == "returned"
                    and e.get("outcome") == "return_cycle_abandoned"):
                escaped_returned += 1
        abandoned_as_returned = [
            e for e in seq
            if e.get("event") == "sequence_terminal"
            and e.get("outcome") == "returned"
            and any(
                x.get("event") == "return_cycle_escape"
                and x.get("step") == e.get("step")
                for x in seq)
        ]
        escaped_returned = len(abandoned_as_returned)
    out = {
        "policy": policy,
        "budget": budget,
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
        "wall_seconds": row.get("wall_seconds"),
        "canonical_hub_count": row.get("canonical_hub_count"),
        "unique_branches_discovered": row.get("unique_branches_discovered"),
        "unique_branches_started": row.get("unique_branches_started"),
        "branch_attempts_per_unique_branch": row.get("branch_attempts_per_unique_branch"),
        "mean_sequence_len": row.get("mean_sequence_len"),
        "max_sequence_len": row.get("max_sequence_len"),
        "max_workflow_depth": row.get("max_workflow_depth"),
        **counts,
        **esc,
        **novelty,
        "c1_opportunities": opps,
        "c1_opportunity_count": len(opps),
        "escape_counted_returned": escaped_returned,
    }
    return out


def derive_bundle(root: str, *, safety: dict | None = None,
                  historical_ok: bool = True, freeze_ok: bool = True) -> dict:
    cells = {}
    table = []
    for pol in MATRIX_POLICIES:
        for bud in (40, 80, 120):
            cell = derive_policy_cell(root, pol, bud)
            cells[f"{pol}@{bud}"] = cell
            if bud == PRIMARY_BUDGET:
                table.append(cell)
    c1 = cells[f"{PRIMARY}@{PRIMARY_BUDGET}"]
    guard = cells[f"{GUARD}@{PRIMARY_BUDGET}"]
    events_g, graph_g, _ = load_cell_files(root, GUARD, PRIMARY_BUDGET)
    events_c, graph_c, _ = load_cell_files(root, PRIMARY, PRIMARY_BUDGET)
    abs_c1 = novelty_absent_from_c1(
        graph_g, events_g, graph_c, events_c, guard.get("first_escape_step"))
    if safety is None:
        sp = os.path.join(root, "evidence", "safety", "safety.json")
        safety = load_json(sp) if os.path.isfile(sp) else {}
    lost = sorted(set(c1.get("confirmed_bugs") or []) - set(guard.get("confirmed_bugs") or []))
    c1_returned_keys = {
        e.get("branch_key") for e in load_cell_files(root, PRIMARY, PRIMARY_BUDGET)[2]
        if e.get("event") == "sequence_terminal" and e.get("outcome") == "returned"
    }
    g_returned_keys = {
        e.get("branch_key") for e in load_cell_files(root, GUARD, PRIMARY_BUDGET)[2]
        if e.get("event") == "sequence_terminal" and e.get("outcome") == "returned"
    }
    lost_return_keys = sorted(k for k in (c1_returned_keys - g_returned_keys) if k)
    guard_escapes_list = [
        e for e in load_cell_files(root, GUARD, PRIMARY_BUDGET)[2]
        if e.get("event") == "return_cycle_escape"
    ]
    outcome = derive_outcome(
        opportunity_count=c1.get("c1_opportunity_count") or 0,
        guard_escapes=guard.get("return_cycle_escape_events") or 0,
        post_escape_novel_state_count=guard.get("post_escape_novel_state_count") or 0,
        post_escape_novel_url_count=guard.get("post_escape_novel_url_count") or 0,
        absent_from_c1_state_count=abs_c1.get("absent_from_c1_state_count") or 0,
        absent_from_c1_url_count=abs_c1.get("absent_from_c1_url_count") or 0,
        c1_confirmed=c1.get("confirmed_bugs") or [],
        guard_confirmed=guard.get("confirmed_bugs") or [],
        s1_escapes=int((safety or {}).get("s1_escapes") or 0),
        s2_escapes=int((safety or {}).get("s2_escapes") or 0),
        s3_escapes=int((safety or {}).get("s3_escapes") or 0),
        s4_escapes=int((safety or {}).get("s4_escapes") or 1),
        s4_returned_inflation=int((safety or {}).get("s4_returned_inflation") or 0),
        s5_escapes=int((safety or {}).get("s5_escapes") or 1),
        s5_returned_inflation=int((safety or {}).get("s5_returned_inflation") or 0),
        escape_counted_returned=bool(guard.get("escape_counted_returned")),
        safety_regression=not bool((safety or {}).get("all_pass", True)),
        historical_ok=historical_ok,
        freeze_ok=freeze_ok,
    )
    return {
        "observed": {
            "cells": {k: {kk: vv for kk, vv in v.items() if kk != "c1_opportunities"}
                      for k, v in cells.items()},
            "primary_budget": PRIMARY_BUDGET,
            "table_120": [
                {
                    "policy": c["policy"],
                    "states": c.get("states"),
                    "urls": c.get("normalized_unique_urls"),
                    "BDR": c.get("bug_discovery_rate"),
                    "Deep-BDR": c.get("deep_bug_discovery_rate"),
                    "return_attempts": c.get("return_attempt_events"),
                    "returned": c.get("successful_return_to_parent_events"),
                    "escapes": c.get("return_cycle_escape_events"),
                    "confirmed": c.get("confirmed_bugs"),
                }
                for c in table
            ],
        },
        "c1_120": c1,
        "guard_120": {**guard, **abs_c1},
        "c1_opportunities": c1.get("c1_opportunities") or [],
        "guard_escapes": [
            {"step": e.get("step"), "repeated_destination_sig": e.get("repeated_destination_sig"),
             "parent_hub_sig": e.get("parent_hub_sig"),
             "branch": e.get("active_branch") or e.get("branch_key")}
            for e in guard_escapes_list
        ],
        "safety": safety,
        "derived": {
            "outcome": outcome,
            "outcome_meaning": OUTCOME_MEANING[outcome],
            "lost_c1_confirmed": lost,
            "lost_return_branch_keys": lost_return_keys,
            "generalization_claim": False,
            "product_default_changed": False,
        },
        "interpretation": {
            "outcome_meaning": OUTCOME_MEANING[outcome],
            "generalization_claim": False,
            "product_default_changed": False,
            "scope": "one fresh application transfer under a frozen candidate",
        },
    }
