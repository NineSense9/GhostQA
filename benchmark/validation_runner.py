"""v0.3.7 generalization runner.

Reuses benchmark.web_runner.make_policy / run_one. Judge loads the
declared manifest after exploration. Policy never receives it.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

from ghostqa.oracle.spec import load_spec
from benchmark.algorithm_freeze import assert_frozen, ROOT
from benchmark.web_runner import (
    APPS, aggregate, make_policy, run_one, _free_port,
)

PROTOCOL_DEFAULT = os.path.join(
    ROOT, "experiments", "validation", "v0.3.7", "protocol.json")


def load_protocol(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def mark_executed(path: str, extra: dict) -> None:
    proto = load_protocol(path)
    proto["executed"] = True
    proto["execution"] = extra
    with open(path, "w", encoding="utf-8") as f:
        json.dump(proto, f, indent=2)
        f.write("\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--protocol", default=PROTOCOL_DEFAULT)
    ap.add_argument("--target", required=True, choices=["holdout", "buggy-shop"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--rerun-for-repro", action="store_true")
    ap.add_argument("--skip-minimize", action="store_true", default=True)
    args = ap.parse_args()

    proto = load_protocol(args.protocol)
    if proto.get("executed") and args.target == "holdout" and not args.rerun_for_repro:
        print("abort: protocol already executed; use --rerun-for-repro",
              file=sys.stderr)
        return 2

    freeze_path = proto.get("algorithm_freeze") or ""
    if freeze_path and not os.path.isabs(freeze_path):
        freeze_path = os.path.join(ROOT, freeze_path.replace("/", os.sep))
    if freeze_path:
        assert_frozen(freeze_path)

    if args.target == "holdout":
        spec_t = proto["v1_holdout"]
    else:
        spec_t = proto["v2_buggy_shop"]
    app = spec_t["app"]
    app_dir = APPS[app]
    man = spec_t["manifest"]
    man_path = man if os.path.isabs(man) else os.path.join(app_dir, man)

    spec = load_spec(os.path.join(app_dir, "spec.json"))
    with open(man_path, encoding="utf-8") as f:
        manifest = json.load(f)["bugs"]

    policies = list(proto["policies"])
    budgets = list(proto["budgets"])
    seeds = list(proto.get("trials") or [1])
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
            make_policy(policy, seeds[0])  # fail fast on unknown names
            for budget in budgets:
                for seed in seeds:
                    row = run_one(
                        base_url, shared, policy, seed, budget, spec,
                        manifest, skip_minimize=args.skip_minimize,
                        trace_dir=os.path.join(args.out, "traces"))
                    row["validation_target"] = args.target
                    row["manifest_file"] = os.path.basename(man_path)
                    row["reproducibility_rerun"] = bool(args.rerun_for_repro)
                    rows.append(row)
                    print(
                        f"[{policy:24s} bud={budget} seed={seed}] "
                        f"confirmed={row['confirmed_bugs']} "
                        f"{len(row['confirmed_bugs'])}/{len(manifest)} "
                        f"replay={row['replay_pass']}/{row['replay_fail']}/"
                        f"{row['replay_invalid']} "
                        f"TTCB={row['ttcb']} states={row['states']} "
                        f"br={row.get('unique_branches_started')} "
                        f"wall={row['wall_seconds']}s",
                        flush=True)
    finally:
        browser.close()
        pw.stop()
        server.terminate()

    agg = aggregate(rows)
    with open(os.path.join(args.out, "config.json"), "w", encoding="utf-8") as f:
        json.dump({
            "protocol": args.protocol,
            "target": args.target,
            "app": app,
            "manifest": man_path,
            "policies": policies,
            "budgets": budgets,
            "trials": seeds,
            "rerun_for_repro": bool(args.rerun_for_repro),
            "freeze": freeze_path,
        }, f, indent=2)
    with open(os.path.join(args.out, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump({"runs": rows, "aggregate": agg, "n_manifest_bugs": len(manifest)},
                  f, ensure_ascii=False, indent=2)

    if args.target == "holdout" and not args.rerun_for_repro:
        mark_executed(args.protocol, {
            "target": args.target,
            "out": args.out,
            "n_runs": len(rows),
        })
    print(f"metrics -> {os.path.join(args.out, 'metrics.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
