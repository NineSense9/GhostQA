"""v0.3.9 return-cycle guard. Isolated from frozen C1."""
import inspect
import json
import os

from ghostqa.agent.gateway import NullLLM
from ghostqa.exploration.policy import GhostPolicy
from ghostqa.exploration.return_cycle_guard import (
    ReturnCycleGuardGhostPolicy, ReturnCycleGuardSequenceController,
)
from ghostqa.exploration.sequence import SequenceController
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState, UIElement
from benchmark.algorithm_freeze import DEFAULT_FREEZE, verify_freeze
from benchmark.web_runner import make_policy

try:
    from helpers import make_hub_state, make_seq_el
except ImportError:
    from tests.helpers import make_hub_state, make_seq_el


def _leaf(url="/a", title="A"):
    return GUIState(app="t", url=url, title=title,
                    elements=(make_seq_el("x", "x"),), obs={})


def _graph():
    g = StateGraph()
    g.add_state("P", "/hub", "Hub", cluster_id="hub")
    g.add_state("A", "/a", "A", cluster_id="a")
    g.add_state("B", "/b", "B", cluster_id="b")
    g.add_state("C", "/c", "C", cluster_id="c")
    g.add_state("Av1", "/a", "A1", cluster_id="a", variant_key="v1")
    g.add_state("Av2", "/a", "A2", cluster_id="a", variant_key="v2")
    return g


def _enter_returning(ctrl, g, hub, leaf):
    """Start a branch at P then burn commitment so returning becomes true."""
    ctrl.after("P", Action("click", "go_a"), hub, leaf, "new", [], "A", False, g, 1)
    ctrl.after("A", Action("click", "x"), leaf, leaf, "identical", [], "A", False, g, 2)
    ctrl.after("A", Action("click", "x"), leaf, leaf, "identical", [], "A", False, g, 3)
    assert ctrl.ledger.returning is True
    return ctrl.ledger.return_success, ctrl.ledger.completed_total


def test_candidate_identity_distinct_from_c1():
    p = make_policy("ghost-structural-return-guard", 1)
    c1 = make_policy("ghost-structural-memory", 1)
    assert p.__class__ is ReturnCycleGuardGhostPolicy
    assert p.name == "ghost-structural-return-guard"
    assert p.use_frontier is False
    assert isinstance(p.sequence, ReturnCycleGuardSequenceController)
    assert isinstance(c1.sequence, SequenceController)
    assert not isinstance(c1.sequence, ReturnCycleGuardSequenceController)


def test_product_default_unchanged():
    p = GhostPolicy(NullLLM())
    assert p.use_frontier is False
    assert p.sequence_mode in ("off", None, "") or p.sequence is None


def test_structural_memory_policy_does_not_enable_return_guard():
    p = make_policy("ghost-structural-memory", 1)
    assert p.sequence_mode == "structural"
    src = inspect.getsource(p.sequence.__class__)
    assert "return_cycle_escape" not in src


def test_v036_freeze_still_passes():
    assert verify_freeze(DEFAULT_FREEZE) == []


def test_candidate_freeze_matches():
    path = os.path.join(
        "experiments", "frozen", "ghost-return-cycle-guard-v0.3.9", "freeze.json")
    assert verify_freeze(path) == []


def test_return_cycle_guard_escapes_on_first_exact_repeat():
    ctrl = ReturnCycleGuardSequenceController("structural")
    g, hub, leaf = _graph(), make_hub_state(), _leaf()
    rs, ct = _enter_returning(ctrl, g, hub, leaf)
    leaf_b = _leaf("/b", "B")
    ctrl.after("A", Action("click", "x"), leaf, leaf_b, "new", [], "B", False, g, 4)
    ctrl.after("B", Action("click", "x"), leaf_b, leaf, "new", [], "A", False, g, 5)
    assert ctrl.ledger.returning is False
    assert ctrl.ledger.active_branch == ""
    assert ctrl.ledger.parent_hub_sig == ""
    assert ctrl.ledger.parent_hub_cluster == ""
    assert ctrl.ledger.return_success == rs
    assert ctrl.ledger.completed_total == ct
    escapes = [e for e in ctrl.events if e.get("event") == "return_cycle_escape"]
    assert len(escapes) == 1
    assert escapes[0]["repeated_destination_sig"] == "A"
    assert ctrl.metrics()["return_cycle_escape_events"] == 1


