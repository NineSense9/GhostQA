"""v0.3.8 application-shape facts. Must not change frozen algorithm files."""
from ghostqa.exploration.sequence import is_branch_click, is_hub, branch_clicks
from ghostqa.oracle.engine import OracleEngine
from ghostqa.oracle.spec import load_spec
from ghostqa.state.models import Action, GUIState
from benchmark.algorithm_freeze import DEFAULT_FREEZE, verify_freeze
from benchmark.application_shape import (
    H2_CLICKS_TO_VIOLATE, H2_INITIAL_QTY, SOURCE_MODELED_SHOP_PAGES,
    SHOP_DETAIL_LABELS, SHOP_HOME_LABELS, flow_billing_state,
    flow_changelog_state, flow_home_state, flow_settings_state,
    graph_descriptors, html_string_literals, label_text, page_depths,
    shop_detail_state, shop_home_state, static_shop_descriptors,
)
from benchmark.web_runner import make_policy
from ghostqa.exploration.policy import GhostPolicy
from ghostqa.agent.gateway import NullLLM


def test_freeze_still_matches_after_shape_tooling():
    assert verify_freeze(DEFAULT_FREEZE) == []


def test_product_default_still_no_sequence():
    p = GhostPolicy(NullLLM())
    assert p.use_frontier is False
    assert p.sequence_mode in ("off", None, "") or not p.sequence.enabled()


def test_shop_detail_is_also_a_hub_nested():
    """Nested hub is the collapse trigger: detail has 3 non-return clicks."""
    st = shop_detail_state()
    assert is_hub(st)
    eids = {a.target_eid for a in branch_clicks(st)}
    assert "btn_add" in eids and "btn_buy" in eids
    assert "back_list" not in eids


def test_shop_home_is_a_hub_with_four_branches():
    st = shop_home_state()
    assert is_hub(st)
    eids = {a.target_eid for a in branch_clicks(st)}
    assert "cart" in eids and "products" in eids
    assert "login" not in eids  # progress
    assert "register" not in eids
    d = static_shop_descriptors()
    assert d["home_is_hub"] is True
    assert d["max_shortest_path_depth"] <= 3


def test_flow_home_is_not_a_hub_all_progress_or_distractor():
    st = flow_home_state()
    assert not is_hub(st)
    assert [label_text(el.text) for el in st.elements] == [
        "progress", "progress", "distractor", "distractor", "distractor"]


def test_changelog_and_settings_are_distractors_not_branches():
    settings = flow_settings_state()
    changelog = Action("click", "nav_changelog")
    assert not is_branch_click(changelog, settings)
    assert label_text("更新日志") == "distractor"
    assert label_text("系统设置") == "distractor"
    cl = flow_changelog_state()
    detail = Action("click", "btn_changelog_detail")
    assert is_branch_click(detail, cl) or cl.elements[-1].text == "查看详情"


def test_h2_requires_two_qty_downs_from_default():
    assert H2_INITIAL_QTY == 1
    assert H2_CLICKS_TO_VIOLATE == 2
    spec = load_spec("apps/buggy-flow/spec.json")
    oracle = OracleEngine(spec)
    before = flow_billing_state("0")
    after = flow_billing_state("-1")
    after.url = "http://127.0.0.1/billing.html"
    before.url = "http://127.0.0.1/billing.html"
    findings = oracle.inspect(
        before, Action("click", "btn_qty_down"),
        type("R", (), {"crashed": False, "ok": True, "js_errors": [],
                       "http_errors": [], "events": []})(),
        after, {"step_index": 8, "history_sigs": [], "ground_truth": {}})
    kinds = [f.kind for f in findings]
    assert "semantic" in kinds
    assert any((f.evidence or {}).get("assert_id") == "bill_qty_non_negative"
               for f in findings)


def test_qty_zero_is_not_h2():
    spec = load_spec("apps/buggy-flow/spec.json")
    oracle = OracleEngine(spec)
    before = flow_billing_state("1")
    after = flow_billing_state("0")
    after.url = "http://127.0.0.1/billing.html"
    before.url = "http://127.0.0.1/billing.html"
    findings = oracle.inspect(
        before, Action("click", "btn_qty_down"),
        type("R", (), {"crashed": False, "ok": True, "js_errors": [],
                       "http_errors": [], "events": []})(),
        after, {"step_index": 8, "history_sigs": [], "ground_truth": {}})
    assert not any((f.evidence or {}).get("assert_id") == "bill_qty_non_negative"
                   for f in findings)


def test_graph_descriptors_do_not_require_policy():
    nodes = [
        {"sig": "a", "url": "/index.html", "cluster_id": "i", "first_seen_step": 1},
        {"sig": "b", "url": "/cart.html", "cluster_id": "c", "first_seen_step": 2},
        {"sig": "c", "url": "/cart.html", "cluster_id": "c", "first_seen_step": 3},
    ]
    edges = [{"src": "a", "dst": "b"}, {"src": "b", "dst": "c"}]
    d = graph_descriptors(nodes, edges, [])
    assert d["n_states"] == 3
    assert d["n_urls"] == 2
    assert d["semantic_variant_churn"] == 1.5
    assert d["max_reached_depth"] == 2


def test_structural_policy_construction_unchanged():
    p = make_policy("ghost-structural-memory", 1)
    assert p.sequence_mode == "structural"
    assert p.use_frontier is False


def test_page_depths_shop_promo_is_shallow():
    d = page_depths(SOURCE_MODELED_SHOP_PAGES, "index.html")
    assert d["promo.html"] == 1
    assert d["help.html"] == 2
