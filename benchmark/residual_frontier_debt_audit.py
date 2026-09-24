"""Code-derived v0.3.22 residual-frontier audit for the v0.3.23 protocol.

Reads committed publications and explorer source. Does not choose actions and
does not import the v0.3.23 candidate.
"""
from __future__ import annotations

import json
import os

from benchmark.algorithm_freeze import sha256_file
from ghostqa.exploration.planner import pending_opportunity_counts
from ghostqa.state.graph import StateEdge, StateGraph

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V0321 = os.path.join(ROOT, "experiments", "published", "return-waypoint-frontier-v0.3.21")
V0322 = os.path.join(ROOT, "experiments", "published", "post-escape-sink-v0.3.22")
VALIDATION = os.path.join(ROOT, "experiments", "validation", "v0.3.23")
CANDIDATE_SOURCE = os.path.join(
    ROOT, "ghostqa", "exploration", "return_waypoint_frontier_guard.py")
CANDIDATE_FREEZE = os.path.join(
    ROOT, "experiments", "frozen", "ghost-return-waypoint-frontier-v0.3.21", "freeze.json")
EXPLORER = os.path.join(ROOT, "ghostqa", "exploration", "explorer.py")
TARGETS = ("buggy-campus", "buggy-warehouse", "buggy-studio", "buggy-booking")
TEMPLATE_NUMBERS = (5, 8, 9)
CLICK_KINDS = ("button", "click")


def _load(path: str):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write(path: str, payload) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def normalize_residual_tokens(local_keys, structural_keys, waypoint_cluster: str) -> list:
    """Collapse button/click duplicates to cluster:role:eid. No hardcoded eids."""
    seen = set()
    tokens = []
    for raw in list(local_keys or []) + list(structural_keys or []):
        parts = str(raw or "").split(":")
        if len(parts) < 3:
            continue
        cluster, kind, eid = parts[0], parts[1], ":".join(parts[2:])
        if not cluster or not kind or not eid:
            continue
        if waypoint_cluster and cluster != waypoint_cluster:
            continue
        role = "click" if kind in CLICK_KINDS else kind
        identity = (cluster, role, eid)
        if identity in seen:
            continue
        seen.add(identity)
        tokens.append(f"{cluster}:{role}:{eid}")
    return tokens


def _page(url: str) -> str:
    raw = url or ""
    if "://" in raw:
        raw = raw.split("://", 1)[1]
        raw = raw.split("/", 1)[1] if "/" in raw else ""
    raw = raw.split("#", 1)[0].split("?", 1)[0]
    name = raw.strip("/").split("/")[-1] if raw.strip("/") else ""
    return name


def _template_number(bug_id: str):
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


def template_ids(app: str) -> list:
    manifest = _load(os.path.join(ROOT, "apps", app, "bugs.manifest.json"))
    found = []
    for bug in manifest.get("bugs") or []:
        bug_id = bug.get("id") or ""
        if _template_number(bug_id) in TEMPLATE_NUMBERS:
            found.append(bug_id)
    return found


def tarjan_sccs(nodes: list, adjacency: dict) -> list:
    index = {}
    low = {}
    stack = []
    on_stack = set()
    components = []
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


def hydrate_graph(payload: dict) -> StateGraph:
    graph = StateGraph()
    for raw in payload.get("nodes") or []:
        node = graph.add_state(
            raw.get("sig") or "",
            raw.get("url") or "",
            raw.get("title") or "",
            brief=raw.get("brief") or "",
            cluster_id=raw.get("cluster_id") or "",
            variant_key=raw.get("variant_key") or "",
            relation=raw.get("relation") or "new",
        )
        node.visits = int(raw.get("visits") or 0)
        node.tried_actions = set(raw.get("tried_actions") or [])
        node.observed_actions = set(raw.get("observed_actions") or [])
        node.observed_opps = dict(raw.get("observed_opps") or {})
        node.flags = list(raw.get("flags") or [])
        node.restore_failures = int(raw.get("restore_failures") or 0)
        node.first_seen_step = int(raw.get("first_seen_step") or 0)
    graph.start_sig = payload.get("start") or payload.get("start_sig") or graph.start_sig
    for raw in payload.get("edges") or []:
        graph.edges[(raw.get("src"), raw.get("action_key"))] = StateEdge(
            src=raw.get("src") or "",
            action_key=raw.get("action_key") or "",
            dst=raw.get("dst") or "",
            count=int(raw.get("count") or 0),
            action=raw.get("action"),
        )
    return graph


