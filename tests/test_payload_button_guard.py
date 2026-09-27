"""An alternate payload on a non-hub page is followed by one untried button."""
import os

from ghostqa.exploration.alternate_payload_guard import AlternatePayloadSequenceController
from ghostqa.exploration.payload_button_guard import (
    PayloadButtonGuardGhostPolicy,
    PayloadButtonSequenceController,
)
from ghostqa.exploration.policy import GhostPolicy
from ghostqa.exploration.sequence import MutationContext
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState, UIElement
from benchmark.algorithm_freeze import sha256_file
from benchmark.fresh_composite_analysis import product_default_changed

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARENT = os.path.join(ROOT, "ghostqa", "exploration", "alternate_payload_guard.py")
PARENT_SHA = "fef17c7441df69e68f083ec04e201e2a942b0be6cacf59a054e135d09b49d018"


def _prefs():
    return GUIState(
        app="t", url="/prefs", title="Prefs",
        elements=(
            UIElement("topic_title", "input", "标题", kind="input"),
            UIElement("open_side", "link", "旁边", kind="click"),
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
            UIElement("btn_go", "button", "前往", kind="click"),
            UIElement("up", "link", "返回", kind="click"),
        ),
        obs={},
    )


def _arm(ctrl):
    ctrl.ledger.commitment_left = 2
    ctrl.ledger.returning = False
    ctrl.ledger.active_branch = "hub:click:nav_prefs"
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
        Action("click", "open_side"),
        Action("click", "btn_submit"),
        Action("click", "up"),
    ]


def _graph(sig="P"):
    graph = StateGraph()
    graph.add_state(sig, "/prefs", "Prefs", cluster_id="prefs")
    graph.nodes[sig].tried_actions.add("input:topic_title:测试输入")
    return graph


def test_alternate_payload_then_untried_button_before_return():
    ctrl = PayloadButtonSequenceController("structural")
    graph = _graph()
    _arm(ctrl)
    first = ctrl.pick_override(_actions(), _prefs(), graph, {"sig": "P"})
    assert first is not None and first.type == "input" and first.text == ""
    assert ctrl._button_due is True
    ctrl.ledger.returning = True
    ctrl.ledger.commitment_left = 0
    second = ctrl.pick_override(_actions(), _prefs(), graph, {"sig": "P"})
    assert second is not None and second.type == "click" and second.target_eid == "btn_submit"
    assert ctrl.metrics()["payload_button_selections"] == 1
    assert ctrl.metrics()["alternate_payload_selections"] == 1
    third = ctrl.pick_override(_actions(), _prefs(), graph, {"sig": "P"})
    assert third is not None and third.target_eid == "up"


def test_hub_drops_the_button_and_does_not_steal_a_click():
    ctrl = PayloadButtonSequenceController("structural")
    graph = _graph()
    _arm(ctrl)
    first = ctrl.pick_override(_actions(), _prefs(), graph, {"sig": "P"})
    assert first is not None and first.text == ""
    ctrl.ledger.returning = True
    ctrl.ledger.commitment_left = 0
    ctrl.ledger.parent_hub_cluster = "chart"
    hub = StateGraph()
    hub.add_state("H", "/hub", "Hub", cluster_id="hub")
    chosen = ctrl.pick_override(
        [Action("click", "btn_go"), Action("click", "a"), Action("click", "up")],
        _hub(), hub, {"sig": "H"})
    assert chosen is not None and chosen.target_eid == "up"
    assert ctrl.metrics()["payload_button_selections"] == 0
    assert ctrl._button_due is False


def test_return_without_payload_does_not_take_a_button():
    ctrl = PayloadButtonSequenceController("structural")
    parent = AlternatePayloadSequenceController("structural")
    graph = _graph()
    ctrl.ledger.returning = True
    ctrl.ledger.active_branch = "hub:click:nav_prefs"
    parent.ledger.returning = True
    parent.ledger.active_branch = "hub:click:nav_prefs"
    chosen = ctrl.pick_override(_actions(), _prefs(), graph, {"sig": "P"})
    other = parent.pick_override(_actions(), _prefs(), graph, {"sig": "P"})
    assert chosen is not None and chosen.target_eid == "up"
    assert other is not None and other.target_eid == "up"
    assert ctrl.metrics()["payload_button_selections"] == 0


def test_tried_button_is_skipped():
    ctrl = PayloadButtonSequenceController("structural")
    graph = _graph()
    graph.nodes["P"].tried_actions.add("click:btn_submit:")
    _arm(ctrl)
    ctrl.pick_override(_actions(), _prefs(), graph, {"sig": "P"})
    ctrl.ledger.returning = True
    ctrl.ledger.commitment_left = 0
    chosen = ctrl.pick_override(_actions(), _prefs(), graph, {"sig": "P"})
    assert chosen is not None and chosen.target_eid == "up"
    assert ctrl.metrics()["payload_button_selections"] == 0


def test_frozen_parent_and_product_default():
    assert sha256_file(PARENT) == PARENT_SHA
    text = open(
        os.path.join(ROOT, "ghostqa", "exploration", "payload_button_guard.py"),
        encoding="utf-8").read()
    assert "buggy-dune" not in text and "btn_submit" not in text
    policy = PayloadButtonGuardGhostPolicy()
    assert policy.name == "ghost-structural-payload-button-guard"
    assert isinstance(policy.sequence, PayloadButtonSequenceController)
    assert GhostPolicy().sequence_mode == "off"
    assert GhostPolicy().use_frontier is False
    assert product_default_changed() is False
