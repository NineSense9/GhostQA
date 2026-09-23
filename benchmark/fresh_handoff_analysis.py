"""Measurement and outcome gate for v0.3.15. Does not choose actions."""
from __future__ import annotations

import json
import os

from benchmark.fresh_handoff_qualify import qualify_topology

POLICY = {
    "C1": "ghost-structural-memory",
    "G": "ghost-structural-return-guard",
    "H": "ghost-structural-horizon-handoff-guard",
}
POSITIVE = ("buggy-forum", "buggy-billing", "buggy-lab")
NEGATIVE = "buggy-directory"
CANDIDATE_EVENTS = {
    "nested_continuation",
    "horizon_handoff_started",
    "child_parent_witness",
    "parent_frame_resume_to_return",
    "horizon_handoff_unwind",
    "witness_rejection",
}
OUTCOME_MEANING = {
    "A": (
        "Frozen Horizon Handoff transfers on at least two of three fresh "
        "qualified application shapes while preserving the frozen guard's "
        "confirmed bugs and remaining inactive on a fresh shallow negative control"
    ),
    "B": "evaluable but mixed transfer",
    "C": "validation failed or protocol invalid",
    "D": "fresh suite inconclusive",
}


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _load_jsonl(path):
    rows = []
    if not os.path.isfile(path):
        return rows
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def cell_stem(policy_name: str, budget: int, seed: int = 1) -> str:
    return f"{policy_name}_b{budget}_s{seed}"


def opportunities_from_trace(trace_rows: list) -> list:
    """Final-slot and continuation opportunities from pre-action ledger snaps.

    The step record is written before sequence.after, so its commitment is
    the value before the action. The seq_after record says whether the source
    state was a hub.
    """
    snaps = {
        _int(row.get("step")): row
        for row in trace_rows
        if row.get("kind") == "seq_after"
    }
    found = []
    for row in trace_rows:
        if row.get("kind") != "step":
            continue
        step = _int(row.get("index"))
        snap = snaps.get(step) or {}
        action = row.get("action") or {}
        if action.get("type") != "click":
            continue
        if not snap.get("is_hub"):
            continue
        if not row.get("active_branch"):
            continue
        if row.get("returning"):
            continue
        commitment = _int(row.get("commitment_left"))
        if commitment > 1:
            kind = "continuation"
        elif commitment == 1:
            kind = "handoff"
        else:
            continue
        found.append({
            "step": step,
            "kind": kind,
            "commitment_before": commitment,
            "active_branch": row.get("active_branch") or "",
            "src_sig": row.get("src_sig") or "",
            "src_cluster": row.get("src_cluster") or "",
            "src_url": row.get("src_url") or "",
            "action": action.get("target_eid") or "",
            "expected_child_parent_sig": row.get("src_sig") or "",
            "expected_child_parent_cluster": row.get("src_cluster") or "",
            "dst_sig": row.get("dst_sig") or "",
            "n_nodes": _int(row.get("n_nodes")),
        })
    return found


def match_candidate_events(sequence_events: list, trace_rows: list) -> dict:
    """Pair H events with detector opportunities and stack frames. No count fallback."""
    opps = opportunities_from_trace(trace_rows)
    by_step = {}
    for opp in opps:
        by_step.setdefault((opp["step"], opp["kind"]), []).append(opp)
    used = set()
    failures = []
    stack = []
    witness_steps = set()

    def take(step, kind):
        pool = by_step.get((step, kind)) or []
        for index, opp in enumerate(pool):
            key = (step, kind, index)
            if key in used:
                continue
            used.add(key)
            return opp
        return None

    for event in sequence_events:
        name = event.get("event")
        if name not in CANDIDATE_EVENTS:
            continue
        step = _int(event.get("step"))
        if name == "nested_continuation":
            opp = take(step, "continuation")
            if opp is None:
                failures.append(f"unmatched nested_continuation step {step}")
            elif event.get("commitment_before") not in (None, opp["commitment_before"]):
                failures.append(f"continuation commitment step {step}")
        elif name == "horizon_handoff_started":
            opp = take(step, "handoff")
            if opp is None:
                failures.append(f"unmatched horizon_handoff_started step {step}")
            else:
                expected = event.get("child_parent_sig") or ""
                if expected and expected != opp["expected_child_parent_sig"]:
                    failures.append(f"handoff parent step {step}")
                stack.append({
                    "child": event.get("child_sequence_instance_id") or "",
                    "parent_sig": opp["expected_child_parent_sig"],
                    "step": step,
                    "resumed": False,
                })
        elif name == "child_parent_witness":
            if not stack:
                failures.append(f"witness without frame step {step}")
            else:
                top = stack[-1]
                child = event.get("child_sequence_instance_id") or ""
                if top["child"] and child and top["child"] != child:
                    failures.append(f"witness wrong frame step {step}")
                else:
                    stack.pop()
                    witness_steps.add(step)
        elif name == "parent_frame_resume_to_return":
            if step not in witness_steps:
                failures.append(f"resume without witness step {step}")
        elif name == "horizon_handoff_unwind":
            escaped = any(
                item.get("event") == "return_cycle_escape" and _int(item.get("step")) == step
                for item in sequence_events
            )
            if not escaped:
                failures.append(f"unwind without escape step {step}")
            stack.clear()
        elif name == "witness_rejection":
            if not stack:
                failures.append(f"rejection without frame step {step}")
        else:
            failures.append(f"unclassified {name}")
    return {
        "ok": not failures,
        "failures": failures,
        "opportunities": opps,
        "continuation_opportunities": sum(1 for item in opps if item["kind"] == "continuation"),
        "handoff_opportunities": sum(1 for item in opps if item["kind"] == "handoff"),
    }


