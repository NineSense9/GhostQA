"""After four side steps, browser back is taken instead of the pair return."""
import os

from ghostqa.exploration.loop_exit_guard import LoopExitSequenceController
from ghostqa.exploration.policy import GhostPolicy
from ghostqa.exploration.side_back_guard import (
    SideBackGuardGhostPolicy,
    SideBackSequenceController,
)
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState, UIElement
from benchmark.algorithm_freeze import sha256_file
from benchmark.fresh_composite_analysis import product_default_changed

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARENT = os.path.join(ROOT, "ghostqa", "exploration", "loop_exit_guard.py")
PARENT_SHA = "cc763197a9cc4531b5e93c567535e2dfc195a3fcafb54dabf44a36d105e95e6a"


def _page(url):
    return GUIState(
        app="t", url=url, title="T",
        elements=(
            UIElement("open_loop", "link", "另一页", kind="click"),
            UIElement("up", "link", "返回", kind="click"),
        ),
        obs={},
    )


def _actions():
    return [Action("click", "open_loop"), Action("click", "up"), Action("back")]


def test_browser_back_beats_the_in_page_return_and_stops_outside():
    ctrl = SideBackSequenceController("structural")
    parent = LoopExitSequenceController("structural")
    graph = StateGraph()
    graph.add_state("S", "/settings", "S", cluster_id="settings")
    ctrl._side = True
    ctrl._side_steps = 4
    ctrl._side_urls = {"/help", "/settings"}
    parent._side = True
    parent._side_steps = 4
    chosen = ctrl.pick_override(_actions(), _page("/settings"), graph, {"sig": "S"})
    other = parent.pick_override(_actions(), _page("/settings"), graph, {"sig": "S"})
    assert chosen is not None and chosen.type == "back"
    assert other is not None and other.target_eid == "up"
    assert ctrl.metrics()["side_back_selections"] == 1
    outside = ctrl.pick_override(_actions(), _page("/index"), graph, {"sig": "H"})
    assert outside is None or getattr(outside, "type", "") != "back"
    assert ctrl._side is False


def test_frozen_parent_and_product_default():
    assert sha256_file(PARENT) == PARENT_SHA
    text = open(
        os.path.join(ROOT, "ghostqa", "exploration", "side_back_guard.py"),
        encoding="utf-8").read()
    assert "buggy-fjord" not in text and "help.html" not in text
    policy = SideBackGuardGhostPolicy()
    assert policy.name == "ghost-structural-side-back-guard"
    assert isinstance(policy.sequence, SideBackSequenceController)
    assert GhostPolicy().sequence_mode == "off"
    assert GhostPolicy().use_frontier is False
    assert product_default_changed() is False
