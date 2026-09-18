"""DeepBench (BuggyFlow) static checks — no browser required."""
import json
import os
import re

from ghostqa.oracle.spec import load_spec

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "apps", "buggy-flow")


def test_manifest_shape_and_depths():
    with open(os.path.join(APP, "bugs.manifest.json"), encoding="utf-8") as f:
        data = json.load(f)
    bugs = data["bugs"]
    assert 12 <= len(bugs) <= 16
    depths = [b["trigger_depth"] for b in bugs]
    assert min(depths) <= 2
    assert max(depths) >= 6
    assert sum(1 for d in depths if d >= 4) >= 3
    assert sum(1 for d in depths if d >= 6) >= 3
    kinds = {b["kind"] for b in bugs}
    for needed in ("js_error", "http_error", "dead_action", "semantic",
                   "blank", "nav_loop"):
        assert needed in kinds, f"missing kind {needed}"
    ids = [b["id"] for b in bugs]
    assert len(ids) == len(set(ids))
    for b in bugs:
        assert b["match"], b["id"]


def test_holdout_is_disjoint():
    with open(os.path.join(APP, "bugs.manifest.json"), encoding="utf-8") as f:
        dev = {b["id"] for b in json.load(f)["bugs"]}
    with open(os.path.join(APP, "holdout.manifest.json"), encoding="utf-8") as f:
        hold = {b["id"] for b in json.load(f)["bugs"]}
    assert dev.isdisjoint(hold)
    assert hold


def test_spec_loads_and_covers_semantic_bugs():
    spec = load_spec(os.path.join(APP, "spec.json"))
    ids = {a["id"] for a in spec}
    with open(os.path.join(APP, "bugs.manifest.json"), encoding="utf-8") as f:
        semantic = [b for b in json.load(f)["bugs"] if b["kind"] == "semantic"]
    for b in semantic:
        assert b["match"]["assert_id"] in ids, b["id"]
    brief_ids = {a["id"] for a in spec}
    assert "project_name_required" in brief_ids
    assert "archived_guest_cannot_edit" in brief_ids


def test_static_does_not_expose_bug_ids():
    static = os.path.join(APP, "static")
    pattern = re.compile(r"data-bug-id|BUG-D\d+|BUG-H\d+")
    for name in os.listdir(static):
        if not name.endswith((".html", ".js")):
            continue
        text = open(os.path.join(static, name), encoding="utf-8").read()
        # Comments in JS may mention BUG-D* for maintainers; the tester-visible
        # DOM must not. HTML shells are data-page only.
        if name.endswith(".html"):
            assert "data-bug-id" not in text
            assert not re.search(r"BUG-[DH]\d+", text)


def test_discovery_auc_bounds():
    from benchmark.web_runner import _auc
    assert _auc([], 10, 5) == 0.0
    # find 1 bug at step 0 of 2 bugs / budget 2 → area 1+1 = 2, / 4 = 0.5
    assert _auc([0], 2, 2) == 0.5
    assert 0 <= _auc([0, 1, 5], 10, 10) <= 1


def test_html_shells_exist():
    static = os.path.join(APP, "static")
    for name in ("index.html", "wizard.html", "project.html", "members.html",
                 "tasks.html", "billing.html", "help.html", "docs.html"):
        assert os.path.exists(os.path.join(static, name)), name
        html = open(os.path.join(static, name), encoding="utf-8").read()
        assert "app.js" in html
        assert "data-page" in html
