"""v0.3.14 measurement re-audit of the published v0.3.13 restore metric.

The historical ``stack_audit`` accepts a parent-frame resume when the child
has a same-step ``returned`` terminal or a prior finding/crash terminal. It
does not accept a same-step finding or crash whose browser destination is
already the recorded child parent. Historical SequenceController can close
that child and increment return_success in the same call. This module joins
sequence events to browser steps and reports the corrected residual.

It does not rewrite ``experiments/published/nested-stack-v0.3.13``.
"""
from __future__ import annotations

import argparse
import json
import os

from benchmark.application_shape_evidence import (
    canonical_json_bytes, load_json, load_jsonl, sha256_bytes,
)
from benchmark.nested_stack_analysis import derive_v0313_outcome, stack_audit

PUBLISHED_ROOT = os.path.join("experiments", "published", "nested-stack-v0.3.13")
VALIDATION_JSON = os.path.join(
    "experiments", "validation", "v0.3.14", "v0313-restore-reaudit.json")
STACK = "ghost-structural-nested-stack-guard"
PRIMARY = 120
APPS = (
    "buggy-crm",
    "buggy-desk",
    "buggy-ops",
    "buggy-shop",
    "deepbench",
    "wiki",
)
SAME_STEP_CONTEXTS = ("returned", "finding_same_step", "crash_same_step")
ACCEPTED_CONTEXTS = SAME_STEP_CONTEXTS + ("finding_prior", "crash_prior")


def _steps_by_index(events: list) -> dict:
    out = {}
    for event in events or []:
        if event.get("kind") != "step":
            continue
        out[event.get("index")] = event
    return out


def _branch_starts(seq: list) -> dict:
    out = {}
    for event in seq or []:
        if event.get("event") != "branch_start":
            continue
        iid = event.get("sequence_instance_id")
        if iid:
            out[iid] = event
    return out


def _child_starts(seq: list) -> dict:
    out = {}
    for event in seq or []:
        if event.get("event") != "nested_child_started":
            continue
        iid = event.get("child_sequence_instance_id")
        if iid:
            out[iid] = event
    return out


def _terminals_for(seq: list, child_id: str) -> list:
    return [
        event for event in seq or []
        if event.get("event") == "sequence_terminal"
        and event.get("sequence_instance_id") == child_id
    ]


def _old_bad_indexes(seq: list) -> set:
    """Resume positions the historical detector rejects."""
    audit = stack_audit(seq)
    return {
        item.get("index")
        for item in (audit.get("bad_restore") or [])
        if item.get("index") is not None
    }


def _terminal_context(terminals: list, step) -> str:
    same = [item for item in terminals if item.get("step") == step]
    outcomes = [item.get("outcome") for item in same]
    if "returned" in outcomes:
        return "returned"
    if "finding" in outcomes:
        return "finding_same_step"
    if "crash" in outcomes:
        return "crash_same_step"
    prior = []
    for item in terminals:
        item_step = item.get("step")
        if item_step is None or step is None:
            continue
        if int(item_step) < int(step):
            prior.append(item.get("outcome"))
    if "finding" in prior:
        return "finding_prior"
    if "crash" in prior:
        return "crash_prior"
    return "none"


def classify_resume(seq: list, steps: dict, event: dict, index: int) -> dict:
    """Judge one parent_frame_resumed event from joined evidence."""
    child_id = event.get("child_sequence_instance_id") or ""
    child_branch = event.get("child_branch") or ""
    step = event.get("step")
    started = _branch_starts(seq).get(child_id) or {}
    child_start = _child_starts(seq).get(child_id) or {}
    parent_sig = started.get("exact_sig") or ""
    parent_cluster = started.get("cluster_id") or ""
    started_branch = started.get("branch_key") or ""
    browser = steps.get(step)
    dst_sig = "" if browser is None else (browser.get("dst_sig") or "")
    dst_cluster = "" if browser is None else (browser.get("dst_cluster") or "")
    terminals = _terminals_for(seq, child_id)
    context = _terminal_context(terminals, step)
    exact = bool(parent_sig) and dst_sig == parent_sig
    cluster = bool(parent_cluster) and dst_cluster == parent_cluster
    if exact:
        strength = "exact"
    elif cluster:
        strength = "cluster"
    else:
        strength = ""
    escaped = any(
        item.get("event") == "return_cycle_escape" and item.get("step") == step
        for item in seq
    )
    same_step_other = [
        item for item in seq
        if item.get("event") == "sequence_terminal"
        and item.get("step") == step
        and item.get("sequence_instance_id") not in (None, "", child_id)
    ]
    identity_ok = bool(child_id) and bool(started)
    if child_branch and started_branch and child_branch != started_branch:
        identity_ok = False
    if child_start:
        if (child_start.get("child_sequence_instance_id") or "") != child_id:
            identity_ok = False
        recorded_parent = child_start.get("parent_hub_sig") or ""
        if recorded_parent and parent_sig and recorded_parent != parent_sig:
            identity_ok = False
    if same_step_other and context == "none":
        identity_ok = False
    physical = strength in ("exact", "cluster")
    terminal_ok = context in ACCEPTED_CONTEXTS
    # Same-step returned is itself the historical completion record, and it
    # still has to land on the recorded parent. Finding/crash, including a
    # prior terminal, count only together with that physical parent witness.
    historical_return = physical and terminal_ok and not escaped
    accepted = bool(
        identity_ok and physical and terminal_ok and not escaped
        and historical_return and browser is not None
    )
    reasons = []
    if browser is None:
        reasons.append("missing_browser_step")
    if not identity_ok:
        reasons.append("child_identity")
    if not physical:
        reasons.append("parent_mismatch")
    if escaped:
        reasons.append("escape_same_step")
    if not terminal_ok:
        reasons.append("no_terminal_evidence")
    if not historical_return:
        reasons.append("no_historical_return")
    return {
        "index": index,
        "step": step,
        "child_sequence_instance_id": child_id,
        "child_branch": child_branch,
        "recorded_child_parent_sig": parent_sig,
        "recorded_child_parent_cluster": parent_cluster,
        "destination_sig": dst_sig,
        "destination_cluster": dst_cluster,
        "witness_strength": strength,
        "terminal_context": context,
        "escape_same_step": escaped,
        "browser_step_joined": browser is not None,
        "identity_ok": identity_ok,
        "physical_parent_match": physical,
        "historical_return_completion": historical_return,
        "accepted": accepted,
        "reasons": [] if accepted else reasons,
    }


