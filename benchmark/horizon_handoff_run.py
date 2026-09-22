"""v0.3.14 candidate-only runner.

Installs the horizon-handoff policy in this process only.
Frozen web_runner.py stays byte-identical. Historical policies are not rerun.
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

CANDIDATE = "ghost-structural-horizon-handoff-guard"
_ORIGINAL_MAKE_POLICY = web_runner.make_policy
SEED = 1


def make_policy(name: str, seed: int):
    if name == CANDIDATE:
        from ghostqa.exploration.horizon_handoff_guard import (
            HorizonHandoffReturnGuardGhostPolicy,
        )
        return HorizonHandoffReturnGuardGhostPolicy(llm=None)
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
                    if not (item.get("policy") == policy and item.get("budget") == budget)
                ]
                rows.append(row)
                save_metrics(out_root, app, rows)
                print(
                    f"[done]  {app} {policy} b{budget} "
                    f"states={row.get('states')} "
                    f"urls={row.get('normalized_unique_urls')} "
                    f"cont={row.get('nested_continuation_events')} "
                    f"handoff={row.get('horizon_handoff_started_events')} "
                    f"witness={row.get('child_parent_witness_events')} "
                    f"resume={row.get('parent_frame_resume_to_return_events')} "
                    f"unwind={row.get('horizon_handoff_unwind_events')} "
                    f"depth={row.get('max_handoff_stack_depth')} "
                    f"horizon={row.get('sequence_horizon_reached')} "
                    f"ret={row.get('return_attempt_events')} "
                    f"esc={row.get('return_cycle_escape_events')} "
                    f"viol={row.get('witness_violations')} "
                    f"term={row.get('terminal_accounting_violations')} "
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


def _split(text: str) -> tuple:
    return tuple(part.strip() for part in (text or "").split(",") if part.strip())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join(
        "experiments", "runs", "v0314-horizon"))
    parser.add_argument("--apps", required=True)
    parser.add_argument("--budgets", required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    apps = _split(args.apps)
    budgets = tuple(int(item) for item in _split(args.budgets))
    os.makedirs(args.out, exist_ok=True)
    _install_policy()
    print(
        f"planned apps={list(apps)} policy={CANDIDATE} "
        f"budgets={list(budgets)} out={args.out}",
        flush=True)
    for app in apps:
        run_app(app, args.out, (CANDIDATE,), budgets, resume=args.resume)
    print("OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
