"""Frontier planner v1.1: interaction-level value + restore cost.

v0.3 scored raw pending *action* count, so 6 payloads on one field looked
like 6 opportunities. v1.1 counts InteractionOpportunity (one per field).
"""
from __future__ import annotations

from dataclasses import dataclass

from ..state.similarity import NEW
from .interaction import interaction_key_from_str


@dataclass
class FrontierTarget:
    sig: str
    score: float
    untried: int
    path_len: int
    cluster_id: str
    reasons: list
    n_progress: int = 0
    n_inputs: int = 0
    n_deferred: int = 0


DEFAULT_FRONTIER_WEIGHTS = {
    "progress": 1.2,
    "nav_click": 0.7,
    "input_field": 0.35,     # one per field, not per payload
    "deferred_fuzz": 0.08,
    "cluster_novelty": 0.4,
    "risk_flag": 0.3,
    "path_cost": 0.25,       # restore cost in the same units as score
    "visits": 0.05,
    "restore_fail": 1.0,
}


def pending_opportunity_counts(graph, sig: str, payload_policy=None) -> dict:
    """Count pending *interactions*, never raw payload cardinality."""
    counts = {"progress": 0, "clicks": 0, "inputs": 0, "deferred": 0}
    node = graph.nodes.get(sig)
    if node is None:
        return counts
    tried_iks = {interaction_key_from_str(k) for k in node.tried_actions}
    opps = getattr(node, "observed_opps", None) or {}
    if not opps:
        # Fallback: group raw observed keys (still 1 per input field).
        seen_input = set()
        for k in node.observed_actions:
            if k in node.tried_actions or k.startswith("back:"):
                continue
            ik = interaction_key_from_str(k)
            if ik.startswith("input:"):
                if ik in seen_input:
                    continue
                seen_input.add(ik)
                counts["inputs"] += 1
            else:
                counts["clicks"] += 1
        return counts
    for ik, meta in opps.items():
        kind = meta.get("kind")
        if kind == "back":
            continue
        if kind == "input":
            eid = ik.split(":", 1)[-1]
            ftype = meta.get("field_type") or "unknown"
            if ik not in tried_iks:
                counts["inputs"] += 1
            elif payload_policy is not None:
                if payload_policy.remaining_deferred_eid(sig, eid, ftype):
                    counts["deferred"] += 1
            else:
                leftover = [k for k in node.observed_actions
                            if interaction_key_from_str(k) == ik
                            and k not in node.tried_actions]
                if leftover:
                    counts["deferred"] += 1
        else:
            if ik in tried_iks:
                continue
            if meta.get("progress"):
                counts["progress"] += 1
            else:
                counts["clicks"] += 1
    return counts


class FrontierPlanner:
    def __init__(self, weights: dict = None):
        self.w = dict(DEFAULT_FRONTIER_WEIGHTS)
        if weights:
            self.w.update(weights)

    def score_node(self, graph, sig: str, current_sig: str,
                   payload_policy=None) -> FrontierTarget | None:
        node = graph.nodes.get(sig)
        if node is None or sig == "CRASHED":
            return None
        start = graph.start_sig or current_sig
        path = graph.shortest_path(start, sig)
        if path is None and sig != start:
            return None
        path_len = 0 if path is None else len(path)
        c = pending_opportunity_counts(graph, sig, payload_policy)
        if c["progress"] + c["clicks"] + c["inputs"] + c["deferred"] <= 0:
            return None
        cluster_visits = sum(n.visits for n in graph.nodes.values()
                             if n.cluster_id == node.cluster_id)
        reasons = [f"prog={c['progress']}", f"in={c['inputs']}",
                   f"click={c['clicks']}", f"defer={c['deferred']}"]
        score = (self.w["progress"] * c["progress"]
                 + self.w["nav_click"] * c["clicks"]
                 + self.w["input_field"] * c["inputs"]
                 + self.w["deferred_fuzz"] * c["deferred"])
        if cluster_visits <= 1:
            score += self.w["cluster_novelty"]
            reasons.append("novel_cluster")
        if "had_l2_finding" in node.flags:
            score += self.w["risk_flag"]
            reasons.append("l2_flag")
        restore_cost = self.w["path_cost"] * path_len
        score -= restore_cost
        score -= self.w["visits"] * node.visits
        score -= self.w["restore_fail"] * node.restore_failures
        if node.relation == NEW:
            reasons.append("new_structure")
        if restore_cost:
            reasons.append(f"restore_cost={restore_cost:.2f}")
        n_pending = c["progress"] + c["clicks"] + c["inputs"] + c["deferred"]
        return FrontierTarget(
            sig=sig, score=score, untried=n_pending, path_len=path_len,
            cluster_id=node.cluster_id, reasons=reasons,
            n_progress=c["progress"], n_inputs=c["inputs"],
            n_deferred=c["deferred"],
        )

    def discover(self, graph, current_sig: str, payload_policy=None) -> list:
        out = []
        for sig in graph.nodes:
            t = self.score_node(graph, sig, current_sig, payload_policy)
            if t is not None:
                out.append(t)
        out.sort(key=lambda t: -t.score)
        return out

    def select(self, graph, current_sig: str, remaining_budget: int = 10**9,
               payload_policy=None):
        for t in self.discover(graph, current_sig, payload_policy):
            if t.sig == current_sig:
                continue
            if t.path_len >= remaining_budget:
                continue
            if t.score <= 0:
                continue
            return t
        return None
