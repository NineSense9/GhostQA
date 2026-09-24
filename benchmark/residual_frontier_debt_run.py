"""Exact 24-cell runner for the frozen v0.3.23 residual-debt candidate.

Installs the research policy in this process only. Completed cells are never
rerun. Does not rerun v0.3.20 Guard or v0.3.21 references.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

from benchmark.algorithm_freeze import sha256_file, verify_freeze
from benchmark.return_cycle_guard_reproduce import verify_candidate_identity
from benchmark.web_runner import run_one
import benchmark.web_runner as web_runner

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = 1
CANDIDATE = "ghost-structural-residual-frontier-debt-guard"
CANDIDATE_SOURCE = os.path.join(
    "ghostqa", "exploration", "residual_frontier_debt_guard.py")
CANDIDATE_FREEZE = os.path.join(
    ROOT, "experiments", "frozen", "ghost-residual-frontier-debt-v0.3.23", "freeze.json")
WAYPOINT_FREEZE = os.path.join(
    ROOT, "experiments", "frozen", "ghost-return-waypoint-frontier-v0.3.21", "freeze.json")
WAYPOINT_SOURCE = os.path.join(
    "ghostqa", "exploration", "return_waypoint_frontier_guard.py")
FINDING_FREEZE = os.path.join(
    ROOT, "experiments", "frozen", "ghost-finding-return-entry-v0.3.19", "freeze.json")
GUARD_FREEZE = os.path.join(
    ROOT, "experiments", "frozen", "ghost-return-cycle-guard-v0.3.9", "freeze.json")
SUITE_FREEZE = os.path.join(
    ROOT, "experiments", "frozen", "v0.3.20-fresh-composite-suite", "freeze.json")

POSITIVE = ("buggy-campus", "buggy-warehouse", "buggy-studio", "buggy-booking")
CONTROLS = ("buggy-catalog", "buggy-kiosk")
HISTORICAL = (
    "buggy-lab", "buggy-directory", "buggy-forum", "buggy-billing",
    "buggy-crm", "buggy-ops", "buggy-desk", "buggy-flow", "buggy-wiki", "buggy-shop",
)
EVIDENCE = {
    "buggy-flow": "deepbench",
    "buggy-wiki": "wiki",
}
APPS = {}
for _name in POSITIVE + CONTROLS + HISTORICAL:
    APPS[_name] = {
        "dir": os.path.join(ROOT, "apps", _name),
        "evidence": EVIDENCE.get(_name, _name),
    }

CELLS = []
for _app in POSITIVE:
    for _budget in (40, 80, 120):
        CELLS.append((_app, _budget))
for _app in CONTROLS + HISTORICAL:
    CELLS.append((_app, 120))

_ORIGINAL_MAKE_POLICY = web_runner.make_policy


def make_policy(name: str, seed: int):
    if name == CANDIDATE:
        from ghostqa.exploration.residual_frontier_debt_guard import (
            ResidualFrontierDebtGuardGhostPolicy,
        )
        return ResidualFrontierDebtGuardGhostPolicy(llm=None)
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
        ".events.jsonl", ".graph.json", ".sequence_events.json", ".config.json", ".DONE")]
    return all(os.path.isfile(os.path.join(base, name)) for name in needed)


def _write_json(path: str, payload) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _check_freezes() -> None:
    # v0.3.9 records web_runner.py, which later rounds may extend with app
    # registration. Identity is the guard source and its protocol.
    bad = verify_candidate_identity(GUARD_FREEZE)
    if bad:
        raise SystemExit("v0.3.9 guard identity mismatch\n" + "\n".join(bad))
    for path, label in (
        (CANDIDATE_FREEZE, "v0.3.23 candidate"),
        (WAYPOINT_FREEZE, "v0.3.21 candidate"),
        (FINDING_FREEZE, "v0.3.19 candidate"),
        (SUITE_FREEZE, "v0.3.20 suite"),
    ):
        bad = verify_freeze(path)
        if bad:
            raise SystemExit(label + " freeze mismatch\n" + "\n".join(bad))
    frozen = json.load(open(CANDIDATE_FREEZE, encoding="utf-8"))
    recorded = ((frozen.get("files") or {}).get(CANDIDATE_SOURCE.replace("\\", "/")) or {}).get("sha256")
    if recorded and sha256_file(os.path.join(ROOT, CANDIDATE_SOURCE)) != recorded:
        raise SystemExit("v0.3.23 candidate source hash mismatch")
    waypoint = json.load(open(WAYPOINT_FREEZE, encoding="utf-8"))
    waypoint_hash = ((waypoint.get("files") or {}).get(WAYPOINT_SOURCE.replace("\\", "/")) or {}).get("sha256")
    if waypoint_hash and sha256_file(os.path.join(ROOT, WAYPOINT_SOURCE)) != waypoint_hash:
        raise SystemExit("v0.3.21 candidate source hash mismatch")


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _wait_http(url: str) -> None:
    last = None
    for _ in range(50):
        try:
            urllib.request.urlopen(url, timeout=1).read(64)
            return
        except Exception as exc:
            last = exc
            time.sleep(0.2)
    raise SystemExit(f"server did not answer {url}: {last}")


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
    app_dir = meta["dir"]
    from ghostqa.oracle.spec import load_spec
    spec = load_spec(os.path.join(app_dir, "spec.json"))
    manifest = json.load(open(os.path.join(app_dir, "bugs.manifest.json"), encoding="utf-8"))["bugs"]
    port = _free_port()
    server = subprocess.Popen(
        [sys.executable, os.path.join(app_dir, "server.py"), str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base_url = f"http://127.0.0.1:{port}"
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
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
        _wait_http(base_url + "/index.html")
        t0 = time.time()
        print(f"[start] {app} {CANDIDATE} b{budget}", flush=True)
        row = run_one(
            base_url, {"pw": pw, "browser": browser}, CANDIDATE, SEED, budget,
            spec, manifest, skip_minimize=True, dump_dir=dump_dir)
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
            f"confirmed={row.get('confirmed_bugs')} "
            f"debts={row.get('residual_frontier_debts_created')} "
            f"relocations={row.get('residual_frontier_debt_relocations')} "
            f"consumed={row.get('residual_frontier_tokens_consumed')} "
            f"escapes={row.get('return_waypoint_frontier_escape_events')} "
            f"handoff={row.get('horizon_handoff_started_events')} "
            f"finding={row.get('finding_return_entry_trigger_events')} "
            f"horizon_drain={row.get('finding_return_entry_horizon_bypass_events')} "
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
    parser.add_argument("--out", default=os.path.join("experiments", "runs", "v0323-residual-debt"))
    parser.add_argument("--apps", default="")
    args = parser.parse_args(argv)
    if len(CELLS) != 24:
        raise SystemExit("protocol cell list is not 24")
    cells = selected_cells([part.strip() for part in args.apps.split(",") if part.strip()])
    os.makedirs(args.out, exist_ok=True)
    _install_policy()
    _check_freezes()
    print(f"planned cells={len(cells)} out={args.out}", flush=True)
    for app, budget in cells:
        run_cell(app, budget, args.out)
    print("OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