def observed_components(graph: StateGraph) -> dict:
    nodes = [sig for sig in graph.nodes if sig and sig != "CRASHED"]
    adjacency = {sig: [] for sig in nodes}
    usable = []
    for edge in graph.edges.values():
        if edge.action is None or edge.dst == "CRASHED" or edge.src == "CRASHED":
            continue
        if edge.src not in adjacency or edge.dst not in graph.nodes:
            continue
        if edge.dst == "CRASHED":
            continue
        usable.append(edge)
        if edge.dst not in adjacency[edge.src] and edge.dst in adjacency:
            adjacency[edge.src].append(edge.dst)
    components = tarjan_sccs(nodes, adjacency)
    described = []
    for component in components:
        members = set(component)
        outgoing = []
        for edge in usable:
            if edge.src in members and edge.dst not in members and edge.dst != "CRASHED":
                outgoing.append({
                    "src": edge.src,
                    "dst": edge.dst,
                    "action_key": edge.action_key,
                })
        pending = 0
        for sig in component:
            counts = pending_opportunity_counts(graph, sig, None)
            pending += (
                counts["progress"] + counts["clicks"]
                + counts["inputs"] + counts["deferred"]
            )
        pages = sorted({_page(graph.nodes[sig].url) for sig in component})
        described.append({
            "sigs": component,
            "size": len(component),
            "closed": len(outgoing) == 0,
            "outgoing": len(outgoing),
            "pending_interactions": pending,
            "pages": pages,
        })
    return {"components": described, "node_count": len(nodes), "edge_count": len(usable)}


def _sink_component(report: dict) -> dict:
    closed = [item for item in report["components"] if item["closed"]]
    if not closed:
        return {}
    closed.sort(key=lambda item: (-item["size"], item["sigs"]))
    return closed[0]


def _read_jsonl(path: str) -> list:
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _confirmed_v0321(app: str, budget: int) -> list:
    path = os.path.join(V0321, "evidence", app, "metrics.json")
    payload = _load(path)
    for row in payload.get("runs") or []:
        if int(row.get("budget") or 0) == budget and row.get("policy", "").endswith("waypoint-frontier-guard"):
            return sorted(row.get("confirmed_bugs") or [])
    return []


def _confirmed_v0322(app: str, budget: int) -> list:
    path = os.path.join(V0322, "evidence", app, f"b{budget}", "summary.json")
    payload = _load(path)
    return sorted(payload.get("confirmed_bugs") or [])


def _template_status(app: str, confirmed: list) -> dict:
    wanted = template_ids(app)
    missing = [bug_id for bug_id in wanted if bug_id not in confirmed]
    return {
        "template_ids": wanted,
        "confirmed_template": [bug_id for bug_id in wanted if bug_id in confirmed],
        "missing": missing,
        "recovered": not missing and bool(wanted),
    }


def _first_escape(events: list) -> dict:
    for event in events:
        if event.get("event") == "return_waypoint_frontier_escape":
            return event
    return {}


def _terminal_after_escape(events: list, escape: dict) -> dict:
    instance = escape.get("sequence_instance_id") or ""
    step = int(escape.get("step") or 0)
    later = [
        event for event in events
        if int(event.get("step") or -1) >= step
        and event.get("event") == "return_cycle_escape"
    ]
    chosen = later[0] if later else {}
    terminal = {}
    if chosen:
        inst = chosen.get("sequence_instance_id") or ""
        for event in events:
            if (
                event.get("event") == "sequence_terminal"
                and event.get("sequence_instance_id") == inst
                and event.get("outcome") == "return_cycle_abandoned"
            ):
                terminal = event
                break
        afterward = [
            event.get("event") for event in events
            if event.get("sequence_instance_id") == inst
            and int(event.get("step") or -1) > int(terminal.get("step") or 10**9)
        ] if terminal else []
    else:
        afterward = []
    return {
        "return_cycle_escape_step": chosen.get("step"),
        "terminal_step": terminal.get("step"),
        "terminal_outcome": terminal.get("outcome"),
        "terminal_reason": terminal.get("reason"),
        "events_after_terminal": afterward,
        "sequence_terminalled_before_suffix": bool(
            terminal and terminal.get("outcome") == "return_cycle_abandoned"
            and not afterward
        ),
    }


