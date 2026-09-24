"""Exact 42-cell runner for the frozen v0.3.20 fresh composite suite.

Does not discover apps. Completed cells are never rerun.
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
from benchmark.web_runner import run_one
import benchmark.web_runner as web_runner

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = 1
CANDIDATE = "ghost-structural-finding-return-entry-drain-guard"
CANDIDATE_SHA = "0bfec3c7bd2811f154daa83bc81fde632976b8ab6e1da9ee6a208cf81c4bb42c"
CANDIDATE_SOURCE = os.path.join(
    "ghostqa", "exploration", "finding_return_entry_guard.py")
POLICY = {
    "C1": "ghost-structural-memory",
    "G": "ghost-structural-return-guard",
    "F": CANDIDATE,
}
POSITIVE = ("buggy-campus", "buggy-warehouse", "buggy-studio", "buggy-booking")
NEGATIVE = ("buggy-catalog", "buggy-kiosk")
PORTS = {
    "buggy-campus": 3951,
    "buggy-warehouse": 3952,
    "buggy-studio": 3953,
    "buggy-booking": 3954,
    "buggy-catalog": 3955,
    "buggy-kiosk": 3956,
}
CANDIDATE_FREEZE = os.path.join(
    ROOT, "experiments", "frozen", "ghost-finding-return-entry-v0.3.19", "freeze.json")
SUITE_FREEZE = os.path.join(
    ROOT, "experiments", "frozen", "v0.3.20-fresh-composite-suite", "freeze.json")

APPS = {}
for _name, _port in PORTS.items():
    APPS[_name] = {
        "dir": os.path.join(ROOT, "apps", _name),
        "port": _port,
        "freeze": os.path.join(
            ROOT, "experiments", "frozen", "v0.3.20-fresh-composite-suite",
            _name, "freeze.json"),
    }

CELLS = []
for _app in POSITIVE:
    for _policy in ("C1", "G", "F"):
        for _budget in (40, 80, 120):
            CELLS.append({"app": _app, "policy": _policy, "budget": _budget, "seed": SEED})
for _app in NEGATIVE:
    for _policy in ("C1", "G", "F"):
        CELLS.append({"app": _app, "policy": _policy, "budget": 120, "seed": SEED})

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


def cell_stem(policy_name: str, budget: int, seed: int = SEED) -> str:
    return f"{policy_name}_b{budget}_s{seed}"


def cell_dir(out_root: str, app: str) -> str:
    return os.path.join(out_root, "evidence", app)


def cell_done(out_root: str, app: str, policy_name: str, budget: int) -> bool:
    base = cell_dir(out_root, app)
    stem = cell_stem(policy_name, budget)
    needed = [stem + ext for ext in (
        ".events.jsonl", ".graph.json", ".sequence_events.json", ".config.json", ".DONE")]
    return all(os.path.isfile(os.path.join(base, name)) for name in needed)


def _write_json(path: str, payload) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _load_rows(path: str) -> list:
    if not os.path.isfile(path):
        return []
    try:
        return json.load(open(path, encoding="utf-8")).get("runs") or []
    except json.JSONDecodeError:
        return []


def _wait_http(url: str) -> None:
    for _ in range(50):
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("server did not start " + url)


def _check_freezes(app: str) -> None:
    if sha256_file(os.path.join(ROOT, CANDIDATE_SOURCE)) != CANDIDATE_SHA:
        raise SystemExit("candidate source hash mismatch")
    bad = verify_freeze(CANDIDATE_FREEZE)
    if bad:
        raise SystemExit("candidate freeze mismatch\n" + "\n".join(bad))
    bad = verify_freeze(SUITE_FREEZE)
    if bad:
        raise SystemExit("suite freeze mismatch\n" + "\n".join(bad))
    bad = verify_freeze(APPS[app]["freeze"])
    if bad:
        raise SystemExit(f"{app} target freeze mismatch\n" + "\n".join(bad))


def run_cell(app: str, policy_code: str, budget: int, out_root: str) -> dict:
    meta = APPS[app]
    policy_name = POLICY[policy_code]
    if cell_done(out_root, app, policy_name, budget):
        print(f"[skip] {app} {policy_code} b{budget} DONE", flush=True)
        return {}
    _check_freezes(app)
    spec_path = os.path.join(meta["dir"], "spec.json")
    manifest_path = os.path.join(meta["dir"], "bugs.manifest.json")
    from ghostqa.oracle.spec import load_spec
    spec = load_spec(spec_path)
    manifest = json.load(open(manifest_path, encoding="utf-8"))["bugs"]
    port = meta["port"]
    probe = socket.socket()
    try:
        probe.bind(("127.0.0.1", port))
    except OSError as exc:
        raise SystemExit(f"{app} port {port} is busy") from exc
    finally:
        probe.close()
    server = subprocess.Popen(
        [sys.executable, os.path.join(meta["dir"], "server.py"), str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base_url = f"http://127.0.0.1:{port}"
    dump_dir = cell_dir(out_root, app)
    os.makedirs(dump_dir, exist_ok=True)
    stem = cell_stem(policy_name, budget)
    config = {
        "app": app,
        "policy_code": policy_code,
        "policy": policy_name,
        "budget": budget,
        "seed": SEED,
        "port": port,
        "skip_minimize": True,
    }
    _write_json(os.path.join(dump_dir, stem + ".config.json"), config)
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    try:
        _wait_http(base_url + "/index.html")
        t0 = time.time()
        print(f"[start] {app} {policy_code} {policy_name} b{budget}", flush=True)
        row = run_one(
            base_url, {"pw": pw, "browser": browser}, policy_name, SEED, budget,
            spec, manifest, skip_minimize=True, dump_dir=dump_dir)
        row["app"] = app
        row["policy_code"] = policy_code
        metrics_path = os.path.join(dump_dir, "metrics.json")
        rows = [
            item for item in _load_rows(metrics_path)
            if not (item.get("policy") == policy_name and item.get("budget") == budget)
        ]
        rows.append(row)
        _write_json(metrics_path, {"app": app, "runs": rows})
        with open(os.path.join(dump_dir, stem + ".DONE"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write("ok\n")
        print(
            f"[done] {app} {policy_code} b{budget} states={row.get('states')} "
            f"urls={row.get('normalized_unique_urls')} "
            f"confirmed={row.get('confirmed_bugs')} "
            f"handoff={row.get('horizon_handoff_started_events')} "
            f"trigger={row.get('finding_return_entry_trigger_events')} "
            f"drain={row.get('return_entry_drain_started_events')} "
            f"wall={row.get('wall_seconds')}s elapsed={round(time.time()-t0,1)}s",
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join("experiments", "runs", "v0320-fresh"))
    parser.add_argument("--apps", default="")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    if len(CELLS) != 42:
        raise SystemExit("protocol cell list is not 42")
    selected = {item.strip() for item in args.apps.split(",") if item.strip()}
    unknown = selected - set(APPS)
    if unknown:
        raise SystemExit("unknown apps " + ",".join(sorted(unknown)))
    cells = [cell for cell in CELLS if not selected or cell["app"] in selected]
    _install_policy()
    _check_freezes(cells[0]["app"])
    print(f"planned cells={len(cells)} out={args.out}", flush=True)
    for cell in cells:
        if args.resume and cell_done(
            args.out, cell["app"], POLICY[cell["policy"]], cell["budget"]
        ):
            print(f"[skip] {cell['app']} {cell['policy']} b{cell['budget']} DONE", flush=True)
            continue
        run_cell(cell["app"], cell["policy"], cell["budget"], args.out)
    print("OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
