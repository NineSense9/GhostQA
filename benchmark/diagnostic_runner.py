"""Diagnostic reruns for v0.3.8. Observability only.

Does not change frozen algorithm files. Tags every row diagnostic_rerun=true.
Not an independent trial: compare confirmed sets to v0.3.7 published metrics.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

from ghostqa.exploration.explorer import run_exploration
from ghostqa.exploration.sequence import branch_clicks, is_hub
from ghostqa.oracle.engine import OracleEngine
from ghostqa.oracle.spec import load_spec
from benchmark.algorithm_freeze import ROOT, assert_frozen
from benchmark.web_runner import (
    APPS, evidence_matches, make_policy, _free_port, _state_model,
)

FREEZE = os.path.join(
    ROOT, "experiments", "frozen", "ghost-structural-v0.3.6", "freeze.json")


def _dump_graph(graph) -> dict:
    nodes = []
    for n in graph.nodes.values():
        d = n.to_dict()
        d["tried_actions"] = sorted(d.get("tried_actions") or [])
        d["observed_actions"] = sorted(d.get("observed_actions") or [])
        nodes.append(d)
    edges = [e.to_dict() for e in graph.edges.values()]
    return {"start": graph.start_sig, "nodes": nodes, "edges": edges}


def _ledger_snap(seq) -> dict:
    if seq is None:
        return {}
    led = seq.ledger
    return {
        "seq_mode": seq.mode,
        "last_label": seq.last_label,
        "commitment_left": led.commitment_left,
        "returning": led.returning,
        "active_branch": led.active_branch,
        "parent_hub_cluster": led.parent_hub_cluster,
    }


def run_diagnostic(base_url, shared, policy_name, seed, budget, spec,
                   manifest, out_dir) -> dict:
    from ghostqa.executor.playwright_web import PlaywrightWebExecutor

    oracle = OracleEngine(spec)
    web = PlaywrightWebExecutor(base_url, headless=True, shared=shared)
    policy = make_policy(policy_name, seed)
    seq = getattr(policy, "sequence", None)
    events = []

    def on_step(ev):
        rec = {
            "kind": "step",
            "index": ev.get("index"),
            "decision_mode": ev.get("decision_mode") or "",
            "action": ev.get("action"),
            "relation": ev.get("relation"),
            "src_url": (ev.get("src") or {}).get("url"),
            "src_title": (ev.get("src") or {}).get("title"),
            "src_cluster": (ev.get("src") or {}).get("cluster_id"),
            "dst_url": (ev.get("dst") or {}).get("url"),
            "dst_title": (ev.get("dst") or {}).get("title"),
            "dst_cluster": (ev.get("dst") or {}).get("cluster_id"),
            "dst_is_new": (ev.get("dst") or {}).get("is_new"),
            "findings": [
                {"kind": f.get("kind"), "assert_id": (f.get("evidence") or {}).get("assert_id"),
                 "error": (f.get("evidence") or {}).get("error")
                 or (f.get("evidence") or {}).get("error_contains")}
                for f in (ev.get("findings") or [])
            ],
            "js_errors": ev.get("js_errors") or [],
            "n_nodes": (ev.get("graph_stats") or {}).get("nodes"),
        }
        rec.update(_ledger_snap(seq))
        events.append(rec)

    orig_after = seq.after if seq is not None else None

    def after_hook(*a, **k):
        orig_after(*a, **k)
        try:
            state = a[2] if len(a) > 2 else None
            snap = _ledger_snap(seq)
            snap["kind"] = "seq_after"
            snap["step"] = a[9] if len(a) > 9 else k.get("step")
            snap["is_hub"] = bool(state is not None and is_hub(state))
            snap["n_branch_clicks"] = len(branch_clicks(state)) if state else 0
            if seq.events:
                snap["last_seq_event"] = seq.events[-1].get("event")
                snap["last_seq_outcome"] = seq.events[-1].get("outcome")
            events.append(snap)
        except Exception:
            pass

    if orig_after is not None:
        seq.after = after_hook

    t0 = time.time()
    result = run_exploration(
        web, policy, budget, oracle=oracle,
        state_model=_state_model(policy_name), on_step=on_step)

    found_ids = set()
    first_step = {}
    for f in result.candidates:
        for bug in manifest:
            if f.kind == bug["kind"] and evidence_matches(f.evidence, bug["match"]):
                found_ids.add(bug["id"])
                st = result.step_for_finding(f)
                idx = None if st is None else st.index
                prev = first_step.get(bug["id"])
                if prev is None or (idx is not None and idx < prev):
                    first_step[bug["id"]] = idx

    os.makedirs(out_dir, exist_ok=True)
    stem = f"{policy_name}_b{budget}_s{seed}"
    with open(os.path.join(out_dir, stem + ".events.jsonl"), "w", encoding="utf-8") as f:
        for rec in events:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    with open(os.path.join(out_dir, stem + ".graph.json"), "w", encoding="utf-8") as f:
        json.dump(_dump_graph(result.graph), f, ensure_ascii=False, indent=2)
    seq_events = list(getattr(result, "sequence_events", None) or (
        seq.events if seq is not None else []))
    with open(os.path.join(out_dir, stem + ".sequence_events.json"), "w",
              encoding="utf-8") as f:
        json.dump(seq_events, f, ensure_ascii=False, indent=2)

    return {
        "policy": policy_name,
        "seed": seed,
        "budget": budget,
        "diagnostic_rerun": True,
        "not_an_independent_trial": True,
        "states": len(result.graph.nodes),
        "clusters": result.graph.cluster_count(),
        "actions": result.actions_executed,
        "confirmed_bugs": sorted(found_ids),
        "first_step_by_bug": first_step,
        "candidates": len(result.candidates),
        "wall_seconds": round(time.time() - t0, 1),
        "trace": stem,
        **(result.sequence_metrics or {}),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", required=True, choices=sorted(APPS))
    ap.add_argument("--manifest", default="bugs.manifest.json")
    ap.add_argument("--policies", required=True)
    ap.add_argument("--budget", type=int, default=120)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    assert_frozen(FREEZE)

    app_dir = APPS[args.app]
    spec = load_spec(os.path.join(app_dir, "spec.json"))
    man = args.manifest
    if not os.path.isabs(man):
        man = os.path.join(app_dir, man)
    with open(man, encoding="utf-8") as f:
        manifest = json.load(f)["bugs"]

    os.makedirs(args.out, exist_ok=True)
    port = _free_port()
    server = subprocess.Popen(
        [sys.executable, os.path.join(app_dir, "server.py"), str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.8)
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    shared = {"pw": pw, "browser": browser}
    rows = []
    try:
        for name in args.policies.split(","):
            row = run_diagnostic(
                f"http://127.0.0.1:{port}", shared, name, 1, args.budget,
                spec, manifest, args.out)
            rows.append(row)
            print(
                f"[diag {name:24s} {args.app} b={args.budget}] "
                f"states={row['states']} confirmed={row['confirmed_bugs']} "
                f"wall={row['wall_seconds']}s",
                flush=True)
    finally:
        browser.close()
        pw.stop()
        server.terminate()

    with open(os.path.join(args.out, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump({"diagnostic_rerun": True, "not_an_independent_trial": True,
                   "runs": rows}, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
