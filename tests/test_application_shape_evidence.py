"""Evidence-derived v0.3.8 tests. Read only published/evidence, never experiments/runs."""
import inspect
import json
import os

from ghostqa.exploration.explorer import _build_step_event
from ghostqa.exploration.sequence import SequenceController
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, Finding, GUIState, UIElement, Step
from benchmark.algorithm_freeze import DEFAULT_FREEZE, verify_freeze
from benchmark.application_shape import (
    SOURCE_MODELED_SHOP_PAGES, SHOP_DETAIL_LABELS, SHOP_HOME_LABELS,
    html_string_literals,
)
from benchmark.application_shape_evidence import (
    FLOW_POLICIES, PUBLISHED_ROOT, SHOP_POLICIES, canonical_json_bytes,
    derive_canonical_analysis, derive_flow_policy, derive_shop_collapse,
    derive_shop_policy, evidence_path, load_json, load_jsonl, sha256_bytes,
    sha256_file, steps_only, verify_manifest,
)
from benchmark.diagnostic_runner import wrap_sequence_after
try:
    from helpers import make_hub_state
except ImportError:
    from tests.helpers import make_hub_state


def _root():
    return PUBLISHED_ROOT


def test_freeze_still_matches():
    assert verify_freeze(DEFAULT_FREEZE) == []


def test_v038_evidence_manifest_hashes():
    man = load_json(os.path.join(_root(), "evidence-manifest.json"))
    bad = verify_manifest(_root(), man)
    assert bad == []
    paths = [f["relative_path"] for f in man["files"]]
    assert len(paths) == len(set(paths))
    for rec in man["files"]:
        assert rec["budget"] == 120
        assert rec["seed"] == 1
        assert rec["diagnostic_rerun"] is True
        assert rec["independent_trial"] is False
        assert rec["app"] in ("buggy-shop", "buggy-flow")
        assert rec["policy"]


def test_v038_evidence_matrix_complete():
    man = load_json(os.path.join(_root(), "evidence-manifest.json"))
    kinds = {("shop" if f["app"] == "buggy-shop" else "flow",
              f["policy"], f["evidence_kind"]) for f in man["files"]}
    for pol in SHOP_POLICIES:
        for k in ("events", "graph", "sequence_events"):
            assert ("shop", pol, k) in kinds
    for pol in FLOW_POLICIES:
        for k in ("events", "graph", "sequence_events"):
            assert ("flow", pol, k) in kinds


def test_published_shop_lock_is_trace_derived():
    for pol in ("ghost-sequence", "ghost-structural-memory"):
        d = derive_shop_policy(_root(), pol)
        assert d["n_states"] == 6
        assert d["n_urls"] == 4
        obs = d["observed"]
        assert obs["branch_start_events"] == 2
        assert obs["return_attempt_events"] == 116
        assert obs["successful_return_to_parent_events"] == 0
        assert obs["sequence_terminal_outcomes"]["lost_parent"] == 1
        assert obs["sequence_terminal_outcomes"]["finding"] == 1
        assert obs["sequence_terminal_outcomes"]["returned"] == 0
    bfs = derive_shop_policy(_root(), "bfs")
    assert bfs["n_states"] == 41
    assert bfs["n_urls"] == 11
    deferred = derive_shop_policy(_root(), "ghost-deferred")
    assert deferred["n_states"] == 34
    assert deferred["n_urls"] == 11


def test_parent_hub_mismatch_cart_index_not_detail():
    ev = load_jsonl(evidence_path(_root(), "shop", "ghost-structural-memory",
                                  "events.jsonl"))
    parent = None
    for e in ev:
        if e.get("kind") == "seq_after" and e.get("active_branch", "").endswith("btn_add"):
            parent = e.get("parent_hub_cluster")
            break
    assert parent
    returning_urls = []
    for e in ev:
        if e.get("kind") == "step" and e.get("returning") is True:
            returning_urls.append(e.get("src_url") or "")
            returning_urls.append(e.get("dst_url") or "")
    blob = " ".join(returning_urls)
    assert "cart.html" in blob and "index.html" in blob
    assert "detail.html" not in blob


def test_published_h1_divergence():
    dfs = derive_flow_policy(_root(), "dfs")
    bfs = derive_flow_policy(_root(), "bfs")
    deferred = derive_flow_policy(_root(), "ghost-deferred")
    c0 = derive_flow_policy(_root(), "ghost-sequence")
    c1 = derive_flow_policy(_root(), "ghost-structural-memory")
    assert dfs["first_action"] == "nav_settings"
    assert dfs["h1_confirm_step"] == 8
    assert bfs["h1_confirm_step"] == 28
    assert deferred["h1_confirm_step"] == 93
    assert c0["first_action"] == "nav_login"
    assert c0["settings_visits"] == 0
    assert c0["changelog_visits"] == 0
    assert c0["h1_confirm_step"] is None
    assert c1["first_action"] == "nav_login"
    assert c1["settings_visits"] == 0
    assert c1["changelog_visits"] == 0
    assert c1["h1_confirm_step"] is None


