"""Experimental nested-hub parent preservation (v0.3.12).

Isolated from the frozen SequenceController and the frozen v0.3.9
return-cycle guard. Benchmark-only. Not the product default.

One semantic delta. Before the branch-start mutation, when every condition
below holds, the active outer sequence absorbs the click instead of dying
as lost_parent:

- mode is sequence-like
- current state is a hub
- chosen action is a branch click
- an outer sequence instance is open
- ledger.active_branch is non-empty
- ledger.returning is false
- ledger.commitment_left > 0

The click is discovered, audited as nested_branch_followup, and then
processed by the frozen after() implementation with hub detection hidden
for that call only. Hiding the hub skips the frozen branch-start block
(lost_parent, new instance, parent overwrite, commitment reset) and leaves
relation, finding, crash, horizon, return, and exact-signature escape
behavior on the frozen code path. The hub function is restored before
after() returns.

Ledger policy, candidate-only: the nested branch is recorded in
_nested_followed and its structural attempt counter is incremented the
same way a historical branch_start would, so later scoring does not treat
the traversed branch as never-tried. It is not added to BranchRec.started,
branch_start is not emitted, and sequence_instances_started does not grow.

No parent stack. No threshold N. No URL or app condition.
"""
from __future__ import annotations

from .policy import GhostPolicy
from .return_cycle_guard import ReturnCycleGuardSequenceController
from .sequence import (
    CONTEXT_MODES, SEQUENCE_LIKE, SequenceController, branch_key,
    is_branch_click, is_hub,
)
from . import sequence as sequence_mod


class NestedHubPreservingSequenceController(ReturnCycleGuardSequenceController):
    """Structural sequence, exact-repeat return escape, nested-hub preservation."""

    def __init__(self, mode: str = "structural"):
        super().__init__(mode)
        self._nested_followed: set = set()
        self._nested_followup_n = 0

    def reset(self):
        super().reset()
        self._nested_followed = set()
        self._nested_followup_n = 0

    def _cluster(self, sig: str, graph) -> str:
        node = graph.nodes.get(sig) if graph is not None else None
        return (node.cluster_id if node else "") or (sig.split(":")[0] if sig else "")

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

    def _absorb_nested_branch(self, sig, action, state, graph, step: int):
        cluster = self._cluster(sig, graph)
        key = branch_key(cluster, action)
        outer_id = self._open_instance["id"]
        commitment_before = self.ledger.commitment_left
        self._emit("hub_seen", step, sig, cluster)
        rec = self.ledger.hub(sig, cluster)
        rec.discovered.add(key)
        self._emit("branch_discovered", step, sig, cluster, key)
        self._emit(
            "nested_branch_followup", step, sig, cluster,
            self.ledger.active_branch,
            {
                "outer_branch": self.ledger.active_branch,
                "outer_parent_hub_sig": self.ledger.parent_hub_sig,
                "outer_parent_hub_cluster": self.ledger.parent_hub_cluster,
                "nested_hub_sig": sig,
                "nested_hub_cluster": cluster,
                "nested_branch_key": key,
                "commitment_left_before": commitment_before,
                "sequence_instance_id": outer_id,
            },
        )
        self._nested_followed.add(key)
        self._nested_followup_n += 1
        if self.mode in CONTEXT_MODES:
            self._on_struct_branch_start(cluster, sig, key, step)

    def after(self, sig, action, state, new_state, relation, findings,
              new_sig, crashed, graph, step: int):
        if not self._preservation_applies(action, state):
            return super().after(
                sig, action, state, new_state, relation, findings,
                new_sig, crashed, graph, step)
        self._absorb_nested_branch(sig, action, state, graph, step)
        # Frozen after() starts a new sequence only when is_hub is true.
        # Hide that for this call so the rest of the lifecycle stays frozen.
        real_is_hub = sequence_mod.is_hub

        def _hide_hub(*_args, **_kwargs):
            return False

        sequence_mod.is_hub = _hide_hub
        try:
            return super().after(
                sig, action, state, new_state, relation, findings,
                new_sig, crashed, graph, step)
        finally:
            sequence_mod.is_hub = real_is_hub

    def metrics(self) -> dict:
        out = super().metrics()
        followed = [
            event for event in self.events
            if event.get("event") == "nested_branch_followup"
        ]
        keys = {
            event.get("nested_branch_key")
            for event in followed if event.get("nested_branch_key")
        }
        out["nested_branch_followup_events"] = len(followed)
        out["unique_nested_branches_followed"] = len(keys)
        out["nested_preemption_avoided_events"] = len(followed)
        return out


class NestedHubReturnGuardGhostPolicy(GhostPolicy):
    """Benchmark-only identity. Does not replace the product default."""

    name = "ghost-structural-nested-return-guard"

    def __init__(self, llm=None, **kwargs):
        kwargs["use_frontier"] = False
        kwargs["sequence_mode"] = "structural"
        super().__init__(llm=llm, **kwargs)
        self.sequence = NestedHubPreservingSequenceController("structural")
        self.sequence_mode = "structural"


# Re-exported so identity checks can see the frozen base without editing it.
__all__ = [
    "NestedHubPreservingSequenceController",
    "NestedHubReturnGuardGhostPolicy",
    "SequenceController",
]