def _organic(steps: list, escape: dict, tokens: list, terminal_step) -> dict:
    cluster = escape.get("waypoint_cluster") or ""
    eids = []
    for token in tokens:
        eid = token.split(":")[-1]
        if eid not in eids:
            eids.append(eid)
    step = int(escape.get("step") or 0)
    immediate = []
    later = []
    for row in steps:
        if row.get("kind") != "step":
            continue
        index = int(row.get("index") or -1)
        if index <= step:
            continue
        if (row.get("src_cluster") or "") != cluster:
            continue
        action = row.get("action") or {}
        eid = action.get("target_eid") or ""
        if eid not in eids:
            continue
        bucket = immediate if index == step + 1 else later
        if eid not in bucket:
            bucket.append(eid)
    after_terminal = []
    if terminal_step is not None:
        for row in steps:
            if row.get("kind") != "step":
                continue
            index = int(row.get("index") or -1)
            if index <= int(terminal_step):
                continue
            if (row.get("src_cluster") or "") != cluster:
                continue
            eid = (row.get("action") or {}).get("target_eid") or ""
            if eid in eids and eid not in after_terminal:
                after_terminal.append(eid)
    return {
        "residual_eids": eids,
        "immediate_next_eids": immediate,
        "later_eids": later,
        "eids_after_return_cycle_terminal": after_terminal,
        "organic_consumption": bool(later),
        "productive_entity_reentry": bool(after_terminal),
    }


def _final_sig(steps: list) -> str:
    final = ""
    for row in steps:
        if row.get("kind") == "step":
            final = row.get("dst_sig") or final
    return final


def _component_for(report: dict, sig: str) -> dict:
    for item in report["components"]:
        if sig in item["sigs"]:
            return item
    return {}


def _budget_graph(app: str, budget: int) -> dict:
    if budget == 120:
        path = os.path.join(
            V0321, "evidence", app,
            f"ghost-structural-return-waypoint-frontier-guard_b120_s1.graph.json")
    else:
        path = os.path.join(V0322, "evidence", app, f"b{budget}", "graph.json")
    graph = hydrate_graph(_load(path))
    report = observed_components(graph)
    sink = _sink_component(report)
    return {
        "budget": budget,
        "node_count": report["node_count"],
        "edge_count": report["edge_count"],
        "scc_count": len(report["components"]),
        "closed_scc_count": sum(1 for item in report["components"] if item["closed"]),
        "sink": {
            "size": sink.get("size", 0),
            "closed": bool(sink.get("closed")),
            "outgoing": sink.get("outgoing", 0),
            "pending_interactions": sink.get("pending_interactions", 0),
            "pages": sink.get("pages") or [],
            "sigs": sink.get("sigs") or [],
        },
    }


def _restore_fact() -> dict:
    lines = open(EXPLORER, encoding="utf-8").read().splitlines()
    predicate = "if seqc is not None and not restore_step:"
    hits = [number for number, line in enumerate(lines, start=1) if predicate in line]
    window = "\n".join(lines[250:470])
    return {
        "file": "ghostqa/exploration/explorer.py",
        "predicate": predicate,
        "lines": hits,
        "after_skipped_on_restore": bool(hits),
        "policy_reset_in_relocate_window": "policy.reset(" in window,
    }


def _debt_from_v0321(app: str) -> dict:
    path = os.path.join(
        V0321, "evidence", app,
        "ghost-structural-return-waypoint-frontier-guard_b120_s1.sequence_events.json")
    events = _load(path)
    escape = _first_escape(events)
    tokens = normalize_residual_tokens(
        escape.get("local_residual_keys"),
        escape.get("structural_residual_keys"),
        escape.get("waypoint_cluster") or "",
    )
    raw = list(escape.get("local_residual_keys") or []) + list(
        escape.get("structural_residual_keys") or [])
    return {
        "source": "experiments/published/return-waypoint-frontier-v0.3.21",
        "budget": 120,
        "step": escape.get("step"),
        "sequence_instance_id": escape.get("sequence_instance_id"),
        "source_branch": escape.get("active_branch") or escape.get("branch_key") or "",
        "waypoint_sig": escape.get("waypoint_sig") or "",
        "waypoint_cluster": escape.get("waypoint_cluster") or "",
        "replay_target_exact_sig": escape.get("waypoint_sig") or "",
        "raw_local_keys": list(escape.get("local_residual_keys") or []),
        "raw_structural_keys": list(escape.get("structural_residual_keys") or []),
        "raw_key_count": len(raw),
        "normalized_tokens": tokens,
        "normalized_count": len(tokens),
        "deduped": len(tokens) < len(raw),
    }


