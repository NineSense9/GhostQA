"""Code-derived v0.3.23 episode-drain audit for the v0.3.24 protocol.

Reads the committed v0.3.23 publication and explorer/drain source. Does not
choose actions and does not import a v0.3.24 candidate.
"""
from __future__ import annotations

import json
import os

from benchmark.algorithm_freeze import sha256_file

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUB = os.path.join(ROOT, "experiments", "published", "residual-frontier-debt-v0.3.23")
VALIDATION = os.path.join(ROOT, "experiments", "validation", "v0.3.24")
EXPLORER = os.path.join(ROOT, "ghostqa", "exploration", "explorer.py")
DRAIN = os.path.join(ROOT, "ghostqa", "exploration", "local_action_drain_guard.py")
RETURN_DRAIN = os.path.join(ROOT, "ghostqa", "exploration", "return_entry_drain_guard.py")
DEBT = os.path.join(ROOT, "ghostqa", "exploration", "residual_frontier_debt_guard.py")
DEBT_FREEZE = os.path.join(
    ROOT, "experiments", "frozen", "ghost-residual-frontier-debt-v0.3.23", "freeze.json")
STEM = "ghost-structural-residual-frontier-debt-guard_b120_s1"
DIAGNOSED = ("buggy-campus", "buggy-studio", "buggy-warehouse", "buggy-booking")
DEEP = "buggy-flow"
TEMPLATE_NUMBERS = (5, 8, 9)
STAFF_EIDS = ("btn_variant", "btn_staff_note")


def _load(path: str):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write(path: str, payload) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _jsonl(path: str) -> list:
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _evidence(app: str) -> str:
    return "deepbench" if app == DEEP else app


def _seq_path(app: str) -> str:
    return os.path.join(PUB, "evidence", _evidence(app), STEM + ".sequence_events.json")


def _events_path(app: str) -> str:
    return os.path.join(PUB, "evidence", _evidence(app), STEM + ".events.jsonl")


def _metrics_row(app: str) -> dict:
    path = os.path.join(PUB, "evidence", _evidence(app), "metrics.json")
    for row in _load(path).get("runs") or []:
        if int(row.get("budget") or 0) == 120 and int(row.get("seed") or 0) == 1:
            return row
    raise SystemExit(f"missing b120 metrics for {app}")


def _template_number(bug_id: str):
    suffix = str(bug_id or "").rsplit("-", 1)[-1]
    digits = ""
    for char in reversed(suffix):
        if char.isdigit():
            digits = char + digits
        else:
            break
    return int(digits) if digits else None


def _template_ids(app: str) -> list:
    manifest = _load(os.path.join(ROOT, "apps", app, "bugs.manifest.json"))
    found = []
    for bug in manifest.get("bugs") or []:
        if _template_number(bug.get("id") or "") in TEMPLATE_NUMBERS:
            found.append(bug["id"])
    return found


def _template_status(app: str, confirmed) -> dict:
    confirmed = set(confirmed or [])
    ids = _template_ids(app)
    missing = [bug_id for bug_id in ids if bug_id not in confirmed]
    return {
        "ids": ids,
        "retained": [bug_id for bug_id in ids if bug_id in confirmed],
        "missing": missing,
        "five_and_eight_retained": all(
            bug_id in confirmed
            for bug_id in ids
            if _template_number(bug_id) in (5, 8)
        ),
        "nine_missing": any(
            bug_id not in confirmed
            for bug_id in ids
            if _template_number(bug_id) == 9
        ),
        "nine_retained": all(
            bug_id in confirmed
            for bug_id in ids
            if _template_number(bug_id) == 9
        ),
    }


def _named(events: list, name: str) -> list:
    return [event for event in events if event.get("event") == name]


def _eid(key: str) -> str:
    parts = str(key or "").split(":")
    return parts[-1] if parts else ""


def _staff_drain(events: list):
    for event in _named(events, "local_action_drain_started"):
        keys = list(event.get("visible_eligible_keys") or [])
        eids = {_eid(key) for key in keys}
        if set(STAFF_EIDS) <= eids:
            return event
    return None


def _probe(events: list, eid: str, kind: str, hub: str):
    for event in _named(events, kind):
        key = event.get("key") or ""
        if _eid(key) == eid and key.startswith(hub + ":"):
            return event
    return None


