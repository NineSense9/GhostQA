"""Deterministic S1–S7 safety suite for the frozen return-cycle guard.

Independent of BuggyDesk BDR. Does not read manifests.
"""
from __future__ import annotations

from ghostqa.exploration.return_cycle_guard import ReturnCycleGuardSequenceController
from ghostqa.exploration.sequence import SequenceController
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState, UIElement


def make_seq_el(eid, text, kind="click"):
    return UIElement(eid, "button", text, kind=kind)


def make_hub_state():
    return GUIState(
        app="t", url="/hub", title="Hub",
        elements=(
            make_seq_el("go_a", "分支A"),
            make_seq_el("go_b", "分支B"),
            make_seq_el("go_c", "分支C"),
            make_seq_el("submit", "提交"),
        ), obs={})


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
    ctrl.after("P", Action("click", "go_a"), hub, leaf, "new", [], "A", False, g, 1)
    ctrl.after("A", Action("click", "x"), leaf, leaf, "identical", [], "A", False, g, 2)
    ctrl.after("A", Action("click", "x"), leaf, leaf, "identical", [], "A", False, g, 3)
    return ctrl.ledger.return_success, ctrl.ledger.completed_total


def _escapes(ctrl):
    return sum(1 for e in ctrl.events if e.get("event") == "return_cycle_escape")


def _returned(ctrl):
    return sum(1 for e in ctrl.events
               if e.get("event") == "sequence_terminal" and e.get("outcome") == "returned")


def run_s1():
    ctrl = ReturnCycleGuardSequenceController("structural")
    g, hub, leaf = _graph(), make_hub_state(), _leaf()
    rs, _ = _enter_returning(ctrl, g, hub, leaf)
    ctrl.after("A", Action("click", "backh"), leaf, hub, "new", [], "P", False, g, 4)
    esc, ret = _escapes(ctrl), _returned(ctrl)
    ok = esc == 0 and ret >= 1 and ctrl.ledger.return_success == rs + 1
    return {"scenario": "S1", "name": "direct successful return",
            "expected": "returned terminal, zero escape",
            "observed": f"escapes={esc} returned={ret}",
            "escapes": esc, "returned": ret, "pass": ok}


def run_s2():
    ctrl = ReturnCycleGuardSequenceController("structural")
    g, hub, leaf = _graph(), make_hub_state(), _leaf()
    rs, _ = _enter_returning(ctrl, g, hub, leaf)
    leaf_c, leaf_b = _leaf("/c", "C"), _leaf("/b", "B")
    ctrl.after("A", Action("click", "x"), leaf, leaf_c, "new", [], "C", False, g, 4)
    ctrl.after("C", Action("click", "x"), leaf_c, leaf_b, "new", [], "B", False, g, 5)
    ctrl.after("B", Action("click", "x"), leaf_b, hub, "new", [], "P", False, g, 6)
    esc, ret = _escapes(ctrl), _returned(ctrl)
    ok = esc == 0 and ret >= 1 and ctrl.ledger.return_success == rs + 1
    return {"scenario": "S2", "name": "multi-step successful return",
            "expected": "successful return, zero escape",
            "observed": f"escapes={esc} returned={ret}",
            "escapes": esc, "returned": ret, "pass": ok}


def run_s3():
    ctrl = ReturnCycleGuardSequenceController("structural")
    g, hub, leaf = _graph(), make_hub_state(), _leaf()
    _enter_returning(ctrl, g, hub, leaf)
    v1, v2 = _leaf("/a1", "A1"), _leaf("/a2", "A2")
    ctrl.after("A", Action("click", "x"), leaf, v1, "similar", [], "Av1", False, g, 4)
    ctrl.after("Av1", Action("click", "x"), v1, v2, "similar", [], "Av2", False, g, 5)
    esc_mid = _escapes(ctrl)
    ctrl.after("Av2", Action("click", "x"), v2, hub, "new", [], "P", False, g, 6)
    esc, ret = _escapes(ctrl), _returned(ctrl)
    ok = esc_mid == 0 and esc == 0 and ret >= 1
    return {"scenario": "S3", "name": "same cluster, distinct exact variants",
            "expected": "zero escape solely because cluster repeats",
            "observed": f"escapes={esc} returned={ret}",
            "escapes": esc, "returned": ret, "pass": ok}