def build_audit() -> dict:
    freeze = _load(CANDIDATE_FREEZE)
    recorded = ((freeze.get("files") or {}).get(
        "ghostqa/exploration/return_waypoint_frontier_guard.py") or {}).get("sha256")
    targets = {}
    for app in TARGETS:
        debt = _debt_from_v0321(app)
        graphs = {str(budget): _budget_graph(app, budget) for budget in (120, 240, 480)}
        seq_path = os.path.join(V0322, "evidence", app, "b480", "sequence_events.json")
        events = _load(seq_path)
        escape = _first_escape(events)
        tokens = normalize_residual_tokens(
            escape.get("local_residual_keys"),
            escape.get("structural_residual_keys"),
            escape.get("waypoint_cluster") or "",
        )
        steps = _read_jsonl(os.path.join(V0322, "evidence", app, "b480", "events.jsonl"))
        terminal = _terminal_after_escape(events, escape)
        organic = _organic(steps, escape, tokens, terminal.get("terminal_step"))
        final = _final_sig(steps)
        b480 = graphs["480"]
        graph = hydrate_graph(_load(os.path.join(V0322, "evidence", app, "b480", "graph.json")))
        report = observed_components(graph)
        final_component = _component_for(report, final)
        templates = {}
        for budget, confirmed in (
            (120, _confirmed_v0321(app, 120)),
            (240, _confirmed_v0322(app, 240)),
            (480, _confirmed_v0322(app, 480)),
        ):
            templates[str(budget)] = _template_status(app, confirmed)
        sink = b480["sink"]
        targets[app] = {
            "sink_scc_size": sink["size"],
            "sink_closed": sink["closed"],
            "sink_outgoing": sink["outgoing"],
            "sink_pending_interactions": sink["pending_interactions"],
            "sink_pages": sink["pages"],
            "sink_sigs": sink["sigs"],
            "final_sig": final,
            "final_sig_in_sink": final in set(sink["sigs"]),
            "final_component_pending": final_component.get("pending_interactions"),
            "graphs": graphs,
            "template_589": templates,
            "template_589_missing_through_b480": all(
                not templates[name]["recovered"] for name in ("120", "240", "480")
            ),
            "template_589_retained_through_b480": all(
                templates[name]["recovered"] for name in ("120", "240", "480")
            ),
            "first_v0321_waypoint_debt": debt,
            "replay_target_exact_sig": debt["replay_target_exact_sig"],
            "b480_waypoint_escape_step": escape.get("step"),
            "b480_normalized_tokens": tokens,
            "organic": organic,
            "post_terminal": terminal,
        }
    return {
        "version": "v0.3.23",
        "basis_round": "v0.3.22",
        "basis_diagnosis": "persistent_post_terminal_sink",
        "product_default_changed": False,
        "computed_from_publications": True,
        "publications": {
            "v0.3.21": "experiments/published/return-waypoint-frontier-v0.3.21",
            "v0.3.22": "experiments/published/post-escape-sink-v0.3.22",
        },
        "source_candidate": {
            "freeze": "experiments/frozen/ghost-return-waypoint-frontier-v0.3.21/freeze.json",
            "freeze_sha256": sha256_file(CANDIDATE_FREEZE),
            "module": "ghostqa/exploration/return_waypoint_frontier_guard.py",
            "module_sha256": sha256_file(CANDIDATE_SOURCE),
            "freeze_recorded_module_sha256": recorded,
            "module_matches_freeze": sha256_file(CANDIDATE_SOURCE) == recorded,
        },
        "restore_step_sequence_isolation": _restore_fact(),
        "scc_definition": {
            "nodes": "runtime StateGraph exact signatures",
            "edges": "known edges with a stored action, excluding CRASHED",
            "closed": "no stored-action edge from the component to a signature outside it",
            "exhausted": "pending progress+clicks+inputs+deferred == 0 via pending_opportunity_counts",
            "topology_files_read": False,
        },
        "targets": targets,
    }


def main() -> int:
    audit = build_audit()
    path = os.path.join(VALIDATION, "v0322-residual-debt-audit.json")
    _write(path, audit)
    print(path)
    for app, row in audit["targets"].items():
        print(
            app,
            "sink", row["sink_scc_size"],
            "closed", row["sink_closed"],
            "out", row["sink_outgoing"],
            "pending", row["sink_pending_interactions"],
            "missing480", row["template_589_missing_through_b480"],
            "retained480", row["template_589_retained_through_b480"],
            "tokens", row["first_v0321_waypoint_debt"]["normalized_count"],
            "organic", row["organic"]["organic_consumption"],
            "reentry", row["organic"]["productive_entity_reentry"],
            "pending120", row["graphs"]["120"]["sink"]["pending_interactions"],
            "terminalled", row["post_terminal"]["sequence_terminalled_before_suffix"],
        )
    print("freeze match", audit["source_candidate"]["module_matches_freeze"])
    print("restore isolation", audit["restore_step_sequence_isolation"]["after_skipped_on_restore"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
