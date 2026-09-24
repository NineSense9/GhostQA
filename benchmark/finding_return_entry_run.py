"""Exact 12-cell runner for the frozen v0.3.19 finding-gated candidate.

Installs the research policy in this process only. Does not rerun historical
controls. Completed cells are never rerun.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time

from benchmark.algorithm_freeze import verify_freeze
from benchmark.web_runner import run_one
import benchmark.web_runner as web_runner

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANDIDATE = "ghost-structural-finding-return-entry-drain-guard"
SEED = 1
CANDIDATE_FREEZE = os.path.join(
    ROOT, "experiments", "frozen", "ghost-finding-return-entry-v0.3.19", "freeze.json")
RETURN_ENTRY_FREEZE = os.path.join(
    ROOT, "experiments", "frozen", "ghost-return-entry-drain-v0.3.18", "freeze.json")
HISTORICAL_FREEZE = os.path.join(
    ROOT, "experiments", "frozen", "ghost-horizon-handoff-v0.3.14", "freeze.json")
SUITE_FREEZE = os.path.join(
    ROOT, "experiments", "frozen", "v0.3.15-fresh-handoff-suite", "freeze.json")
REENTRY_FREEZE = os.path.join(
    ROOT, "experiments", "frozen", "ghost-reentry-frontier-v0.3.16", "freeze.json")
LOCAL_FREEZE = os.path.join(
    ROOT, "experiments", "frozen", "ghost-local-action-drain-v0.3.17", "freeze.json")

APPS = {
    "buggy-directory": {"dir": "apps/buggy-directory", "evidence": "buggy-directory"},
    "buggy-lab": {"dir": "apps/buggy-lab", "evidence": "buggy-lab"},
    "buggy-forum": {"dir": "apps/buggy-forum", "evidence": "buggy-forum"},
    "buggy-billing": {"dir": "apps/buggy-billing", "evidence": "buggy-billing"},
    "buggy-crm": {"dir": "apps/buggy-crm", "evidence": "buggy-crm"},
    "buggy-ops": {"dir": "apps/buggy-ops", "evidence": "buggy-ops"},
    "buggy-desk": {"dir": "apps/buggy-desk", "evidence": "buggy-desk"},
    "buggy-flow": {"dir": "apps/buggy-flow", "evidence": "deepbench"},
    "buggy-wiki": {"dir": "apps/buggy-wiki", "evidence": "wiki"},
    "buggy-shop": {"dir": "apps/buggy-shop", "evidence": "buggy-shop"},
}
CELLS = (
    ("buggy-lab", 40),
    ("buggy-lab", 80),
    ("buggy-lab", 120),
    ("buggy-directory", 120),
    ("buggy-forum", 120),
    ("buggy-billing", 120),
    ("buggy-crm", 120),
    ("buggy-ops", 120),
    ("buggy-desk", 120),
    ("buggy-flow", 120),
    ("buggy-wiki", 120),
    ("buggy-shop", 120),
)

_ORIGINAL_MAKE_POLICY = web_runner.make_policy


def make_policy(name: str, seed: int):
    if name == CANDIDATE:
        from ghostqa.exploration.finding_return_entry_guard import (
            FindingReturnEntryDrainGuardGhostPolicy,
        )
        return FindingReturnEntryDrainGuardGhostPolicy(llm=None)
    return _ORIGINAL_MAKE_POLICY(name, seed)


def _install_policy():
    web_runner.make_policy = make_policy


def cell_stem(budget: int, seed: int = SEED) -> str:
    return f"{CANDIDATE}_b{budget}_s{seed}"


def cell_dir(out_root: str, app: str) -> str:
    return os.path.join(out_root, "evidence", APPS[app]["evidence"])


def cell_done(out_root: str, app: str, budget: int) -> bool:
    base = cell_dir(out_root, app)
    stem = cell_stem(budget)
    needed = [stem + ext for ext in (
        ".events.jsonl", ".graph.json", ".sequence_events.json",
        ".config.json", ".DONE")]
    return all(os.path.isfile(os.path.join(base, name)) for name in needed)


def _write_json(path: str, payload) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _check_freezes() -> None:
    for path, label in (
        (CANDIDATE_FREEZE, "v0.3.19 candidate"),
        (RETURN_ENTRY_FREEZE, "v0.3.18 candidate"),
        (LOCAL_FREEZE, "v0.3.17 candidate"),
        (REENTRY_FREEZE, "v0.3.16 candidate"),
        (HISTORICAL_FREEZE, "v0.3.14 candidate"),
        (SUITE_FREEZE, "v0.3.15 suite"),
    ):
        bad = verify_freeze(path)
        if bad:
            raise SystemExit(label + " freeze mismatch\n" + "\n".join(bad))


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _load_rows(path: str) -> list:
    if not os.path.isfile(path):
        return []
    try:
        return json.load(open(path, encoding="utf-8")).get("runs") or []
    except json.JSONDecodeError:
        return []


def save_metrics(out_root: str, app: str, rows: list) -> None:
    path = os.path.join(cell_dir(out_root, app), "metrics.json")
    _write_json(path, {"app": APPS[app]["evidence"], "runs": rows})


def run_cell(app: str, budget: int, out_root: str) -> dict:
    if (app, budget) not in CELLS:
        raise SystemExit(f"refusing cell outside the preregistered matrix: {app} {budget}")
    if cell_done(out_root, app, budget):
        print(f"[skip] {app} b{budget} DONE", flush=True)
        return {}
    _check_freezes()
    meta = APPS[app]
    app_dir = os.path.join(ROOT, meta["dir"])
    from ghostqa.oracle.spec import load_spec
    spec = load_spec(os.path.join(app_dir, "spec.json"))
    manifest = json.load(open(os.path.join(app_dir, "bugs.manifest.json"), encoding="utf-8"))["bugs"]
    port = _free_port()
    server = subprocess.Popen(
        [sys.executable, os.path.join(app_dir, "server.py"), str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base_url = f"http://127.0.0.1:{port}"
    time.sleep(0.4)
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    shared = {"pw": pw, "browser": browser}
    dump_dir = cell_dir(out_root, app)
    os.makedirs(dump_dir, exist_ok=True)
    stem = cell_stem(budget)
    config = {
        "app": app,
        "evidence_app": meta["evidence"],
        "policy": CANDIDATE,
        "budget": budget,
        "seed": SEED,
        "port": port,
        "skip_minimize": True,
    }
    try:
        t0 = time.time()
        print(f"[start] {app} {CANDIDATE} b{budget}", flush=True)
        row = run_one(
            base_url, shared, CANDIDATE, SEED, budget, spec, manifest,
            skip_minimize=True, dump_dir=dump_dir)
        row["app"] = meta["evidence"]
        row["source_app"] = app
        metrics_path = os.path.join(dump_dir, "metrics.json")
        rows = [
            item for item in _load_rows(metrics_path)
            if not (item.get("policy") == CANDIDATE and int(item.get("budget") or 0) == budget)
        ]
        rows.append(row)
        save_metrics(out_root, app, rows)
        _write_json(os.path.join(dump_dir, stem + ".config.json"), config)
        open(os.path.join(dump_dir, stem + ".DONE"), "w", encoding="utf-8").write("ok\n")
        print(
            f"[done] {app} b{budget} states={row.get('states')} "
            f"urls={row.get('normalized_unique_urls')} "
            f"handoff={row.get('horizon_handoff_started_events')} "
            f"drain={row.get('local_action_drain_started_events')} "
            f"return_entry={row.get('return_entry_drain_started_events')} "
            f"finding_trigger={row.get('finding_return_entry_trigger_events')} "
            f"horizon_bypass={row.get('finding_return_entry_horizon_bypass_events')} "
            f"probes={row.get('return_entry_probe_completed_events')} "
            f"left={row.get('return_entry_probe_left_hub_events')} "
            f"witness_v={row.get('witness_violations')} "
            f"term_v={row.get('terminal_accounting_violations')} "
            f"entry_v={row.get('return_entry_accounting_violations')} "
            f"confirmed={row.get('confirmed_bugs')} "
            f"wall={row.get('wall_seconds')}s elapsed={round(time.time() - t0, 1)}s",
            flush=True)
        return row
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


def selected_cells(apps: list | None) -> list:
    if not apps:
        return list(CELLS)
    wanted = set(apps)
    unknown = wanted - set(APPS)
    if unknown:
        raise SystemExit("unknown app " + ",".join(sorted(unknown)))
    return [cell for cell in CELLS if cell[0] in wanted]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join("experiments", "runs", "v0319-finding-return-entry"))
    parser.add_argument("--apps", default="")
    args = parser.parse_args(argv)
    cells = selected_cells([part.strip() for part in args.apps.split(",") if part.strip()])
    os.makedirs(args.out, exist_ok=True)
    _install_policy()
    _check_freezes()
    print(f"planned cells={cells} out={args.out}", flush=True)
    for app, budget in cells:
        run_cell(app, budget, args.out)
    print("OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
