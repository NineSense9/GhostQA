"""A button id already taken on this branch is not clicked again."""
import os

from ghostqa.exploration.page_buttons_guard import PageButtonsSequenceController
from ghostqa.exploration.policy import GhostPolicy
from ghostqa.exploration.seen_button_guard import (
    SeenButtonGuardGhostPolicy,
    SeenButtonSequenceController,
)
from ghostqa.exploration.sequence import MutationContext
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState, UIElement
from benchmark.algorithm_freeze import sha256_file
from benchmark.fresh_composite_analysis import product_default_changed

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARENT = os.path.join(ROOT, "ghostqa", "exploration", "page_buttons_guard.py")
PARENT_SHA = "0d933edc834928a70c46af07a24091379e5b1ec3cdd81e18e1a4845d92464d81"


def _prefs():
    return GUIState(
        app="t", url="/prefs", title="Prefs",
        elements=(
            UIElement("topic_title", "input", "标题", kind="input"),
            UIElement("btn_submit", "button", "提交", kind="click"),
            UIElement("btn_probe", "button", "提交同步", kind="click"),
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


def _fresh(sig):
    graph = StateGraph()
    graph.add_state(sig, "/prefs", "Prefs", cluster_id="prefs")
    return graph


def test_repeated_button_id_stops_even_on_a_new_signature():
    ctrl = SeenButtonSequenceController("structural")
    parent = PageButtonsSequenceController("structural")
    graph = _fresh("P")
    _arm(ctrl)
    _arm(parent)
    state = _prefs()
    actions = _actions()
    assert ctrl.pick_override(actions, state, graph, {"sig": "P"}).text == ""
    ctrl.ledger.returning = True
    ctrl.ledger.commitment_left = 0
    parent.pick_override(actions, state, _fresh("P"), {"sig": "P"})
    parent.ledger.returning = True
    parent.ledger.commitment_left = 0
    first = ctrl.pick_override(actions, state, graph, {"sig": "P"})
    assert first is not None and first.target_eid == "btn_submit"
    nxt = _fresh("Q")
    second = ctrl.pick_override(actions, state, nxt, {"sig": "Q"})
    assert second is not None and second.target_eid == "btn_probe"
    third = ctrl.pick_override(actions, state, _fresh("R"), {"sig": "R"})
    assert third is not None and third.target_eid == "up"
    assert ctrl.metrics()["seen_button_stops"] == 1
    parent_graph = _fresh("S")
    parent_first = parent.pick_override(actions, state, parent_graph, {"sig": "S"})
    parent_second = parent.pick_override(actions, state, _fresh("T"), {"sig": "T"})
    assert parent_first.target_eid == "btn_submit"
    assert parent_second.target_eid == "btn_submit"


def test_same_button_is_not_repeated_when_it_is_the_only_choice():
    ctrl = SeenButtonSequenceController("structural")
    graph = _fresh("P")
    _arm(ctrl)
    state = _prefs()
    only = [
        Action("input", "topic_title", "测试输入"),
        Action("input", "topic_title", ""),
        Action("click", "btn_submit"),
        Action("click", "up"),
    ]
    ctrl.pick_override(only, state, graph, {"sig": "P"})
    ctrl.ledger.returning = True
    ctrl.ledger.commitment_left = 0
    first = ctrl.pick_override(only, state, graph, {"sig": "P"})
    second = ctrl.pick_override(only, state, _fresh("Q"), {"sig": "Q"})
    assert first.target_eid == "btn_submit"
    assert second.target_eid == "up"
    assert ctrl.metrics()["seen_button_stops"] == 1


def test_frozen_parent_and_product_default():
    assert sha256_file(PARENT) == PARENT_SHA
    text = open(
        os.path.join(ROOT, "ghostqa", "exploration", "seen_button_guard.py"),
        encoding="utf-8").read()
    assert "buggy-wiki" not in text and "btn_preview" not in text
    policy = SeenButtonGuardGhostPolicy()
    assert policy.name == "ghost-structural-seen-button-guard"
    assert isinstance(policy.sequence, SeenButtonSequenceController)
    assert GhostPolicy().sequence_mode == "off"
    assert GhostPolicy().use_frontier is False
    assert product_default_changed() is False
