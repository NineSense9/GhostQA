"""Code-derived v0.3.16 local-frontier audit for the v0.3.17 repair round.

Reads committed reentry-frontier and fresh-handoff evidence. Does not run a
browser and does not choose exploration actions.
"""
from __future__ import annotations

import os

from benchmark.algorithm_freeze import sha256_file
from benchmark.application_shape_evidence import (
    canonical_json_bytes, load_json, load_jsonl, sha256_bytes, steps_only,
)
from benchmark.fresh_transfer_analysis import normalize_url

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REENTRY = os.path.join("experiments", "published", "reentry-frontier-v0.3.16")
FRESH = os.path.join("experiments", "published", "fresh-handoff-v0.3.15")
GUARD = "ghost-structural-return-guard"
REENTRY_POLICY = "ghost-structural-reentry-frontier-guard"
LAB = "buggy-lab"


def _abs(rel: str) -> str:
    return os.path.join(ROOT, rel.replace("/", os.sep))


def _stem(policy: str, budget: int = 120, seed: int = 1) -> str:
    return f"{policy}_b{budget}_s{seed}"


def _evidence(root: str, app: str, policy: str, kind: str, budget: int = 120) -> str:
    return os.path.join(root, "evidence", app, _stem(policy, budget) + "." + kind)


def _eid(key: str) -> str:
    text = str(key or "")
    if ":click:" in text:
        return text.split(":click:", 1)[1]
    if ":button:" in text:
        return text.split(":button:", 1)[1]
    return text


def _load_seq() -> list:
    return load_json(_abs(_evidence(
        REENTRY, LAB, REENTRY_POLICY, "sequence_events.json")))


def _load_steps(root: str, policy: str) -> list:
    return steps_only(load_jsonl(_abs(_evidence(root, LAB, policy, "events.jsonl"))))


def _row(root: str, policy: str, budget: int = 120) -> dict:
    metrics = load_json(_abs(os.path.join(root, "evidence", LAB, "metrics.json")))
    for row in metrics.get("runs") or []:
        if row.get("policy") == policy and int(row.get("budget") or 0) == budget:
            return row
    return {}


def _manifest() -> dict:
    data = load_json(_abs(os.path.join("apps", LAB, "bugs.manifest.json")))
    return {bug["id"]: bug for bug in data.get("bugs") or []}


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


def _step_view(step: dict) -> dict:
    action = step.get("action") or {}
    return {
        "index": step.get("index"),
        "target_eid": action.get("target_eid"),
        "type": action.get("type"),
        "dst_url": normalize_url(step.get("dst_url") or ""),
        "src_url": normalize_url(step.get("src_url") or ""),
        "finding_assert_ids": sorted({
            item.get("assert_id")
            for item in (step.get("findings") or [])
            if item.get("assert_id")
        }),
    }


def _first_hit(steps: list, bug: dict) -> dict | None:
    for step in steps:
        if _match_step(step, bug):
            return _step_view(step)
    return None


def _window(steps: list, index: int, before: int = 12) -> list:
    rows = []
    for step in steps:
        current = step.get("index")
        if isinstance(current, int) and index - before <= current <= index:
            rows.append(_step_view(step))
    return rows


def _events(seq: list, name: str) -> list:
    return [event for event in seq if event.get("event") == name]


def _grant_with(seq: list, eids: set) -> dict:
    for event in _events(seq, "local_frontier_lease_granted"):
        got = {_eid(key) for key in (event.get("frontier_keys") or [])}
        if eids <= got:
            return event
    return {}


def _actions_between(seq: list, start: int, end: int, cluster: str) -> list:
    rows = []
    for event in _events(seq, "local_frontier_lease_action"):
        step = event.get("step")
        if not isinstance(step, int) or not (start < step <= end):
            continue
        if cluster and (event.get("hub_cluster") or event.get("cluster_id")) != cluster:
            continue
        rows.append({
            "step": step,
            "chosen_branch_key": event.get("chosen_branch_key") or "",
            "eid": _eid(event.get("chosen_branch_key") or ""),
            "frontier_keys": list(event.get("frontier_keys") or []),
        })
    return rows


def _escape_after(seq: list, step: int) -> dict:
    for event in _events(seq, "return_cycle_escape"):
        if isinstance(event.get("step"), int) and event["step"] > step:
            return event
    return {}


def _terminal_at(seq: list, step: int, outcome: str) -> dict:
    for event in seq:
        if event.get("event") != "sequence_terminal":
            continue
        if event.get("step") == step and event.get("outcome") == outcome:
            return event
    return {}


def _hub_record(seq: list, eids: set) -> dict:
    grant = _grant_with(seq, eids)
    if not grant:
        return {"found": False}
    cluster = grant.get("hub_cluster") or grant.get("cluster_id") or ""
    escape = _escape_after(seq, int(grant.get("step") or 0))
    escape_step = escape.get("step")
    actions = _actions_between(
        seq, int(grant.get("step") or 0),
        int(escape_step if escape_step is not None else 10 ** 9),
        cluster)
    remaining = list(grant.get("frontier_keys") or [])
    chosen = {row["chosen_branch_key"] for row in actions}
    remaining = [key for key in remaining if key not in chosen]
    abandoned = {}
    if escape_step is not None:
        abandoned = _terminal_at(seq, escape_step, "horizon_handoff_abandoned")
    return {
        "found": True,
        "witness_step": grant.get("step"),
        "hub_cluster": cluster,
        "hub_sig": grant.get("hub_sig") or grant.get("exact_sig") or "",
        "frontier_keys": list(grant.get("frontier_keys") or []),
        "frontier_eids": [_eid(key) for key in (grant.get("frontier_keys") or [])],
        "frontier_count": grant.get("frontier_count"),
        "suspended_outer_id": grant.get("outer_sequence_instance_id"),
        "suspended_branch": grant.get("active_branch") or "",
        "lease_actions_before_escape": actions,
        "escape_step": escape_step,
        "escape_branch": escape.get("active_branch") or escape.get("branch_key") or "",
        "outer_abandoned": bool(abandoned),
        "outer_abandon_outcome": abandoned.get("outcome") or "",
        "outer_abandon_reason": abandoned.get("reason") or "",
        "remaining_frontier_keys": remaining,
        "remaining_frontier_eids": [_eid(key) for key in remaining],
    }