def _later_witness(events: list, hub: str, after_step: int):
    prefix = hub + ":"
    for event in _named(events, "child_parent_witness"):
        step = int(event.get("step") or -1)
        branch = event.get("branch_key") or ""
        if step <= after_step or not branch.startswith(prefix):
            return_match = False
        else:
            return_match = True
        if not return_match:
            continue
        same = [item.get("event") for item in events if item.get("step") == step]
        return {
            "step": step,
            "exact_sig": event.get("exact_sig") or "",
            "cluster_id": event.get("cluster_id") or "",
            "branch_key": branch,
            "witness_strength": event.get("witness_strength") or "",
            "same_step_events": same,
            "local_action_drain_started": "local_action_drain_started" in same,
        }
    return None


def _replay(events: list, steps: list, relocate: dict, reset: dict) -> dict:
    if not relocate or not reset:
        return {
            "present": False,
            "local_probe_events": [],
            "sequence_events_during_restore_steps": {},
        }
    start = int(reset.get("before_step"))
    length = int(relocate.get("replay_path_length") or 0)
    window = list(range(start, start + length))
    probe_names = {
        "local_action_drain_started",
        "local_action_probe_selected",
        "local_action_probe_completed",
        "return_entry_drain_started",
        "return_entry_probe_selected",
        "return_entry_probe_completed",
    }
    during = {}
    probes = []
    for step in window:
        names = [event.get("event") for event in events if event.get("step") == step]
        during[str(step)] = names
        probes.extend(name for name in names if name in probe_names)
    executed = []
    for rec in steps:
        if rec.get("kind") != "step":
            continue
        index = rec.get("index")
        if index not in window:
            continue
        action = rec.get("action") or {}
        executed.append({
            "index": index,
            "type": action.get("type"),
            "target_eid": action.get("target_eid"),
            "src_cluster": rec.get("src_cluster") or "",
        })
    interior = window[1:]
    return {
        "present": True,
        "reset_before_step": start,
        "replay_path_length": length,
        "restore_step_indexes": window,
        "sequence_events_during_restore_steps": during,
        "local_or_return_probe_events_during_restore": probes,
        "interior_restore_steps_have_no_sequence_events": all(
            not during[str(step)] for step in interior),
        "executed_actions": executed,
    }


def _post_reset_staff(events: list, steps: list, hub: str, after_step: int) -> dict:
    later_probes = []
    for event in events:
        if event.get("event") not in (
            "local_action_probe_selected", "local_action_probe_completed",
            "local_action_drain_started",
        ):
            continue
        if int(event.get("step") or -1) <= after_step:
            continue
        blob = " ".join([
            event.get("key") or "",
            " ".join(event.get("visible_eligible_keys") or []),
            event.get("hub_cluster") or "",
        ])
        if hub in blob and any(eid in blob for eid in STAFF_EIDS):
            later_probes.append({
                "step": event.get("step"),
                "event": event.get("event"),
                "key": event.get("key") or "",
                "visible_eligible_keys": list(event.get("visible_eligible_keys") or []),
            })
    openings = []
    for rec in steps:
        if rec.get("kind") != "step":
            continue
        index = int(rec.get("index") or -1)
        action = rec.get("action") or {}
        if index <= after_step or action.get("target_eid") != "open_mid_b":
            continue
        openings.append({
            "index": index,
            "src_cluster": rec.get("src_cluster") or "",
            "src_url": rec.get("src_url") or "",
        })
    return {
        "staff_hub_drain_or_probe_after_relocation": later_probes,
        "open_mid_b_after_relocation": openings,
    }


