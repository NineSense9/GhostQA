"""Code-derived v0.3.17 result-hub return audit for the v0.3.18 repair round.

Reads committed local-action-drain and fresh-handoff evidence. Does not run a
browser and does not choose exploration actions.
"""
from __future__ import annotations

import os

from benchmark.algorithm_freeze import sha256_file
from benchmark.application_shape_evidence import (
    canonical_json_bytes, load_json, load_jsonl, sha256_bytes, steps_only,
)
from benchmark.fresh_transfer_analysis import normalize_url
from benchmark.local_action_drain_audit import _first_hit, _manifest, _window

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREVIOUS = os.path.join("experiments", "published", "local-action-drain-v0.3.17")
FRESH = os.path.join("experiments", "published", "fresh-handoff-v0.3.15")
GUARD = "ghost-structural-return-guard"
PREVIOUS_POLICY = "ghost-structural-local-action-drain-guard"
LAB = "buggy-lab"
GUARD_REFERENCE = ("BUG-L1", "BUG-L2", "BUG-L8", "BUG-L9", "BUG-L10")


def _abs(rel: str) -> str:
    return os.path.join(ROOT, rel.replace("/", os.sep))


def _stem(policy: str, budget: int = 120, seed: int = 1) -> str:
    return f"{policy}_b{budget}_s{seed}"


def _evidence(root: str, policy: str, kind: str, budget: int = 120) -> str:
    return os.path.join(root, "evidence", LAB, _stem(policy, budget) + "." + kind)


def _row(root: str, policy: str, budget: int = 120) -> dict:
    metrics = load_json(_abs(os.path.join(root, "evidence", LAB, "metrics.json")))
    for row in metrics.get("runs") or []:
        if row.get("policy") == policy and int(row.get("budget") or 0) == budget:
            return row
    return {}


def _browser(steps: list, index: int) -> dict:
    for step in steps:
        if step.get("index") != index:
            continue
        action = step.get("action") or {}
        return {
            "index": index,
            "target_eid": action.get("target_eid") or "",
            "type": action.get("type") or "",
            "src_url": normalize_url(step.get("src_url") or ""),
            "dst_url": normalize_url(step.get("dst_url") or ""),
            "finding_assert_ids": sorted({
                item.get("assert_id")
                for item in (step.get("findings") or [])
                if item.get("assert_id")
            }),
        }
    return {}


def _events_at(seq: list, step: int, name: str, outcome: str = "") -> list:
    rows = []
    for event in seq:
        if event.get("step") != step or event.get("event") != name:
            continue
        if outcome and event.get("outcome") != outcome:
            continue
        rows.append(event)
    return rows


def _names_at(seq: list, step: int) -> list:
    return sorted({
        event.get("event") or ""
        for event in seq
        if event.get("step") == step and event.get("event")
    })


def _transition(seq: list, steps: list, terminal_step: int, next_step: int) -> dict:
    terminals = _events_at(seq, terminal_step, "sequence_terminal", "finding")
    returns = _events_at(seq, next_step, "return_attempt")
    result_cluster = "" if not returns else (returns[0].get("cluster_id") or "")
    drains_on_boundary = [
        event for event in seq
        if event.get("event") == "local_action_drain_started"
        and event.get("step") in (terminal_step, next_step)
    ]
    drains_on_result = [
        event for event in seq
        if event.get("event") == "local_action_drain_started"
        and result_cluster
        and (event.get("hub_cluster") or event.get("cluster_id") or "") == result_cluster
    ]
    return {
        "terminal_step": terminal_step,
        "next_step": next_step,
        "finding_terminal": bool(terminals),
        "finding_outcome": "" if not terminals else (terminals[0].get("outcome") or ""),
        "finding_branch": "" if not terminals else (terminals[0].get("branch_key") or ""),
        "same_step_events": _names_at(seq, terminal_step),
        "next_is_return_attempt": bool(returns),
        "return_attempt_cluster": result_cluster,
        "drain_started_on_terminal_or_next_step": bool(drains_on_boundary),
        "drain_started_on_result_cluster": bool(drains_on_result),
        "browser": _browser(steps, terminal_step),
        "next_browser": _browser(steps, next_step),
    }


