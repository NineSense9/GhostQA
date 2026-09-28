"""A hub takes one distractor link after its branch clicks are started."""
import os

from ghostqa.exploration.hub_distractor_guard import (
    HubDistractorGuardGhostPolicy,
    HubDistractorSequenceController,
)
from ghostqa.exploration.policy import GhostPolicy
from ghostqa.exploration.search_submit_guard import SearchSubmitSequenceController
from ghostqa.exploration.sequence import branch_key
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState, UIElement
from benchmark.algorithm_freeze import sha256_file
from benchmark.fresh_composite_analysis import product_default_changed

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARENT = os.path.join(ROOT, "ghostqa", "exploration", "search_submit_guard.py")
PARENT_SHA = "04fd1fdc67f545c80c9744ad7d3ce6607cdfdba892f413b900d5bee912269112"


def _home():
    return GUIState(
        app="t", url="/", title="Home",
        elements=(
            UIElement("nav_roster", "link", "名册", kind="click"),
            UIElement("nav_board", "link", "看板", kind="click"),
            UIElement("nav_blank", "link", "空白", kind="click"),
            UIElement("open_aid", "link", "帮助", kind="click"),
            UIElement("up", "link", "返回", kind="click"),
        ),
        obs={},
    )


def _actions():
    return [
        Action("click", "nav_roster"),
        Action("click", "nav_board"),
        Action("click", "nav_blank"),
        Action("click", "open_aid"),
        Action("click", "up"),
    ]


def _graph():
    graph = StateGraph()
    graph.add_state("H", "/", "Home", cluster_id="home")
    return graph


def _start_branches(ctrl):
    rec = ctrl.ledger.hub("H", "home")
    for eid in ("nav_roster", "nav_board", "nav_blank"):
        rec.started.add(branch_key("home", Action("click", eid)))


def test_untried_branch_is_not_replaced_by_the_distractor():
    ctrl = HubDistractorSequenceController("structural")
    parent = SearchSubmitSequenceController("structural")
    graph = _graph()
    chosen = ctrl.pick_override(_actions(), _home(), graph, {"sig": "H"})
    other = parent.pick_override(_actions(), _home(), graph, {"sig": "H"})
    assert chosen is not None and chosen.target_eid == "nav_roster"
    assert other is not None and other.target_eid == "nav_roster"
    assert ctrl.metrics()["hub_distractor_selections"] == 0


def test_started_hub_takes_the_distractor_once():
    ctrl = HubDistractorSequenceController("structural")
    _start_branches(ctrl)
    graph = _graph()
    first = ctrl.pick_override(_actions(), _home(), graph, {"sig": "H"})
    second = ctrl.pick_override(_actions(), _home(), graph, {"sig": "H"})
    assert first is not None and first.target_eid == "open_aid"
    assert second is not None and second.target_eid != "open_aid"
    assert ctrl.metrics()["hub_distractor_selections"] == 1


def test_frozen_parent_and_product_default():
    assert sha256_file(PARENT) == PARENT_SHA
    text = open(
        os.path.join(ROOT, "ghostqa", "exploration", "hub_distractor_guard.py"),
        encoding="utf-8").read()
    assert "buggy-quarry" not in text and "open_aid" not in text
    policy = HubDistractorGuardGhostPolicy()
    assert policy.name == "ghost-structural-hub-distractor-guard"
    assert isinstance(policy.sequence, HubDistractorSequenceController)
    assert GhostPolicy().sequence_mode == "off"
    assert GhostPolicy().use_frontier is False
    assert product_default_changed() is False
