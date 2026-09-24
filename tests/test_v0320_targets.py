"""v0.3.20 generator, qualification, and judge isolation. No target policies."""
import hashlib
import inspect
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

from benchmark.algorithm_freeze import sha256_file
from benchmark.fresh_composite_generator import (
    APP_NAMES, ROOT, generate_all, generated_relpaths, lf_bytes,
)
from benchmark.fresh_composite_qualify import BRANCH_HORIZON, qualify_topology
from benchmark.fresh_composite_registry import FRESH, HISTORICAL_KEYS, fresh_port, resolve
from benchmark.fresh_composite_vocab import FAMILIES, POSITIVE, SEED_PREFIX, resolve_seed
from benchmark.runner import _check_manifest_discriminative
from benchmark.web_runner import APPS as HISTORICAL_APPS
from ghostqa.oracle.spec import load_spec

PROTOCOL = os.path.join("experiments", "validation", "v0.3.20", "protocol.json")
CANDIDATE = os.path.join("ghostqa", "exploration", "finding_return_entry_guard.py")
CANDIDATE_SHA = "0bfec3c7bd2811f154daa83bc81fde632976b8ab6e1da9ee6a208cf81c4bb42c"
FORBIDDEN_SNIPPETS = (
    "ghostqa.exploration",
    "benchmark.web_runner",
    "benchmark.fresh_composite_analysis",
    "benchmark.fresh_composite_run",
    "benchmark.finding_return_entry",
    "ghost-structural",
    "bug_discovery_rate",
    "derive_v0319",
    "derive_v0320",
)
LEAKS = (
    "finding_return_opportunity",
    "finding_return_entry",
    "nested_handoff",
    "horizon_only",
    "bugs.manifest",
    "mechanism-opportunities",
)


def _app(name):
    return os.path.join(ROOT, "apps", name)


def _topo(name):
    with open(os.path.join(_app(name), "topology.json"), encoding="utf-8") as handle:
        return json.load(handle)


def _bugs(name):
    with open(os.path.join(_app(name), "bugs.manifest.json"), encoding="utf-8") as handle:
        return json.load(handle)["bugs"]


def _proto():
    with open(PROTOCOL, encoding="utf-8") as handle:
        return json.load(handle)


def test_seeds_match_protocol_rule():
    proto = _proto()
    by_app = {item["app"]: item for item in proto["targets"]}
    for name in APP_NAMES:
        seed, hex8 = resolve_seed(name)
        digest = hashlib.sha256((SEED_PREFIX + name).encode("utf-8")).hexdigest()
        assert hex8 == digest[:8]
        assert seed == int(digest[:8], 16)
        assert by_app[name]["seed"] == seed
        assert by_app[name]["seed_hex"] == hex8
        assert FAMILIES[name]["family"] == by_app[name]["topology_family"]
        assert FAMILIES[name]["port"] == by_app[name]["default_port"]
        assert fresh_port(name) == by_app[name]["default_port"]


def test_pages_bugs_and_static_isolation():
    proto = _proto()
    by_app = {item["app"]: item for item in proto["targets"]}
    for name in APP_NAMES:
        fam = FAMILIES[name]
        bugs = _bugs(name)
        assert len(bugs) == fam["bug_count"]
        assert [bug["id"] for bug in bugs] == by_app[name]["bug_ids"]
        _check_manifest_discriminative(bugs)
        depths = [bug["trigger_depth"] for bug in bugs]
        if fam["control_class"] == "positive":
            assert sum(1 for depth in depths if depth <= 2) >= 2
            assert sum(1 for depth in depths if 3 <= depth <= 4) >= 3
            assert sum(1 for depth in depths if 4 <= depth <= 6) >= 4
            assert sum(1 for depth in depths if depth >= 5) >= 2
            assert sum(1 for depth in depths if depth >= 4) >= 4
            assert sum(1 for depth in depths if depth >= 6) >= 1
        else:
            assert max(depths) <= 3
        kinds = {bug["kind"] for bug in bugs}
        for needed in ("js_error", "nav_loop", "semantic", "http_error", "dead_action"):
            assert needed in kinds, (name, needed)
        if name != "buggy-kiosk":
            assert "blank" in kinds
        spec = load_spec(os.path.join(_app(name), "spec.json"))
        spec_ids = {item["id"] for item in spec}
        blob = json.dumps(spec, ensure_ascii=False)
        assert "BUG-" not in blob
        for bug in bugs:
            if bug["kind"] == "semantic":
                assert bug["match"]["assert_id"] in spec_ids
        static = os.path.join(_app(name), "static")
        for fname in by_app[name]["pages"]:
            assert os.path.isfile(os.path.join(static, fname)), fname
        for hidden in ("bugs.manifest.json", "topology.json", "mechanism-opportunities.json", "spec.json"):
            assert hidden not in os.listdir(static)
        pattern = re.compile(re.escape(fam["prefix"]) + r"\d+")
        for fname in os.listdir(static):
            text = open(os.path.join(static, fname), encoding="utf-8").read()
            assert pattern.search(text) is None, fname
            for leak in LEAKS:
                assert leak not in text, (fname, leak)
        server = open(os.path.join(_app(name), "server.py"), encoding="utf-8").read()
        assert str(fam["port"]) in server
        assert "127.0.0.1" in server


