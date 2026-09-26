"""A return yields to an untried branch only on its own parent hub."""
import os

from ghostqa.exploration.parent_hub_sibling_guard import (
    ParentHubSiblingGuardGhostPolicy,
    ParentHubSiblingSequenceController,
)
from ghostqa.exploration.policy import GhostPolicy
from ghostqa.exploration.untried_sibling_guard import UntriedSiblingSequenceController
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState, UIElement
from benchmark.algorithm_freeze import sha256_file
from benchmark.fresh_composite_analysis import product_default_changed
from benchmark.fresh_transfer_v0327_analysis import derive_v0327_outcome, passing_facts

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARENT = os.path.join(ROOT, "ghostqa", "exploration", "untried_sibling_guard.py")
EPISODE = os.path.join(ROOT, "ghostqa", "exploration", "episode_drain_epoch_guard.py")
SOURCE = os.path.join(ROOT, "ghostqa", "exploration", "parent_hub_sibling_guard.py")
PARENT_SHA = "0a425a46df8884bc8260bf2c9fa1ac3c85da6a7931b7dec2899a94b9daac35dd"
EPISODE_SHA = "9403e81f34625ff225f4cca69bf65c992d937305cb3a516a8be12a7bc9e08d45"
NEEDLES = (
    "buggy-desk", "buggy-ward", "buggy-pier", "nav_customers", "btn_watch",
    "BUG-K", "BUG-PR", "ticket.html",
)


def _el(eid, text):
    return UIElement(eid, "link", text, kind="click")


def _state():
    return GUIState(
        app="t", url="/hub", title="Hub",
        elements=(_el("a", "甲"), _el("b", "乙"), _el("c", "丙"), _el("up", "返回")),
        obs={},
    )


def _graph():
    graph = StateGraph()
    graph.add_state("H", "/hub", "Hub", cluster_id="hub")
    return graph


def _actions():
    return [Action("click", eid) for eid in ("a", "b", "c", "up")]


def _arm(ctrl, parent_cluster):
    ctrl.ledger.returning = True
    ctrl.ledger.active_branch = f"{parent_cluster}:click:old"
    ctrl.ledger.parent_hub_sig = "P"
    ctrl.ledger.parent_hub_cluster = parent_cluster
    ctrl._open_instance = {"id": "seq-0001", "branch": ctrl.ledger.active_branch, "len": 2}


def _ctx():
    return {"sig": "H", "step_index": 4}


def test_parent_hub_still_takes_the_untried_sibling():
    ctrl = ParentHubSiblingSequenceController("structural")
    _arm(ctrl, "hub")
    chosen = ctrl.pick_override(_actions(), _state(), _graph(), _ctx())
    assert chosen is not None and chosen.target_eid == "a"
    assert ctrl.metrics()["untried_sibling_before_return_selections"] == 1


def test_in_transit_return_is_not_interrupted():
    narrowed = ParentHubSiblingSequenceController("structural")
    wide = UntriedSiblingSequenceController("structural")
    _arm(narrowed, "elsewhere")
    _arm(wide, "elsewhere")
    graph = _graph()
    state = _state()
    ctx = _ctx()
    stayed = narrowed.pick_override(_actions(), state, graph, ctx)
    diverted = wide.pick_override(_actions(), state, graph, ctx)
    assert stayed is not None and stayed.target_eid == "up"
    assert diverted is not None and diverted.target_eid == "a"
    assert narrowed.metrics()["untried_sibling_before_return_selections"] == 0


def test_frozen_parents_and_product_default():
    assert sha256_file(PARENT) == PARENT_SHA
    assert sha256_file(EPISODE) == EPISODE_SHA
    text = open(SOURCE, encoding="utf-8").read()
    assert not any(needle in text for needle in NEEDLES)
    policy = ParentHubSiblingGuardGhostPolicy()
    assert policy.name == "ghost-structural-parent-hub-sibling-guard"
    assert policy.use_frontier is False
    assert policy.sequence_mode == "structural"
    default = GhostPolicy()
    assert default.use_frontier is False
    assert default.sequence_mode == "off"
    assert product_default_changed() is False


def test_desk_loss_is_outcome_c_and_clean_pass_is_a():
    facts = passing_facts()
    facts["historical_guard_loss"] = [{"app": "buggy-desk", "bugs": ["BUG-K3"]}]
    assert derive_v0327_outcome(**facts)["outcome"] == "C"
    assert derive_v0327_outcome(**passing_facts())["outcome"] == "A"
    assert derive_v0327_outcome(**passing_facts())["promotion_readiness"] == "not_ready"
