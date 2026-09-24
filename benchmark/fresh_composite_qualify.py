"""Policy-blind static qualification for v0.3.20 topologies.

Reads topology declarations only. Does not import exploration code, runners,
or published results. BRANCH_HORIZON is the preregistered constant 3.
"""
from __future__ import annotations

import json
import os

BRANCH_HORIZON = 3
MAX_EDGES = 8
POSITIVE = ("buggy-campus", "buggy-warehouse", "buggy-studio", "buggy-booking")
ORDER = POSITIVE + ("buggy-catalog", "buggy-kiosk")


def _productive(edge: dict) -> bool:
    return bool(edge.get("branch_like") or edge.get("follow_up") or edge.get("child_local"))


def _usable(edge: dict) -> bool:
    return _productive(edge) or bool(
        edge.get("parent_return") or edge.get("alternate_child_completion"))


def _witness_role(nodes: dict, start: str, path: list[dict]) -> str:
    cut = len(path)
    for index, edge in enumerate(path):
        if edge.get("parent_return") and edge.get("returns_to") == start:
            cut = index
            break
    before = path[:cut]
    if sum(1 for edge in before if _productive(edge)) < BRANCH_HORIZON:
        return ""
    candidates = []
    for index, edge in enumerate(before):
        source = nodes.get(edge["src"]) or {}
        if (
            edge.get("branch_like")
            and edge.get("navigates")
            and source.get("hub")
            and edge["src"] != start
        ):
            candidates.append(index)
    for nested_at in candidates:
        after = before[nested_at + 1:]
        local = [edge for edge in after if edge.get("child_local") or edge.get("follow_up")]
        if not local:
            continue
        child_parent = before[nested_at]["src"]
        returned = any(
            edge.get("parent_return") and edge.get("returns_to") == child_parent
            for edge in path
        )
        alternate = any(edge.get("alternate_child_completion") for edge in path)
        if not (returned or alternate):
            continue
        roles = {edge.get("child_workflow_role") or "" for edge in local}
        roles.discard("")
        if len(roles) == 1:
            return next(iter(roles))
    return ""


def _max_branch_path(nodes: dict, outgoing: dict) -> int:
    best = 0

    def walk(node_id: str, depth: int, used: set) -> None:
        nonlocal best
        if depth > best:
            best = depth
        if depth >= MAX_EDGES:
            return
        for edge in outgoing.get(node_id, []):
            if not edge.get("branch_like") or not edge.get("navigates"):
                continue
            if edge["id"] in used:
                continue
            used.add(edge["id"])
            walk(edge["dst"], depth + 1, used)
            used.remove(edge["id"])

    for node_id in nodes:
        walk(node_id, 0, set())
    return best


def _chain_summaries(nodes: dict, edges: list) -> tuple[list, int]:
    outgoing: dict[str, list] = {}
    for edge in edges:
        outgoing.setdefault(edge["src"], []).append(edge)
    seen = set()
    best: dict[str, tuple] = {}

    def signature(path: list[dict], role: str) -> tuple:
        return (
            role,
            tuple(
                (
                    edge["src"],
                    edge.get("action") or "",
                    edge["dst"],
                    bool(edge.get("branch_like")),
                    bool(edge.get("child_local") or edge.get("follow_up")),
                    bool(edge.get("parent_return")),
                )
                for edge in path
            ),
        )

    def consider(start: str, path: list[dict]) -> None:
        if not path:
            return
        role = _witness_role(nodes, start, path)
        if not role:
            return
        key = signature(path, role)
        if key in seen:
            return
        seen.add(key)
        current = best.get(role)
        if current is None or len(path) < len(current[1]):
            best[role] = (start, list(path))

    def dfs(start: str, node_id: str, path: list[dict], used: set) -> None:
        consider(start, path)
        if len(path) >= MAX_EDGES:
            return
        for edge in outgoing.get(node_id, []):
            if edge["id"] in used or not _usable(edge):
                continue
            if edge.get("parent_return") and len(path) < BRANCH_HORIZON:
                continue
            used.add(edge["id"])
            path.append(edge)
            dfs(start, edge["dst"], path, used)
            path.pop()
            used.remove(edge["id"])

    for node_id, node in nodes.items():
        if node.get("hub"):
            dfs(node_id, node_id, [], set())
    summaries = []
    for role, (start, path) in best.items():
        summaries.append({
            "id": f"nested:{role}",
            "class": "nested_handoff_opportunity",
            "child_workflow_role": role,
            "start_hub": start,
            "start_hub_role": (nodes.get(start) or {}).get("hub_role") or "",
            "destination_hub_role": (nodes.get(path[-1]["dst"]) or {}).get("hub_role") or "",
            "edge_count": len(path),
            "crosses_branch_horizon": sum(1 for edge in path if _productive(edge)) >= BRANCH_HORIZON,
            "actions": [edge.get("action") for edge in path],
            "edge_ids": [edge["id"] for edge in path],
            "nodes": [start] + [edge["dst"] for edge in path],
        })
    summaries.sort(key=lambda item: item["child_workflow_role"])
    return summaries, len(seen)


