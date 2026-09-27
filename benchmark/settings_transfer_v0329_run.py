"""Two inspected cells for the v0.3.29 settings-button check.

Does not change the frozen v0.3.27 candidate.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

from benchmark.algorithm_freeze import sha256_file
from benchmark.web_runner import run_one
import benchmark.web_runner as web_runner

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLICY = "ghost-structural-parent-hub-sibling-guard"
SEED = 1
BUDGET = 120
CELLS = ("buggy-campus", "buggy-studio")
PARENT_SHA = "33a479db2f062071438bb05c4b8dcc90a7a85bdcec4b97e54ebf06d2ebf7183b"
EPISODE_SHA = "9403e81f34625ff225f4cca69bf65c992d937305cb3a516a8be12a7bc9e08d45"
SIBLING_SHA = "0a425a46df8884bc8260bf2c9fa1ac3c85da6a7931b7dec2899a94b9daac35dd"


def _policy(name: str, seed: int):
    if name == POLICY:
        from ghostqa.exploration.parent_hub_sibling_guard import (
            ParentHubSiblingGuardGhostPolicy,
        )
        return ParentHubSiblingGuardGhostPolicy(llm=None)
    raise SystemExit(f"refusing policy {name}")


def _check() -> None:
    base = os.path.join(ROOT, "ghostqa", "exploration")
    if sha256_file(os.path.join(base, "parent_hub_sibling_guard.py")) != PARENT_SHA:
        raise SystemExit("v0.3.27 candidate changed")
    if sha256_file(os.path.join(base, "untried_sibling_guard.py")) != SIBLING_SHA:
        raise SystemExit("v0.3.26 candidate changed")
    if sha256_file(os.path.join(base, "episode_drain_epoch_guard.py")) != EPISODE_SHA:
        raise SystemExit("v0.3.24 candidate changed")


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


def run_cell(app: str, out_root: str) -> None:
    if app not in CELLS:
        raise SystemExit(f"refusing {app}")
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
    dump = os.path.join(out_root, "evidence", app)
    os.makedirs(dump, exist_ok=True)
    try:
        _wait(base + "/index.html")
        t0 = time.time()
        print(f"[start] {app} {POLICY} b{BUDGET}", flush=True)
        row = run_one(
            base, {"pw": pw, "browser": browser}, POLICY, SEED, BUDGET,
            spec, manifest, skip_minimize=True, dump_dir=dump)
        row["app"] = app
        path = os.path.join(dump, "metrics.json")
        payload = {"app": app, "runs": [row]}
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        open(os.path.join(dump, f"{POLICY}_b{BUDGET}_s{SEED}.DONE"), "w", encoding="utf-8").write("ok\n")
        print(
            f"[done] {app} confirmed={row.get('confirmed_bugs')} wall={round(time.time() - t0, 1)}s",
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


def main() -> int:
    web_runner.make_policy = _policy
    out = os.path.join(ROOT, "experiments", "runs", "v0329-settings-transfer")
    os.makedirs(out, exist_ok=True)
    _check()
    for app in CELLS:
        run_cell(app, out)
    print("OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