def test_published_h2_behavior():
    dfs = derive_flow_policy(_root(), "dfs")
    bfs = derive_flow_policy(_root(), "bfs")
    c0 = derive_flow_policy(_root(), "ghost-sequence")
    deferred = derive_flow_policy(_root(), "ghost-deferred")
    c1 = derive_flow_policy(_root(), "ghost-structural-memory")
    assert dfs["billing_entry_steps"] == []
    assert bfs["billing_entry_steps"] == []
    assert c0["billing_entry_steps"] == []
    assert deferred["billing_entry_steps"]
    assert deferred["qty_actions"] == []
    assert c1["billing_entry_steps"] == [32, 53, 87, 97]
    assert c1["qty_actions"] == [
        [33, "up"], [34, "down"], [35, "up"],
        [54, "up"], [55, "down"], [56, "up"],
        [88, "up"], [89, "down"], [90, "up"],
        [98, "down"],
    ]
    assert c1["h2_finding"] is False


def test_reproduce_cli_verify_uses_published_evidence_only():
    from benchmark.application_shape_reproduce import verify
    assert verify(_root()) == 0


def test_v038_offline_analysis_reproduces_published():
    analysis = derive_canonical_analysis(_root())
    published = os.path.join(_root(), "metrics", "analysis.json")
    expected = sha256_file(published)
    got = sha256_bytes(canonical_json_bytes(analysis))
    assert got == expected


def test_shape_module_has_no_seed_bug_ids():
    src = inspect.getsource(
        __import__("benchmark.application_shape", fromlist=["x"]))
    assert "BUG-W1" not in src
    assert "bugs.manifest" not in src


def test_source_modeled_shop_routes_exist_in_app_js():
    lit = html_string_literals(os.path.join("apps", "buggy-shop", "static", "app.js"))
    text = open(os.path.join("apps", "buggy-shop", "static", "app.js"),
                encoding="utf-8").read()
    for src, dsts in SOURCE_MODELED_SHOP_PAGES.items():
        assert src in lit
        for d in dsts:
            assert d in lit
    for label in SHOP_HOME_LABELS + SHOP_DETAIL_LABELS:
        assert label in text


def test_build_step_event_is_pure_serialization():
    el = UIElement("a", "button", "A", kind="click")
    state = GUIState("t", "/x", "X", elements=(el,), obs={})
    g = StateGraph()
    g.add_state("s1", "/x", "X")
    g.add_state("s2", "/y", "Y")
    g.nodes["s1"].visits = 3
    step = Step(0, "s1", Action("click", "a"), "s2", findings=[], decision_mode="branch")
    exec_result = type("R", (), {"crashed": False, "js_errors": [],
                                 "http_errors": [], "events": []})()
    before = (g.nodes["s1"].visits, step.decision_mode, step.state_sig_before)
    ev = _build_step_event(step, g, state, state, "new", exec_result, 1, 0)
    assert ev["decision_mode"] == "branch"
    assert (g.nodes["s1"].visits, step.decision_mode, step.state_sig_before) == before
    src = inspect.getsource(_build_step_event)
    assert "policy.select" not in src
    assert "oracle.inspect" not in src
    assert "executor.execute" not in src


def test_diagnostic_after_hook_parity():
    g = StateGraph()
    g.add_state("h", "/hub", "Hub", cluster_id="hub")
    hub = make_hub_state()
    a = SequenceController("sequence")
    b = SequenceController("sequence")
    sink = []
    orig = wrap_sequence_after(b, sink)
    args = ("h", Action("click", "go_a"), hub, hub, "new", [], "x", False, g, 1)
    a.after(*args)
    b.after(*args)
    assert orig is not b.after
    assert a.ledger.active_branch == b.ledger.active_branch
    assert a.ledger.returning == b.ledger.returning
    assert a.ledger.commitment_left == b.ledger.commitment_left
    assert a.ledger.parent_hub_cluster == b.ledger.parent_hub_cluster
    assert [e.get("event") for e in a.events] == [e.get("event") for e in b.events]
    assert len(sink) == 1


def test_shop_collapse_json_matches_raw_evidence():
    derived = derive_shop_collapse(_root())
    published = load_json(os.path.join(_root(), "metrics", "shop-collapse.json"))
    assert published["observed"]["ghost-structural-memory"][
        "successful_return_to_parent_events"] == 0
    assert published["observed"]["ghost-structural-memory"][
        "return_attempt_events"] == 116
    assert published["observed"]["old_return_success_events"] == 2
    assert published == derived