def _handoff_edges(nodes: dict) -> list:
    """Branch clicks that can be the third action of a branch while the source is a hub.

    Depth counts branch clicks only. Action 1 starts on a hub. Action 3 is a
    handoff when its source is still a hub. Self-loop buttons stay on the node.
    """
    actions = {}
    for node_id, node in nodes.items():
        actions[node_id] = list(node.get("branch_actions") or [])
    found = {}

    def walk(node_id: str, depth: int, used: tuple) -> None:
        if depth >= BRANCH_HORIZON:
            return
        for action in actions.get(node_id, []):
            key = (node_id, action.get("testid") or "")
            if key in used:
                continue
            nxt = node_id if not action.get("navigates") else (action.get("dst") or node_id)
            step = depth + 1
            if step == BRANCH_HORIZON and (nodes.get(node_id) or {}).get("hub"):
                edge_id = f"{node_id}:{action.get('testid') or ''}"
                dest = nodes.get(nxt) or {}
                found[edge_id] = {
                    "id": edge_id,
                    "class": "nested_handoff_opportunity",
                    "source_node": node_id,
                    "source_hub_role": (nodes.get(node_id) or {}).get("hub_role") or "",
                    "action": action.get("testid") or "",
                    "destination_node": nxt,
                    "destination_hub_role": dest.get("hub_role") or "",
                    "navigates": bool(action.get("navigates")),
                }
            if step < BRANCH_HORIZON:
                walk(nxt, step, used + (key,))

    for node_id, node in nodes.items():
        if node.get("hub"):
            walk(node_id, 0, ())
    rows = list(found.values())
    rows.sort(key=lambda item: item["id"])
    return rows


def _path_groups(edges: list) -> dict:
    groups: dict[str, list] = {}
    for edge in edges:
        path_id = edge.get("path_id") or ""
        if not path_id:
            continue
        groups.setdefault(path_id, []).append(edge)
    for rows in groups.values():
        rows.sort(key=lambda edge: int(edge.get("path_index") or 0))
    return groups


def _finding_opportunities(nodes: dict, edges: list) -> list:
    rows = []
    for edge in edges:
        if edge.get("opportunity_class") != "finding_return_entry_opportunity":
            continue
        if not edge.get("guarantees_finding"):
            continue
        dest = nodes.get(edge["dst"]) or {}
        buttons = list(dest.get("eligible_buttons") or [])
        rows.append({
            "id": edge["id"],
            "class": "finding_return_entry_opportunity",
            "source_node": edge["src"],
            "source_hub_role": (nodes.get(edge["src"]) or {}).get("hub_role") or "",
            "action": edge.get("action") or "",
            "destination_node": edge["dst"],
            "destination_hub_role": dest.get("hub_role") or "",
            "eligible_button_count": len(buttons),
            "eligible_buttons": buttons,
            "offline_guarantees_finding": True,
            "path_id": edge.get("path_id") or edge["id"],
        })
    rows.sort(key=lambda item: item["id"])
    return rows


