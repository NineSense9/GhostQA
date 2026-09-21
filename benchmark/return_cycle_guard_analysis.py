"""Derive v0.3.9 mechanism metrics and Outcome A/B/C from committed evidence."""
from __future__ import annotations

import json
import os
from collections import Counter

from benchmark.application_shape_evidence import (
    load_json, load_jsonl, page_name, steps_only,
)

HISTORICAL_C1_120 = ["D6", "D7", "D11", "D12", "D13", "D14"]


def seq_event_counts(seq_events: list) -> dict:
    outcomes = Counter()
    types = Counter()
    for e in seq_events:
        types[e.get("event") or ""] += 1
        if e.get("event") == "sequence_terminal":
            outcomes[e.get("outcome") or "unknown"] += 1
        if e.get("event") == "return_cycle_escape":
            outcomes["return_cycle_escape"] += 1
    return {
        "branch_start_events": types.get("branch_start", 0),
        "return_attempt_events": types.get("return_attempt", 0),
        "successful_return_to_parent_events": outcomes.get("returned", 0),
        "return_cycle_escape_events": types.get("return_cycle_escape", 0),
        "return_cycle_abandoned": outcomes.get("return_cycle_abandoned", 0),
        "finding": outcomes.get("finding", 0),
        "lost_parent": outcomes.get("lost_parent", 0),
        "returned": outcomes.get("returned", 0),
        "event_types": dict(types),
    }


def unique_pages(graph: dict) -> list:
    return sorted({page_name(n.get("url") or "") for n in graph.get("nodes") or []
                   if page_name(n.get("url") or "")})


def first_escape(seq_events: list, events: list) -> dict:
    esc = next((e for e in seq_events if e.get("event") == "return_cycle_escape"), None)
    if esc is None:
        return {}
    step = esc.get("step")
    before_states, before_urls = set(), set()
    after_new_state_step = None
    after_new_url_step = None
    post_states, post_urls = set(), set()
    for s in steps_only(events):
        idx = s.get("index")
        dst = s.get("dst_url") or ""
        # graph grows; n_nodes if present
        url = page_name(dst)
        if idx is None:
            continue
        if step is not None and idx < step:
            before_urls.add(url)
        elif step is not None and idx > step:
            post_urls.add(url)
            if url and url not in before_urls and after_new_url_step is None:
                after_new_url_step = idx
    # states from graph first_seen vs escape step if available
    return {
        "escape_step": step,
        "repeated_destination_sig": esc.get("repeated_destination_sig"),
        "parent_hub_sig": esc.get("parent_hub_sig"),
        "parent_hub_cluster": esc.get("parent_hub_cluster"),
        "active_branch": esc.get("active_branch"),
        "urls_before_escape": sorted(before_urls - {""}),
        "first_post_escape_novel_url_step": after_new_url_step,
        "post_escape_new_url_count": len(post_urls - before_urls - {""}),
    }


def post_escape_states(graph: dict, escape_step) -> dict:
    if escape_step is None:
        return {"states_before": 0, "post_escape_new_state_count": 0,
                "first_post_escape_novel_state_step": None}
    before = [n for n in graph.get("nodes") or []
              if (n.get("first_seen_step") or 0) <= (escape_step + 1)]
    after = [n for n in graph.get("nodes") or []
             if (n.get("first_seen_step") or 0) > (escape_step + 1)]
    first = None
    if after:
        first = min(n.get("first_seen_step") for n in after)
    return {
        "states_before": len(before),
        "post_escape_new_state_count": len(after),
        "first_post_escape_novel_state_step": first,
    }


def load_run_metrics(path: str) -> dict:
    return load_json(path)


def norm_bug(i: str) -> str:
    s = str(i)
    return s[4:] if s.startswith("BUG-") else s


def compute_outcome(shop_base: dict, shop_cand: dict, deep_c1_120: dict,
                    deep_g_120: dict) -> str:
    """Preregistered A/B/C from derived metric dicts."""
    esc = int(shop_cand.get("return_cycle_escape_events") or 0)
    novel = int(shop_cand.get("post_escape_new_state_count") or 0)
    returned_term = int(shop_cand.get("successful_return_to_parent_events") or 0)
    mechanism_escape = esc >= 1
    lock_broken = novel >= 1 or int(shop_cand.get("n_urls") or 0) > int(
        shop_base.get("n_urls") or 0)
    if not mechanism_escape:
        return "C"
    if returned_term > 0 and esc >= 1 and novel < 1:
        return "C"
    conf = {norm_bug(x) for x in (deep_g_120.get("confirmed_bugs") or [])}
    hist = set(HISTORICAL_C1_120)
    lost = sorted(hist - conf)
    d6 = "D6" in conf
    d12 = "D12" in conf
    depth = int(deep_g_120.get("max_workflow_depth") or 0)
    if mechanism_escape and lock_broken and novel >= 1 and d6 and d12 and depth >= 4 and not lost:
        return "A"
    if mechanism_escape:
        return "B"
    return "C"


PUBLISHED_ROOT = os.path.join(
    "experiments", "published", "return-cycle-guard-v0.3.9")


