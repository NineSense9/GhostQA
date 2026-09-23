"""Code-derived v0.3.15 failure audit for the v0.3.16 repair round.

Reads committed fresh-handoff evidence. Does not run a browser and does not
choose exploration actions.
"""
from __future__ import annotations

import os

from benchmark.algorithm_freeze import sha256_file
from benchmark.application_shape_evidence import canonical_json_bytes, load_json, load_jsonl, sha256_bytes, steps_only
from benchmark.fresh_transfer_analysis import normalize_url

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLISHED = os.path.join("experiments", "published", "fresh-handoff-v0.3.15")
GUARD = "ghost-structural-return-guard"
HAND = "ghost-structural-horizon-handoff-guard"
CENSUS_APPS = ("buggy-forum", "buggy-billing", "buggy-lab", "buggy-directory")
LAB_LOST = ("BUG-L1", "BUG-L8", "BUG-L9", "BUG-L10")
# Direct first-divergence support is limited to the run-hub frontier bugs.
DIRECT_FRONTIER_BUGS = ("BUG-L8", "BUG-L10")
TRAJECTORY_BUGS = ("BUG-L1", "BUG-L9")


def _abs(rel: str) -> str:
    return os.path.join(ROOT, rel.replace("/", os.sep))


def _stem(policy: str, budget: int = 120, seed: int = 1) -> str:
    return f"{policy}_b{budget}_s{seed}"


def _evidence(app: str, policy: str, kind: str, budget: int = 120) -> str:
    return os.path.join(PUBLISHED, "evidence", app, _stem(policy, budget) + "." + kind)


def _load_events(app: str, policy: str, budget: int = 120) -> list:
    return load_jsonl(_abs(_evidence(app, policy, "events.jsonl", budget)))


def _load_seq(app: str, policy: str, budget: int = 120) -> list:
    return load_json(_abs(_evidence(app, policy, "sequence_events.json", budget)))


def _load_metrics(app: str) -> dict:
    return load_json(_abs(os.path.join(PUBLISHED, "evidence", app, "metrics.json")))


def _row(metrics: dict, policy: str, budget: int = 120) -> dict:
    for row in metrics.get("runs") or []:
        if row.get("policy") == policy and int(row.get("budget") or 0) == budget:
            return row
    return {}


def _manifest(app: str) -> dict:
    data = load_json(_abs(os.path.join("apps", app, "bugs.manifest.json")))
    return {bug["id"]: bug for bug in data.get("bugs") or []}


def _step_view(step: dict) -> dict:
    action = step.get("action") or {}
    return {
        "index": step.get("index"),
        "type": action.get("type"),
        "target_eid": action.get("target_eid"),
        "src_url": normalize_url(step.get("src_url") or ""),
        "dst_url": normalize_url(step.get("dst_url") or ""),
        "src_sig": step.get("src_sig") or "",
        "dst_sig": step.get("dst_sig") or "",
        "src_cluster": step.get("src_cluster") or "",
        "dst_cluster": step.get("dst_cluster") or "",
        "commitment_left": step.get("commitment_left"),
        "returning": bool(step.get("returning")),
        "active_branch": step.get("active_branch") or "",
        "parent_hub_cluster": step.get("parent_hub_cluster") or "",
        "last_label": step.get("last_label") or "",
        "finding_assert_ids": sorted({
            item.get("assert_id")
            for item in (step.get("findings") or [])
            if item.get("assert_id")
        }),
    }


def _match_step(step: dict, bug: dict) -> bool:
    match = bug.get("match") or {}
    action = step.get("action") or {}
    findings = step.get("findings") or []
    if match.get("assert_id"):
        return any(item.get("assert_id") == match["assert_id"] for item in findings)
    if match.get("error_contains"):
        needle = str(match["error_contains"])
        blob = " ".join(str(item.get("error") or "") for item in findings)
        blob += " " + " ".join(str(err) for err in (step.get("js_errors") or []))
        return needle in blob
    if match.get("url_contains"):
        return str(match["url_contains"]) in normalize_url(step.get("dst_url") or "")
    if match.get("eid"):
        return action.get("target_eid") == match["eid"]
    return False


