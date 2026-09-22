"""Code-derived v0.3.13 regression-mechanism analysis.

Reads committed v0.3.10 guard traces and v0.3.12 flattening traces.
Does not run exploration and does not choose actions.
"""
from __future__ import annotations

import os

from benchmark.algorithm_freeze import sha256_file
from benchmark.application_shape_evidence import load_json, load_jsonl, steps_only
from benchmark.fresh_transfer_analysis import normalize_url
from ghostqa.exploration.sequence import BRANCH_HORIZON

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GUARD = "ghost-structural-return-guard"
FLATTEN = "ghost-structural-nested-return-guard"
DESK_REF = os.path.join(
    "experiments", "published", "fresh-transfer-v0.3.10", "evidence", "buggy-desk")
DESK_FLAT = os.path.join(
    "experiments", "published", "nested-hub-parent-v0.3.12",
    "evidence", "regression", "buggy-desk")
DEEP_REF_METRICS = os.path.join(
    "experiments", "published", "return-cycle-guard-v0.3.9",
    "evidence", "deepbench", "metrics.json")
DEEP_FLAT = os.path.join(
    "experiments", "published", "nested-hub-parent-v0.3.12",
    "evidence", "regression", "deepbench")
DESK_MANIFEST = os.path.join("apps", "buggy-desk", "bugs.manifest.json")
FLOW_MANIFEST = os.path.join("apps", "buggy-flow", "bugs.manifest.json")
LOST_DESK = ("BUG-K3", "BUG-K6", "BUG-K9", "BUG-K10")
ANCHOR_STEP = 3
ANCHOR_REFERENCE_EID = "nav_activity"
ANCHOR_CANDIDATE_EID = "nav_back_customers"
ANCHOR_SRC = "/customer.html?id=c1"


def _abs(rel: str) -> str:
    return os.path.join(ROOT, rel.replace("/", os.sep))


def _stem(policy: str, budget: int = 120, seed: int = 1) -> str:
    return f"{policy}_b{budget}_s{seed}"


def _pair(events: list) -> list:
    """Pair each step record with the seq_after record that follows it."""
    steps = steps_only(events)
    after = {}
    for record in events:
        if record.get("kind") == "seq_after" and record.get("step") is not None:
            after[int(record["step"])] = record
    rows = []
    for step in steps:
        idx = step.get("index")
        rows.append({
            "step": step,
            "after": after.get(int(idx)) if idx is not None else None,
        })
    return rows


def _action_view(step: dict) -> dict:
    action = step.get("action") or {}
    return {
        "index": step.get("index"),
        "type": action.get("type"),
        "target_eid": action.get("target_eid"),
        "src_url": normalize_url(step.get("src_url") or ""),
        "dst_url": normalize_url(step.get("dst_url") or ""),
        "commitment_left": step.get("commitment_left"),
        "returning": bool(step.get("returning")),
        "active_branch": step.get("active_branch") or "",
        "parent_hub_cluster": step.get("parent_hub_cluster") or "",
        "last_label": step.get("last_label") or "",
    }


def _align_key(step: dict) -> tuple:
    action = step.get("action") or {}
    return (
        normalize_url(step.get("src_url") or ""),
        action.get("type") or "",
        action.get("target_eid") or "",
        normalize_url(step.get("dst_url") or ""),
    )


def _urls(events: list) -> list:
    found = set()
    for step in steps_only(events):
        for key in ("src_url", "dst_url"):
            url = normalize_url(step.get(key) or "")
            if url:
                found.add(url)
    return sorted(found)


def _seq_at(seq_events: list, step: int) -> list:
    rows = []
    for event in seq_events or []:
        if event.get("step") != step:
            continue
        rows.append({
            "event": event.get("event"),
            "outcome": event.get("outcome"),
            "branch_key": event.get("branch_key") or "",
            "sequence_instance_id": event.get("sequence_instance_id"),
            "nested_branch_key": event.get("nested_branch_key") or "",
            "outer_branch": event.get("outer_branch") or "",
            "commitment_left_before": event.get("commitment_left_before"),
        })
    return rows


def _ledger_after(record: dict | None) -> dict:
    if not record:
        return {}
    return {
        "commitment_left": record.get("commitment_left"),
        "returning": bool(record.get("returning")),
        "active_branch": record.get("active_branch") or "",
        "parent_hub_cluster": record.get("parent_hub_cluster") or "",
        "last_label": record.get("last_label") or "",
        "last_seq_event": record.get("last_seq_event"),
        "last_seq_outcome": record.get("last_seq_outcome"),
        "is_hub": record.get("is_hub"),
        "n_branch_clicks": record.get("n_branch_clicks"),
    }