def test_static_qualification_matches_preregistered_rule():
    for name in APP_NAMES:
        row = qualify_topology(_topo(name))
        assert row["qualification_ok"] is True, row
        assert row["branch_horizon"] == BRANCH_HORIZON
        if name in POSITIVE:
            assert row["class"] == "positive"
            assert row["qualified"] is True
            assert row["nested_handoff_opportunity_count"] >= 2
            assert len(set(row["distinct_child_workflows"])) >= 2
            chains = row["qualifying_chains"]
            assert chains[0]["actions"] != chains[1]["actions"]
            assert all(item["crosses_branch_horizon"] for item in chains)
            assert row["finding_return_entry_opportunity_count"] >= 1
            assert row["horizon_only_return_entry_control_count"] >= 1
            assert row["state_variant_return_count"] >= 1
            assert row["finding_and_horizon_distinct"] is True
            rich = [
                item for item in row["finding_return_opportunities"]
                if item["eligible_button_count"] >= 2
            ]
            assert rich
            assert row["horizon_only_controls"][0]["eligible_button_count"] >= 1
        elif name == "buggy-catalog":
            assert row["class"] == "negative"
            assert row["positive_class"] is False
            assert row["nested_handoff_opportunity_count"] == 0
            assert row["handoff_edge_count"] == 0
            assert row["finding_return_entry_opportunity_count"] == 0
            assert row["finding_return_entry_any_button_count"] == 0
            assert row["max_nested_branch_depth"] < BRANCH_HORIZON
        else:
            assert row["class"] == "negative"
            assert row["nested_handoff_opportunity_count"] == 0
            assert row["handoff_edge_count"] == 0
            assert row["finding_return_entry_opportunity_count"] >= 2
            assert row["horizon_only_return_entry_control_count"] >= 1


def test_generator_and_qualifier_are_policy_blind():
    import benchmark.fresh_composite_generator as gen
    import benchmark.fresh_composite_js as js
    import benchmark.fresh_composite_qualify as qual
    import benchmark.fresh_composite_vocab as vocab
    blob = "\n".join(inspect.getsource(mod) for mod in (gen, js, qual, vocab))
    for needle in FORBIDDEN_SNIPPETS:
        assert needle not in blob, needle
    candidate = open(CANDIDATE, encoding="utf-8").read()
    for name in APP_NAMES:
        assert name not in candidate
    for root, dirs, files in os.walk(os.path.join(ROOT, "ghostqa", "exploration")):
        dirs[:] = [item for item in dirs if item != "__pycache__"]
        for fname in files:
            if not fname.endswith(".py"):
                continue
            text = open(os.path.join(root, fname), encoding="utf-8").read()
            for name in APP_NAMES:
                assert name not in text, fname


def test_regeneration_is_deterministic():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        generate_all(root=tmp)
        for name in APP_NAMES:
            for rel in generated_relpaths(name):
                committed = os.path.join(ROOT, rel.replace("/", os.sep))
                produced = os.path.join(tmp, rel.replace("/", os.sep))
                assert lf_bytes(committed) == lf_bytes(produced), rel


def test_candidate_source_hash_unchanged():
    assert sha256_file(CANDIDATE) == CANDIDATE_SHA


def test_registry_adds_six_apps_without_changing_historical_map():
    assert tuple(HISTORICAL_APPS) == HISTORICAL_KEYS
    assert set(FRESH) == set(APP_NAMES)
    ports = [fresh_port(name) for name in APP_NAMES]
    assert ports == [3951, 3952, 3953, 3954, 3955, 3956]
    assert len(set(ports)) == 6
    for name in HISTORICAL_KEYS:
        assert os.path.isdir(resolve(name))
        assert resolve(name) == HISTORICAL_APPS[name]
    for name in APP_NAMES:
        assert os.path.isdir(resolve(name))
        assert os.path.isfile(os.path.join(resolve(name), "spec.json"))


def _free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_servers_hide_judge_artifacts():
    proto = _proto()
    by_app = {item["app"]: item for item in proto["targets"]}
    for name in APP_NAMES:
        port = _free_port()
        proc = subprocess.Popen(
            [sys.executable, os.path.join(_app(name), "server.py"), str(port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        base = f"http://127.0.0.1:{port}"
        try:
            for _ in range(50):
                try:
                    urllib.request.urlopen(base + "/index.html", timeout=1)
                    break
                except Exception:
                    time.sleep(0.1)
            else:
                raise AssertionError(name + " did not start")
            for page in by_app[name]["pages"]:
                with urllib.request.urlopen(base + "/" + page, timeout=3) as resp:
                    assert resp.status == 200, (name, page)
            for hidden in (
                "/bugs.manifest.json",
                "/mechanism-opportunities.json",
                "/topology.json",
                "/spec.json",
                "/generation.json",
            ):
                try:
                    urllib.request.urlopen(base + hidden, timeout=3)
                except urllib.error.HTTPError as exc:
                    assert exc.code == 404, (name, hidden, exc.code)
                else:
                    raise AssertionError(name + " served " + hidden)
            req = urllib.request.Request(base + "/api/export", data=b"{}", method="POST")
            try:
                urllib.request.urlopen(req, timeout=3)
            except urllib.error.HTTPError as exc:
                assert exc.code == 500, (name, exc.code)
            else:
                raise AssertionError(name + " export did not fail")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