def _diagnosed(app: str) -> dict:
    events = _load(_seq_path(app))
    steps = _jsonl(_events_path(app))
    metrics = _metrics_row(app)
    drain = _staff_drain(events)
    if drain is None:
        raise SystemExit(f"{app} has no staff-note local drain")
    hub = drain.get("hub_cluster") or ""
    probes = {}
    for eid in STAFF_EIDS:
        selected = _probe(events, eid, "local_action_probe_selected", hub)
        completed = _probe(events, eid, "local_action_probe_completed", hub)
        probes[eid] = {
            "selected_step": None if selected is None else selected.get("step"),
            "completed_step": None if completed is None else completed.get("step"),
            "key": "" if selected is None else selected.get("key") or "",
            "destination_sig": "" if completed is None else completed.get("destination_sig") or "",
            "destination_cluster": "" if completed is None else completed.get("destination_cluster") or "",
            "same_hub": bool(completed) and completed.get("destination_cluster") == hub,
        }
    relocates = _named(events, "residual_frontier_debt_relocate")
    relocate = relocates[0] if relocates else None
    resets = [
        item for item in (metrics.get("reset_events") or [])
        if item.get("reason") != "initial"
    ]
    reset = next((item for item in resets if item.get("reason") == "relocate"), None)
    templates = _template_status(app, metrics.get("confirmed_bugs"))
    witness = _later_witness(events, hub, int(drain.get("step") or 0))
    record = {
        "app": app,
        "budget": 120,
        "seed": 1,
        "confirmed_bugs": sorted(metrics.get("confirmed_bugs") or []),
        "template_589": templates,
        "debt_created": metrics.get("residual_frontier_debts_created"),
        "debt_tokens_consumed": metrics.get("residual_frontier_tokens_consumed"),
        "debt_relocations": metrics.get("residual_frontier_debt_relocations"),
        "relocation_failures": metrics.get("residual_frontier_relocation_failures"),
        "false_success_violations": metrics.get("residual_frontier_false_success_violations"),
        "first_staff_local_drain": {
            "step": drain.get("step"),
            "hub_cluster": hub,
            "hub_sig": drain.get("hub_sig") or "",
            "visible_eligible_keys": list(drain.get("visible_eligible_keys") or []),
            "trigger_same_step_includes_child_parent_witness": (
                "child_parent_witness" in [
                    event.get("event") for event in events
                    if event.get("step") == drain.get("step")
                ]
            ),
        },
        "same_hub_probes": probes,
        "relocation": None if relocate is None else {
            "step": relocate.get("step"),
            "debt_id": relocate.get("debt_id") or "",
            "from_sig": relocate.get("from_sig") or "",
            "from_cluster": relocate.get("from_cluster") or "",
            "target_waypoint_sig": relocate.get("target_waypoint_sig") or "",
            "target_waypoint_cluster": relocate.get("target_waypoint_cluster") or "",
            "replay_path_length": relocate.get("replay_path_length"),
            "reason": relocate.get("reason") or "",
            "scc_closed": relocate.get("scc_closed"),
            "scc_pending_count": relocate.get("scc_pending_count"),
            "active_sequence": relocate.get("active_sequence"),
            "remaining_count": relocate.get("remaining_count"),
        },
        "executor_reset": reset,
        "non_initial_resets": resets,
        "replay": _replay(events, steps, relocate or {}, reset or {}),
        "later_same_hub_witness": witness,
        "after_relocation": (
            {"present": False}
            if relocate is None else
            _post_reset_staff(events, steps, hub, int(relocate.get("step") or 0))
        ),
    }
    return record


def _deep(events_app: str = DEEP) -> dict:
    events = _load(_seq_path(events_app))
    metrics = _metrics_row(events_app)
    resumes = _named(events, "parent_frame_resume_to_return")
    facts = []
    for resume in resumes:
        step = int(resume.get("step") or -1)
        cluster = resume.get("cluster_id") or ""
        drains = [
            event for event in _named(events, "local_action_drain_started")
            if int(event.get("step") or 10**9) <= step
            and (event.get("hub_cluster") or "") == cluster
        ]
        visible = list((drains[-1].get("visible_eligible_keys") if drains else []) or [])
        probed = []
        for event in _named(events, "local_action_probe_completed"):
            key = event.get("key") or ""
            if int(event.get("step") or 10**9) <= step and key in visible:
                probed.append(key)
        exhausted = [
            event for event in _named(events, "local_action_drain_exhausted")
            if event.get("step") == step and (event.get("cluster_id") or "") == cluster
        ]
        pending = [key for key in visible if key not in set(probed)]
        facts.append({
            "step": step,
            "cluster_id": cluster,
            "resumed_branch": resume.get("resumed_branch") or resume.get("branch_key") or "",
            "original_parent_hub_cluster": resume.get("original_parent_hub_cluster") or "",
            "same_step_events": [
                event.get("event") for event in events if event.get("step") == step
            ],
            "visible_local_button_keys": visible,
            "probed_local_button_keys": probed,
            "unprobed_visible_local_keys": pending,
            "local_buttons_on_resumed_hub": bool(visible),
            "drain_exhausted_same_step": bool(exhausted),
            "exhausted_next_phase": "" if not exhausted else exhausted[-1].get("next_phase") or "",
            "remaining_structural_frontier_count": (
                None if not exhausted else exhausted[-1].get("remaining_structural_frontier_count")
            ),
        })
    return {
        "app": "deepbench",
        "source_app": events_app,
        "budget": 120,
        "seed": 1,
        "debt_created": metrics.get("residual_frontier_debts_created"),
        "debt_relocations": metrics.get("residual_frontier_debt_relocations"),
        "non_initial_resets": [
            item for item in (metrics.get("reset_events") or [])
            if item.get("reason") != "initial"
        ],
        "confirmed_bugs": sorted(metrics.get("confirmed_bugs") or []),
        "parent_frame_resumes": facts,
        "broad_resume_drain_rejected": True,
        "rejection": (
            "A parent_frame_resume_to_return exists on a hub whose visible "
            "local buttons were the subject of the existing drain, and this "
            "run performs zero residual-debt relocations. A new resume drain "
            "would be an extra trigger. v0.3.24 may advance an interaction "
            "episode only when a real debt relocation reset is selected."
        ),
    }


