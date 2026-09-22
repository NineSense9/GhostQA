"""Experimental suspended-parent stack (v0.3.13).

Research-only. Not the product default. Does not replace the v0.3.12
flattening candidate.

When an active non-returning sequence with commitment remaining takes a hub
branch click, the current frame is pushed and the click starts a normal
child sequence. The outer frame resumes only after that child returns to
its own parent. A child return-cycle escape abandons every suspended
ancestor. ``sequence.is_hub`` is never reassigned.

Frame-local fields, snapshotted because a historical branch start overwrites
them:

- active_branch, parent_hub_sig, parent_hub_cluster: the suspended
  sequence's identity and return target
- commitment_left: remaining budget before the child click
- returning: return-phase flag for that frame
- branch_actions, branch_new_states, branch_findings, _seq_len: counters
  the historical branch-start block resets
- _open_instance: the suspended sequence instance
- _seen_failed_return_dests: exact destinations already seen by that
  frame's return phase

Left global because historical branch starts do not scope them to one
sequence: hub records, aggregate counters, StructuralHubMemory, context
stats, mutation TTL list, tried-action context, last delta, local context
id, pending retest, the instance counter, and the event log.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .policy import GhostPolicy
from .return_cycle_guard import ReturnCycleGuardSequenceController
from .sequence import SEQUENCE_LIKE, is_branch_click, is_hub

LEGAL_TERMINALS = frozenset({
    "returned",
    "finding",
    "crash",
    "return_cycle_abandoned",
    "nested_descendant_abandoned",
    "budget_end",
    "lost_parent",
})


@dataclass
class SuspendedParentFrame:
    active_branch: str
    parent_hub_sig: str
    parent_hub_cluster: str
    commitment_left: int
    returning: bool
    branch_actions: int
    branch_new_states: int
    branch_findings: int
    seq_len: int
    open_instance: dict | None
    seen_failed_return_dests: set = field(default_factory=set)
    suspended_at_step: int = -1
    child_branch: str = ""
    child_instance_id: str = ""


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


class SuspendedParentSequenceController(ReturnCycleGuardSequenceController):
    """Structural sequence, exact-repeat escape, suspended parent frames."""

    def __init__(self, mode: str = "structural"):
        super().__init__(mode)
        self._stack: list = []
        self._max_depth = 0
        self._stack_depth_at_budget_end = None
        self._active_budget_end = 0
        self._suspended_budget_end = 0
        self._budget_closed = False

    def reset(self):
        super().reset()
        self._stack = []
        self._max_depth = 0
        self._stack_depth_at_budget_end = None
        self._active_budget_end = 0
        self._suspended_budget_end = 0
        self._budget_closed = False

    @property
    def stack_depth(self) -> int:
        return len(self._stack)

    def _cluster(self, sig: str, graph) -> str:
        node = graph.nodes.get(sig) if graph is not None else None
        return (node.cluster_id if node else "") or (sig.split(":")[0] if sig else "")

    def _snapshot_frame(self, step: int) -> SuspendedParentFrame:
        ledger = self.ledger
        return SuspendedParentFrame(
            active_branch=ledger.active_branch,
            parent_hub_sig=ledger.parent_hub_sig,
            parent_hub_cluster=ledger.parent_hub_cluster,
            commitment_left=ledger.commitment_left,
            returning=bool(ledger.returning),
            branch_actions=ledger.branch_actions,
            branch_new_states=ledger.branch_new_states,
            branch_findings=ledger.branch_findings,
            seq_len=ledger._seq_len,
            open_instance=_copy_instance(self._open_instance),
            seen_failed_return_dests=set(self._seen_failed_return_dests),
            suspended_at_step=step,
        )

    def _restore_frame(self, frame: SuspendedParentFrame) -> None:
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

    def _preservation_applies(self, action, state) -> bool:
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

    def _stack_fields(self, frame, *, depth, reason, active_child_branch, **more):
        inst = None if frame is None else frame.open_instance
        extra = {
            "stack_depth": depth,
            "active_child_branch": active_child_branch or "",
            "parent_hub_sig": "" if frame is None else frame.parent_hub_sig,
            "suspended_branch": "" if frame is None else frame.active_branch,
            "suspended_sequence_instance_id": None if not inst else inst.get("id"),
            "reason": reason,
        }
        extra.update(more)
        return extra

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
        if not child_id and self._open_instance is not None:
            child_id = self._open_instance.get("id") or ""
            child_branch = child_branch or self._open_instance.get("branch") or ""
        return child_id, child_branch

    def _clear_active_sequence(self) -> None:
        self.ledger.active_branch = ""
        self.ledger.returning = False
        self.ledger.commitment_left = 0
        self.ledger.parent_hub_sig = ""
        self.ledger.parent_hub_cluster = ""
        self.ledger._seq_len = 0
        self._open_instance = None
        self._seen_failed_return_dests = set()

    def after(self, sig, action, state, new_state, relation, findings,
              new_sig, crashed, graph, step: int):
        if self._preservation_applies(action, state):
            self._suspend_for_child(
                sig, action, state, new_state, relation, findings,
                new_sig, crashed, graph, step)
            return
        before = self._markers()
        super().after(
            sig, action, state, new_state, relation, findings,
            new_sig, crashed, graph, step)
        self._resolve_stack(before, sig, graph, step)

    def _suspend_for_child(self, sig, action, state, new_state, relation,
                           findings, new_sig, crashed, graph, step: int):
        frame = self._snapshot_frame(step)
        self._stack.append(frame)
        self._max_depth = max(self._max_depth, len(self._stack))
        cluster = self._cluster(sig, graph)
        self._emit(
            "parent_frame_suspended", step, sig, cluster, frame.active_branch,
            self._stack_fields(
                frame, depth=len(self._stack), reason="nested_hub_branch",
                active_child_branch="",
                commitment_left=frame.commitment_left,
            ),
        )
        # Detach the open instance so the frozen branch-start block does not
        # emit lost_parent. The click is then a normal child sequence.
        self._open_instance = None
        self._seen_failed_return_dests = set()
        before = self._markers()
        super().after(
            sig, action, state, new_state, relation, findings,
            new_sig, crashed, graph, step)
        child_id, child_branch = self._child_identity(before["n_events"])
        frame.child_instance_id = child_id or ""
        frame.child_branch = child_branch or self.ledger.active_branch
        self._emit(
            "nested_child_started", step, sig, cluster,
            frame.child_branch,
            self._stack_fields(
                frame, depth=len(self._stack), reason="historical_child_start",
                active_child_branch=frame.child_branch,
                parent_hub_sig=self.ledger.parent_hub_sig,
                child_sequence_instance_id=frame.child_instance_id,
                child_commitment_left=self.ledger.commitment_left,
                suspended_commitment_left=frame.commitment_left,
            ),
        )
        self._resolve_stack(before, sig, graph, step)

    def _resolve_stack(self, before: dict, sig, graph, step: int) -> None:
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
        if self.ledger.return_success > before["return_success"]:
            self._resume_one(step, sig, graph, before)

    def _resume_one(self, step: int, sig, graph, before: dict) -> None:
        frame = self._stack.pop()
        child_branch = frame.child_branch or before.get("active_branch") or ""
        child_id = frame.child_instance_id or before.get("open_id") or ""
        self._restore_frame(frame)
        cluster = self._cluster(sig, graph)
        resumed_id = None if self._open_instance is None else self._open_instance.get("id")
        self._emit(
            "parent_frame_resumed", step, sig, cluster, frame.active_branch,
            self._stack_fields(
                frame, depth=len(self._stack),
                reason="child_returned_to_parent",
                active_child_branch=child_branch,
                resumed_branch=frame.active_branch,
                resumed_parent_hub=frame.parent_hub_sig,
                remaining_commitment=frame.commitment_left,
                child_branch=child_branch,
                child_sequence_instance_id=child_id,
                resumed_sequence_instance_id=resumed_id,
                child_parent_matched=True,
            ),
        )

    def _unwind(self, step: int, sig, graph, reason: str) -> None:
        frames = list(self._stack)
        depth_before = len(frames)
        self._stack.clear()
        cluster = self._cluster(sig, graph)
        top = frames[-1] if frames else None
        self._clear_active_sequence()
        self._emit(
            "nested_stack_unwind", step, sig, cluster,
            "" if top is None else top.active_branch,
            self._stack_fields(
                top, depth=0, reason=reason,
                active_child_branch="" if top is None else top.child_branch,
                stack_depth_before=depth_before,
                abandoned_frames=depth_before,
            ),
        )
        for frame in reversed(frames):
            inst = frame.open_instance
            if inst is not None:
                self._emit_terminal_for(
                    inst, step, sig, cluster, "nested_descendant_abandoned",
                    {"reason": reason})
            self._emit_for_instance(
                inst, "suspended_parent_terminal", step, sig, cluster,
                frame.active_branch,
                self._stack_fields(
                    frame, depth=0, reason=reason,
                    active_child_branch=frame.child_branch,
                    outcome="nested_descendant_abandoned",
                ),
            )

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
            if inst is None or iid in closed:
                continue
            self._emit_terminal_for(
                inst, step, sig, cluster, "budget_end",
                {"reason": "budget_end", "suspended": True})
            self._emit_for_instance(
                inst, "suspended_parent_terminal", step, sig, cluster,
                frame.active_branch,
                self._stack_fields(
                    frame, depth=0, reason="budget_end",
                    active_child_branch=frame.child_branch,
                    outcome="budget_end",
                    stack_depth_at_budget_end=self._stack_depth_at_budget_end,
                ),
            )
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

        resumes = named("parent_frame_resumed")
        unwinds = named("nested_stack_unwind")
        abandoned = [
            event for event in events
            if event.get("event") == "sequence_terminal"
            and event.get("outcome") == "nested_descendant_abandoned"
        ]
        out["suspended_frame_push_events"] = len(named("parent_frame_suspended"))
        out["suspended_frame_resume_events"] = len(resumes)
        out["suspended_frame_unwind_events"] = len(unwinds)
        out["suspended_frames_abandoned"] = len(abandoned)
        out["max_suspended_stack_depth"] = self._max_depth
        out["stack_depth_at_budget_end"] = (
            0 if self._stack_depth_at_budget_end is None
            else self._stack_depth_at_budget_end)
        out["child_sequence_start_events"] = len(named("nested_child_started"))
        out["child_return_resume_events"] = sum(
            1 for event in resumes
            if event.get("reason") == "child_returned_to_parent")
        out["child_escape_unwind_events"] = sum(
            1 for event in unwinds
            if event.get("reason") == "child_return_cycle_escape")
        out["outer_instances_resumed"] = len(resumes)
        out["outer_instances_abandoned"] = len(abandoned)
        out["terminal_accounting_violations"] = len(terminal_violations(events))
        out["active_frame_budget_end_count"] = self._active_budget_end
        out["suspended_frame_budget_end_count"] = self._suspended_budget_end
        return out


class NestedStackReturnGuardGhostPolicy(GhostPolicy):
    """Benchmark-only identity. Does not replace the product default."""

    name = "ghost-structural-nested-stack-guard"

    def __init__(self, llm=None, **kwargs):
        kwargs["use_frontier"] = False
        kwargs["sequence_mode"] = "structural"
        super().__init__(llm=llm, **kwargs)
        self.sequence = SuspendedParentSequenceController("structural")
        self.sequence_mode = "structural"


__all__ = [
    "LEGAL_TERMINALS",
    "NestedStackReturnGuardGhostPolicy",
    "SuspendedParentFrame",
    "SuspendedParentSequenceController",
    "terminal_violations",
]
