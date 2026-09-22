"""Experimental horizon handoff (v0.3.14).

Research-only. Not the product default. Does not replace the v0.3.9,
v0.3.12, or v0.3.13 identities.

Nested hub branch clicks stay on the current sequence while commitment_left
is greater than 1. The click that would consume the final commitment slot
suspends that sequence with a deferred horizon and starts a real child.
A frame is pushed only for that handoff. Restoration requires a
child-specific physical parent witness, not a global return counter.

``sequence.is_hub`` is never reassigned. The continuation path below is an
isolated copy of the historical action lifecycle with the branch-start block
omitted.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..state.similarity import NEW, SIMILAR
from .policy import GhostPolicy
from .return_cycle_guard import ReturnCycleGuardSequenceController
from .sequence import (
    BRANCH_HORIZON, CONTEXT_MODES, FOLLOWUP_LIKE, SEQUENCE_LIKE,
    _finding_fps, branch_key, is_branch_click, is_hub, is_return_action,
)

LEGAL_TERMINALS = frozenset({
    "returned",
    "finding",
    "crash",
    "return_cycle_abandoned",
    "horizon_handoff_abandoned",
    "budget_end",
    "lost_parent",
})
ACCEPTED_CONTEXTS = frozenset({
    "returned",
    "finding_same_step",
    "crash_same_step",
    "finding_prior",
    "crash_prior",
})
SAME_STEP_CONTEXTS = frozenset({
    "returned",
    "finding_same_step",
    "crash_same_step",
})


@dataclass
class HandoffFrame:
    active_branch: str
    parent_hub_sig: str
    parent_hub_cluster: str
    commitment_left: int
    returning: bool
    deferred_horizon: bool
    branch_actions: int
    branch_new_states: int
    branch_findings: int
    seq_len: int
    open_instance: dict | None
    seen_failed_return_dests: set = field(default_factory=set)
    suspended_at_step: int = -1
    child_branch: str = ""
    child_instance_id: str = ""
    child_parent_sig: str = ""
    child_parent_cluster: str = ""
    expected_resume_mode: str = "return"
    horizon_resolved: bool = False


def _copy_instance(instance) -> dict | None:
    if not instance:
        return None
    return {
        "id": instance.get("id"),
        "branch": instance.get("branch"),
        "len": instance.get("len", 0),
    }


def terminal_violations(events) -> list:
    """One legal sequence_terminal for every branch_start instance."""
    outcomes: dict = {}
    started = []
    extras = []
    for event in events or []:
        iid = event.get("sequence_instance_id")
        kind = event.get("event")
        if kind == "branch_start" and iid:
            if iid not in outcomes:
                outcomes[iid] = []
                started.append(iid)
        elif kind == "sequence_terminal":
            if not iid or iid not in outcomes:
                extras.append({
                    "sequence_instance_id": iid,
                    "outcomes": [event.get("outcome") or ""],
                    "reason": "terminal_without_branch_start",
                })
                continue
            outcomes[iid].append(event.get("outcome") or "")
    bad = list(extras)
    for iid in started:
        got = outcomes.get(iid) or []
        if len(got) != 1 or got[0] not in LEGAL_TERMINALS:
            bad.append({
                "sequence_instance_id": iid,
                "outcomes": list(got),
                "reason": "count" if len(got) != 1 else "illegal",
            })
    return bad


class HorizonHandoffSequenceController(ReturnCycleGuardSequenceController):
    """Structural sequence, exact-repeat escape, final-slot handoff."""

    def __init__(self, mode: str = "structural"):
        super().__init__(mode)
        self._reset_handoff_state()

    def _reset_handoff_state(self) -> None:
        self._stack: list = []
        self._max_depth = 0
        self._stack_depth_at_budget_end = None
        self._active_budget_end = 0
        self._suspended_budget_end = 0
        self._budget_closed = False
        self._witness_violations = 0

    def reset(self):
        super().reset()
        self._reset_handoff_state()

    @property
    def stack_depth(self) -> int:
        return len(self._stack)

    def _cluster(self, sig: str, graph) -> str:
        node = graph.nodes.get(sig) if graph is not None else None
        return (node.cluster_id if node else "") or (sig.split(":")[0] if sig else "")

    def _nested_branch_ready(self, action, state) -> bool:
        if self.mode not in SEQUENCE_LIKE:
            return False
        if state is None or action is None:
            return False
        if not is_hub(state):
            return False
        if not is_branch_click(action, state):
            return False
        if self._open_instance is None:
            return False
        if not self.ledger.active_branch:
            return False
        if self.ledger.returning:
            return False
        if self.ledger.commitment_left <= 0:
            return False
        return True

    def _continuation_applies(self, action, state) -> bool:
        return self._nested_branch_ready(action, state) and self.ledger.commitment_left > 1

    def _handoff_applies(self, action, state) -> bool:
        return self._nested_branch_ready(action, state) and self.ledger.commitment_left == 1

    def _markers(self) -> dict:
        return {
            "return_success": self.ledger.return_success,
            "escape_n": self._escape_n,
            "n_events": len(self.events),
            "active_branch": self.ledger.active_branch,
            "open_id": None if self._open_instance is None else self._open_instance.get("id"),
        }

    def _child_identity(self, n_events: int) -> tuple:
        child_id = ""
        child_branch = ""
        for event in self.events[n_events:]:
            if event.get("event") != "branch_start":
                continue
            child_id = event.get("sequence_instance_id") or child_id
            child_branch = event.get("branch_key") or child_branch
        return child_id, child_branch

    def _emit_for_instance(self, instance, event, step, sig, cluster, branch, extra):
        previous = self._open_instance
        self._open_instance = instance
        try:
            self._emit(event, step, sig, cluster, branch, extra)
        finally:
            self._open_instance = previous

    def _emit_terminal_for(self, instance, step, sig, cluster, outcome, extra=None):
        payload = {
            "outcome": outcome,
            "length": 0 if instance is None else instance.get("len", 0),
        }
        if extra:
            payload.update(extra)
        branch = "" if instance is None else (instance.get("branch") or "")
        self._emit_for_instance(
            instance, "sequence_terminal", step, sig, cluster, branch, payload)

    def _guard_tail(self, was_returning, sig, new_sig, graph, step: int) -> None:
        if not self.ledger.returning:
            self._seen_failed_return_dests = set()
            return
        if not was_returning:
            self._seen_failed_return_dests = set()
        dest = new_sig or ""
        if not dest:
            return
        if dest in self._seen_failed_return_dests:
            self._escape_cycle(step, sig, dest, graph)
            return
        self._seen_failed_return_dests.add(dest)

    def _historical_after(self, sig, action, state, new_state, relation, findings,
                          new_sig, crashed, graph, step: int, *,
                          suppress_branch_start: bool) -> None:
        """Historical action lifecycle. Branch start can be omitted locally."""
        if not self.enabled() or action is None:
            return
        node = graph.nodes.get(sig) if graph else None
        cluster = (node.cluster_id if node else "") or (sig.split(":")[0] if sig else "")
        was_hub = is_hub(state) if state is not None else False
        if not suppress_branch_start:
            if was_hub:
                self._emit("hub_seen", step, sig, cluster)
            if was_hub and is_branch_click(action, state):
                rec = self.ledger.hub(sig, cluster)
                key = branch_key(cluster, action)
                rec.discovered.add(key)
                self._emit("branch_discovered", step, sig, cluster, key)
                if key in rec.started:
                    self.ledger.repeats += 1
                else:
                    rec.started.add(key)
                    self.ledger.started_total += 1
                    self.ledger.sequences_started += 1
                if self._open_instance is not None:
                    self._emit(
                        "sequence_terminal", step, sig, cluster,
                        self._open_instance.get("branch", ""),
                        {"outcome": "lost_parent",
                         "length": self._open_instance.get("len", 0)})
                self._instance_n += 1
                self._open_instance = {
                    "id": f"seq-{self._instance_n:04d}",
                    "branch": key,
                    "len": 1,
                }
                self._emit("branch_start", step, sig, cluster, key)
                self.ledger.active_branch = key
                self.ledger.parent_hub_sig = sig
                self.ledger.parent_hub_cluster = cluster
                self.ledger.branch_actions = 0
                self.ledger.branch_new_states = 0
                self.ledger.branch_findings = 0
                self.ledger._seq_len = 1
                if self.mode in SEQUENCE_LIKE:
                    self.ledger.commitment_left = BRANCH_HORIZON
                self.ledger.returning = False
                if self.mode in CONTEXT_MODES:
                    self._on_struct_branch_start(cluster, sig, key, step)

        if self._open_instance is not None:
            self._emit(
                "sequence_action", step, sig, cluster,
                self._open_instance.get("branch", ""),
                {"action_key": action.key() if action is not None else "",
                 "decision_mode": self.last_label},
            )

        if self.ledger.active_branch:
            self.ledger.branch_actions += 1
            self.ledger._seq_len += 1
            if self.ledger.commitment_left > 0:
                self.ledger.commitment_left -= 1

        if findings:
            self.ledger.branch_findings += 1
        if relation in (NEW, SIMILAR):
            self.ledger.branch_new_states += 1

        if self.mode in FOLLOWUP_LIKE:
            self._record_mutation(sig, action, state, new_state, relation, step)

        if self.last_label == "sequence_followup":
            self.ledger.followup_actions += 1
            self._emit("followup", step, sig, cluster, self.ledger.active_branch)

        if self.mode in CONTEXT_MODES:
            self._update_context_memory(
                sig, action, state, new_state, relation, findings,
                new_sig, graph, step, cluster)

        expire = False
        terminal_reason = None
        if crashed:
            expire = True
            terminal_reason = "crash"
        elif findings and self.mode in SEQUENCE_LIKE:
            expire = True
            terminal_reason = "finding"
        if (self.mode in SEQUENCE_LIKE and self.ledger.commitment_left <= 0
                and self.ledger.active_branch):
            expire = True
            if terminal_reason is None:
                terminal_reason = "horizon"
        if (self.mode in SEQUENCE_LIKE and relation not in (NEW, SIMILAR)
                and not findings):
            if self.ledger.commitment_left <= 0:
                expire = True
                if terminal_reason is None:
                    terminal_reason = "horizon"

        if expire and self.ledger.active_branch and not self.ledger.returning:
            self.ledger.returning = True
            self.ledger.commitment_left = 0
            if terminal_reason in ("finding", "crash") and self._open_instance:
                self._emit(
                    "sequence_terminal", step, sig, cluster,
                    self._open_instance.get("branch", ""),
                    {"outcome": terminal_reason,
                     "fingerprints": _finding_fps(findings)})
                self._open_instance = None
            elif terminal_reason == "horizon":
                self._emit(
                    "sequence_horizon_reached", step, sig, cluster,
                    self.ledger.active_branch)

        if is_return_action(action, state) and self.ledger.returning:
            self._emit(
                "return_attempt", step, sig, cluster, self.ledger.active_branch)

        if self.ledger.returning and new_state is not None:
            self.ledger.return_attempts += 1
            dst_cluster = ""
            if graph and new_sig in graph.nodes:
                dst_cluster = graph.nodes[new_sig].cluster_id
            if (new_sig == self.ledger.parent_hub_sig
                    or (dst_cluster and dst_cluster == self.ledger.parent_hub_cluster)):
                self._complete_branch(step, sig, cluster)

        if self.last_label == "return_hub":
            self.ledger.return_attempts += 1

        self.mutations = [m for m in self.mutations if m.ttl > 0]
        for mutation in self.mutations:
            mutation.ttl -= 1

    def after(self, sig, action, state, new_state, relation, findings,
              new_sig, crashed, graph, step: int):
        if self._continuation_applies(action, state):
            self._continue_nested(
                sig, action, state, new_state, relation, findings,
                new_sig, crashed, graph, step)
            return
        if self._handoff_applies(action, state):
            self._handoff(
                sig, action, state, new_state, relation, findings,
                new_sig, crashed, graph, step)
            return
        before = self._markers()
        super().after(
            sig, action, state, new_state, relation, findings,
            new_sig, crashed, graph, step)
        self._resolve_stack(before, sig, new_sig, graph, step)

    def _continue_nested(self, sig, action, state, new_state, relation,
                         findings, new_sig, crashed, graph, step: int) -> None:
        before = self._markers()
        was_returning = self.ledger.returning
        commitment_before = self.ledger.commitment_left
        cluster = self._cluster(sig, graph)
        key = branch_key(cluster, action)
        outer_id = self._open_instance["id"]
        outer_branch = self.ledger.active_branch
        outer_parent = self.ledger.parent_hub_sig
        outer_parent_cluster = self.ledger.parent_hub_cluster
        self._emit("hub_seen", step, sig, cluster)
        rec = self.ledger.hub(sig, cluster)
        rec.discovered.add(key)
        self._emit("branch_discovered", step, sig, cluster, key)
        if self.mode in CONTEXT_MODES:
            self._on_struct_branch_start(cluster, sig, key, step)
        self._historical_after(
            sig, action, state, new_state, relation, findings,
            new_sig, crashed, graph, step, suppress_branch_start=True)
        self._guard_tail(was_returning, sig, new_sig, graph, step)
        self._emit(
            "nested_continuation", step, sig, cluster, outer_branch,
            {
                "outer_sequence_instance_id": outer_id,
                "outer_branch": outer_branch,
                "outer_parent_hub_sig": outer_parent,
                "outer_parent_hub_cluster": outer_parent_cluster,
                "nested_hub_sig": sig,
                "nested_hub_cluster": cluster,
                "nested_branch": key,
                "commitment_before": commitment_before,
                "commitment_after": self.ledger.commitment_left,
                "sequence_instance_id": outer_id,
            },
        )
        self._resolve_stack(before, sig, new_sig, graph, step)

    def _handoff(self, sig, action, state, new_state, relation, findings,
                 new_sig, crashed, graph, step: int) -> None:
        cluster = self._cluster(sig, graph)
        commitment_before = self.ledger.commitment_left
        outer_actions = self.ledger.branch_actions
        outer_len = self.ledger._seq_len
        frame = HandoffFrame(
            active_branch=self.ledger.active_branch,
            parent_hub_sig=self.ledger.parent_hub_sig,
            parent_hub_cluster=self.ledger.parent_hub_cluster,
            commitment_left=0,
            returning=True,
            deferred_horizon=True,
            branch_actions=outer_actions + 1,
            branch_new_states=self.ledger.branch_new_states,
            branch_findings=self.ledger.branch_findings,
            seq_len=outer_len + 1,
            open_instance=_copy_instance(self._open_instance),
            seen_failed_return_dests=set(self._seen_failed_return_dests),
            suspended_at_step=step,
            child_parent_sig=sig,
            child_parent_cluster=cluster,
            expected_resume_mode="return",
        )
        self._stack.append(frame)
        self._max_depth = max(self._max_depth, len(self._stack))
        # The historical branch-start block would terminal this instance as
        # lost_parent. Detach it first. The outer slot lives only on the frame.
        self._open_instance = None
        self._seen_failed_return_dests = set()
        before = self._markers()
        super().after(
            sig, action, state, new_state, relation, findings,
            new_sig, crashed, graph, step)
        child_id, child_branch = self._child_identity(before["n_events"])
        frame.child_instance_id = child_id or ""
        frame.child_branch = child_branch or self.ledger.active_branch
        outer = frame.open_instance or {}
        self._emit(
            "horizon_handoff_started", step, sig, cluster, frame.child_branch,
            {
                "suspended_sequence_instance_id": outer.get("id"),
                "suspended_branch": frame.active_branch,
                "suspended_parent_hub_sig": frame.parent_hub_sig,
                "suspended_parent_hub_cluster": frame.parent_hub_cluster,
                "outer_commitment_before": commitment_before,
                "stored_commitment": 0,
                "resume_returning": True,
                "deferred_horizon": True,
                "child_branch": frame.child_branch,
                "child_parent_sig": frame.child_parent_sig,
                "child_parent_cluster": frame.child_parent_cluster,
                "child_sequence_instance_id": frame.child_instance_id,
                "child_commitment_after": self.ledger.commitment_left,
                "child_commitment_assigned": BRANCH_HORIZON,
                "stack_depth": len(self._stack),
                "expected_resume_mode": "return",
                "sequence_instance_id": frame.child_instance_id or None,
            },
        )
        self._resolve_stack(before, sig, new_sig, graph, step)

    def _already_terminal(self, iid: str, step=None) -> bool:
        for event in self.events:
            if event.get("event") != "sequence_terminal":
                continue
            if event.get("sequence_instance_id") != iid:
                continue
            if step is not None and event.get("step") != step:
                continue
            return True
        return False

    def _resolution_matches(self, frame: HandoffFrame, before: dict) -> bool:
        child_id = frame.child_instance_id or ""
        child_branch = frame.child_branch or ""
        if not child_id or not child_branch:
            return False
        new_events = self.events[before["n_events"]:]
        terminals = [
            event for event in new_events
            if event.get("event") == "sequence_terminal"
        ]
        term_ids = {
            event.get("sequence_instance_id")
            for event in terminals if event.get("sequence_instance_id")
        }
        if term_ids and term_ids != {child_id}:
            return False
        open_id = before.get("open_id")
        active_branch = before.get("active_branch") or ""
        if open_id == child_id and active_branch == child_branch:
            return True
        if open_id is None and active_branch == child_branch:
            return True
        starts = [
            event for event in new_events if event.get("event") == "branch_start"
        ]
        start_ids = {
            event.get("sequence_instance_id")
            for event in starts if event.get("sequence_instance_id")
        }
        if start_ids == {child_id} and (not term_ids or term_ids == {child_id}):
            return True
        return False

    def _physical_parent(self, frame: HandoffFrame, new_sig, graph):
        dst_cluster = ""
        nodes = getattr(graph, "nodes", {}) if graph is not None else {}
        if new_sig and new_sig in nodes:
            dst_cluster = nodes[new_sig].cluster_id or ""
        exact = bool(frame.child_parent_sig) and new_sig == frame.child_parent_sig
        cluster = bool(dst_cluster) and dst_cluster == (frame.child_parent_cluster or "")
        if exact:
            return True, "exact", dst_cluster
        if cluster:
            return True, "cluster", dst_cluster
        return False, "", dst_cluster

    def _terminal_context(self, child_id: str, step, n_events: int) -> str:
        same = [
            event for event in self.events[n_events:]
            if event.get("event") == "sequence_terminal"
            and event.get("sequence_instance_id") == child_id
        ]
        outcomes = [event.get("outcome") for event in same]
        if "returned" in outcomes:
            return "returned"
        if "finding" in outcomes:
            return "finding_same_step"
        if "crash" in outcomes:
            return "crash_same_step"
        prior = []
        for event in self.events[:n_events]:
            if event.get("event") != "sequence_terminal":
                continue
            if event.get("sequence_instance_id") != child_id:
                continue
            event_step = event.get("step")
            if event_step is None or step is None:
                continue
            if int(event_step) < int(step):
                prior.append(event.get("outcome"))
        if "finding" in prior:
            return "finding_prior"
        if "crash" in prior:
            return "crash_prior"
        return "none"

    def _reject(self, step, sig, graph, frame: HandoffFrame, reason: str, delta: int):
        cluster = self._cluster(sig, graph)
        self._emit(
            "witness_rejection", step, sig, cluster, frame.child_branch,
            {
                "reason": reason,
                "return_success_delta": delta,
                "child_sequence_instance_id": frame.child_instance_id,
                "child_branch": frame.child_branch,
                "stack_depth": len(self._stack),
            },
        )

    def _resolve_stack(self, before: dict, sig, new_sig, graph, step: int) -> None:
        if not self._stack:
            return
        escaped = self._escape_n > before["escape_n"]
        if not escaped:
            for event in self.events[before["n_events"]:]:
                if event.get("event") == "return_cycle_escape":
                    escaped = True
                    break
        if escaped:
            self._unwind(step, sig, graph, "child_return_cycle_escape")
            return
        delta = self.ledger.return_success - before["return_success"]
        if delta < 1:
            return
        frame = self._stack[-1]
        if delta != 1:
            self._reject(step, sig, graph, frame, "return_success_delta", delta)
            return
        if not self._resolution_matches(frame, before):
            self._reject(step, sig, graph, frame, "wrong_child", delta)
            return
        physical, strength, dst_cluster = self._physical_parent(frame, new_sig, graph)
        if not physical:
            self._reject(step, sig, graph, frame, "wrong_parent", delta)
            return
        if self.ledger.active_branch or self.ledger.returning:
            self._reject(step, sig, graph, frame, "obligation_open", delta)
            return
        context = self._terminal_context(frame.child_instance_id, step, before["n_events"])
        if context not in ACCEPTED_CONTEXTS:
            self._reject(step, sig, graph, frame, "no_terminal_evidence", delta)
            return
        self._witness_and_resume(
            frame, step, sig, new_sig, graph, strength, context, delta, dst_cluster)

    def _restore_frame(self, frame: HandoffFrame) -> None:
        ledger = self.ledger
        ledger.active_branch = frame.active_branch
        ledger.parent_hub_sig = frame.parent_hub_sig
        ledger.parent_hub_cluster = frame.parent_hub_cluster
        ledger.commitment_left = frame.commitment_left
        ledger.returning = frame.returning
        ledger.branch_actions = frame.branch_actions
        ledger.branch_new_states = frame.branch_new_states
        ledger.branch_findings = frame.branch_findings
        ledger._seq_len = frame.seq_len
        self._open_instance = _copy_instance(frame.open_instance)
        self._seen_failed_return_dests = set(frame.seen_failed_return_dests)

    def _witness_and_resume(self, frame, step, sig, new_sig, graph, strength,
                            context, delta, dst_cluster) -> None:
        if frame.horizon_resolved:
            self._witness_violations += 1
            return
        depth_before = len(self._stack)
        self._stack.pop()
        source_cluster = self._cluster(sig, graph)
        self._emit(
            "child_parent_witness", step, sig, source_cluster, frame.child_branch,
            {
                "child_sequence_instance_id": frame.child_instance_id,
                "child_branch": frame.child_branch,
                "expected_parent_sig": frame.child_parent_sig,
                "expected_parent_cluster": frame.child_parent_cluster,
                "observed_destination_sig": new_sig or "",
                "observed_destination_cluster": dst_cluster,
                "witness_strength": strength,
                "terminal_context": context,
                "return_success_delta": delta,
                "stack_depth_before_pop": depth_before,
                "sequence_instance_id": frame.child_instance_id,
            },
        )
        self._restore_frame(frame)
        self.ledger.commitment_left = 0
        self.ledger.returning = True
        frame.horizon_resolved = True
        resumed = None if self._open_instance is None else self._open_instance.get("id")
        self._emit(
            "parent_frame_resume_to_return", step, sig, source_cluster,
            frame.active_branch,
            {
                "resumed_sequence_instance_id": resumed,
                "resumed_branch": frame.active_branch,
                "original_parent_hub_sig": frame.parent_hub_sig,
                "original_parent_hub_cluster": frame.parent_hub_cluster,
                "returning": True,
                "commitment_left": 0,
                "stack_depth": len(self._stack),
                "sequence_instance_id": resumed,
            },
        )
        if frame.deferred_horizon:
            self._emit(
                "sequence_horizon_reached", step, sig, source_cluster,
                frame.active_branch,
                {
                    "reason": "horizon_handoff_resolved",
                    "sequence_instance_id": resumed,
                },
            )

    def _unwind(self, step: int, sig, graph, reason: str) -> None:
        frames = list(self._stack)
        depth_before = len(frames)
        self._stack.clear()
        cluster = self._cluster(sig, graph)
        if self._open_instance is not None:
            iid = self._open_instance.get("id")
            if iid and not self._already_terminal(iid, step):
                self._emit(
                    "sequence_terminal", step, sig, cluster,
                    self._open_instance.get("branch", ""),
                    {"outcome": "return_cycle_abandoned", "reason": reason})
            self._open_instance = None
        self.ledger.active_branch = ""
        self.ledger.returning = False
        self.ledger.commitment_left = 0
        self.ledger.parent_hub_sig = ""
        self.ledger.parent_hub_cluster = ""
        self.ledger._seq_len = 0
        self._seen_failed_return_dests = set()
        self._emit(
            "horizon_handoff_unwind", step, sig, cluster, "",
            {
                "reason": reason,
                "stack_depth": 0,
                "stack_depth_before": depth_before,
                "abandoned_frames": depth_before,
            },
        )
        for frame in reversed(frames):
            inst = frame.open_instance
            iid = None if inst is None else inst.get("id")
            if not iid or self._already_terminal(iid):
                continue
            self._emit_terminal_for(
                inst, step, sig, cluster, "horizon_handoff_abandoned",
                {"reason": reason})

    def close_open(self, step: int = -1, sig: str = "", cluster: str = ""):
        if self._budget_closed:
            return
        self._budget_closed = True
        self._stack_depth_at_budget_end = len(self._stack)
        closed = set()
        active = 0
        if self._open_instance is not None:
            active_id = self._open_instance.get("id")
            super().close_open(step, sig, cluster)
            if active_id:
                closed.add(active_id)
            active = 1
        suspended = 0
        frames = list(self._stack)
        self._stack.clear()
        for frame in frames:
            inst = frame.open_instance
            iid = None if inst is None else inst.get("id")
            if inst is None or not iid or iid in closed:
                continue
            if self._already_terminal(iid):
                closed.add(iid)
                continue
            self._emit_terminal_for(
                inst, step, sig, cluster, "budget_end",
                {"reason": "budget_end", "suspended": True})
            closed.add(iid)
            suspended += 1
        self._active_budget_end = active
        self._suspended_budget_end = suspended
        self._open_instance = None

    def metrics(self) -> dict:
        out = super().metrics()
        events = self.events

        def named(event_name: str) -> list:
            return [event for event in events if event.get("event") == event_name]

        continuations = named("nested_continuation")
        handoffs = named("horizon_handoff_started")
        witnesses = named("child_parent_witness")
        exact = [
            event for event in witnesses
            if event.get("witness_strength") == "exact"
        ]
        clustered = [
            event for event in witnesses
            if event.get("witness_strength") == "cluster"
        ]
        same_step = [
            event for event in witnesses
            if event.get("terminal_context") in SAME_STEP_CONTEXTS
        ]
        abandoned = [
            event for event in events
            if event.get("event") == "sequence_terminal"
            and event.get("outcome") == "horizon_handoff_abandoned"
        ]
        resolved = [
            event for event in events
            if event.get("event") == "sequence_horizon_reached"
            and event.get("reason") == "horizon_handoff_resolved"
        ]
        keys = {
            event.get("nested_branch")
            for event in continuations if event.get("nested_branch")
        }
        out["nested_continuation_events"] = len(continuations)
        out["unique_nested_continuations"] = len(keys)
        out["horizon_handoff_started_events"] = len(handoffs)
        out["handoff_child_started_events"] = sum(
            1 for event in handoffs if event.get("child_sequence_instance_id"))
        out["child_parent_witness_events"] = len(witnesses)
        out["child_parent_exact_witness_events"] = len(exact)
        out["child_parent_cluster_witness_events"] = len(clustered)
        out["same_step_terminal_witness_events"] = len(same_step)
        out["witness_rejection_events"] = len(named("witness_rejection"))
        out["parent_frame_resume_to_return_events"] = len(
            named("parent_frame_resume_to_return"))
        out["horizon_handoff_unwind_events"] = len(named("horizon_handoff_unwind"))
        out["max_handoff_stack_depth"] = self._max_depth
        out["handoff_stack_depth_at_budget_end"] = (
            0 if self._stack_depth_at_budget_end is None
            else self._stack_depth_at_budget_end)
        out["handoff_frames_abandoned"] = len(abandoned)
        out["deferred_horizon_events"] = sum(
            1 for event in handoffs if event.get("deferred_horizon") is True)
        out["resolved_deferred_horizon_events"] = len(resolved)
        out["witness_violations"] = self._witness_violations
        out["terminal_accounting_violations"] = len(terminal_violations(events))
        out["active_budget_end_count"] = self._active_budget_end
        out["suspended_budget_end_count"] = self._suspended_budget_end
        return out


class HorizonHandoffReturnGuardGhostPolicy(GhostPolicy):
    """Benchmark-only identity. Does not replace the product default."""

    name = "ghost-structural-horizon-handoff-guard"

    def __init__(self, llm=None, **kwargs):
        kwargs["use_frontier"] = False
        kwargs["sequence_mode"] = "structural"
        super().__init__(llm=llm, **kwargs)
        self.sequence = HorizonHandoffSequenceController("structural")
        self.sequence_mode = "structural"


__all__ = [
    "ACCEPTED_CONTEXTS",
    "LEGAL_TERMINALS",
    "HandoffFrame",
    "HorizonHandoffReturnGuardGhostPolicy",
    "HorizonHandoffSequenceController",
    "terminal_violations",
]
