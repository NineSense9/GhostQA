"""Post-escape sink measurement for v0.3.22.

Reads frozen topology and committed event evidence. Does not import candidate
decision logic and does not choose exploration actions.
"""
from __future__ import annotations

import json
import os

from benchmark.algorithm_freeze import sha256_file, verify_freeze
from benchmark.fresh_composite_analysis import product_default_changed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSITIVE_TARGETS = (
    "buggy-campus",
    "buggy-warehouse",
    "buggy-studio",
    "buggy-booking",
)
DIAGNOSTIC_BUDGETS = (240, 480)
HISTORICAL_BUDGET = 120
SEED = 1
CANDIDATE = "ghost-structural-return-waypoint-frontier-guard"
GUARD = "ghost-structural-return-guard"
DOMINANCE_THRESHOLD = 0.60
FINAL_QUARTILE = 0.25
TEMPLATE_NUMBERS = (5, 8, 9)
CONCLUSIONS = (
    "persistent_post_terminal_sink",
    "budget_delay",
    "mixed_or_inconclusive",
    "protocol_invalid",
)
CELLS = tuple(
    (app, budget) for app in POSITIVE_TARGETS for budget in DIAGNOSTIC_BUDGETS
)
V0321_PUBLICATION = os.path.join(
    "experiments", "published", "return-waypoint-frontier-v0.3.21")
V0320_PUBLICATION = os.path.join(
    "experiments", "published", "fresh-composite-v0.3.20")
CANDIDATE_FREEZE = os.path.join(
    "experiments", "frozen", "ghost-return-waypoint-frontier-v0.3.21", "freeze.json")
SUITE_FREEZE = os.path.join(
    "experiments", "frozen", "v0.3.20-fresh-composite-suite", "freeze.json")
CANDIDATE_SOURCE = "ghostqa/exploration/return_waypoint_frontier_guard.py"
VALIDATION_DIR = os.path.join("experiments", "validation", "v0.3.22")
PUBLICATION_DIR = os.path.join(
    "experiments", "published", "post-escape-sink-v0.3.22")
RUN_DIR = os.path.join("experiments", "runs", "v0322-post-escape-sink")
STARTING_HEAD = "deda60a7ef7494466d12598b9418234c09b543f4"

DIAGNOSIS_MEANING = {
    "persistent_post_terminal_sink": (
        "Within the preregistered horizons, the remaining regression on the "
        "targets that lost template 5/8/9 at budget 120 is consistent with a "
        "post-terminal ordinary-policy attractor rather than sequence-scoped "
        "return-cycle failure or 120-step budget delay."
    ),
    "budget_delay": (
        "The budget-120 split was a finite-budget delay on the losing targets. "
        "The unchanged candidate reached the entity residual frontier and "
        "recovered template 5/8/9 by budget 240 or 480."
    ),
    "mixed_or_inconclusive": (
        "The preregistered budgets do not isolate one shared mechanism."
    ),
    "protocol_invalid": (
        "Freeze, protocol, semantic, or publication identity failed."
    ),
}


def _load(path: str):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write(path: str, payload) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _frac(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count / total, 6)


def meets_threshold(count: int, total: int, threshold: float = DOMINANCE_THRESHOLD) -> bool:
    if total <= 0:
        return False
    return (count / total) >= threshold


def template_number(bug_id: str) -> int | None:
    suffix = str(bug_id or "").rsplit("-", 1)[-1]
    digits = ""
    for char in reversed(suffix):
        if char.isdigit():
            digits = char + digits
        else:
            break
    if not digits:
        return None
    return int(digits)


def url_parts(url: str) -> tuple[str, str, set[str]]:
    raw = url or ""
    if "://" in raw:
        raw = raw.split("://", 1)[1]
        raw = raw.split("/", 1)[1] if "/" in raw else ""
    raw = raw.split("#", 1)[0]
    path, _, query = raw.partition("?")
    filename = path.strip("/").split("/")[-1] if path.strip("/") else ""
    values = set()
    for piece in query.split("&"):
        if not piece:
            continue
        values.add(piece.split("=", 1)[1] if "=" in piece else piece)
    normalized = "/" + filename if filename else "/"
    if query:
        normalized += "?" + query
    return filename, normalized, values


def action_eid(step: dict) -> str:
    action = step.get("action") or {}
    if isinstance(action, str):
        return action
    return action.get("target_eid") or action.get("type") or ""


def eids_from_keys(keys) -> list[str]:
    found = []
    for key in keys or []:
        parts = str(key).split(":")
        eid = parts[-1] if parts else ""
        if eid and eid not in found:
            found.append(eid)
    return found


def tarjan_sccs(nodes: list[str], adjacency: dict[str, list[str]]) -> list[list[str]]:
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []
    counter = [0]

    def strong(node: str) -> None:
        index[node] = counter[0]
        low[node] = counter[0]
        counter[0] += 1
        stack.append(node)
        on_stack.add(node)
        for nxt in adjacency.get(node, ()):
            if nxt not in index:
                strong(nxt)
                low[node] = min(low[node], low[nxt])
            elif nxt in on_stack:
                low[node] = min(low[node], index[nxt])
        if low[node] == index[node]:
            component = []
            while True:
                item = stack.pop()
                on_stack.remove(item)
                component.append(item)
                if item == node:
                    break
            components.append(sorted(component))

    for node in sorted(nodes):
        if node not in index:
            strong(node)
    return components


def build_navigation_graph(topology: dict) -> dict:
    node_list = list(topology.get("nodes") or [])
    nodes = {node["id"]: node for node in node_list}
    records = []
    for edge in topology.get("edges") or []:
        src = edge.get("src") or ""
        dst = edge.get("dst") or ""
        if not src or not dst or src == dst or src not in nodes or dst not in nodes:
            continue
        records.append({
            "src": src,
            "dst": dst,
            "action": edge.get("action") or "",
            "parent_return": bool(edge.get("parent_return")),
            "navigates": bool(edge.get("navigates")),
        })
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    for record in records:
        if record["dst"] not in adjacency[record["src"]]:
            adjacency[record["src"]].append(record["dst"])
    components = tarjan_sccs(list(nodes), adjacency)
    scc_of = {}
    for number, component in enumerate(components):
        for node_id in component:
            scc_of[node_id] = number
    outgoing = {number: [] for number in range(len(components))}
    for record in records:
        src_scc = scc_of[record["src"]]
        dst_scc = scc_of[record["dst"]]
        if src_scc != dst_scc:
            outgoing[src_scc].append(record)
    condensation = []
    seen_pairs = set()
    for record in records:
        pair = (scc_of[record["src"]], scc_of[record["dst"]])
        if pair[0] != pair[1] and pair not in seen_pairs:
            seen_pairs.add(pair)
            condensation.append({"src": pair[0], "dst": pair[1]})
    return {
        "nodes": nodes,
        "edges": records,
        "adjacency": adjacency,
        "components": components,
        "scc_of": scc_of,
        "outgoing": outgoing,
        "condensation": condensation,
    }


