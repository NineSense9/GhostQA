"""Exact 8-cell diagnostic runner for the frozen v0.3.21 candidate.

Budget is the only varied input. Completed cells are never rerun.
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

from benchmark.post_escape_sink_analysis import (
    CANDIDATE,
    CELLS,
    ROOT,
    SEED,
    freeze_status,
)
from benchmark.web_runner import run_one
import benchmark.web_runner as web_runner

_ORIGINAL_MAKE_POLICY = web_runner.make_policy


def make_policy(name: str, seed: int):
    if name == CANDIDATE:
        from ghostqa.exploration.return_waypoint_frontier_guard import (
            ReturnWaypointFrontierGuardGhostPolicy,
        )
        return ReturnWaypointFrontierGuardGhostPolicy(llm=None)
    return _ORIGINAL_MAKE_POLICY(name, seed)


def _install_policy() -> None:
    web_runner.make_policy = make_policy


def cell_name(app: str, budget: int) -> str:
    return f"{app}_b{budget}_s{SEED}"


def cell_dir(out_root: str, app: str, budget: int) -> str:
    return os.path.join(out_root, cell_name(app, budget))


def cell_done(out_root: str, app: str, budget: int) -> bool:
    base = cell_dir(out_root, app, budget)
    needed = ("config.json", "events.jsonl", "sequence_events.json", "summary.json", "DONE")
    return all(os.path.isfile(os.path.join(base, name)) for name in needed)


def _write_json(path: str, payload) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _check_freezes() -> None:
    status = freeze_status()
    if not status["ok"] or status["product_default_changed"]:
        raise SystemExit("freeze or product-default check failed\n" + "\n".join(status["mismatches"]))


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


def _promote(dump_dir: str, stem: str, dest: str) -> None:
    os.makedirs(dest, exist_ok=True)
    mapping = {
        stem + ".events.jsonl": "events.jsonl",
        stem + ".sequence_events.json": "sequence_events.json",
        stem + ".graph.json": "graph.json",
    }
    for source_name, dest_name in mapping.items():
        source = os.path.join(dump_dir, source_name)
        if not os.path.isfile(source):
            raise SystemExit("missing runner output " + source_name)
        target = os.path.join(dest, dest_name)
        os.replace(source, target)


def run_cell(app: str, budget: int, out_root: str) -> dict:
    if (app, budget) not in CELLS:
        raise SystemExit(f"refusing cell outside the preregistered matrix: {app} {budget}")
    if cell_done(out_root, app, budget):
        print(f"[skip] {app} b{budget} DONE", flush=True)
        return {}
    _check_freezes()
    app_dir = os.path.join(ROOT, "apps", app)
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
    dest = cell_dir(out_root, app, budget)
    os.makedirs(dest, exist_ok=True)
    stem = f"{CANDIDATE}_b{budget}_s{SEED}"
    try:
        _wait_http(base_url + "/index.html")
        t0 = time.time()
        print(f"[start] {app} {CANDIDATE} b{budget}", flush=True)
        row = run_one(
            base_url, {"pw": pw, "browser": browser}, CANDIDATE, SEED, budget,
            spec, manifest, skip_minimize=True, dump_dir=dest)
        _promote(dest, stem, dest)
        row["app"] = app
        row["source_app"] = app
        _write_json(os.path.join(dest, "summary.json"), row)
        _write_json(os.path.join(dest, "config.json"), {
            "app": app,
            "policy": CANDIDATE,
            "budget": budget,
            "seed": SEED,
            "skip_minimize": True,
        })
        with open(os.path.join(dest, "DONE"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write("ok\n")
        print(
            f"[done] {app} b{budget} states={row.get('states')} "
            f"urls={row.get('normalized_unique_urls')} "
            f"confirmed={row.get('confirmed_bugs')} "
            f"escapes={row.get('return_waypoint_frontier_escape_events')} "
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


def selected_cells(apps: list[str] | None) -> list[tuple[str, int]]:
    if not apps:
        return list(CELLS)
    wanted = set(apps)
    unknown = wanted - set(dict(CELLS))
    if unknown:
        raise SystemExit("unknown app " + ",".join(sorted(unknown)))
    return [cell for cell in CELLS if cell[0] in wanted]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join("experiments", "runs", "v0322-post-escape-sink"))
    parser.add_argument("--apps", default="")
    args = parser.parse_args(argv)
    if list(CELLS) != [
        ("buggy-campus", 240), ("buggy-campus", 480),
        ("buggy-warehouse", 240), ("buggy-warehouse", 480),
        ("buggy-studio", 240), ("buggy-studio", 480),
        ("buggy-booking", 240), ("buggy-booking", 480),
    ]:
        raise SystemExit("protocol cell list is not the preregistered 8")
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