def audit_trace(seq: list, browser_events: list) -> dict:
    """Corrected resume audit for one sequence/browser pair."""
    steps = _steps_by_index(browser_events)
    old_indexes = _old_bad_indexes(seq)
    rows = []
    for index, event in enumerate(seq or []):
        if event.get("event") != "parent_frame_resumed":
            continue
        row = classify_resume(seq, steps, event, index)
        row["old_detector_bad"] = index in old_indexes
        rows.append(row)
    old_bad = [row for row in rows if row["old_detector_bad"]]
    residual = [row for row in rows if not row["accepted"]]
    joined = all(row["browser_step_joined"] for row in rows) if rows else True

    def _count(context: str) -> int:
        return sum(
            1 for row in rows
            if row["accepted"] and row["terminal_context"] == context
        )

    return {
        "resume_count": len(rows),
        "old_bad_restore_count": len(old_bad),
        "same_step_finding_witness_count": _count("finding_same_step"),
        "same_step_crash_witness_count": _count("crash_same_step"),
        "same_step_returned_count": _count("returned"),
        "corrected_residual_bad_count": len(residual),
        "corrected_bad_examples": [
            {
                "step": row["step"],
                "child_sequence_instance_id": row["child_sequence_instance_id"],
                "reasons": row["reasons"],
                "terminal_context": row["terminal_context"],
                "destination_sig": row["destination_sig"],
                "recorded_child_parent_sig": row["recorded_child_parent_sig"],
            }
            for row in residual
        ],
        "old_bad_examples": [
            {
                "step": row["step"],
                "child_sequence_instance_id": row["child_sequence_instance_id"],
                "terminal_context": row["terminal_context"],
                "witness_strength": row["witness_strength"],
                "accepted_by_corrected_rule": row["accepted"],
            }
            for row in old_bad
        ],
        "browser_step_join_verified": joined,
        "resumes": rows,
    }


def _trace_paths(root: str, app: str, budget: int) -> tuple:
    stem = f"{STACK}_b{budget}_s1"
    base = os.path.join(root, "evidence", app, stem)
    return base + ".sequence_events.json", base + ".events.jsonl"


def _load_pair(root: str, app: str, budget: int):
    seq_path, ev_path = _trace_paths(root, app, budget)
    if not os.path.isfile(seq_path) or not os.path.isfile(ev_path):
        return None
    return load_json(seq_path), load_jsonl(ev_path)


def _published_counterfactual(root: str, *, restore_without_child_return: bool) -> dict:
    mechanism = load_json(os.path.join(root, "metrics", "mechanism.json"))
    regression = load_json(os.path.join(root, "metrics", "regression.json"))
    safety = load_json(os.path.join(root, "metrics", "stack-safety.json"))
    audit = mechanism.get("stack_audit") or {}
    lost = {
        case_id: list((case.get("lost_vs_guard") or []))
        for case_id, case in (regression.get("cases") or {}).items()
    }
    targets = mechanism.get("targets") or {}
    crm = bool(((targets.get("buggy-crm") or {}).get("assessment_120") or {}).get("pass"))
    ops = bool(((targets.get("buggy-ops") or {}).get("assessment_120") or {}).get("pass"))
    derived = derive_v0313_outcome(
        candidate_freeze_ok=bool(safety.get("candidate_freeze_ok")),
        historical_freezes_ok=bool(safety.get("historical_freezes_ok")),
        p_series_failures=int(safety.get("p_series_failures") or 0),
        s1_s7_pass=bool(safety.get("s1_s7_all_pass")),
        exhaustive_failures=int(safety.get("exhaustive_failures") or 0),
        exhaustive_traces=int(safety.get("exhaustive_traces") or 0),
        terminal_accounting_violations=int(audit.get("terminal_accounting_violations") or 0),
        return_inflation=bool(audit.get("return_inflation")),
        stack_frame_corruption=bool(audit.get("stack_frame_corruption")),
        restore_without_child_return=bool(restore_without_child_return),
        app_specific_logic=bool(safety.get("app_specific_logic")),
        product_default_changed=bool(safety.get("product_default_changed")),
        crm_repair=crm,
        ops_repair=ops,
        lost_vs_guard=lost,
    )
    return {
        "restore_without_child_return": bool(restore_without_child_return),
        "published_outcome": (mechanism.get("derived") or {}).get("outcome"),
        "counterfactual_outcome": derived["outcome"],
        "counterfactual_meaning": derived["outcome_meaning"],
        "crm_repair": derived["crm_repair"],
        "ops_repair": derived["ops_repair"],
        "lost_vs_guard": derived["lost_vs_guard"],
        "additional_lost": derived["additional_lost"],
        "lost_cases": derived["lost_cases"],
        "safety_failure": derived["safety_failure"],
        "promotable": derived["outcome"] == "A",
        "publication_rewritten": False,
    }