def derive_shop_policy(root: str, policy: str) -> dict:
    stem = f"{policy}_b120_s1"
    base = os.path.join(root, "evidence", "shop")
    ev = load_jsonl(os.path.join(base, stem + ".events.jsonl"))
    seq = load_json(os.path.join(base, stem + ".sequence_events.json"))
    g = load_json(os.path.join(base, stem + ".graph.json"))
    c = seq_event_counts(seq)
    pages = unique_pages(g)
    esc = next((e for e in seq if e.get("event") == "return_cycle_escape"), None)
    step = None if esc is None else esc.get("step")
    after_nodes = [n for n in g.get("nodes") or []
                   if step is not None and (n.get("first_seen_step") or 0) > step + 1]
    before_urls = {page_name(s.get("dst_url")) for s in steps_only(ev)
                   if (s.get("index") or 0) <= (step if step is not None else -1)}
    after_urls = {page_name(s.get("dst_url")) for s in steps_only(ev)
                  if step is not None and (s.get("index") or 0) > step}
    new_urls = sorted(after_urls - before_urls - {""})
    first_new_url = None
    for s in steps_only(ev):
        if step is not None and (s.get("index") or 0) > step:
            u = page_name(s.get("dst_url"))
            if u and u not in before_urls:
                first_new_url = s.get("index")
                break
    conf = []
    shop_m = os.path.join(base, "metrics.json")
    if os.path.isfile(shop_m):
        for r in (load_json(shop_m).get("runs") or []):
            if r.get("policy") == policy:
                conf = r.get("confirmed_bugs") or []
    return {
        "policy": policy,
        "states": len(g.get("nodes") or []),
        "n_urls": len(pages),
        "pages": pages,
        **c,
        "confirmed_bugs": conf,
        "escape_step": None if esc is None else esc.get("step"),
        "repeated_destination_sig": None if esc is None else esc.get("repeated_destination_sig"),
        "parent_hub_sig": None if esc is None else esc.get("parent_hub_sig"),
        "parent_hub_cluster": None if esc is None else esc.get("parent_hub_cluster"),
        "post_escape_new_state_count": len(after_nodes),
        "first_post_escape_novel_state_step": (
            None if not after_nodes else min(n.get("first_seen_step") for n in after_nodes)),
        "post_escape_new_url_count": len(new_urls),
        "first_post_escape_novel_url_step": first_new_url,
        "post_escape_new_urls": new_urls,
    }


def derive_deep_row(root: str, policy: str, budget: int) -> dict:
    deep = load_json(os.path.join(root, "evidence", "deepbench", "metrics.json"))
    for r in deep.get("runs") or []:
        if r.get("policy") == policy and r.get("budget") == budget:
            return {
                "policy": policy, "budget": budget,
                "confirmed_bugs": r.get("confirmed_bugs"),
                "bug_discovery_rate": r.get("bug_discovery_rate"),
                "deep_bug_discovery_rate": r.get("deep_bug_discovery_rate"),
                "max_workflow_depth": r.get("max_workflow_depth"),
                "ttcb": r.get("ttcb"),
                "unique_branches_started": r.get("unique_branches_started"),
                "branch_attempts_per_unique_branch": r.get("branch_attempts_per_unique_branch"),
                "return_cycle_escape_events": r.get("return_cycle_escape_events"),
                "sequence_instances_returned": r.get("sequence_instances_returned"),
                "states": r.get("states"),
            }
    raise KeyError(f"{policy}@{budget}")


def derive_bundle(root: str) -> dict:
    shop_c1 = derive_shop_policy(root, "ghost-structural-memory")
    shop_g = derive_shop_policy(root, "ghost-structural-return-guard")
    deep = [derive_deep_row(root, p, b)
            for p in ("ghost-structural-memory", "ghost-structural-return-guard")
            for b in (40, 80, 120)]
    deep_c1_120 = derive_deep_row(root, "ghost-structural-memory", 120)
    deep_g_120 = derive_deep_row(root, "ghost-structural-return-guard", 120)
    outcome = compute_outcome(shop_c1, shop_g, deep_c1_120, deep_g_120)
    lost = sorted(set(HISTORICAL_C1_120) - {norm_bug(x) for x in deep_g_120["confirmed_bugs"]})
    gained = sorted({norm_bug(x) for x in deep_g_120["confirmed_bugs"]} - set(HISTORICAL_C1_120))
    return {
        "observed": {
            "shop": {"baseline": shop_c1, "candidate": shop_g},
            "deepbench": deep,
        },
        "derived": {
            "outcome": outcome,
            "lost_from_baseline_120": lost,
            "gained_vs_baseline_120": gained,
            "historical_c1_120": HISTORICAL_C1_120,
        },
        "interpretation": {
            "outcome_meaning": {
                "A": "Mechanism repaired, regression-safe",
                "B": "Mechanism repaired, but regression/tradeoff",
                "C": "Mechanism not repaired",
            }[outcome],
            "generalization_claim": False,
            "product_default_changed": False,
        },
    }
