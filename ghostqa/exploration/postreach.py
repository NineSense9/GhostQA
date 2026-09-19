"""Post-reach exploration (v0.3.4).

Bounded exploitation after workflow progress. Does not read bug manifests.
Replay still sees only concrete Actions.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .interaction import is_progress_action, form_progress, classify_field
from .payload import PAYLOAD_VALUES, class_of_value, first_wave, deferred_wave
from ..state.similarity import NEW, SIMILAR

EXPLOIT_BUDGET = 2
DEFERRED_PER_VISIT = 1

RISKISH = ("delete", "remove", "archive", "export", "rename", "reopen",
           "destroy", "清空", "删除", "归档", "导出", "重命名")


@dataclass
class StateRec:
    sig: str
    cluster_id: str = ""
    graph_depth: int = 0
    first_seen_step: int = 0
    visits: int = 0
    arrival_action_type: str = ""
    arrived_via_progress: bool = False
    first_wave_used: int = 0
    deferred_used: int = 0
    non_progress_used: int = 0
    progress_used: int = 0
    local_budget_used: int = 0
    novelty_generated: int = 0
    finding_generated: int = 0
    saturated: bool = False
    deferred_this_visit: int = 0
    exploit_this_visit: int = 0
    last_local_novelty: bool = False


class StateExplorationLedger:
    def __init__(self):
        self.recs: dict = {}
        self.recent_new: list = []
        self.post_reach_actions: int = 0
        self.exploit_actions: int = 0
        self.progress_mode_actions: int = 0
        self.deferred_executed: int = 0
        self.deferred_commit_attempts: int = 0
        self.deferred_commit_findings: int = 0
        self.local_saturation_count: int = 0
        self.local_backtrack_count: int = 0
        self.unique_deep_interactions: set = set()
        self.deep_states: set = set()
        self._via_progress_pending: bool = False

    def rec(self, sig: str) -> StateRec:
        r = self.recs.get(sig)
        if r is None:
            r = StateRec(sig=sig)
            self.recs[sig] = r
        return r

    def graph_depth(self, graph, sig: str) -> int:
        start = getattr(graph, "start_sig", "") or sig
        path = graph.shortest_path(start, sig) if graph else None
        if path is None:
            return 0
        return len(path)

    def arrive(self, sig: str, graph, step: int, via_progress: bool,
               cluster_id: str, arrival_type: str):
        r = self.rec(sig)
        if r.visits == 0:
            r.first_seen_step = step
            r.arrived_via_progress = via_progress
            r.arrival_action_type = arrival_type
            r.cluster_id = cluster_id
            r.graph_depth = self.graph_depth(graph, sig)
            if r.graph_depth >= 3 or via_progress:
                self.deep_states.add(sig)
        if r.visits > 0:
            r.deferred_this_visit = 0
            r.exploit_this_visit = 0
        r.visits += 1
        node = graph.nodes.get(sig) if graph else None
        if node:
            r.cluster_id = node.cluster_id or cluster_id

    def should_exploit(self, sig: str, graph, mode: str) -> bool:
        if mode == "off":
            return False
        r = self.rec(sig)
        if r.saturated:
            return False
        if r.exploit_this_visit >= EXPLOIT_BUDGET:
            return False
        if r.arrived_via_progress:
            return True
        if r.graph_depth >= 2:
            return True
        if r.visits >= 2:
            return True
        recent = self.recent_new[-3:]
        if recent and not any(recent):
            return True
        node = graph.nodes.get(sig) if graph else None
        if node and r.visits <= 1 and node.relation == NEW:
            return True
        return False

    def mark_saturated(self, sig: str):
        r = self.rec(sig)
        if not r.saturated:
            r.saturated = True
            self.local_saturation_count += 1

    def snapshot(self) -> dict:
        return {
            "post_reach_actions": self.post_reach_actions,
            "exploit_actions": self.exploit_actions,
            "progress_mode_actions": self.progress_mode_actions,
            "deferred_payloads_executed": self.deferred_executed,
            "deferred_commit_attempts": self.deferred_commit_attempts,
            "deferred_commit_findings": self.deferred_commit_findings,
            "local_saturation_count": self.local_saturation_count,
            "local_backtrack_count": self.local_backtrack_count,
            "deep_states_reached": len(self.deep_states),
            "unique_deep_interactions": len(self.unique_deep_interactions),
            "saturated_states": sum(1 for r in self.recs.values() if r.saturated),
        }


class PostReachController:
    """PROGRESS vs EXPLOIT local modes. Modes: off, deferred, exploit, postreach."""

    def __init__(self, mode: str = "off"):
        self.mode = mode  # off | deferred | exploit | postreach
        self.ledger = StateExplorationLedger()
        self.pending_commit = None  # Action or None
        self.pending_from_sig = ""
        self.last_label = "progress"

    def reset(self):
        self.ledger = StateExplorationLedger()
        self.pending_commit = None
        self.pending_from_sig = ""

    def enabled(self) -> bool:
        return self.mode != "off"

    def enum_flags(self, sig: str, graph) -> dict:
        exploit = self.ledger.should_exploit(sig, graph, self.mode)
        flags = {
            "exploit_active": exploit and self.mode in ("deferred", "exploit", "postreach"),
            "force_deferred": False,
            "exploit_deferred": False,
        }
        if exploit and self.mode in ("deferred", "postreach", "exploit"):
            rec = self.ledger.rec(sig)
            if rec.deferred_this_visit < DEFERRED_PER_VISIT:
                flags["exploit_deferred"] = True
                flags["force_deferred"] = True
        return flags

    def pick(self, actions, state, graph, ctx) -> tuple:
        sig = ctx["sig"]
        rec = self.ledger.rec(sig)
        exploit = self.ledger.should_exploit(sig, graph, self.mode)
        untried = set(graph.untried_actions(sig, [a.key() for a in actions]))

        if self.mode == "postreach" and self.pending_commit is not None:
            if self.pending_from_sig != sig:
                self.pending_commit = None
            else:
                key = self.pending_commit.key()
                for a in actions:
                    if a.key() == key:
                        self.last_label = "probe_commit"
                        return a, "probe_commit"

        if rec.saturated and self.mode == "postreach":
            for a in actions:
                if a.type == "back":
                    self.last_label = "escape"
                    return a, "escape"

        first_in = self._first_wave_input(actions, state, untried)
        if first_in is not None:
            self.last_label = "progress"
            return first_in, "progress"

        if exploit and self.mode in ("exploit", "postreach") and rec.exploit_this_visit < EXPLOIT_BUDGET:
            risk = self._risk_click(actions, state, untried)
            if risk is not None:
                self.last_label = "exploit"
                return risk, "exploit"
            deferred = self._deferred_input(actions, state, untried)
            if deferred is not None:
                if self.mode == "postreach":
                    self.pending_commit = self._commit_candidate(actions, state)
                    self.pending_from_sig = sig
                self.last_label = "exploit"
                return deferred, "exploit"
            ordinary = self._ordinary_click(actions, state, untried)
            if ordinary is not None:
                self.last_label = "exploit"
                return ordinary, "exploit"

        if exploit and self.mode == "deferred":
            deferred = self._deferred_input(actions, state, untried)
            if deferred is not None:
                self.last_label = "exploit"
                return deferred, "exploit"

        for a in actions:
            if a.type != "back" and is_progress_action(a, state) and a.key() in untried:
                self.last_label = "progress"
                return a, "progress"
        for a in actions:
            if a.type != "back" and a.key() in untried:
                self.last_label = "progress"
                return a, "progress"
        for a in actions:
            if a.type == "back":
                self.last_label = "escape"
                return a, "escape"
        self.last_label = "progress"
        return actions[0], "progress"

    def after(self, sig: str, action, relation: str, findings: list,
              new_sig: str, crashed: bool, state=None):
        rec = self.ledger.rec(sig)
        if state is not None and is_progress_action(action, state):
            rec.progress_used += 1
        if action.type == "input":
            cls = class_of_value(action.text or "")
            rec.first_wave_used += 1
            if cls not in ("NORMAL", "EMPTY") and cls != first_wave("text")[0]:
                rec.deferred_used += 1
                self.ledger.deferred_executed += 1
            rec.deferred_this_visit += 1
        if action.type == "click" and self.last_label == "exploit":
            rec.non_progress_used += 1
        if self.last_label == "progress":
            rec.progress_used += 1
            self.ledger.progress_mode_actions += 1
        if self.last_label == "exploit":
            rec.exploit_this_visit += 1
            rec.local_budget_used += 1
            self.ledger.exploit_actions += 1
            self.ledger.post_reach_actions += 1
            if rec.graph_depth >= 2:
                self.ledger.unique_deep_interactions.add(action.key())
        if self.last_label == "probe_commit":
            self.ledger.deferred_commit_attempts += 1
            self.ledger.post_reach_actions += 1
            if findings:
                self.ledger.deferred_commit_findings += 1
            self.pending_commit = None
        if self.last_label == "escape":
            self.ledger.local_backtrack_count += 1
        if relation in (NEW, SIMILAR):
            rec.novelty_generated += 1
            rec.last_local_novelty = True
            self.ledger.recent_new.append(True)
        else:
            rec.last_local_novelty = False
            self.ledger.recent_new.append(False)
        self.ledger.recent_new = self.ledger.recent_new[-8:]
        if findings:
            rec.finding_generated += 1
        if crashed or findings or (new_sig and new_sig != sig):
            self.pending_commit = None
            self.pending_from_sig = ""
        if (self.last_label in ("exploit", "probe_commit")
                and rec.exploit_this_visit >= EXPLOIT_BUDGET
                and not rec.last_local_novelty and not findings):
            self.ledger.mark_saturated(sig)
        elif rec.exploit_this_visit >= EXPLOIT_BUDGET:
            self.ledger.mark_saturated(sig)

    def _risk_click(self, actions, state, untried):
        for a in actions:
            if a.type != "click" or a.key() not in untried:
                continue
            if is_progress_action(a, state):
                continue
            blob = (a.target_eid or "").lower()
            for el in state.elements:
                if el.eid == a.target_eid:
                    blob = f"{el.text} {el.eid} {el.role}".lower()
                    break
            if any(k in blob for k in RISKISH):
                return a
        return None

    def _ordinary_click(self, actions, state, untried):
        for a in actions:
            if a.type == "click" and a.key() in untried and not is_progress_action(a, state):
                return a
        return None

    def _first_wave_input(self, actions, state, untried):
        for a in actions:
            if a.type != "input" or a.key() not in untried:
                continue
            el = next((e for e in state.elements if e.eid == a.target_eid), None)
            field = classify_field(el) if el else "unknown"
            if class_of_value(a.text or "") in first_wave(field):
                return a
        return None

    def _deferred_input(self, actions, state, untried):
        for a in actions:
            if a.type != "input" or a.key() not in untried:
                continue
            el = next((e for e in state.elements if e.eid == a.target_eid), None)
            field = classify_field(el) if el else "unknown"
            cls = class_of_value(a.text or "")
            if cls not in first_wave(field):
                return a
        return None

    def _commit_candidate(self, actions, state):
        fp = form_progress(state, set())
        eids = set(fp.get("submit_candidates") or [])
        for a in actions:
            if a.type == "click" and (a.target_eid in eids or is_progress_action(a, state)):
                return a
        return None
