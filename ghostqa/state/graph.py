"""State Graph: nodes = state signatures, edges = executed actions."""
from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class StateNode:
    sig: str
    url: str
    title: str
    brief: str = ""
    visits: int = 0
    first_seen_step: int = 0
    tried_actions: set = field(default_factory=set)   # action keys executed from here
    flags: list = field(default_factory=list)          # oracle flags (e.g. "had_l2_finding")

    def to_dict(self):
        return {
            "sig": self.sig, "url": self.url, "title": self.title,
            "brief": self.brief, "visits": self.visits,
            "first_seen_step": self.first_seen_step,
            "tried_actions": sorted(self.tried_actions),
            "flags": self.flags,
        }


@dataclass
class StateEdge:
    src: str
    action_key: str
    dst: str
    count: int = 0

    def to_dict(self):
        return {"src": self.src, "action_key": self.action_key,
                "dst": self.dst, "count": self.count}


class StateGraph:
    def __init__(self):
        self.nodes: dict[str, StateNode] = {}
        self.edges: dict[tuple, StateEdge] = {}        # (src_sig, action_key) -> edge
        self._step_counter = 0

    def add_state(self, sig: str, url: str, title: str, brief: str = "") -> StateNode:
        if sig not in self.nodes:
            self._step_counter += 1
            self.nodes[sig] = StateNode(sig=sig, url=url, title=title, brief=brief,
                                        first_seen_step=self._step_counter)
        return self.nodes[sig]

    def add_transition(self, src_sig: str, url: str, title: str,
                       action_key: str, dst_sig: str,
                       dst_url: str = "", dst_title: str = "") -> StateEdge:
        self.add_state(src_sig, url, title)
        self.add_state(dst_sig, dst_url, dst_title)
        self.nodes[src_sig].visits += 1
        self.nodes[src_sig].tried_actions.add(action_key)
        key = (src_sig, action_key)
        if key not in self.edges:
            self.edges[key] = StateEdge(src=src_sig, action_key=action_key, dst=dst_sig)
        self.edges[key].count += 1
        return self.edges[key]

    def is_new_state(self, sig: str) -> bool:
        return sig not in self.nodes

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

    def flag_node(self, sig: str, flag: str):
        node = self.nodes.get(sig)
        if node is not None and flag not in node.flags:
            node.flags.append(flag)

    def stats(self) -> dict:
        return {
            "states": len(self.nodes),
            "edges": len(self.edges),
            "total_transitions": sum(e.count for e in self.edges.values()),
        }

    def to_dict(self) -> dict:
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges.values()],
        }

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