def _first_hit(events: list, bug: dict) -> dict | None:
    for step in steps_only(events):
        if _match_step(step, bug):
            return _step_view(step)
    return None


def _handoff_record(event: dict, steps: list) -> dict:
    current_sig = event.get("exact_sig") or ""
    current_cluster = event.get("cluster_id") or ""
    parent_sig = event.get("suspended_parent_hub_sig") or ""
    parent_cluster = event.get("suspended_parent_hub_cluster") or ""
    step_index = event.get("step")
    preceding = None
    current = None
    by_index = {step.get("index"): step for step in steps}
    if step_index in by_index:
        current = _step_view(by_index[step_index])
    if isinstance(step_index, int) and (step_index - 1) in by_index:
        preceding = _step_view(by_index[step_index - 1])
    return {
        "step": step_index,
        "current_exact_sig": current_sig,
        "current_cluster": current_cluster,
        "suspended_sequence_instance_id": event.get("suspended_sequence_instance_id"),
        "suspended_branch": event.get("suspended_branch") or "",
        "suspended_parent_hub_sig": parent_sig,
        "suspended_parent_hub_cluster": parent_cluster,
        "child_sequence_instance_id": event.get("child_sequence_instance_id"),
        "child_branch": event.get("child_branch") or "",
        "child_parent_sig": event.get("child_parent_sig") or "",
        "child_parent_cluster": event.get("child_parent_cluster") or "",
        "outer_commitment_before": event.get("outer_commitment_before"),
        "same_parent_exact": bool(current_sig) and current_sig == parent_sig,
        "same_parent_cluster": bool(current_cluster) and current_cluster == parent_cluster,
        "handoff_action": current,
        "preceding_action": preceding,
        "preceding_lands_on_suspended_parent_exact": bool(
            preceding and preceding.get("dst_sig") == parent_sig
        ),
        "preceding_lands_on_suspended_parent_cluster": bool(
            preceding and parent_cluster and preceding.get("dst_cluster") == parent_cluster
        ),
    }


def handoff_census(app: str, budget: int = 120) -> dict:
    seq = _load_seq(app, HAND, budget)
    steps = steps_only(_load_events(app, HAND, budget))
    handoffs = [_handoff_record(event, steps) for event in seq if event.get("event") == "horizon_handoff_started"]
    return {
        "app": app,
        "budget": budget,
        "policy": HAND,
        "total_handoffs": len(handoffs),
        "same_parent_exact": sum(1 for row in handoffs if row["same_parent_exact"]),
        "same_parent_cluster": sum(1 for row in handoffs if row["same_parent_cluster"]),
        "handoffs": handoffs,
    }


def _path(events: list, start: int, end: int) -> list:
    rows = []
    for step in steps_only(events):
        index = step.get("index")
        if isinstance(index, int) and start <= index <= end:
            rows.append(_step_view(step))
    return rows


def _first_divergence(guard_events: list, hand_events: list) -> dict:
    guard_steps = steps_only(guard_events)
    hand_steps = steps_only(hand_events)
    limit = min(len(guard_steps), len(hand_steps))
    split = None
    for index in range(limit):
        left = _step_view(guard_steps[index])
        right = _step_view(hand_steps[index])
        if (left["target_eid"], left["type"], left["dst_url"]) != (
            right["target_eid"], right["type"], right["dst_url"],
        ):
            split = index
            break
    if split is None and len(guard_steps) != len(hand_steps):
        split = limit
    return {
        "first_divergent_step": split,
        "guard": None if split is None or split >= len(guard_steps) else _step_view(guard_steps[split]),
        "horizon": None if split is None or split >= len(hand_steps) else _step_view(hand_steps[split]),
        "guard_path_around": _path(guard_events, max(0, (split or 0) - 5), (split or 0) + 3),
        "horizon_path_around": _path(hand_events, max(0, (split or 0) - 5), (split or 0) + 3),
    }


def _confirmed(app: str, policy: str, budget: int = 120) -> list:
    return sorted(_row(_load_metrics(app), policy, budget).get("confirmed_bugs") or [])


