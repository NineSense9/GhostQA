"""One-shot 40-cell runner for the v0.3.35 search-submit transfer.

Guard and the new candidate on the new suite, the candidate on the historical
list, and the candidate on Campus and Studio. Completed cells are not rerun.
Cells of one app stay in one process. Different apps run together.
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
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

from benchmark.algorithm_freeze import sha256_file, verify_freeze
from benchmark.web_runner import run_one
import benchmark.web_runner as web_runner

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = 1
CANDIDATE = "ghost-structural-search-submit-guard"
GUARD = "ghost-structural-return-guard"
SUITE_FREEZE = os.path.join(
    ROOT, "experiments", "frozen", "v0.3.35-fresh-transfer-suite", "freeze.json")
CANDIDATE_FREEZE = os.path.join(
    ROOT, "experiments", "frozen", "ghost-search-submit-v0.3.35", "freeze.json")
PARENT_SOURCE = os.path.join(
    ROOT, "ghostqa", "exploration", "alternate_payload_guard.py")
PARENT_SHA = "fef17c7441df69e68f083ec04e201e2a942b0be6cacf59a054e135d09b49d018"
EPISODE_SOURCE = os.path.join(
    ROOT, "ghostqa", "exploration", "episode_drain_epoch_guard.py")
EPISODE_SHA = "9403e81f34625ff225f4cca69bf65c992d937305cb3a516a8be12a7bc9e08d45"
REPEAT_SOURCE = os.path.join(
    ROOT, "ghostqa", "exploration", "repeat_click_guard.py")
REPEAT_SHA = "e52e87a312120f838e6b9d922928f7666824d6f7fd32c4e73c3b5e538f41b501"
BUTTON_SOURCE = os.path.join(
    ROOT, "ghostqa", "exploration", "payload_button_guard.py")
BUTTON_SHA = "9f65597aa16971d8afae1a83c6e666fea800745df88dca67a3b50764530ffc52"
PAGE_SOURCE = os.path.join(
    ROOT, "ghostqa", "exploration", "page_buttons_guard.py")
PAGE_SHA = "0d933edc834928a70c46af07a24091379e5b1ec3cdd81e18e1a4845d92464d81"
SEEN_SOURCE = os.path.join(
    ROOT, "ghostqa", "exploration", "seen_button_guard.py")
SEEN_SHA = "6db20305153d89712c3ef0e9998c254a31cd96c6da338a5242e88cb649ed3449"
POSITIVE = ("buggy-quarry", "buggy-rapid", "buggy-shoal", "buggy-tundra")
NEGATIVE = ("buggy-umber", "buggy-verge")
HISTORICAL = (
    "buggy-lab", "buggy-flow", "buggy-forum", "buggy-billing", "buggy-directory",
    "buggy-crm", "buggy-ops", "buggy-desk", "buggy-wiki", "buggy-shop",
)
INSPECTED = ("buggy-campus", "buggy-studio")
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
INSPECTED_CELLS = [(_app, CANDIDATE, 120) for _app in INSPECTED]
CELLS = FRESH_CELLS + HIST_CELLS + INSPECTED_CELLS
WORKERS = 6


_ORIGINAL = web_runner.make_policy


def _policy(name: str, seed: int):
    if name == CANDIDATE:
        from ghostqa.exploration.search_submit_guard import (
            SearchSubmitGuardGhostPolicy,
        )
        return SearchSubmitGuardGhostPolicy(llm=None)
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
    if sha256_file(PARENT_SOURCE) != PARENT_SHA:
        raise SystemExit("v0.3.31 candidate source changed")
    if sha256_file(EPISODE_SOURCE) != EPISODE_SHA:
        raise SystemExit("v0.3.24 candidate source changed")
    if sha256_file(REPEAT_SOURCE) != REPEAT_SHA:
        raise SystemExit("v0.3.30 candidate source changed")
    if sha256_file(BUTTON_SOURCE) != BUTTON_SHA:
        raise SystemExit("v0.3.32 candidate source changed")
    if sha256_file(PAGE_SOURCE) != PAGE_SHA:
        raise SystemExit("v0.3.33 candidate source changed")
    if sha256_file(SEEN_SOURCE) != SEEN_SHA:
        raise SystemExit("v0.3.34 candidate source changed")


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
            f"search={row.get('search_submit_selections')} "
            f"seen={row.get('seen_button_stops')} "
            f"page={row.get('page_button_selections')} "
            f"button={row.get('payload_button_selections')} "
            f"payload={row.get('alternate_payload_selections')} "
            f"episodes={row.get('local_drain_episode_advances')} "
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


def run_app(app: str, cells: list, out_root: str) -> str:
    _install()
    for policy, budget in cells:
        try:
            run_cell(app, policy, budget, out_root)
        except SystemExit as exc:
            raise RuntimeError(f"{app} {policy} b{budget} failed: {exc}") from exc
    print(f"[app-done] {app}", flush=True)
    return app


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join("experiments", "runs", "v0335-fresh-transfer"))
    parser.add_argument("--workers", type=int, default=WORKERS)
    args = parser.parse_args(argv)
    if len(CELLS) != 40:
        raise SystemExit(f"cell count {len(CELLS)}")
    os.makedirs(args.out, exist_ok=True)
    _install()
    _check()
    grouped = defaultdict(list)
    for app, policy, budget in CELLS:
        grouped[app].append((policy, budget))
    print(f"planned cells={len(CELLS)} apps={len(grouped)} workers={args.workers} out={args.out}", flush=True)
    failures = []
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {
            pool.submit(run_app, app, cells, args.out): app
            for app, cells in grouped.items()
        }
        for future in as_completed(futures):
            app = futures[future]
            try:
                future.result()
            except Exception as exc:
                failures.append(f"{app}: {exc}")
                print(f"[app-fail] {app} {exc}", flush=True)
                for pending in futures:
                    pending.cancel()
                break
    if failures:
        raise SystemExit("matrix failed\n" + "\n".join(failures))
    print("OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
