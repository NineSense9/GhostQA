"""Measurement-only escape/opportunity matching and L1/L2 lifecycle.

Does not affect C1 or guard decisions. Does not read bug manifests.
"""
from __future__ import annotations

from collections import Counter

L1 = "L1_open_instance_abandonment"
L2 = "L2_already_terminal_return_cleanup"
UNCLASSIFIED = "unclassified"

MATCH_KEY_FIELDS = (
    "step",
    "repeated_destination_sig",
    "parent_hub_sig",
    "branch",
)


def branch_of(rec: dict) -> str:
    return (
        rec.get("active_branch")
        or rec.get("branch_key")
        or rec.get("branch")
        or ""
    )


def escape_match_key(rec: dict) -> tuple:
    """Structured identity for one escape or one detector opportunity."""
    return (
        rec.get("step"),
        rec.get("repeated_destination_sig") or "",
        rec.get("parent_hub_sig") or "",
        branch_of(rec),
    )


def match_escapes_to_opportunities(escapes: list, opportunities: list) -> dict:
    """Multiset match on structured keys. Count equality alone is not success.

    Every guard escape must correspond to a detector opportunity with the
    same (step, repeated_destination_sig, parent_hub_sig, branch).
    """
    ekeys = [escape_match_key(e) for e in escapes or []]
    okeys = [escape_match_key(o) for o in opportunities or []]
    ecount = Counter(ekeys)
    ocount = Counter(okeys)
    unmatched = []
    for key, n in ecount.items():
        if ocount[key] < n:
            unmatched.append({
                "key": {
                    "step": key[0],
                    "repeated_destination_sig": key[1],
                    "parent_hub_sig": key[2],
                    "branch": key[3],
                },
                "escape_count": n,
                "opportunity_count": ocount[key],
            })
    matched = sum(min(ecount[k], ocount[k]) for k in ecount)
    return {
        "ok": not unmatched,
        "escape_count": len(ekeys),
        "opportunity_count": len(okeys),
        "matched": matched,
        "unmatched_escapes": unmatched,
        "escape_keys": [
            {"step": k[0], "repeated_destination_sig": k[1],
             "parent_hub_sig": k[2], "branch": k[3]}
            for k in ekeys
        ],
        "key_fields": list(MATCH_KEY_FIELDS),
    }


def classify_escape_lifecycle(seq_events: list) -> dict:
    """Classify every return_cycle_escape as L1 or L2.

    L1: instance still open at escape; same instance emits
        sequence_terminal outcome=return_cycle_abandoned; no returned
        terminal for that instance.
    L2: instance already terminally ended while a return obligation
        remained; escape is allowed; no second sequence_terminal.
    """
    events = list(seq_events or [])
    closed: dict = {}
    rows = []
    inflation_flags = []

    for i, e in enumerate(events):
        ev = e.get("event")
        iid = e.get("sequence_instance_id")
        if ev == "sequence_terminal":
            outcome = e.get("outcome")
            if iid and iid not in closed:
                closed[iid] = {
                    "outcome": outcome,
                    "step": e.get("step"),
                    "index": i,
                    "branch": branch_of(e),
                }
            continue
        if ev != "return_cycle_escape":
            continue

        step = e.get("step")
        branch = branch_of(e)
        same_step_after = events[i + 1:]
        same_step_terminals = [
            x for x in same_step_after
            if x.get("event") == "sequence_terminal"
            and x.get("step") == step
        ]
        abandoned = [
            x for x in same_step_terminals
            if x.get("outcome") == "return_cycle_abandoned"
        ]
        returned_here = [
            x for x in same_step_terminals
            if x.get("outcome") == "returned"
        ]
        prior_for_iid = closed.get(iid) if iid else None

        klass = UNCLASSIFIED
        prior_outcome = None
        if iid and prior_for_iid is None and abandoned:
            ab_iid = abandoned[0].get("sequence_instance_id")
            if ab_iid == iid and not returned_here:
                klass = L1
                closed[iid] = {
                    "outcome": "return_cycle_abandoned",
                    "step": step,
                    "index": i,
                    "branch": branch,
                }
        elif (iid is None or prior_for_iid is not None) and not abandoned:
            klass = L2
            if prior_for_iid is not None:
                prior_outcome = prior_for_iid.get("outcome")
            else:
                prior = None
                for x in events[:i]:
                    if (x.get("event") == "sequence_terminal"
                            and branch_of(x) == branch
                            and x.get("outcome") in ("finding", "crash")):
                        prior = x
                if prior is not None:
                    prior_outcome = prior.get("outcome")
        if returned_here:
            inflation_flags.append({"step": step, "branch": branch})
            klass = UNCLASSIFIED

        rows.append({
            "step": step,
            "class": klass,
            "sequence_instance_id": iid,
            "branch": branch,
            "repeated_destination_sig": e.get("repeated_destination_sig") or "",
            "parent_hub_sig": e.get("parent_hub_sig") or "",
            "abandoned_terminal": bool(abandoned),
            "returned_terminal": bool(returned_here),
            "prior_terminal_outcome": prior_outcome,
        })

    n_l1 = sum(1 for r in rows if r["class"] == L1)
    n_l2 = sum(1 for r in rows if r["class"] == L2)
    n_un = sum(1 for r in rows if r["class"] == UNCLASSIFIED)
    n_abandoned = sum(
        1 for e in events
        if e.get("event") == "sequence_terminal"
        and e.get("outcome") == "return_cycle_abandoned"
    )
    return {
        "escapes": rows,
        "escape_count": len(rows),
        "L1": n_l1,
        "L2": n_l2,
        "unclassified": n_un,
        "return_cycle_abandoned_terminals": n_abandoned,
        "return_inflation_events": inflation_flags,
        "ok": n_un == 0 and not inflation_flags and n_l1 + n_l2 == len(rows),
    }


def lifecycle_counts(seq_events: list) -> dict:
    rec = classify_escape_lifecycle(seq_events)
    return {
        "escapes": rec["escape_count"],
        "L1_open_instance": rec["L1"],
        "L2_already_terminal": rec["L2"],
        "unclassified": rec["unclassified"],
        "abandoned_terminals": rec["return_cycle_abandoned_terminals"],
        "return_inflation": len(rec["return_inflation_events"]),
        "ok": rec["ok"],
    }