def _guard_bug(steps: list, bugs: dict, bug_id: str, causality: str) -> dict:
    bug = bugs[bug_id]
    hit = _first_hit(steps, bug)
    window = [] if hit is None else _window(steps, int(hit["index"]))
    eids = [row.get("target_eid") for row in window]
    return {
        "bug_id": bug_id,
        "match": bug.get("match") or {},
        "first_hit": hit,
        "window_eids": eids,
        "causality": causality,
    }


def build_local_frontier_analysis() -> dict:
    seq = _load_seq()
    guard_steps = _load_steps(FRESH, GUARD)
    reentry_steps = _load_steps(REENTRY, REENTRY_POLICY)
    bugs = _manifest()
    run_hub = _hub_record(seq, {"btn_cool", "btn_staff_note", "open_result_from_run", "open_sample_s2"})
    result_hub = _hub_record(seq, {"btn_close", "btn_reopen", "open_notebook", "open_run_again"})
    guard = {
        "BUG-L10": _guard_bug(
            guard_steps, bugs, "BUG-L10",
            "direct local-action ordering hypothesis: btn_staff_note occurs before "
            "open_result_from_run on the Guard chain that first confirms lab_note_visibility"),
        "BUG-L9": _guard_bug(
            guard_steps, bugs, "BUG-L9",
            "direct local-action ordering hypothesis: btn_close occurs before "
            "btn_reopen on the Guard chain that first confirms lab_reopen_clears"),
        "BUG-L8": _guard_bug(
            guard_steps, bugs, "BUG-L8",
            "Guard first confirms lab_heat_matches on btn_cool. v0.3.16 later "
            "executes that button on another trajectory and confirms BUG-L8"),
        "BUG-L1": _guard_bug(
            guard_steps, bugs, "BUG-L1",
            "downstream trajectory outcome only. The first hit is navigation to "
            "/samples.html. Local button drain is not claimed as its cause"),
    }
    read_paths = [
        _evidence(REENTRY, LAB, REENTRY_POLICY, "sequence_events.json"),
        _evidence(REENTRY, LAB, REENTRY_POLICY, "events.jsonl"),
        os.path.join(REENTRY, "evidence", LAB, "metrics.json"),
        _evidence(FRESH, LAB, GUARD, "events.jsonl"),
        os.path.join(FRESH, "evidence", LAB, "metrics.json"),
        os.path.join("apps", LAB, "bugs.manifest.json"),
    ]
    reentry_row = _row(REENTRY, REENTRY_POLICY)
    guard_row = _row(FRESH, GUARD)
    report = {
        "round": "v0.3.17",
        "source_round": "v0.3.16",
        "source_publication": REENTRY.replace("\\", "/"),
        "guard_publication": FRESH.replace("\\", "/"),
        "candidate_policy": REENTRY_POLICY,
        "guard_policy": GUARD,
        "budget": 120,
        "seed": 1,
        "derived_from_committed_evidence": True,
        "hand_typed_counts": False,
        "browser_rerun": False,
        "run_hub": run_hub,
        "result_hub": result_hub,
        "guard_bugs": guard,
        "l1_causal_claim": False,
        "v0316_lab_confirmed": sorted(reentry_row.get("confirmed_bugs") or []),
        "guard_lab_confirmed": sorted(guard_row.get("confirmed_bugs") or []),
        "v0316_recovered_vs_guard": sorted(
            set(reentry_row.get("confirmed_bugs") or [])
            & {"BUG-L1", "BUG-L8", "BUG-L9", "BUG-L10"}),
        "v0316_still_lost_vs_guard": sorted(
            set(guard_row.get("confirmed_bugs") or [])
            - set(reentry_row.get("confirmed_bugs") or [])),
        "run_child_does_not_return_to_run_before_escape": _child_leaves_run(
            reentry_steps, 13, 20),
        "evidence_files": [
            {"path": rel.replace("\\", "/"), "sha256": sha256_file(_abs(rel))}
            for rel in read_paths
        ],
    }
    return report


def _child_leaves_run(steps: list, start: int, end: int) -> dict:
    rows = []
    back_on_run = False
    for step in steps:
        index = step.get("index")
        if not isinstance(index, int) or not (start <= index <= end):
            continue
        view = _step_view(step)
        rows.append({
            "index": view["index"],
            "target_eid": view["target_eid"],
            "dst_url": view["dst_url"],
        })
        if index > start and view["dst_url"].startswith("/run.html"):
            back_on_run = True
    return {
        "start_step": start,
        "end_step": end,
        "path": rows,
        "returns_to_run_html": back_on_run,
    }


def analysis_bytes(report: dict | None = None) -> bytes:
    return canonical_json_bytes(
        report if report is not None else build_local_frontier_analysis())


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        default=os.path.join(
            "experiments", "validation", "v0.3.17",
            "v0316-local-frontier-analysis.json"),
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
