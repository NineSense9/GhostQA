"""Return yields to an unstarted hub branch before leaving."""
import os

from ghostqa.exploration.episode_drain_epoch_guard import (
    EpisodeDrainEpochSequenceController,
)
from ghostqa.exploration.policy import GhostPolicy
from ghostqa.exploration.sequence import NEW, branch_key
from ghostqa.exploration.sequence_memory import BranchHistory
from ghostqa.exploration.untried_sibling_guard import (
    UntriedSiblingGuardGhostPolicy,
    UntriedSiblingSequenceController,
)
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState, UIElement
from benchmark.algorithm_freeze import sha256_file
from benchmark.fresh_composite_analysis import product_default_changed

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARENT = os.path.join(ROOT, "ghostqa", "exploration", "episode_drain_epoch_guard.py")
SOURCE = os.path.join(ROOT, "ghostqa", "exploration", "untried_sibling_guard.py")
PARENT_SHA = "9403e81f34625ff225f4cca69bf65c992d937305cb3a516a8be12a7bc9e08d45"
NEEDLES = (
    "buggy-clinic", "buggy-dispatch", "buggy-archive", "buggy-fleet",
    "buggy-ward", "buggy-harbor", "buggy-gallery", "buggy-signal",
    "open_finding", "finding.html", "BUG-CL", "BUG-WD",
)


def _el(eid, text):
    return UIElement(eid, "link", text, kind="click")


def _hub_state():
    return GUIState(
        app="t", url="/hub", title="Hub",
        elements=(
            _el("a", "甲"), _el("b", "乙"), _el("c", "丙"), _el("up", "返回"),
        ),
        obs={},
    )


def _graph():
    graph = StateGraph()
    graph.add_state("H", "/hub", "Hub", cluster_id="hub")
    graph.add_state("C", "/child", "Child", cluster_id="child")
    return graph


def _actions():
    return [Action("click", eid) for eid in ("a", "b", "c", "up")]


def _arm(ctrl):
    ctrl.ledger.returning = True
    ctrl.ledger.active_branch = "hub:click:old"
    ctrl.ledger.parent_hub_sig = "H"
    ctrl.ledger.parent_hub_cluster = "hub"
    ctrl._open_instance = {"id": "seq-0001", "branch": "hub:click:old", "len": 2}


def _ctx():
    return {"sig": "H", "step_index": 4}


def test_returning_hub_takes_untried_sibling_before_return():
    ctrl = UntriedSiblingSequenceController("structural")
    parent = EpisodeDrainEpochSequenceController("structural")
    _arm(ctrl)
    _arm(parent)
    chosen = ctrl.pick_override(_actions(), _hub_state(), _graph(), _ctx())
    other = parent.pick_override(_actions(), _hub_state(), _graph(), _ctx())
    assert chosen is not None and chosen.target_eid == "a"
    assert other is not None and other.target_eid == "up"
    assert ctrl.last_label == "untried_sibling_before_return"
    assert ctrl.metrics()["untried_sibling_before_return_selections"] == 1


def test_started_sibling_is_skipped():
    ctrl = UntriedSiblingSequenceController("structural")
    _arm(ctrl)
    key = branch_key("hub", Action("click", "a"))
    ctrl.struct.hub("hub").branches[key] = BranchHistory(branch_key=key, attempts=1)
    chosen = ctrl.pick_override(_actions(), _hub_state(), _graph(), _ctx())
    assert chosen is not None and chosen.target_eid == "b"


def test_no_untried_sibling_keeps_the_return():
    ctrl = UntriedSiblingSequenceController("structural")
    _arm(ctrl)
    for eid in ("a", "b", "c"):
        key = branch_key("hub", Action("click", eid))
        ctrl.struct.hub("hub").branches[key] = BranchHistory(branch_key=key, attempts=1)
    chosen = ctrl.pick_override(_actions(), _hub_state(), _graph(), _ctx())
    assert chosen is not None and chosen.target_eid == "up"
    assert ctrl._sibling_pending is None


def test_sibling_click_suspends_the_return_and_starts_a_child():
    ctrl = UntriedSiblingSequenceController("structural")
    graph = _graph()
    state = _hub_state()
    _arm(ctrl)
    chosen = ctrl.pick_override(_actions(), state, graph, _ctx())
    child = GUIState(
        app="t", url="/child", title="Child",
        elements=(_el("z", "丁"), _el("q", "戊"), _el("back", "返回")),
        obs={},
    )
    ctrl.after("H", chosen, state, child, NEW, [], "C", False, graph, 4)
    assert ctrl._sibling_pending is None
    assert len(ctrl._stack) == 1
    frame = ctrl._stack[0]
    assert frame.active_branch == "hub:click:old"
    assert frame.returning is True
    assert frame.deferred_horizon is False
    assert frame.child_parent_cluster == "hub"
    assert ctrl.ledger.active_branch == "hub:click:a"
    assert ctrl.ledger.returning is False
    assert ctrl._open_instance is not None
    assert ctrl.metrics()["untried_sibling_return_suspensions"] == 1
    assert not any(
        event.get("event") == "horizon_handoff_started" for event in ctrl.events)


def test_parent_module_and_product_default_stay_put():
    assert sha256_file(PARENT) == PARENT_SHA
    text = open(SOURCE, encoding="utf-8").read()
    assert not any(needle in text for needle in NEEDLES)
    policy = UntriedSiblingGuardGhostPolicy()
    assert policy.name == "ghost-structural-untried-sibling-guard"
    assert policy.use_frontier is False
    assert policy.sequence_mode == "structural"
    default = GhostPolicy()
    assert default.use_frontier is False
    assert default.sequence_mode == "off"
    assert product_default_changed() is False
