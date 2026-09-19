"""GhostBench runner: policy x app matrix experiment with validation+minimization.

Usage:
    python -m benchmark.runner --budget 120 --out experiments/runs/latest
"""
from __future__ import annotations

import argparse
import json
import os
import time

from ghostqa.agent.gateway import MockLLM
from ghostqa.executor.sim import SimExecutor
from ghostqa.exploration.explorer import run_exploration
from ghostqa.exploration.metrics import (
    classify_validation, episode_stats, latency_metrics,
)
from ghostqa.exploration.policy import (RandomPolicy, DFSPolicy, BFSPolicy,
                                        LLMNaivePolicy, GhostPolicy)
from ghostqa.minimizer.ddmin import minimize_reproduction
from ghostqa.oracle.engine import OracleEngine
from ghostqa.oracle.spec import format_spec_brief
from ghostqa.replay.validator import validate_candidate
from benchmark.sim_apps import APPS


def evidence_matches(evidence: dict, match: dict) -> bool:
    """Match semantics: exact equality; key suffix '_contains' = substring match."""
    for k, v in match.items():
        if k.endswith("_contains"):
            if v not in str(evidence.get(k[:-len("_contains")], "")):
                return False
        elif evidence.get(k) != v:
            return False
    return True


def match_manifest(candidates, manifest) -> set:
    """Map findings to seeded bug ids. Every manifest entry must carry
    discriminating match keys so one finding can only hit its own bug."""
    _check_manifest_discriminative(manifest)
    found = set()
    for f in candidates:
        for bug in manifest:
            if f.kind != bug["kind"]:
                continue
            if bug["match"] and evidence_matches(f.evidence, bug["match"]):
                found.add(bug["id"])
    return found


def _check_manifest_discriminative(manifest):
    seen = {}
    for bug in manifest:
        key = (bug["kind"], json.dumps(bug["match"], sort_keys=True, default=str))
        if key in seen:
            raise ValueError(
                f"manifest entries {seen[key]} and {bug['id']} are indistinguishable "
                f"(same kind+match) - add discriminating match keys")
        seen[key] = bug["id"]
    for bug in manifest:
        if not bug["match"]:
            import warnings
            warnings.warn(f"manifest {bug['id']} has empty match - "
                          f"any {bug['kind']} finding will count as this bug")


def run_one(app_name: str, make_app, policy, budget: int, validate: bool = True) -> dict:
    app, spec, manifest = make_app()
    factory = lambda: SimExecutor(make_app()[0])
    oracle = OracleEngine(spec)
    spec_brief = format_spec_brief(spec)

    executor = SimExecutor(app)
    result = run_exploration(executor, policy, budget, oracle=oracle, spec_brief=spec_brief)

    found_ids = match_manifest(result.candidates, manifest)
    confirmed_bugs, confirmed_ids = [], set()
    first_step = {}
    replay_attempted = replay_pass = replay_fail = replay_invalid = 0
    if validate:
        for f in result.candidates:
            ids = {b["id"] for b in manifest
                   if b["kind"] == f.kind and b["match"]
                   and evidence_matches(f.evidence, b["match"])}
            if not ids:
                continue
            replay_attempted += 1
            repro_actions = result.reproduction_actions(f)
            vr = validate_candidate(factory, repro_actions, f, oracle)
            bucket = classify_validation(vr)
            if bucket != "pass":
                if bucket == "invalid":
                    replay_invalid += 1
                else:
                    replay_fail += 1
                continue
            replay_pass += 1
            repro = minimize_reproduction(factory, repro_actions, f, oracle)
            confirmed_bugs.append(result.make_confirmed(f, repro))
            confirmed_ids |= ids
            for bid in ids:
                first_step[bid] = min(first_step.get(bid, f.step_index), f.step_index)

    lat = latency_metrics(result, first_step)
    return {
        "app": app_name,
        "policy": policy.name,
        "budget": budget,
        "actions": result.actions_executed,
        "states": len(result.graph.nodes),
        "edges": len(result.graph.edges),
        "candidates": len(result.candidates),
        "candidate_count": len(result.candidates),
        "bugs_found": sorted(found_ids),
        "bug_discovery_rate": round(len(found_ids) / len(manifest), 3),
        "confirmed_bugs": sorted(confirmed_ids),
        "confirmed_bug_count": len(confirmed_ids),
        "replay_attempted": replay_attempted,
        "replay_pass": replay_pass,
        "replay_fail": replay_fail,
        "replay_invalid": replay_invalid,
        **lat,
        **episode_stats(result),
        "repeat_actions": result.repeat_actions,
        "llm_calls": result.llm_calls,
        "pseudo_tokens": result.pseudo_tokens,
        "min_repro_lengths": {b.finding.fingerprint(): len(b.reproduction)
                              for b in confirmed_bugs},
        "wall_seconds": round(result.wall_seconds, 2),
    }


def make_policies(seed: int) -> list:
    return [
        RandomPolicy(seed=seed),
        DFSPolicy(),
        BFSPolicy(),
        LLMNaivePolicy(MockLLM()),
        GhostPolicy(llm=None),               # ablation: no LLM
        GhostPolicy(llm=MockLLM()),          # full
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=120)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=str, default="")
    ap.add_argument("--no-validate", action="store_true")
    args = ap.parse_args()

    out_dir = args.out or os.path.join(
        "experiments", "runs", time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(out_dir, exist_ok=True)

    rows = []
    for app_name, make_app in APPS.items():
        for policy in make_policies(args.seed):
            row = run_one(app_name, make_app, policy, args.budget,
                          validate=not args.no_validate)
            rows.append(row)
            print(f"[{app_name:9s}] {row['policy']:10s} "
                  f"bugs={row['bug_discovery_rate']:.2f} states={row['states']:3d} "
                  f"cand={row['candidates']:2d} confirmed={len(row['confirmed_bugs']):2d} "
                  f"llm={row['llm_calls']:3d} TTF={row['ttf']} TTCB={row['ttcb']}")

    metrics_path = os.path.join(out_dir, "metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump({"config": vars(args), "rows": rows}, f, ensure_ascii=False, indent=2)
    print(f"\nmetrics -> {metrics_path}")


if __name__ == "__main__":
    main()
