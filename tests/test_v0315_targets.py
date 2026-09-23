"""v0.3.15 generator, qualification, and judge isolation. No target policies."""
import hashlib
import inspect
import json
import os
import re

from benchmark.algorithm_freeze import sha256_file
from benchmark.fresh_handoff_generator import (
    APP_NAMES, BUILDERS, ROOT, generate_all, generated_relpaths, lf_bytes, resolve_seed,
)
from benchmark.fresh_handoff_qualify import BRANCH_HORIZON, qualify_topology
from benchmark.fresh_handoff_vocab import FAMILIES, SEED_PREFIX
from benchmark.runner import _check_manifest_discriminative
from ghostqa.oracle.spec import load_spec

PROTOCOL = os.path.join("experiments", "validation", "v0.3.15", "protocol.json")
CANDIDATE = os.path.join("ghostqa", "exploration", "horizon_handoff_guard.py")
FORBIDDEN_SNIPPETS = (
    "ghostqa.exploration",
    "benchmark.web_runner",
    "benchmark.horizon_handoff",
    "benchmark.fresh_handoff_analysis",
    "benchmark.fresh_handoff_run",
    "ghost-structural",
    "bug_discovery_rate",
    "derive_v0314",
    "derive_v0315",
)


def _app(name):
    return os.path.join(ROOT, "apps", name)


def _topo(name):
    with open(os.path.join(_app(name), "topology.json"), encoding="utf-8") as handle:
        return json.load(handle)


def _bugs(name):
    with open(os.path.join(_app(name), "bugs.manifest.json"), encoding="utf-8") as handle:
        return json.load(handle)["bugs"]


def test_seeds_match_protocol_rule():
    proto = json.load(open(PROTOCOL, encoding="utf-8"))
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


def test_pages_bugs_and_static_isolation():
    proto = json.load(open(PROTOCOL, encoding="utf-8"))
    by_app = {item["app"]: item for item in proto["targets"]}
    for name in APP_NAMES:
        fam = FAMILIES[name]
        bugs = _bugs(name)
        assert len(bugs) == fam["bug_count"]
        assert len(bugs) == by_app[name]["bug_count"]
        ids = [bug["id"] for bug in bugs]
        assert ids == by_app[name]["bug_ids"]
        _check_manifest_discriminative(bugs)
        depths = [bug["trigger_depth"] for bug in bugs]
        if fam["control_class"] == "positive":
            assert sum(1 for depth in depths if depth <= 2) >= 2
            assert sum(1 for depth in depths if 3 <= depth <= 4) >= 3
            assert sum(1 for depth in depths if 4 <= depth <= 6) >= 3
            assert sum(1 for depth in depths if depth >= 5) >= 2
            assert sum(1 for depth in depths if depth >= 4) >= 3
            assert sum(1 for depth in depths if depth >= 6) >= 1
        else:
            assert max(depths) <= 3
        kinds = {bug["kind"] for bug in bugs}
        for needed in ("js_error", "blank", "dead_action", "nav_loop", "semantic", "http_error"):
            assert needed in kinds, (name, needed)
        spec = load_spec(os.path.join(_app(name), "spec.json"))
        spec_ids = {item["id"] for item in spec}
        assert "BUG-" not in json.dumps(spec, ensure_ascii=False)
        for bug in bugs:
            if bug["kind"] == "semantic":
                assert bug["match"]["assert_id"] in spec_ids
        static = os.path.join(_app(name), "static")
        for fname in by_app[name]["pages"]:
            assert os.path.isfile(os.path.join(static, fname)), fname
        assert "bugs.manifest.json" not in os.listdir(static)
        assert "topology.json" not in os.listdir(static)
        pattern = re.compile(re.escape(fam["prefix"]) + r"\d+")
        for fname in os.listdir(static):
            text = open(os.path.join(static, fname), encoding="utf-8").read()
            assert pattern.search(text) is None, fname
            assert "bugs.manifest" not in text
            assert "topology.json" not in text
        server = open(os.path.join(_app(name), "server.py"), encoding="utf-8").read()
        assert f"default {fam['port']}" in server or str(fam["port"]) in server
        assert "127.0.0.1" in server


def test_static_qualification_matches_preregistered_rule():
    for name in APP_NAMES:
        topo = _topo(name)
        result = qualify_topology(topo)
        assert result["qualification_ok"] is True, result
        if FAMILIES[name]["control_class"] == "positive":
            assert result["qualified"] is True
            assert result["qualifying_chain_count"] >= 2
            assert result["negative_control_expected"] is False
            roles = result["distinct_child_workflows"]
            assert len(set(roles)) >= 2
            chains = result["qualifying_chains"]
            assert chains[0]["actions"] != chains[1]["actions"]
        else:
            assert result["qualified"] is False
            assert result["qualifying_chain_count"] == 0
            assert result["max_nested_branch_chain"] < BRANCH_HORIZON
            assert result["negative_control_expected"] is True


def test_each_positive_role_has_two_child_actions():
    for name in ("buggy-forum", "buggy-billing", "buggy-lab"):
        topo = _topo(name)
        counts = {}
        for edge in topo["edges"]:
            if edge.get("child_local"):
                role = edge.get("child_workflow_role") or ""
                counts[role] = counts.get(role, 0) + 1
        assert len(counts) >= 2
        for role, count in counts.items():
            assert count >= 2, (name, role, count)


def test_generator_and_qualifier_are_policy_blind():
    import benchmark.fresh_handoff_generator as gen
    import benchmark.fresh_handoff_js as js
    import benchmark.fresh_handoff_qualify as qual
    import benchmark.fresh_handoff_vocab as vocab
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
        generate_all(root=tmp)
        for name in APP_NAMES:
            for rel in generated_relpaths(name):
                committed = os.path.join(ROOT, rel.replace("/", os.sep))
                produced = os.path.join(tmp, rel.replace("/", os.sep))
                assert lf_bytes(committed) == lf_bytes(produced), rel


def test_candidate_source_hash_unchanged():
    assert sha256_file(CANDIDATE) == (
        "827b8e64f953012ceec06fe3e0302c343a016463b5b1f88191e7a0a486c2467e"
    )


def test_builders_cover_exactly_the_four_identities():
    assert set(BUILDERS) == set(APP_NAMES)
