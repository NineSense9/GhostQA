"""One-shot 38-cell runner for the v0.3.25 fresh transfer.

Guard and the frozen v0.3.24 candidate on the new suite, plus the candidate
on the historical regression list. Completed cells are not rerun.
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
CANDIDATE = "ghost-structural-episode-drain-epoch-guard"
GUARD = "ghost-structural-return-guard"
SUITE_FREEZE = os.path.join(
    ROOT, "experiments", "frozen", "v0.3.25-fresh-transfer-suite", "freeze.json")
CANDIDATE_FREEZE = os.path.join(
    ROOT, "experiments", "frozen", "ghost-episode-drain-epoch-v0.3.24", "freeze.json")
POSITIVE = ("buggy-clinic", "buggy-dispatch", "buggy-archive", "buggy-fleet")
NEGATIVE = ("buggy-shelf", "buggy-counter")
HISTORICAL = (
    "buggy-lab", "buggy-flow", "buggy-forum", "buggy-billing", "buggy-directory",
    "buggy-crm", "buggy-ops", "buggy-desk", "buggy-wiki", "buggy-shop",
)
EVIDENCE = {"buggy-flow": "deepbench", "buggy-wiki": "wiki"}
FRESH_CELLS = []
for _app in POSITIVE:
    for _budget in (40, 80, 120):
        for _policy in (GUARD, CANDIDATE):
            FRESH_CELLS.append((_app, _policy, _budget))
for _app in NEGATIVE:
    for _policy in (GUARD, CANDIDATE):
        FRESH_CELLS.append((_app, _policy, 120))
HIST_CELLS = [(_app, CANDIDATE, 120) for _app in HISTORICAL]
CELLS = FRESH_CELLS + HIST_CELLS


_ORIGINAL = web_runner.make_policy


def _policy(name: str, seed: int):
    if name == CANDIDATE:
        from ghostqa.exploration.episode_drain_epoch_guard import (
            EpisodeDrainEpochGuardGhostPolicy,
        )
        return EpisodeDrainEpochGuardGhostPolicy(llm=None)
    return _ORIGINAL(name, seed)


def _install():
    web_runner.make_policy = _policy


def _evidence(app: str) -> str:
    return EVIDENCE.get(app, app)


def _stem(policy: str, budget: int) -> str:
    return f"{policy}_b{budget}_s{SEED}"


def _dir(out_root: str, app: str) -> str:
    return os.path.join(out_root, "evidence", _evidence(app))


def _done(out_root: str, app: str, policy: str, budget: int) -> bool:
    base = _dir(out_root, app)
    stem = _stem(policy, budget)
    return all(os.path.isfile(os.path.join(base, stem + ext)) for ext in (
        ".events.jsonl", ".graph.json", ".sequence_events.json", ".config.json", ".DONE"))


def _write(path: str, payload) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _check() -> None:
    bad = verify_freeze(SUITE_FREEZE) + verify_freeze(CANDIDATE_FREEZE)
    if bad:
        raise SystemExit("freeze mismatch\n" + "\n".join(bad))
    if sha256_file(os.path.join(
        ROOT, "ghostqa", "exploration", "episode_drain_epoch_guard.py"
    )) != "9403e81f34625ff225f4cca69bf65c992d937305cb3a516a8be12a7bc9e08d45":
        raise SystemExit("candidate source changed")


def _port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _wait(url: str) -> None:
    last = None
    for _ in range(50):
        try:
            urllib.request.urlopen(url, timeout=1).read(64)
            return
        except Exception as exc:
            last = exc
            time.sleep(0.2)
    raise SystemExit(f"server did not answer {url}: {last}")


def _rows(path: str) -> list:
    if not os.path.isfile(path):
        return []
    return json.load(open(path, encoding="utf-8")).get("runs") or []


def run_cell(app: str, policy: str, budget: int, out_root: str) -> None:
    if (app, policy, budget) not in CELLS:
        raise SystemExit(f"refusing cell {app} {policy} {budget}")
    if _done(out_root, app, policy, budget):
        print(f"[skip] {app} {policy} b{budget}", flush=True)
        return
    _check()
    app_dir = os.path.join(ROOT, "apps", app)
    from ghostqa.oracle.spec import load_spec
    spec = load_spec(os.path.join(app_dir, "spec.json"))
    manifest = json.load(open(os.path.join(app_dir, "bugs.manifest.json"), encoding="utf-8"))["bugs"]
    port = _port()
    server = subprocess.Popen(
        [sys.executable, os.path.join(app_dir, "server.py"), str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    dump = _dir(out_root, app)
    os.makedirs(dump, exist_ok=True)
    try:
        _wait(base + "/index.html")
        t0 = time.time()
        print(f"[start] {app} {policy} b{budget}", flush=True)
        row = run_one(
            base, {"pw": pw, "browser": browser}, policy, SEED, budget,
            spec, manifest, skip_minimize=True, dump_dir=dump)
        row["app"] = _evidence(app)
        row["source_app"] = app
        metrics_path = os.path.join(dump, "metrics.json")
        rows = [
            item for item in _rows(metrics_path)
            if not (item.get("policy") == policy and int(item.get("budget") or 0) == budget)
        ]
        rows.append(row)
        _write(metrics_path, {"app": _evidence(app), "runs": rows})
        _write(os.path.join(dump, _stem(policy, budget) + ".config.json"), {
            "app": app, "policy": policy, "budget": budget, "seed": SEED,
        })
        open(os.path.join(dump, _stem(policy, budget) + ".DONE"), "w", encoding="utf-8").write("ok\n")
        print(
            f"[done] {app} {policy} b{budget} confirmed={row.get('confirmed_bugs')} "
            f"episodes={row.get('local_drain_episode_advances')} "
            f"reloc={row.get('residual_frontier_debt_relocations')} "
            f"wall={round(time.time() - t0, 1)}s",
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join("experiments", "runs", "v0325-fresh-transfer"))
    args = parser.parse_args(argv)
    if len(CELLS) != 38:
        raise SystemExit(f"cell count {len(CELLS)}")
    os.makedirs(args.out, exist_ok=True)
    _install()
    _check()
    print(f"planned cells={len(CELLS)} out={args.out}", flush=True)
    for app, policy, budget in CELLS:
        run_cell(app, policy, budget, args.out)
    print("OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
