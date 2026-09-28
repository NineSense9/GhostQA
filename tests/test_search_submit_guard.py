"""A long search input is followed by one button on that signature."""
import os

from ghostqa.exploration.policy import GhostPolicy
from ghostqa.exploration.search_submit_guard import (
    SearchSubmitGuardGhostPolicy,
    SearchSubmitSequenceController,
)
from ghostqa.exploration.seen_button_guard import SeenButtonSequenceController
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState, UIElement
from ghostqa.state.similarity import NEW
from benchmark.algorithm_freeze import sha256_file
from benchmark.fresh_composite_analysis import product_default_changed

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARENT = os.path.join(ROOT, "ghostqa", "exploration", "seen_button_guard.py")
PARENT_SHA = "6db20305153d89712c3ef0e9998c254a31cd96c6da338a5242e88cb649ed3449"
LONG = "x" * 25


def _home():
    return GUIState(
        app="t", url="/", title="Home",
        elements=(
            UIElement("nav_roster", "link", "名册", kind="click"),
            UIElement("nav_board", "link", "看板", kind="click"),
            UIElement("nav_blank", "link", "空白", kind="click"),
            UIElement("search_box", "input", "检索词", kind="input"),
            UIElement("query_go", "button", "提交查询", kind="click"),
        ),
        obs={},
    )


def _graph(sig="H2"):
    graph = StateGraph()
    graph.add_state("H1", "/", "Home", cluster_id="home")
    graph.add_state(sig, "/", "Home", cluster_id="home2")
    return graph


def _actions():
    return [
        Action("click", "nav_roster"),
        Action("click", "nav_board"),
        Action("click", "nav_blank"),
        Action("input", "search_box", "测试输入"),
        Action("input", "search_box", LONG),
        Action("click", "query_go"),
    ]


def _after(ctrl, text, new_sig="H2"):
    state = _home()
    ctrl.after(
        "H1", Action("input", "search_box", text), state, state,
        NEW, [], new_sig, False, _graph(new_sig), 1)


def test_long_search_takes_the_button_before_a_hub_link():
    ctrl = SearchSubmitSequenceController("structural")
    parent = SeenButtonSequenceController("structural")
    _after(ctrl, LONG)
    graph = _graph()
    chosen = ctrl.pick_override(_actions(), _home(), graph, {"sig": "H2"})
    other = parent.pick_override(_actions(), _home(), graph, {"sig": "H2"})
    assert chosen is not None and chosen.target_eid == "query_go"
    assert other is not None and other.target_eid == "nav_roster"
    assert ctrl.metrics()["search_submit_selections"] == 1
    again = ctrl.pick_override(_actions(), _home(), graph, {"sig": "H2"})
    assert again is not None and again.target_eid == "nav_roster"


def test_normal_search_and_other_signatures_do_not_arm():
    ctrl = SearchSubmitSequenceController("structural")
    _after(ctrl, "测试输入")
    graph = _graph()
    chosen = ctrl.pick_override(_actions(), _home(), graph, {"sig": "H2"})
    assert chosen is not None and chosen.target_eid == "nav_roster"
    _after(ctrl, LONG, "H2")
    left = ctrl.pick_override(_actions(), _home(), graph, {"sig": "OTHER"})
    assert left is not None and left.target_eid == "nav_roster"
    assert ctrl.metrics()["search_submit_selections"] == 0


def test_frozen_parent_and_product_default():
    assert sha256_file(PARENT) == PARENT_SHA
    text = open(
        os.path.join(ROOT, "ghostqa", "exploration", "search_submit_guard.py"),
        encoding="utf-8").read()
    assert "buggy-brook" not in text and "query_go" not in text
    policy = SearchSubmitGuardGhostPolicy()
    assert policy.name == "ghost-structural-search-submit-guard"
    assert isinstance(policy.sequence, SearchSubmitSequenceController)
    assert GhostPolicy().sequence_mode == "off"
    assert GhostPolicy().use_frontier is False
    assert product_default_changed() is False