def test_return_cycle_guard_self_loop():
    ctrl = ReturnCycleGuardSequenceController("structural")
    g, hub, leaf = _graph(), make_hub_state(), _leaf()
    _enter_returning(ctrl, g, hub, leaf)
    ctrl.after("A", Action("click", "x"), leaf, leaf, "identical", [], "A", False, g, 4)
    assert ctrl.ledger.returning is False
    assert ctrl.metrics()["return_cycle_escape_events"] == 1


def test_return_cycle_guard_preserves_successful_multistep_return():
    ctrl = ReturnCycleGuardSequenceController("structural")
    g, hub, leaf = _graph(), make_hub_state(), _leaf()
    rs, ct = _enter_returning(ctrl, g, hub, leaf)
    leaf_c = _leaf("/c", "C")
    leaf_b = _leaf("/b", "B")
    ctrl.after("A", Action("click", "x"), leaf, leaf_c, "new", [], "C", False, g, 4)
    ctrl.after("C", Action("click", "x"), leaf_c, leaf_b, "new", [], "B", False, g, 5)
    ctrl.after("B", Action("click", "x"), leaf_b, hub, "new", [], "P", False, g, 6)
    assert any(e.get("outcome") == "returned" for e in ctrl.events
               if e.get("event") == "sequence_terminal")
    assert ctrl.ledger.return_success == rs + 1
    assert ctrl.ledger.completed_total == ct + 1
    assert ctrl.metrics()["return_cycle_escape_events"] == 0
    assert ctrl.ledger.returning is False


def test_return_cycle_guard_does_not_escape_distinct_variants():
    ctrl = ReturnCycleGuardSequenceController("structural")
    g, hub, leaf = _graph(), make_hub_state(), _leaf()
    _enter_returning(ctrl, g, hub, leaf)
    v1, v2 = _leaf("/a1", "A1"), _leaf("/a2", "A2")
    ctrl.after("A", Action("click", "x"), leaf, v1, "similar", [], "Av1", False, g, 4)
    ctrl.after("Av1", Action("click", "x"), v1, v2, "similar", [], "Av2", False, g, 5)
    assert ctrl.ledger.returning is True
    assert ctrl.metrics()["return_cycle_escape_events"] == 0
    ctrl.after("Av2", Action("click", "x"), v2, hub, "new", [], "P", False, g, 6)
    assert ctrl.ledger.return_success >= 1


def test_return_cycle_escape_does_not_mark_branch_returned():
    ctrl = ReturnCycleGuardSequenceController("structural")
    g, hub, leaf = _graph(), make_hub_state(), _leaf()
    key = ctrl.ledger.active_branch
    _enter_returning(ctrl, g, hub, leaf)
    key = ctrl.ledger.active_branch
    ctrl.after("A", Action("click", "x"), leaf, leaf, "identical", [], "A", False, g, 4)
    parent = "P"
    rec = ctrl.ledger.hubs.get(parent)
    if rec is not None:
        assert key not in rec.completed
        assert key not in rec.returned
    assert not any(e.get("outcome") == "returned" for e in ctrl.events
                   if e.get("event") == "sequence_terminal")


def test_return_cycle_guard_history_resets_between_branches():
    ctrl = ReturnCycleGuardSequenceController("structural")
    g, hub, leaf = _graph(), make_hub_state(), _leaf()
    _enter_returning(ctrl, g, hub, leaf)
    ctrl.after("A", Action("click", "x"), leaf, leaf, "identical", [], "A", False, g, 4)
    assert ctrl.metrics()["return_cycle_escape_events"] == 1
    _enter_returning(ctrl, g, hub, leaf)
    leaf_c = _leaf("/c", "C")
    ctrl.after("A", Action("click", "x"), leaf, leaf_c, "new", [], "C", False, g, 10)
    ctrl.after("C", Action("click", "x"), leaf_c, hub, "new", [], "P", False, g, 11)
    assert ctrl.ledger.return_success >= 1
    assert ctrl.metrics()["return_cycle_escape_events"] == 1