def _guard_l9(steps: list) -> dict:
    bugs = _manifest()
    bug = bugs["BUG-L9"]
    hit = _first_hit(steps, bug)
    window = [] if hit is None else _window(steps, int(hit["index"]))
    eids = [row.get("target_eid") or "" for row in window]
    close_at = eids.index("btn_close") if "btn_close" in eids else -1
    reopen_at = eids.index("btn_reopen") if "btn_reopen" in eids else -1
    return {
        "bug_id": "BUG-L9",
        "assert_id": (bug.get("match") or {}).get("assert_id") or "",
        "first_hit": hit,
        "window_eids": eids,
        "btn_close_before_btn_reopen": close_at >= 0 and reopen_at >= 0 and close_at < reopen_at,
    }


def build_return_entry_analysis() -> dict:
    seq = load_json(_abs(_evidence(PREVIOUS, PREVIOUS_POLICY, "sequence_events.json")))
    steps = steps_only(load_jsonl(_abs(_evidence(PREVIOUS, PREVIOUS_POLICY, "events.jsonl"))))
    guard_steps = steps_only(load_jsonl(_abs(_evidence(FRESH, GUARD, "events.jsonl"))))
    previous_row = _row(PREVIOUS, PREVIOUS_POLICY)
    guard_row = _row(FRESH, GUARD)
    previous_confirmed = sorted(previous_row.get("confirmed_bugs") or [])
    guard_confirmed = sorted(guard_row.get("confirmed_bugs") or [])
    reference = list(GUARD_REFERENCE)
    lost_vs_reference = sorted(set(reference) - set(previous_confirmed))
    lost_vs_guard = sorted(set(guard_confirmed) - set(previous_confirmed))
    step15 = _transition(seq, steps, 15, 16)
    step21 = _transition(seq, steps, 21, 22)
    guard_l9 = _guard_l9(guard_steps)
    read_paths = [
        _evidence(PREVIOUS, PREVIOUS_POLICY, "sequence_events.json"),
        _evidence(PREVIOUS, PREVIOUS_POLICY, "events.jsonl"),
        os.path.join(PREVIOUS, "evidence", LAB, "metrics.json"),
        _evidence(FRESH, GUARD, "events.jsonl"),
        os.path.join(FRESH, "evidence", LAB, "metrics.json"),
        os.path.join("apps", LAB, "bugs.manifest.json"),
    ]
    return {
        "round": "v0.3.18",
        "source_round": "v0.3.17",
        "source_publication": PREVIOUS.replace("\\", "/"),
        "guard_publication": FRESH.replace("\\", "/"),
        "candidate_policy": PREVIOUS_POLICY,
        "guard_policy": GUARD,
        "budget": 120,
        "seed": 1,
        "derived_from_committed_evidence": True,
        "hand_typed_counts": False,
        "browser_rerun": False,
        "step15_result_return": step15,
        "step21_result_return": step21,
        "result_drain_missing": (
            not step15["drain_started_on_terminal_or_next_step"]
            and not step15["drain_started_on_result_cluster"]
            and not step21["drain_started_on_terminal_or_next_step"]
            and not step21["drain_started_on_result_cluster"]
        ),
        "guard_l9": guard_l9,
        "guard_reference": reference,
        "v0317_lab_confirmed": previous_confirmed,
        "guard_lab_confirmed": guard_confirmed,
        "v0317_lost_vs_guard_reference": lost_vs_reference,
        "v0317_lost_vs_guard_confirmed": lost_vs_guard,
        "v0317_only_guard_loss": lost_vs_reference,
        "evidence_files": [
            {"path": rel.replace("\\", "/"), "sha256": sha256_file(_abs(rel))}
            for rel in read_paths
        ],
    }


def analysis_bytes(report: dict | None = None) -> bytes:
    return canonical_json_bytes(
        report if report is not None else build_return_entry_analysis())


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        default=os.path.join(
            "experiments", "validation", "v0.3.18",
            "v0317-return-entry-analysis.json"),
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