def is_form_hub(node_id: str, graph: dict) -> bool:
    node = graph["nodes"].get(node_id) or {}
    if node.get("entity"):
        return False
    outgoing = [
        edge for edge in graph["edges"]
        if edge["src"] == node_id and edge["parent_return"]
        and (graph["nodes"].get(edge["dst"]) or {}).get("entity")
    ]
    incoming = [
        edge for edge in graph["edges"]
        if edge["dst"] == node_id and not (graph["nodes"].get(edge["src"]) or {}).get("entity")
    ]
    return bool(outgoing and incoming)


def match_nodes(url: str, graph: dict) -> list[dict]:
    filename, _normalized, values = url_parts(url)
    same = [node for node in graph["nodes"].values() if node.get("page") == filename]
    specific = [node for node in same if (node.get("entity") or "") and node["entity"] in values]
    if specific:
        return specific
    bare = [node for node in same if not (node.get("entity") or "")]
    return bare or same


def scc_id(component: list[str]) -> str:
    return "|".join(component)


def _bfs_path(graph: dict, sources: list[str], goal: str) -> list[str] | None:
    if not sources or not goal:
        return None
    if goal in sources:
        return [goal]
    previous = {source: None for source in sources}
    queue = list(sources)
    seen = set(sources)
    while queue:
        current = queue.pop(0)
        for nxt in graph["adjacency"].get(current, ()):
            if nxt in seen:
                continue
            seen.add(nxt)
            previous[nxt] = current
            if nxt == goal:
                path = [goal]
                cursor = goal
                while previous[cursor] is not None:
                    cursor = previous[cursor]
                    path.append(cursor)
                path.reverse()
                return path
            queue.append(nxt)
    return None


def _reachable(graph: dict, sources: list[str], goal: str) -> bool:
    return _bfs_path(graph, sources, goal) is not None


def classify_static(coverage: float, outgoing_count: int, tie: bool, matched: bool) -> str:
    if tie:
        return "ambiguous"
    if not matched or coverage < DOMINANCE_THRESHOLD:
        return "no_dominant_scc"
    if outgoing_count == 0:
        return "closed_scc"
    return "policy_attractor_with_static_exit"


