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
from .exploration.metrics import classify_validation, episode_stats
from .exploration.policy import (RandomPolicy, DFSPolicy, BFSPolicy,
                                 LLMNaivePolicy, GhostPolicy,
                                 WorkflowBFSPolicy)
from .minimizer.ddmin import minimize_reproduction
from .oracle.engine import OracleEngine
from .oracle.spec import load_spec, format_spec_brief
from .replay.validator import validate_candidate
from .report.generator import build_report, write_report

POLICIES = ["ghost", "ghost-nollm", "monkey", "dfs", "bfs", "llm-naive",
            "workflow-bfs", "ghost-frontier-r0", "ghost-frontier-marginal",
            "ghost-deferred", "ghost-exploit", "ghost-postreach"]


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
        return GhostPolicy(llm=None, use_frontier=False)
    if name == "ghost-deferred":
        return GhostPolicy(llm=None, use_frontier=False, postreach_mode="deferred")
    if name == "ghost-exploit":
        return GhostPolicy(llm=None, use_frontier=False, postreach_mode="exploit")
    if name == "ghost-postreach":
        return GhostPolicy(llm=None, use_frontier=False, postreach_mode="postreach")
    if name == "ghost-branch":
        return GhostPolicy(llm=None, use_frontier=False, sequence_mode="branch")
    if name == "ghost-followup":
        return GhostPolicy(llm=None, use_frontier=False, sequence_mode="followup")
    if name == "ghost-sequence":
        return GhostPolicy(llm=None, use_frontier=False, sequence_mode="sequence")
    if name == "ghost-structural-memory":
        return GhostPolicy(llm=None, use_frontier=False, sequence_mode="structural")
    if name == "ghost-structural-return-guard":
        # Dashboard/research exposure of the existing experimental class.
        # Product `ghost` default is unchanged (NoFrontier, sequence off).
        from .exploration.return_cycle_guard import ReturnCycleGuardGhostPolicy
        return ReturnCycleGuardGhostPolicy(llm=None)
    if name == "ghost-structural-nested-return-guard":
        # Research-only. Not the product default. v0.3.12 Outcome C.
        from .exploration.nested_hub_guard import NestedHubReturnGuardGhostPolicy
        return NestedHubReturnGuardGhostPolicy(llm=None)
    if name == "ghost-structural-nested-stack-guard":
        # Research-only. Not the product default. Does not replace v0.3.12.
        from .exploration.nested_stack_guard import NestedStackReturnGuardGhostPolicy
        return NestedStackReturnGuardGhostPolicy(llm=None)
    if name == "ghost-contextual":
        return GhostPolicy(llm=None, use_frontier=False, sequence_mode="contextual")
    if name == "ghost-contextual-crossview":
        return GhostPolicy(llm=None, use_frontier=False,
                           sequence_mode="contextual-crossview")
    if name == "ghost-frontier-r0":
        return GhostPolicy(llm=llm, use_frontier=True,
                           relocate_mode="opportunity")
    if name == "ghost-frontier-marginal":
        return GhostPolicy(llm=llm, use_frontier=True,
                           relocate_mode="marginal")
    if name == "ghost-nollm-shadow":
        return GhostPolicy(llm=None, use_frontier=True, relocate_mode="shadow")
    if name == "ghost-nollm-momentum":
        return GhostPolicy(llm=None, use_frontier=True, relocate_mode="momentum")
    if name == "ghost-nollm-lease":
        return GhostPolicy(llm=None, use_frontier=True, relocate_mode="lease")
    if name == "workflow-bfs":
        return WorkflowBFSPolicy()
    # Product Ghost: local policy, Frontier OFF (v0.3.3 conclusion).
    return GhostPolicy(llm=llm, use_frontier=False) if llm else GhostPolicy(
        llm=None, use_frontier=False)


def cmd_run(args) -> int:
    from .executor.playwright_web import PlaywrightWebExecutor

    os.makedirs(args.out, exist_ok=True)
    shots = os.path.join(args.out, "screenshots")
    spec = load_spec(args.spec) if args.spec else []
    oracle = OracleEngine(spec)
    spec_brief = format_spec_brief(spec)
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
        json.dump([result.finding_artifact(x) for x in result.candidates], f,
                  ensure_ascii=False, indent=2)
    result.graph.save(os.path.join(args.out, "graph.json"))
    with open(os.path.join(args.out, "trace.jsonl"), "w", encoding="utf-8") as f:
        for s in result.steps:
            f.write(json.dumps(s.to_dict(), ensure_ascii=False) + "\n")
    with open(os.path.join(args.out, "reset_events.json"), "w", encoding="utf-8") as f:
        json.dump(result.reset_events, f, ensure_ascii=False, indent=2)
    with open(os.path.join(args.out, "relocation_trace.jsonl"), "w",
              encoding="utf-8") as f:
        for rec in result.relocation_decisions:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    confirmed = []
    replay_attempted = replay_pass = replay_fail = replay_invalid = 0
    if not args.no_validate:
        shared = web.share_handle()
        factory = lambda: PlaywrightWebExecutor(args.url, headless=True,
                                                shared=shared)
        for finding in result.candidates:
            replay_attempted += 1
            repro_actions = result.reproduction_actions(finding)
            vr = validate_candidate(factory, repro_actions, finding, oracle)
            bucket = classify_validation(vr)
            if bucket == "pass":
                replay_pass += 1
                repro = minimize_reproduction(factory, repro_actions, finding, oracle)
                confirmed.append(result.make_confirmed(finding, repro))
            elif bucket == "invalid":
                replay_invalid += 1
            else:
                replay_fail += 1
    web.close()

    with open(os.path.join(args.out, "confirmed_bugs.json"), "w", encoding="utf-8") as f:
        json.dump([b.to_dict() for b in confirmed], f, ensure_ascii=False, indent=2)

    config = {"url": args.url, "policy": policy.name, "budget": args.budget,
              "seed": args.seed, "spec": args.spec, "mock_llm": args.mock_llm}
    report = build_report(result, confirmed, config)
    write_report(report, os.path.join(args.out, "report.json"),
                 os.path.join(args.out, "report.html"))
    ep = episode_stats(result)
    metrics = {
        "config": config,
        "wall_seconds": round(time.time() - t0, 2),
        "actions": result.actions_executed,
        "repeat_actions": result.repeat_actions,
        "states": len(result.graph.nodes),
        "edges": len(result.graph.edges),
        "candidates": len(result.candidates),
        "candidate_count": len(result.candidates),
        "matched_candidate_count": len(result.candidates),
        "confirmed": len(confirmed),
        "confirmed_bug_count": len(confirmed),
        "replay_attempted": replay_attempted,
        "replay_pass": replay_pass,
        "replay_fail": replay_fail,
        "replay_invalid": replay_invalid,
        "replay_success_rate": (
            round(replay_pass / replay_attempted, 3) if replay_attempted else None),
        **ep,
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
