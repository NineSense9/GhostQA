"""Deterministic bounded model check for ReturnCycleGuardSequenceController.

Enumerates abstract return-phase traces over {P, A, B, C} of length 1..6
and compares the live controller against a reference model. Not a theorem
prover. Independent of application targets and bug manifests.
"""
from __future__ import annotations

import itertools

from ghostqa.exploration.return_cycle_guard import ReturnCycleGuardSequenceController
from ghostqa.state.graph import StateGraph
from ghostqa.state.models import Action, GUIState, UIElement

from benchmark.return_cycle_safety import (
    _enter_returning, _escapes, _returned, collect_safety_suite, make_hub_state,
    make_seq_el,
)


ALPHABET = ("P", "A", "B", "C")
TRACE_LENGTHS = (1, 2, 3, 4, 5, 6)
VARIANT_ALPHABET = ("P", "A1", "A2", "B")
VARIANT_LENGTHS = (1, 2, 3, 4)


def _leaf(url, title):
    return GUIState(
        app="t", url=url, title=title,
        elements=(make_seq_el("x", "x"),), obs={})


def _base_graph():
    g = StateGraph()
    g.add_state("P", "/hub", "Hub", cluster_id="hub")
    g.add_state("A", "/a", "A", cluster_id="a")
    g.add_state("B", "/b", "B", cluster_id="b")
    g.add_state("C", "/c", "C", cluster_id="c")
    g.add_state("A1", "/a1", "A1", cluster_id="a", variant_key="v1")
    g.add_state("A2", "/a2", "A2", cluster_id="a", variant_key="v2")
    return g


def _states():
    return {
        "P": make_hub_state(),
        "A": _leaf("/a", "A"),
        "B": _leaf("/b", "B"),
        "C": _leaf("/c", "C"),
        "A1": _leaf("/a1", "A1"),
        "A2": _leaf("/a2", "A2"),
    }


def cluster_of(dest: str) -> str:
    if dest == "P":
        return "hub"
    if dest in ("A", "A1", "A2"):
        return "a"
    if dest == "B":
        return "b"
    if dest == "C":
        return "c"
    return dest


def reference_return_phase(dests, *, parent="P", parent_cluster="hub"):
    """Independent model of one return phase.

    Parent match uses exact id or parent cluster (mirrors SequenceController).
    Cycle trigger uses exact destination identity only.
    """
    seen: set = set()
    returning = True
    events = []
    for i, dest in enumerate(dests):
        if not returning:
            events.append({"i": i, "dest": dest, "kind": "outside"})
            continue
        if not dest:
            events.append({"i": i, "dest": dest, "kind": "skip"})
            continue
        parent_hit = dest == parent or cluster_of(dest) == parent_cluster
        if parent_hit:
            events.append({"i": i, "dest": dest, "kind": "return"})
            returning = False
            seen = set()
            continue
        if dest in seen:
            events.append({"i": i, "dest": dest, "kind": "escape"})
            returning = False
            seen = set()
            continue
        seen.add(dest)
        events.append({"i": i, "dest": dest, "kind": "continue"})
    return events


def _first_kind(events, kind):
    for e in events:
        if e["kind"] == kind:
            return e["i"]
    return None


def expected_from_reference(dests) -> dict:
    ev = reference_return_phase(dests)
    esc = _first_kind(ev, "escape")
    ret = _first_kind(ev, "return")
    return {
        "events": ev,
        "escape_index": esc,
        "return_index": ret,
        "n_escape": sum(1 for e in ev if e["kind"] == "escape"),
        "n_return": sum(1 for e in ev if e["kind"] == "return"),
    }


