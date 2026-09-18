"""GhostQA CLI.

    python -m ghostqa run \
        --url http://127.0.0.1:3939 \
        --policy ghost \
        --budget 60 \
        --spec apps/buggy-shop/spec.json \
        --out runs/demo [--mock-llm] [--no-validate] [--headed]

Artifacts in --out:
    trace.jsonl graph.json findings.json confirmed_bugs.json
    report.json report.html metrics.json screenshots/
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from .agent.gateway import MockLLM, NullLLM, OpenAICompatibleGateway
from .exploration.explorer import run_exploration
from .exploration.policy import (RandomPolicy, DFSPolicy, BFSPolicy,
                                 LLMNaivePolicy, GhostPolicy)
from .minimizer.ddmin import minimize_reproduction
from .oracle.engine import OracleEngine
from .oracle.spec import load_spec
from .replay.validator import validate_candidate
from .report.generator import build_report, write_report
from .state.models import ConfirmedBug

POLICIES = ["ghost", "ghost-nollm", "monkey", "dfs", "bfs", "llm-naive"]


def _make_llm(args):
    if args.mock_llm:
        return MockLLM()
    gw = OpenAICompatibleGateway()
    if gw.available:
        print(f"[ghostqa] LLM: {gw.model} @ {gw.base_url}")
        return gw
    if args.llm:
        print("[ghostqa] WARNING: LLM requested but not configured "
              "(GHOSTQA_MODEL_* env vars) - falling back to no-LLM", file=sys.stderr)
    return None


def _make_policy(name: str, llm, seed: int):
    if name == "monkey":
        return RandomPolicy(seed=seed)
    if name == "dfs":
        return DFSPolicy()
    if name == "bfs":
        return BFSPolicy()
    if name == "llm-naive":
        return LLMNaivePolicy(llm or MockLLM())
    if name == "ghost-nollm":
        return GhostPolicy(llm=None)
    return GhostPolicy(llm=llm) if llm else GhostPolicy(llm=None)


def cmd_run(args) -> int:
    from .executor.playwright_web import PlaywrightWebExecutor

    os.makedirs(args.out, exist_ok=True)
    shots = os.path.join(args.out, "screenshots")
    spec = load_spec(args.spec) if args.spec else []
    oracle = OracleEngine(spec)
    spec_brief = "; ".join(a["id"] for a in spec)
    llm = _make_llm(args)
    policy = _make_policy(args.policy, llm, args.seed)

    web = PlaywrightWebExecutor(args.url, headless=not args.headed,
                                screenshots_dir=shots)
    t0 = time.time()
    try:
        result = run_exploration(web, policy, args.budget, oracle=oracle,
                                 spec_brief=spec_brief)
    finally:
        pass

    findings_path = os.path.join(args.out, "findings.json")
    with open(findings_path, "w", encoding="utf-8") as f:
        json.dump([x.to_dict() for x in result.candidates], f,
                  ensure_ascii=False, indent=2)
    result.graph.save(os.path.join(args.out, "graph.json"))
    with open(os.path.join(args.out, "trace.jsonl"), "w", encoding="utf-8") as f:
        for s in result.steps:
            f.write(json.dumps(s.to_dict(), ensure_ascii=False) + "\n")

    confirmed = []
    if not args.no_validate:
        shared = web.share_handle()
        factory = lambda: PlaywrightWebExecutor(args.url, headless=True,
                                                shared=shared)
        for finding in result.candidates:
            vr = validate_candidate(factory, result.actions(), finding, oracle)
            if not vr.confirmed:
                continue
            repro = minimize_reproduction(factory, result.actions(), finding, oracle)
            confirmed.append(ConfirmedBug(finding=finding, reproduction=repro,
                                          original_length=finding.step_index + 1))
    web.close()

    with open(os.path.join(args.out, "confirmed_bugs.json"), "w", encoding="utf-8") as f:
        json.dump([b.to_dict() for b in confirmed], f, ensure_ascii=False, indent=2)

    config = {"url": args.url, "policy": policy.name, "budget": args.budget,
              "seed": args.seed, "spec": args.spec, "mock_llm": args.mock_llm}
    report = build_report(result, confirmed, config)
    write_report(report, os.path.join(args.out, "report.json"),
                 os.path.join(args.out, "report.html"))
    metrics = {
        "config": config,
        "wall_seconds": round(time.time() - t0, 2),
        "actions": result.actions_executed,
        "repeat_actions": result.repeat_actions,
        "states": len(result.graph.nodes),
        "edges": len(result.graph.edges),
        "candidates": len(result.candidates),
        "confirmed": len(confirmed),
        "llm_calls": result.llm_calls,
        "tokens": result.pseudo_tokens,
        "min_repro_lengths": {b.finding.fingerprint(): len(b.reproduction)
                              for b in confirmed},
    }
    with open(os.path.join(args.out, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    print(f"[ghostqa] done: {len(confirmed)} confirmed bugs / "
          f"{len(result.candidates)} candidates, "
          f"{len(result.graph.nodes)} states, "
          f"report -> {os.path.join(args.out, 'report.html')}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="ghostqa")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run an exploratory test")
    run.add_argument("--url", required=True)
    run.add_argument("--policy", default="ghost", choices=POLICIES)
    run.add_argument("--budget", type=int, default=60)
    run.add_argument("--spec", default="")
    run.add_argument("--out", required=True)
    run.add_argument("--seed", type=int, default=0)
    run.add_argument("--mock-llm", action="store_true")
    run.add_argument("--llm", action="store_true",
                     help="use real LLM via GHOSTQA_MODEL_* env vars")
    run.add_argument("--no-validate", action="store_true")
    run.add_argument("--headed", action="store_true",
                     help="show the browser window")
    args = parser.parse_args(argv)
    if args.cmd == "run":
        return cmd_run(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
