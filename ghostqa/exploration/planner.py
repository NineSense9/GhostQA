"""Global frontier planner: which known state is most worth returning to?

Local GhostPolicy answers "which action on *this* page?".
FrontierPlanner answers "which already-seen state has the highest-value
untried neighbourhood, and how do we get back there?"

Restoration policy (v0.3): deterministic reset + replay of a known path.
No browser snapshots.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..state.similarity import NEW


@dataclass
class FrontierTarget:
    sig: str
    score: float
    untried: int
    path_len: int
    cluster_id: str
    reasons: list


# Each term is independently measurable / ablatable.
DEFAULT_FRONTIER_WEIGHTS = {
    "untried": 1.0,          # pending observed actions
    "cluster_novelty": 0.4,  # cluster visited only once
    "risk_flag": 0.3,        # node previously grew an L2 finding
    "brief_risk": 0.2,       # risk keywords in the stored brief
    "path_cost": 0.15,       # shorter known path from start is better
    "visits": 0.05,          # lightly prefer less-visited nodes
    "restore_fail": 1.0,     # heavily penalise unreachable frontiers
}


_RISK = ("支付", "删除", "提交", "结算", "清空", "注册", "购买", "归档",
         "权限", "成员", "导出", "pay", "delete", "submit", "checkout",
         "archive", "permission")


class FrontierPlanner:
    def __init__(self, weights: dict = None):
        self.w = dict(DEFAULT_FRONTIER_WEIGHTS)
        if weights:
            self.w.update(weights)

    def discover(self, graph, current_sig: str) -> list:
        out = []
        start = graph.start_sig or current_sig
        cluster_visits: dict = {}
        for n in graph.nodes.values():
            cluster_visits[n.cluster_id] = cluster_visits.get(n.cluster_id, 0) + n.visits
        for sig, node in graph.nodes.items():
            if sig == "CRASHED":
                continue
            pending = graph.pending_actions(sig)
            if not pending:
                continue
            path = graph.shortest_path(start, sig)
            if path is None and sig != start:
                continue
            path_len = 0 if path is None else len(path)
            cv = cluster_visits.get(node.cluster_id, 0)
            brief = (node.brief or "").lower()
            brief_risk = 1.0 if any(k in brief for k in _RISK) else 0.0
            reasons = [f"untried={len(pending)}"]
            score = self.w["untried"] * len(pending)
            if cv <= 1:
                score += self.w["cluster_novelty"]
                reasons.append("novel_cluster")
            if "had_l2_finding" in node.flags:
                score += self.w["risk_flag"]
                reasons.append("l2_flag")
            if brief_risk:
                score += self.w["brief_risk"] * brief_risk
                reasons.append("brief_risk")
            score -= self.w["path_cost"] * path_len
            score -= self.w["visits"] * node.visits
            score -= self.w["restore_fail"] * node.restore_failures
            if node.relation == NEW:
                reasons.append("new_structure")
            out.append(FrontierTarget(
                sig=sig, score=score, untried=len(pending),
                path_len=path_len, cluster_id=node.cluster_id, reasons=reasons,
            ))
        out.sort(key=lambda t: -t.score)
        return out

    def select(self, graph, current_sig: str, remaining_budget: int = 10**9):
        for t in self.discover(graph, current_sig):
            if t.sig == current_sig:
                continue
            if t.path_len >= remaining_budget:
                continue
            if t.score <= 0:
                continue
            return t
        return None
