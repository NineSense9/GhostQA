"""Experimental finding-gated return-entry drain (v0.3.19).

Research-only. Not the product default. The v0.3.18 controller is reused by
subclassing; its module is not modified.

Return-Entry Drain starts only when the same step appends a new
sequence_terminal with outcome finding and that terminal belongs to the
branch that just entered returning. An ordinary sequence_horizon_reached
transition does not start the drain.
"""
from __future__ import annotations

from .policy import GhostPolicy
from .return_entry_drain_guard import ReturnEntryDrainSequenceController

_PROVENANCE_MODES = ("sequence_instance", "branch_step_fallback")


class FindingReturnEntryDrainSequenceController(ReturnEntryDrainSequenceController):
    """v0.3.18 drain with finding-terminal trigger provenance."""

    def __init__(self, mode: str = "structural"):
        super().__init__(mode)
        self._reset_finding_gate()

    def _reset_finding_gate(self) -> None:
        self._pre_step = None
        self._consumed_triggers = set()
        self._trigger_records = []
        self._trigger_mismatch_violations = 0
        self._reused_trigger_violations = 0
        self._wrong_instance_violations = 0

    def reset(self):
        super().reset()
        self._reset_finding_gate()

    def _named(self, event_name: str) -> list:
        return [event for event in self.events if event.get("event") == event_name]

    def _event_index(self, event: dict) -> int:
        for index, item in enumerate(self.events):
            if item is event:
                return index
        return -1

    def _matching_finding_terminals(self, new_events: list) -> list:
        live = self.ledger.active_branch or ""
        if not live:
            return []
        pre = self._pre_step or {}
        pre_id = pre.get("open_id")
        matches = []
        for event in new_events:
            if event.get("event") != "sequence_terminal":
                continue
            if event.get("outcome") != "finding":
                continue
            branch = event.get("branch_key") or ""
            if branch != live:
                continue
            iid = event.get("sequence_instance_id")
            if iid:
                started_here = any(
                    item.get("event") == "branch_start"
                    and item.get("sequence_instance_id") == iid
                    and (item.get("branch_key") or "") == live
                    for item in new_events
                )
                same_open = bool(pre_id) and iid == pre_id
                if not started_here and not same_open:
                    continue
                matches.append((event, "sequence_instance"))
                continue
            matches.append((event, "branch_step_fallback"))
        return matches

    def _emit_horizon_bypass(self, new_state, new_sig, graph, step: int) -> None:
        cluster = self._cluster(new_sig, graph) if new_sig else ""
        buttons = self._eligible_buttons(new_state, cluster) if cluster else []
        self._emit(
            "finding_return_entry_horizon_bypassed", step, new_sig or "", cluster,
            self.ledger.active_branch or "",
            {
                "step": step,
                "branch": self.ledger.active_branch or "",
                "hub": cluster,
                "parent": self.ledger.parent_hub_cluster or "",
                "eligible_visible_buttons": len(buttons),
                "behavior": "v0317_fallback",
            },
        )

    def _emit_nonfinding_bypass(self, new_sig, graph, step: int, outcome: str) -> None:
        cluster = self._cluster(new_sig, graph) if new_sig else ""
        self._emit(
            "finding_return_entry_nonfinding_bypassed", step, new_sig or "", cluster,
            self.ledger.active_branch or "",
            {
                "step": step,
                "branch": self.ledger.active_branch or "",
                "hub": cluster,
                "parent": self.ledger.parent_hub_cluster or "",
                "terminal_outcome": outcome,
                "behavior": "v0317_fallback",
            },
        )

    def _record_trigger(self, event, mode, index, new_sig, graph, step,
                        returning_before) -> None:
        starts = self._named("return_entry_drain_started")
        start = starts[-1]
        iid = event.get("sequence_instance_id")
        branch = event.get("branch_key") or ""
        cluster = self._cluster(new_sig, graph) if new_sig else (start.get("hub_cluster") or "")
        payload = {
            "step": step,
            "sequence_instance_id": iid,
            "branch_key": branch,
            "terminal_outcome": event.get("outcome") or "",
            "terminal_event_index": index,
            "destination_sig": new_sig or "",
            "destination_cluster": cluster,
            "parent_sig": self.ledger.parent_hub_sig or "",
            "parent_cluster": self.ledger.parent_hub_cluster or "",
            "returning_before": bool(returning_before),
            "returning_after": bool(self.ledger.returning),
            "visible_eligible_keys": list(start.get("visible_eligible_keys") or []),
            "provenance_mode": mode,
        }
        bad = False
        if payload["step"] != start.get("step") or payload["terminal_outcome"] != "finding":
            bad = True
        if branch != (self.ledger.active_branch or ""):
            bad = True
            self._wrong_instance_violations += 1
        if mode not in _PROVENANCE_MODES or (mode == "sequence_instance" and not iid):
            bad = True
        if index < 0:
            bad = True
        trigger_id = (iid or "", index)
        if trigger_id in self._consumed_triggers:
            self._reused_trigger_violations += 1
            bad = True
        self._consumed_triggers.add(trigger_id)
        self._trigger_records.append(payload)
        self._emit(
            "finding_return_entry_trigger", step, new_sig or "", cluster, branch, payload)
        if (len(self._named("finding_return_entry_trigger")) != len(starts)
                or len(self._trigger_records) != self._return_entry_epochs):
            bad = True
        if bad:
            self._trigger_mismatch_violations += 1

    def _maybe_start_return_entry(self, returning_before, new_state, new_sig,
                                  crashed, graph, step, success_before,
                                  completed_before, n_events) -> None:
        new_events = self.events[n_events:]
        matches = self._matching_finding_terminals(new_events)
        finding_any = [
            event for event in new_events
            if event.get("event") == "sequence_terminal" and event.get("outcome") == "finding"
        ]
        horizons = [
            event for event in new_events
            if event.get("event") == "sequence_horizon_reached"
        ]
        nonfinding = [
            event for event in new_events
            if event.get("event") == "sequence_terminal" and event.get("outcome") != "finding"
        ]
        if len(matches) == 1 and not crashed:
            event, mode = matches[0]
            index = self._event_index(event)
            trigger_id = (event.get("sequence_instance_id") or "", index)
            if trigger_id in self._consumed_triggers:
                self._reused_trigger_violations += 1
                return
            before = len(self._named("return_entry_drain_started"))
            super()._maybe_start_return_entry(
                returning_before, new_state, new_sig, crashed, graph, step,
                success_before, completed_before, n_events)
            if len(self._named("return_entry_drain_started")) == before:
                return
            self._record_trigger(
                event, mode, index, new_sig, graph, step, returning_before)
            return
        false_to_true = (not returning_before) and bool(self.ledger.returning)
        if not false_to_true:
            return
        if horizons and not finding_any:
            self._emit_horizon_bypass(new_state, new_sig, graph, step)
            return
        if nonfinding or crashed:
            outcome = nonfinding[0].get("outcome") if nonfinding else "crash"
            self._emit_nonfinding_bypass(new_sig, graph, step, outcome or "")

    def after(self, sig, action, state, new_state, relation, findings,
              new_sig, crashed, graph, step: int):
        if self._pending_return_probe is not None:
            super().after(
                sig, action, state, new_state, relation, findings,
                new_sig, crashed, graph, step)
            return
        self._pre_step = {
            "returning": bool(self.ledger.returning),
            "active_branch": self.ledger.active_branch or "",
            "n_events": len(self.events),
            "open_id": None if self._open_instance is None else self._open_instance.get("id"),
            "open_branch": (
                "" if self._open_instance is None else (self._open_instance.get("branch") or "")),
        }
        super().after(
            sig, action, state, new_state, relation, findings,
            new_sig, crashed, graph, step)

    def metrics(self) -> dict:
        out = super().metrics()
        out["finding_return_entry_trigger_events"] = len(
            self._named("finding_return_entry_trigger"))
        out["finding_return_entry_horizon_bypass_events"] = len(
            self._named("finding_return_entry_horizon_bypassed"))
        out["finding_return_entry_nonfinding_bypass_events"] = len(
            self._named("finding_return_entry_nonfinding_bypassed"))
        out["finding_return_entry_trigger_mismatch_violations"] = (
            self._trigger_mismatch_violations)
        out["finding_return_entry_reused_trigger_violations"] = (
            self._reused_trigger_violations)
        out["finding_return_entry_wrong_instance_violations"] = (
            self._wrong_instance_violations)
        return out


class FindingReturnEntryDrainGuardGhostPolicy(GhostPolicy):
    """Benchmark-only identity. Does not replace the product default."""

    name = "ghost-structural-finding-return-entry-drain-guard"

    def __init__(self, llm=None, **kwargs):
        kwargs["use_frontier"] = False
        kwargs["sequence_mode"] = "structural"
        super().__init__(llm=llm, **kwargs)
        self.sequence = FindingReturnEntryDrainSequenceController("structural")
        self.sequence_mode = "structural"


__all__ = [
    "FindingReturnEntryDrainGuardGhostPolicy",
    "FindingReturnEntryDrainSequenceController",
]
