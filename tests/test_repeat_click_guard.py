"""A repeated followup yields to an untried click."""
import os

from ghostqa.exploration.parent_hub_sibling_guard import ParentHubSiblingSequenceController
from ghostqa.exploration.policy import GhostPolicy
from ghostqa.exploration.repeat_click_guard import (
    RepeatClickGuardGhostPolicy,
    RepeatClickSequenceController,
)
from ghostqa.exploration.sequence import MutationContext
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState, UIElement
from benchmark.algorithm_freeze import sha256_file
from benchmark.fresh_composite_analysis import product_default_changed

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARENT = os.path.join(ROOT, "ghostqa", "exploration", "parent_hub_sibling_guard.py")
SOURCE = os.path.join(ROOT, "ghostqa", "exploration", "repeat_click_guard.py")
PARENT_SHA = "33a479db2f062071438bb05c4b8dcc90a7a85bdcec4b97e54ebf06d2ebf7183b"


def _state():
    return GUIState(
        app="t", url="/prefs", title="Prefs",
        elements=(
            UIElement("topic_title", "input", "标题", kind="input"),
            UIElement("btn_submit", "button", "提交", kind="click"),
            UIElement("up", "link", "返回", kind="click"),
        ),
        obs={},
    )


def _arm(ctrl):
    ctrl.ledger.commitment_left = 2
    ctrl.ledger.returning = False
    ctrl.ledger.active_branch = "hub:click:nav_prefs"
    ctrl.mutations = [MutationContext(
        step=1, source_sig="P", action_key="input:topic_title:测试输入",
        new_eids=("topic_title", "btn_submit"), changed_obs_keys=(),
        branch_id="hub:click:nav_prefs", visible_facts={}, ttl=2,
    )]


def test_repeated_followup_yields_to_the_untried_click():
    ctrl = RepeatClickSequenceController("structural")
    parent = ParentHubSiblingSequenceController("structural")
    graph = StateGraph()
    graph.add_state("P", "/prefs", "Prefs", cluster_id="prefs")
    graph.nodes["P"].tried_actions.add("input:topic_title:测试输入")
    _arm(ctrl)
    _arm(parent)
    actions = [
        Action("input", "topic_title", "测试输入"),
        Action("click", "btn_submit"),
        Action("click", "up"),
    ]
    ctx = {"sig": "P", "step_index": 4}
    chosen = ctrl.pick_override(actions, _state(), graph, ctx)
    other = parent.pick_override(actions, _state(), graph, ctx)
    assert chosen is not None and chosen.target_eid == "btn_submit"
    assert other is not None and other.target_eid == "topic_title"
    assert ctrl.metrics()["untried_click_before_repeat_selections"] == 1


def test_first_followup_is_not_replaced():
    ctrl = RepeatClickSequenceController("structural")
    graph = StateGraph()
    graph.add_state("P", "/prefs", "Prefs", cluster_id="prefs")
    _arm(ctrl)
    actions = [
        Action("input", "topic_title", "测试输入"),
        Action("click", "btn_submit"),
    ]
    chosen = ctrl.pick_override(actions, _state(), graph, {"sig": "P"})
    assert chosen is None or chosen.target_eid != "btn_submit"
    assert ctrl.metrics()["untried_click_before_repeat_selections"] == 0


def test_parent_module_and_default_stay_put():
    assert sha256_file(PARENT) == PARENT_SHA
    text = open(SOURCE, encoding="utf-8").read()
    assert "buggy-campus" not in text and "btn_probe" not in text
    policy = RepeatClickGuardGhostPolicy()
    assert policy.name == "ghost-structural-repeat-click-guard"
    assert policy.sequence_mode == "structural"
    assert GhostPolicy().sequence_mode == "off"
    assert product_default_changed() is False
