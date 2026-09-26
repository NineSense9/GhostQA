"""Yield to an untried branch only on the return's own parent hub (v0.3.27).

Research-only. Not the product default. The v0.3.26 controller is reused by
subclassing; its module is not modified.

A return that is still passing through some other hub keeps going. The
untried-sibling yield runs only when the current cluster is the active
return's parent hub.
"""
from __future__ import annotations

from .episode_drain_epoch_guard import EpisodeDrainEpochSequenceController
from .untried_sibling_guard import (
    UntriedSiblingGuardGhostPolicy,
    UntriedSiblingSequenceController,
)


class ParentHubSiblingSequenceController(UntriedSiblingSequenceController):
    """v0.3.26 sibling yield, restricted to the return's parent hub."""

    def _return_is_in_transit(self, graph, ctx) -> bool:
        if not self.ledger.returning:
            return False
        parent = self.ledger.parent_hub_cluster or ""
        if not parent:
            return False
        sig = "" if not ctx else (ctx.get("sig") or "")
        return self._cluster(sig, graph) != parent

    def pick_override(self, actions, state, graph, ctx):
        if self._return_is_in_transit(graph, ctx):
            return EpisodeDrainEpochSequenceController.pick_override(
                self, actions, state, graph, ctx)
        return super().pick_override(actions, state, graph, ctx)


class ParentHubSiblingGuardGhostPolicy(UntriedSiblingGuardGhostPolicy):
    """Benchmark-only identity. Does not replace the product default."""

    name = "ghost-structural-parent-hub-sibling-guard"

    def __init__(self, llm=None, **kwargs):
        kwargs["use_frontier"] = False
        kwargs["sequence_mode"] = "structural"
        super().__init__(llm=llm, **kwargs)
        self.sequence = ParentHubSiblingSequenceController("structural")
        self.sequence_mode = "structural"
        self.use_frontier = False

    def maybe_relocate(self, graph, state, actions, ctx):
        seq = self.sequence
        if not isinstance(seq, ParentHubSiblingSequenceController) or not seq.enabled():
            return None
        return seq.maybe_debt_relocate(
            graph, state, actions, ctx, payload_policy=self.payload_policy)


__all__ = [
    "ParentHubSiblingGuardGhostPolicy",
    "ParentHubSiblingSequenceController",
]
