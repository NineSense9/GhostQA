"""v0.3.12 mechanism matrix runner.

Does not change candidate semantics. The nested-hub policy is installed
only inside this process so frozen web_runner.py stays byte-identical.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time

from ghostqa.oracle.spec import load_spec
from benchmark.web_runner import APPS, run_one
import benchmark.web_runner as web_runner

NESTED = "ghost-structural-nested-return-guard"
_ORIGINAL_MAKE_POLICY = web_runner.make_policy
DEFAULT_APPS = ("buggy-crm", "buggy-ops")
DEFAULT_POLICIES = (
    "ghost-structural-memory",
    "ghost-structural-return-guard",
    NESTED,
)
DEFAULT_BUDGETS = (40, 80, 120)
SEED = 1


def make_policy(name: str, seed: int):
    if name == NESTED:
        from ghostqa.exploration.nested_hub_guard import (
            NestedHubReturnGuardGhostPolicy,
        )
        return NestedHubReturnGuardGhostPolicy(llm=None)
    return _ORIGINAL_MAKE_POLICY(name, seed)


def _install_policy():
    web_runner.make_policy = make_policy


def _free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def cell_stem(policy: str, budget: int, seed: int = SEED) -> str:
    return f"{policy}_b{budget}_s{seed}"


def cell_done(out_root: str, app: str, policy: str, budget: int) -> bool:
    base = os.path.join(out_root, "evidence", app)
    stem = cell_stem(policy, budget)
    return all(
        os.path.isfile(os.path.join(base, stem + ext))
        for ext in (".events.jsonl", ".graph.json", ".sequence_events.json")
    )


def save_metrics(out_root: str, app: str, rows: list) -> None:
    path = os.path.join(out_root, "evidence", app, "metrics.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"app": app, "runs": rows}, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    all_path = os.path.join(out_root, "metrics.json")
    all_rows = []
    if os.path.isfile(all_path):
        try:
            all_rows = json.load(open(all_path, encoding="utf-8")).get("runs") or []
        except json.JSONDecodeError:
            all_rows = []
    kept = [
        row for row in all_rows
        if not (row.get("app") == app and any(
            row.get("policy") == item.get("policy")
            and row.get("budget") == item.get("budget")
            for item in rows))
    ]
    for row in rows:
        rec = dict(row)
        rec["app"] = app
        kept.append(rec)
    with open(all_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"runs": kept}, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def json_load_bugs(path: str) -> list:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)["bugs"]


def run_app(app: str, out_root: str, policies: tuple, budgets: tuple,
            *, resume: bool) -> list:
    app_dir = APPS[app]
    spec = load_spec(os.path.join(app_dir, "spec.json"))
    manifest = json_load_bugs(os.path.join(app_dir, "bugs.manifest.json"))
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
    dump_dir = os.path.join(out_root, "evidence", app)
    os.makedirs(dump_dir, exist_ok=True)
    metrics_path = os.path.join(dump_dir, "metrics.json")
    rows = []
    if os.path.isfile(metrics_path):
        try:
            rows = json.load(open(metrics_path, encoding="utf-8")).get("runs") or []
        except json.JSONDecodeError:
            rows = []
    try:
        for policy in policies:
            for budget in budgets:
                if resume and cell_done(out_root, app, policy, budget):
                    print(f"[skip] {app} {policy} b{budget} already present",
                          flush=True)
                    continue
                t0 = time.time()
                print(f"[start] {app} {policy} b{budget}", flush=True)
                row = run_one(
                    base_url, shared, policy, SEED, budget, spec, manifest,
                    skip_minimize=True, dump_dir=dump_dir)
                row["app"] = app
                rows = [
                    item for item in rows
                    if not (item.get("policy") == policy
                            and item.get("budget") == budget)
                ]
                rows.append(row)
                save_metrics(out_root, app, rows)
                print(
                    f"[done]  {app} {policy} b{budget} "
                    f"states={row.get('states')} "
                    f"urls={row.get('normalized_unique_urls')} "
                    f"lost={row.get('sequence_lost_parent')} "
                    f"follow={row.get('nested_branch_followup_events')} "
                    f"horizon={row.get('sequence_horizon_reached')} "
                    f"ret={row.get('return_attempt_events')} "
                    f"esc={row.get('return_cycle_escape_events')} "
                    f"confirmed={row.get('confirmed_bugs')} "
                    f"wall={row.get('wall_seconds')}s "
                    f"elapsed={round(time.time() - t0, 1)}s",
                    flush=True)
    finally:
        try:
            browser.close()
        except Exception:
            pass
        try:
            pw.stop()
        except Exception:
            pass
        server.terminate()
        try:
            server.wait(timeout=5)
        except Exception:
            server.kill()
    return rows


def _split(text: str, fallback: tuple) -> tuple:
    if not text:
        return fallback
    return tuple(part.strip() for part in text.split(",") if part.strip())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join(
        "experiments", "runs", "v0312-nested"))
    parser.add_argument("--apps", default=",".join(DEFAULT_APPS))
    parser.add_argument("--policies", default=",".join(DEFAULT_POLICIES))
    parser.add_argument("--budgets", default=",".join(str(b) for b in DEFAULT_BUDGETS))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    apps = _split(args.apps, DEFAULT_APPS)
    policies = _split(args.policies, DEFAULT_POLICIES)
    budgets = tuple(int(item) for item in _split(args.budgets, tuple()))
    os.makedirs(args.out, exist_ok=True)
    _install_policy()
    print(
        f"planned apps={list(apps)} policies={list(policies)} "
        f"budgets={list(budgets)} out={args.out}",
        flush=True)
    for app in apps:
        run_app(app, args.out, policies, budgets, resume=args.resume)
    print("OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
