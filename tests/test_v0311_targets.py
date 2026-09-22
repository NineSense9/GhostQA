"""v0.3.11 generated-app static correctness. No target policies."""
import hashlib
import inspect
import json
import os
import re
import tempfile

from ghostqa.oracle.spec import load_spec
from benchmark.runner import _check_manifest_discriminative
from benchmark.multitarget_generator import (
    APP_NAMES, FAMILIES, generate_all, generated_relpaths, lf_bytes,
)
from benchmark.multitarget_vocab import SEED_PREFIX, resolve_seed, vocab_for
from benchmark.multitarget_generator import ROOT

PROTOCOL_SEEDS = {
    "buggy-crm": (1059087843, "3f2065e3"),
    "buggy-wiki": (3204138653, "befb469d"),
    "buggy-ops": (4252390393, "fd7653f9"),
}


def _app(name):
    return os.path.join(ROOT, "apps", name)


def test_protocol_seeds_match_derivation_rule():
    for name, (seed, hex8) in PROTOCOL_SEEDS.items():
        got_seed, got_hex = resolve_seed(name)
        assert got_hex == hex8
        assert got_seed == seed
        digest = hashlib.sha256((SEED_PREFIX + name).encode("utf-8")).hexdigest()
        assert digest[:8] == hex8
        assert int(digest[:8], 16) == seed


def test_page_counts_and_shells():
    for name in APP_NAMES:
        fam = FAMILIES[name]
        pages = [p[0] for p in fam["pages"]]
        assert 10 <= len(pages) <= 16
        static = os.path.join(_app(name), "static")
        for fname in pages:
            path = os.path.join(static, fname)
            html = open(path, encoding="utf-8").read()
            assert "app.js" in html
            assert "data-page" in html
            assert "cycle.html" not in fname
            assert "return-loop" not in fname
            assert "guard-test" not in fname


def test_manifest_mix_and_spec():
    for name in APP_NAMES:
        app = _app(name)
        bugs = json.load(open(os.path.join(app, "bugs.manifest.json"), encoding="utf-8"))["bugs"]
        assert 8 <= len(bugs) <= 10
        depths = [b["trigger_depth"] for b in bugs]
        assert sum(1 for d in depths if d <= 2) >= 3
        assert sum(1 for d in depths if 3 <= d <= 4) >= 3
        assert sum(1 for d in depths if d >= 4) >= 2
        kinds = {b["kind"] for b in bugs}
        for needed in ("js_error", "http_error", "dead_action", "semantic",
                       "blank", "nav_loop"):
            assert needed in kinds, (name, needed)
        assert len({b["id"] for b in bugs}) == len(bugs)
        _check_manifest_discriminative(bugs)
        spec = load_spec(os.path.join(app, "spec.json"))
        ids = {a["id"] for a in spec}
        for b in bugs:
            if b["kind"] == "semantic":
                assert b["match"]["assert_id"] in ids, b["id"]
        blob = json.dumps(spec, ensure_ascii=False)
        assert "BUG-" not in blob
        assert any(b["kind"] == "semantic" for b in bugs)
        assert any(b["kind"] == "dead_action" for b in bugs)
        assert any("search_box" in " ".join(b.get("min_reproduction") or [])
                   for b in bugs)
        assert any(b["trigger_depth"] >= 4 for b in bugs)
        unrelated = [b for b in bugs if b["kind"] in ("blank", "http_error")]
        assert unrelated, name


def test_static_does_not_leak_bug_ids():
    for name in APP_NAMES:
        static = os.path.join(_app(name), "static")
        prefix = FAMILIES[name]["prefix"]
        pattern = re.compile(prefix + r"\d+|data-bug-id|bugs\.manifest|topology\.manifest")
        for fname in os.listdir(static):
            if not fname.endswith((".html", ".js", ".css")):
                continue
            text = open(os.path.join(static, fname), encoding="utf-8").read()
            assert not pattern.search(text), (name, fname)


def test_judge_files_not_served_from_static():
    for name in APP_NAMES:
        static = set(os.listdir(os.path.join(_app(name), "static")))
        assert "bugs.manifest.json" not in static
        assert "topology.manifest.json" not in static
        topo = json.load(open(os.path.join(_app(name), "topology.manifest.json"),
                              encoding="utf-8"))
        note = (topo.get("note") or "").lower()
        assert "judge" in note or "not served" in note


def test_policy_modules_do_not_read_v0311_secrets():
    mods = [
        "ghostqa.exploration.policy",
        "ghostqa.exploration.sequence",
        "ghostqa.exploration.sequence_memory",
        "ghostqa.exploration.payload",
        "ghostqa.exploration.explorer",
        "ghostqa.exploration.return_cycle_guard",
        "ghostqa.oracle.engine",
        "ghostqa.oracle.spec",
    ]
    needles = (
        "BUG-C1", "BUG-W1", "BUG-O1", "bugs.manifest.json",
        "topology.manifest.json", "crm sync handshake",
        "wiki plugin handshake", "ops pager handshake",
        "buggy-crm/bugs.manifest", "buggy-wiki/bugs.manifest",
        "buggy-ops/bugs.manifest",
    )
    for mod in mods:
        src = inspect.getsource(__import__(mod, fromlist=["x"]))
        for needle in needles:
            assert needle not in src, f"{mod} {needle}"


def test_generator_has_no_policy_feedback():
    import benchmark.multitarget_generator as gen
    import benchmark.multitarget_js as js
    import benchmark.multitarget_vocab as vocab
    blob = inspect.getsource(gen) + inspect.getsource(js) + inspect.getsource(vocab)
    for needle in (
        "ghost-structural-return-guard", "make_policy", "run_exploration",
        "GhostPolicy", "BFSPolicy", "DFSPolicy", "return_cycle_escape",
        "bug_discovery_rate",
    ):
        assert needle not in blob, needle


def test_regeneration_is_lf_deterministic():
    with tempfile.TemporaryDirectory() as td:
        generate_all(root=td)
        generate_all(root=td)
        for name in APP_NAMES:
            for rel in generated_relpaths(name):
                committed = os.path.join(ROOT, rel.replace("/", os.sep))
                produced = os.path.join(td, rel.replace("/", os.sep))
                assert lf_bytes(committed) == lf_bytes(produced), rel


def test_vocab_only_depends_on_identity_and_seed():
    a = vocab_for("buggy-crm")
    b = vocab_for("buggy-crm")
    assert a == b
    assert a["seed"] == PROTOCOL_SEEDS["buggy-crm"][0]