def _horizon_opportunities(nodes: dict, edges: list) -> list:
    rows = []
    for path_id, path in _path_groups(edges).items():
        if not path or path[0].get("opportunity_class") != "horizon_only_return_entry_control":
            continue
        last = path[-1]
        dest = nodes.get(last["dst"]) or {}
        buttons = list(dest.get("eligible_buttons") or [])
        sources = [(nodes.get(edge["src"]) or {}) for edge in path]
        rows.append({
            "id": path_id,
            "class": "horizon_only_return_entry_control",
            "source_node": path[0]["src"],
            "source_hub_role": (nodes.get(path[0]["src"]) or {}).get("hub_role") or "",
            "destination_node": last["dst"],
            "destination_hub_role": dest.get("hub_role") or "",
            "actions": [edge.get("action") or "" for edge in path],
            "edge_ids": [edge["id"] for edge in path],
            "nodes": [path[0]["src"]] + [edge["dst"] for edge in path],
            "length": len(path),
            "eligible_button_count": len(buttons),
            "eligible_buttons": buttons,
            "offline_guarantees_finding": False,
            "offline_guarantees_no_finding": all(
                edge.get("guarantees_no_finding") for edge in path),
            "start_is_hub": bool(sources[0].get("hub")) if sources else False,
            "later_sources_are_hubs": any(item.get("hub") for item in sources[1:]),
            "final_source_is_hub": bool(sources[-1].get("hub")) if sources else False,
        })
    rows.sort(key=lambda item: item["id"])
    return rows


def _distinct(left: list, right: list) -> bool:
    if not left or not right:
        return False
    finding_nodes = {item["destination_node"] for item in left}
    finding_edges = {item["id"] for item in left}
    for item in right:
        if item["destination_node"] in finding_nodes:
            return False
        if finding_edges.intersection(item["edge_ids"]):
            return False
    return True


def qualify_topology(topo: dict) -> dict:
    nodes = {node["id"]: node for node in topo.get("nodes") or []}
    edges = list(topo.get("edges") or [])
    outgoing: dict[str, list] = {}
    for edge in edges:
        outgoing.setdefault(edge["src"], []).append(edge)
    summaries, path_count = _chain_summaries(nodes, edges)
    handoffs = _handoff_edges(nodes)
    findings = _finding_opportunities(nodes, edges)
    horizons = _horizon_opportunities(nodes, edges)
    max_chain = _max_branch_path(nodes, outgoing)
    expected = topo.get("expected_control_class") or "positive"
    roles = [item["child_workflow_role"] for item in summaries]
    variant = sum(1 for edge in edges if edge.get("state_variant_return"))
    finding_rich = [item for item in findings if item["eligible_button_count"] >= 2]
    finding_any = [item for item in findings if item["eligible_button_count"] >= 1]
    horizon_ok = [
        item for item in horizons
        if item["length"] >= BRANCH_HORIZON
        and item["eligible_button_count"] >= 1
        and item["offline_guarantees_no_finding"]
        and item["start_is_hub"]
        and not item["final_source_is_hub"]
        and not item["later_sources_are_hubs"]
    ]
    distinct_paths = _distinct(findings, horizon_ok)
    chains_cross = bool(summaries) and all(item["crosses_branch_horizon"] for item in summaries)
    if expected == "positive":
        qualified = (
            len(roles) >= 2
            and len(set(roles)) >= 2
            and chains_cross
            and len(finding_rich) >= 1
            and len(horizon_ok) >= 1
            and distinct_paths
            and variant >= 1
            and len(handoffs) >= 1
        )
    elif expected == "catalog":
        qualified = (
            len(summaries) == 0
            and len(handoffs) == 0
            and len(finding_any) == 0
            and max_chain < BRANCH_HORIZON
        )
    elif expected == "kiosk":
        qualified = (
            len(summaries) == 0
            and len(handoffs) == 0
            and len(finding_rich) >= 2
            and len(horizon_ok) >= 1
            and distinct_paths
        )
    else:
        qualified = False
    local_buttons = {
        node["id"]: list(node.get("eligible_buttons") or [])
        for node in nodes.values()
        if node.get("eligible_buttons")
    }
    return {
        "app": topo.get("app"),
        "seed": topo.get("seed"),
        "seed_hex": topo.get("seed_hex"),
        "family": topo.get("topology_family"),
        "topology_family": topo.get("topology_family"),
        "class": "positive" if expected == "positive" else "negative",
        "expected_control_class": expected,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "hub_count": sum(1 for node in nodes.values() if node.get("hub")),
        "max_nested_branch_depth": max_chain,
        "nested_handoff_opportunity_count": len(summaries),
        "handoff_edge_count": len(handoffs),
        "finding_return_entry_opportunity_count": len(finding_rich),
        "finding_return_entry_any_button_count": len(finding_any),
        "horizon_only_return_entry_control_count": len(horizon_ok),
        "state_variant_return_count": variant,
        "qualifying_path_summaries": summaries,
        "qualifying_chains": summaries,
        "handoff_edges": handoffs,
        "finding_return_opportunities": findings,
        "horizon_only_controls": horizons,
        "local_button_opportunity_counts": {
            key: len(value) for key, value in sorted(local_buttons.items())
        },
        "qualified": qualified,
        "qualification_ok": qualified,
        "positive_class": expected == "positive",
        "distinct_child_workflows": roles,
        "finding_and_horizon_distinct": distinct_paths if findings and horizon_ok else expected != "positive",
        "branch_horizon": BRANCH_HORIZON,
    }


