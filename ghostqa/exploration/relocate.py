"""Relocation research helpers (v0.3.3).

Does not change local GhostPolicy scoring. Provides:
- a single restore_cost() definition
- a common opportunity_value() scale for local vs remote comparison
- a decision/outcome ledger for experiments

R0 (relocate_mode='opportunity') keeps the v0.3.2 decision rule, including
the historical double path-cost deduction. Newer modes use the unified scale.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .interaction import is_progress_action
from .planner import DEFAULT_FRONTIER_WEIGHTS, pending_opportunity_counts


# Common scale: one pending interaction of this kind. Matches planner weights
# so a remote *inventory sum* is visibly larger than a single local action.
KIND_VALUE = {
    "progress": 1.2,
    "nav_click": 0.7,
    "input": 0.35,
    "deferred": 0.08,
    "other": 0.30,
    "back": 0.0,
}

RESERVE_DEFAULT = 5
LEASE_K_DEFAULT = 3
MOMENTUM_K = 3
WINDOWS = (3, 5, 10)


def opportunity_kind(action, state) -> str:
    if action is None or action.type == "back":
        return "back"
    if action.type == "input":
        return "input"
    if is_progress_action(action, state):
        return "progress"
    if action.type == "click":
        return "nav_click"
    return "other"


def opportunity_value(kind: str) -> float:
    return KIND_VALUE.get(kind, KIND_VALUE["other"])


def restore_cost(path_len: int, restore_failures: int = 0,
                 weights: dict = None) -> float:
    """Single-source restore cost. Path length is charged here, not twice."""
    w = weights or DEFAULT_FRONTIER_WEIGHTS
    return (w["path_cost"] * max(0, path_len)
            + w["restore_fail"] * max(0, restore_failures))


def breadth_bonus(pending_count: int) -> float:
    """Capped log bonus. 10 pending clicks must not be 10× one click."""
    return 0.15 * math.log1p(max(0, pending_count))


def best_pending_interaction_value(counts: dict) -> float:
    best = 0.0
    if counts.get("progress"):
        best = max(best, opportunity_value("progress"))
    if counts.get("clicks"):
        best = max(best, opportunity_value("nav_click"))
    if counts.get("inputs"):
        best = max(best, opportunity_value("input"))
    if counts.get("deferred"):
        best = max(best, opportunity_value("deferred"))
    return best


def inventory_sum(counts: dict, weights: dict = None) -> float:
    w = weights or DEFAULT_FRONTIER_WEIGHTS
    return (w["progress"] * counts.get("progress", 0)
            + w["nav_click"] * counts.get("clicks", 0)
            + w["input_field"] * counts.get("inputs", 0)
            + w["deferred_fuzz"] * counts.get("deferred", 0))


def local_action_values(actions, state) -> list:
    rows = []
    for a in actions:
        if a.type == "back":
            continue
        kind = opportunity_kind(a, state)
        rows.append((opportunity_value(kind), a, kind))
    rows.sort(key=lambda r: -r[0])
    return rows


def momentum_penalty(recent_new_states: list, k: int = MOMENTUM_K) -> float:
    """How strongly current NEW-state streak should resist interruption."""
    streak = 0
    for flag in reversed(recent_new_states[-k:]):
        if flag:
            streak += 1
        else:
            break
    return 0.30 * streak


def empty_outcome() -> dict:
    return {
        "restore_actions": 0,
        "restore_success": None,
        "actions_until_new_state": None,
        "actions_until_new_cluster": None,
        "actions_until_finding": None,
        "new_states_within_3": 0,
        "new_states_within_5": 0,
        "new_states_within_10": 0,
        "new_clusters_within_5": 0,
        "finding_within_5": False,
        "finding_within_10": False,
        "returned_to_previous_region": False,
        "relocated_again_before_new_state": False,
        "productive": None,
        "wasted": None,
        "closed": False,
    }


@dataclass
class RelocationLedger:
    """Records every stay/relocate/shadow decision and post-relocate outcomes."""
    decisions: list = field(default_factory=list)
    recent_new_states: list = field(default_factory=list)
    recent_clusters: list = field(default_factory=list)
    _open_idx: int = -1
    _lease_left: int = 0
    _lease_need_novelty: bool = False
    _from_cluster: str = ""

    def lease_blocks(self) -> bool:
        return self._lease_need_novelty or self._lease_left > 0

    def grant_lease(self, k: int = LEASE_K_DEFAULT):
        self._lease_left = k
        self._lease_need_novelty = True

    def record(self, rec: dict) -> dict:
        rec = dict(rec)
        rec.setdefault("outcome", None)
        self.decisions.append(rec)
        return rec

    def mark_executed(self, path_len: int, from_cluster: str = ""):
        if not self.decisions:
            return
        rec = self.decisions[-1]
        rec["executed"] = True
        rec["outcome"] = empty_outcome()
        rec["outcome"]["restore_path_len"] = path_len
        self._open_idx = len(self.decisions) - 1
        self._from_cluster = from_cluster

    def mark_shadow_window(self):
        if not self.decisions:
            return
        rec = self.decisions[-1]
        rec["executed"] = False
        rec["outcome"] = empty_outcome()
        rec["outcome"]["restore_success"] = None
        self._open_idx = len(self.decisions) - 1

    def on_restore_step(self, ok: bool, last: bool):
        if self._open_idx < 0:
            return
        out = self.decisions[self._open_idx]["outcome"]
        if out is None:
            return
        out["restore_actions"] = out.get("restore_actions", 0) + 1
        if last:
            out["restore_success"] = bool(ok)

    def on_productive_step(self, *, relation: str, new_cluster: bool,
                           had_finding: bool, cluster_id: str,
                           returned_to_prev: bool):
        is_new = relation == "new"
        self.recent_new_states.append(is_new)
        self.recent_new_states = self.recent_new_states[-10:]
        if cluster_id:
            self.recent_clusters.append(cluster_id)
            self.recent_clusters = self.recent_clusters[-10:]
        if self._lease_left > 0:
            self._lease_left -= 1
        if is_new or had_finding:
            self._lease_need_novelty = False
            self._lease_left = 0
        if self._open_idx < 0:
            return
        rec = self.decisions[self._open_idx]
        out = rec.get("outcome")
        if not out or out.get("closed"):
            return
        n = 0
        for key in ("post_actions",):
            out[key] = out.get(key, 0) + 1
            n = out[key]
        if is_new and out["actions_until_new_state"] is None:
            out["actions_until_new_state"] = n
        if new_cluster and out["actions_until_new_cluster"] is None:
            out["actions_until_new_cluster"] = n
        if had_finding and out["actions_until_finding"] is None:
            out["actions_until_finding"] = n
        if is_new:
            if n <= 3:
                out["new_states_within_3"] += 1
            if n <= 5:
                out["new_states_within_5"] += 1
            if n <= 10:
                out["new_states_within_10"] += 1
        if new_cluster and n <= 5:
            out["new_clusters_within_5"] += 1
        if had_finding:
            if n <= 5:
                out["finding_within_5"] = True
            if n <= 10:
                out["finding_within_10"] = True
        if returned_to_prev:
            out["returned_to_previous_region"] = True
        if n >= 10 and out["actions_until_new_state"] is None:
            self._close_outcome(wasted=True)
        elif n >= 5 and (out["actions_until_new_state"] is not None
                         or out["actions_until_finding"] is not None
                         or out["new_clusters_within_5"]):
            self._close_outcome(wasted=False)

    def note_chain_relocate(self):
        if self._open_idx < 0:
            return
        out = self.decisions[self._open_idx].get("outcome")
        if not out or out.get("closed"):
            return
        if out.get("actions_until_new_state") is None:
            out["relocated_again_before_new_state"] = True
            self._close_outcome(wasted=True)

    def _close_outcome(self, wasted: bool):
        if self._open_idx < 0:
            return
        out = self.decisions[self._open_idx]["outcome"]
        out["wasted"] = wasted
        out["productive"] = not wasted
        out["closed"] = True
        self._open_idx = -1

    def close_open(self):
        if self._open_idx < 0:
            return
        out = self.decisions[self._open_idx]["outcome"]
        if out and not out.get("closed"):
            wasted = out.get("actions_until_new_state") is None and not out.get(
                "finding_within_10")
            self._close_outcome(wasted=wasted)

    def metrics(self) -> dict:
        executed = [d for d in self.decisions
                    if d.get("decision") == "relocate" and d.get("executed")]
        recs = [d for d in self.decisions if d.get("decision") == "relocate"]
        productive = wasted = chains = 0
        path_lens = []
        for d in executed:
            out = d.get("outcome") or {}
            if out.get("productive"):
                productive += 1
            if out.get("wasted"):
                wasted += 1
            if out.get("relocated_again_before_new_state"):
                chains += 1
            pl = (d.get("frontier") or {}).get("path_len")
            if pl is not None:
                path_lens.append(pl)
        n = len(executed)
        path_lens.sort()
        median = path_lens[len(path_lens) // 2] if path_lens else None
        t_nov = [d["outcome"]["actions_until_new_state"] for d in executed
                 if d.get("outcome") and d["outcome"].get("actions_until_new_state") is not None]
        t_find = [d["outcome"]["actions_until_finding"] for d in executed
                  if d.get("outcome") and d["outcome"].get("actions_until_finding") is not None]
        return {
            "relocate_recommendations": len(recs),
            "relocate_count": n,
            "shadow_recommendations": sum(
                1 for d in recs if d.get("decision") == "relocate"
                and not d.get("executed")),
            "stay_count": sum(1 for d in self.decisions if d.get("decision") == "stay"),
            "productive_relocate_count": productive,
            "wasted_relocate_count": wasted,
            "productive_relocate_rate": round(productive / n, 3) if n else None,
            "wasted_relocate_rate": round(wasted / n, 3) if n else None,
            "relocate_chain_count": chains,
            "mean_restore_path_len": (
                round(sum(path_lens) / len(path_lens), 3) if path_lens else None),
            "median_restore_path_len": median,
            "actions_to_first_post_relocate_novelty": (
                round(sum(t_nov) / len(t_nov), 3) if t_nov else None),
            "actions_to_first_post_relocate_finding": (
                round(sum(t_find) / len(t_find), 3) if t_find else None),
            "relocate_without_novelty_count": sum(
                1 for d in executed
                if d.get("outcome")
                and d["outcome"].get("actions_until_new_state") is None),
        }


def explain(decision: str, local_best: float, remote_net: float,
            restore: float, extra: str = "") -> str:
    parts = [decision,
             f"local={local_best:.2f}",
             f"remote_net={remote_net:.2f}",
             f"restore={restore:.2f}"]
    if extra:
        parts.append(extra)
    return " ".join(parts)