def lost_parent_on_qualified_chain(sequence_events, trace_rows, topology) -> int:
    qualified = qualify_topology(topology)
    pages = set()
    nodes = {node["id"]: node for node in topology.get("nodes") or []}
    for chain in qualified.get("qualifying_chains") or []:
        for node_id in chain.get("nodes") or []:
            node = nodes.get(node_id) or {}
            if node.get("page"):
                pages.add(node["page"])
    steps = {
        _int(row.get("index")): row
        for row in trace_rows
        if row.get("kind") == "step"
    }
    count = 0
    for event in sequence_events:
        if event.get("event") != "sequence_terminal":
            continue
        if event.get("outcome") != "lost_parent":
            continue
        row = steps.get(_int(event.get("step"))) or {}
        url = row.get("src_url") or ""
        if any(page in url for page in pages):
            count += 1
    return count


def post_handoff_novelty(trace_rows) -> dict:
    seen = set()
    urls = set()
    novel_states = 0
    novel_urls = 0
    started = False
    for row in trace_rows:
        if row.get("kind") != "step":
            continue
        if not started:
            if _int(row.get("commitment_left")) == 1 and row.get("active_branch") and not row.get("returning"):
                started = True
            dst = row.get("dst_sig") or ""
            if dst:
                seen.add(dst)
            if row.get("dst_url"):
                urls.add(row.get("dst_url"))
            continue
        dst = row.get("dst_sig") or ""
        url = row.get("dst_url") or ""
        if dst and dst not in seen:
            novel_states += 1
            seen.add(dst)
        if url and url not in urls:
            novel_urls += 1
            urls.add(url)
    return {"post_handoff_novel_states": novel_states, "post_handoff_novel_urls": novel_urls}


def row_at(metrics: dict, policy_name: str, budget: int) -> dict:
    for row in metrics.get("runs") or []:
        if row.get("policy") == policy_name and _int(row.get("budget")) == budget:
            return row
    return {}


def confirmed(row: dict) -> list:
    return sorted(row.get("confirmed_bugs") or [])


def full_transfer(static_ok: bool, evaluable: bool, guard: dict, candidate: dict) -> dict:
    lost = sorted(set(confirmed(guard)) - set(confirmed(candidate)))
    states_h = _int(candidate.get("states"))
    states_g = _int(guard.get("states"))
    urls_h = _int(candidate.get("normalized_unique_urls"))
    urls_g = _int(guard.get("normalized_unique_urls"))
    handoffs = _int(candidate.get("horizon_handoff_started_events"))
    witnesses = _int(candidate.get("child_parent_witness_events"))
    unwinds = _int(candidate.get("horizon_handoff_unwind_events"))
    resumes = _int(candidate.get("parent_frame_resume_to_return_events"))
    depth = _int(candidate.get("max_handoff_stack_depth"))
    horizon = _int(candidate.get("sequence_horizon_reached"))
    returned = _int(candidate.get("sequence_instances_returned"))
    escapes = _int(candidate.get("return_cycle_escape_events"))
    witness_violations = _int(candidate.get("witness_violations"))
    terminal = _int(candidate.get("terminal_accounting_violations"))
    runaway = depth == handoffs and (resumes + unwinds) == 0 and horizon == 0
    resolved = witnesses > 0 or unwinds > 0
    expanded = states_h > states_g or urls_h > urls_g
    lifecycle = horizon > 0 or returned > 0 or escapes > 0
    ok = bool(
        static_ok and evaluable and handoffs >= 1 and resolved
        and witness_violations == 0 and terminal == 0 and not lost
        and expanded and not runaway and lifecycle
    )
    return {
        "pass": ok,
        "lost_vs_guard": lost,
        "expanded": expanded,
        "resolved": resolved,
        "runaway": runaway,
        "lifecycle": lifecycle,
        "witness_violations": witness_violations,
        "terminal_accounting_violations": terminal,
    }