def _row(metrics_path: str, policy: str, budget: int = 120) -> dict:
    data = load_json(_abs(metrics_path))
    for row in data.get("runs") or []:
        if row.get("policy") == policy and int(row.get("budget") or 0) == budget:
            return row
    return {}


def _bug_index(manifest_path: str) -> dict:
    data = load_json(_abs(manifest_path))
    return {bug["id"]: bug for bug in data.get("bugs") or []}


def _match_step(step: dict, bug: dict) -> bool:
    match = bug.get("match") or {}
    action = step.get("action") or {}
    findings = step.get("findings") or []
    if match.get("assert_id"):
        return any(item.get("assert_id") == match["assert_id"] for item in findings)
    if match.get("eid"):
        if action.get("target_eid") != match["eid"]:
            return False
        kind = bug.get("kind")
        if kind:
            return any(item.get("kind") == kind for item in findings)
        return True
    if match.get("error_contains"):
        needle = match["error_contains"]
        blob = " ".join(
            str(item.get("error") or "") for item in findings
        ) + " " + " ".join(str(err) for err in (step.get("js_errors") or []))
        return needle in blob
    if match.get("url_contains"):
        return match["url_contains"] in normalize_url(step.get("dst_url") or "")
    return False


def _first_match(events: list, bug: dict) -> dict | None:
    for step in steps_only(events):
        if _match_step(step, bug):
            view = _action_view(step)
            view["finding_assert_ids"] = sorted({
                item.get("assert_id") for item in (step.get("findings") or [])
                if item.get("assert_id")
            })
            return view
    return None


def _source(rel: str) -> dict:
    path = _abs(rel)
    return {
        "path": rel.replace("\\", "/"),
        "sha256": sha256_file(path),
        "bytes": os.path.getsize(path),
    }


