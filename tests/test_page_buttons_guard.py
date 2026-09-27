"""Remaining untried buttons are taken before the return."""
import os

from ghostqa.exploration.page_buttons_guard import (
    PageButtonsGuardGhostPolicy,
    PageButtonsSequenceController,
)
from ghostqa.exploration.payload_button_guard import PayloadButtonSequenceController
from ghostqa.exploration.policy import GhostPolicy
from ghostqa.exploration.sequence import MutationContext
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState, UIElement
from benchmark.algorithm_freeze import sha256_file
from benchmark.fresh_composite_analysis import product_default_changed

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARENT = os.path.join(ROOT, "ghostqa", "exploration", "payload_button_guard.py")
PARENT_SHA = "9f65597aa16971d8afae1a83c6e666fea800745df88dca67a3b50764530ffc52"


def _prefs():
    return GUIState(
        app="t", url="/prefs", title="Prefs",
        elements=(
            UIElement("topic_title", "input", "标题", kind="input"),
            UIElement("btn_submit", "button", "提交", kind="click"),
            UIElement("btn_probe", "button", "提交同步", kind="click"),
            UIElement("btn_export", "button", "提交导出", kind="click"),
            UIElement("up", "link", "返回", kind="click"),
        ),
        obs={},
    )


def _actions():
    return [
        Action("input", "topic_title", "测试输入"),
        Action("input", "topic_title", ""),
        Action("click", "btn_submit"),
        Action("click", "btn_probe"),
        Action("click", "btn_export"),
        Action("click", "up"),
    ]


def _arm(ctrl):
    ctrl.ledger.commitment_left = 1
    ctrl.ledger.returning = False
    ctrl.ledger.active_branch = "hub:click:nav_prefs"
    ctrl._branch_inputs["hub:click:nav_prefs"] = {"input:topic_title:测试输入"}
    ctrl.mutations = [MutationContext(
        step=1, source_sig="P", action_key="input:topic_title:测试输入",
        new_eids=("topic_title",), changed_obs_keys=(),
        branch_id="hub:click:nav_prefs", visible_facts={}, ttl=2,
    )]


def _graph():
    graph = StateGraph()
    graph.add_state("P", "/prefs", "Prefs", cluster_id="prefs")
    graph.nodes["P"].tried_actions.add("input:topic_title:测试输入")
    return graph


def test_each_untried_button_is_taken_before_return():
    ctrl = PageButtonsSequenceController("structural")
    graph = _graph()
    _arm(ctrl)
    state = _prefs()
    actions = _actions()
    first = ctrl.pick_override(actions, state, graph, {"sig": "P"})
    assert first is not None and first.text == ""
    ctrl.ledger.returning = True
    ctrl.ledger.commitment_left = 0
    seen = []
    for _ in range(4):
        chosen = ctrl.pick_override(actions, state, graph, {"sig": "P"})
        assert chosen is not None
        seen.append(chosen.target_eid)
        if chosen.type == "click" and chosen.target_eid != "up":
            graph.nodes["P"].tried_actions.add(chosen.key())
    assert seen == ["btn_submit", "btn_probe", "btn_export", "up"]
    assert ctrl.metrics()["page_button_selections"] == 3
    parent = PayloadButtonSequenceController("structural")
    parent_graph = _graph()
    _arm(parent)
    parent.pick_override(actions, state, parent_graph, {"sig": "P"})
    parent.ledger.returning = True
    parent.ledger.commitment_left = 0
    parent_first = parent.pick_override(actions, state, parent_graph, {"sig": "P"})
    parent_second = parent.pick_override(actions, state, parent_graph, {"sig": "P"})
    assert parent_first is not None and parent_first.target_eid == "btn_submit"
    assert parent_second is not None and parent_second.target_eid == "up"


def test_frozen_parent_and_product_default():
    assert sha256_file(PARENT) == PARENT_SHA
    text = open(
        os.path.join(ROOT, "ghostqa", "exploration", "page_buttons_guard.py"),
        encoding="utf-8").read()
    assert "buggy-fen" not in text and "btn_submit" not in text
    policy = PageButtonsGuardGhostPolicy()
    assert policy.name == "ghost-structural-page-buttons-guard"
    assert isinstance(policy.sequence, PageButtonsSequenceController)
    assert GhostPolicy().sequence_mode == "off"
    assert GhostPolicy().use_frontier is False
    assert product_default_changed() is False
