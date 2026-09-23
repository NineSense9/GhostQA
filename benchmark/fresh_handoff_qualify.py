"""Policy-blind static qualification for v0.3.15 topologies.

Reads topology declarations only. Does not import exploration code, runners,
or published results. BRANCH_HORIZON is the preregistered constant 3.
"""
from __future__ import annotations

import json
import os

BRANCH_HORIZON = 3
MAX_EDGES = 8


def _productive(edge: dict) -> bool:
    return bool(edge.get("branch_like") or edge.get("follow_up") or edge.get("child_local"))


def _usable(edge: dict) -> bool:
    return _productive(edge) or bool(
        edge.get("parent_return") or edge.get("alternate_child_completion"))


def _witness_role(nodes: dict, start: str, path: list[dict]) -> str:
    """Role of the child-local edges that make one nested branch qualify.

    A path that merely brushes a second workflow does not inherit that role.
    """
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


def qualify_topology(topo: dict) -> dict:
    nodes = {node["id"]: node for node in topo.get("nodes") or []}
    edges = list(topo.get("edges") or [])
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
            "child_workflow_role": role,
            "start_hub": start,
            "edge_count": len(path),
            "actions": [edge.get("action") for edge in path],
            "nodes": [start] + [edge["dst"] for edge in path],
        })
    summaries.sort(key=lambda item: item["child_workflow_role"])
    max_chain = _max_branch_path(nodes, outgoing)
    expected = topo.get("expected_control_class") or "positive"
    distinct = [item["child_workflow_role"] for item in summaries]
    if expected == "negative":
        qualified = False
        ok = len(seen) == 0 and len(distinct) == 0 and max_chain < BRANCH_HORIZON
    else:
        qualified = len(distinct) >= 2
        ok = qualified
    return {
        "app": topo.get("app"),
        "seed": topo.get("seed"),
        "seed_hex": topo.get("seed_hex"),
        "topology_family": topo.get("topology_family"),
        "expected_control_class": expected,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "hub_count": sum(1 for node in nodes.values() if node.get("hub")),
        "qualified": qualified,
        "qualification_ok": ok,
        "qualifying_chain_count": len(distinct),
        "qualifying_path_count": len(seen),
        "qualifying_chains": summaries,
        "max_nested_branch_chain": max_chain,
        "max_nested_depth": max_chain,
        "distinct_child_workflows": distinct,
        "child_workflow_roles": distinct,
        "negative_control_expected": expected == "negative",
        "branch_horizon": BRANCH_HORIZON,
    }


def qualify_path(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return qualify_topology(json.load(handle))


def write_qualification(apps_root: str, dest: str) -> dict:
    payload = {
        "round": "v0.3.15",
        "branch_horizon": BRANCH_HORIZON,
        "note": "Static qualification only. It does not mean a policy reached the structure.",
        "apps": {},
    }
    for name in ("buggy-forum", "buggy-billing", "buggy-lab", "buggy-directory"):
        topo_path = os.path.join(apps_root, name, "topology.json")
        payload["apps"][name] = qualify_path(topo_path)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return payload