def build_buggy_desk() -> dict:
    ref_events_rel = os.path.join(DESK_REF, _stem(GUARD) + ".events.jsonl")
    flat_events_rel = os.path.join(DESK_FLAT, _stem(FLATTEN) + ".events.jsonl")
    ref_seq_rel = os.path.join(DESK_REF, _stem(GUARD) + ".sequence_events.json")
    flat_seq_rel = os.path.join(DESK_FLAT, _stem(FLATTEN) + ".sequence_events.json")
    ref_events = load_jsonl(_abs(ref_events_rel))
    flat_events = load_jsonl(_abs(flat_events_rel))
    ref_seq = load_json(_abs(ref_seq_rel))
    flat_seq = load_json(_abs(flat_seq_rel))
    ref_rows = _pair(ref_events)
    flat_rows = _pair(flat_events)
    prefix = 0
    limit = min(len(ref_rows), len(flat_rows))
    while prefix < limit and _align_key(ref_rows[prefix]["step"]) == _align_key(
            flat_rows[prefix]["step"]):
        prefix += 1
    if prefix >= limit:
        raise RuntimeError("BuggyDesk traces have no action divergence")
    ref_div = ref_rows[prefix]
    flat_div = flat_rows[prefix]
    nested_index = prefix - 1
    if nested_index < 0:
        raise RuntimeError("divergence has no preceding nested action")
    ref_nested = ref_rows[nested_index]
    flat_nested = flat_rows[nested_index]
    ref_after = _ledger_after(ref_nested["after"])
    flat_after = _ledger_after(flat_nested["after"])
    ref_before_nested = _action_view(ref_nested["step"])
    flat_before_nested = _action_view(flat_nested["step"])
    ref_urls = _urls(ref_events)
    flat_urls = _urls(flat_events)
    bugs = _bug_index(DESK_MANIFEST)
    lost = []
    for bug_id in LOST_DESK:
        bug = bugs[bug_id]
        lost.append({
            "id": bug_id,
            "desc": bug.get("desc") or "",
            "kind": bug.get("kind") or "",
            "trigger_depth": bug.get("trigger_depth"),
            "prerequisites": list(bug.get("prerequisites") or []),
            "match": bug.get("match") or {},
            "min_reproduction": list(bug.get("min_reproduction") or []),
            "reference_first_match": _first_match(ref_events, bug),
            "v0_3_12_first_match": _first_match(flat_events, bug),
        })
    ref_metrics = _row(os.path.join(DESK_REF, "metrics.json"), GUARD)
    flat_metrics = _row(os.path.join(DESK_FLAT, "metrics.json"), FLATTEN)
    child_reset = (
        ref_after.get("commitment_left") == BRANCH_HORIZON - 1
        and ref_after.get("returning") is False
        and ref_after.get("active_branch") != ref_before_nested.get("active_branch")
    )
    outer_consumed = (
        flat_before_nested.get("commitment_left") is not None
        and flat_after.get("commitment_left") == flat_before_nested["commitment_left"] - 1
        and flat_after.get("active_branch") == flat_before_nested.get("active_branch")
        and flat_after.get("returning") is True
    )
    return {
        "reference_policy": GUARD,
        "candidate_policy": FLATTEN,
        "budget": 120,
        "seed": 1,
        "alignment": "normalized URL path plus action type and target_eid; signatures differ across runs",
        "first_identical_prefix_length": prefix,
        "first_divergence_step": ref_div["step"].get("index"),
        "identical_prefix": [
            _action_view(ref_rows[i]["step"]) for i in range(prefix)
        ],
        "reference_action": _action_view(ref_div["step"]),
        "v0_3_12_action": _action_view(flat_div["step"]),
        "commitment_state_at_divergence": {
            "when": "pre-action ledger on the first diverging step",
            "reference": {
                "commitment_left": ref_div["step"].get("commitment_left"),
                "returning": bool(ref_div["step"].get("returning")),
                "active_branch": ref_div["step"].get("active_branch") or "",
                "last_label": ref_div["step"].get("last_label") or "",
            },
            "v0_3_12": {
                "commitment_left": flat_div["step"].get("commitment_left"),
                "returning": bool(flat_div["step"].get("returning")),
                "active_branch": flat_div["step"].get("active_branch") or "",
                "last_label": flat_div["step"].get("last_label") or "",
            },
        },
        "nested_branch_step": ref_nested["step"].get("index"),
        "nested_branch_action": _action_view(ref_nested["step"]),
        "reference_after_nested_branch": ref_after,
        "v0_3_12_after_nested_branch": flat_after,
        "reference_sequence_events_at_nested_step": _seq_at(
            ref_seq, int(ref_nested["step"]["index"])),
        "v0_3_12_sequence_events_at_nested_step": _seq_at(
            flat_seq, int(flat_nested["step"]["index"])),
        "child_commitment_reset_vs_outer_consumption": {
            "branch_horizon": BRANCH_HORIZON,
            "historical_child_commitment_after_branch_action": BRANCH_HORIZON - 1,
            "reference_commitment_before": ref_before_nested.get("commitment_left"),
            "reference_commitment_after": ref_after.get("commitment_left"),
            "reference_active_branch_before": ref_before_nested.get("active_branch"),
            "reference_active_branch_after": ref_after.get("active_branch"),
            "reference_child_commitment_reset": child_reset,
            "v0_3_12_commitment_before": flat_before_nested.get("commitment_left"),
            "v0_3_12_commitment_after": flat_after.get("commitment_left"),
            "v0_3_12_active_branch_before": flat_before_nested.get("active_branch"),
            "v0_3_12_active_branch_after": flat_after.get("active_branch"),
            "v0_3_12_outer_commitment_consumed": outer_consumed,
            "explanation": (
                "At the nested ticket-to-customer branch click, the v0.3.9 guard "
                "ends the outer sequence and starts a child sequence. The child "
                "commitment is set to BRANCH_HORIZON and then decremented by that "
                "same branch action, so the post-action commitment is "
                "BRANCH_HORIZON - 1 and the active branch changes. The v0.3.12 "
                "candidate keeps the outer branch, decrements the outer commitment "
                "through zero, and enters returning on that same click. The next "
                "decision is therefore an outer return instead of a child-local "
                "follow-up."
            ),
        },
        "reference_only_urls": sorted(set(ref_urls) - set(flat_urls)),
        "candidate_only_urls": sorted(set(flat_urls) - set(ref_urls)),
        "shared_urls": sorted(set(ref_urls) & set(flat_urls)),
        "reference_metrics": {
            "states": ref_metrics.get("states"),
            "normalized_unique_urls": ref_metrics.get("normalized_unique_urls"),
            "confirmed_bugs": list(ref_metrics.get("confirmed_bugs") or []),
        },
        "v0_3_12_metrics": {
            "states": flat_metrics.get("states"),
            "normalized_unique_urls": flat_metrics.get("normalized_unique_urls"),
            "confirmed_bugs": list(flat_metrics.get("confirmed_bugs") or []),
            "sequence_lost_parent": flat_metrics.get("sequence_lost_parent"),
            "nested_branch_followup_events": flat_metrics.get(
                "nested_branch_followup_events"),
        },
        "lost_bug_first_steps": lost,
        "sources": [
            _source(ref_events_rel),
            _source(flat_events_rel),
            _source(ref_seq_rel),
            _source(flat_seq_rel),
            _source(os.path.join(DESK_REF, "metrics.json")),
            _source(os.path.join(DESK_FLAT, "metrics.json")),
            _source(DESK_MANIFEST),
        ],
    }