def load_jsonl(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def step_rows(events: list[dict]) -> list[dict]:
    return [row for row in events if row.get("kind") == "step"]


def target_freeze_path(app: str) -> str:
    return os.path.join(
        "experiments", "frozen", "v0.3.20-fresh-composite-suite", app, "freeze.json")


def candidate_source_sha() -> str:
    return sha256_file(os.path.join(ROOT, CANDIDATE_SOURCE.replace("/", os.sep)))


def freeze_status() -> dict:
    mismatches = []
    for path, label in (
        (CANDIDATE_FREEZE, "v0.3.21 candidate"),
        (SUITE_FREEZE, "v0.3.20 suite"),
    ):
        for item in verify_freeze(os.path.join(ROOT, path.replace("/", os.sep))):
            mismatches.append(label + " " + item)
    frozen = _load(os.path.join(ROOT, CANDIDATE_FREEZE.replace("/", os.sep)))
    recorded = ((frozen.get("files") or {}).get(CANDIDATE_SOURCE) or {}).get("sha256")
    live = candidate_source_sha()
    if recorded and live != recorded:
        mismatches.append("candidate source hash mismatch")
    for app in POSITIVE_TARGETS:
        rel = target_freeze_path(app)
        for item in verify_freeze(os.path.join(ROOT, rel.replace("/", os.sep))):
            mismatches.append(app + " " + item)
    return {
        "ok": not mismatches,
        "mismatches": mismatches,
        "candidate_source_sha256": live,
        "candidate_freeze_sha256": sha256_file(os.path.join(ROOT, CANDIDATE_FREEZE.replace("/", os.sep))),
        "suite_freeze_sha256": sha256_file(os.path.join(ROOT, SUITE_FREEZE.replace("/", os.sep))),
        "target_freeze_sha256": {
            app: sha256_file(os.path.join(ROOT, target_freeze_path(app).replace("/", os.sep)))
            for app in POSITIVE_TARGETS
        },
        "product_default_changed": bool(product_default_changed()),
    }


def _historical_stem(budget: int = HISTORICAL_BUDGET) -> str:
    return f"{CANDIDATE}_b{budget}_s{SEED}"


def historical_cell_paths(app: str, budget: int = HISTORICAL_BUDGET) -> dict:
    base = os.path.join(ROOT, V0321_PUBLICATION.replace("/", os.sep), "evidence", app)
    stem = _historical_stem(budget)
    return {
        "events": os.path.join(base, stem + ".events.jsonl"),
        "sequence": os.path.join(base, stem + ".sequence_events.json"),
        "summary": os.path.join(base, "metrics.json"),
        "topology": os.path.join(ROOT, "apps", app, "topology.json"),
    }


def diagnostic_cell_dir(app: str, budget: int, run_root: str | None = None) -> str:
    root = run_root or os.path.join(ROOT, RUN_DIR.replace("/", os.sep))
    return os.path.join(root, f"{app}_b{budget}_s{SEED}")


def _summary_row(summary: dict, budget: int) -> dict:
    if "runs" in summary:
        for row in summary.get("runs") or []:
            if row.get("policy") == CANDIDATE and _int(row.get("budget")) == budget and _int(row.get("seed")) == SEED:
                return row
        return {}
    return summary


def load_bundle(app: str, budget: int, *, run_root: str | None = None, historical: bool = False) -> dict:
    if historical or budget == HISTORICAL_BUDGET:
        paths = historical_cell_paths(app, budget)
        summary = _summary_row(_load(paths["summary"]), budget)
        events = load_jsonl(paths["events"])
        sequence = _load(paths["sequence"])
    else:
        base = diagnostic_cell_dir(app, budget, run_root)
        events = load_jsonl(os.path.join(base, "events.jsonl"))
        sequence = _load(os.path.join(base, "sequence_events.json"))
        summary = _load(os.path.join(base, "summary.json"))
    return {
        "app": app,
        "budget": budget,
        "events": events,
        "sequence": sequence,
        "summary": summary,
        "topology": _load(os.path.join(ROOT, "apps", app, "topology.json")),
    }


def guard_confirmed(app: str, budget: int = HISTORICAL_BUDGET) -> list[str]:
    path = os.path.join(
        ROOT, V0320_PUBLICATION.replace("/", os.sep), "evidence", app, "metrics.json")
    payload = _load(path)
    for row in payload.get("runs") or []:
        if row.get("policy") == GUARD and _int(row.get("budget")) == budget and _int(row.get("seed")) == SEED:
            return list(row.get("confirmed_bugs") or [])
    return []


def template_bug_ids(app: str) -> dict[int, str]:
    manifest = _load(os.path.join(ROOT, "apps", app, "bugs.manifest.json"))
    found = {}
    for bug in manifest.get("bugs") or []:
        number = template_number(bug.get("id") or "")
        if number in TEMPLATE_NUMBERS and number not in found:
            found[number] = bug["id"]
    return found


def _group_sequences(sequence: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for event in sequence:
        seq_id = event.get("sequence_instance_id")
        if not seq_id:
            continue
        grouped.setdefault(seq_id, []).append(event)
    return grouped


def _cycle_record(seq_id: str, events: list[dict]) -> dict | None:
    starts = [event for event in events if event.get("event") == "branch_start"]
    horizons = [event for event in events if event.get("event") == "sequence_horizon_reached"]
    escapes = [event for event in events if event.get("event") == "return_cycle_escape"]
    terminals = [
        event for event in events
        if event.get("event") == "sequence_terminal"
        and event.get("outcome") == "return_cycle_abandoned"
    ]
    if not starts or not escapes or not terminals:
        return None
    return {
        "sequence_instance_id": seq_id,
        "branch_key": starts[0].get("branch_key") or "",
        "branch_start_step": _int(starts[0].get("step")),
        "horizon_step": None if not horizons else _int(horizons[0].get("step")),
        "return_attempt_count": sum(1 for event in events if event.get("event") == "return_attempt"),
        "return_cycle_escape_step": _int(escapes[0].get("step")),
        "terminal_step": _int(terminals[0].get("step")),
        "terminal_outcome": terminals[0].get("outcome") or "",
        "has_horizon": bool(horizons),
        "events_after_terminal": [
            {
                "step": event.get("step"),
                "event": event.get("event"),
            }
            for event in events
            if _int(event.get("step")) > _int(terminals[0].get("step"))
        ],
    }


def waypoint_escapes(sequence: list[dict]) -> list[dict]:
    rows = [event for event in sequence if event.get("event") == "return_waypoint_frontier_escape"]
    return sorted(rows, key=lambda event: _int(event.get("step")))


def post_escape_cycles(sequence: list[dict], escape_step: int) -> list[dict]:
    found = []
    for seq_id, events in _group_sequences(sequence).items():
        record = _cycle_record(seq_id, events)
        if record is None:
            continue
        if record["branch_start_step"] <= escape_step:
            continue
        if record["return_cycle_escape_step"] < escape_step:
            continue
        found.append(record)
    return sorted(found, key=lambda record: (record["terminal_step"], record["branch_start_step"]))


def _streak(flags: list[bool]) -> int:
    best = current = 0
    for flag in flags:
        if flag:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def _edge_key(step: dict) -> tuple[str, str, str]:
    src_name, _src_norm, _src_values = url_parts(step.get("src_url") or "")
    dst_name, _dst_norm, _dst_values = url_parts(step.get("dst_url") or "")
    return (src_name, action_eid(step), dst_name)


def analyze_cell(bundle: dict, *, guard_ids: list[str] | None = None, templates: dict | None = None) -> dict:
    app = bundle["app"]
    budget = int(bundle["budget"])
    steps = step_rows(bundle["events"])
    by_index = {_int(step.get("index")): step for step in steps}
    sequence = bundle["sequence"]
    summary = bundle["summary"] or {}
    graph = build_navigation_graph(bundle["topology"])
    escapes = waypoint_escapes(sequence)
    confirmed = list(summary.get("confirmed_bugs") or [])
    templates = templates if templates is not None else template_bug_ids(app)
    guard_ids = list(guard_confirmed(app) if guard_ids is None else guard_ids)
    template_ids = [templates[number] for number in TEMPLATE_NUMBERS if number in templates]
    lost_templates = [bug_id for bug_id in template_ids if bug_id not in set(confirmed)]
    first_steps = summary.get("first_step_by_bug") or {}
    template_confirm_steps = [
        _int(first_steps.get(bug_id))
        for bug_id in template_ids
        if bug_id in set(confirmed) and bug_id in first_steps and _int(first_steps.get(bug_id)) >= 0
    ]
    if not escapes:
        return {
            "app": app,
            "budget": budget,
            "first_waypoint_escape_step": None,
            "template_589_recovered": not lost_templates and bool(template_ids),
            "template_lost": lost_templates,
            "all_guard_bugs_retained": set(guard_ids) <= set(confirmed),
            "persistent_sink": False,
            "productive_entity_reentry": False,
            "protocol_note": "no waypoint escape",
            "static": _empty_static(graph),
        }
    first = escapes[0]
    escape_step = _int(first.get("step"))
    escape_state = by_index.get(escape_step) or {}
    waypoint_cluster = first.get("waypoint_cluster") or first.get("cluster_id") or ""
    waypoint_nodes = match_nodes(escape_state.get("dst_url") or "", graph)
    waypoint_node = waypoint_nodes[0]["id"] if len(waypoint_nodes) == 1 else ""
    next_step = by_index.get(escape_step + 1) or {}
    cycles = post_escape_cycles(sequence, escape_step)
    first_cycle = cycles[0] if cycles else None
    horizon_cycles = [cycle for cycle in cycles if cycle["has_horizon"]]
    horizon_cycle = horizon_cycles[-1] if horizon_cycles else None
    post_abandon_step = None if first_cycle is None else first_cycle["terminal_step"]
    suffix = [step for step in steps if _int(step.get("index")) > (post_abandon_step if post_abandon_step is not None else 10 ** 9)]
    static_match = match_suffix_scc(graph, suffix, waypoint_node)
    sink_entry = static_match["sink_entry_step"]
    if sink_entry is None and post_abandon_step is not None and static_match["visit_fraction"] < DOMINANCE_THRESHOLD:
        sink_entry = post_abandon_step
    residual_keys = list(first.get("local_residual_keys") or []) + list(first.get("structural_residual_keys") or [])
    residual_eids = eids_from_keys(residual_keys)
    tried_before = []
    for step in steps:
        if _int(step.get("index")) >= escape_step:
            continue
        if step.get("src_cluster") != waypoint_cluster:
            continue
        eid = action_eid(step)
        if eid and eid not in tried_before:
            tried_before.append(eid)
    residual_tried_before = [eid for eid in residual_eids if eid in set(tried_before)]
    topo_actions = set()
    if waypoint_node:
        node = graph["nodes"][waypoint_node]
        topo_actions.update(node.get("eligible_buttons") or [])
        topo_actions.update(action.get("testid") for action in node.get("branch_actions") or [])
        topo_actions.update(
            edge["action"] for edge in graph["edges"]
            if edge["src"] == waypoint_node or edge["dst"] == waypoint_node
        )
    entity_reentry_steps = [
        _int(step.get("index"))
        for step in suffix
        if step.get("dst_cluster") == waypoint_cluster
    ]
    residual_action_steps = [
        _int(step.get("index"))
        for step in steps
        if post_abandon_step is not None
        and _int(step.get("index")) > post_abandon_step
        and step.get("src_cluster") == waypoint_cluster
        and action_eid(step) in set(residual_eids)
    ]
    after_entry_reentry = [step for step in entity_reentry_steps if sink_entry is not None and step > sink_entry]
    after_entry_residual = [step for step in residual_action_steps if sink_entry is not None and step > sink_entry]
    productive = bool(after_entry_reentry and after_entry_residual and residual_eids and not residual_tried_before)
    productive_step = after_entry_residual[0] if productive else None
    recurrence = _suffix_recurrence(suffix, steps, static_match)
    abandoned_id = "" if first_cycle is None else first_cycle["sequence_instance_id"]
    abandoned_continues = bool(first_cycle and first_cycle["events_after_terminal"])
    horizon_continues = bool(horizon_cycle and horizon_cycle["events_after_terminal"])
    new_branch_steps = [
        _int(event.get("step"))
        for event in sequence
        if event.get("event") == "branch_start"
        and post_abandon_step is not None
        and _int(event.get("step")) > post_abandon_step
    ]
    quartile = _final_quartile(steps)
    quartile_scc_count = 0
    quartile_idle_scc = 0
    quartile_counts: dict[str, int] = {}
    for step in quartile:
        matched = match_nodes(step.get("dst_url") or "", graph)
        number = graph["scc_of"].get(matched[0]["id"]) if len(matched) == 1 else None
        if number is None:
            continue
        component = graph["components"][number]
        key = scc_id(component)
        quartile_counts[key] = quartile_counts.get(key, 0) + 1
        if key == static_match["scc_id"]:
            quartile_scc_count += 1
            if not (step.get("active_branch") or ""):
                quartile_idle_scc += 1
    best_quartile = ""
    best_quartile_count = -1
    quartile_tie = False
    for key, count in quartile_counts.items():
        if count > best_quartile_count:
            best_quartile = key
            best_quartile_count = count
            quartile_tie = False
        elif count == best_quartile_count:
            quartile_tie = True
    final_same = (
        bool(static_match["scc_id"])
        and not quartile_tie
        and best_quartile == static_match["scc_id"]
        and meets_threshold(quartile_scc_count, len(quartile))
    )
    idle_fraction = _frac(quartile_idle_scc, quartile_scc_count)
    later_escapes = [event for event in escapes if _int(event.get("step")) > escape_step]
    cycle_after = [
        event for event in sequence
        if event.get("event") == "return_cycle_escape"
        and event.get("sequence_instance_id")
        and _int(event.get("step")) > escape_step
    ]
    result = {
        "app": app,
        "budget": budget,
        "seed": SEED,
        "policy": CANDIDATE,
        "first_waypoint_escape_step": escape_step,
        "first_escape_entity_cluster": waypoint_cluster,
        "first_escape_entity_node": waypoint_node,
        "first_escape_match_strength": first.get("waypoint_match_strength") or "",
        "first_escape_stack_depth": first.get("stack_depth"),
        "local_residual_count": first.get("local_residual_count"),
        "structural_residual_count": first.get("structural_residual_count"),
        "residual_eids": residual_eids,
        "residual_tried_before_escape": residual_tried_before,
        "residual_known_on_topology": [eid for eid in residual_eids if eid in topo_actions],
        "next_action_eid": action_eid(next_step),
        "next_action_label": next_step.get("last_label") or next_step.get("decision_mode") or "",
        "waypoint_escape_count": len(escapes),
        "second_waypoint_escape_count": len(later_escapes),
        "return_cycle_escape_count_after_first_escape": len(cycle_after),
        "template_ids": template_ids,
        "template_lost": lost_templates,
        "template_589_recovered": not lost_templates and bool(template_ids),
        "template_first_confirm_step": min(template_confirm_steps) if template_confirm_steps and not lost_templates else None,
        "confirmed_bugs": confirmed,
        "guard_confirmed": guard_ids,
        "all_guard_bugs_retained": set(guard_ids) <= set(confirmed) if guard_ids else False,
        "post_abandon_step": post_abandon_step,
        "first_post_escape_cycle": first_cycle,
        "horizon_cycle": horizon_cycle,
        "abandoned_sequence_continues": abandoned_continues,
        "horizon_sequence_continues": horizon_continues,
        "active_sequence_after_abandonment": bool(new_branch_steps),
        "new_branch_start_steps_after_abandon": new_branch_steps,
        "new_branch_start_count_after_abandon": len(new_branch_steps),
        "suffix_steps": len(suffix),
        "suffix_unique_urls": recurrence["unique_urls"],
        "suffix_unique_states": recurrence["unique_states"],
        "dominant_scc_id": static_match["scc_id"],
        "dominant_scc_size": static_match["scc_size"],
        "dominant_scc_visit_count": static_match["visit_count"],
        "dominant_scc_visit_fraction": static_match["visit_fraction"],
        "dominant_edge": recurrence["dominant_edge"],
        "dominant_edge_count": recurrence["dominant_edge_count"],
        "dominant_edge_fraction": recurrence["dominant_edge_fraction"],
        "repeated_edge_count": recurrence["repeated_edge_count"],
        "no_new_url_streak_max": recurrence["no_new_url_streak_max"],
        "no_new_state_streak_max": recurrence["no_new_state_streak_max"],
        "suffix_page_histogram": recurrence["page_histogram"],
        "suffix_edge_histogram": recurrence["edge_histogram"],
        "sink_entry_step": sink_entry,
        "entity_reentry_count_after_abandon": len(entity_reentry_steps),
        "entity_reentry_steps_after_abandon": entity_reentry_steps,
        "entity_residual_action_count_after_abandon": len(residual_action_steps),
        "entity_residual_action_steps_after_abandon": residual_action_steps,
        "productive_entity_reentry": productive,
        "productive_reentry_step": productive_step,
        "final_quartile_steps": len(quartile),
        "final_quartile_same_scc": final_same,
        "final_quartile_scc_fraction": _frac(quartile_scc_count, len(quartile)),
        "final_quartile_idle_visit_fraction": idle_fraction,
        "static": static_match,
        "persistent_sink": False,
        "sequence_scoped_return_cycle_after_escape": first_cycle is not None,
    }
    result["persistent_sink"] = cell_persistent(result, semantic_unchanged=True)
    return result


def _empty_static(graph: dict) -> dict:
    return {
        "node_count": len(graph["nodes"]),
        "edge_count": len(graph["edges"]),
        "scc_count": len(graph["components"]),
        "matched": False,
        "scc_id": "",
        "scc_size": 0,
        "closed": False,
        "outgoing_edge_count": 0,
        "entity_reachable": False,
        "entity_in_scc": False,
        "shortest_entity_path_length": None,
        "shortest_entity_path": [],
        "path_traverses_form_hub": False,
        "productive_exit_candidate_edge_count": 0,
        "classification": "no_dominant_scc",
        "visit_count": 0,
        "visit_fraction": 0.0,
        "tie": False,
        "sink_entry_step": None,
        "recurrent_pages": [],
    }


def match_suffix_scc(graph: dict, suffix: list[dict], waypoint_node: str) -> dict:
    histogram: dict[str, int] = {}
    assignments = []
    for step in suffix:
        matched = match_nodes(step.get("dst_url") or "", graph)
        filename, _normalized, _values = url_parts(step.get("dst_url") or "")
        histogram[filename] = histogram.get(filename, 0) + 1
        node_id = matched[0]["id"] if len(matched) == 1 else ""
        number = graph["scc_of"].get(node_id) if node_id else None
        assignments.append((step, filename, node_id, number))
    recurrent_pages = sorted(page for page, count in histogram.items() if count >= 2)
    candidate_numbers = set()
    for _step, filename, _node_id, number in assignments:
        if filename in recurrent_pages and number is not None:
            candidate_numbers.add(number)
    coverage: dict[int, int] = {}
    for _step, _filename, _node_id, number in assignments:
        if number is None or number not in candidate_numbers:
            continue
        coverage[number] = coverage.get(number, 0) + 1
    best_number = None
    best_count = -1
    tie = False
    for number, count in coverage.items():
        if count > best_count:
            best_number = number
            best_count = count
            tie = False
        elif count == best_count:
            tie = True
    total = len(suffix)
    if best_number is None:
        empty = _empty_static(graph)
        empty["recurrent_pages"] = recurrent_pages
        return empty
    component = graph["components"][best_number]
    outgoing = graph["outgoing"].get(best_number) or []
    members = set(component)
    entity_in = bool(waypoint_node and waypoint_node in members)
    path = _bfs_path(graph, component, waypoint_node) if waypoint_node else None
    form_nodes = {node_id for node_id in graph["nodes"] if is_form_hub(node_id, graph)}
    traverses = False
    if path:
        for node_id in path[:-1]:
            if node_id in form_nodes:
                traverses = True
    productive_exits = 0
    for edge in outgoing:
        if waypoint_node and _reachable(graph, [edge["dst"]], waypoint_node):
            productive_exits += 1
    form_hub_to_entity = bool(waypoint_node) and any(
        edge["parent_return"] and edge["dst"] == waypoint_node and edge["src"] in form_nodes and edge["src"] in members
        for edge in graph["edges"]
    )
    sink_entry = None
    for step, _filename, _node_id, number in assignments:
        if number == best_number:
            sink_entry = _int(step.get("index"))
            break
    fraction = _frac(best_count, total)
    classification = classify_static(best_count / total if total else 0.0, len(outgoing), tie, True)
    return {
        "node_count": len(graph["nodes"]),
        "edge_count": len(graph["edges"]),
        "scc_count": len(graph["components"]),
        "condensation_edge_count": len(graph["condensation"]),
        "matched": classification != "no_dominant_scc",
        "scc_id": "" if tie else scc_id(component),
        "scc_members": [] if tie else component,
        "scc_size": 0 if tie else len(component),
        "closed": (not tie) and len(outgoing) == 0,
        "outgoing_edge_count": 0 if tie else len(outgoing),
        "outgoing_edges": [] if tie else [
            {"src": edge["src"], "dst": edge["dst"], "action": edge["action"]}
            for edge in outgoing
        ],
        "entity_reachable": bool(path),
        "entity_in_scc": entity_in and not tie,
        "shortest_entity_path_length": None if path is None or tie else (len(path) - 1),
        "shortest_entity_path": [] if path is None or tie else path,
        "path_traverses_form_hub": traverses and not tie,
        "form_hub_edge_to_entity": form_hub_to_entity and not tie,
        "productive_exit_candidate_edge_count": 0 if tie else productive_exits,
        "classification": classification,
        "visit_count": 0 if tie else best_count,
        "visit_fraction": 0.0 if tie else fraction,
        "tie": tie,
        "sink_entry_step": None if tie else sink_entry,
        "recurrent_pages": recurrent_pages,
        "form_hub_nodes": sorted(form_nodes),
    }


def _suffix_recurrence(suffix: list[dict], all_steps: list[dict], static_match: dict) -> dict:
    ordered = sorted(all_steps, key=lambda step: _int(step.get("index")))
    seen_urls = set()
    seen_states = set()
    suffix_start = _int(suffix[0].get("index")) if suffix else 10 ** 9
    for step in ordered:
        if _int(step.get("index")) >= suffix_start:
            break
        _filename, normalized, _values = url_parts(step.get("dst_url") or "")
        seen_urls.add(normalized)
        if step.get("dst_sig"):
            seen_states.add(step.get("dst_sig"))
    url_flags = []
    state_flags = []
    pages: dict[str, int] = {}
    edges: dict[str, int] = {}
    edge_seen = set()
    repeated = 0
    unique_urls = set()
    unique_states = set()
    for step in suffix:
        filename, normalized, _values = url_parts(step.get("dst_url") or "")
        pages[filename] = pages.get(filename, 0) + 1
        unique_urls.add(normalized)
        url_flags.append(normalized in seen_urls)
        seen_urls.add(normalized)
        state = step.get("dst_sig") or ""
        unique_states.add(state)
        state_flags.append(bool(state) and state in seen_states)
        if state:
            seen_states.add(state)
        edge = _edge_key(step)
        label = f"{edge[0]}|{edge[1]}|{edge[2]}"
        edges[label] = edges.get(label, 0) + 1
        if edge in edge_seen:
            repeated += 1
        edge_seen.add(edge)
    dominant_edge = ""
    dominant_count = 0
    for label, count in edges.items():
        if count > dominant_count:
            dominant_edge = label
            dominant_count = count
    page_items = sorted(pages.items(), key=lambda item: (-item[1], item[0]))
    edge_items = sorted(edges.items(), key=lambda item: (-item[1], item[0]))[:12]
    return {
        "unique_urls": len(unique_urls),
        "unique_states": len(unique_states),
        "dominant_edge": dominant_edge,
        "dominant_edge_count": dominant_count,
        "dominant_edge_fraction": _frac(dominant_count, len(suffix)),
        "repeated_edge_count": repeated,
        "no_new_url_streak_max": _streak(url_flags),
        "no_new_state_streak_max": _streak(state_flags),
        "page_histogram": [{"page": page, "count": count} for page, count in page_items],
        "edge_histogram": [{"edge": edge, "count": count} for edge, count in edge_items],
        "dominant_scc_id": static_match.get("scc_id") or "",
    }


def _final_quartile(steps: list[dict]) -> list[dict]:
    if not steps:
        return []
    count = max(1, int(len(steps) * FINAL_QUARTILE))
    ordered = sorted(steps, key=lambda step: _int(step.get("index")))
    return ordered[-count:]


def cell_persistent(metrics: dict, *, semantic_unchanged: bool) -> bool:
    if not semantic_unchanged:
        return False
    return bool(
        metrics.get("sequence_scoped_return_cycle_after_escape")
        and meets_threshold(
            int(metrics.get("dominant_scc_visit_count") or 0),
            int(metrics.get("suffix_steps") or 0),
        )
        and metrics.get("final_quartile_same_scc")
        and not metrics.get("productive_entity_reentry")
        and not metrics.get("template_589_recovered")
        and not metrics.get("abandoned_sequence_continues")
    )


def _budget_map(rows: list[dict]) -> dict[str, dict[int, dict]]:
    grouped: dict[str, dict[int, dict]] = {}
    for row in rows:
        grouped.setdefault(row["app"], {})[int(row["budget"])] = row
    return grouped


def _reentry_before_recovery(cell: dict) -> bool:
    if not cell.get("productive_entity_reentry"):
        return False
    reentry = cell.get("productive_reentry_step")
    confirm = cell.get("template_first_confirm_step")
    if reentry is None or confirm is None:
        return False
    return int(reentry) <= int(confirm)


def derive_v0322_diagnosis(
    rows: list[dict],
    *,
    protocol_valid: bool = True,
    semantic_unchanged: bool = True,
) -> dict:
    """Derive the only allowed diagnostic conclusion from cell metrics."""
    reasons = []
    if not protocol_valid:
        reasons.append("protocol_invalid")
    if not semantic_unchanged:
        reasons.append("semantic_change")
    grouped = _budget_map(rows)
    expected = {120, 240, 480}
    for app in POSITIVE_TARGETS:
        have = set(grouped.get(app) or ())
        if have != expected and not reasons:
            reasons.append("missing_cell")
        elif have != expected:
            reasons.append("missing_cell")
    if reasons:
        return _diagnosis("protocol_invalid", {
            "reasons": sorted(set(reasons)),
            "losing_targets": [],
            "contrast_targets": [],
            "first_recovery_budget": {},
        })
    losers = [
        app for app in POSITIVE_TARGETS
        if not grouped[app][120].get("template_589_recovered")
    ]
    contrasts = [
        app for app in POSITIVE_TARGETS
        if grouped[app][120].get("template_589_recovered")
    ]
    prefix_ok = all(
        grouped[app][budget].get("trajectory_prefix_match", True)
        for app in POSITIVE_TARGETS
        for budget in DIAGNOSTIC_BUDGETS
    )
    recovery_budget = {}
    reentry_ok = {}
    for app in losers:
        found = None
        for budget in DIAGNOSTIC_BUDGETS:
            if grouped[app][budget].get("template_589_recovered"):
                found = budget
                break
        recovery_budget[app] = found
        reentry_ok[app] = bool(found is not None and _reentry_before_recovery(grouped[app][found]))
    contrasts_hold = [
        app for app in contrasts
        if any(
            grouped[app][budget].get("template_589_recovered")
            and grouped[app][budget].get("productive_entity_reentry")
            for budget in DIAGNOSTIC_BUDGETS
        )
    ]
    all_losers_recover = bool(losers) and all(recovery_budget[app] is not None for app in losers)
    delay_reentry = bool(losers) and all(reentry_ok[app] for app in losers)
    retained_loss = bool(losers) and all(
        not grouped[app][budget].get("template_589_recovered")
        for app in losers
        for budget in DIAGNOSTIC_BUDGETS
    )
    persistent_cells = bool(losers) and all(
        cell_persistent(grouped[app][480], semantic_unchanged=semantic_unchanged)
        for app in losers
    )
    no_reentry = bool(losers) and all(
        not grouped[app][480].get("productive_entity_reentry")
        for app in losers
    )
    after_terminal = bool(losers) and all(
        grouped[app][480].get("sequence_scoped_return_cycle_after_escape")
        and not grouped[app][480].get("abandoned_sequence_continues")
        and float(grouped[app][480].get("final_quartile_idle_visit_fraction") or 0) >= DOMINANCE_THRESHOLD
        for app in losers
    )
    facts = {
        "reasons": [],
        "losing_targets": losers,
        "contrast_targets": contrasts,
        "first_recovery_budget": recovery_budget,
        "contrasts_preserved": contrasts_hold,
        "trajectory_prefix_match": prefix_ok,
        "retained_template_loss": retained_loss,
        "persistent_at_b480": persistent_cells,
        "no_productive_reentry_at_b480": no_reentry,
        "ordinary_policy_recurrence": after_terminal,
    }
    if not prefix_ok:
        facts["reasons"] = ["trajectory_prefix_mismatch"]
        return _diagnosis("mixed_or_inconclusive", facts)
    if all_losers_recover and delay_reentry and semantic_unchanged:
        if contrasts and len(contrasts_hold) != len(contrasts):
            facts["reasons"] = ["contrast_regression"]
            return _diagnosis("mixed_or_inconclusive", facts)
        return _diagnosis("budget_delay", facts)
    if (
        retained_loss
        and persistent_cells
        and no_reentry
        and after_terminal
        and contrasts
        and len(contrasts_hold) == len(contrasts)
    ):
        return _diagnosis("persistent_post_terminal_sink", facts)
    facts["reasons"] = ["no_single_mechanism"]
    return _diagnosis("mixed_or_inconclusive", facts)


def _diagnosis(name: str, facts: dict) -> dict:
    return {
        "diagnostic_conclusion": name,
        "meaning": DIAGNOSIS_MEANING[name],
        "promotion_readiness": "not_ready",
        "product_default_changed": False,
        "fresh_validation": False,
        "facts": facts,
    }


def public_copy(conclusion: str) -> str:
    copies = {
        "persistent_post_terminal_sink": (
            "v0.3.22 没有改策略，只分析 v0.3.21 的分裂结果。Campus/Studio 在 "
            "sequence-scoped return cycle 已经被正确 abandon 后，普通探索仍进入重复 "
            "导航吸引子；到 b480 仍未重新获得原 entity residual frontier。"
            "Warehouse/Booking 则保留了回到 entity 的生产性路径。"
            "这是已检查目标上的 failure diagnosis，不是新修复，也不是 fresh validation。"
        ),
        "budget_delay": (
            "v0.3.22 没有改策略。提高诊断预算后，Campus/Studio 在冻结候选下重新进入 "
            "entity residual frontier 并恢复 5/8/9，因此 v0.3.21 的分裂更符合有限预算 "
            "延迟，而不是 b480 内持续的 post-terminal sink。"
        ),
        "mixed_or_inconclusive": (
            "v0.3.22 没有改策略。b240/b480 的分裂没有收敛到单一机制，诊断为 "
            "mixed_or_inconclusive。这不是新修复，也不是 fresh validation。"
        ),
        "protocol_invalid": (
            "v0.3.22 诊断协议未能成立，结论为 protocol_invalid。没有改策略，也没有新修复。"
        ),
    }
    return copies.get(conclusion, copies["mixed_or_inconclusive"])


def build_protocol(freeze: dict | None = None) -> dict:
    freeze = freeze or freeze_status()
    return {
        "name": "v0.3.22 post-escape sink attractor analysis",
        "version": "v0.3.22",
        "date": "2026-09-24",
        "starting_head": STARTING_HEAD,
        "executed": False,
        "question_kind": "analysis-only",
        "research_question": (
            "Why does the same first Return-Waypoint Frontier Escape repair "
            "two of the four v0.3.20 positive targets and not the other two?"
        ),
        "hypotheses": {
            "H1": "persistent_post_terminal_sink",
            "H2": "budget_delay",
            "H3": "mixed_or_inconclusive",
            "H4": "protocol_invalid",
        },
        "hypothesis_definitions": {
            "persistent_post_terminal_sink": DIAGNOSIS_MEANING["persistent_post_terminal_sink"],
            "budget_delay": DIAGNOSIS_MEANING["budget_delay"],
            "mixed_or_inconclusive": DIAGNOSIS_MEANING["mixed_or_inconclusive"],
            "protocol_invalid": DIAGNOSIS_MEANING["protocol_invalid"],
        },
        "not": [
            "a candidate repair",
            "a fresh validation round",
            "permission to change v0.3.21 candidate semantics",
            "permission to change v0.3.20 target or generator semantics",
            "permission to generate new targets",
            "permission to change the product default",
            "permission to add a global loop guard",
            "an infinite-loop proof",
        ],
        "v0_3_21_immutable": {
            "outcome": "C",
            "sha": STARTING_HEAD,
            "publication": V0321_PUBLICATION,
            "candidate": CANDIDATE,
            "candidate_freeze": CANDIDATE_FREEZE,
            "candidate_source": CANDIDATE_SOURCE,
            "candidate_source_sha256": freeze["candidate_source_sha256"],
            "candidate_freeze_sha256": freeze["candidate_freeze_sha256"],
            "product_default_changed": False,
        },
        "v0_3_20_immutable": {
            "outcome": "C",
            "publication": V0320_PUBLICATION,
            "suite_freeze": SUITE_FREEZE,
            "suite_freeze_sha256": freeze["suite_freeze_sha256"],
            "target_freeze_sha256": freeze["target_freeze_sha256"],
        },
        "dominance_threshold": DOMINANCE_THRESHOLD,
        "final_quartile": FINAL_QUARTILE,
        "recurrent_page_minimum_visits": 2,
        "matrix": {
            "candidate": CANDIDATE,
            "targets": list(POSITIVE_TARGETS),
            "budgets": list(DIAGNOSTIC_BUDGETS),
            "seed": SEED,
            "cells": [{"app": app, "budget": budget, "seed": SEED} for app, budget in CELLS],
            "cells_total": len(CELLS),
            "historical_reference_budget": HISTORICAL_BUDGET,
            "excluded": ["C1", "guard rerun", "v0.3.19 rerun", "negative-control rerun", "budgets other than 240 and 480"],
        },
        "operational_definitions": {
            "navigation_edge": "topology edge whose source and destination node ids differ, including parent-return edges",
            "relevant_abandonment": "earliest sequence-scoped return_cycle_escape after the first waypoint escape whose branch_start is after that escape and whose sequence_terminal outcome is return_cycle_abandoned",
            "suffix": "step rows with index strictly greater than the relevant abandonment step",
            "dominant_scc": "SCC that contains a recurrent suffix page and has the greatest suffix visit coverage; equal coverage is ambiguous",
            "form_hub": "empty-entity node with a parent_return edge to a non-empty-entity node and an incoming page-changing edge from an empty-entity node",
            "productive_reentry": "after sink entry, the run reaches the first-escape entity cluster and executes a residual frontier action recorded on that escape",
            "sink_entry": "first suffix step whose destination lies in the dominant SCC when coverage meets the threshold; otherwise the abandonment step",
            "ordinary_policy_recurrence": "the abandoned sequence has no later events, and at least the dominance threshold of final-quartile dominant-SCC visits have an empty active branch",
            "horizon_cycle": "latest post-escape sequence that has branch_start, sequence_horizon_reached, return_cycle_escape, and terminal return_cycle_abandoned",
            "template_589": "manifest bug ids whose trailing integer is 5, 8, or 9",
            "guard_retained": "v0.3.20 guard budget-120 confirmed set is a subset of the cell confirmed set",
            "persistent_sink": [
                "sequence-scoped return_cycle_escape after the first waypoint escape",
                "dominant suffix SCC coverage >= 0.60",
                "the same SCC remains dominant through the final 25 percent of the run at coverage >= 0.60",
                "no productive entity re-entry after sink entry",
                "template 5/8/9 remains unrecovered",
                "no candidate, source, or target semantic change",
            ],
            "budget_delay": [
                "budget-120 template 5/8/9 lost",
                "budget 240 or 480 recovers template 5/8/9",
                "productive entity re-entry step is at or before the first recovered template confirmation",
                "no protocol, target, or candidate change",
            ],
        },
        "classifications": [
            "closed_scc",
            "policy_attractor_with_static_exit",
            "no_dominant_scc",
            "ambiguous",
        ],
        "diagnostic_conclusion_values": list(CONCLUSIONS),
        "publication": PUBLICATION_DIR,
        "runs": RUN_DIR,
        "validation": VALIDATION_DIR,
        "product_default_changed": False,
        "promotion_readiness": "not_ready",
        "public_copy": {name: public_copy(name) for name in CONCLUSIONS},
    }


def _cycle_public(cycle: dict | None) -> dict:
    if not cycle:
        return {}
    return {
        "sequence_instance_id": cycle["sequence_instance_id"],
        "branch_key": cycle["branch_key"],
        "branch_start_step": cycle["branch_start_step"],
        "horizon_step": cycle["horizon_step"],
        "return_attempt_count": cycle["return_attempt_count"],
        "return_cycle_escape_step": cycle["return_cycle_escape_step"],
        "terminal_step": cycle["terminal_step"],
        "terminal_outcome": cycle["terminal_outcome"],
        "events_after_terminal": cycle["events_after_terminal"],
        "active_same_sequence_afterward": bool(cycle["events_after_terminal"]),
    }


def build_historical_audit() -> dict:
    targets = []
    for app in POSITIVE_TARGETS:
        metrics = analyze_cell(load_bundle(app, HISTORICAL_BUDGET, historical=True))
        targets.append({
            "app": app,
            "budget": HISTORICAL_BUDGET,
            "first_waypoint_escape_step": metrics["first_waypoint_escape_step"],
            "first_escape_entity_cluster": metrics["first_escape_entity_cluster"],
            "first_escape_entity_node": metrics["first_escape_entity_node"],
            "next_action_eid": metrics["next_action_eid"],
            "next_action_label": metrics["next_action_label"],
            "match_strength": metrics["first_escape_match_strength"],
            "stack_depth": metrics["first_escape_stack_depth"],
            "local_residual_count": metrics["local_residual_count"],
            "structural_residual_count": metrics["structural_residual_count"],
            "residual_eids": metrics["residual_eids"],
            "residual_tried_before_escape": metrics["residual_tried_before_escape"],
            "waypoint_escape_count": metrics["waypoint_escape_count"],
            "template_lost": metrics["template_lost"],
            "template_589_recovered": metrics["template_589_recovered"],
            "all_guard_bugs_retained": metrics["all_guard_bugs_retained"],
            "first_post_escape_cycle": _cycle_public(metrics["first_post_escape_cycle"]),
            "horizon_cycle": _cycle_public(metrics["horizon_cycle"]),
            "sequence_events_after_horizon_terminal": (
                (metrics["horizon_cycle"] or {}).get("events_after_terminal") or []
            ),
            "suffix_dominant_pages": metrics["suffix_page_histogram"][:8],
            "suffix_dominant_edges": metrics["suffix_edge_histogram"][:8],
            "entity_reentry_count_after_abandon": metrics["entity_reentry_count_after_abandon"],
            "entity_residual_action_count_after_abandon": metrics["entity_residual_action_count_after_abandon"],
            "productive_entity_reentry": metrics["productive_entity_reentry"],
            "dominant_scc_visit_fraction": metrics["dominant_scc_visit_fraction"],
            "static_classification": metrics["static"]["classification"],
            "post_abandon_step": metrics["post_abandon_step"],
            "active_sequence_after_abandonment": metrics["active_sequence_after_abandonment"],
        })
    return {
        "version": "v0.3.22",
        "source_publication": V0321_PUBLICATION,
        "source_round": "v0.3.21",
        "source_outcome": "C",
        "budget": HISTORICAL_BUDGET,
        "seed": SEED,
        "candidate_policy": CANDIDATE,
        "derived_from_events": True,
        "targets": targets,
    }


def build_static_report(rows: list[dict]) -> dict:
    targets = {}
    for row in rows:
        app = row["app"]
        bucket = targets.setdefault(app, {"budgets": {}})
        static = row["static"]
        bucket["node_count"] = static["node_count"]
        bucket["edge_count"] = static["edge_count"]
        bucket["scc_count"] = static["scc_count"]
        bucket["budgets"][str(row["budget"])] = {
            "recurrent_pages": static.get("recurrent_pages") or [],
            "matched_scc_size": static.get("scc_size"),
            "matched_scc_closed": static.get("closed"),
            "outgoing_edge_count": static.get("outgoing_edge_count"),
            "entity_waypoint_reachable": static.get("entity_reachable"),
            "entity_in_scc": static.get("entity_in_scc"),
            "shortest_entity_path_length": static.get("shortest_entity_path_length"),
            "shortest_entity_path": static.get("shortest_entity_path") or [],
            "path_traverses_form_hub": static.get("path_traverses_form_hub"),
            "form_hub_edge_to_entity": static.get("form_hub_edge_to_entity"),
            "productive_exit_candidate_edge_count": static.get("productive_exit_candidate_edge_count"),
            "classification": static.get("classification"),
            "dominant_scc_visit_fraction": row.get("dominant_scc_visit_fraction"),
            "tie": static.get("tie"),
        }
    return {
        "version": "v0.3.22",
        "dominance_threshold": DOMINANCE_THRESHOLD,
        "navigation_edge": "src != dst",
        "targets": targets,
    }


def compare_prefix(historical_steps: list[dict], later_steps: list[dict], limit: int = HISTORICAL_BUDGET) -> bool:
    hist = sorted(step_rows(historical_steps), key=lambda step: _int(step.get("index")))
    later = sorted(step_rows(later_steps), key=lambda step: _int(step.get("index")))
    if len(later) < limit or len(hist) < limit:
        return False
    for index in range(limit):
        left = hist[index]
        right = later[index]
        if _int(left.get("index")) != _int(right.get("index")):
            return False
        if action_eid(left) != action_eid(right):
            return False
        if url_parts(left.get("dst_url") or "")[1] != url_parts(right.get("dst_url") or "")[1]:
            return False
    return True