def qualify_path(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return qualify_topology(json.load(handle))


def _public_qualification(row: dict) -> dict:
    keys = (
        "app", "seed", "seed_hex", "family", "class", "node_count", "edge_count",
        "hub_count", "max_nested_branch_depth", "nested_handoff_opportunity_count",
        "finding_return_entry_opportunity_count", "horizon_only_return_entry_control_count",
        "state_variant_return_count", "qualified", "positive_class",
        "distinct_child_workflows", "qualifying_path_summaries",
        "finding_return_opportunities", "horizon_only_controls", "handoff_edges",
        "local_button_opportunity_counts", "qualification_ok",
    )
    return {key: row[key] for key in keys if key in row}


def write_qualification(apps_root: str, dest: str) -> dict:
    payload = {
        "round": "v0.3.20",
        "branch_horizon": BRANCH_HORIZON,
        "note": "Static qualification only. It does not mean a policy reached the structure.",
        "apps": {},
    }
    for name in ORDER:
        topo_path = os.path.join(apps_root, name, "topology.json")
        payload["apps"][name] = _public_qualification(qualify_path(topo_path))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return payload


def mechanism_from_qualification(row: dict) -> dict:
    opportunities = []
    for item in row.get("qualifying_path_summaries") or []:
        opportunities.append({
            "id": item["id"],
            "class": "nested_handoff_opportunity",
            "child_workflow_role": item["child_workflow_role"],
            "source_hub_role": item.get("start_hub_role") or "",
            "destination_hub_role": item.get("destination_hub_role") or "",
            "edge_ids": item.get("edge_ids") or [],
            "nodes": item.get("nodes") or [],
            "offline_guarantees_finding": False,
        })
    for item in row.get("finding_return_opportunities") or []:
        opportunities.append({
            "id": item["id"],
            "class": "finding_return_entry_opportunity",
            "source_hub_role": item.get("source_hub_role") or "",
            "destination_hub_role": item.get("destination_hub_role") or "",
            "action": item.get("action") or "",
            "destination_node": item.get("destination_node") or "",
            "eligible_button_count": item.get("eligible_button_count") or 0,
            "offline_guarantees_finding": True,
        })
    for item in row.get("horizon_only_controls") or []:
        opportunities.append({
            "id": item["id"],
            "class": "horizon_only_return_entry_control",
            "source_hub_role": item.get("source_hub_role") or "",
            "destination_hub_role": item.get("destination_hub_role") or "",
            "edge_ids": item.get("edge_ids") or [],
            "nodes": item.get("nodes") or [],
            "eligible_button_count": item.get("eligible_button_count") or 0,
            "offline_guarantees_finding": False,
            "offline_guarantees_no_finding": True,
        })
    if row.get("class") == "negative" and row.get("app") == "buggy-catalog":
        opportunities.append({
            "id": "catalog:shallow_control",
            "class": "shallow_control",
            "source_hub_role": "category_list",
            "destination_hub_role": "product",
            "offline_guarantees_finding": False,
        })
    return {
        "app": row.get("app"),
        "note": "OFFLINE JUDGE ONLY. Not served. No empirical policy results.",
        "round": "v0.3.20",
        "opportunities": opportunities,
    }