def _members_followups(seq_events: list) -> list:
    rows = []
    for event in seq_events or []:
        if event.get("event") != "nested_branch_followup":
            continue
        blob = " ".join([
            event.get("outer_branch") or "",
            event.get("nested_branch_key") or "",
            event.get("branch_key") or "",
        ])
        if "btn_members" not in blob and "btn_add_alice" not in blob:
            continue
        rows.append({
            "step": event.get("step"),
            "sequence_instance_id": event.get("sequence_instance_id"),
            "outer_branch": event.get("outer_branch") or "",
            "nested_branch_key": event.get("nested_branch_key") or "",
            "commitment_left_before": event.get("commitment_left_before"),
            "outer_parent_hub_cluster": event.get("outer_parent_hub_cluster") or "",
        })
    return rows


def build_deepbench() -> dict:
    flat_seq_rel = os.path.join(DEEP_FLAT, _stem(FLATTEN) + ".sequence_events.json")
    flat_events_rel = os.path.join(DEEP_FLAT, _stem(FLATTEN) + ".events.jsonl")
    seq_events = load_json(_abs(flat_seq_rel))
    followups = _members_followups(seq_events)
    add_starts = [
        event for event in seq_events
        if event.get("event") == "branch_start"
        and "btn_add_alice" in (event.get("branch_key") or "")
    ]
    member_starts = [
        event for event in seq_events
        if event.get("event") == "branch_start"
        and "btn_members" in (event.get("branch_key") or "")
    ]
    bugs = _bug_index(FLOW_MANIFEST)
    d12 = bugs["BUG-D12"]
    ref_row = _row(DEEP_REF_METRICS, GUARD)
    flat_row = _row(os.path.join(DEEP_FLAT, "metrics.json"), FLATTEN)
    ref_confirmed = list(ref_row.get("confirmed_bugs") or [])
    flat_confirmed = list(flat_row.get("confirmed_bugs") or [])
    return {
        "reference_policy": GUARD,
        "candidate_policy": FLATTEN,
        "budget": 120,
        "seed": 1,
        "reference_event_trace_published": False,
        "reference_evidence_note": (
            "experiments/published/return-cycle-guard-v0.3.9/evidence/deepbench "
            "contains metrics.json and does not contain the guard event trace. "
            "This section does not claim a step-aligned comparison with the guard."
        ),
        "bug_d12": {
            "id": "BUG-D12",
            "desc": d12.get("desc") or "",
            "kind": d12.get("kind") or "",
            "trigger_depth": d12.get("trigger_depth"),
            "prerequisites": list(d12.get("prerequisites") or []),
            "match": d12.get("match") or {},
            "reference_confirmed": "BUG-D12" in ref_confirmed,
            "v0_3_12_confirmed": "BUG-D12" in flat_confirmed,
        },
        "reference_confirmed": ref_confirmed,
        "v0_3_12_confirmed": flat_confirmed,
        "members_nested_followups": followups,
        "members_nested_followup_count": len(followups),
        "btn_members_branch_start_count": len(member_starts),
        "btn_add_alice_branch_start_count": len(add_starts),
        "followup_commitment_left_before": [
            row.get("commitment_left_before") for row in followups
        ],
        "followup_instance_ids": sorted({
            row.get("sequence_instance_id") for row in followups
            if row.get("sequence_instance_id")
        }),
        "mechanism_consistency": {
            "causal_proof": False,
            "consistent_with_buggy_desk_flattening": bool(followups) and not add_starts,
            "statement": (
                "The v0.3.12 candidate records btn_add_alice as nested_branch_followup "
                "while the open sequence remains the btn_members branch. Those clicks "
                "do not emit branch_start, and commitment_left_before on the outer "
                "instance decreases across the repeated follow-ups. That is the same "
                "flattening pattern as the BuggyDesk divergence: a child-local action "
                "consumes the outer commitment instead of opening a child sequence. "
                "D12's prerequisites are login, project, add-member, and remove. The "
                "members workflow is the kind of child-local multi-action path that "
                "needs its own commitment. This is mechanism consistency with the "
                "BuggyDesk regression, not a proof that flattening is the only reason "
                "D12 is absent from the candidate confirmed set."
            ),
        },
        "sources": [
            _source(flat_seq_rel),
            _source(flat_events_rel),
            _source(os.path.join(DEEP_FLAT, "metrics.json")),
            _source(DEEP_REF_METRICS),
            _source(FLOW_MANIFEST),
        ],
    }


