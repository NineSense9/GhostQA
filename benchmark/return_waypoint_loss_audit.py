"""Code-derived audit of the frozen v0.3.20 fresh-positive waypoint loss.

Reads the committed v0.3.20 publication and the benchmark manifests.
Bug ids and element ids appear only in this audit. They are not candidate
policy inputs.
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLICATION = os.path.join(
    ROOT, "experiments", "published", "fresh-composite-v0.3.20")
POSITIVE = ("buggy-campus", "buggy-warehouse", "buggy-studio", "buggy-booking")
GUARD = "ghost-structural-return-guard"
CANDIDATE = "ghost-structural-finding-return-entry-drain-guard"
BUDGET = 120
SEED = 1
AUDIT_EIDS = ("btn_pin", "btn_cool", "open_side", "nav_prefs")
TEMPLATE_SUFFIXES = {
    "5": {
        "template": 5,
        "category": "dead action",
        "depth": 3,
        "action_role": "entity/detail local button",
        "generic_eid": "btn_pin",
    },
    "8": {
        "template": 8,
        "category": "state inconsistency",
        "depth": 4,
        "action_role": "entity/detail same-hub local mutation",
        "generic_eid": "btn_cool",
    },
    "9": {
        "template": 9,
        "category": "cross-page consistency",
        "depth": 5,
        "action_role": "entity -> side list -> side entity local mutation then cross-page navigation",
        "generic_eid": "btn_staff_note",
        "generic_path": [
            "entity -> open_side",
            "side list -> side entity",
            "side entity -> btn_staff_note",
            "side entity -> open_mid_b",
        ],
    },
}


def _load(path: str):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _stem(policy: str) -> str:
    return f"{policy}_b{BUDGET}_s{SEED}"


def _events(app: str, policy: str) -> list:
    path = os.path.join(
        PUBLICATION, "evidence", app, _stem(policy) + ".events.jsonl")
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _sequence(app: str, policy: str) -> list:
    path = os.path.join(
        PUBLICATION, "evidence", app, _stem(policy) + ".sequence_events.json")
    return _load(path)


def _graph(app: str, policy: str) -> dict:
    path = os.path.join(
        PUBLICATION, "evidence", app, _stem(policy) + ".graph.json")
    return _load(path)


def _metrics(app: str) -> dict:
    return _load(os.path.join(PUBLICATION, "evidence", app, "metrics.json"))


def _confirmed(app: str, policy: str) -> list:
    for row in _metrics(app).get("runs") or []:
        if row.get("policy") == policy and int(row.get("budget") or 0) == BUDGET and int(row.get("seed") or 0) == SEED:
            return list(row.get("confirmed_bugs") or [])
    return []


def _steps(events: list) -> list:
    return [row for row in events if row.get("kind") == "step"]


def _page(url: str) -> str:
    path = url or ""
    if "://" in path:
        path = path.split("://", 1)[1]
        path = path.split("/", 1)[1] if "/" in path else ""
    path = path.split("?", 1)[0].split("#", 1)[0]
    return path or ""


def _action_eid(step: dict) -> str:
    action = step.get("action") or {}
    return action.get("target_eid") or action.get("type") or ""


def _first_divergence(guard_steps: list, candidate_steps: list) -> dict:
    limit = min(len(guard_steps), len(candidate_steps))
    for index in range(limit):
        guard = guard_steps[index]
        candidate = candidate_steps[index]
        guard_key = (
            _action_eid(guard),
            guard.get("action", {}).get("type"),
            _page(guard.get("src_url") or ""),
            _page(guard.get("dst_url") or ""),
        )
        candidate_key = (
            _action_eid(candidate),
            candidate.get("action", {}).get("type"),
            _page(candidate.get("src_url") or ""),
            _page(candidate.get("dst_url") or ""),
        )
        if guard_key != candidate_key:
            return {
                "action_index": index,
                "guard": _step_brief(guard),
                "candidate": _step_brief(candidate),
            }
    return {
        "action_index": None,
        "guard": None,
        "candidate": None,
    }


def _step_brief(step: dict) -> dict:
    action = step.get("action") or {}
    return {
        "action_index": step.get("index"),
        "decision_mode": step.get("decision_mode") or "",
        "last_label": step.get("last_label") or "",
        "action_type": action.get("type") or "",
        "action_eid": action.get("target_eid") or "",
        "src_page": _page(step.get("src_url") or ""),
        "dst_page": _page(step.get("dst_url") or ""),
        "src_cluster": step.get("src_cluster") or "",
        "dst_cluster": step.get("dst_cluster") or "",
        "src_sig": step.get("src_sig") or "",
        "dst_sig": step.get("dst_sig") or "",
        "returning": bool(step.get("returning")),
        "active_branch": step.get("active_branch") or "",
    }


def _named(events: list, name: str) -> list:
    return [event for event in events if event.get("event") == name]


def _first_eid(steps: list, eid: str):
    for step in steps:
        action = step.get("action") or {}
        if action.get("target_eid") == eid:
            return {
                "action_index": step.get("index"),
                "src_page": _page(step.get("src_url") or ""),
                "dst_page": _page(step.get("dst_url") or ""),
                "decision_mode": step.get("decision_mode") or "",
                "last_label": step.get("last_label") or "",
            }
    return None


def _eid_of(action_key: str) -> str:
    parts = (action_key or "").split(":")
    if parts and parts[0] == "back":
        return "back"
    if len(parts) >= 2 and parts[0] in ("click", "input"):
        return parts[1]
    return action_key or ""


def _action_eids(keys) -> list:
    found = []
    for key in keys or []:
        eid = _eid_of(key)
        if eid and eid not in found:
            found.append(eid)
    return found


def _node_actions(graph: dict, sig: str) -> dict:
    for node in graph.get("nodes") or []:
        if node.get("sig") != sig:
            continue
        observed = _action_eids(node.get("observed_actions"))
        tried = _action_eids(node.get("tried_actions"))
        return {
            "sig": sig,
            "cluster": node.get("cluster_id") or "",
            "page": _page(node.get("url") or ""),
            "first_seen_step": node.get("first_seen_step"),
            "visits": node.get("visits"),
            "observed": observed,
            "tried": tried,
            "final_graph_residual": [eid for eid in observed if eid not in set(tried)],
        }
    return {
        "sig": sig,
        "cluster": "",
        "page": "",
        "observed": [],
        "tried": [],
        "final_graph_residual": [],
    }


def _template_roles(app: str, lost: list) -> list:
    manifest = _load(os.path.join(ROOT, "apps", app, "bugs.manifest.json"))
    by_id = {bug.get("id"): bug for bug in manifest.get("bugs") or []}
    roles = []
    for bug_id in lost:
        suffix = bug_id.rsplit("-", 1)[-1]
        # BUG-CP5 -> suffix is CP5; the template digit is the trailing number.
        digit = ""
        for char in reversed(suffix):
            if char.isdigit():
                digit = char + digit
            else:
                break
        spec = TEMPLATE_SUFFIXES.get(digit)
        bug = by_id.get(bug_id) or {}
        roles.append({
            "bug_id": bug_id,
            "template": None if spec is None else spec["template"],
            "category": bug.get("category") or (None if spec is None else spec["category"]),
            "depth": bug.get("trigger_depth"),
            "action_role": None if spec is None else spec["action_role"],
            "generic_eid": None if spec is None else spec["generic_eid"],
            "manifest_match": bug.get("match") or {},
            "min_reproduction": bug.get("min_reproduction") or [],
        })
    return roles


def _resume_event(sequence: list) -> dict:
    for event in sequence:
        if event.get("event") == "parent_frame_resume_to_return":
            return event
    return {}


def _paired_witness(sequence: list, step: int) -> dict:
    for event in sequence:
        if event.get("event") == "child_parent_witness" and event.get("step") == step:
            return event
    return {}


def _outer_returns(steps: list, resume_step: int, branch: str) -> list:
    rows = []
    for step in steps:
        index = int(step.get("index") if step.get("index") is not None else -1)
        if index <= resume_step:
            continue
        if (step.get("last_label") or "") != "return_hub":
            continue
        if branch and (step.get("active_branch") or "") != branch:
            continue
        rows.append(_step_brief(step))
        if len(rows) >= 2:
            break
    return rows


def audit_target(app: str) -> dict:
    guard_steps = _steps(_events(app, GUARD))
    candidate_events = _events(app, CANDIDATE)
    candidate_steps = _steps(candidate_events)
    sequence = _sequence(app, CANDIDATE)
    graph = _graph(app, CANDIDATE)
    guard_confirmed = _confirmed(app, GUARD)
    candidate_confirmed = _confirmed(app, CANDIDATE)
    lost = [bug_id for bug_id in guard_confirmed if bug_id not in set(candidate_confirmed)]
    witnesses = _named(sequence, "child_parent_witness")
    resumes = _named(sequence, "parent_frame_resume_to_return")
    first_resume = _resume_event(sequence)
    resume_step = int(first_resume.get("step") if first_resume.get("step") is not None else -1)
    first_witness = _paired_witness(sequence, resume_step)
    outer_branch = first_resume.get("resumed_branch") or first_resume.get("branch_key") or ""
    returns = _outer_returns(candidate_steps, resume_step, outer_branch) if resume_step >= 0 else []
    first_return = returns[0] if returns else {}
    second_return = returns[1] if len(returns) > 1 else {}
    entity_graph = _node_actions(graph, first_return.get("dst_sig") or "")
    occurrences = {eid: _first_eid(candidate_steps, eid) for eid in AUDIT_EIDS}
    waypoint_index = first_return.get("action_index")
    observed = set(entity_graph.get("observed") or [])
    residual = {}
    for eid in AUDIT_EIDS:
        hit = occurrences[eid]
        tried_at_or_before = bool(
            hit is not None and waypoint_index is not None
            and int(hit["action_index"]) <= int(waypoint_index))
        residual[eid] = {
            "observed_on_entity_node": eid in observed,
            "first_occurrence": None if hit is None else hit["action_index"],
            "first_occurrence_detail": hit,
            "residual_at_first_waypoint": bool(eid in observed and not tried_at_or_before),
        }
    return {
        "app": app,
        "budget": BUDGET,
        "seed": SEED,
        "guard_policy": GUARD,
        "candidate_policy": CANDIDATE,
        "guard_confirmed": guard_confirmed,
        "candidate_confirmed": candidate_confirmed,
        "lost_vs_guard": lost,
        "template_roles": _template_roles(app, lost),
        "first_divergence": _first_divergence(guard_steps, candidate_steps),
        "child_parent_witness": {
            "step": first_witness.get("step"),
            "branch_key": first_witness.get("branch_key") or "",
            "child_branch": first_witness.get("child_branch") or "",
            "expected_parent_sig": first_witness.get("expected_parent_sig") or "",
            "expected_parent_cluster": first_witness.get("expected_parent_cluster") or "",
            "observed_destination_sig": first_witness.get("observed_destination_sig") or "",
            "observed_destination_cluster": first_witness.get("observed_destination_cluster") or "",
            "stack_depth_before_pop": first_witness.get("stack_depth_before_pop"),
        },
        "parent_frame_resume_to_return": {
            "step": first_resume.get("step"),
            "resumed_sequence_instance_id": first_resume.get("resumed_sequence_instance_id"),
            "resumed_branch": first_resume.get("resumed_branch") or first_resume.get("branch_key") or "",
            "original_parent_hub_sig": first_resume.get("original_parent_hub_sig") or "",
            "original_parent_hub_cluster": first_resume.get("original_parent_hub_cluster") or "",
            "stack_depth": first_resume.get("stack_depth"),
            "returning": first_resume.get("returning"),
            "commitment_left": first_resume.get("commitment_left"),
        },
        "original_outer_branch": first_resume.get("resumed_branch") or first_resume.get("branch_key") or "",
        "original_parent": {
            "sig": first_resume.get("original_parent_hub_sig") or "",
            "cluster": first_resume.get("original_parent_hub_cluster") or "",
        },
        "first_return_after_resume": first_return,
        "second_return_after_resume": second_return,
        "common_step_mid_to_entity": first_return,
        "common_step_entity_to_list": second_return,
        "first_occurrences": occurrences,
        "residual_at_first_waypoint": residual,
        "entity_graph": entity_graph,
        "witness_count": len(witnesses),
        "resume_count": len(resumes),
    }


def build_audit() -> dict:
    targets = [audit_target(app) for app in POSITIVE]
    pattern = []
    for target in targets:
        mid = target["common_step_mid_to_entity"]
        parent = target["common_step_entity_to_list"]
        pattern.append({
            "app": target["app"],
            "resume_step": target["parent_frame_resume_to_return"]["step"],
            "stack_depth": target["parent_frame_resume_to_return"]["stack_depth"],
            "mid_to_entity_index": mid.get("action_index"),
            "mid_page": mid.get("src_page"),
            "entity_page": mid.get("dst_page"),
            "entity_to_parent_index": parent.get("action_index"),
            "parent_page": parent.get("dst_page"),
            "lost_vs_guard": target["lost_vs_guard"],
        })
    return {
        "version": "v0.3.21",
        "source_publication": "experiments/published/fresh-composite-v0.3.20",
        "source_round": "v0.3.20",
        "source_outcome": "C",
        "budget": BUDGET,
        "seed": SEED,
        "candidate_policy": CANDIDATE,
        "guard_policy": GUARD,
        "causal_language": (
            "consistent with intermediate-waypoint residual-frontier starvation; "
            "entity local actions were observable but skipped at the first resumed return; "
            "open_side was residual at the first waypoint and either absent or delayed. "
            "This audit does not prove the mechanism will recover every bug."
        ),
        "common_pattern": pattern,
        "targets": targets,
    }


def main() -> None:
    print(json.dumps(build_audit(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