def lab_lost_bugs() -> dict:
    bugs = _manifest("buggy-lab")
    guard_events = _load_events("buggy-lab", GUARD)
    hand_events = _load_events("buggy-lab", HAND)
    rows = {}
    for bug_id in LAB_LOST:
        bug = bugs[bug_id]
        guard_hit = _first_hit(guard_events, bug)
        hand_hit = _first_hit(hand_events, bug)
        if bug_id in DIRECT_FRONTIER_BUGS:
            causality = (
                "strong mechanism evidence: the first action divergence leaves "
                "the local run/result frontier that later contains this bug"
            )
        else:
            causality = (
                "consistent with the broader downstream trajectory shift; "
                "direct causal attribution is not established by the first divergence alone"
            )
        rows[bug_id] = {
            "assert_or_match": bug.get("match") or {},
            "guard_first_hit": guard_hit,
            "horizon_first_hit": hand_hit,
            "horizon_never_hits": hand_hit is None,
            "causality": causality,
        }
    return rows


def build_failure_analysis() -> dict:
    census = {app: handoff_census(app) for app in CENSUS_APPS}
    directory = census["buggy-directory"]
    guard_lab = _load_events("buggy-lab", GUARD)
    hand_lab = _load_events("buggy-lab", HAND)
    divergence = _first_divergence(guard_lab, hand_lab)
    lost = lab_lost_bugs()
    confirmed = {
        app: {
            "guard": _confirmed(app, GUARD),
            "horizon": _confirmed(app, HAND),
            "lost_vs_guard": sorted(set(_confirmed(app, GUARD)) - set(_confirmed(app, HAND))),
        }
        for app in CENSUS_APPS
    }
    read_paths = []
    for app in CENSUS_APPS:
        read_paths.append(_evidence(app, HAND, "events.jsonl"))
        read_paths.append(_evidence(app, HAND, "sequence_events.json"))
        read_paths.append(os.path.join(PUBLISHED, "evidence", app, "metrics.json"))
    read_paths.append(_evidence("buggy-lab", GUARD, "events.jsonl"))
    read_paths.append(os.path.join("apps", "buggy-lab", "bugs.manifest.json"))
    sources = [
        {"path": rel.replace("\\", "/"), "sha256": sha256_file(_abs(rel))}
        for rel in read_paths
    ]
    report = {
        "round": "v0.3.16",
        "source_round": "v0.3.15",
        "source_publication": PUBLISHED.replace("\\", "/"),
        "candidate_policy": HAND,
        "guard_policy": GUARD,
        "budget": 120,
        "seed": 1,
        "derived_from_committed_evidence": True,
        "hand_typed_counts": False,
        "directory": {
            "handoff_count": directory["total_handoffs"],
            "same_parent_exact_handoff_count": directory["same_parent_exact"],
            "same_parent_cluster_handoff_count": directory["same_parent_cluster"],
            "events": directory["handoffs"],
            "interpretation": (
                "Both handoffs fire while the current hub is the active outer "
                "sequence's own parent. The preceding action has already landed "
                "on that parent. The following branch is a sibling, not a nested child."
            ),
        },
        "same_parent_census": {
            app: {
                "total_handoffs": census[app]["total_handoffs"],
                "same_parent_exact": census[app]["same_parent_exact"],
                "same_parent_cluster": census[app]["same_parent_cluster"],
            }
            for app in CENSUS_APPS
        },
        "lab_first_divergence": divergence,
        "lab_lost_bugs": lost,
        "confirmed_at_120": confirmed,
        "causality_limit": (
            "BUG-L8 and BUG-L10 sit on the local run/result frontier skipped by "
            "the first divergence. BUG-L1 and BUG-L9 are downstream trajectory "
            "outcomes; the first divergence alone does not establish their cause."
        ),
        "evidence_files": sources,
    }
    return report


def analysis_bytes(report: dict | None = None) -> bytes:
    return canonical_json_bytes(report if report is not None else build_failure_analysis())


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        default=os.path.join("experiments", "validation", "v0.3.16", "v0315-failure-analysis.json"),
    )
    args = parser.parse_args(argv)
    payload = analysis_bytes()
    path = _abs(args.write) if not os.path.isabs(args.write) else args.write
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(payload)
    print(sha256_bytes(payload))
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
