"""Take an unstarted hub branch before continuing a return (v0.3.26).

Research-only. Not the product default. The v0.3.24 controller is reused by
subclassing; its module is not modified.

While a sequence is already returning, a hub that still has an unstarted
branch click is not walked past. That click starts a normal child sequence.
The suspended return resumes after the child comes back to this hub. The
suspension is not a horizon handoff.
"""
from __future__ import annotations

from .episode_drain_epoch_guard import (
    EpisodeDrainEpochGuardGhostPolicy,
    EpisodeDrainEpochSequenceController,
)
from .horizon_handoff_guard import HandoffFrame, _copy_instance
from .sequence import (
    CONTEXT_MODES, SEQUENCE_LIKE, branch_key, is_branch_click, is_hub,
    is_return_action,
)

_METRIC_KEYS = (
    "untried_sibling_before_return_selections",
    "untried_sibling_return_suspensions",
)


class UntriedSiblingSequenceController(EpisodeDrainEpochSequenceController):
    """v0.3.24 episode drain, plus one return-yield for an unstarted sibling."""

    def __init__(self, mode: str = "structural"):
        super().__init__(mode)
        self._reset_sibling()

    def _reset_sibling(self) -> None:
        self._sibling_pending = None
        self._sibling_counts = {key: 0 for key in _METRIC_KEYS}

    def reset(self):
        super().reset()
        self._reset_sibling()

    def _sibling_blocked(self) -> bool:
        lease = getattr(self, "_lease", None)
        if isinstance(lease, dict) and lease.get("active"):
            return True
        if getattr(self, "_drain", None) is not None:
            return True
        holding = getattr(self, "_return_holding", None)
        if holding is not None and holding():
            return True
        return False

    def _untried_siblings(self, actions, state, graph, sig: str) -> list:
        cluster = self._cluster(sig, graph)
        rec = self.ledger.hub(sig, cluster)
        pending = []
        for action in actions or []:
            if not is_branch_click(action, state):
                continue
            key = branch_key(cluster, action)
            if self.mode in CONTEXT_MODES:
                hist = self.struct.hub(cluster).branches.get(key)
                if hist is not None and hist.attempts > 0:
                    continue
            elif key in rec.started or key in rec.completed:
                continue
            pending.append(action)
        return pending

    def pick_override(self, actions, state, graph, ctx):
        if self._sibling_blocked():
            return super().pick_override(actions, state, graph, ctx)
        if (
            self.mode in SEQUENCE_LIKE
            and self.ledger.returning
            and is_hub(state)
            and any(is_return_action(action, state) for action in actions or [])
        ):
            sig = "" if not ctx else (ctx.get("sig") or "")
            siblings = self._untried_siblings(actions, state, graph, sig)
            if siblings:
                chosen = siblings[0]
                cluster = self._cluster(sig, graph)
                self._sibling_pending = {
                    "key": branch_key(cluster, chosen),
                    "hub_sig": sig,
                    "hub_cluster": cluster,
                }
                self._sibling_counts["untried_sibling_before_return_selections"] += 1
                self.last_label = "untried_sibling_before_return"
                return chosen
        return super().pick_override(actions, state, graph, ctx)

    def label_for(self, action, state) -> str:
        if (
            self._sibling_pending is not None
            and self.last_label == "untried_sibling_before_return"
        ):
            return self.last_label
        return super().label_for(action, state)

    def _suspend_return(self, sig, action, state, new_state, relation, findings,
                        new_sig, crashed, graph, step: int, pending: dict) -> None:
        cluster = pending.get("hub_cluster") or self._cluster(sig, graph)
        frame = HandoffFrame(
            active_branch=self.ledger.active_branch,
            parent_hub_sig=self.ledger.parent_hub_sig,
            parent_hub_cluster=self.ledger.parent_hub_cluster,
            commitment_left=0,
            returning=True,
            deferred_horizon=False,
            branch_actions=self.ledger.branch_actions,
            branch_new_states=self.ledger.branch_new_states,
            branch_findings=self.ledger.branch_findings,
            seq_len=self.ledger._seq_len,
            open_instance=_copy_instance(self._open_instance),
            seen_failed_return_dests=set(self._seen_failed_return_dests),
            suspended_at_step=step,
            child_parent_sig=pending.get("hub_sig") or sig,
            child_parent_cluster=cluster,
            expected_resume_mode="return",
        )
        self._stack.append(frame)
        self._max_depth = max(self._max_depth, len(self._stack))
        self._sibling_counts["untried_sibling_return_suspensions"] += 1
        self._emit(
            "untried_sibling_return_suspended",
            step,
            sig,
            cluster,
            frame.active_branch,
            {
                "suspended_branch": frame.active_branch,
                "hub_sig": frame.child_parent_sig,
                "hub_cluster": cluster,
                "sibling_key": pending.get("key") or "",
                "stack_depth": len(self._stack),
                "sequence_instance_id": None if frame.open_instance is None else frame.open_instance.get("id"),
            },
        )
        self._open_instance = None
        self.ledger.active_branch = ""
        self.ledger.returning = False
        self.ledger.commitment_left = 0
        self.ledger.parent_hub_sig = ""
        self.ledger.parent_hub_cluster = ""
        self._seen_failed_return_dests = set()
        before_n = len(self.events)
        super().after(
            sig, action, state, new_state, relation, findings,
            new_sig, crashed, graph, step)
        child_id, child_branch = self._child_identity(before_n)
        frame.child_instance_id = child_id or ""
        frame.child_branch = child_branch or self.ledger.active_branch

    def after(self, sig, action, state, new_state, relation, findings,
              new_sig, crashed, graph, step: int):
        pending = self._sibling_pending
        if pending is not None:
            self._sibling_pending = None
            cluster = self._cluster(sig, graph)
            clicked = "" if action is None else branch_key(cluster, action)
            if clicked and clicked == pending.get("key"):
                self._suspend_return(
                    sig, action, state, new_state, relation, findings,
                    new_sig, crashed, graph, step, pending)
                return
        super().after(
            sig, action, state, new_state, relation, findings,
            new_sig, crashed, graph, step)

    def metrics(self) -> dict:
        out = super().metrics()
        out.update(self._sibling_counts)
        return out


class UntriedSiblingGuardGhostPolicy(EpisodeDrainEpochGuardGhostPolicy):
    """Benchmark-only identity. Does not replace the product default."""

    name = "ghost-structural-untried-sibling-guard"

    def __init__(self, llm=None, **kwargs):
        kwargs["use_frontier"] = False
        kwargs["sequence_mode"] = "structural"
        super().__init__(llm=llm, **kwargs)
        self.sequence = UntriedSiblingSequenceController("structural")
        self.sequence_mode = "structural"
        self.use_frontier = False

    def maybe_relocate(self, graph, state, actions, ctx):
        seq = self.sequence
        if not isinstance(seq, UntriedSiblingSequenceController) or not seq.enabled():
            return None
        return seq.maybe_debt_relocate(
            graph, state, actions, ctx, payload_policy=self.payload_policy)


__all__ = [
    "UntriedSiblingGuardGhostPolicy",
    "UntriedSiblingSequenceController",
]
