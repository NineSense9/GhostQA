"""A distractor side path returns after four steps."""
import os

from ghostqa.exploration.hub_distractor_guard import HubDistractorSequenceController
from ghostqa.exploration.loop_exit_guard import (
    LoopExitGuardGhostPolicy,
    LoopExitSequenceController,
)
from ghostqa.exploration.policy import GhostPolicy
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState, UIElement
from benchmark.algorithm_freeze import sha256_file
from benchmark.fresh_composite_analysis import product_default_changed

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARENT = os.path.join(ROOT, "ghostqa", "exploration", "hub_distractor_guard.py")
PARENT_SHA = "30a93da8ff3644db9a753bb85a2629d1d350d75739ff78cba6fff64f80cda558"


def _page():
    return GUIState(
        app="t", url="/help", title="Help",
        elements=(
            UIElement("open_loop", "link", "偏好页", kind="click"),
            UIElement("up", "link", "返回", kind="click"),
        ),
        obs={},
    )


def _actions():
    return [Action("click", "open_loop"), Action("click", "up")]


def test_four_side_steps_then_return():
    ctrl = LoopExitSequenceController("structural")
    parent = HubDistractorSequenceController("structural")
    graph = StateGraph()
    graph.add_state("S", "/help", "Help", cluster_id="help")
    ctrl._side = True
    ctrl._side_steps = 3
    early = ctrl.pick_override(_actions(), _page(), graph, {"sig": "S"})
    assert early is None or early.target_eid != "up"
    assert ctrl.metrics()["loop_exit_selections"] == 0
    ctrl._side_steps = 4
    leaving = ctrl.pick_override(_actions(), _page(), graph, {"sig": "S"})
    other = parent.pick_override(_actions(), _page(), graph, {"sig": "S"})
    assert leaving is not None and leaving.target_eid == "up"
    assert other is None or other.target_eid != "up"
    assert ctrl.metrics()["loop_exit_selections"] == 1
    assert ctrl._side is False


def test_frozen_parent_and_product_default():
    assert sha256_file(PARENT) == PARENT_SHA
    text = open(
        os.path.join(ROOT, "ghostqa", "exploration", "loop_exit_guard.py"),
        encoding="utf-8").read()
    assert "buggy-wicket" not in text and "btn_reopen" not in text
    policy = LoopExitGuardGhostPolicy()
    assert policy.name == "ghost-structural-loop-exit-guard"
    assert isinstance(policy.sequence, LoopExitSequenceController)
    assert GhostPolicy().sequence_mode == "off"
    assert GhostPolicy().use_frontier is False
    assert product_default_changed() is False
