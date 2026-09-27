"""A repeated input on a non-hub page switches to another payload."""
import os

from ghostqa.exploration.alternate_payload_guard import (
    AlternatePayloadGuardGhostPolicy,
    AlternatePayloadSequenceController,
)
from ghostqa.exploration.policy import GhostPolicy
from ghostqa.exploration.repeat_click_guard import RepeatClickSequenceController
from ghostqa.exploration.sequence import MutationContext
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState, UIElement
from benchmark.algorithm_freeze import sha256_file
from benchmark.fresh_composite_analysis import product_default_changed

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARENT = os.path.join(ROOT, "ghostqa", "exploration", "repeat_click_guard.py")
PARENT_SHA = "e52e87a312120f838e6b9d922928f7666824d6f7fd32c4e73c3b5e538f41b501"


def _prefs():
    return GUIState(
        app="t", url="/prefs", title="Prefs",
        elements=(
            UIElement("topic_title", "input", "标题", kind="input"),
            UIElement("btn_submit", "button", "提交", kind="click"),
            UIElement("up", "link", "返回", kind="click"),
        ),
        obs={},
    )


def _hub():
    return GUIState(
        app="t", url="/hub", title="Hub",
        elements=(
            UIElement("a", "link", "甲", kind="click"),
            UIElement("b", "link", "乙", kind="click"),
            UIElement("c", "link", "丙", kind="click"),
            UIElement("topic_title", "input", "标题", kind="input"),
            UIElement("up", "link", "返回", kind="click"),
        ),
        obs={},
    )


def _arm(ctrl, remember=False):
    ctrl.ledger.commitment_left = 2
    ctrl.ledger.returning = False
    ctrl.ledger.active_branch = "hub:click:nav_prefs"
    if remember:
        ctrl._branch_inputs["hub:click:nav_prefs"] = {"input:topic_title:测试输入"}
    ctrl.mutations = [MutationContext(
        step=1, source_sig="P", action_key="input:topic_title:测试输入",
        new_eids=("topic_title",), changed_obs_keys=(),
        branch_id="hub:click:nav_prefs", visible_facts={}, ttl=2,
    )]


def _actions():
    return [
        Action("input", "topic_title", "测试输入"),
        Action("input", "topic_title", ""),
        Action("click", "btn_submit"),
        Action("click", "up"),
    ]


def test_repeated_input_switches_payload_on_a_non_hub():
    ctrl = AlternatePayloadSequenceController("structural")
    parent = RepeatClickSequenceController("structural")
    graph = StateGraph()
    graph.add_state("P", "/prefs", "Prefs", cluster_id="prefs")
    graph.nodes["P"].tried_actions.add("input:topic_title:测试输入")
    _arm(ctrl, remember=True)
    _arm(parent)
    chosen = ctrl.pick_override(_actions(), _prefs(), graph, {"sig": "P"})
    other = parent.pick_override(_actions(), _prefs(), graph, {"sig": "P"})
    assert chosen is not None and chosen.type == "input" and chosen.text == ""
    assert other is not None and other.target_eid == "btn_submit"
    assert ctrl.metrics()["alternate_payload_selections"] == 1


def test_hub_page_does_not_switch_or_steal_a_click():
    ctrl = AlternatePayloadSequenceController("structural")
    graph = StateGraph()
    graph.add_state("H", "/hub", "Hub", cluster_id="hub")
    graph.nodes["H"].tried_actions.add("input:topic_title:测试输入")
    _arm(ctrl, remember=True)
    chosen = ctrl.pick_override(_actions(), _hub(), graph, {"sig": "H"})
    assert chosen is None or chosen.text != ""
    assert ctrl.metrics()["alternate_payload_selections"] == 0


def test_frozen_parent_and_product_default():
    assert sha256_file(PARENT) == PARENT_SHA
    text = open(os.path.join(ROOT, "ghostqa", "exploration", "alternate_payload_guard.py"), encoding="utf-8").read()
    assert "buggy-creek" not in text and "btn_submit" not in text
    policy = AlternatePayloadGuardGhostPolicy()
    assert policy.name == "ghost-structural-alternate-payload-guard"
    assert isinstance(policy.sequence, AlternatePayloadSequenceController)
    assert GhostPolicy().sequence_mode == "off"
    assert product_default_changed() is False