def run_controller_trace(dests) -> dict:
    """Drive the live guard. seen starts empty at the return-phase boundary."""
    ctrl = ReturnCycleGuardSequenceController("structural")
    g = _base_graph()
    st = _states()
    hub, leaf = st["P"], st["A"]
    rs, ct = _enter_returning(ctrl, g, hub, leaf)
    ctrl._seen_failed_return_dests = set()
    prev_id, prev_state = "A", leaf
    step = 4
    esc_idx = None
    ret_idx = None
    n_escape_first_phase = 0
    inflation = False
    later_phase = False
    n_branch_starts = sum(1 for e in ctrl.events if e.get("event") == "branch_start")
    for i, dest in enumerate(dests):
        n_esc_before = _escapes(ctrl)
        rs_before = ctrl.ledger.return_success
        ct_before = ctrl.ledger.completed_total
        starts_before = n_branch_starts
        new_state = st[dest]
        if dest == prev_id:
            relation = "identical"
        elif cluster_of(dest) == cluster_of(prev_id) and dest != "P" and prev_id != "P":
            relation = "similar"
        else:
            relation = "new"
        ctrl.after(
            prev_id, Action("click", "x"), prev_state, new_state,
            relation, [], dest, False, g, step)
        n_branch_starts = sum(
            1 for e in ctrl.events if e.get("event") == "branch_start")
        if esc_idx is None and ret_idx is None:
            if _escapes(ctrl) > n_esc_before:
                esc_idx = i
                n_escape_first_phase = 1
                if ctrl.ledger.return_success != rs or ctrl.ledger.completed_total != ct:
                    inflation = True
            elif ctrl.ledger.return_success > rs_before:
                ret_idx = i
        elif esc_idx is not None and not later_phase:
            if n_branch_starts > starts_before:
                later_phase = True
            elif ctrl.ledger.return_success != rs_before or ctrl.ledger.completed_total != ct_before:
                # Same return phase after escape: parent must not convert it (R7).
                inflation = True
        prev_id, prev_state = dest, new_state
        step += 1
    return {
        "escape_index": esc_idx,
        "return_index": ret_idx,
        "n_escape": n_escape_first_phase if esc_idx is not None else 0,
        "n_return_after_enter": 1 if ret_idx is not None else 0,
        "return_success_delta": ctrl.ledger.return_success - rs,
        "completed_delta": ctrl.ledger.completed_total - ct,
        "active_branch": ctrl.ledger.active_branch,
        "returning": ctrl.ledger.returning,
        "inflation": inflation,
        "escapes": [e for e in ctrl.events if e.get("event") == "return_cycle_escape"],
    }


def compare_trace(dests) -> dict:
    exp = expected_from_reference(dests)
    obs = run_controller_trace(dests)
    ok = (
        exp["escape_index"] == obs["escape_index"]
        and exp["return_index"] == obs["return_index"]
        and exp["n_escape"] == obs["n_escape"]
        and not obs["inflation"]
    )
    # R7: parent after theoretical repeat must not convert escape to return.
    if exp["escape_index"] is not None:
        if obs["return_index"] is not None and obs["return_index"] >= exp["escape_index"]:
            ok = False
    return {
        "dests": list(dests),
        "ok": ok,
        "expected": {
            "escape_index": exp["escape_index"],
            "return_index": exp["return_index"],
        },
        "observed": {
            "escape_index": obs["escape_index"],
            "return_index": obs["return_index"],
            "inflation": obs["inflation"],
            "return_success_delta": obs["return_success_delta"],
        },
    }


def _check_named_rules() -> list:
    """Explicit R1–R10 examples (also covered by the enumerator where applicable)."""
    cases = [
        ("R1", ("P",), dict(escape_index=None, return_index=0)),
        ("R1b", ("A", "P"), dict(escape_index=None, return_index=1)),
        ("R2", ("A", "B", "A"), dict(escape_index=2, return_index=None)),
        ("R3", ("A", "B", "C", "P"), dict(escape_index=None, return_index=3)),
        ("R4", ("A", "A"), dict(escape_index=1, return_index=None)),
        ("R5", ("A", "B", "A"), dict(escape_index=2, return_index=None)),
        ("R6", ("A", "B", "C", "B"), dict(escape_index=3, return_index=None)),
        ("R7", ("A", "B", "A", "P"), dict(escape_index=2, return_index=None)),
        ("R8", ("A", "B", "P", "A"), dict(escape_index=None, return_index=2)),
        ("R9", ("A1", "A2", "P"), dict(escape_index=None, return_index=2)),
        ("R9b", ("A1", "A2"), dict(escape_index=None, return_index=None)),
        ("R9c", ("A1", "A1"), dict(escape_index=1, return_index=None)),
    ]
    rows = []
    for name, dests, want in cases:
        got = compare_trace(dests)
        ok = (
            got["ok"]
            and got["expected"]["escape_index"] == want["escape_index"]
            and got["expected"]["return_index"] == want["return_index"]
        )
        rows.append({"rule": name, "dests": list(dests), "ok": ok, **got})
    # R10: cycle in branch 1 must not seed branch 2.
    rows.append(_check_r10())
    return rows