def run_s4():
    ctrl = ReturnCycleGuardSequenceController("structural")
    g, hub, leaf = _graph(), make_hub_state(), _leaf()
    rs, ct = _enter_returning(ctrl, g, hub, leaf)
    ctrl.after("A", Action("click", "x"), leaf, leaf, "identical", [], "A", False, g, 4)
    esc, ret = _escapes(ctrl), _returned(ctrl)
    inflation = ctrl.ledger.return_success - rs
    ok = (esc == 1 and ret == 0 and inflation == 0
          and ctrl.ledger.completed_total == ct
          and ctrl.ledger.active_branch == "")
    return {"scenario": "S4", "name": "exact self-loop",
            "expected": "exactly one escape, abandoned, not returned",
            "observed": f"escapes={esc} returned={ret} inflation={inflation}",
            "escapes": esc, "returned": ret, "return_inflation": inflation,
            "pass": ok}


def run_s5():
    ctrl = ReturnCycleGuardSequenceController("structural")
    g, hub, leaf = _graph(), make_hub_state(), _leaf()
    rs, ct = _enter_returning(ctrl, g, hub, leaf)
    leaf_b = _leaf("/b", "B")
    ctrl.after("A", Action("click", "x"), leaf, leaf_b, "new", [], "B", False, g, 4)
    ctrl.after("B", Action("click", "x"), leaf_b, leaf, "new", [], "A", False, g, 5)
    esc, ret = _escapes(ctrl), _returned(ctrl)
    inflation = ctrl.ledger.return_success - rs
    ok = (esc == 1 and ret == 0 and inflation == 0
          and ctrl.ledger.completed_total == ct
          and ctrl.ledger.active_branch == "")
    return {"scenario": "S5", "name": "short A→B→A cycle",
            "expected": "escape on first exact repeated destination; abandoned",
            "observed": f"escapes={esc} returned={ret} inflation={inflation}",
            "escapes": esc, "returned": ret, "return_inflation": inflation,
            "pass": ok}


def run_s6():
    ctrl = ReturnCycleGuardSequenceController("structural")
    g, hub, leaf = _graph(), make_hub_state(), _leaf()
    _enter_returning(ctrl, g, hub, leaf)
    ctrl.after("A", Action("click", "x"), leaf, leaf, "identical", [], "A", False, g, 4)
    esc1 = _escapes(ctrl)
    _enter_returning(ctrl, g, hub, leaf)
    leaf_c = _leaf("/c", "C")
    ctrl.after("A", Action("click", "x"), leaf, leaf_c, "new", [], "C", False, g, 10)
    ctrl.after("C", Action("click", "x"), leaf_c, hub, "new", [], "P", False, g, 11)
    esc, ret = _escapes(ctrl), _returned(ctrl)
    ok = esc1 == 1 and esc == 1 and ret >= 1
    return {"scenario": "S6", "name": "history reset between branches",
            "expected": "branch-one cycle history does not poison branch two",
            "observed": f"escapes={esc} returned={ret}",
            "escapes": esc, "returned": ret, "pass": ok}


def run_s7():
    ctrl = ReturnCycleGuardSequenceController("structural")
    g, hub, leaf = _graph(), make_hub_state(), _leaf()

    class _F:
        def fingerprint(self):
            return "fp-1"

    ctrl.after("P", Action("click", "go_a"), hub, leaf, "new", [], "A", False, g, 1)
    ctrl.after("A", Action("click", "x"), leaf, leaf, "new", [_F()], "A", False, g, 2)
    leaf_b = _leaf("/b", "B")
    ctrl.after("A", Action("click", "x"), leaf, leaf_b, "new", [], "B", False, g, 3)
    ctrl.after("B", Action("click", "x"), leaf_b, leaf, "new", [], "A", False, g, 4)
    esc, ret = _escapes(ctrl), _returned(ctrl)
    ok = esc == 1 and ret == 0 and ctrl.ledger.active_branch == ""
    return {"scenario": "S7", "name": "finding then cycle",
            "expected": "finding + cycle escape is not counted returned",
            "observed": f"escapes={esc} returned={ret}",
            "escapes": esc, "returned": ret, "pass": ok}


def collect_safety_suite() -> dict:
    rows = [run_s1(), run_s2(), run_s3(), run_s4(), run_s5(), run_s6(), run_s7()]
    return {
        "rows": rows,
        "all_pass": all(r["pass"] for r in rows),
        "s1_escapes": rows[0]["escapes"],
        "s2_escapes": rows[1]["escapes"],
        "s3_escapes": rows[2]["escapes"],
        "s4_escapes": rows[3]["escapes"],
        "s4_returned_inflation": rows[3].get("return_inflation", 0),
        "s5_escapes": rows[4]["escapes"],
        "s5_returned_inflation": rows[4].get("return_inflation", 0),
        "c1_controller_is_unguarded": not isinstance(
            SequenceController("structural"), ReturnCycleGuardSequenceController),
    }