def test_empty_signature_does_not_trigger_cycle():
    ctrl = ReturnCycleGuardSequenceController("structural")
    g, hub, leaf = _graph(), make_hub_state(), _leaf()
    _enter_returning(ctrl, g, hub, leaf)
    ctrl.after("A", Action("click", "x"), leaf, leaf, "identical", [], "", False, g, 4)
    ctrl.after("A", Action("click", "x"), leaf, leaf, "identical", [], "", False, g, 5)
    assert ctrl.metrics()["return_cycle_escape_events"] == 0
    assert ctrl.ledger.returning is True


def test_finding_then_return_cycle_no_false_returned():
    ctrl = ReturnCycleGuardSequenceController("structural")
    g, hub, leaf = _graph(), make_hub_state(), _leaf()

    class _F:
        def fingerprint(self):
            return "fp-1"

    ctrl.after("P", Action("click", "go_a"), hub, leaf, "new", [], "A", False, g, 1)
    ctrl.after("A", Action("click", "x"), leaf, leaf, "new", [_F()], "A", False, g, 2)
    assert ctrl.ledger.returning is True
    assert ctrl._open_instance is None
    leaf_b = _leaf("/b", "B")
    ctrl.after("A", Action("click", "x"), leaf, leaf_b, "new", [], "B", False, g, 3)
    ctrl.after("B", Action("click", "x"), leaf_b, leaf, "new", [], "A", False, g, 4)
    assert ctrl.metrics()["return_cycle_escape_events"] == 1
    returned = [e for e in ctrl.events if e.get("outcome") == "returned"]
    assert returned == []
    assert ctrl.ledger.active_branch == ""


def test_new_branch_after_escape():
    ctrl = ReturnCycleGuardSequenceController("structural")
    g, hub, leaf = _graph(), make_hub_state(), _leaf()
    _enter_returning(ctrl, g, hub, leaf)
    ctrl.after("A", Action("click", "x"), leaf, leaf, "identical", [], "A", False, g, 4)
    ctrl.after("P", Action("click", "go_b"), hub, leaf, "new", [], "B", False, g, 5)
    assert ctrl.ledger.active_branch
    assert ctrl.ledger.parent_hub_sig == "P"
    assert ctrl._seen_failed_return_dests == set()


def test_reset_clears_guard_history():
    ctrl = ReturnCycleGuardSequenceController("structural")
    g, hub, leaf = _graph(), make_hub_state(), _leaf()
    _enter_returning(ctrl, g, hub, leaf)
    ctrl.reset()
    assert ctrl._seen_failed_return_dests == set()
    assert ctrl.metrics()["return_cycle_escape_events"] == 0
    assert ctrl.ledger.active_branch == ""


def test_candidate_source_has_no_benchmark_strings():
    src = open(
        os.path.join("ghostqa", "exploration", "return_cycle_guard.py"),
        encoding="utf-8").read()
    for needle in ("cart.html", "index.html", "detail.html", "BuggyShop",
                   "billing.html", "settings.html", "BUG-H1", "BUG-H2",
                   "BUG-D6", "BUG-W"):
        assert needle not in src
    assert "RETURN_CYCLE_LIMIT" not in src


def test_protocol_preregistration_lock():
    proto = json.load(open(
        os.path.join("experiments", "validation", "v0.3.9", "protocol.json"),
        encoding="utf-8"))
    assert proto["candidate"] == "ghost-structural-return-guard"
    assert proto["deepbench"]["budgets"] == [40, 80, 120]
    assert proto["shop"]["budgets"] == [120]
    assert proto["shop"]["trials"] == [1]
    assert proto["excluded"]["h1_h2_headline"] is True
    assert set(proto["outcomes"]) == {"A", "B", "C"}
    assert proto["stop_rules"]["product_default_unchanged"] is True
    assert proto["stop_rules"]["no_threshold_N"] is True
