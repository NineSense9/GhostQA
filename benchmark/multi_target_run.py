"""One-shot v0.3.11 matrix. Run only after P1 freeze exists.

Writes each cell durably as it finishes. Rerun exact cells on infrastructure
failure. Does not change protocol, budgets, or apps.
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
from benchmark.multitarget_vocab import APP_NAMES
from benchmark.web_runner import APPS, run_one, ROOT

PRIMARY = (
    "ghost-structural-memory",
    "ghost-structural-return-guard",
)
CONTEXT = ("ghost-nollm", "bfs", "dfs")
PRIMARY_BUDGETS = (40, 80, 120)
CONTEXT_BUDGET = 120
SEED = 1


def _cells():
    for app in APP_NAMES:
        for pol in PRIMARY:
            for bud in PRIMARY_BUDGETS:
                yield app, pol, bud
        for pol in CONTEXT:
            yield app, pol, CONTEXT_BUDGET


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def cell_stem(policy: str, budget: int, seed: int = SEED) -> str:
    return f"{policy}_b{budget}_s{seed}"


def cell_done(out_root: str, app: str, policy: str, budget: int) -> bool:
    base = os.path.join(out_root, "evidence", app)
    stem = cell_stem(policy, budget)
    return all(os.path.isfile(os.path.join(base, stem + ext))
               for ext in (".events.jsonl", ".graph.json", ".sequence_events.json"))


def save_metrics(out_root: str, app: str, rows: list) -> None:
    path = os.path.join(out_root, "evidence", app, "metrics.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"app": app, "runs": rows}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    all_path = os.path.join(out_root, "metrics.json")
    all_rows = []
    if os.path.isfile(all_path):
        try:
            all_rows = json.load(open(all_path, encoding="utf-8")).get("runs") or []
        except json.JSONDecodeError:
            all_rows = []
    kept = [r for r in all_rows
            if not (r.get("app") == app and any(
                r.get("policy") == x.get("policy") and r.get("budget") == x.get("budget")
                for x in rows))]
    for r in rows:
        rec = dict(r)
        rec["app"] = app
        kept.append(rec)
    with open(all_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"runs": kept}, f, ensure_ascii=False, indent=2)
        f.write("\n")


def run_app(app: str, out_root: str, *, resume: bool) -> list:
    app_dir = APPS[app]
    spec = load_spec(os.path.join(app_dir, "spec.json"))
    manifest = json_load_bugs(os.path.join(app_dir, "bugs.manifest.json"))
    planned = [(pol, bud) for a, pol, bud in _cells() if a == app]
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
        for policy, budget in planned:
            if resume and cell_done(out_root, app, policy, budget):
                existing = next((r for r in rows if r.get("policy") == policy
                                 and r.get("budget") == budget), None)
                print(f"[skip] {app} {policy} b{budget} already present", flush=True)
                if existing is None:
                    print(f"[warn] evidence exists but metrics row missing: {app} {policy} b{budget}",
                          flush=True)
                continue
            t0 = time.time()
            print(f"[start] {app} {policy} b{budget}", flush=True)
            row = run_one(base_url, shared, policy, SEED, budget, spec, manifest,
                          skip_minimize=True, dump_dir=dump_dir)
            row["app"] = app
            rows = [r for r in rows
                    if not (r.get("policy") == policy and r.get("budget") == budget)]
            rows.append(row)
            save_metrics(out_root, app, rows)
            print(
                f"[done]  {app} {policy} b{budget} "
                f"bdr={row.get('bug_discovery_rate')} "
                f"states={row.get('states')} "
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


def json_load_bugs(path: str) -> list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)["bugs"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join("experiments", "runs", "v0311-multitarget"))
    ap.add_argument("--app", default="", help="one app, or all")
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    apps = [args.app] if args.app else list(APP_NAMES)
    planned = list(_cells())
    print(f"planned cells {len(planned)} apps {apps} out {args.out}", flush=True)
    for app in apps:
        run_app(app, args.out, resume=args.resume)
    print("OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
