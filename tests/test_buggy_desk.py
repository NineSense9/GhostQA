"""BuggyDesk static correctness — no browser, no target policies."""
import inspect
import json
import os
import re

from ghostqa.oracle.spec import load_spec
from benchmark.runner import _check_manifest_discriminative

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "apps", "buggy-desk")
STATIC = os.path.join(APP, "static")
PAGES = [
    "index.html", "tickets.html", "ticket.html", "customers.html",
    "customer.html", "activity.html", "kb.html", "article.html",
    "reports.html", "team.html", "settings.html", "profile.html",
    "integrations.html", "compose.html", "help.html", "handbook.html",
]


def test_page_count_and_shells():
    assert 12 <= len(PAGES) <= 16
    for name in PAGES:
        path = os.path.join(STATIC, name)
        assert os.path.isfile(path), name
        html = open(path, encoding="utf-8").read()
        assert "app.js" in html
        assert "data-page" in html
        assert "cycle.html" not in name
        assert "return-loop" not in name
        assert "guard-test" not in name


def test_manifest_shape_mix_and_depths():
    with open(os.path.join(APP, "bugs.manifest.json"), encoding="utf-8") as f:
        data = json.load(f)
    bugs = data["bugs"]
    assert 8 <= len(bugs) <= 12
    depths = [b["trigger_depth"] for b in bugs]
    assert sum(1 for d in depths if d <= 2) >= 3
    assert sum(1 for d in depths if 3 <= d <= 4) >= 3
    assert sum(1 for d in depths if d >= 4) >= 2
    kinds = {b["kind"] for b in bugs}
    for needed in ("js_error", "http_error", "dead_action", "semantic",
                   "blank", "nav_loop"):
        assert needed in kinds, needed
    ids = [b["id"] for b in bugs]
    assert len(ids) == len(set(ids))
    _check_manifest_discriminative(bugs)
    for b in bugs:
        assert b["match"], b["id"]
        assert b.get("min_reproduction"), b["id"]


def test_spec_covers_semantic_bugs():
    spec = load_spec(os.path.join(APP, "spec.json"))
    ids = {a["id"] for a in spec}
    with open(os.path.join(APP, "bugs.manifest.json"), encoding="utf-8") as f:
        semantic = [b for b in json.load(f)["bugs"] if b["kind"] == "semantic"]
    for b in semantic:
        assert b["match"]["assert_id"] in ids, b["id"]
    for a in spec:
        blob = json.dumps(a, ensure_ascii=False)
        assert "BUG-K" not in blob
        assert "BUG-" not in blob


def test_static_does_not_leak_bug_ids_or_manifest():
    pattern = re.compile(r"BUG-K\d+|data-bug-id|bugs\.manifest")
    for name in os.listdir(STATIC):
        if not name.endswith((".html", ".js", ".css")):
            continue
        text = open(os.path.join(STATIC, name), encoding="utf-8").read()
        assert not pattern.search(text), name
        assert "cycle.html" not in text
        assert "return-loop" not in text


def test_topology_is_judge_only_and_not_in_static():
    topo_path = os.path.join(APP, "topology.json")
    assert os.path.isfile(topo_path)
    topo = json.load(open(topo_path, encoding="utf-8"))
    assert "judge" in (topo.get("note") or "").lower() or "not served" in (
        topo.get("note") or "").lower()
    assert os.path.isfile(os.path.join(APP, "bugs.manifest.json"))
    static_names = set(os.listdir(STATIC))
    assert "bugs.manifest.json" not in static_names
    assert "topology.json" not in static_names


def test_not_every_bug_is_return_cycle_and_some_need_mutation():
    with open(os.path.join(APP, "bugs.manifest.json"), encoding="utf-8") as f:
        bugs = json.load(f)["bugs"]
    shallow = [b for b in bugs if b["trigger_depth"] <= 2]
    assert any(b["id"] in ("BUG-K1", "BUG-K2", "BUG-K7", "BUG-K8") for b in shallow)
    semantic = [b for b in bugs if b["kind"] == "semantic"]
    assert any("compose" in " ".join(b.get("min_reproduction") or [])
               or "btn_create" in " ".join(b.get("min_reproduction") or [])
               for b in semantic)
    assert any("btn_internal_note" in " ".join(b.get("min_reproduction") or [])
               for b in bugs)
    assert any("btn_reopen" in " ".join(b.get("min_reproduction") or [])
               for b in bugs)


def test_policy_explorer_oracle_do_not_reference_desk_secrets():
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
        "BUG-K1", "BUG-K10", "bugs.manifest.json", "channel handshake",
        "search query too long", "buggy-desk/bugs.manifest",
    )
    for name in mods:
        src = inspect.getsource(__import__(name, fromlist=["x"]))
        for needle in needles:
            assert needle not in src, f"{name} {needle}"
