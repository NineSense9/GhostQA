"""WebBench: real-browser benchmark of exploration policies.

    python -m benchmark.web_runner --app buggy-shop --budget 40 --seeds 1,2 \
        --out experiments/published/webbench-v0.2

    python -m benchmark.web_runner --app buggy-flow --budgets 20,40,80 \
        --seeds 1,2,3 --skip-minimize --out experiments/published/deepbench-v0.3
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import statistics
import subprocess
import sys
import time

from ghostqa.agent.gateway import MockLLM
from ghostqa.exploration.explorer import run_exploration
from ghostqa.exploration.metrics import (
    classify_validation, episode_stats, latency_metrics,
)
from ghostqa.exploration.policy import (RandomPolicy, DFSPolicy, BFSPolicy,
                                        LLMNaivePolicy, GhostPolicy,
                                        WorkflowBFSPolicy)
from ghostqa.minimizer.ddmin import minimize_reproduction
from ghostqa.oracle.engine import OracleEngine
from ghostqa.oracle.spec import load_spec, format_spec_brief
from ghostqa.replay.validator import validate_candidate
from benchmark.runner import evidence_matches

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPS = {
    "buggy-shop": os.path.join(ROOT, "apps", "buggy-shop"),
    "buggy-flow": os.path.join(ROOT, "apps", "buggy-flow"),
}
DEEP_DEPTH = 4


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def make_policy(name: str, seed: int):
    if name == "monkey":
        return RandomPolicy(seed=seed)
    if name == "dfs":
        return DFSPolicy()
    if name == "bfs":
        return BFSPolicy()
    if name == "llm-naive":
        return LLMNaivePolicy(MockLLM())
    if name == "ghost-nollm":
        # Product-aligned v0.3.4 default: NoFrontier.
        return GhostPolicy(llm=None, use_frontier=False)
    if name == "ghost-nollm-nofrontier":
        return GhostPolicy(llm=None, use_frontier=False)
    if name == "ghost-deferred":
        return GhostPolicy(llm=None, use_frontier=False, postreach_mode="deferred")
    if name == "ghost-exploit":
        return GhostPolicy(llm=None, use_frontier=False, postreach_mode="exploit")
    if name == "ghost-postreach":
        return GhostPolicy(llm=None, use_frontier=False, postreach_mode="postreach")
    if name == "workflow-bfs-postreach":
        return WorkflowBFSPolicy(postreach_mode="postreach")
    if name == "ghost-frontier-r0":
        # Historical v0.3.2 / v0.3.3 R0 (explicit, not the constructor default).
        return GhostPolicy(llm=None, use_frontier=True,
                           relocate_mode="opportunity")
    if name == "ghost-frontier-marginal":
        return GhostPolicy(llm=None, use_frontier=True,
                           relocate_mode="marginal")
    if name == "ghost-nollm-shadow":
        return GhostPolicy(llm=None, use_frontier=True, relocate_mode="shadow")
    if name == "ghost-nollm-marginal":
        return GhostPolicy(llm=None, use_frontier=True, relocate_mode="marginal")
    if name == "ghost-nollm-momentum":
        return GhostPolicy(llm=None, use_frontier=True, relocate_mode="momentum")
    if name == "ghost-nollm-lease":
        return GhostPolicy(llm=None, use_frontier=True, relocate_mode="lease")
    if name == "ghost-full":
        return GhostPolicy(llm=MockLLM(), use_frontier=True)
    if name == "ghost-nofrontier":
        return GhostPolicy(llm=MockLLM(), use_frontier=False)
    if name == "ghost-nosemantic":
        return GhostPolicy(llm=MockLLM(), use_frontier=True, use_semantic_state=False)
    if name == "workflow-bfs":
        return WorkflowBFSPolicy()
    if name == "ghost-oldinput":
        return GhostPolicy(llm=MockLLM(), use_frontier=True, progressive=False,
                           relocate_mode="exhaustion")
    raise ValueError(name)


def _state_model(policy_name: str) -> str:
    return "structural" if policy_name == "ghost-nosemantic" else "semantic"


def _auc(first_steps: list, budget: int, n_bugs: int) -> float:
    """Area under (actions → confirmed bugs) curve, normalised by budget * n_bugs."""
    if not n_bugs or not budget:
        return 0.0
    hits = sorted(t for t in first_steps if t is not None)
    found, area, i = 0, 0.0, 0
    for t in range(budget):
        while i < len(hits) and hits[i] <= t:
            found += 1
            i += 1
        area += found
    return round(area / (budget * n_bugs), 3)


def run_one(base_url: str, shared, policy_name: str, seed: int, budget: int,
            spec, manifest, skip_minimize: bool, trace_dir: str = "") -> dict:
    from ghostqa.executor.playwright_web import PlaywrightWebExecutor

    oracle = OracleEngine(spec)
    spec_brief = format_spec_brief(spec)
    web = PlaywrightWebExecutor(base_url, headless=True, shared=shared)
    policy = make_policy(policy_name, seed)
    t0 = time.time()
    result = run_exploration(web, policy, budget, oracle=oracle,
                             spec_brief=spec_brief,
                             state_model=_state_model(policy_name))

    found_ids = set()
    for f in result.candidates:
        for bug in manifest:
            if f.kind == bug["kind"] and evidence_matches(f.evidence, bug["match"]):
                found_ids.add(bug["id"])

    factory = lambda: PlaywrightWebExecutor(base_url, headless=True, shared=shared)
    confirmed_ids, min_ratios = set(), []
    first_step = {}
    candidate_episode_ids = []
    candidates_after_reset = 0
    confirmed_after_reset = 0
    matched_candidate_count = 0
    replay_attempted = replay_pass = replay_fail = replay_invalid = 0
    for f in result.candidates:
        step = result.step_for_finding(f)
        eid = 0 if step is None else step.episode_id
        candidate_episode_ids.append(eid)
        if eid > 0:
            candidates_after_reset += 1
        ids = {b["id"] for b in manifest
               if f.kind == b["kind"] and evidence_matches(f.evidence, b["match"])}
        if not ids:
            continue
        matched_candidate_count += 1
        replay_attempted += 1
        repro_actions = result.reproduction_actions(f)
        vr = validate_candidate(factory, repro_actions, f, oracle)
        bucket = classify_validation(vr)
        if bucket == "pass":
            replay_pass += 1
            confirmed_ids |= ids
            if eid > 0:
                confirmed_after_reset += 1
            for bid in ids:
                first_step[bid] = min(first_step.get(bid, f.step_index), f.step_index)
            if not skip_minimize:
                repro = minimize_reproduction(factory, repro_actions, f, oracle)
                if repro_actions and repro:
                    min_ratios.append(len(repro) / len(repro_actions))
        elif bucket == "invalid":
            replay_invalid += 1
        else:
            replay_fail += 1
    web.close()

    deep = [b for b in manifest if b.get("trigger_depth", 0) >= DEEP_DEPTH]
    deep_ids = {b["id"] for b in deep}
    confirmed_deep = confirmed_ids & deep_ids
    by_depth = {}
    for b in manifest:
        d = str(b.get("trigger_depth", "?"))
        by_depth.setdefault(d, {"total": 0, "confirmed": 0})
        by_depth[d]["total"] += 1
        if b["id"] in confirmed_ids:
            by_depth[d]["confirmed"] += 1
    lat = latency_metrics(result, first_step, confirmed_deep)
    ep = episode_stats(result)
    row = {
        "policy": policy_name, "seed": seed, "budget": budget,
        "actions": result.actions_executed,
        "states": len(result.graph.nodes),
        "clusters": result.graph.cluster_count(),
        "variants": result.graph.variant_count(),
        "relocate_count": result.relocate_count,
        "restore_failures": result.restore_failures,
        "similarity": dict(result.graph.similarity_counts),
        "candidates": len(result.candidates),
        "candidate_count": len(result.candidates),
        "matched_candidate_count": matched_candidate_count,
        "confirmed_bug_count": len(confirmed_ids),
        "bugs_found": sorted(found_ids),
        "confirmed_bugs": sorted(confirmed_ids),
        "bug_discovery_rate": round(len(confirmed_ids) / len(manifest), 3),
        "deep_bug_discovery_rate": round(len(confirmed_deep) / len(deep), 3) if deep else None,
        "discovery_auc": _auc(list(first_step.values()), budget, len(manifest)),
        **lat,
        "bugs_by_depth": by_depth,
        "repeat_rate": round(result.repeat_actions / max(1, result.actions_executed), 3),
        "replay_attempted": replay_attempted,
        "replay_pass": replay_pass,
        "replay_fail": replay_fail,
        "replay_invalid": replay_invalid,
        "replay_success_rate": (
            round(replay_pass / replay_attempted, 3) if replay_attempted else None),
        "candidates_after_reset": candidates_after_reset,
        "confirmed_after_reset": confirmed_after_reset,
        "candidate_episode_ids": candidate_episode_ids,
        **ep,
        "reset_events": list(result.reset_events),
        "min_repro_ratio": round(statistics.mean(min_ratios), 3) if min_ratios else None,
        "llm_calls": result.llm_calls,
        "tokens": result.pseudo_tokens,
        "wall_seconds": round(time.time() - t0, 1),
        "restore_actions": result.restore_actions,
        "restore_ratio": result.restore_ratio,
        "productive_actions": result.productive_actions,
        "input_actions_executed": result.input_actions_executed,
        "input_action_share": result.input_action_share,
        "unique_inputs_touched": result.unique_inputs_touched,
        "progress_actions": result.progress_actions,
        "max_workflow_depth": result.max_workflow_depth,
        "raw_action_count_mean": result.raw_action_count_mean,
        "interaction_opportunity_mean": result.interaction_opportunity_mean,
        "first_step_by_bug": first_step,
        **(result.relocation_metrics or {}),
        **(result.postreach_metrics or {}),
    }
    if trace_dir:
        os.makedirs(trace_dir, exist_ok=True)
        tpath = os.path.join(
            trace_dir, f"{policy_name}_b{budget}_s{seed}.jsonl")
        with open(tpath, "w", encoding="utf-8") as tf:
            for rec in result.relocation_decisions:
                tf.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return row


def aggregate(rows: list) -> list:
    by_policy: dict = {}
    for r in rows:
        by_policy.setdefault(r["policy"], []).append(r)
    out = []
    for policy, rs in by_policy.items():
        rates = [r["bug_discovery_rate"] for r in rs]
        deeps = [r["deep_bug_discovery_rate"] for r in rs
                 if r.get("deep_bug_discovery_rate") is not None]
        aucs = [r.get("discovery_auc", 0) for r in rs]
        ttf = [r["ttf"] for r in rs if r.get("ttf") is not None]
        ttcb = [r["ttcb"] for r in rs if r.get("ttcb") is not None]
        ttdcb = [r["ttdcb"] for r in rs if r.get("ttdcb") is not None]
        budgets = sorted({r["budget"] for r in rs})
        out.append({
            "policy": policy,
            "runs": len(rs),
            "budgets": budgets,
            "bugs_mean": round(statistics.mean(rates), 3),
            "bugs_std": round(statistics.stdev(rates), 3) if len(rates) > 1 else 0.0,
            "bugs_min": min(rates), "bugs_max": max(rates),
            "deep_mean": round(statistics.mean(deeps), 3) if deeps else None,
            "auc_mean": round(statistics.mean(aucs), 3) if aucs else None,
            "ttf_mean": round(statistics.mean(ttf), 1) if ttf else None,
            "ttcb_mean": round(statistics.mean(ttcb), 1) if ttcb else None,
            "ttdcb_mean": round(statistics.mean(ttdcb), 1) if ttdcb else None,
            "t2bug_mean": round(statistics.mean(ttf), 1) if ttf else None,  # deprecated TTF
            "replay_pass_sum": sum(r.get("replay_pass", 0) for r in rs),
            "replay_fail_sum": sum(r.get("replay_fail", 0) for r in rs),
            "replay_invalid_sum": sum(r.get("replay_invalid", 0) for r in rs),
            "episode_count_mean": round(
                statistics.mean(r.get("episode_count", 0) for r in rs), 2),
            "relocate_episode_mean": round(
                statistics.mean(r.get("relocate_episode_count", 0) for r in rs), 2),
            "states_mean": round(statistics.mean(r["states"] for r in rs), 1),
            "clusters_mean": round(statistics.mean(r.get("clusters", 0) for r in rs), 1),
            "relocate_mean": round(statistics.mean(r.get("relocate_count", 0) for r in rs), 2),
            "repeat_rate_mean": round(statistics.mean(r["repeat_rate"] for r in rs), 3),
            "llm_calls_mean": round(statistics.mean(r["llm_calls"] for r in rs), 1),
            "wall_mean_s": round(statistics.mean(r["wall_seconds"] for r in rs), 1),
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default="buggy-shop", choices=sorted(APPS))
    ap.add_argument("--budget", type=int, default=40)
    ap.add_argument("--budgets", type=str, default="",
                    help="comma-separated budgets; overrides --budget")
    ap.add_argument("--seeds", type=str, default="1,2")
    ap.add_argument("--policies", type=str,
                    default="monkey,dfs,bfs,ghost-nollm,ghost-full")
    ap.add_argument("--skip-minimize", action="store_true")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    app_dir = APPS[args.app]
    spec = load_spec(os.path.join(app_dir, "spec.json"))
    with open(os.path.join(app_dir, "bugs.manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)["bugs"]
    seeds = [int(s) for s in args.seeds.split(",")]
    policies = args.policies.split(",")
    budgets = [int(x) for x in args.budgets.split(",") if x.strip()] or [args.budget]
    os.makedirs(args.out, exist_ok=True)

    port = _free_port()
    server = subprocess.Popen(
        [sys.executable, os.path.join(app_dir, "server.py"), str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base_url = f"http://127.0.0.1:{port}"
    time.sleep(0.8)

    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    shared = {"pw": pw, "browser": browser}

    rows = []
    try:
        for policy in policies:
            for budget in budgets:
                for seed in seeds:
                    row = run_one(base_url, shared, policy, seed, budget,
                                  spec, manifest, args.skip_minimize,
                                  trace_dir=os.path.join(args.out, "relocation_traces"))
                    rows.append(row)
                    print(f"[{policy:16s} bud={budget} seed={seed}] "
                          f"bdr={row['bug_discovery_rate']:.2f} "
                          f"deep={row['deep_bug_discovery_rate']} "
                          f"auc={row['discovery_auc']} "
                          f"confirmed={len(row['confirmed_bugs'])} "
                          f"states={row['states']}/{row['clusters']}c "
                          f"reloc={row['relocate_count']} "
                          f"prod={row.get('productive_relocate_rate')} "
                          f"waste={row.get('wasted_relocate_rate')} "
                          f"ep={row['episode_count']} "
                          f"replay={row['replay_pass']}/{row['replay_fail']}/{row['replay_invalid']} "
                          f"TTF={row['ttf']} TTCB={row['ttcb']} "
                          f"depth={row.get('max_workflow_depth')} "
                          f"def={row.get('deferred_payloads_executed')} "
                          f"exp={row.get('exploit_actions')} "
                          f"llm={row['llm_calls']} wall={row['wall_seconds']}s",
                          flush=True)
    finally:
        browser.close()
        pw.stop()
        server.terminate()

    agg = aggregate(rows)
    with open(os.path.join(args.out, "config.json"), "w", encoding="utf-8") as f:
        json.dump(vars(args), f, indent=2)
    with open(os.path.join(args.out, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump({"runs": rows, "aggregate": agg}, f, ensure_ascii=False, indent=2)

    print("\n== aggregate (confirmed bug discovery rate) ==")
    for a in agg:
        print(f"{a['policy']:11s} mean={a['bugs_mean']:.3f}±{a['bugs_std']:.3f} "
              f"[{a['bugs_min']},{a['bugs_max']}] TTF={a['ttf_mean']} "
              f"TTCB={a['ttcb_mean']} states={a['states_mean']} "
              f"llm={a['llm_calls_mean']}")
    print(f"\nmetrics -> {os.path.join(args.out, 'metrics.json')}")


if __name__ == "__main__":
    main()