def _source_facts() -> dict:
    explorer = open(EXPLORER, encoding="utf-8").read().splitlines()
    window = "\n".join(explorer[250:470])
    predicate = "if seqc is not None and not restore_step:"
    drain = open(DRAIN, encoding="utf-8").read()
    returned = open(RETURN_DRAIN, encoding="utf-8").read()
    debt = open(DEBT, encoding="utf-8").read()
    freeze = _load(DEBT_FREEZE)
    recorded = ((freeze.get("files") or {}).get(
        "ghostqa/exploration/residual_frontier_debt_guard.py") or {}).get("sha256")
    return {
        "explorer_after_skipped_on_restore": predicate in window,
        "explorer_policy_reset_in_relocate_window": "policy.reset(" in window,
        "executor_reset_in_relocate_window": "executor.reset()" in window,
        "drained_by_cluster_cleared_in_local_reset": "_drained_by_cluster = {}" in drain,
        "same_hub_completion_marks_drained": "def _complete_same_hub" in drain and "_mark_drained" in drain,
        "return_same_hub_completion_marks_drained": "def _complete_return_same_hub" in returned,
        "return_left_hub_marks_drained": "def _leave_hub" in returned,
        "promoted_resume_marks_drained": "def _resume_drain" in drain,
        "debt_relocate_does_not_assign_drained_by_cluster": "_drained_by_cluster" not in debt,
        "debt_module_sha256": sha256_file(DEBT),
        "debt_freeze_recorded_sha256": recorded,
        "debt_module_matches_freeze": sha256_file(DEBT) == recorded,
        "debt_freeze_sha256": sha256_file(DEBT_FREEZE),
    }


def build_audit() -> dict:
    diagnosed = {app: _diagnosed(app) for app in DIAGNOSED}
    return {
        "version": "v0.3.24",
        "basis_round": "v0.3.23",
        "basis_outcome": "B",
        "basis_publication": "experiments/published/residual-frontier-debt-v0.3.23",
        "question": (
            "Does v0.3.23 lose the Campus and Studio template 9 because "
            "executor.reset clears browser-side mutation state while the "
            "local-action drain's run-global already-drained memory survives?"
        ),
        "hypothesis": (
            "Same-hub local-action and return-entry drain dedupe keys are "
            "browser-episode interaction memory. Promoted and other cross-hub "
            "drain keys, and all structural sequence, branch, debt, waypoint, "
            "and return-cycle memory, stay run-scoped."
        ),
        "product_default_changed": False,
        "computed_from_publication": True,
        "no_candidate_import": True,
        "source_facts": _source_facts(),
        "diagnosed_targets": diagnosed,
        "deepbench": _deep(),
        "split": {
            "relocation_reset_targets": [
                app for app, rec in diagnosed.items()
                if int(rec.get("debt_relocations") or 0) > 0
            ],
            "no_relocation_targets": [
                app for app, rec in diagnosed.items()
                if int(rec.get("debt_relocations") or 0) == 0
            ],
            "template_9_missing_only_when_relocation": all(
                (int(rec.get("debt_relocations") or 0) > 0) == bool(
                    rec["template_589"]["nine_missing"])
                for rec in diagnosed.values()
            ),
        },
    }


def main() -> int:
    payload = build_audit()
    path = os.path.join(VALIDATION, "v0323-episode-drain-audit.json")
    _write(path, payload)
    print(path)
    print(sha256_file(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