def _check_r10() -> dict:
    ctrl = ReturnCycleGuardSequenceController("structural")
    g = _base_graph()
    st = _states()
    hub, leaf = st["P"], st["A"]
    _enter_returning(ctrl, g, hub, leaf)
    ctrl._seen_failed_return_dests = set()
    ctrl.after("A", Action("click", "x"), leaf, leaf, "identical", [], "A", False, g, 4)
    ctrl.after("A", Action("click", "x"), leaf, leaf, "identical", [], "A", False, g, 5)
    esc1 = _escapes(ctrl)
    rs = ctrl.ledger.return_success
    _enter_returning(ctrl, g, hub, leaf)
    ctrl._seen_failed_return_dests = set()
    leaf_b = st["B"]
    ctrl.after("A", Action("click", "x"), leaf, leaf_b, "new", [], "B", False, g, 20)
    ctrl.after("B", Action("click", "x"), leaf_b, hub, "new", [], "P", False, g, 21)
    esc = _escapes(ctrl)
    ret = _returned(ctrl)
    ok = esc1 == 1 and esc == 1 and ret >= 1 and ctrl.ledger.return_success == rs + 1
    return {
        "rule": "R10",
        "dests": ["branch1:A,A", "branch2:B,P"],
        "ok": ok,
        "expected": {"escape_index": 1, "return_index": 1},
        "observed": {"escape_index": 1 if esc1 == 1 else None,
                     "return_index": 1 if ret else None,
                     "inflation": False,
                     "return_success_delta": ctrl.ledger.return_success - rs},
    }


def enumerate_traces(alphabet=ALPHABET, lengths=TRACE_LENGTHS) -> list:
    rows = []
    for n in lengths:
        for dests in itertools.product(alphabet, repeat=n):
            rows.append(compare_trace(dests))
    return rows


def run_exhaustive_check() -> dict:
    primary = enumerate_traces(ALPHABET, TRACE_LENGTHS)
    variants = enumerate_traces(VARIANT_ALPHABET, VARIANT_LENGTHS)
    named = _check_named_rules()
    s17 = collect_safety_suite()
    all_rows = primary + variants + named
    failures = [r for r in all_rows if not r.get("ok")]
    named_fail = [r for r in named if not r.get("ok")]
    return {
        "alphabet": list(ALPHABET),
        "trace_lengths": list(TRACE_LENGTHS),
        "primary_traces": len(primary),
        "variant_traces": len(variants),
        "named_rules": len(named),
        "traces_enumerated": len(primary) + len(variants),
        "named_plus_enumerated": len(all_rows),
        "passed": len(all_rows) - len(failures),
        "failures": len(failures),
        "named_failures": [
            {"rule": r.get("rule"), "dests": r.get("dests")} for r in named_fail
        ],
        "failure_examples": [
            {"dests": r.get("dests"), "expected": r.get("expected"),
             "observed": r.get("observed"), "rule": r.get("rule")}
            for r in failures[:12]
        ],
        "s1_s7_all_pass": bool(s17.get("all_pass")),
        "s1_s7": s17,
        "all_pass": (not failures) and bool(s17.get("all_pass")),
        "zero_failures_required": True,
    }


if __name__ == "__main__":
    rec = run_exhaustive_check()
    print("enumerated", rec["traces_enumerated"],
          "passed", rec["passed"], "failures", rec["failures"],
          "s1_s7", rec["s1_s7_all_pass"])
    if rec["failure_examples"]:
        for row in rec["failure_examples"]:
            print(" FAIL", row)
    raise SystemExit(0 if rec["all_pass"] else 2)