def build_regression_analysis() -> dict:
    desk = build_buggy_desk()
    deep = build_deepbench()
    problems = anchor_problems(desk)
    if problems:
        raise RuntimeError("regression anchor failed: " + "; ".join(problems))
    return {
        "round": "v0.3.13",
        "kind": "regression-mechanism-analysis",
        "derived_by": "benchmark.nested_stack_regression.build_regression_analysis",
        "status": "before candidate implementation",
        "v0_3_12_outcome_preserved": "C",
        "v0_3_12_outcome_meaning": "harmful/regression",
        "question": (
            "Can nested branch starts keep normal child-sequence exploration "
            "while the outer sequence is suspended instead of discarded or flattened?"
        ),
        "mechanism_hypothesis": (
            "Flattening a real child branch into the outer commitment changes "
            "child-local scheduling and causes premature outer return."
        ),
        "not": [
            "proof that nested preservation is generally harmful",
            "a fresh-generalization claim",
            "a product-default change"
        ],
        "buggy_desk": desk,
        "deepbench": deep,
    }


def anchor_problems(desk: dict) -> list:
    problems = []
    if desk.get("first_divergence_step") != ANCHOR_STEP:
        problems.append(
            f"divergence step {desk.get('first_divergence_step')} != {ANCHOR_STEP}")
    if desk.get("first_identical_prefix_length") != ANCHOR_STEP:
        problems.append("prefix length does not stop at the divergence step")
    ref = desk.get("reference_action") or {}
    cand = desk.get("v0_3_12_action") or {}
    if ref.get("target_eid") != ANCHOR_REFERENCE_EID:
        problems.append(f"reference eid {ref.get('target_eid')}")
    if cand.get("target_eid") != ANCHOR_CANDIDATE_EID:
        problems.append(f"candidate eid {cand.get('target_eid')}")
    if ref.get("src_url") != ANCHOR_SRC or cand.get("src_url") != ANCHOR_SRC:
        problems.append("divergence source is not customer?id=c1")
    mech = desk.get("child_commitment_reset_vs_outer_consumption") or {}
    if not mech.get("reference_child_commitment_reset"):
        problems.append("reference did not reset child commitment")
    if not mech.get("v0_3_12_outer_commitment_consumed"):
        problems.append("v0.3.12 did not consume outer commitment")
    ref_events = desk.get("reference_sequence_events_at_nested_step") or []
    flat_events = desk.get("v0_3_12_sequence_events_at_nested_step") or []
    ref_names = {row.get("event") for row in ref_events}
    flat_names = {row.get("event") for row in flat_events}
    if "branch_start" not in ref_names or "lost_parent" not in {
            row.get("outcome") for row in ref_events}:
        problems.append("reference nested step is not a historical child start")
    if "nested_branch_followup" not in flat_names or "branch_start" in flat_names:
        problems.append("v0.3.12 nested step is not a flatten-without-branch-start")
    return problems


def main() -> int:
    from benchmark.application_shape_evidence import canonical_json_bytes
    obj = build_regression_analysis()
    text = canonical_json_bytes(obj).decode("utf-8")
    dest = _abs(os.path.join(
        "experiments", "validation", "v0.3.13", "regression-analysis.json"))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    desk = obj["buggy_desk"]
    print(
        f"prefix={desk['first_identical_prefix_length']} "
        f"divergence={desk['first_divergence_step']} "
        f"ref={desk['reference_action']['target_eid']} "
        f"flat={desk['v0_3_12_action']['target_eid']}")
    print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