def _app_budgets(root: str, app: str) -> list:
    folder = os.path.join(root, "evidence", app)
    budgets = []
    if not os.path.isdir(folder):
        return budgets
    prefix = STACK + "_b"
    for name in os.listdir(folder):
        if not name.startswith(prefix) or not name.endswith(".sequence_events.json"):
            continue
        middle = name[len(prefix):-len("_s1.sequence_events.json")]
        try:
            budgets.append(int(middle))
        except ValueError:
            continue
    return sorted(set(budgets))


def build_report(root: str = PUBLISHED_ROOT) -> dict:
    """Re-audit every published stack trace. Primary fields are budget 120."""
    apps = {}
    for app in APPS:
        budgets = {}
        for budget in _app_budgets(root, app):
            loaded = _load_pair(root, app, budget)
            if loaded is None:
                continue
            seq, browser = loaded
            view = audit_trace(seq, browser)
            view.pop("resumes", None)
            view["budget"] = budget
            view["v0313_reference_outcome"] = "C"
            budgets[str(budget)] = view
        primary = dict(budgets.get(str(PRIMARY)) or {})
        primary["v0313_reference_outcome"] = "C"
        primary["budgets"] = {
            key: {
                "resume_count": row["resume_count"],
                "old_bad_restore_count": row["old_bad_restore_count"],
                "corrected_residual_bad_count": row["corrected_residual_bad_count"],
            }
            for key, row in budgets.items()
        }
        apps[app] = primary
    published = _published_counterfactual(root, restore_without_child_return=True)
    corrected = _published_counterfactual(root, restore_without_child_return=False)
    return {
        "version": "v0.3.14",
        "kind": "v0.3.13-restore-reaudit",
        "source_publication": "experiments/published/nested-stack-v0.3.13",
        "source_policy": STACK,
        "seed": 1,
        "primary_budget": PRIMARY,
        "publication_rewritten": False,
        "v0313_published_outcome": published["published_outcome"],
        "old_detector": {
            "name": "stack_audit",
            "accepts": [
                "same-step sequence_terminal outcome=returned",
                "prior-step sequence_terminal outcome=finding or crash",
            ],
            "does_not_accept": [
                "same-step finding or crash together with a same-step physical child-parent match",
            ],
        },
        "corrected_acceptance": [
            "child identity matches the recorded branch_start",
            "browser destination matches the recorded child parent exact signature or cluster",
            "no same-step return_cycle_escape",
            "historical return completion is a same-step returned terminal, a same-step finding, a same-step crash, or a prior finding/crash with the physical parent match",
            "a global return_success change is not sufficient",
        ],
        "apps": apps,
        "counterfactual_gate": corrected,
        "published_gate": {
            "outcome": published["counterfactual_outcome"],
            "restore_without_child_return": True,
        },
    }


def write_report(path: str = VALIDATION_JSON, root: str = PUBLISHED_ROOT) -> dict:
    report = build_report(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = canonical_json_bytes(report)
    with open(path, "wb") as handle:
        handle.write(payload)
    report["sha256"] = sha256_bytes(payload)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=PUBLISHED_ROOT)
    parser.add_argument("--write", default="")
    args = parser.parse_args(argv)
    if args.write:
        report = write_report(args.write, args.root)
        print(args.write)
        print(report["sha256"])
    else:
        report = build_report(args.root)
    for app, row in (report.get("apps") or {}).items():
        print(
            f"{app} resumes={row.get('resume_count')} "
            f"old_bad={row.get('old_bad_restore_count')} "
            f"finding={row.get('same_step_finding_witness_count')} "
            f"crash={row.get('same_step_crash_witness_count')} "
            f"returned={row.get('same_step_returned_count')} "
            f"residual={row.get('corrected_residual_bad_count')}"
        )
    gate = report.get("counterfactual_gate") or {}
    print(
        f"counterfactual outcome {gate.get('counterfactual_outcome')} "
        f"crm_repair={gate.get('crm_repair')} ops_repair={gate.get('ops_repair')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
