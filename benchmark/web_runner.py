"""WebBench: real-browser benchmark of exploration policies against BuggyShop.

Layer B of GhostBench. Starts BuggyShop locally, runs each policy x seed,
validates+minimizes findings, and aggregates mean/std/min/max.

    python -m benchmark.web_runner --budget 40 --seeds 1,2 \
        --out experiments/published/webbench-v0.2
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
from ghostqa.exploration.policy import (RandomPolicy, DFSPolicy, BFSPolicy,
                                        LLMNaivePolicy, GhostPolicy)
from ghostqa.minimizer.ddmin import minimize_reproduction
from ghostqa.oracle.engine import OracleEngine
from ghostqa.oracle.spec import load_spec
from ghostqa.replay.validator import validate_candidate
from ghostqa.state.models import ConfirmedBug
from benchmark.runner import evidence_matches

APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "apps", "buggy-shop")


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
        return GhostPolicy(llm=None)
    if name == "ghost-full":
        return GhostPolicy(llm=MockLLM())
    raise ValueError(name)


def run_one(base_url: str, shared, policy_name: str, seed: int, budget: int,
            spec, manifest, skip_minimize: bool) -> dict:
    from ghostqa.executor.playwright_web import PlaywrightWebExecutor

    oracle = OracleEngine(spec)
    spec_brief = "; ".join(a["id"] for a in spec)
    web = PlaywrightWebExecutor(base_url, headless=True, shared=shared)
    policy = make_policy(policy_name, seed)
    t0 = time.time()
    result = run_exploration(web, policy, budget, oracle=oracle,
                             spec_brief=spec_brief)

    found_ids = set()
    for f in result.candidates:
        for bug in manifest:
            if f.kind == bug["kind"] and evidence_matches(f.evidence, bug["match"]):
                found_ids.add(bug["id"])

    factory = lambda: PlaywrightWebExecutor(base_url, headless=True, shared=shared)
    confirmed_ids, replay_ok, replay_total, min_ratios = set(), 0, 0, []
    for f in result.candidates:
        ids = {b["id"] for b in manifest
               if f.kind == b["kind"] and evidence_matches(f.evidence, b["match"])}
        if not ids:
            continue
        replay_total += 1
        vr = validate_candidate(factory, result.actions(), f, oracle)
        if not vr.confirmed:
            continue
        replay_ok += 1
        confirmed_ids |= ids
        if not skip_minimize:
            repro = minimize_reproduction(factory, result.actions(), f, oracle)
            if f.step_index + 1 > 0 and repro:
                min_ratios.append(len(repro) / (f.step_index + 1))
    web.close()

    first_bug = next((s.index for s in result.steps if s.findings), None)
    return {
        "policy": policy_name, "seed": seed, "budget": budget,
        "actions": result.actions_executed,
        "states": len(result.graph.nodes),
        "candidates": len(result.candidates),
        "bugs_found": sorted(found_ids),
        "confirmed_bugs": sorted(confirmed_ids),
        "bug_discovery_rate": round(len(confirmed_ids) / len(manifest), 3),
        "time_to_first_bug": first_bug,
        "repeat_rate": round(result.repeat_actions / max(1, result.actions_executed), 3),
        "replay_success_rate": round(replay_ok / replay_total, 3) if replay_total else None,
        "min_repro_ratio": round(statistics.mean(min_ratios), 3) if min_ratios else None,
        "llm_calls": result.llm_calls,
        "tokens": result.pseudo_tokens,
        "wall_seconds": round(time.time() - t0, 1),
    }


def aggregate(rows: list) -> list:
    by_policy: dict = {}
    for r in rows:
        by_policy.setdefault(r["policy"], []).append(r)
    out = []
    for policy, rs in by_policy.items():
        rates = [r["bug_discovery_rate"] for r in rs]
        t2b = [r["time_to_first_bug"] for r in rs
               if r["time_to_first_bug"] is not None]
        out.append({
            "policy": policy,
            "runs": len(rs),
            "bugs_mean": round(statistics.mean(rates), 3),
            "bugs_std": round(statistics.stdev(rates), 3) if len(rates) > 1 else 0.0,
            "bugs_min": min(rates), "bugs_max": max(rates),
            "t2bug_mean": round(statistics.mean(t2b), 1) if t2b else None,
            "states_mean": round(statistics.mean(r["states"] for r in rs), 1),
            "repeat_rate_mean": round(statistics.mean(r["repeat_rate"] for r in rs), 3),
            "llm_calls_mean": round(statistics.mean(r["llm_calls"] for r in rs), 1),
            "wall_mean_s": round(statistics.mean(r["wall_seconds"] for r in rs), 1),
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=40)
    ap.add_argument("--seeds", type=str, default="1,2")
    ap.add_argument("--policies", type=str,
                    default="monkey,dfs,bfs,ghost-nollm,ghost-full")
    ap.add_argument("--skip-minimize", action="store_true")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    spec = load_spec(os.path.join(APP_DIR, "spec.json"))
    with open(os.path.join(APP_DIR, "bugs.manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)["bugs"]
    seeds = [int(s) for s in args.seeds.split(",")]
    policies = args.policies.split(",")
    os.makedirs(args.out, exist_ok=True)

    port = _free_port()
    server = subprocess.Popen(
        [sys.executable, os.path.join(APP_DIR, "server.py"), str(port)],
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
            for seed in seeds:
                row = run_one(base_url, shared, policy, seed, args.budget,
                              spec, manifest, args.skip_minimize)
                rows.append(row)
                print(f"[{policy:11s} seed={seed}] "
                      f"bugs={row['bug_discovery_rate']:.2f} "
                      f"confirmed={len(row['confirmed_bugs'])} states={row['states']} "
                      f"cand={row['candidates']} t2bug={row['time_to_first_bug']} "
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
              f"[{a['bugs_min']},{a['bugs_max']}] t2bug={a['t2bug_mean']} "
              f"states={a['states_mean']} llm={a['llm_calls_mean']}")
    print(f"\nmetrics -> {os.path.join(args.out, 'metrics.json')}")


if __name__ == "__main__":
    main()
