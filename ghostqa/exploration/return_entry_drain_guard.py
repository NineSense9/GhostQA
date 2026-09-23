"""Experimental return-phase entry drain (v0.3.18).

Research-only. Not the product default. The v0.3.17 controller is reused by
subclassing; its module is not modified.

When returning flips from false to true on a non-crashed destination that
still has eligible undrained buttons, those buttons are probed once before
the original return action. Same-hub probes are not return attempts. A probe
that leaves the hub does not become a promoted child.
"""
from __future__ import annotations

from .local_action_drain_guard import (
    LocalActionDrainSequenceController, _public_findings,
)
from .policy import GhostPolicy


class ReturnEntryDrainSequenceController(LocalActionDrainSequenceController):
    """v0.3.17 drain, plus a drain at the false-to-true return boundary."""

    def __init__(self, mode: str = "structural"):
        super().__init__(mode)
        self._reset_return_entry()

    def _reset_return_entry(self) -> None:
        self._return_entry = None
        self._pending_return_probe = None
        self._return_entry_epochs = 0
        self._return_entry_accounting_violations = 0
        self._return_entry_max_actions = 0

    def reset(self):
        super().reset()
        self._reset_return_entry()

    def _count(self, event_name: str) -> int:
        return sum(1 for event in self.events if event.get("event") == event_name)

    def _obligation(self) -> tuple:
        return (
            bool(self.ledger.returning),
            self.ledger.active_branch or "",
            self.ledger.parent_hub_sig or "",
            self.ledger.parent_hub_cluster or "",
            int(self.ledger.return_success),
            int(self.ledger.return_attempts),
            int(self.ledger.sequences_started),
            int(self.ledger.sequences_completed),
            int(self.ledger.commitment_left),
            tuple(sorted(self._seen_failed_return_dests)),
            self._count("return_attempt"),
            self._count("branch_start"),
            self._count("sequence_action"),
            self._count("sequence_terminal"),
            self._count("return_cycle_escape"),
        )

    def _note_return_epoch(self, count: int) -> None:
        if count > self._return_entry_max_actions:
            self._return_entry_max_actions = count

    def _return_holding(self) -> bool:
        entry = self._return_entry or {}
        return bool(entry.get("active"))

    def _obligation_fields(self) -> dict:
        return {
            "returning": bool(self.ledger.returning),
            "active_branch": self.ledger.active_branch or "",
            "parent_hub_sig": self.ledger.parent_hub_sig or "",
            "parent_hub_cluster": self.ledger.parent_hub_cluster or "",
            "return_attempts": int(self.ledger.return_attempts),
            "return_success": int(self.ledger.return_success),
            "return_cycle_history_count": len(self._seen_failed_return_dests),
            "sequences_started": int(self.ledger.sequences_started),
            "sequences_completed": int(self.ledger.sequences_completed),
        }

    def _returned_count(self) -> int:
        return sum(
            1 for event in self.events
            if event.get("event") == "sequence_terminal"
            and event.get("outcome") == "returned")

    def _completed_or_unwound(self, n_events: int, success_before: int,
                              completed_before: int) -> bool:
        if not self.ledger.active_branch or not self.ledger.returning:
            return True
        if not self.ledger.parent_hub_sig and not self.ledger.parent_hub_cluster:
            return True
        if self.ledger.return_success != success_before:
            return True
        if self.ledger.sequences_completed != completed_before:
            return True
        parent = self.ledger.parent_hub_sig
        key = self.ledger.active_branch
        if parent in self.ledger.hubs and key in self.ledger.hubs[parent].completed:
            return True
        for event in self.events[n_events:]:
            name = event.get("event")
            if name in ("horizon_handoff_unwind", "return_cycle_escape"):
                return True
            if name == "sequence_terminal" and event.get("outcome") in (
                "returned", "horizon_handoff_abandoned", "return_cycle_abandoned",
            ):
                return True
        return False

    def _maybe_start_return_entry(self, returning_before, new_state, new_sig,
                                  crashed, graph, step, success_before,
                                  completed_before, n_events) -> None:
        if returning_before or not self.ledger.returning:
            return
        if crashed or new_state is None or not new_sig or new_sig == "CRASHED":
            return
        if self._drain is not None or self._return_holding():
            return
        if self._pending_probe is not None or self._pending_return_probe is not None:
            return
        if self._completed_or_unwound(n_events, success_before, completed_before):
            return
        cluster = self._cluster(new_sig, graph)
        if not cluster:
            return
        buttons = self._eligible_buttons(new_state, cluster)
        if not buttons:
            return
        keys = [item[2] for item in buttons]
        self._return_entry_epochs += 1
        self._return_entry = {
            "active": True,
            "hub_cluster": cluster,
            "hub_sig": new_sig,
            "branch": self.ledger.active_branch or "",
            "epoch_keys": [],
            "step": step,
        }
        payload = {
            "hub_sig": new_sig,
            "hub_cluster": cluster,
            "visible_eligible_keys": list(keys),
            "sequence_instance_id": (
                None if self._open_instance is None else self._open_instance.get("id")),
        }
        payload.update(self._obligation_fields())
        self._emit(
            "return_entry_drain_started", step, new_sig, cluster,
            self.ledger.active_branch or "", payload)

    def _select_return_entry(self, actions, state, graph, ctx, sig):
        entry = self._return_entry or {}
        step = -1 if not ctx else ctx.get("step_index", -1)
        hub_cluster = entry.get("hub_cluster") or ""
        observed = self._cluster(sig, graph) if sig else ""
        if observed and hub_cluster and observed != hub_cluster:
            self._exhaust_return_entry(step, sig, graph)
            return None
        buttons = self._eligible_buttons(state, hub_cluster)
        if not buttons:
            self._exhaust_return_entry(step, sig or entry.get("hub_sig") or "", graph)
            return None
        element, action, key = buttons[0]
        if key in self._drained_by_cluster.get(hub_cluster, set()):
            self._repeat_violations += 1
            return None
        self.last_label = "return_entry_drain"
        self._pending_return_probe = {
            "key": key,
            "eid": element.eid,
            "role": element.role,
            "hub_cluster": hub_cluster,
            "frontier_before": len(buttons),
        }
        self._emit(
            "return_entry_probe_selected", step, sig or entry.get("hub_sig") or "",
            hub_cluster, key,
            {
                "key": key,
                "eid": element.eid,
                "role": element.role,
                "hub_cluster": hub_cluster,
                "frontier_count": len(buttons),
                "sequence_instance_id": (
                    None if self._open_instance is None else self._open_instance.get("id")),
                **self._obligation_fields(),
            },
        )
        for candidate in actions or []:
            if getattr(candidate, "type", "") == "click" and candidate.target_eid == element.eid:
                return candidate
        return action

    def pick_override(self, actions, state, graph, ctx):
        if self._drain is not None:
            return super().pick_override(actions, state, graph, ctx)
        if self._return_holding():
            sig = "" if not ctx else (ctx.get("sig") or "")
            chosen = self._select_return_entry(actions, state, graph, ctx, sig)
            if chosen is not None:
                return chosen
        return super().pick_override(actions, state, graph, ctx)

    def label_for(self, action, state) -> str:
        if self.last_label == "return_entry_drain" and self._return_holding():
            return self.last_label
        return super().label_for(action, state)

    def after(self, sig, action, state, new_state, relation, findings,
              new_sig, crashed, graph, step: int):
        if self._pending_return_probe is not None:
            probe = self._pending_return_probe
            self._pending_return_probe = None
            self._finish_return_probe(
                probe, sig, action, state, new_state, relation, findings,
                new_sig, crashed, graph, step)
            return
        returning_before = bool(self.ledger.returning)
        success_before = int(self.ledger.return_success)
        completed_before = int(self.ledger.sequences_completed)
        n_events = len(self.events)
        super().after(
            sig, action, state, new_state, relation, findings,
            new_sig, crashed, graph, step)
        self._maybe_start_return_entry(
            returning_before, new_state, new_sig, bool(crashed), graph, step,
            success_before, completed_before, n_events)

    def _check_obligation(self, before: tuple) -> None:
        if self._obligation() != before:
            self._return_entry_accounting_violations += 1

    def _finish_return_probe(self, probe, sig, action, state, new_state, relation,
                             findings, new_sig, crashed, graph, step) -> None:
        del action, state, relation
        if crashed or new_state is None:
            self._abort_return_entry(step, sig, graph, "crash")
            return
        before = self._obligation()
        entry = self._return_entry or {}
        hub_cluster = probe.get("hub_cluster") or entry.get("hub_cluster") or ""
        dst_cluster = self._cluster(new_sig, graph) if new_sig else ""
        if dst_cluster == hub_cluster and hub_cluster:
            self._complete_return_same_hub(
                probe, sig, findings, new_state, new_sig, graph, step,
                dst_cluster, before)
            return
        self._leave_hub(probe, sig, new_sig, graph, step, dst_cluster, before)

    def _complete_return_same_hub(self, probe, sig, findings, new_state, new_sig,
                                  graph, step, dst_cluster, before: tuple) -> None:
        entry = self._return_entry
        if not entry:
            return
        key = probe.get("key") or ""
        self._mark_drained(entry["hub_cluster"], key)
        entry["epoch_keys"].append(key)
        self._note_return_epoch(len(entry["epoch_keys"]))
        entry["step"] = step
        if new_sig:
            entry["hub_sig"] = new_sig
        fingerprints, asserts = _public_findings(findings)
        instance = None if self._open_instance is None else self._open_instance.get("id")
        payload = {
            "source_sig": sig,
            "destination_sig": new_sig or "",
            "destination_cluster": dst_cluster,
            "key": key,
            "eid": probe.get("eid") or "",
            "hub_cluster": entry["hub_cluster"],
            "finding_count": len(findings or []),
            "sequence_instance_id": instance,
        }
        payload.update(self._obligation_fields())
        self._emit(
            "return_entry_probe_completed", step, sig, entry["hub_cluster"], key, payload)
        if findings:
            finding_payload = {
                "key": key,
                "eid": probe.get("eid") or "",
                "finding_count": len(findings or []),
                "hub_cluster": entry["hub_cluster"],
                "sequence_instance_id": instance,
            }
            if fingerprints:
                finding_payload["fingerprints"] = fingerprints
            if asserts:
                finding_payload["assert_ids"] = asserts
            finding_payload.update(self._obligation_fields())
            self._emit(
                "return_entry_probe_finding", step, sig, entry["hub_cluster"], key,
                finding_payload)
        self._check_obligation(before)
        if entry.get("active") and not self._eligible_buttons(new_state, entry["hub_cluster"]):
            self._exhaust_return_entry(step, new_sig or sig, graph)

    def _leave_hub(self, probe, sig, new_sig, graph, step, dst_cluster, before) -> None:
        entry = self._return_entry
        if not entry:
            return
        key = probe.get("key") or ""
        self._mark_drained(entry["hub_cluster"], key)
        entry["epoch_keys"].append(key)
        self._note_return_epoch(len(entry["epoch_keys"]))
        payload = {
            "key": key,
            "eid": probe.get("eid") or "",
            "hub_cluster": entry["hub_cluster"],
            "hub_sig": entry.get("hub_sig") or "",
            "destination_sig": new_sig or "",
            "destination_cluster": dst_cluster,
            "sequence_instance_id": (
                None if self._open_instance is None else self._open_instance.get("id")),
        }
        payload.update(self._obligation_fields())
        self._emit(
            "return_entry_probe_left_hub", step, sig, entry["hub_cluster"], key, payload)
        self._return_entry = None
        self._pending_return_probe = None
        self._check_obligation(before)

    def _exhaust_return_entry(self, step, sig, graph) -> None:
        del graph
        entry = self._return_entry
        if not entry or not entry.get("active"):
            return
        hub_cluster = entry.get("hub_cluster") or ""
        drained = list(entry.get("epoch_keys") or [])
        self._note_return_epoch(len(drained))
        payload = {
            "drained_keys": drained,
            "hub_cluster": hub_cluster,
            "hub_sig": entry.get("hub_sig") or "",
            "sequence_instance_id": (
                None if self._open_instance is None else self._open_instance.get("id")),
        }
        payload.update(self._obligation_fields())
        self._emit(
            "return_entry_drain_exhausted", step, sig, hub_cluster,
            self.ledger.active_branch or "", payload)
        self._return_entry = None
        self._pending_return_probe = None

    def _abort_return_entry(self, step, sig, graph, reason: str) -> None:
        entry = self._return_entry or {}
        hub_cluster = entry.get("hub_cluster") or ""
        success = int(self.ledger.return_success)
        completed = int(self.ledger.sequences_completed)
        returned = self._returned_count()
        self._emit(
            "return_entry_drain_abort", step, sig, hub_cluster, "",
            {
                "reason": reason,
                "hub_cluster": hub_cluster,
                "sequence_instance_id": (
                    None if self._open_instance is None else self._open_instance.get("id")),
            },
        )
        self._return_entry = None
        self._pending_return_probe = None
        self._unwind(step, sig, graph, reason)
        if (self.ledger.return_success != success
                or self.ledger.sequences_completed != completed
                or self._returned_count() != returned):
            self._return_entry_accounting_violations += 1

    def close_open(self, step: int = -1, sig: str = "", cluster: str = ""):
        self._return_entry = None
        self._pending_return_probe = None
        super().close_open(step, sig, cluster)

    def metrics(self) -> dict:
        out = super().metrics()

        def named(event_name: str) -> list:
            return [event for event in self.events if event.get("event") == event_name]

        out["return_entry_drain_started_events"] = len(named("return_entry_drain_started"))
        out["return_entry_drain_exhausted_events"] = len(named("return_entry_drain_exhausted"))
        out["return_entry_drain_abort_events"] = len(named("return_entry_drain_abort"))
        out["return_entry_probe_selected_events"] = len(named("return_entry_probe_selected"))
        out["return_entry_probe_completed_events"] = len(named("return_entry_probe_completed"))
        out["return_entry_probe_finding_events"] = len(named("return_entry_probe_finding"))
        out["return_entry_probe_left_hub_events"] = len(named("return_entry_probe_left_hub"))
        out["return_entry_epochs"] = self._return_entry_epochs
        out["max_return_entry_actions_per_drain"] = self._return_entry_max_actions
        out["return_entry_accounting_violations"] = self._return_entry_accounting_violations
        return out


class ReturnEntryDrainGuardGhostPolicy(GhostPolicy):
    """Benchmark-only identity. Does not replace the product default."""

    name = "ghost-structural-return-entry-drain-guard"

    def __init__(self, llm=None, **kwargs):
        kwargs["use_frontier"] = False
        kwargs["sequence_mode"] = "structural"
        super().__init__(llm=llm, **kwargs)
        self.sequence = ReturnEntryDrainSequenceController("structural")
        self.sequence_mode = "structural"


__all__ = [
    "ReturnEntryDrainGuardGhostPolicy",
    "ReturnEntryDrainSequenceController",
]
