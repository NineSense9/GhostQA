"""State Graph: nodes = exact state ids, clustered by structural signature."""
from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field

from .models import Action
from .similarity import IDENTICAL, SIMILAR, NEW


@dataclass
class StateNode:
    sig: str
    url: str
    title: str
    brief: str = ""
    visits: int = 0
    first_seen_step: int = 0
    tried_actions: set = field(default_factory=set)
    flags: list = field(default_factory=list)
    cluster_id: str = ""
    variant_key: str = ""
    observed_actions: set = field(default_factory=set)
    restore_failures: int = 0
    relation: str = NEW          # how this node first related to the graph

    def to_dict(self):
        return {
            "sig": self.sig, "url": self.url, "title": self.title,
            "brief": self.brief, "visits": self.visits,
            "first_seen_step": self.first_seen_step,
            "tried_actions": sorted(self.tried_actions),
            "flags": self.flags,
            "cluster_id": self.cluster_id,
            "variant_key": self.variant_key,
            "observed_actions": sorted(self.observed_actions),
            "restore_failures": self.restore_failures,
            "relation": self.relation,
        }


@dataclass
class StateEdge:
    src: str
    action_key: str
    dst: str
    count: int = 0
    action: dict = None          # Action.to_dict() snapshot for replay

    def to_dict(self):
        return {"src": self.src, "action_key": self.action_key,
                "dst": self.dst, "count": self.count,
                "action": self.action}


class StateGraph:
    def __init__(self):
        self.nodes: dict[str, StateNode] = {}
        self.edges: dict[tuple, StateEdge] = {}        # (src_sig, action_key) -> edge
        self._step_counter = 0
        self.start_sig: str = ""
        self.similarity_counts: dict = {IDENTICAL: 0, SIMILAR: 0, NEW: 0}

    def add_state(self, sig: str, url: str, title: str, brief: str = "",
                  cluster_id: str = "", variant_key: str = "",
                  relation: str = "") -> StateNode:
        if sig not in self.nodes:
            self._step_counter += 1
            cid = cluster_id or (sig.split(":", 1)[0] if ":" in sig else sig)
            self.nodes[sig] = StateNode(
                sig=sig, url=url, title=title, brief=brief,
                first_seen_step=self._step_counter,
                cluster_id=cid, variant_key=variant_key or "none",
                relation=relation or NEW,
            )
            if not self.start_sig:
                self.start_sig = sig
            bucket = relation or NEW
            if bucket in self.similarity_counts:
                self.similarity_counts[bucket] += 1
        return self.nodes[sig]

    def add_transition(self, src_sig: str, url: str, title: str,
                       action_key: str, dst_sig: str,
                       dst_url: str = "", dst_title: str = "",
                       action: Action = None,
                       src_cluster: str = "", src_variant: str = "",
                       dst_cluster: str = "", dst_variant: str = "",
                       dst_relation: str = "") -> StateEdge:
        self.add_state(src_sig, url, title,
                       cluster_id=src_cluster, variant_key=src_variant)
        self.add_state(dst_sig, dst_url, dst_title,
                       cluster_id=dst_cluster, variant_key=dst_variant,
                       relation=dst_relation)
        self.nodes[src_sig].visits += 1
        self.nodes[src_sig].tried_actions.add(action_key)
        key = (src_sig, action_key)
        if key not in self.edges:
            self.edges[key] = StateEdge(
                src=src_sig, action_key=action_key, dst=dst_sig,
                action=action.to_dict() if action is not None else None)
        elif self.edges[key].action is None and action is not None:
            self.edges[key].action = action.to_dict()
        self.edges[key].count += 1
        return self.edges[key]

    def record_observed(self, sig: str, action_keys: list):
        node = self.nodes.get(sig)
        if node is None:
            return
        node.observed_actions.update(action_keys)

    def is_new_state(self, sig: str) -> bool:
        return sig not in self.nodes

    def is_new_cluster(self, cluster: str) -> bool:
        return all(n.cluster_id != cluster for n in self.nodes.values())

    def edge(self, src_sig: str, action_key: str):
        return self.edges.get((src_sig, action_key))

    def edge_count(self, src_sig: str, action_key: str) -> int:
        e = self.edges.get((src_sig, action_key))
        return e.count if e else 0

    def untried_actions(self, sig: str, candidate_keys: list) -> list:
        node = self.nodes.get(sig)
        if node is None:
            return list(candidate_keys)
        return [k for k in candidate_keys if k not in node.tried_actions]

    def pending_actions(self, sig: str) -> list:
        """Observed but not yet tried (excludes `back`)."""
        node = self.nodes.get(sig)
        if node is None:
            return []
        return [k for k in node.observed_actions
                if k not in node.tried_actions and not k.startswith("back:")]

    def flag_node(self, sig: str, flag: str):
        node = self.nodes.get(sig)
        if node is not None and flag not in node.flags:
            node.flags.append(flag)

    def mark_restore_failure(self, sig: str):
        node = self.nodes.get(sig)
        if node is not None:
            node.restore_failures += 1

    def cluster_count(self) -> int:
        return len({n.cluster_id for n in self.nodes.values() if n.cluster_id})

    def variant_count(self) -> int:
        return len(self.nodes)

    def shortest_path(self, src: str, dst: str) -> list | None:
        """Return a list of Action along a shortest known path, or None."""
        if src == dst:
            return []
        if src not in self.nodes or dst not in self.nodes:
            return None
        prev: dict = {src: None}          # node -> (parent, action_dict)
        q = deque([src])
        while q:
            u = q.popleft()
            for (s, _k), edge in self.edges.items():
                if s != u or edge.dst in prev:
                    continue
                if edge.dst == "CRASHED" or edge.action is None:
                    continue
                prev[edge.dst] = (u, edge.action)
                if edge.dst == dst:
                    path = []
                    cur = dst
                    while prev[cur] is not None:
                        parent, ad = prev[cur]
                        path.append(Action.from_dict(ad))
                        cur = parent
                    path.reverse()
                    return path
                q.append(edge.dst)
        return None

    def stats(self) -> dict:
        return {
            "states": len(self.nodes),
            "clusters": self.cluster_count(),
            "variants": self.variant_count(),
            "edges": len(self.edges),
            "total_transitions": sum(e.count for e in self.edges.values()),
            "similarity": dict(self.similarity_counts),
        }

    def to_dict(self) -> dict:
        return {
            "start_sig": self.start_sig,
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges.values()],
            "similarity": dict(self.similarity_counts),
        }

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