def evaluable_target(*, qualified: bool, guard_lost_parent: int,
                     candidate: dict, handoff_opportunities: int) -> dict:
    continuations = _int(candidate.get("nested_continuation_events"))
    handoffs = _int(candidate.get("horizon_handoff_started_events"))
    by_guard = qualified and guard_lost_parent > 0
    by_candidate = continuations > 0 and handoffs > 0
    by_detector = handoff_opportunities > 0
    return {
        "actual_evaluable": bool(by_guard or by_candidate or by_detector),
        "by_guard_lost_parent": by_guard,
        "by_candidate_events": by_candidate,
        "by_detector": by_detector,
        "guard_lost_parent": guard_lost_parent,
        "handoff_opportunities": handoff_opportunities,
    }


def negative_control_gate(guard: dict, candidate: dict) -> dict:
    lost = sorted(set(confirmed(guard)) - set(confirmed(candidate)))
    handoffs = _int(candidate.get("horizon_handoff_started_events"))
    witnesses = _int(candidate.get("child_parent_witness_events"))
    resumes = _int(candidate.get("parent_frame_resume_to_return_events"))
    depth = _int(candidate.get("max_handoff_stack_depth"))
    witness_violations = _int(candidate.get("witness_violations"))
    terminal = _int(candidate.get("terminal_accounting_violations"))
    clean = (
        handoffs == 0 and witnesses == 0 and resumes == 0 and depth == 0
        and witness_violations == 0 and terminal == 0 and not lost
    )
    keys = (
        "states", "normalized_unique_urls", "return_attempt_events",
        "sequence_instances_returned", "return_cycle_escape_events",
    )
    same = {key: guard.get(key) == candidate.get(key) for key in keys}
    same["confirmed_bugs"] = confirmed(guard) == confirmed(candidate)
    return {
        "pass": clean,
        "horizon_handoff_started_events": handoffs,
        "child_parent_witness_events": witnesses,
        "parent_frame_resume_to_return_events": resumes,
        "max_handoff_stack_depth": depth,
        "witness_violations": witness_violations,
        "terminal_accounting_violations": terminal,
        "lost_vs_guard": lost,
        "lifecycle_equivalence": same,
    }


def derive_v0315_outcome(
    *,
    candidate_freeze_ok: bool,
    suite_freeze_ok: bool,
    protocol_ok: bool,
    static_qualification_ok: bool,
    historical_safety_ok: bool,
    source_isolation_ok: bool,
    witness_violations: int,
    terminal_accounting_violations: int,
    app_specific_logic: bool,
    bug_loss_apps: list,
    negative_control_handoffs: int,
    product_default_changed: bool,
    post_freeze_tuning: bool,
    judge_leakage: bool,
    target_changed_after_result: bool = False,
    generator_used_feedback: bool = False,
    actual_evaluable_positive_targets: int,
    full_transfer_targets: int,
) -> dict:
    """Preregistered order: C, then D, then B, else A."""
    harmful = (
        not candidate_freeze_ok
        or not suite_freeze_ok
        or not protocol_ok
        or not static_qualification_ok
        or not historical_safety_ok
        or not source_isolation_ok
        or _int(witness_violations) > 0
        or _int(terminal_accounting_violations) > 0
        or bool(app_specific_logic)
        or bool(bug_loss_apps)
        or _int(negative_control_handoffs) > 0
        or bool(product_default_changed)
        or bool(post_freeze_tuning)
        or bool(judge_leakage)
        or bool(target_changed_after_result)
        or bool(generator_used_feedback)
    )
    evaluable = _int(actual_evaluable_positive_targets)
    transferred = _int(full_transfer_targets)
    if harmful:
        outcome = "C"
    elif evaluable < 2:
        outcome = "D"
    elif transferred < 2:
        outcome = "B"
    else:
        outcome = "A"
    readiness = (
        "evidence_supports_productization_study" if outcome == "A" else "not_ready"
    )
    return {
        "outcome": outcome,
        "outcome_meaning": OUTCOME_MEANING[outcome],
        "promotion_readiness": readiness,
        "product_default_changed": bool(product_default_changed),
        "generalization_claim": False,
        "actual_evaluable_positive_targets": evaluable,
        "full_transfer_targets": transferred,
        "bug_loss_apps": list(bug_loss_apps or []),
        "negative_control_handoffs": _int(negative_control_handoffs),
        "witness_violations": _int(witness_violations),
        "terminal_accounting_violations": _int(terminal_accounting_violations),
    }


def product_default_changed() -> bool:
    import inspect
    from ghostqa.exploration.policy import GhostPolicy
    signature = inspect.signature(GhostPolicy.__init__)
    frontier = signature.parameters["use_frontier"].default
    mode = signature.parameters["sequence_mode"].default
    main_path = os.path.join("ghostqa", "__main__.py")
    text = open(main_path, encoding="utf-8").read()
    cli_default = 'default="ghost"' in text or "default='ghost'" in text
    return not (frontier is False and mode == "off" and cli_default)
